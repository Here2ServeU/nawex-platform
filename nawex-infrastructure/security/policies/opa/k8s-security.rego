package nawex.k8s.security

default allow = true

deny[msg] {
  input.kind == "Pod"
  c := input.spec.containers[_]
  not c.securityContext.runAsNonRoot
  msg := sprintf("container %s must set runAsNonRoot=true", [c.name])
}

deny[msg] {
  input.kind == "Pod"
  c := input.spec.containers[_]
  c.securityContext.privileged == true
  msg := sprintf("container %s must not run privileged", [c.name])
}
