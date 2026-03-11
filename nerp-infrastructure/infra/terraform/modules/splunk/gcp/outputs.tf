output "splunk_public_ip" {
  description = "Splunk VM public IP"
  value       = google_compute_instance.splunk.network_interface[0].access_config[0].nat_ip
}

output "splunk_web_url" {
  value = "http://${google_compute_instance.splunk.network_interface[0].access_config[0].nat_ip}:8000"
}

output "splunk_hec_endpoint" {
  value = "http://${google_compute_instance.splunk.network_interface[0].access_config[0].nat_ip}:8088/services/collector"
}
