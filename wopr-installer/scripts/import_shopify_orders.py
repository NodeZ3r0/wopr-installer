#!/usr/bin/env python3
"""
Import Shopify Orders Export CSV into Saleor via GraphQL
========================================================

Creates draft orders from Shopify order history and completes them.

Usage:
    python import_shopify_orders.py \
        --csv /path/to/orders_export.csv \
        --saleor-url https://shop.dudeabides.wopr.systems/graphql/ \
        --token <SALEOR_STAFF_TOKEN> \
        --channel default-channel

    Dry run:
        python import_shopify_orders.py --csv orders.csv --dry-run

Requires: pip install httpx
"""

import argparse
import csv
import json
import sys
import time
from collections import defaultdict
from typing import Dict, List, Optional

import io

# Fix Windows console encoding for unicode product names
if sys.stdout.encoding != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

try:
    import httpx
except ImportError:
    print("ERROR: httpx required. Install with: pip install httpx")
    sys.exit(1)


# ---------------------------------------------------------------------------
# Saleor GraphQL
# ---------------------------------------------------------------------------

CUSTOMER_LOOKUP = """
query CustomerByEmail($email: String!) {
  customers(filter: { search: $email }, first: 1) {
    edges {
      node {
        id
        email
      }
    }
  }
}
"""

DRAFT_ORDER_CREATE = """
mutation DraftOrderCreate($input: DraftOrderCreateInput!) {
  draftOrderCreate(input: $input) {
    order {
      id
      number
      status
    }
    errors {
      field
      message
      code
    }
  }
}
"""

DRAFT_ORDER_COMPLETE = """
mutation DraftOrderComplete($id: ID!) {
  draftOrderComplete(id: $id) {
    order {
      id
      number
      status
    }
    errors {
      field
      message
      code
    }
  }
}
"""

ORDER_NOTE_UPDATE = """
mutation OrderNoteUpdate($id: ID!, $input: OrderUpdateInput!) {
  orderUpdate(id: $id, input: $input) {
    order { id }
    errors { field message }
  }
}
"""

PRODUCT_TYPE_CREATE = """
mutation ProductTypeCreate($input: ProductTypeInput!) {
  productTypeCreate(input: $input) {
    productType { id name }
    errors { field message code }
  }
}
"""

PRODUCT_CREATE = """
mutation ProductCreate($input: ProductCreateInput!) {
  productCreate(input: $input) {
    product { id name }
    errors { field message code }
  }
}
"""

PRODUCT_CHANNEL_LISTING = """
mutation ProductChannelListingUpdate($id: ID!, $input: ProductChannelListingUpdateInput!) {
  productChannelListingUpdate(id: $id, input: $input) {
    product { id }
    errors { field message code }
  }
}
"""

PRODUCT_VARIANT_CREATE = """
mutation ProductVariantCreate($input: ProductVariantCreateInput!) {
  productVariantCreate(input: $input) {
    productVariant { id sku }
    errors { field message code }
  }
}
"""

PRODUCT_VARIANT_CHANNEL_LISTING = """
mutation ProductVariantChannelListingUpdate($id: ID!, $input: [ProductVariantChannelListingAddInput!]!) {
  productVariantChannelListingUpdate(id: $id, input: $input) {
    variant { id }
    errors { field message code }
  }
}
"""

CHANNEL_QUERY = """
query Channels {
  channels { id slug name currencyCode }
}
"""

VARIANTS_BY_SKU = """
query VariantsBySku($channel: String!, $after: String) {
  products(first: 100, channel: $channel, after: $after) {
    pageInfo { hasNextPage endCursor }
    edges {
      node {
        variants {
          id
          sku
        }
      }
    }
  }
}
"""


def gql(client: httpx.Client, url: str, token: str, query: str, variables: dict) -> dict:
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


# ---------------------------------------------------------------------------
# Shopify Order CSV Parsing
# ---------------------------------------------------------------------------

def parse_orders(csv_path: str) -> List[Dict]:
    """
    Parse Shopify orders CSV. Shopify exports one row per line item,
    so multiple rows can belong to the same order (grouped by 'Name').
    """
    with open(csv_path, "r", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))

    orders: Dict[str, Dict] = {}

    for row in rows:
        order_name = row.get("Name", "").strip()
        if not order_name:
            continue

        if order_name not in orders:
            orders[order_name] = {
                "name": order_name,
                "email": row.get("Email", "").strip().lower(),
                "created_at": row.get("Created at", ""),
                "financial_status": row.get("Financial Status", ""),
                "fulfillment_status": row.get("Fulfillment Status", ""),
                "currency": row.get("Currency", "USD"),
                "subtotal": row.get("Subtotal", "0"),
                "shipping": row.get("Shipping", "0"),
                "taxes": row.get("Taxes", "0"),
                "total": row.get("Total", "0"),
                "discount_code": row.get("Discount Code", ""),
                "discount_amount": row.get("Discount Amount", "0"),
                "billing_name": row.get("Billing Name", ""),
                "billing_address1": row.get("Billing Address1", ""),
                "billing_city": row.get("Billing City", ""),
                "billing_zip": row.get("Billing Zip", ""),
                "billing_province": row.get("Billing Province", ""),
                "billing_country": row.get("Billing Country", ""),
                "shipping_name": row.get("Shipping Name", ""),
                "shipping_address1": row.get("Shipping Address1", ""),
                "shipping_city": row.get("Shipping City", ""),
                "shipping_zip": row.get("Shipping Zip", ""),
                "shipping_province": row.get("Shipping Province", ""),
                "shipping_country": row.get("Shipping Country", ""),
                "line_items": [],
            }

        # Add line item
        qty = row.get("Lineitem quantity", "1")
        price = row.get("Lineitem price", "0")
        name = row.get("Lineitem name", "Unknown Item")
        sku = row.get("Lineitem sku", "")

        orders[order_name]["line_items"].append({
            "name": name,
            "quantity": int(qty) if qty else 1,
            "price": float(price) if price else 0.0,
            "sku": sku,
        })

    return list(orders.values())


# ---------------------------------------------------------------------------
# Import Logic
# ---------------------------------------------------------------------------

def import_orders(
    csv_path: str,
    saleor_url: str,
    token: str,
    channel_slug: str,
    dry_run: bool = False,
):
    orders = parse_orders(csv_path)
    print(f"Parsed {len(orders)} orders from {csv_path}")
    print(f"Saleor endpoint: {saleor_url}")
    print(f"Channel: {channel_slug}")
    print(f"Dry run: {dry_run}")
    print()

    client = httpx.Client()
    channel_id = None
    customer_cache: Dict[str, str] = {}  # email -> saleor user ID

    sku_map: Dict[str, str] = {}  # sku -> variant ID

    if not dry_run:
        # Verify connection and get channel ID
        try:
            result = gql(client, saleor_url, token, CHANNEL_QUERY, {})
            channels = result.get("data", {}).get("channels", [])
            for ch in channels:
                if ch["slug"] == channel_slug:
                    channel_id = ch["id"]
                    break
            if not channel_id:
                print(f"ERROR: Channel '{channel_slug}' not found. Available: {[c['slug'] for c in channels]}")
                sys.exit(1)
            print(f"Connected. Channel ID: {channel_id}")
        except Exception as e:
            print(f"ERROR: Cannot connect to Saleor: {e}")
            sys.exit(1)

        # Build SKU -> variant ID map
        print("Building SKU lookup table...")
        has_next = True
        cursor = None
        while has_next:
            result = gql(client, saleor_url, token, VARIANTS_BY_SKU,
                         {"channel": channel_slug, "after": cursor})
            products = result.get("data", {}).get("products", {})
            for edge in products.get("edges", []):
                for v in edge["node"].get("variants", []):
                    if v.get("sku"):
                        sku_map[v["sku"]] = v["id"]
            has_next = products.get("pageInfo", {}).get("hasNextPage", False)
            cursor = products.get("pageInfo", {}).get("endCursor")
        print(f"Loaded {len(sku_map)} SKU mappings")
        print()

    imported = 0
    errors = 0
    error_details: List[str] = []

    for i, order in enumerate(orders):
        email = order["email"]
        label = f"[{i+1}/{len(orders)}] {order['name']} ({email})"
        items_summary = ", ".join(
            f"{li['quantity']}x {li['name']} @ ${li['price']:.2f}"
            for li in order["line_items"]
        )

        if dry_run:
            print(f"  OK [dry-run] {label}")
            print(f"         Items: {items_summary}")
            print(f"         Total: ${order['total']}")
            imported += 1
            continue

        # Look up customer by email
        user_id = customer_cache.get(email)
        if not user_id and email:
            try:
                result = gql(client, saleor_url, token, CUSTOMER_LOOKUP, {"email": email})
                edges = result.get("data", {}).get("customers", {}).get("edges", [])
                if edges:
                    user_id = edges[0]["node"]["id"]
                    customer_cache[email] = user_id
            except Exception:
                pass

        # Build draft order input with line items
        lines = []
        skipped_lines = []
        for li in order["line_items"]:
            variant_id = sku_map.get(li["sku"]) if li["sku"] else None
            if variant_id:
                lines.append({
                    "quantity": li["quantity"],
                    "variantId": variant_id,
                    "forceNewLine": True,
                })
            else:
                skipped_lines.append(li["name"])

        if not lines:
            print(f"  SKIP {label} - no matching SKUs in Saleor")
            errors += 1
            error_details.append(f"{order['name']}: no matching SKUs")
            continue

        draft_input = {
            "channelId": channel_id,
            "lines": lines,
        }
        if user_id:
            draft_input["user"] = user_id
        elif email:
            draft_input["userEmail"] = email

        # Create draft order
        try:
            result = gql(client, saleor_url, token, DRAFT_ORDER_CREATE, {"input": draft_input})
            data = result.get("data", {}).get("draftOrderCreate", {})
            errs = data.get("errors", [])

            if errs:
                msg = "; ".join(f"{e['field']}: {e['message']}" for e in errs)
                print(f"  FAIL {label} - {msg}")
                error_details.append(f"{order['name']}: {msg}")
                errors += 1
                continue

            saleor_order = data.get("order", {})
            order_id = saleor_order.get("id", "")

            # Add note with Shopify metadata
            note = (
                f"Imported from Shopify | Order: {order['name']} | "
                f"Date: {order['created_at']} | Total: ${order['total']} | "
                f"Items: {items_summary}"
            )
            if skipped_lines:
                note += f" | Skipped (no SKU match): {', '.join(skipped_lines)}"
            try:
                gql(client, saleor_url, token, ORDER_NOTE_UPDATE, {
                    "id": order_id,
                    "input": {"internalComment": note},
                })
            except Exception:
                pass  # Non-critical

            # Complete the draft order
            try:
                gql(client, saleor_url, token, DRAFT_ORDER_COMPLETE, {"id": order_id})
            except Exception as e:
                print(f"  WARN {label} - draft created but not completed: {e}")

            print(f"  OK   {label} -> {saleor_order.get('number', order_id)}")
            imported += 1

        except Exception as e:
            print(f"  FAIL {label} - {e}")
            error_details.append(f"{order['name']}: {e}")
            errors += 1

        time.sleep(0.3)

    client.close()

    print()
    print("=" * 60)
    print("ORDER IMPORT SUMMARY")
    print("=" * 60)
    print(f"  Total orders:   {len(orders)}")
    print(f"  Imported:       {imported}")
    print(f"  Errors:         {errors}")
    if error_details:
        print()
        print("  Error details:")
        for ed in error_details:
            print(f"    - {ed}")
    print("=" * 60)


def main():
    parser = argparse.ArgumentParser(
        description="Import Shopify orders export CSV into Saleor"
    )
    parser.add_argument("--csv", required=True, help="Path to Shopify orders CSV")
    parser.add_argument(
        "--saleor-url",
        default="https://shop.dudeabides.wopr.systems/graphql/",
        help="Saleor GraphQL endpoint",
    )
    parser.add_argument("--token", help="Saleor staff API token")
    parser.add_argument("--channel", default="default-channel", help="Saleor channel slug")
    parser.add_argument("--dry-run", action="store_true", help="Parse without calling Saleor")
    args = parser.parse_args()

    if not args.dry_run and not args.token:
        print("ERROR: --token required (or use --dry-run)")
        sys.exit(1)

    import_orders(
        csv_path=args.csv,
        saleor_url=args.saleor_url,
        token=args.token or "",
        channel_slug=args.channel,
        dry_run=args.dry_run,
    )


if __name__ == "__main__":
    main()
