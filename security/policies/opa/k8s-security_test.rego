package golden.k8s.security_test

import rego.v1

import data.golden.k8s.security

good_deployment := {
	"kind": "Deployment",
	"spec": {"template": {"spec": {
		"securityContext": {"runAsNonRoot": true},
		"containers": [{
			"name": "api",
			"image": "ghcr.io/here2serveu/golden-platform:0.1.0",
			"securityContext": {
				"allowPrivilegeEscalation": false,
				"capabilities": {"drop": ["ALL"]},
			},
		}],
	}}},
}

test_good_deployment_allowed if {
	security.allow with input as good_deployment
}

test_root_pod_denied if {
	pod := {
		"kind": "Pod",
		"spec": {"containers": [{"name": "x", "image": "busybox:1.36", "securityContext": {"privileged": true}}]},
	}
	count(security.deny) > 0 with input as pod
	not security.allow with input as pod
}

test_latest_tag_denied if {
	bad := json.patch(good_deployment, [{"op": "replace", "path": "/spec/template/spec/containers/0/image", "value": "nginx:latest"}])
	"container api must not use the :latest tag" in security.deny with input as bad
}
