"""GPU optimisation and VMware → OpenShift migration domains."""

from __future__ import annotations

import yaml

from golden.decision import DecisionEngine, evaluate_risk, evaluate_severity
from golden.gpu import GPUSample, analyze_fleet, make_gpu_fleet, nodes_freeable, parse_nvidia_smi_csv
from golden.migration import (
    VM,
    Disk,
    assess_inventory,
    assess_vm,
    build_wave_manifests,
    load_inventory,
    plan_waves,
    sample_inventory,
    write_wave_manifests,
)


# ----------------------------------------------------------------------------- GPU
def test_parse_nvidia_smi():
    csv_text = (
        "0, GPU-abc, NVIDIA H100 80GB HBM3, 87, 40960, 81920, 71, 612.5, 700.00, 0\n"
        "1, GPU-def, NVIDIA H100 80GB HBM3, 0, 512, 81920, 34, 70.1, 700.00, [N/A]\n"
    )
    samples = parse_nvidia_smi_csv(csv_text, node="n1")
    assert [s.index for s in samples] == [0, 1]
    assert samples[0].memory_used_pct == 50.0 and samples[0].memory_total_gb == 80.0
    assert samples[1].ecc_errors == 0


def test_hot_fleet_raises_risks_and_recommendations():
    report = analyze_fleet(make_gpu_fleet(scenario="hot"))
    assert report.hot_gpus >= 8 and report.hardware_faults == 1
    assert report.risk_flags["gpu_thermal_risk"] == "critical"
    assert report.risk_flags["gpu_hardware_risk"] == "critical"
    actions = {r["action"] for r in report.recommendations}
    assert {"migrate_gpu_workload", "reclaim_idle_gpus"} <= actions
    assert report.projected_annual_savings_usd > 0


def test_efficient_fleet_is_quiet():
    report = analyze_fleet(make_gpu_fleet(scenario="efficient"))
    assert report.idle_gpus == 0 and "gpu_idle_risk" not in report.risk_flags


def test_bin_packing_frees_nodes():
    samples = [GPUSample(node=f"n{n}", index=i, utilization_pct=20) for n in range(4) for i in range(2)]
    assert nodes_freeable(samples) == 2  # 8 GPUs × 20% → 3 GPUs at ≤70% → 2 nodes of 2 GPUs


# ----------------------------------------------------------------------------- migration
def test_sample_inventory_assessment_catches_blockers():
    by_vm = {a.vm: a for a in (assess_vm(vm) for vm in sample_inventory())}
    assert by_vm["erp-db-01"].readiness == "blocked"
    assert "RDM_PHYSICAL" in {f.code for f in by_vm["erp-db-01"].findings}
    assert {f.code for f in by_vm["mfgw-01"].findings} >= {"UNSUPPORTED_OS", "PASSTHROUGH"}
    assert by_vm["fileserver-01"].migration_type == "warm"
    summary = assess_inventory(sample_inventory())["summary"]
    assert summary["blocked"] >= 2 and summary["vms"] == len(sample_inventory())


def test_clean_vm_is_ready():
    vm = VM("web-01", "Red Hat Enterprise Linux 9 (64-bit)", 2, 4096, disks=[Disk("d1", 40, "ds1")])
    result = assess_vm(vm)
    assert result.readiness == "ready" and result.migration_type == "cold"


def test_wave_plan_respects_dependencies_and_blockers():
    vms = sample_inventory(apps_multiplier=2)
    plan = plan_waves(vms, max_vms_per_wave=6)
    planned = [name for wave in plan.waves for name in wave.vms]
    assert len(planned) == len(set(planned))  # no VM in two waves
    assert plan.waves[0].pilot
    blocked_apps = {app for item in plan.backlog for app in item["applications"]}
    assert "erp" in blocked_apps  # whole erp move group held back by the RDM blocker
    for wave in plan.waves:
        apps = {vm.application for vm in vms if vm.name in wave.vms}
        for app in apps:  # move groups never split across waves
            assert {vm.name for vm in vms if vm.application == app} <= set(wave.vms)
    crit = {"low": 0, "medium": 1, "high": 2, "mission_critical": 3}
    order = [max(crit[vm.criticality] for vm in vms if vm.name in w.vms) for w in plan.waves]
    assert order == sorted(order)  # riskiest apps migrate last


def test_mtv_manifests(tmp_path):
    vms = sample_inventory()
    plan = plan_waves(vms)
    docs = build_wave_manifests(plan.waves[0], vms)
    kinds = [d["kind"] for d in docs]
    assert kinds == ["NetworkMap", "StorageMap", "Plan", "Migration"]
    assert all(d["apiVersion"] == "forklift.konveyor.io/v1beta1" for d in docs)
    plan_doc = docs[2]
    assert {v["name"] for v in plan_doc["spec"]["vms"]} == set(plan.waves[0].vms)
    files = write_wave_manifests(tmp_path, plan.waves, vms)
    kustomizations = [f for f in files if f.name == "kustomization.yaml"]
    assert len(kustomizations) == len(plan.waves)
    for f in files:
        assert yaml.safe_load(f.read_text())


def test_rvtools_loader(tmp_path):
    (tmp_path / "RVTools_tabvInfo.csv").write_text(
        "VM,Powerstate,CPUs,Memory,OS according to the configuration file,Firmware,Cluster,Folder,Template\n"
        "app-01,poweredOn,4,8192,Red Hat Enterprise Linux 8 (64-bit),efi,cl1,/Apps/crm,False\n"
        "tmpl-01,poweredOff,2,2048,Red Hat Enterprise Linux 8 (64-bit),bios,cl1,/Templates,True\n"
    )
    (tmp_path / "RVTools_tabvDisk.csv").write_text(
        "VM,Disk,Capacity MiB,Raw,Disk Mode,Sharing mode,Path\n"
        "app-01,Hard disk 1,102400,False,persistent,sharingNone,[ds-01] app-01/app-01.vmdk\n"
    )
    (tmp_path / "RVTools_tabvNetwork.csv").write_text("VM,Network,IPv4 Address\napp-01,VLAN-10,10.0.0.5\n")
    vms = load_inventory(tmp_path)
    assert [vm.name for vm in vms] == ["app-01"]  # templates skipped
    vm = vms[0]
    assert vm.application == "crm" and vm.disks[0].capacity_gb == 100 and vm.disks[0].datastore == "ds-01"
    assert vm.nics[0].network == "VLAN-10"


# ----------------------------------------------------------------------------- decision engine
def test_risk_and_severity_bands():
    assert [evaluate_risk(s) for s in (0.1, 0.5, 0.7, 0.9)] == ["low", "medium", "high", "critical"]
    assert evaluate_severity("critical", "mission_critical") == "SEV1"
    assert evaluate_severity("low", "low") == "SEV4"


def test_decision_engine_routes_and_governs(governor):
    engine = DecisionEngine(governor=governor)
    fraud = engine.decide({"fraud_score": 0.97})
    assert fraud.incident_class == "security.fraud"
    assert fraud.recommended_action == "isolate_fraud_transactions"
    assert fraud.outcome == "simulate"  # dry_run default
    calm = engine.decide({"latency_ms": 50})
    assert calm.recommended_action is None and calm.outcome == "no_action"
    assert [d.decision_id for d in engine.history()] == [calm.decision_id, fraud.decision_id]
