output "splunk_public_ip" {
  description = "Public IP address of the Splunk EC2 instance"
  value       = aws_instance.splunk.public_ip
}

output "splunk_web_url" {
  description = "URL for Splunk Web UI"
  value       = "http://${aws_instance.splunk.public_ip}:8000"
}

output "splunk_hec_endpoint" {
  description = "Splunk HEC endpoint URL"
  value       = "http://${aws_instance.splunk.public_ip}:8088/services/collector"
}
