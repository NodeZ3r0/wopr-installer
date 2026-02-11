# WOPR Sovereign Suite Installer

One-click deployable personal cloud on user-owned VPS infrastructure.

**Target Market:** USA (v1.0)
**Version:** 1.5

## Overview

WOPR provisions self-hosted personal clouds across multiple VPS providers. Each installation is your **Beacon** - a lifeboat for digital freedom, running on infrastructure you own and control. No Big Tech dependency, no vendor lock-in.

Beacons connect back to WOPR Lighthouses for updates, support, and optional services - but your data stays with you.

This installer provisions and configures WOPR instances across multiple VPS providers.

Users choose their preferred:
- **Geographic region** (US West, US Central, US East)
- **VPS provider** (Hetzner, Vultr, DigitalOcean, Linode)
- **Datacenter location** (specific city)

## Directory Structure

```
wopr-installer/
├── manifest.json           # Installer manifest and bundle definitions
├── requirements.txt        # Python dependencies
├── scripts/
│   ├── wopr_common.sh      # Shared bash helpers
│   └── wopr_install.sh     # Main installation orchestrator
├── templates/              # Configuration templates
├── modules/                # Module-specific installers
├── control_plane/
│   ├── provision.py        # Main provisioning orchestrator
│   └── providers/
│       ├── base.py         # Abstract provider interface
│       ├── registry.py     # Provider registration
│       ├── plan_registry.py # WOPR tier to plan mapping
│       ├── hetzner.py      # Hetzner Cloud adapter
│       ├── vultr.py        # Vultr adapter (via libcloud)
│       ├── digitalocean.py # DigitalOcean adapter (via libcloud)
│       ├── linode.py       # Linode/Akamai adapter (via libcloud)
│       ├── ovh.py          # OVHcloud adapter (via libcloud)
│       └── byo.py          # Bring Your Own VPS adapter
└── config/                 # Runtime configuration
```

## Supported Providers (v1.0 - US Focus)

| Provider | US Datacenters | Cheapest Plan | Best For |
|----------|----------------|---------------|----------|
| **Hetzner** | Ashburn VA, Hillsboro OR | $4.49/mo | Price/performance |
| **Vultr** | 8 locations | $10.00/mo | Most US locations |
| **Linode** | 7 locations | $5.00/mo | Akamai network |
| **DigitalOcean** | SF, NYC | $12.00/mo | Developer experience |
| **BYO** | Any | - | Existing infrastructure |

### US Datacenter Coverage

**US West (CA, OR, WA)**
- Hetzner: Hillsboro OR
- Vultr: Los Angeles, Silicon Valley, Seattle
- Linode: Los Angeles, Seattle
- DigitalOcean: San Francisco

**US Central (TX, IL)**
- Vultr: Dallas, Chicago
- Linode: Dallas, Chicago

**US East (NY, NJ, VA, GA, FL)**
- Hetzner: Ashburn VA
- Vultr: Newark NJ, Atlanta, Miami
- Linode: Newark NJ, Atlanta, Miami
- DigitalOcean: New York

## Bundles & Resource Tiers

| Bundle | Tier | Min CPU | Min RAM | Min Disk | Use Case |
|--------|------|---------|---------|----------|----------|
| personal | low | 2 vCPU | 4 GB | 40 GB | Privacy-focused individuals |
| creator | medium | 4 vCPU | 8 GB | 80 GB | Artists, writers, sellers |
| developer | medium | 4 vCPU | 8 GB | 80 GB | Code ownership + AI |
| professional | high | 8 vCPU | 16 GB | 200 GB | Freelancers, consultants |

## Quick Start

### Phase 1: Manual Install (BYO VPS)

1. Provision a VPS manually from any provider
2. SSH into the server as root
3. Run the installer:

```bash
curl -fsSL https://install.wopr.systems/bootstrap.sh | bash -s -- \
    --bundle personal \
    --domain mycloud.example.com
```

### Phase 2: API Provisioning

```python
from control_plane.provision import WOPRProvisioner

# Initialize
provisioner = WOPRProvisioner()

# Add providers
provisioner.add_provider("hetzner", api_token="your-token")
provisioner.add_provider("vultr", api_token="your-token")

# Provision for bundle (auto-selects cheapest provider)
result = provisioner.provision_for_bundle(
    bundle="personal",
    domain="mycloud.example.com",
    customer_id="cust_123"
)

print(f"Instance: {result.instance.ip_address}")
```

### Region-Based Selection

```python
from control_plane.providers.plan_registry import PlanRegistry, GeoRegion

# Get all options for a bundle, organized by US region
choices = PlanRegistry.get_user_choices("personal")
# Returns: {
#   "regions": {
#     "US West": [{provider, plan, datacenters}, ...],
#     "US Central": [...],
#     "US East": [...]
#   }
# }

# Get cheapest option in a specific region
cheapest = PlanRegistry.get_cheapest_for_bundle("personal", GeoRegion.US_WEST)

# Display formatted choices for CLI
print(PlanRegistry.format_choices_for_display("personal"))
```

### Distributed Provisioning

```python
# Provision instances across multiple providers for redundancy
results = provisioner.provision_distributed(
    bundle="developer",
    domain="mycloud.example.com",
    customer_id="cust_123",
    count=3  # Creates instances on 3 different providers
)
```

## Installation Flow

1. **detect_system_resources** - Check CPU, RAM, disk
2. **validate_cpu_ram_disk** - Ensure tier requirements met
3. **install_core_stack** - Podman, Caddy, base packages
4. **select_bundle** - User chooses bundle
5. **enable_bundle_modules** - Configure module list
6. **prompt_optional_modules** - Offer additional modules
7. **require_human_confirmation** - DEFCON ONE gate
8. **deploy_modules** - Install bundle applications
9. **configure_authentik** - Setup SSO
10. **configure_caddy** - Setup reverse proxy
11. **configure_postgresql** - Setup database
12. **configure_redis** - Setup cache
13. **schedule_backups** - Daily backup cron
14. **register_update_agent** - Update notifications
15. **log_to_defcon_one** - Audit trail
16. **finalize_installation** - Complete setup

## DEFCON ONE Compliance

All infrastructure changes require:
- Human confirmation OR signed token
- Pre-change snapshot
- Immutable audit log entry

The installer will NOT:
- Enable modules autonomously
- Modify production without approval
- Expand scope without instruction

## Reference: YunoHost Adaptation

This installer architecture is adapted from YunoHost's battle-tested app packaging model:

| YunoHost | WOPR |
|----------|------|
| manifest.toml | manifest.json |
| scripts/install | scripts/wopr_install.sh |
| scripts/_common.sh | scripts/wopr_common.sh |
| ynh_* helpers | wopr_* helpers |
| YunoHost SSO | Authentik |
| nginx | Caddy (API-driven) |

See `*_ynh/` directories for reference implementations.

## License

AGPL-3.0 - WOPR Foundation
