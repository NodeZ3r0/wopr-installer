"""
Quick server runner for Stripe testing.
Usage: python -m control_plane.run_server
"""
import os
import sys
from pathlib import Path

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Load .env
env_path = Path(__file__).parent.parent / ".env"
if env_path.exists():
    print(f"Loading environment from {env_path}")
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, _, value = line.partition("=")
            os.environ.setdefault(key.strip(), value.strip())

# Set defaults for required vars
os.environ.setdefault("AUTHENTIK_API_URL", os.environ.get("AUTHENTIK_URL", "https://auth.wopr.systems"))

def main():
    import uvicorn
    from control_plane.dashboard_api import create_app_from_env

    print("Starting WOPR Control Plane API...")
    print(f"  STRIPE_SECRET_KEY: {os.environ.get('STRIPE_SECRET_KEY', 'NOT SET')[:20]}...")
    print(f"  HETZNER_API_TOKEN: {os.environ.get('HETZNER_API_TOKEN', 'NOT SET')[:10]}...")

    app = create_app_from_env()

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8001,
        log_level="info",
    )

if __name__ == "__main__":
    main()
