# Kubernetes workload security baseline for the Golden platform.
# Evaluate against a Pod, or a Deployment/StatefulSet/DaemonSet/Job manifest:
#   opa eval -d security/policies/opa -i manifest.json 'data.golden.k8s.security.deny'
package golden.k8s.security

import rego.v1

default allow := false

allow if count(deny) == 0

workload_kinds := {"Deployment", "StatefulSet", "DaemonSet", "ReplicaSet", "Job"}

pod_spec := input.spec if input.kind == "Pod"

pod_spec := input.spec.template.spec if input.kind in workload_kinds

pod_spec := input.spec.jobTemplate.spec.template.spec if input.kind == "CronJob"

containers contains c if {
	some c in pod_spec.containers
}

containers contains c if {
	some c in pod_spec.initContainers
}

run_as_non_root(c) if c.securityContext.runAsNonRoot == true

run_as_non_root(c) if {
	not c.securityContext.runAsNonRoot == false
	pod_spec.securityContext.runAsNonRoot == true
}

deny contains msg if {
	some c in containers
	not run_as_non_root(c)
	msg := sprintf("container %s must run as non-root (runAsNonRoot=true)", [c.name])
}

deny contains msg if {
	some c in containers
	c.securityContext.privileged == true
	msg := sprintf("container %s must not run privileged", [c.name])
}

deny contains msg if {
	some c in containers
	not c.securityContext.allowPrivilegeEscalation == false
	msg := sprintf("container %s must set allowPrivilegeEscalation=false", [c.name])
}

deny contains msg if {
	some c in containers
	not "ALL" in object.get(c, ["securityContext", "capabilities", "drop"], [])
	msg := sprintf("container %s must drop ALL capabilities", [c.name])
}

deny contains msg if {
	some c in containers
	endswith(c.image, ":latest")
	msg := sprintf("container %s must not use the :latest tag", [c.name])
}

deny contains msg if {
	pod_spec.hostNetwork == true
	msg := "pods must not use hostNetwork"
}
