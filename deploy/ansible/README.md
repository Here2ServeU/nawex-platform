# Ansible: Linux Security Baseline

`roles/rhel_baseline` applies a CIS-style baseline to RHEL, Rocky Linux and AlmaLinux 8/9. It covers
the hosts Kubernetes doesn't manage: bastions, database VMs, and the VMs migrated to OpenShift
Virtualization by MTV. Container hardening is handled separately, by the Helm chart's security
contexts and the OPA/Kyverno admission policies.

```bash
cd deploy/ansible
ansible-galaxy collection install -r requirements.yml
ansible-playbook playbooks/baseline.yml --check --diff         # audit only: report drift, change nothing
ansible-playbook playbooks/baseline.yml                        # enforce
ansible-playbook playbooks/baseline.yml --tags cis_5_2         # one CIS section (SSH)
```

| Tag | CIS section | What it enforces |
|---|---|---|
| `cis_1` | Initial setup | Unused filesystems and USB storage disabled; `/tmp` and `/dev/shm` mounted nodev/nosuid/noexec; AIDE file integrity with a daily check; core dumps off; SELinux enforcing; login banners; system crypto policy |
| `cis_2` | Services | chrony time sync; insecure packages (telnet, rsh, tftp, ...) removed; unneeded services masked |
| `cis_3` | Network | sysctl hardening (redirects, source routing, rp_filter, syncookies, ASLR); firewalld default-deny, opened only for the services you list |
| `cis_4` | Logging and auditing | auditd rules for identity, time, network config, SELinux, logins and sessions, permission changes, denied access, sudo and kernel modules, made immutable until reboot; persistent journald |
| `cis_5` | Access | sshd drop-in (no root, no passwords, AllowGroups, timeouts), checked with `sshd -t` before reload; sudo logging; pwquality; faillock; password ageing; idle timeout; umask 027 |
| `cis_6` | Maintenance | Permissions on sensitive files; fails the run if any account has an empty password; security-only updates via dnf-automatic (download only by default) |

**Safety.** SSH is allowed in firewalld *before* the default zone switches to `drop`, and sshd and
sudoers changes are validated before they are applied. A bad template therefore can't lock you out.
Level 2 or disruptive controls (the FUTURE crypto policy, applying patches automatically) are off by
default. Turn them on per group in `group_vars`.

**Drift detection.** Run the playbook nightly in `--check` mode (from AWX/AAP or CI); every
`changed` result is drift. For a formal benchmark score, run OpenSCAP:
`oscap xccdf eval --profile cis_server_l1 ...`.

**Test locally.** `ansible-playbook --syntax-check playbooks/baseline.yml` runs in CI. For a real
run, use a RHEL UBI or Rocky container or VM with Molecule.
