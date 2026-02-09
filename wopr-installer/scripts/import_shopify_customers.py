#!/usr/bin/env python3
"""
Import Shopify Customer Export CSV into Saleor via GraphQL
==========================================================

Usage:
    python import_shopify_customers.py \
        --csv /path/to/customers_export.csv \
        --saleor-url https://shop.dudeabides.wopr.systems/graphql/ \
        --token <SALEOR_STAFF_TOKEN> \
        --channel default-channel

    Dry run (no API calls):
        python import_shopify_customers.py --csv customers.csv --dry-run

    Include likely-fake accounts:
        python import_shopify_customers.py --csv customers.csv --include-fakes

Requires: pip install httpx
"""

import argparse
import csv
import hashlib
import json
import sys
import time
from typing import Dict, List, Optional, Tuple

try:
    import httpx
except ImportError:
    print("ERROR: httpx required. Install with: pip install httpx")
    sys.exit(1)


# ---------------------------------------------------------------------------
# Saleor GraphQL Mutations
# ---------------------------------------------------------------------------

CUSTOMER_CREATE = """
mutation CustomerCreate($input: UserCreateInput!) {
  customerCreate(input: $input) {
    user {
      id
      email
      firstName
      lastName
    }
    errors {
      field
      message
      code
    }
  }
}
"""

ADDRESS_CREATE = """
mutation AddressCreate($userId: ID!, $input: AddressInput!) {
  addressCreate(userId: $userId, input: $input) {
    address { id }
    errors { field message code }
  }
}
"""

CHANNEL_QUERY = """
query Channels {
  channels {
    id
    slug
    name
    currencyCode
  }
}
"""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def gql(client: httpx.Client, url: str, token: str, query: str, variables: dict) -> dict:
    """Execute a Saleor GraphQL request."""
    resp = client.post(
        url,
        json={"query": query, "variables": variables},
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        timeout=30,
    )
    data = resp.json()
    if "errors" in data and data["errors"]:
        raise RuntimeError(f"GraphQL errors: {data['errors']}")
    if resp.status_code >= 500:
        resp.raise_for_status()
    return data


def normalize_phone(phone: str) -> str:
    """Clean up phone number to E.164-ish format."""
    if not phone or not phone.strip():
        return ""
    p = phone.strip().replace("(", "").replace(")", "").replace(" ", "").replace("-", "")
    p = p.replace("(+1)", "+1")
    if p and not p.startswith("+"):
        digits = "".join(c for c in p if c.isdigit())
        if len(digits) == 11 and digits.startswith("1"):
            p = "+" + digits
        elif len(digits) == 10:
            p = "+1" + digits
    return p


def is_fake(row: Dict[str, str]) -> bool:
    """Detect likely bot/fake accounts from the Shopify export."""
    email = row.get("Email", "").lower()
    first = row.get("First Name", "")
    last = row.get("Last Name", "")

    # TikTok obfuscated emails
    if "scs.tiktokw" in email:
        return True

    # Random gibberish names: mixed-case 5-7 char strings
    for name in (first, last):
        if name and len(name) >= 4:
            uppers = sum(1 for c in name if c.isupper())
            if uppers >= 3 and not name.isupper():
                return True

    # No name, no orders, no address — likely bot signup
    if (not first and not last
            and row.get("Total Orders", "0") == "0"
            and not row.get("Default Address Address1", "").strip()):
        # Check if email looks auto-generated (8+ random chars before @)
        local = email.split("@")[0] if "@" in email else ""
        if len(local) >= 8 and not any(c.isalpha() and c.isupper() for c in local):
            # Heuristic: mostly lowercase + digits, long local part
            digit_ratio = sum(1 for c in local if c.isdigit()) / max(len(local), 1)
            if digit_ratio > 0.3:
                return True

    return False


# ---------------------------------------------------------------------------
# Import Logic
# ---------------------------------------------------------------------------

def import_customers(
    csv_path: str,
    saleor_url: str,
    token: str,
    channel: str,
    skip_fakes: bool = True,
    dry_run: bool = False,
):
    with open(csv_path, "r", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))

    print(f"Loaded {len(rows)} customers from {csv_path}")
    print(f"Saleor endpoint: {saleor_url}")
    print(f"Channel: {channel}")
    print(f"Skip fakes: {skip_fakes}")
    print(f"Dry run: {dry_run}")
    print()

    imported = 0
    skipped_fake = 0
    skipped_exists = 0
    errors = 0
    error_details: List[str] = []

    client = httpx.Client()

    # Verify Saleor connection
    if not dry_run:
        try:
            result = gql(client, saleor_url, token, CHANNEL_QUERY, {})
            channels = result.get("data", {}).get("channels", [])
            print(f"Connected to Saleor. Channels: {[c['slug'] for c in channels]}")
            print()
        except Exception as e:
            print(f"ERROR: Cannot connect to Saleor: {e}")
            sys.exit(1)

    for i, row in enumerate(rows):
        email = row.get("Email", "").strip().lower()
        first = row.get("First Name", "").strip()
        last = row.get("Last Name", "").strip()
        total_orders = int(row.get("Total Orders", "0"))
        total_spent = row.get("Total Spent", "0.00")

        if not email:
            continue

        if skip_fakes and is_fake(row):
            print(f"  SKIP [fake] {email}")
            skipped_fake += 1
            continue

        # Build note with Shopify metadata
        notes = []
        shopify_id = row.get("Customer ID", "")
        if shopify_id:
            notes.append(f"Shopify ID: {shopify_id}")
        notes.append(f"Shopify totals: ${total_spent} / {total_orders} orders")
        tags = row.get("Tags", "").strip()
        if tags:
            notes.append(f"Tags: {tags}")
        user_note = row.get("Note", "").strip()
        if user_note:
            notes.append(f"Note: {user_note}")

        customer_input = {
            "email": email,
            "firstName": first,
            "lastName": last,
            "isActive": True,
            "note": " | ".join(notes),
        }

        label = f"[{i+1}/{len(rows)}] {email}"

        if dry_run:
            addr = row.get("Default Address Address1", "").strip()
            print(f"  OK [dry-run] {label} ({first} {last})"
                  + (f" - {addr}" if addr else ""))
            imported += 1
            continue

        # Create customer
        try:
            result = gql(client, saleor_url, token, CUSTOMER_CREATE, {"input": customer_input})
            data = result.get("data", {}).get("customerCreate", {})
            errs = data.get("errors", [])

            if errs:
                if any(e.get("code") == "UNIQUE" for e in errs):
                    print(f"  SKIP [exists] {label}")
                    skipped_exists += 1
                    continue
                else:
                    msg = "; ".join(f"{e['field']}: {e['message']}" for e in errs)
                    print(f"  FAIL {label} - {msg}")
                    error_details.append(f"{email}: {msg}")
                    errors += 1
                    continue

            user_id = data.get("user", {}).get("id", "")
            print(f"  OK   {label} -> {user_id}")
            imported += 1

        except Exception as e:
            print(f"  FAIL {label} - {e}")
            error_details.append(f"{email}: {e}")
            errors += 1
            continue

        # Create address if available
        addr1 = row.get("Default Address Address1", "").strip()
        city = row.get("Default Address City", "").strip()
        country = row.get("Default Address Country Code", "").strip()

        if addr1 and city and country and user_id:
            address_input = {
                "firstName": first,
                "lastName": last,
                "streetAddress1": addr1,
                "streetAddress2": row.get("Default Address Address2", "").strip(),
                "city": city,
                "postalCode": row.get("Default Address Zip", "").strip(),
                "country": country.upper(),
                "phone": normalize_phone(
                    row.get("Default Address Phone", "")
                    or row.get("Phone", "")
                ),
            }

            province = row.get("Default Address Province Code", "").strip()
            if province:
                address_input["countryArea"] = province

            company = row.get("Default Address Company", "").strip()
            if company:
                address_input["companyName"] = company

            try:
                addr_result = gql(
                    client, saleor_url, token, ADDRESS_CREATE,
                    {"userId": user_id, "input": address_input},
                )
                addr_errs = addr_result.get("data", {}).get("addressCreate", {}).get("errors", [])
                if addr_errs:
                    print(f"         addr warning: {addr_errs}")
            except Exception as e:
                print(f"         addr error: {e}")

        # Small delay to avoid hammering the API
        time.sleep(0.2)

    client.close()

    # Summary
    print()
    print("=" * 60)
    print("IMPORT SUMMARY")
    print("=" * 60)
    print(f"  Total in CSV:      {len(rows)}")
    print(f"  Imported:          {imported}")
    print(f"  Skipped (fake):    {skipped_fake}")
    print(f"  Skipped (exists):  {skipped_exists}")
    print(f"  Errors:            {errors}")
    if error_details:
        print()
        print("  Error details:")
        for ed in error_details:
            print(f"    - {ed}")
    print("=" * 60)


def main():
    parser = argparse.ArgumentParser(
        description="Import Shopify customer export CSV into Saleor"
    )
    parser.add_argument("--csv", required=True, help="Path to Shopify customers CSV")
    parser.add_argument(
        "--saleor-url",
        default="https://shop.dudeabides.wopr.systems/graphql/",
        help="Saleor GraphQL endpoint",
    )
    parser.add_argument("--token", help="Saleor staff API token")
    parser.add_argument("--channel", default="default-channel", help="Saleor channel slug")
    parser.add_argument("--include-fakes", action="store_true", help="Don't filter likely-fake accounts")
    parser.add_argument("--dry-run", action="store_true", help="Parse and validate without calling Saleor")
    args = parser.parse_args()

    if not args.dry_run and not args.token:
        print("ERROR: --token required (or use --dry-run)")
        sys.exit(1)

    import_customers(
        csv_path=args.csv,
        saleor_url=args.saleor_url,
        token=args.token or "",
        channel=args.channel,
        skip_fakes=not args.include_fakes,
        dry_run=args.dry_run,
    )


if __name__ == "__main__":
    main()
