output "support_gateway_fqdn" {
  description = "FQDN for the support gateway"
  value       = "${cloudflare_record.support_gateway.name}.wopr.systems"
}

output "sshca_fqdn" {
  description = "FQDN for the SSH CA"
  value       = "${cloudflare_record.sshca.name}.wopr.systems"
}

output "auth_fqdn" {
  description = "FQDN for the auth endpoint"
  value       = "${cloudflare_record.auth.name}.wopr.systems"
}

output "support_gateway_record_id" {
  description = "Cloudflare record ID for support gateway"
  value       = cloudflare_record.support_gateway.id
}

output "sshca_record_id" {
  description = "Cloudflare record ID for SSH CA"
  value       = cloudflare_record.sshca.id
}
