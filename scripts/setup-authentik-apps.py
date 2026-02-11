#!/usr/bin/env python3
"""
WOPR Authentik App Setup Script
================================

Configures Authentik with OAuth2/OIDC providers and applications
for all WOPR apps.

Creates:
- OAuth2 Providers for each app
- Application entries
- Group bindings for access control
- Outpost configuration

Usage:
    python setup-authentik-apps.py --url https://auth.beacon.wopr.systems --token YOUR_TOKEN
    python setup-authentik-apps.py --env  # Use AUTHENTIK_URL and AUTHENTIK_TOKEN env vars

Prerequisites:
    pip install httpx

Updated: January 2026
"""

import argparse
import os
import sys
import json
from typing import Dict, List, Optional, Any
from dataclasses import asdict

try:
    import httpx
except ImportError:
    print("ERROR: httpx not installed. Run: pip install httpx")
    sys.exit(1)

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from control_plane.authentik_apps import (
    WOPR_APPS,
    AppConfig,
    AuthMode,
    get_oauth_apps,
    get_proxy_apps,
    get_all_app_groups,
)
from control_plane.authentik_integration import WOPR_GROUPS, BUNDLE_GROUPS


class AuthentikSetup:
    """Setup Authentik for WOPR applications."""

    def __init__(self, base_url: str, api_token: str, beacon_name: str = ""):
        self.base_url = base_url.rstrip("/")
        self.api_token = api_token
        self.beacon_name = beacon_name or "beacon"
        self.headers = {
            "Authorization": f"Bearer {api_token}",
            "Content-Type": "application/json",
        }
        self.client = httpx.Client(timeout=30.0)

        # Cache for created resources
        self.providers: Dict[str, str] = {}  # app_id -> provider_pk
        self.applications: Dict[str, str] = {}  # app_id -> app_pk
        self.groups: Dict[str, str] = {}  # group_name -> group_pk

    def _request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """Make API request to Authentik."""
        url = f"{self.base_url}/api/v3/{endpoint}"

        try:
            response = self.client.request(
                method=method,
                url=url,
                headers=self.headers,
                json=data,
            )
            response.raise_for_status()

            if response.content:
                return response.json()
            return {}
        except httpx.HTTPStatusError as e:
            print(f"  ERROR: {e.response.status_code} - {e.response.text}")
            raise

    def _get_or_create(
        self,
        endpoint: str,
        search_field: str,
        search_value: str,
        create_data: Dict,
    ) -> Dict[str, Any]:
        """Get existing resource or create new one."""
        # Search for existing
        try:
            result = self._request("GET", f"{endpoint}?{search_field}={search_value}")
            if result.get("results"):
                return result["results"][0]
        except Exception:
            pass

        # Create new
        return self._request("POST", f"{endpoint}/", create_data)

    # ==========================================
    # GROUP MANAGEMENT
    # ==========================================

    def create_groups(self) -> Dict[str, Any]:
        """Create all WOPR groups in Authentik."""
        print("\n=== Creating Groups ===")

        created = []
        existing = []
        failed = []

        # Collect all unique groups from bundles
        all_groups = set()
        for bundle_groups in BUNDLE_GROUPS.values():
            all_groups.update(bundle_groups)

        # Add groups from WOPR_GROUPS
        all_groups.update(WOPR_GROUPS.keys())

        # Add all app-specific groups
        all_groups.update(get_all_app_groups())

        for group_name in sorted(all_groups):
            try:
                result = self._get_or_create(
                    endpoint="core/groups",
                    search_field="name",
                    search_value=group_name,
                    create_data={"name": group_name},
                )

                self.groups[group_name] = str(result["pk"])

                if "created" in str(result.get("pk", "")):
                    created.append(group_name)
                else:
                    existing.append(group_name)

                print(f"  ✓ {group_name}")

            except Exception as e:
                failed.append({"name": group_name, "error": str(e)})
                print(f"  ✗ {group_name}: {e}")

        return {
            "created": len(created),
            "existing": len(existing),
            "failed": len(failed),
            "total": len(all_groups),
        }

    # ==========================================
    # OAUTH2 PROVIDER MANAGEMENT
    # ==========================================

    def create_oauth2_provider(self, app: AppConfig) -> Optional[str]:
        """Create OAuth2/OIDC provider for an app."""
        provider_name = f"wopr-{app.id}-provider"
        redirect_uri = f"https://{app.subdomain}.{self.beacon_name}.wopr.systems"

        if app.oauth_redirect_uri:
            redirect_uri += app.oauth_redirect_uri

        try:
            # Check if provider exists
            result = self._request("GET", f"providers/oauth2/?name={provider_name}")
            if result.get("results"):
                provider = result["results"][0]
                print(f"  ✓ Provider exists: {provider_name}")
                return str(provider["pk"])

            # Create new provider
            provider_data = {
                "name": provider_name,
                "authorization_flow": self._get_default_flow("authorization"),
                "client_type": "confidential",
                "client_id": f"wopr-{app.id}",
                "redirect_uris": redirect_uri,
                "signing_key": self._get_signing_key(),
                "access_code_validity": "minutes=1",
                "access_token_validity": "hours=1",
                "refresh_token_validity": "days=30",
                "include_claims_in_id_token": True,
                "sub_mode": "user_email",
            }

            result = self._request("POST", "providers/oauth2/", provider_data)
            print(f"  ✓ Created provider: {provider_name}")
            return str(result["pk"])

        except Exception as e:
            print(f"  ✗ Failed to create provider {provider_name}: {e}")
            return None

    def _get_default_flow(self, flow_type: str) -> str:
        """Get the default flow UUID."""
        try:
            if flow_type == "authorization":
                result = self._request("GET", "flows/instances/?designation=authorization")
            else:
                result = self._request("GET", f"flows/instances/?slug=default-{flow_type}-flow")

            if result.get("results"):
                return result["results"][0]["pk"]
        except Exception:
            pass

        return ""

    def _get_signing_key(self) -> str:
        """Get or create signing key for OAuth2."""
        try:
            result = self._request("GET", "crypto/certificatekeypairs/?name=authentik%20Self-signed%20Certificate")
            if result.get("results"):
                return result["results"][0]["pk"]
        except Exception:
            pass

        return ""

    # ==========================================
    # APPLICATION MANAGEMENT
    # ==========================================

    def create_application(self, app: AppConfig, provider_pk: Optional[str] = None) -> Optional[str]:
        """Create Authentik application for a WOPR app."""
        app_name = f"wopr-{app.id}"
        app_slug = f"wopr-{app.id}"

        try:
            # Check if application exists
            result = self._request("GET", f"core/applications/?slug={app_slug}")
            if result.get("results"):
                application = result["results"][0]
                print(f"  ✓ Application exists: {app_name}")
                return str(application["pk"])

            # Create new application
            app_data = {
                "name": app.name,
                "slug": app_slug,
                "provider": int(provider_pk) if provider_pk else None,
                "meta_launch_url": f"https://{app.subdomain}.{self.beacon_name}.wopr.systems",
                "meta_description": app.description,
                "meta_icon": "",  # Would use app.icon but Authentik needs URL
                "policy_engine_mode": "any",
            }

            result = self._request("POST", "core/applications/", app_data)
            print(f"  ✓ Created application: {app_name}")
            return str(result["pk"])

        except Exception as e:
            print(f"  ✗ Failed to create application {app_name}: {e}")
            return None

    def bind_groups_to_application(self, app_pk: str, groups: List[str]) -> None:
        """Bind access groups to an application via policy."""
        for group_name in groups:
            group_pk = self.groups.get(group_name)
            if not group_pk:
                continue

            try:
                # Create group membership policy
                policy_name = f"wopr-{group_name}-access"

                policy_data = {
                    "name": policy_name,
                    "group": group_pk,
                }

                policy_result = self._get_or_create(
                    endpoint="policies/group_membership",
                    search_field="name",
                    search_value=policy_name,
                    create_data=policy_data,
                )

                # Bind policy to application
                binding_data = {
                    "target": app_pk,
                    "policy": policy_result["pk"],
                    "enabled": True,
                    "order": 0,
                }

                self._request("POST", "policies/bindings/", binding_data)

            except Exception as e:
                # Binding might already exist
                pass

    # ==========================================
    # PROXY PROVIDER MANAGEMENT
    # ==========================================

    def create_proxy_provider(self, app: AppConfig) -> Optional[str]:
        """Create forward auth proxy provider for an app."""
        provider_name = f"wopr-{app.id}-proxy"
        external_host = f"https://{app.subdomain}.{self.beacon_name}.wopr.systems"

        try:
            # Check if provider exists
            result = self._request("GET", f"providers/proxy/?name={provider_name}")
            if result.get("results"):
                provider = result["results"][0]
                print(f"  ✓ Proxy provider exists: {provider_name}")
                return str(provider["pk"])

            # Create new proxy provider
            provider_data = {
                "name": provider_name,
                "authorization_flow": self._get_default_flow("authorization"),
                "external_host": external_host,
                "mode": "forward_single",
                "access_token_validity": "hours=24",
            }

            result = self._request("POST", "providers/proxy/", provider_data)
            print(f"  ✓ Created proxy provider: {provider_name}")
            return str(result["pk"])

        except Exception as e:
            print(f"  ✗ Failed to create proxy provider {provider_name}: {e}")
            return None

    # ==========================================
    # MAIN SETUP
    # ==========================================

    def setup_all(self) -> Dict[str, Any]:
        """Run full Authentik setup for all WOPR apps."""
        print("=" * 60)
        print("WOPR Authentik Setup")
        print("=" * 60)
        print(f"Authentik URL: {self.base_url}")
        print(f"Beacon Name: {self.beacon_name}")

        results = {
            "groups": {},
            "providers": {},
            "applications": {},
            "errors": [],
        }

        # Step 1: Create all groups
        results["groups"] = self.create_groups()

        # Step 2: Create OAuth2 providers and applications
        print("\n=== Creating OAuth2 Apps ===")
        for app in get_oauth_apps():
            print(f"\n{app.name} ({app.id}):")

            provider_pk = self.create_oauth2_provider(app)
            if provider_pk:
                self.providers[app.id] = provider_pk

                app_pk = self.create_application(app, provider_pk)
                if app_pk:
                    self.applications[app.id] = app_pk

                    # Bind groups
                    all_groups = app.access_groups + app.trial_groups
                    if all_groups:
                        self.bind_groups_to_application(app_pk, all_groups)
                        print(f"  ✓ Bound groups: {', '.join(all_groups)}")

        # Step 3: Create Proxy providers and applications
        print("\n=== Creating Proxy Apps ===")
        for app in get_proxy_apps():
            print(f"\n{app.name} ({app.id}):")

            provider_pk = self.create_proxy_provider(app)
            if provider_pk:
                self.providers[app.id] = provider_pk

                app_pk = self.create_application(app, provider_pk)
                if app_pk:
                    self.applications[app.id] = app_pk

                    # Bind groups
                    all_groups = app.access_groups + app.trial_groups
                    if all_groups:
                        self.bind_groups_to_application(app_pk, all_groups)
                        print(f"  ✓ Bound groups: {', '.join(all_groups)}")

        # Summary
        print("\n" + "=" * 60)
        print("SETUP COMPLETE")
        print("=" * 60)
        print(f"Groups: {results['groups'].get('total', 0)} total")
        print(f"Providers: {len(self.providers)} created")
        print(f"Applications: {len(self.applications)} created")

        results["providers"] = {"count": len(self.providers)}
        results["applications"] = {"count": len(self.applications)}

        return results

    def export_client_secrets(self, output_file: str = "oauth_secrets.json") -> None:
        """Export OAuth2 client secrets for app configuration."""
        print(f"\nExporting client secrets to {output_file}...")

        secrets = {}

        for app_id, provider_pk in self.providers.items():
            app = WOPR_APPS.get(app_id)
            if not app or app.auth_mode != AuthMode.OAUTH2:
                continue

            try:
                result = self._request("GET", f"providers/oauth2/{provider_pk}/")
                secrets[app_id] = {
                    "client_id": result.get("client_id"),
                    "client_secret": result.get("client_secret"),
                    "authorization_url": f"{self.base_url}/application/o/authorize/",
                    "token_url": f"{self.base_url}/application/o/token/",
                    "userinfo_url": f"{self.base_url}/application/o/userinfo/",
                    "jwks_url": f"{self.base_url}/application/o/wopr-{app_id}/jwks/",
                }
            except Exception as e:
                print(f"  ✗ Failed to get secrets for {app_id}: {e}")

        with open(output_file, "w") as f:
            json.dump(secrets, f, indent=2)

        print(f"  ✓ Exported {len(secrets)} client configurations")


def main():
    parser = argparse.ArgumentParser(description="Setup Authentik for WOPR applications")
    parser.add_argument("--url", help="Authentik URL (e.g., https://auth.beacon.wopr.systems)")
    parser.add_argument("--token", help="Authentik API token")
    parser.add_argument("--beacon", help="Beacon name for domain configuration", default="")
    parser.add_argument("--env", action="store_true", help="Use environment variables")
    parser.add_argument("--export-secrets", help="Export OAuth secrets to file")

    args = parser.parse_args()

    # Get configuration
    if args.env:
        url = os.environ.get("AUTHENTIK_URL")
        token = os.environ.get("AUTHENTIK_TOKEN")
        beacon = os.environ.get("BEACON_NAME", "")
    else:
        url = args.url
        token = args.token
        beacon = args.beacon

    if not url or not token:
        print("ERROR: Authentik URL and token are required")
        print("Use --url and --token, or --env with AUTHENTIK_URL and AUTHENTIK_TOKEN")
        sys.exit(1)

    # Run setup
    setup = AuthentikSetup(url, token, beacon)
    results = setup.setup_all()

    # Export secrets if requested
    if args.export_secrets:
        setup.export_client_secrets(args.export_secrets)

    print("\nDone!")


if __name__ == "__main__":
    main()
