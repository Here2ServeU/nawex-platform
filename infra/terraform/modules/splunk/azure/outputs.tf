output "splunk_public_ip" {
  description = "Public IP of Splunk VM"
  value       = azurerm_public_ip.splunk_pip.ip_address
}

output "splunk_web_url" {
  value = "http://${azurerm_public_ip.splunk_pip.ip_address}:8000"
}

output "splunk_hec_endpoint" {
  value = "http://${azurerm_public_ip.splunk_pip.ip_address}:8088/services/collector"
}
