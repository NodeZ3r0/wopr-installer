"""
WOPR Provider API Configuration
===============================

Centralized API configuration and authentication for all VPS providers.
Each provider has specific requirements for authentication and API access.

Documentation Links:
- Hetzner: https://docs.hetzner.cloud/
- Vultr: https://www.vultr.com/api/
- DigitalOcean: https://docs.digitalocean.com/reference/api/
- Linode: https://techdocs.akamai.com/linode-api/reference/api

Updated: January 2026
"""

from dataclasses import dataclass, field
from typing import Optional, Dict, List
from enum import Enum


class AuthMethod(Enum):
    """Authentication methods supported by providers."""
    BEARER_TOKEN = "bearer_token"
    API_KEY_HEADER = "api_key_header"
    BASIC_AUTH = "basic_auth"


@dataclass
class ProviderAPIConfig:
    """API configuration for a VPS provider."""
    provider_id: str
    name: str

    # API endpoints
    base_url: str
    api_version: str

    # Authentication
    auth_method: AuthMethod
    auth_header: str
    token_prefix: str = "Bearer"

    # Rate limiting
    requests_per_second: int = 10
    burst_limit: int = 30

    # Python SDK
    sdk_package: str = ""
    sdk_install: str = ""
    sdk_docs: str = ""

    # Portal links for users
    signup_url: str = ""
    api_key_url: str = ""
    console_url: str = ""

    # Required scopes/permissions
    required_permissions: List[str] = field(default_factory=list)

    # Example code
    example_create: str = ""


# ============================================
# PROVIDER API CONFIGURATIONS
# ============================================

HETZNER_API = ProviderAPIConfig(
    provider_id="hetzner",
    name="Hetzner Cloud",

    # API
    base_url="https://api.hetzner.cloud/v1",
    api_version="v1",

    # Auth
    auth_method=AuthMethod.BEARER_TOKEN,
    auth_header="Authorization",
    token_prefix="Bearer",

    # Rate limits
    requests_per_second=10,
    burst_limit=100,

    # SDK
    sdk_package="hcloud",
    sdk_install="pip install hcloud",
    sdk_docs="https://hcloud-python.readthedocs.io/",

    # Portal
    signup_url="https://accounts.hetzner.com/signUp",
    api_key_url="https://console.hetzner.cloud/projects/YOUR_PROJECT/security/tokens",
    console_url="https://console.hetzner.cloud/",

    # Permissions
    required_permissions=["Read & Write"],

    # Example
    example_create='''
from hcloud import Client
from hcloud.images import Image
from hcloud.server_types import ServerType
from hcloud.locations import Location

client = Client(token="YOUR_API_TOKEN")

# Create server
response = client.servers.create(
    name="wopr-personal-abc123",
    server_type=ServerType(name="cpx11"),
    image=Image(name="debian-12"),
    location=Location(name="ash"),  # Ashburn, VA
    ssh_keys=[client.ssh_keys.get_by_name("wopr-deploy")],
    user_data=cloud_init_script,
    labels={"wopr": "true", "bundle": "personal"}
)

print(f"Server IP: {response.server.public_net.ipv4.ip}")
print(f"Root password: {response.root_password}")
'''
)

VULTR_API = ProviderAPIConfig(
    provider_id="vultr",
    name="Vultr",

    # API
    base_url="https://api.vultr.com/v2",
    api_version="v2",

    # Auth
    auth_method=AuthMethod.BEARER_TOKEN,
    auth_header="Authorization",
    token_prefix="Bearer",

    # Rate limits (30 req/sec, then 429)
    requests_per_second=25,
    burst_limit=30,

    # SDK
    sdk_package="vultr-python",
    sdk_install="pip install vultr-python",
    sdk_docs="https://vultr-python.sapps.me",

    # Portal
    signup_url="https://www.vultr.com/register/",
    api_key_url="https://my.vultr.com/settings/#settingsapi",
    console_url="https://my.vultr.com/",

    # Permissions
    required_permissions=["Allow All IPv4"],

    # Example
    example_create='''
import requests

api_key = "YOUR_API_KEY"
url = "https://api.vultr.com/v2/instances"
headers = {
    "Authorization": f"Bearer {api_key}",
    "Content-Type": "application/json"
}

data = {
    "region": "ewr",           # Newark, NJ
    "plan": "vc2-1c-2gb",      # 1 vCPU, 2GB RAM
    "label": "wopr-personal-abc123",
    "os_id": 2136,             # Debian 12
    "sshkey_id": ["ssh-key-id"],
    "user_data": cloud_init_base64,
    "tags": ["wopr", "personal"]
}

response = requests.post(url, json=data, headers=headers)
instance = response.json()["instance"]
print(f"Instance ID: {instance['id']}")
print(f"Main IP: {instance['main_ip']}")
'''
)

DIGITALOCEAN_API = ProviderAPIConfig(
    provider_id="digitalocean",
    name="DigitalOcean",

    # API
    base_url="https://api.digitalocean.com/v2",
    api_version="v2",

    # Auth
    auth_method=AuthMethod.BEARER_TOKEN,
    auth_header="Authorization",
    token_prefix="Bearer",

    # Rate limits
    requests_per_second=5,
    burst_limit=250,  # Per minute

    # SDK
    sdk_package="pydo",
    sdk_install="pip install pydo",
    sdk_docs="https://pydo.readthedocs.io/",

    # Portal
    signup_url="https://cloud.digitalocean.com/registrations/new",
    api_key_url="https://cloud.digitalocean.com/account/api/tokens",
    console_url="https://cloud.digitalocean.com/",

    # Permissions
    required_permissions=["Read", "Write"],

    # Example
    example_create='''
from pydo import Client
import os

client = Client(token=os.environ.get("DIGITALOCEAN_TOKEN"))

req = {
    "name": "wopr-personal-abc123",
    "region": "nyc1",
    "size": "s-1vcpu-2gb",
    "image": "debian-12-x64",
    "ssh_keys": ["fingerprint"],
    "user_data": cloud_init_script,
    "tags": ["wopr", "personal"],
    "ipv6": True,
    "monitoring": True
}

response = client.droplets.create(body=req)
droplet = response["droplet"]
print(f"Droplet ID: {droplet['id']}")
'''
)

LINODE_API = ProviderAPIConfig(
    provider_id="linode",
    name="Linode (Akamai)",

    # API
    base_url="https://api.linode.com/v4",
    api_version="v4",

    # Auth
    auth_method=AuthMethod.BEARER_TOKEN,
    auth_header="Authorization",
    token_prefix="Bearer",

    # Rate limits
    requests_per_second=100,
    burst_limit=1600,  # Per 2 minutes

    # SDK
    sdk_package="linode_api4",
    sdk_install="pip install linode_api4",
    sdk_docs="https://linode-api4-python.readthedocs.io/",

    # Portal
    signup_url="https://login.linode.com/signup",
    api_key_url="https://cloud.linode.com/profile/tokens",
    console_url="https://cloud.linode.com/",

    # Permissions
    required_permissions=["Linodes: Read/Write", "StackScripts: Read/Write"],

    # Example
    example_create='''
from linode_api4 import LinodeClient

client = LinodeClient("YOUR_PERSONAL_ACCESS_TOKEN")

new_linode, root_pass = client.linode.instance_create(
    ltype="g6-nanode-1",
    region="us-east",           # Newark, NJ
    image="linode/debian12",
    label="wopr-personal-abc123",
    authorized_keys=["ssh-rsa ..."],
    metadata={"user_data": cloud_init_script},
    tags=["wopr", "personal"]
)

print(f"Linode IP: {new_linode.ipv4[0]}")
print(f"Root Password: {root_pass}")
'''
)


# ============================================
# REGISTRY
# ============================================

API_CONFIGS: Dict[str, ProviderAPIConfig] = {
    "hetzner": HETZNER_API,
    "vultr": VULTR_API,
    "digitalocean": DIGITALOCEAN_API,
    "linode": LINODE_API,
}


def get_api_config(provider_id: str) -> Optional[ProviderAPIConfig]:
    """Get API configuration for a provider."""
    return API_CONFIGS.get(provider_id)


def list_api_configs() -> List[Dict]:
    """List all API configurations with summary info."""
    return [
        {
            "provider_id": config.provider_id,
            "name": config.name,
            "sdk_install": config.sdk_install,
            "signup_url": config.signup_url,
            "api_key_url": config.api_key_url,
        }
        for config in API_CONFIGS.values()
    ]
