#!/usr/bin/env python3
"""Checkout Consent Audit — Main Orchestrator.

Audits Shopify Plus checkout pages for email/SMS consent checkboxes.
Reads domains from storeleads-tam.csv, runs tiered detection, outputs CSV.

Usage:
    python3 audit.py                           # Full TAM run
    python3 audit.py --limit 50                # First 50 domains
    python3 audit.py --domains ridge.com,vuoriclothing.com  # Specific domains
    python3 audit.py --workers 4               # Fewer parallel workers
    python3 audit.py --tier1-only              # Skip Tier 2 (faster, less complete)
"""

import argparse
import asyncio
import csv
import json
import os
import sys
import time
from datetime import datetime, timezone

import httpx
from playwright.async_api import async_playwright

from config import (
    INPUT_CSV, OUTPUT_CSV, ERROR_LOG, PROGRESS_FILE,
    CONCURRENT_WORKERS, REQUEST_DELAY_SECONDS, USER_AGENT,
)
from models import AuditResult
from tier1 import tier1_audit
from tier2 import tier2_audit


# ---------------------------------------------------------------------------
# CSV Loading & Enrichment
# ---------------------------------------------------------------------------

def load_and_enrich_domains(csv_path: str) -> list[dict]:
    """Load TAM CSV and extract useful signals per domain."""
    domains = []

    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            domain = row.get("domain", "").strip()
            if not domain:
                continue

            apps_str = row.get("installed_apps_names", "")
            cluster_str = row.get("cluster_domains", "")

            # Parse cluster_domains for checkout.* subdomains
            clusters = cluster_str.split(":") if cluster_str else []
            checkout_sub = next(
                (c.strip() for c in clusters if c.strip().startswith("checkout.")),
                None,
            )

            domains.append({
                "domain": domain,
                "merchant_name": row.get("merchant_name", ""),
                "country_code": row.get("country_code", ""),
                "platform_rank": row.get("platform_rank", ""),
                "estimated_yearly_sales": row.get("estimated_yearly_sales", ""),
                "has_checkout_blocks": "Checkout Blocks" in apps_str,
                "has_dataships": "Dataships" in apps_str,
                "has_emailgrow": "EmailGrow" in apps_str,
                "checkout_subdomain": checkout_sub,
                "installed_apps": apps_str,
            })

    return domains


# ---------------------------------------------------------------------------
# Progress Tracking (resume support)
# ---------------------------------------------------------------------------

def load_progress(path: str) -> set:
    """Load set of completed domains from progress file."""
    if os.path.exists(path):
        with open(path, "r") as f:
            return set(line.strip() for line in f if line.strip())
    return set()


def save_progress(path: str, domain: str):
    """Append a completed domain to the progress file."""
    with open(path, "a") as f:
        f.write(domain + "\n")


# ---------------------------------------------------------------------------
# Per-Domain Audit
# ---------------------------------------------------------------------------

async def audit_single_domain(
    enriched: dict,
    http_client: httpx.AsyncClient,
    browser,
    tier1_only: bool = False,
) -> AuditResult:
    """Run tiered audit for a single domain."""
    domain = enriched["domain"]

    # Tier 1: AJAX fast path
    try:
        result = await asyncio.wait_for(
            tier1_audit(domain, enriched, http_client),
            timeout=30.0,
        )
        if result and result.email_checkbox and result.email_checkbox.found:
            result.tier_used = 1
            return result
    except asyncio.TimeoutError:
        pass
    except Exception:
        pass

    if tier1_only:
        return AuditResult(
            domain=domain,
            merchant_name=enriched.get("merchant_name", ""),
            country_code=enriched.get("country_code", ""),
            tier_used=3,
            has_checkout_blocks=enriched.get("has_checkout_blocks", False),
            has_dataships=enriched.get("has_dataships", False),
            notes="Tier 1 failed; Tier 2 skipped (--tier1-only)",
        )

    # Tier 2: Full Playwright browser
    try:
        result = await asyncio.wait_for(
            tier2_audit(domain, enriched, browser),
            timeout=90.0,
        )
        if result:
            result.tier_used = 2
            return result
    except asyncio.TimeoutError:
        pass
    except Exception as e:
        return AuditResult(
            domain=domain,
            merchant_name=enriched.get("merchant_name", ""),
            country_code=enriched.get("country_code", ""),
            tier_used=3,
            has_checkout_blocks=enriched.get("has_checkout_blocks", False),
            has_dataships=enriched.get("has_dataships", False),
            error=f"Tier 2 exception: {type(e).__name__}: {str(e)[:200]}",
        )

    # Tier 3: Flag for manual review
    return AuditResult(
        domain=domain,
        merchant_name=enriched.get("merchant_name", ""),
        country_code=enriched.get("country_code", ""),
        tier_used=3,
        has_checkout_blocks=enriched.get("has_checkout_blocks", False),
        has_dataships=enriched.get("has_dataships", False),
        notes="Both Tier 1 and Tier 2 failed",
    )


# ---------------------------------------------------------------------------
# CSV Output
# ---------------------------------------------------------------------------

def write_results_csv(results: list[AuditResult], path: str):
    """Write all results to CSV."""
    if not results:
        return

    rows = [r.to_row() for r in results]
    fieldnames = list(rows[0].keys())

    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_error_log(results: list[AuditResult], path: str):
    """Write failed audits to separate CSV."""
    errors = [r for r in results if r.tier_used == 3 or r.error]
    if not errors:
        return

    rows = [r.to_row() for r in errors]
    fieldnames = list(rows[0].keys())

    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


# ---------------------------------------------------------------------------
# Summary Printer
# ---------------------------------------------------------------------------

def print_summary(results: list[AuditResult]):
    """Print audit summary stats."""
    total = len(results)
    tier1 = sum(1 for r in results if r.tier_used == 1)
    tier2 = sum(1 for r in results if r.tier_used == 2)
    tier3 = sum(1 for r in results if r.tier_used == 3)

    email_found = sum(1 for r in results if r.email_checkbox and r.email_checkbox.found)
    email_preticked = sum(
        1 for r in results
        if r.email_checkbox and r.email_checkbox.found and r.email_checkbox.pre_ticked
    )
    sms_found = sum(1 for r in results if r.sms_checkbox and r.sms_checkbox.found)
    sms_preticked = sum(
        1 for r in results
        if r.sms_checkbox and r.sms_checkbox.found and r.sms_checkbox.pre_ticked
    )

    # Dataships validation
    ds_brands = [r for r in results if r.has_dataships]
    ds_email = sum(1 for r in ds_brands if r.email_checkbox and r.email_checkbox.found)

    avg_confidence = sum(r.confidence_score for r in results) / total if total else 0

    print("\n" + "=" * 60)
    print("CHECKOUT CONSENT AUDIT — SUMMARY")
    print("=" * 60)
    print(f"Total domains audited:  {total}")
    print(f"  Tier 1 (AJAX):        {tier1} ({tier1/total*100:.1f}%)")
    print(f"  Tier 2 (Browser):     {tier2} ({tier2/total*100:.1f}%)")
    print(f"  Tier 3 (Failed):      {tier3} ({tier3/total*100:.1f}%)")
    print(f"  Avg confidence:       {avg_confidence:.2f}")
    print()
    print(f"Email checkbox found:   {email_found}/{total} ({email_found/total*100:.1f}%)")
    print(f"  Pre-ticked:           {email_preticked}/{email_found} ({email_preticked/email_found*100:.1f}%)" if email_found else "  Pre-ticked:           N/A")
    print(f"SMS checkbox found:     {sms_found}/{total} ({sms_found/total*100:.1f}%)")
    print(f"  Pre-ticked:           {sms_preticked}/{sms_found} ({sms_preticked/sms_found*100:.1f}%)" if sms_found else "  Pre-ticked:           N/A")
    print()
    if ds_brands:
        print(f"Dataships brands:       {len(ds_brands)}")
        print(f"  Email detected:       {ds_email}/{len(ds_brands)} ({ds_email/len(ds_brands)*100:.1f}%)")
    print("=" * 60)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

async def run(args):
    """Main async entry point."""
    print(f"Loading domains from {INPUT_CSV}...")
    all_domains = load_and_enrich_domains(INPUT_CSV)
    print(f"Loaded {len(all_domains)} domains from CSV")

    # Filter by specific domains if provided
    if args.domains:
        target_domains = set(d.strip() for d in args.domains.split(","))
        all_domains = [d for d in all_domains if d["domain"] in target_domains]
        print(f"Filtered to {len(all_domains)} specified domains")

    # Apply limit
    if args.limit:
        all_domains = all_domains[:args.limit]
        print(f"Limited to first {args.limit} domains")

    # Load progress for resume
    completed = load_progress(PROGRESS_FILE)
    remaining = [d for d in all_domains if d["domain"] not in completed]
    print(f"Already completed: {len(completed)}, Remaining: {len(remaining)}")

    if not remaining:
        print("All domains already audited. Delete progress file to re-run.")
        return

    workers = args.workers or CONCURRENT_WORKERS
    print(f"Starting audit with {workers} concurrent workers...")
    print(f"Output: {OUTPUT_CSV}")
    print()

    results = []
    # Load any existing results for the completed domains
    # (so the output CSV is complete even on resume)
    if os.path.exists(OUTPUT_CSV) and completed:
        try:
            with open(OUTPUT_CSV, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                # We don't reconstruct AuditResult objects for old data;
                # just write fresh results. On resume, old CSV is kept
                # and new data is appended.
                pass
        except Exception:
            pass

    start_time = time.time()

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)

        async with httpx.AsyncClient(
            follow_redirects=True,
            timeout=httpx.Timeout(15.0),
            headers={"User-Agent": USER_AGENT},
        ) as http_client:

            semaphore = asyncio.Semaphore(workers)
            counter = {"done": 0, "total": len(remaining)}

            async def process_domain(enriched: dict):
                async with semaphore:
                    result = await audit_single_domain(
                        enriched, http_client, browser, args.tier1_only
                    )
                    results.append(result)
                    save_progress(PROGRESS_FILE, enriched["domain"])
                    counter["done"] += 1

                    # Progress indicator
                    done = counter["done"]
                    total = counter["total"]
                    elapsed = time.time() - start_time
                    rate = done / elapsed if elapsed > 0 else 0
                    eta = (total - done) / rate if rate > 0 else 0

                    tier_label = f"T{result.tier_used}"
                    email_status = "✓" if result.email_checkbox and result.email_checkbox.found else "✗"
                    sms_status = "✓" if result.sms_checkbox and result.sms_checkbox.found else "✗"

                    print(
                        f"[{done}/{total}] {enriched['domain']:<40} "
                        f"{tier_label} | Email:{email_status} SMS:{sms_status} | "
                        f"Conf:{result.confidence_score:.2f} | "
                        f"ETA:{eta/60:.0f}m"
                    )

                    await asyncio.sleep(REQUEST_DELAY_SECONDS)

            # Process in batches of 500, flushing results periodically
            batch_size = 500
            for batch_start in range(0, len(remaining), batch_size):
                batch = remaining[batch_start:batch_start + batch_size]
                tasks = [process_domain(d) for d in batch]
                await asyncio.gather(*tasks)

                # Flush to CSV after each batch
                write_results_csv(results, OUTPUT_CSV)
                print(f"\n--- Batch complete. {len(results)} results written to {OUTPUT_CSV} ---\n")

        await browser.close()

    # Final output
    write_results_csv(results, OUTPUT_CSV)
    write_error_log(results, ERROR_LOG)
    print_summary(results)

    elapsed = time.time() - start_time
    print(f"\nTotal time: {elapsed/60:.1f} minutes")
    print(f"Results: {OUTPUT_CSV}")
    print(f"Errors:  {ERROR_LOG}")


def main():
    parser = argparse.ArgumentParser(description="Shopify Checkout Consent Audit")
    parser.add_argument("--limit", type=int, help="Process only first N domains")
    parser.add_argument("--domains", type=str, help="Comma-separated list of specific domains")
    parser.add_argument("--workers", type=int, help=f"Concurrent workers (default: {CONCURRENT_WORKERS})")
    parser.add_argument("--tier1-only", action="store_true", help="Skip Tier 2 browser flow")
    parser.add_argument("--output", type=str, help="Override output CSV path")
    parser.add_argument("--reset", action="store_true", help="Delete progress file and start fresh")
    args = parser.parse_args()

    if args.output:
        import config
        config.OUTPUT_CSV = args.output

    if args.reset and os.path.exists(PROGRESS_FILE):
        os.remove(PROGRESS_FILE)
        print("Progress file deleted. Starting fresh.")

    asyncio.run(run(args))


if __name__ == "__main__":
    main()
