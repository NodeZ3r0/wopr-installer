#!/usr/bin/env python3
"""
Migrate Printful Product Templates to Saleor Store
===================================================

Takes existing product templates (406 designs) and creates sync products
in the native Printful store, which then auto-syncs to Saleor via webhook.

Usage:
    python migrate_printful_templates.py --dry-run
    python migrate_printful_templates.py --limit 10
    python migrate_printful_templates.py --all

Requires: pip install httpx
"""

import argparse
import sys
import time
from typing import Dict, List, Optional

try:
    import httpx
except ImportError:
    print("ERROR: httpx required. Install with: pip install httpx")
    sys.exit(1)


# Printful API configuration
PRINTFUL_API_KEY = "BkycLM6MDIBjAhOgEpYxkkYPdPMbUeTmhycr75tN"
PRINTFUL_STORE_ID = "17263844"  # Native store for Saleor
PRINTFUL_BASE_URL = "https://api.printful.com"


def printful_api(method: str, endpoint: str, data: dict = None) -> dict:
    """Make a Printful API request."""
    url = f"{PRINTFUL_BASE_URL}{endpoint}"
    headers = {
        "Authorization": f"Bearer {PRINTFUL_API_KEY}",
        "Content-Type": "application/json",
    }

    with httpx.Client(timeout=60) as client:
        if method == "GET":
            resp = client.get(url, headers=headers)
        elif method == "POST":
            resp = client.post(url, headers=headers, json=data)
        else:
            raise ValueError(f"Unknown method: {method}")

    result = resp.json()
    if result.get("code", 200) >= 400:
        raise RuntimeError(f"Printful API error: {result}")

    return result


def get_all_templates() -> List[dict]:
    """Fetch all product templates from Printful."""
    templates = []
    offset = 0
    limit = 100

    while True:
        result = printful_api("GET", f"/product-templates?limit={limit}&offset={offset}")
        items = result.get("result", {}).get("items", [])
        templates.extend(items)

        paging = result.get("paging", {})
        total = paging.get("total", 0)

        if offset + limit >= total:
            break
        offset += limit
        time.sleep(0.3)  # Rate limiting

    return templates


def get_existing_products() -> Dict[str, int]:
    """Get existing products in the native store to avoid duplicates."""
    existing = {}
    offset = 0
    limit = 100

    while True:
        result = printful_api("GET", f"/store/products?store_id={PRINTFUL_STORE_ID}&limit={limit}&offset={offset}")
        items = result.get("result", [])

        for item in items:
            # Use title as key for deduplication
            existing[item["name"].lower().strip()] = item["id"]

        paging = result.get("paging", {})
        total = paging.get("total", 0)

        if offset + limit >= total:
            break
        offset += limit
        time.sleep(0.3)

    return existing


def create_product_from_template(template: dict, existing: Dict[str, int]) -> dict:
    """Create a sync product in the native store from a template."""
    template_id = template["id"]
    title = template["title"]
    product_id = template["product_id"]  # Printful catalog product
    variant_ids = template["available_variant_ids"]

    # Check if already exists
    if title.lower().strip() in existing:
        return {"status": "skip", "reason": "exists", "title": title}

    # Build sync product payload
    # Use the template to create variants
    sync_variants = []
    for vid in variant_ids:
        sync_variants.append({
            "variant_id": vid,
            "retail_price": "29.99",  # Default price, can be updated later
            "is_ignored": False,
        })

    payload = {
        "sync_product": {
            "name": title,
            "thumbnail": template.get("mockup_file_url"),
        },
        "sync_variants": sync_variants,
        "template_id": template_id,  # Link to template for print files
    }

    try:
        result = printful_api("POST", f"/store/products?store_id={PRINTFUL_STORE_ID}", payload)
        sync_product = result.get("result", {}).get("sync_product", {})
        return {
            "status": "created",
            "title": title,
            "sync_product_id": sync_product.get("id"),
            "variants": len(variant_ids),
        }
    except Exception as e:
        return {"status": "error", "title": title, "error": str(e)}


def migrate_templates(dry_run: bool = False, limit: int = None):
    """Migrate product templates to the native store."""
    print("=" * 70)
    print("PRINTFUL TEMPLATE MIGRATION")
    print("=" * 70)
    print(f"Store ID: {PRINTFUL_STORE_ID}")
    print(f"Dry run: {dry_run}")
    print(f"Limit: {limit or 'all'}")
    print()

    # Get all templates
    print("Fetching product templates...")
    templates = get_all_templates()
    print(f"Found {len(templates)} templates")
    print()

    if limit:
        templates = templates[:limit]
        print(f"Processing first {limit} templates")
        print()

    # Get existing products to avoid duplicates
    print("Checking existing products in store...")
    existing = get_existing_products()
    print(f"Found {len(existing)} existing products")
    print()

    # Process templates
    created = 0
    skipped = 0
    errors = 0
    error_details = []

    for i, template in enumerate(templates):
        label = f"[{i+1}/{len(templates)}] {template['title'][:50]}"

        if dry_run:
            if template['title'].lower().strip() in existing:
                print(f"  SKIP [exists] {label}")
                skipped += 1
            else:
                print(f"  OK [dry-run] {label} ({len(template['available_variant_ids'])} variants)")
                created += 1
            continue

        result = create_product_from_template(template, existing)

        if result["status"] == "created":
            print(f"  OK   {label} -> {result['sync_product_id']}")
            created += 1
            # Update existing dict to prevent duplicates in same run
            existing[template['title'].lower().strip()] = result['sync_product_id']
        elif result["status"] == "skip":
            print(f"  SKIP {label} - {result['reason']}")
            skipped += 1
        else:
            print(f"  FAIL {label} - {result['error']}")
            errors += 1
            error_details.append(f"{template['title']}: {result['error']}")

        time.sleep(0.5)  # Rate limiting

    # Summary
    print()
    print("=" * 70)
    print("MIGRATION SUMMARY")
    print("=" * 70)
    print(f"  Total templates:  {len(templates)}")
    print(f"  Created:          {created}")
    print(f"  Skipped:          {skipped}")
    print(f"  Errors:           {errors}")

    if error_details:
        print()
        print("  Error details:")
        for ed in error_details[:20]:
            print(f"    - {ed[:80]}")
        if len(error_details) > 20:
            print(f"    ... and {len(error_details) - 20} more")

    print("=" * 70)


def main():
    parser = argparse.ArgumentParser(
        description="Migrate Printful product templates to Saleor store"
    )
    parser.add_argument("--dry-run", action="store_true", help="Preview without creating products")
    parser.add_argument("--limit", type=int, help="Limit number of templates to process")
    parser.add_argument("--all", action="store_true", help="Process all templates (no limit)")
    args = parser.parse_args()

    if not args.dry_run and not args.limit and not args.all:
        print("ERROR: Specify --dry-run, --limit N, or --all")
        print("  --dry-run   Preview what would be created")
        print("  --limit N   Process first N templates")
        print("  --all       Process all templates")
        sys.exit(1)

    migrate_templates(
        dry_run=args.dry_run,
        limit=args.limit if not args.all else None,
    )


if __name__ == "__main__":
    main()
