output "splunk_public_ip" {
  description = "Public IP of Splunk OCI instance"
  value       = oci_core_instance.splunk.public_ip
}

output "splunk_web_url" {
  value = "http://${oci_core_instance.splunk.public_ip}:8000"
}

output "splunk_hec_endpoint" {
  value = "http://${oci_core_instance.splunk.public_ip}:8088/services/collector"
}
