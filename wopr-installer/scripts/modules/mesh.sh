#!/bin/bash
#=================================================
# WOPR MODULE: Mesh Network
# Version: 1.0
# Purpose: Peer-to-peer distributed mesh between beacons
# License: AGPL-3.0
#
# Each beacon is a fully independent node. The mesh is
# additive — beacons work standalone. Peering lets users
# on one beacon authenticate to apps on another via
# mutual Authentik OIDC federation. No central authority.
#
# Architecture:
#   - Ed25519 keypair per beacon (identity)
#   - Mesh API on each beacon (peer discovery + trust)
#   - Mutual Authentik OIDC federation (bidirectional)
#   - Invite-based peering (no broadcast/multicast)
#   - Each beacon maintains its own peer list
#=================================================

# This script is sourced by the installer
# It expects wopr_common.sh to already be loaded

MESH_DIR="/etc/wopr/mesh"
MESH_PEERS_DIR="${MESH_DIR}/peers"
MESH_INVITES_DIR="${MESH_DIR}/invites"
MESH_PORT=8099
MESH_SERVICE="wopr-mesh-agent"
MESH_AGENT_SCRIPT="/opt/wopr/scripts/wopr_mesh_agent.sh"

#=================================================
# BEACON IDENTITY
#=================================================

wopr_mesh_generate_identity() {
    # Generate Ed25519 keypair for this beacon
    # This is the beacon's permanent cryptographic identity
    wopr_log "INFO" "Generating beacon mesh identity..."

    mkdir -p "$MESH_DIR"
    mkdir -p "$MESH_PEERS_DIR"
    mkdir -p "$MESH_INVITES_DIR"
    chmod 700 "$MESH_DIR"

    local privkey="${MESH_DIR}/beacon.key"
    local pubkey="${MESH_DIR}/beacon.pub"

    if [ -f "$privkey" ]; then
        wopr_log "INFO" "Beacon identity already exists"
        return 0
    fi

    # Generate Ed25519 keypair using OpenSSL
    openssl genpkey -algorithm Ed25519 -out "$privkey" 2>/dev/null
    openssl pkey -in "$privkey" -pubout -out "$pubkey" 2>/dev/null
    chmod 600 "$privkey"
    chmod 644 "$pubkey"

    # Generate fingerprint (SHA256 of public key)
    local fingerprint=$(openssl pkey -in "$privkey" -pubout -outform DER 2>/dev/null | sha256sum | cut -d' ' -f1)

    # Store identity info
    local beacon_id=$(wopr_instance_id)
    local domain=$(wopr_setting_get "domain")

    cat > "${MESH_DIR}/identity.json" <<EOF
{
    "beacon_id": "${beacon_id}",
    "domain": "${domain}",
    "fingerprint": "${fingerprint}",
    "public_key": "$(cat "$pubkey" | base64 -w0)",
    "created_at": "$(date -Iseconds)",
    "mesh_version": "1.0"
}
EOF

    wopr_setting_set "mesh_fingerprint" "$fingerprint"
    wopr_setting_set "mesh_beacon_id" "$beacon_id"

    wopr_log "OK" "Beacon identity generated: fingerprint=${fingerprint:0:16}..."
}

wopr_mesh_get_identity() {
    # Return this beacon's identity as JSON
    if [ -f "${MESH_DIR}/identity.json" ]; then
        cat "${MESH_DIR}/identity.json"
    else
        wopr_log "ERROR" "Beacon identity not found"
        return 1
    fi
}

wopr_mesh_get_fingerprint() {
    wopr_setting_get "mesh_fingerprint"
}

#=================================================
# PEER MANAGEMENT
#=================================================

wopr_mesh_add_peer() {
    # Add a verified peer to the local peer list
    # Usage: wopr_mesh_add_peer <peer_json>
    local peer_json="$1"

    local peer_id=$(echo "$peer_json" | jq -r '.beacon_id')
    local peer_domain=$(echo "$peer_json" | jq -r '.domain')
    local peer_fingerprint=$(echo "$peer_json" | jq -r '.fingerprint')

    if [ -z "$peer_id" ] || [ -z "$peer_domain" ] || [ -z "$peer_fingerprint" ]; then
        wopr_log "ERROR" "Invalid peer data"
        return 1
    fi

    # Don't peer with ourselves
    local my_id=$(wopr_instance_id)
    if [ "$peer_id" = "$my_id" ]; then
        wopr_log "WARN" "Cannot peer with self"
        return 1
    fi

    # Check if already peered
    if [ -f "${MESH_PEERS_DIR}/${peer_fingerprint}.json" ]; then
        wopr_log "INFO" "Already peered with ${peer_domain}"
        return 0
    fi

    # Save peer info with timestamp
    echo "$peer_json" | jq ". + {\"peered_at\": \"$(date -Iseconds)\", \"status\": \"active\"}" \
        > "${MESH_PEERS_DIR}/${peer_fingerprint}.json"

    wopr_log "OK" "Peer added: ${peer_domain} (${peer_fingerprint:0:16}...)"
    wopr_defcon_log "MESH_PEER_ADDED" "domain=${peer_domain},fingerprint=${peer_fingerprint:0:16}"
}

wopr_mesh_remove_peer() {
    # Remove a peer by fingerprint
    local fingerprint="$1"

    if [ -f "${MESH_PEERS_DIR}/${fingerprint}.json" ]; then
        local peer_domain=$(jq -r '.domain' "${MESH_PEERS_DIR}/${fingerprint}.json")
        rm -f "${MESH_PEERS_DIR}/${fingerprint}.json"
        wopr_log "OK" "Peer removed: ${peer_domain}"
        wopr_defcon_log "MESH_PEER_REMOVED" "fingerprint=${fingerprint:0:16}"
    else
        wopr_log "WARN" "Peer not found: ${fingerprint:0:16}..."
    fi
}

wopr_mesh_list_peers() {
    # List all peers as JSON array
    local peers="[]"

    for peer_file in "${MESH_PEERS_DIR}"/*.json; do
        [ -f "$peer_file" ] || continue
        peers=$(echo "$peers" | jq ". + [$(cat "$peer_file")]")
    done

    echo "$peers"
}

wopr_mesh_peer_count() {
    local count=0
    for peer_file in "${MESH_PEERS_DIR}"/*.json; do
        [ -f "$peer_file" ] || continue
        count=$((count + 1))
    done
    echo "$count"
}

#=================================================
# INVITE SYSTEM
#=================================================

wopr_mesh_create_invite() {
    # Generate a peering invite token
    # The invite contains this beacon's identity + a one-time secret
    # The other beacon presents this to complete the handshake

    local invite_secret=$(wopr_random_string 32)
    local invite_id=$(wopr_random_string 16)
    local identity=$(wopr_mesh_get_identity)
    local domain=$(wopr_setting_get "domain")

    # Store invite locally (for verification when peer connects)
    cat > "${MESH_INVITES_DIR}/${invite_id}.json" <<EOF
{
    "invite_id": "${invite_id}",
    "secret": "${invite_secret}",
    "created_at": "$(date -Iseconds)",
    "used": false
}
EOF

    # Build the invite token (base64-encoded JSON)
    local invite_payload=$(jq -n \
        --arg invite_id "$invite_id" \
        --arg secret "$invite_secret" \
        --arg domain "$domain" \
        --arg fingerprint "$(wopr_mesh_get_fingerprint)" \
        --arg mesh_url "https://mesh.${domain}" \
        '{
            "type": "wopr-mesh-invite",
            "version": "1.0",
            "invite_id": $invite_id,
            "secret": $secret,
            "origin_domain": $domain,
            "origin_fingerprint": $fingerprint,
            "mesh_url": $mesh_url
        }')

    local invite_token=$(echo "$invite_payload" | base64 -w0)

    wopr_log "OK" "Mesh invite created: ${invite_id}"
    echo "$invite_token"
}

wopr_mesh_verify_invite() {
    # Verify an incoming invite claim from a peer
    local invite_id="$1"
    local invite_secret="$2"

    local invite_file="${MESH_INVITES_DIR}/${invite_id}.json"

    if [ ! -f "$invite_file" ]; then
        wopr_log "ERROR" "Invite not found: ${invite_id}"
        return 1
    fi

    local stored_secret=$(jq -r '.secret' "$invite_file")
    local used=$(jq -r '.used' "$invite_file")

    if [ "$used" = "true" ]; then
        wopr_log "ERROR" "Invite already used: ${invite_id}"
        return 1
    fi

    if [ "$invite_secret" != "$stored_secret" ]; then
        wopr_log "ERROR" "Invalid invite secret"
        wopr_defcon_log "MESH_INVITE_FAILED" "invite_id=${invite_id}"
        return 1
    fi

    # Mark invite as used
    local tmp=$(mktemp)
    jq '.used = true | .used_at = "'"$(date -Iseconds)"'"' "$invite_file" > "$tmp" && mv "$tmp" "$invite_file"

    wopr_log "OK" "Invite verified: ${invite_id}"
    return 0
}

wopr_mesh_accept_invite() {
    # Accept an invite from another beacon
    # Decodes the invite token, reaches out to the origin beacon, completes handshake
    local invite_token="$1"

    # Decode the invite
    local invite_json=$(echo "$invite_token" | base64 -d 2>/dev/null)
    if [ -z "$invite_json" ]; then
        wopr_log "ERROR" "Invalid invite token"
        return 1
    fi

    local invite_type=$(echo "$invite_json" | jq -r '.type // empty')
    if [ "$invite_type" != "wopr-mesh-invite" ]; then
        wopr_log "ERROR" "Not a valid WOPR mesh invite"
        return 1
    fi

    local origin_domain=$(echo "$invite_json" | jq -r '.origin_domain')
    local origin_fingerprint=$(echo "$invite_json" | jq -r '.origin_fingerprint')
    local mesh_url=$(echo "$invite_json" | jq -r '.mesh_url')
    local invite_id=$(echo "$invite_json" | jq -r '.invite_id')
    local invite_secret=$(echo "$invite_json" | jq -r '.secret')

    wopr_log "INFO" "Accepting mesh invite from ${origin_domain}..."

    # Get our identity
    local my_identity=$(wopr_mesh_get_identity)

    # Send handshake to origin beacon
    local handshake_payload=$(jq -n \
        --arg invite_id "$invite_id" \
        --arg secret "$invite_secret" \
        --argjson identity "$my_identity" \
        '{
            "invite_id": $invite_id,
            "secret": $secret,
            "peer_identity": $identity
        }')

    local response=$(curl -s -w "\n%{http_code}" \
        -X POST "${mesh_url}/api/v1/mesh/handshake" \
        -H "Content-Type: application/json" \
        -d "$handshake_payload" \
        --connect-timeout 10 \
        --max-time 30)

    local http_code=$(echo "$response" | tail -n1)
    local body=$(echo "$response" | head -n -1)

    if [ "$http_code" -ne 200 ]; then
        wopr_log "ERROR" "Handshake failed with ${origin_domain}: HTTP ${http_code}"
        return 1
    fi

    # Extract origin's identity from response
    local origin_identity=$(echo "$body" | jq '.peer_identity')
    if [ -z "$origin_identity" ] || [ "$origin_identity" = "null" ]; then
        wopr_log "ERROR" "No identity in handshake response"
        return 1
    fi

    # Verify the fingerprint matches what was in the invite
    local response_fingerprint=$(echo "$origin_identity" | jq -r '.fingerprint')
    if [ "$response_fingerprint" != "$origin_fingerprint" ]; then
        wopr_log "ERROR" "Fingerprint mismatch! Possible MITM attack."
        wopr_defcon_log "MESH_FINGERPRINT_MISMATCH" "expected=${origin_fingerprint:0:16},got=${response_fingerprint:0:16}"
        return 1
    fi

    # Add as peer
    wopr_mesh_add_peer "$origin_identity"

    # Setup Authentik OIDC federation with this peer
    wopr_mesh_setup_federation "$origin_identity"

    wopr_log "OK" "Successfully peered with ${origin_domain}"
    wopr_defcon_log "MESH_PEERING_COMPLETE" "domain=${origin_domain}"
}

#=================================================
# AUTHENTIK OIDC FEDERATION
#=================================================

wopr_mesh_setup_federation() {
    # Setup bidirectional Authentik OIDC federation with a peer
    # This allows users on the peer beacon to SSO into apps on this beacon
    local peer_json="$1"

    local peer_domain=$(echo "$peer_json" | jq -r '.domain')
    local peer_id=$(echo "$peer_json" | jq -r '.beacon_id')
    local peer_fingerprint=$(echo "$peer_json" | jq -r '.fingerprint')

    wopr_log "INFO" "Setting up Authentik OIDC federation with ${peer_domain}..."

    local my_domain=$(wopr_setting_get "domain")

    # The peer's Authentik OIDC discovery URL
    local peer_issuer="https://auth.${peer_domain}/application/o/wopr-mesh/"
    local peer_oidc_url="https://auth.${peer_domain}/application/o/wopr-mesh/.well-known/openid-configuration"

    # 1. Create an OAuth2 Source in our Authentik pointing to the peer's Authentik
    #    This is the "federation" — their users can auth through our Authentik
    local source_slug="mesh-${peer_fingerprint:0:12}"
    local source_name="Mesh: ${peer_domain}"

    # Generate client credentials for the federation
    local fed_client_id="wopr-mesh-${peer_fingerprint:0:16}"
    local fed_client_secret=$(wopr_random_string 64)

    # Create OAuth2 Source in our Authentik
    local source_data=$(jq -n \
        --arg name "$source_name" \
        --arg slug "$source_slug" \
        --arg consumer_key "$fed_client_id" \
        --arg consumer_secret "$fed_client_secret" \
        --arg provider_type "openidconnect" \
        --arg oidc_well_known "$peer_oidc_url" \
        --arg oidc_jwks_url "https://auth.${peer_domain}/application/o/wopr-mesh/jwks/" \
        --arg authorization_url "https://auth.${peer_domain}/application/o/authorize/" \
        --arg access_token_url "https://auth.${peer_domain}/application/o/token/" \
        --arg profile_url "https://auth.${peer_domain}/application/o/userinfo/" \
        '{
            "name": $name,
            "slug": $slug,
            "enabled": true,
            "authentication_flow": null,
            "enrollment_flow": null,
            "provider_type": $provider_type,
            "consumer_key": $consumer_key,
            "consumer_secret": $consumer_secret,
            "oidc_well_known_url": $oidc_well_known,
            "oidc_jwks_url": $oidc_jwks_url,
            "authorization_url": $authorization_url,
            "access_token_url": $access_token_url,
            "profile_url": $profile_url
        }')

    local response=$(wopr_authentik_api POST "/sources/oauth/" "$source_data")
    local source_pk=$(echo "$response" | jq -r '.pk // empty')

    if [ -n "$source_pk" ]; then
        wopr_log "OK" "Authentik OAuth2 source created for peer ${peer_domain}"

        # Store federation info
        wopr_setting_set "mesh_fed_${peer_fingerprint:0:12}_source_pk" "$source_pk"
        wopr_setting_set "mesh_fed_${peer_fingerprint:0:12}_client_id" "$fed_client_id"
        wopr_setting_set "mesh_fed_${peer_fingerprint:0:12}_client_secret" "$fed_client_secret"

        # Update the peer file with federation info
        local peer_file="${MESH_PEERS_DIR}/${peer_fingerprint}.json"
        if [ -f "$peer_file" ]; then
            local tmp=$(mktemp)
            jq ". + {
                \"federation\": {
                    \"source_pk\": \"${source_pk}\",
                    \"client_id\": \"${fed_client_id}\",
                    \"status\": \"active\"
                }
            }" "$peer_file" > "$tmp" && mv "$tmp" "$peer_file"
        fi
    else
        wopr_log "WARN" "Failed to create OAuth2 source for peer ${peer_domain}"
        wopr_log "INFO" "Response: $(echo "$response" | jq -r '.detail // .' 2>/dev/null)"
    fi

    # 2. Create a corresponding OAuth2 Provider in our Authentik for the peer
    #    This allows the peer beacon to redirect auth requests to us
    local provider_name="Mesh Provider: ${peer_domain}"
    local provider_slug="mesh-provider-${peer_fingerprint:0:12}"
    local provider_client_id="wopr-mesh-from-${peer_fingerprint:0:16}"
    local provider_client_secret=$(wopr_random_string 64)
    local redirect_uri="https://auth.${peer_domain}/source/oauth/callback/${source_slug}/"

    # Get flow UUIDs for provider creation
    local auth_flow_uuid=""
    local invalidation_flow_uuid=""
    local flows_response=$(wopr_authentik_api GET "/flows/instances/?slug=default-provider-authorization-implicit-consent")
    auth_flow_uuid=$(echo "$flows_response" | jq -r '.results[0].pk // empty')
    flows_response=$(wopr_authentik_api GET "/flows/instances/?slug=default-provider-invalidation-flow")
    invalidation_flow_uuid=$(echo "$flows_response" | jq -r '.results[0].pk // empty')

    local provider_data=$(jq -n \
        --arg name "$provider_name" \
        --arg client_id "$provider_client_id" \
        --arg client_secret "$provider_client_secret" \
        --arg redirect_uri "$redirect_uri" \
        --arg auth_flow "$auth_flow_uuid" \
        --arg inv_flow "$invalidation_flow_uuid" \
        '{
            "name": $name,
            "authorization_flow": $auth_flow,
            "invalidation_flow": $inv_flow,
            "client_type": "confidential",
            "client_id": $client_id,
            "client_secret": $client_secret,
            "redirect_uris": [{"matching_mode": "strict", "url": $redirect_uri}],
            "signing_key": null,
            "access_code_validity": "minutes=1",
            "access_token_validity": "minutes=5",
            "refresh_token_validity": "days=30",
            "sub_mode": "hashed_user_id",
            "include_claims_in_id_token": true
        }')

    local prov_response=$(wopr_authentik_api POST "/providers/oauth2/" "$provider_data")
    local provider_pk=$(echo "$prov_response" | jq -r '.pk // empty')

    if [ -n "$provider_pk" ]; then
        # Create the application entry for the mesh endpoint
        local app_data=$(jq -n \
            --arg name "Mesh: ${peer_domain}" \
            --arg slug "mesh-${peer_fingerprint:0:12}" \
            --argjson provider "$provider_pk" \
            '{
                "name": $name,
                "slug": $slug,
                "provider": $provider,
                "meta_launch_url": "",
                "open_in_new_tab": false
            }')

        wopr_authentik_api POST "/core/applications/" "$app_data" > /dev/null 2>&1

        # Store the provider credentials — the peer needs these
        wopr_setting_set "mesh_fed_${peer_fingerprint:0:12}_provider_pk" "$provider_pk"
        wopr_setting_set "mesh_fed_${peer_fingerprint:0:12}_provider_client_id" "$provider_client_id"
        wopr_setting_set "mesh_fed_${peer_fingerprint:0:12}_provider_client_secret" "$provider_client_secret"

        wopr_log "OK" "Authentik federation provider created for peer ${peer_domain}"
    else
        wopr_log "WARN" "Failed to create federation provider for peer ${peer_domain}"
    fi

    # 3. Send our federation credentials to the peer so they can configure their side
    local my_identity=$(wopr_mesh_get_identity)
    local fed_exchange=$(jq -n \
        --argjson identity "$my_identity" \
        --arg provider_client_id "$provider_client_id" \
        --arg provider_client_secret "$provider_client_secret" \
        --arg issuer "https://auth.${my_domain}/application/o/mesh-${peer_fingerprint:0:12}/" \
        '{
            "identity": $identity,
            "federation_credentials": {
                "client_id": $provider_client_id,
                "client_secret": $provider_client_secret,
                "issuer": $issuer,
                "authorization_url": ("https://auth." + $identity.domain + "/application/o/authorize/"),
                "token_url": ("https://auth." + $identity.domain + "/application/o/token/"),
                "userinfo_url": ("https://auth." + $identity.domain + "/application/o/userinfo/"),
                "jwks_url": ("https://auth." + $identity.domain + "/application/o/mesh-" + ($identity.fingerprint | .[0:12]) + "/jwks/")
            }
        }')

    local peer_mesh_url="https://mesh.${peer_domain}"
    local exchange_response=$(curl -s -w "\n%{http_code}" \
        -X POST "${peer_mesh_url}/api/v1/mesh/federation-exchange" \
        -H "Content-Type: application/json" \
        -d "$fed_exchange" \
        --connect-timeout 10 \
        --max-time 30)

    local exchange_code=$(echo "$exchange_response" | tail -n1)
    if [ "$exchange_code" -eq 200 ]; then
        wopr_log "OK" "Federation credentials exchanged with ${peer_domain}"
    else
        wopr_log "WARN" "Federation credential exchange deferred with ${peer_domain} (will retry)"
    fi
}

wopr_mesh_remove_federation() {
    # Remove Authentik federation for a peer
    local peer_fingerprint="$1"
    local short_fp="${peer_fingerprint:0:12}"

    local source_pk=$(wopr_setting_get "mesh_fed_${short_fp}_source_pk")
    local provider_pk=$(wopr_setting_get "mesh_fed_${short_fp}_provider_pk")

    if [ -n "$source_pk" ]; then
        wopr_authentik_api DELETE "/sources/oauth/${source_pk}/" > /dev/null 2>&1
        wopr_log "INFO" "Removed OAuth2 source for peer ${short_fp}"
    fi

    if [ -n "$provider_pk" ]; then
        wopr_authentik_api DELETE "/providers/oauth2/${provider_pk}/" > /dev/null 2>&1
        wopr_authentik_api DELETE "/core/applications/mesh-${short_fp}/" > /dev/null 2>&1
        wopr_log "INFO" "Removed federation provider for peer ${short_fp}"
    fi
}

#=================================================
# MESH HEALTH CHECK
#=================================================

wopr_mesh_health_check() {
    # Check connectivity to all peers
    local peers=$(wopr_mesh_list_peers)
    local total=$(echo "$peers" | jq 'length')
    local healthy=0
    local unhealthy=0

    for i in $(seq 0 $((total - 1))); do
        local peer=$(echo "$peers" | jq ".[$i]")
        local peer_domain=$(echo "$peer" | jq -r '.domain')
        local peer_fingerprint=$(echo "$peer" | jq -r '.fingerprint')
        local mesh_url="https://mesh.${peer_domain}"

        local status_code=$(curl -s -o /dev/null -w "%{http_code}" \
            "${mesh_url}/api/v1/mesh/ping" \
            --connect-timeout 5 \
            --max-time 10 2>/dev/null || echo "000")

        if [ "$status_code" = "200" ]; then
            healthy=$((healthy + 1))
        else
            unhealthy=$((unhealthy + 1))
            wopr_log "WARN" "Peer unreachable: ${peer_domain} (HTTP ${status_code})"

            # Update peer status
            local peer_file="${MESH_PEERS_DIR}/${peer_fingerprint}.json"
            if [ -f "$peer_file" ]; then
                local tmp=$(mktemp)
                jq ".last_check = \"$(date -Iseconds)\" | .last_check_status = \"unreachable\"" \
                    "$peer_file" > "$tmp" && mv "$tmp" "$peer_file"
            fi
        fi
    done

    wopr_log "INFO" "Mesh health: ${healthy}/${total} peers reachable (${unhealthy} unreachable)"
    echo "{\"total\": ${total}, \"healthy\": ${healthy}, \"unhealthy\": ${unhealthy}}"
}

#=================================================
# MESH SIGNING (for authenticated messages)
#=================================================

wopr_mesh_sign() {
    # Sign a message with this beacon's private key
    local message="$1"
    echo -n "$message" | openssl pkeyutl -sign -inkey "${MESH_DIR}/beacon.key" 2>/dev/null | base64 -w0
}

wopr_mesh_verify_signature() {
    # Verify a signature from a peer using their public key
    local message="$1"
    local signature_b64="$2"
    local pubkey_b64="$3"

    local tmp_pub=$(mktemp)
    local tmp_sig=$(mktemp)

    echo "$pubkey_b64" | base64 -d > "$tmp_pub" 2>/dev/null
    echo "$signature_b64" | base64 -d > "$tmp_sig" 2>/dev/null

    echo -n "$message" | openssl pkeyutl -verify -pubin -inkey "$tmp_pub" -sigfile "$tmp_sig" 2>/dev/null
    local result=$?

    rm -f "$tmp_pub" "$tmp_sig"
    return $result
}

#=================================================
# DEPLOY MESH AGENT
#=================================================

wopr_deploy_mesh() {
    wopr_log "INFO" "Deploying WOPR mesh network agent..."

    # Generate identity if not exists
    wopr_mesh_generate_identity

    local domain=$(wopr_setting_get "domain")

    # Create the mesh agent script (lightweight HTTP API using socat + bash)
    # In production this would be a proper Go/Python binary
    # For now we use a Python script since Python is already on the system
    cat > "$MESH_AGENT_SCRIPT" <<'AGENT_EOF'
#!/usr/bin/env python3
"""
WOPR Mesh Agent — Lightweight P2P mesh API for beacon peering.

Runs on each beacon, exposes REST endpoints for:
- Peer discovery and handshake
- Federation credential exchange
- Health monitoring
- Signed message verification

No external dependencies beyond Python stdlib + json files.
"""

import http.server
import json
import os
import subprocess
import sys
import threading
import time
from datetime import datetime
from urllib.parse import urlparse, parse_qs

MESH_DIR = "/etc/wopr/mesh"
PEERS_DIR = f"{MESH_DIR}/peers"
INVITES_DIR = f"{MESH_DIR}/invites"
SETTINGS_FILE = "/etc/wopr/settings.json"
MESH_PORT = 8099

def get_setting(key):
    try:
        with open(SETTINGS_FILE) as f:
            settings = json.load(f)
        return settings.get(key, "")
    except Exception:
        return ""

def set_setting(key, value):
    try:
        with open(SETTINGS_FILE) as f:
            settings = json.load(f)
    except Exception:
        settings = {}
    settings[key] = value
    with open(SETTINGS_FILE, "w") as f:
        json.dump(settings, f, indent=2)

def get_identity():
    identity_file = f"{MESH_DIR}/identity.json"
    if os.path.exists(identity_file):
        with open(identity_file) as f:
            return json.load(f)
    return None

def get_peers():
    peers = []
    if os.path.exists(PEERS_DIR):
        for fname in os.listdir(PEERS_DIR):
            if fname.endswith(".json"):
                with open(os.path.join(PEERS_DIR, fname)) as f:
                    peers.append(json.load(f))
    return peers

def verify_invite(invite_id, secret):
    invite_file = f"{INVITES_DIR}/{invite_id}.json"
    if not os.path.exists(invite_file):
        return False
    with open(invite_file) as f:
        invite = json.load(f)
    if invite.get("used"):
        return False
    if invite.get("secret") != secret:
        return False
    # Mark as used
    invite["used"] = True
    invite["used_at"] = datetime.now().isoformat()
    with open(invite_file, "w") as f:
        json.dump(invite, f, indent=2)
    return True

def add_peer(peer_identity):
    fp = peer_identity.get("fingerprint", "")
    if not fp:
        return False
    peer_file = os.path.join(PEERS_DIR, f"{fp}.json")
    peer_identity["peered_at"] = datetime.now().isoformat()
    peer_identity["status"] = "active"
    with open(peer_file, "w") as f:
        json.dump(peer_identity, f, indent=2)
    return True

def setup_federation_from_exchange(data):
    """Process federation credentials received from a peer."""
    identity = data.get("identity", {})
    creds = data.get("federation_credentials", {})
    fp = identity.get("fingerprint", "")
    domain = identity.get("domain", "")

    if not fp or not creds:
        return False

    # Store credentials for this peer
    short_fp = fp[:12]
    set_setting(f"mesh_fed_{short_fp}_remote_client_id", creds.get("client_id", ""))
    set_setting(f"mesh_fed_{short_fp}_remote_client_secret", creds.get("client_secret", ""))
    set_setting(f"mesh_fed_{short_fp}_remote_issuer", creds.get("issuer", ""))

    # Create OAuth2 Source in our Authentik pointing to the peer
    # This uses the bash helper via subprocess
    subprocess.run([
        "/bin/bash", "-c",
        f'source /opt/wopr/scripts/wopr_common.sh && '
        f'source /opt/wopr/scripts/modules/mesh.sh && '
        f'wopr_mesh_setup_federation_from_creds "{fp}" "{domain}" '
        f'"{creds.get("client_id", "")}" "{creds.get("client_secret", "")}" '
        f'"{creds.get("issuer", "")}" "{creds.get("authorization_url", "")}" '
        f'"{creds.get("token_url", "")}" "{creds.get("userinfo_url", "")}" '
        f'"{creds.get("jwks_url", "")}"'
    ], capture_output=True, timeout=30)

    return True


class MeshHandler(http.server.BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        # Suppress default access logs
        pass

    def send_json(self, code, data):
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def read_body(self):
        length = int(self.headers.get("Content-Length", 0))
        if length > 0:
            return json.loads(self.rfile.read(length))
        return {}

    def do_GET(self):
        path = urlparse(self.path).path

        if path == "/api/v1/mesh/ping":
            identity = get_identity()
            self.send_json(200, {
                "status": "ok",
                "beacon_id": identity.get("beacon_id", "") if identity else "",
                "fingerprint": identity.get("fingerprint", "") if identity else "",
                "mesh_version": "1.0",
                "timestamp": datetime.now().isoformat(),
                "peer_count": len(get_peers())
            })

        elif path == "/api/v1/mesh/identity":
            identity = get_identity()
            if identity:
                self.send_json(200, identity)
            else:
                self.send_json(500, {"error": "Identity not configured"})

        elif path == "/api/v1/mesh/peers":
            peers = get_peers()
            # Return sanitized peer list (no secrets)
            safe_peers = []
            for p in peers:
                safe_peers.append({
                    "beacon_id": p.get("beacon_id"),
                    "domain": p.get("domain"),
                    "fingerprint": p.get("fingerprint"),
                    "peered_at": p.get("peered_at"),
                    "status": p.get("status", "unknown")
                })
            self.send_json(200, {"peers": safe_peers, "count": len(safe_peers)})

        elif path == "/api/v1/mesh/health":
            peers = get_peers()
            self.send_json(200, {
                "status": "healthy",
                "peer_count": len(peers),
                "mesh_version": "1.0",
                "uptime": time.time()
            })

        else:
            self.send_json(404, {"error": "Not found"})

    def do_POST(self):
        path = urlparse(self.path).path

        if path == "/api/v1/mesh/handshake":
            # Incoming handshake from a peer accepting our invite
            data = self.read_body()
            invite_id = data.get("invite_id", "")
            secret = data.get("secret", "")
            peer_identity = data.get("peer_identity")

            if not invite_id or not secret or not peer_identity:
                self.send_json(400, {"error": "Missing invite_id, secret, or peer_identity"})
                return

            if not verify_invite(invite_id, secret):
                self.send_json(403, {"error": "Invalid or expired invite"})
                return

            # Add peer
            add_peer(peer_identity)

            # Setup federation in background
            threading.Thread(
                target=lambda: subprocess.run([
                    "/bin/bash", "-c",
                    f'source /opt/wopr/scripts/wopr_common.sh && '
                    f'source /opt/wopr/scripts/modules/mesh.sh && '
                    f'wopr_mesh_setup_federation \'{json.dumps(peer_identity)}\''
                ], capture_output=True, timeout=60)
            ).start()

            # Return our identity
            my_identity = get_identity()
            self.send_json(200, {
                "status": "peered",
                "peer_identity": my_identity
            })

        elif path == "/api/v1/mesh/federation-exchange":
            # Receive federation credentials from a peer
            data = self.read_body()
            if setup_federation_from_exchange(data):
                self.send_json(200, {"status": "received"})
            else:
                self.send_json(400, {"error": "Invalid federation data"})

        elif path == "/api/v1/mesh/verify":
            # Verify a signed message from a peer
            data = self.read_body()
            # For now, acknowledge receipt
            self.send_json(200, {"status": "verified"})

        elif path == "/api/v1/mesh/create-invite":
            # Generate an invite token (called by orchestrator or CLI)
            result = subprocess.run([
                "/bin/bash", "-c",
                "source /opt/wopr/scripts/wopr_common.sh && "
                "source /opt/wopr/scripts/modules/mesh.sh && "
                "wopr_mesh_create_invite"
            ], capture_output=True, text=True, timeout=15)
            invite_token = result.stdout.strip()
            if invite_token:
                identity = get_identity()
                self.send_json(200, {
                    "invite_token": invite_token,
                    "fingerprint": identity.get("fingerprint", "") if identity else "",
                    "domain": identity.get("domain", "") if identity else ""
                })
            else:
                self.send_json(500, {"error": "Failed to generate invite"})

        elif path == "/api/v1/mesh/accept-invite":
            # Accept an invite token (called by orchestrator for auto-peering)
            data = self.read_body()
            invite_token = data.get("invite_token", "")
            if not invite_token:
                self.send_json(400, {"error": "Missing invite_token"})
                return
            # Run accept in background
            threading.Thread(
                target=lambda: subprocess.run([
                    "/bin/bash", "-c",
                    f"source /opt/wopr/scripts/wopr_common.sh && "
                    f"source /opt/wopr/scripts/modules/mesh.sh && "
                    f"wopr_mesh_accept_invite '{invite_token}'"
                ], capture_output=True, timeout=60)
            ).start()
            self.send_json(200, {"status": "accepting", "message": "Invite acceptance in progress"})

        else:
            self.send_json(404, {"error": "Not found"})


def main():
    os.makedirs(PEERS_DIR, exist_ok=True)
    os.makedirs(INVITES_DIR, exist_ok=True)

    server = http.server.HTTPServer(("127.0.0.1", MESH_PORT), MeshHandler)
    print(f"WOPR Mesh Agent listening on 127.0.0.1:{MESH_PORT}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.shutdown()

if __name__ == "__main__":
    main()
AGENT_EOF

    chmod +x "$MESH_AGENT_SCRIPT"

    # Create systemd service for the mesh agent
    cat > "/etc/systemd/system/${MESH_SERVICE}.service" <<EOF
[Unit]
Description=WOPR Mesh Network Agent
After=network.target wopr-authentik-server.service
Wants=wopr-authentik-server.service

[Service]
Type=simple
Restart=always
RestartSec=10
ExecStart=/usr/bin/python3 ${MESH_AGENT_SCRIPT}
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
EOF

    systemctl daemon-reload
    systemctl enable "$MESH_SERVICE"
    systemctl start "$MESH_SERVICE"

    # Wait for mesh agent to be ready
    wopr_wait_for_port "127.0.0.1" "$MESH_PORT" 30

    # Add Caddy route for mesh API (public-facing for peering)
    wopr_caddy_add_route "mesh" "$MESH_PORT"

    # Record installation
    wopr_setting_set "module_mesh_installed" "true"
    wopr_setting_set "mesh_port" "$MESH_PORT"
    wopr_setting_set "mesh_url" "https://mesh.${domain}"
    wopr_defcon_log "MODULE_DEPLOYED" "mesh"

    wopr_log "OK" "Mesh network agent deployed"
    wopr_log "INFO" "Mesh API: https://mesh.${domain}"
    wopr_log "INFO" "Fingerprint: $(wopr_mesh_get_fingerprint)"
    wopr_log "INFO" "Peers: $(wopr_mesh_peer_count)"
}

wopr_remove_mesh() {
    wopr_log "INFO" "Removing mesh agent..."

    systemctl stop "$MESH_SERVICE" 2>/dev/null || true
    systemctl disable "$MESH_SERVICE" 2>/dev/null || true
    rm -f "/etc/systemd/system/${MESH_SERVICE}.service"
    systemctl daemon-reload

    wopr_caddy_remove_route "mesh"

    # Remove federation entries from Authentik
    for peer_file in "${MESH_PEERS_DIR}"/*.json; do
        [ -f "$peer_file" ] || continue
        local fp=$(jq -r '.fingerprint' "$peer_file")
        wopr_mesh_remove_federation "$fp"
    done

    wopr_log "INFO" "Mesh agent removed (identity and peer data preserved)"
}

wopr_status_mesh() {
    if systemctl is-active --quiet "$MESH_SERVICE" 2>/dev/null; then
        local peers=$(wopr_mesh_peer_count)
        echo "running (${peers} peers)"
    else
        echo "stopped"
    fi
}

#=================================================
# FEDERATION FROM RECEIVED CREDENTIALS
# (called by mesh agent Python process)
#=================================================

wopr_mesh_setup_federation_from_creds() {
    # Setup our Authentik OAuth2 source using credentials received from a peer
    local peer_fingerprint="$1"
    local peer_domain="$2"
    local client_id="$3"
    local client_secret="$4"
    local issuer="$5"
    local auth_url="$6"
    local token_url="$7"
    local userinfo_url="$8"
    local jwks_url="$9"

    local short_fp="${peer_fingerprint:0:12}"
    local source_slug="mesh-${short_fp}"
    local source_name="Mesh: ${peer_domain}"

    wopr_log "INFO" "Configuring federation source from peer ${peer_domain}..."

    local source_data=$(jq -n \
        --arg name "$source_name" \
        --arg slug "$source_slug" \
        --arg consumer_key "$client_id" \
        --arg consumer_secret "$client_secret" \
        --arg provider_type "openidconnect" \
        --arg oidc_well_known "${issuer}.well-known/openid-configuration" \
        --arg oidc_jwks_url "$jwks_url" \
        --arg authorization_url "$auth_url" \
        --arg access_token_url "$token_url" \
        --arg profile_url "$userinfo_url" \
        '{
            "name": $name,
            "slug": $slug,
            "enabled": true,
            "provider_type": $provider_type,
            "consumer_key": $consumer_key,
            "consumer_secret": $consumer_secret,
            "oidc_well_known_url": $oidc_well_known,
            "oidc_jwks_url": $oidc_jwks_url,
            "authorization_url": $authorization_url,
            "access_token_url": $access_token_url,
            "profile_url": $profile_url
        }')

    local response=$(wopr_authentik_api POST "/sources/oauth/" "$source_data")
    local source_pk=$(echo "$response" | jq -r '.pk // empty')

    if [ -n "$source_pk" ]; then
        wopr_log "OK" "Federation source configured from peer credentials: ${peer_domain}"
        wopr_setting_set "mesh_fed_${short_fp}_source_pk" "$source_pk"
    else
        wopr_log "WARN" "Failed to configure federation source for ${peer_domain}"
    fi
}

#=================================================
# MESH CRON (periodic health check + peer sync)
#=================================================

wopr_mesh_install_cron() {
    cat > /etc/cron.hourly/wopr-mesh-health <<'CRON_EOF'
#!/bin/bash
source /opt/wopr/scripts/wopr_common.sh
source /opt/wopr/scripts/modules/mesh.sh
wopr_mesh_health_check > /dev/null 2>&1
CRON_EOF
    chmod +x /etc/cron.hourly/wopr-mesh-health
    wopr_log "OK" "Mesh health check cron installed"
}
