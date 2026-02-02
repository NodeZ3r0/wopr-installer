variable "cloudflare_api_token" {
  description = "Cloudflare API token with DNS edit permissions"
  type        = string
  sensitive   = true

  validation {
    condition     = length(var.cloudflare_api_token) > 0
    error_message = "cloudflare_api_token must not be empty. Halting."
  }
}

variable "cloudflare_zone_id_wopr" {
  description = "Cloudflare Zone ID for wopr.systems"
  type        = string

  validation {
    condition     = length(var.cloudflare_zone_id_wopr) == 32
    error_message = "cloudflare_zone_id_wopr must be a 32-character hex string."
  }
}

variable "nodez3r0_vps_ipv4" {
  description = "Public IPv4 address of the NodeZ3r0 VPS"
  type        = string

  validation {
    condition     = can(regex("^\\d{1,3}\\.\\d{1,3}\\.\\d{1,3}\\.\\d{1,3}$", var.nodez3r0_vps_ipv4))
    error_message = "nodez3r0_vps_ipv4 must be a valid IPv4 address."
  }
}

variable "cloudflare_zone_id_pftp" {
  description = "Cloudflare Zone ID for powerforthepeople.party (optional)"
  type        = string
  default     = ""
}

variable "pftp_vps_ipv4" {
  description = "Public IPv4 address of the PFTP VPS (optional)"
  type        = string
  default     = ""
}

variable "proxy_enabled" {
  description = "Whether to enable Cloudflare proxy (orange cloud) on web-facing records"
  type        = bool
  default     = true
}
