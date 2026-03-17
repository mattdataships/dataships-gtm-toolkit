from __future__ import annotations

"""Tier 1: AJAX-based fast path for checkout consent auditing.

Tries the lightweight HTTP approach:
  1. GET /products.json?limit=1 → extract variant ID
  2. POST /cart/add.js → add item to cart
  3. GET /checkout?skip_shop_pay=true → fetch checkout HTML
  4. Parse HTML for consent checkboxes

Returns an AuditResult on success, or None to signal escalation to Tier 2.
"""

import httpx

from config import TIER1_HTTPX_TIMEOUT
from models import AuditResult, ConsentCheckbox
from parsers import parse_checkout_html


async def tier1_audit(
    domain: str,
    enriched: dict,
    http_client: httpx.AsyncClient = None,  # unused now — kept for API compat
) -> AuditResult | None:
    """Run Tier 1 AJAX-based audit. Returns None if Tier 2 should be tried.

    Uses a FRESH httpx client per domain to isolate cookies (like incognito).
    The cart session cookie from /cart/add.js must carry to /checkout.
    """

    base_url = f"https://{domain}"
    notes_parts = []

    # Fresh client per domain — isolates cookies so cart state is preserved
    async with httpx.AsyncClient(
        follow_redirects=True,
        timeout=httpx.Timeout(TIER1_HTTPX_TIMEOUT),
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/122.0.0.0 Safari/537.36"
            ),
        },
    ) as client:

        # ------------------------------------------------------------------
        # Step 1: Get a variant ID from products.json
        # ------------------------------------------------------------------
        variant_id = None

        try:
            resp = await client.get(f"{base_url}/products.json?limit=1")
        except (httpx.ConnectError, httpx.ReadTimeout, httpx.ConnectTimeout):
            return None  # Network issue → Tier 2

        if resp.status_code != 200:
            return None  # Blocked or not standard Shopify → Tier 2

        try:
            data = resp.json()
            products = data.get("products", [])
            if not products:
                return None
            variant_id = products[0]["variants"][0]["id"]
        except (KeyError, IndexError, ValueError):
            return None

        # ------------------------------------------------------------------
        # Step 2: Add to cart
        # ------------------------------------------------------------------
        try:
            cart_resp = await client.post(
                f"{base_url}/cart/add.js",
                json={"items": [{"id": variant_id, "quantity": 1}]},
            )
        except (httpx.ConnectError, httpx.ReadTimeout, httpx.ConnectTimeout):
            return None

        if cart_resp.status_code == 405:
            return None  # Headless storefront → Tier 2

        if cart_resp.status_code == 422:
            # Product unavailable — try page 2
            try:
                resp2 = await client.get(f"{base_url}/products.json?limit=1&page=2")
                if resp2.status_code == 200:
                    data2 = resp2.json()
                    products2 = data2.get("products", [])
                    if products2:
                        variant_id = products2[0]["variants"][0]["id"]
                        cart_resp2 = await client.post(
                            f"{base_url}/cart/add.js",
                            json={"items": [{"id": variant_id, "quantity": 1}]},
                        )
                        if cart_resp2.status_code not in (200, 201):
                            return None
                    else:
                        return None
                else:
                    return None
            except Exception:
                return None

        elif cart_resp.status_code not in (200, 201):
            return None

        # ------------------------------------------------------------------
        # Step 3: Fetch checkout page (cookies carry the cart session)
        # ------------------------------------------------------------------
        checkout_url = f"{base_url}/checkout?skip_shop_pay=true"

        try:
            checkout_resp = await client.get(checkout_url)
        except (httpx.ConnectError, httpx.ReadTimeout, httpx.ConnectTimeout):
            return None

        final_url = str(checkout_resp.url)

        # Check for Shop Pay redirect
        if "shop.app" in final_url or "shopify.com/pay" in final_url:
            notes_parts.append("Redirected to Shop Pay despite skip_shop_pay")
            return None

        if checkout_resp.status_code in (404, 403):
            return None

        if checkout_resp.status_code != 200:
            return None

        html_content = checkout_resp.text

        # Sanity check: does this look like a checkout page?
        if "checkout" not in html_content.lower() and "payment" not in html_content.lower():
            notes_parts.append("Response doesn't look like checkout page")
            return None

    # ------------------------------------------------------------------
    # Step 4: Parse for consent checkboxes
    # ------------------------------------------------------------------
    parse_result = parse_checkout_html(html_content, final_url)

    # Determine confidence
    if parse_result.email_checkbox and parse_result.email_checkbox.detection_method == "standard_id":
        confidence = 0.95
    elif parse_result.email_checkbox:
        confidence = 0.80
    else:
        confidence = 0.50
        notes_parts.append("No email consent checkbox found")

    notes = "; ".join(notes_parts) if notes_parts else ""

    return AuditResult(
        domain=domain,
        merchant_name=enriched.get("merchant_name", ""),
        country_code=enriched.get("country_code", ""),
        checkout_url=final_url,
        email_checkbox=parse_result.email_checkbox,
        sms_checkbox=parse_result.sms_checkbox,
        other_consent_elements=parse_result.other_consent_elements,
        confidence_score=confidence,
        tier_used=1,
        has_checkout_blocks=enriched.get("has_checkout_blocks", False),
        has_dataships=enriched.get("has_dataships", False),
        notes=notes,
        error=None,
    )
