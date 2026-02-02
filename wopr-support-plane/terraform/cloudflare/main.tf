provider "cloudflare" {
  api_token = var.cloudflare_api_token
}

# --- WOPR Core Support Plane DNS Records ---

resource "cloudflare_record" "support_gateway" {
  zone_id = var.cloudflare_zone_id_wopr
  name    = "support-gateway"
  content = var.nodez3r0_vps_ipv4
  type    = "A"
  ttl     = 1 # Auto when proxied
  proxied = var.proxy_enabled

  comment = "WOPR Support Gateway - managed by Terraform"
}

resource "cloudflare_record" "sshca" {
  zone_id = var.cloudflare_zone_id_wopr
  name    = "sshca"
  content = var.nodez3r0_vps_ipv4
  type    = "A"
  ttl     = 1
  proxied = false # SSH-CA needs direct connection, no proxy

  comment = "WOPR SSH CA - managed by Terraform"
}

resource "cloudflare_record" "auth" {
  zone_id = var.cloudflare_zone_id_wopr
  name    = "auth"
  content = var.nodez3r0_vps_ipv4
  type    = "A"
  ttl     = 1
  proxied = var.proxy_enabled

  comment = "WOPR Authentik auth - managed by Terraform"
}

# --- Optional PFTP Records ---

resource "cloudflare_record" "pftp_auth" {
  count = var.cloudflare_zone_id_pftp != "" && var.pftp_vps_ipv4 != "" ? 1 : 0

  zone_id = var.cloudflare_zone_id_pftp
  name    = "auth"
  content = var.pftp_vps_ipv4
  type    = "A"
  ttl     = 1
  proxied = var.proxy_enabled

  comment = "PFTP Authentik auth - managed by Terraform"
}

resource "cloudflare_record" "pftp_main" {
  count = var.cloudflare_zone_id_pftp != "" && var.pftp_vps_ipv4 != "" ? 1 : 0

  zone_id = var.cloudflare_zone_id_pftp
  name    = "pftp"
  content = var.pftp_vps_ipv4
  type    = "A"
  ttl     = 1
  proxied = var.proxy_enabled

  comment = "PFTP main site - managed by Terraform"
}
