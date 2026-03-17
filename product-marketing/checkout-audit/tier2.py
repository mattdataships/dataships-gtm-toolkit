from __future__ import annotations

"""Tier 2: Full Playwright browser flow for checkout consent auditing.

Used when Tier 1 fails (headless storefronts, blocked APIs, Shop Pay redirects).
Launches a real browser context (incognito) per domain:
  1. Navigate to store → find a product → add to cart → checkout
  2. Handle Shop Pay redirects (guest checkout)
  3. Dismiss cookie banners
  4. Parse checkout page for consent checkboxes

Each domain gets a fresh BrowserContext (incognito — no saved Shop Pay sessions).
"""

import asyncio
from playwright.async_api import Browser, Page, TimeoutError as PWTimeout

from config import (
    TIER2_PAGE_TIMEOUT, TIER2_NAV_TIMEOUT, USER_AGENT, VIEWPORT,
    ATC_SELECTORS, CHECKOUT_SELECTORS, COOKIE_DISMISS_SELECTORS,
)
from models import AuditResult
from parsers import parse_checkout_html


async def tier2_audit(
    domain: str,
    enriched: dict,
    browser: Browser,
) -> AuditResult | None:
    """Run Tier 2 full browser audit. Returns AuditResult or None on total failure."""

    context = await browser.new_context(
        user_agent=USER_AGENT,
        viewport=VIEWPORT,
        locale="en-US",
        java_script_enabled=True,
        ignore_https_errors=True,
    )
    context.set_default_timeout(TIER2_PAGE_TIMEOUT)

    page = await context.new_page()
    notes_parts = []

    try:
        result = await _run_browser_flow(domain, enriched, page, notes_parts)
        return result
    except Exception as e:
        return AuditResult(
            domain=domain,
            merchant_name=enriched.get("merchant_name", ""),
            country_code=enriched.get("country_code", ""),
            confidence_score=0.0,
            tier_used=2,
            has_checkout_blocks=enriched.get("has_checkout_blocks", False),
            has_dataships=enriched.get("has_dataships", False),
            notes="; ".join(notes_parts),
            error=f"Tier 2 exception: {type(e).__name__}: {str(e)[:200]}",
        )
    finally:
        await context.close()


async def _run_browser_flow(
    domain: str,
    enriched: dict,
    page: Page,
    notes: list,
) -> AuditResult | None:
    """Core browser flow: homepage → product → add to cart → checkout → parse."""

    base_url = f"https://{domain}"

    # ------------------------------------------------------------------
    # Step 1: Try AJAX approach inside the browser first (works more often
    #         than raw httpx because we have proper cookies/JS context)
    # ------------------------------------------------------------------
    try:
        await page.goto(base_url, wait_until="domcontentloaded", timeout=TIER2_NAV_TIMEOUT)
    except PWTimeout:
        notes.append("Homepage load timed out")
        return None
    except Exception as e:
        notes.append(f"Homepage navigation failed: {str(e)[:100]}")
        return None

    await _dismiss_cookie_banner(page)
    await asyncio.sleep(1)

    # Try AJAX cart approach via page.evaluate
    ajax_result = await _try_ajax_in_browser(page, base_url)

    if ajax_result == "success":
        # Cart populated via AJAX, navigate to checkout
        notes.append("Tier 2: AJAX cart worked in browser context")
        try:
            await page.goto(
                f"{base_url}/checkout?skip_shop_pay=true",
                wait_until="domcontentloaded",
                timeout=TIER2_NAV_TIMEOUT,
            )
        except PWTimeout:
            notes.append("Checkout page load timed out after AJAX cart")
            # Fall through to full navigation
            ajax_result = "failed"

    if ajax_result != "success":
        # ------------------------------------------------------------------
        # Step 2: Full navigation — find product, add to cart, checkout
        # ------------------------------------------------------------------
        notes.append("Tier 2: Using full navigation flow")

        # Find a product page
        product_found = await _navigate_to_product(page, base_url, notes)
        if not product_found:
            notes.append("Could not find any product page")
            return None

        # Click Add to Cart
        atc_clicked = await _click_add_to_cart(page, notes)
        if not atc_clicked:
            notes.append("Could not click Add to Cart")
            return None

        await asyncio.sleep(2)  # Wait for cart drawer / animation

        # Click Checkout
        checkout_reached = await _click_checkout(page, base_url, notes)
        if not checkout_reached:
            notes.append("Could not reach checkout")
            return None

    # ------------------------------------------------------------------
    # Step 3: Handle Shop Pay redirect
    # ------------------------------------------------------------------
    await asyncio.sleep(2)  # Let redirects settle
    current_url = page.url

    if "shop.app" in current_url or "shopify.com/pay" in current_url:
        notes.append("Redirected to Shop Pay, attempting guest checkout")
        guest_ok = await _handle_shop_pay(page, domain, notes)
        if not guest_ok:
            notes.append("Could not bypass Shop Pay")
            return None
        current_url = page.url

    # ------------------------------------------------------------------
    # Step 4: Parse checkout page
    # ------------------------------------------------------------------
    # Wait a moment for any JS-rendered checkboxes
    await asyncio.sleep(2)

    html_content = await page.content()
    parse_result = parse_checkout_html(html_content, current_url)

    # Also try direct Playwright checkbox inspection for JS-rendered state
    # (HTML parsing might miss dynamically-set checked state)
    await _enhance_with_playwright_state(page, parse_result)

    # Determine confidence
    if parse_result.email_checkbox and parse_result.email_checkbox.detection_method == "standard_id":
        confidence = 0.90
    elif parse_result.email_checkbox:
        confidence = 0.75
    else:
        confidence = 0.40
        notes.append("No email consent checkbox found via Tier 2")

    return AuditResult(
        domain=domain,
        merchant_name=enriched.get("merchant_name", ""),
        country_code=enriched.get("country_code", ""),
        checkout_url=current_url,
        email_checkbox=parse_result.email_checkbox,
        sms_checkbox=parse_result.sms_checkbox,
        other_consent_elements=parse_result.other_consent_elements,
        confidence_score=confidence,
        tier_used=2,
        has_checkout_blocks=enriched.get("has_checkout_blocks", False),
        has_dataships=enriched.get("has_dataships", False),
        notes="; ".join(notes),
    )


# ---------------------------------------------------------------------------
# Helper: AJAX cart in browser
# ---------------------------------------------------------------------------

async def _try_ajax_in_browser(page: Page, base_url: str) -> str:
    """Try AJAX products.json + cart/add.js inside the page context."""
    try:
        js_code = (
            "async (baseUrl) => {"
            "  try {"
            "    const prodResp = await fetch(baseUrl + '/products.json?limit=1');"
            "    if (!prodResp.ok) return 'products_failed_' + prodResp.status;"
            "    const prodData = await prodResp.json();"
            "    if (!prodData.products || !prodData.products.length) return 'no_products';"
            "    const variantId = prodData.products[0].variants[0].id;"
            "    const cartResp = await fetch(baseUrl + '/cart/add.js', {"
            "      method: 'POST',"
            "      headers: {'Content-Type': 'application/json'},"
            "      body: JSON.stringify({items: [{id: variantId, quantity: 1}]})"
            "    });"
            "    if (!cartResp.ok) return 'cart_failed_' + cartResp.status;"
            "    return 'success';"
            "  } catch (e) {"
            "    return 'error_' + e.message;"
            "  }"
            "}"
        )
        result = await page.evaluate(js_code, base_url)
        return result
    except Exception:
        return "evaluate_failed"


# ---------------------------------------------------------------------------
# Helper: Navigate to a product page
# ---------------------------------------------------------------------------

async def _navigate_to_product(page: Page, base_url: str, notes: list) -> bool:
    """Find and navigate to a product page.

    Uses href extraction + page.goto() instead of clicking links,
    because many product links are hidden (lazy-loaded, menus, etc.)
    and Playwright can't click non-visible elements.
    """

    async def _extract_product_href(p: Page) -> str | None:
        """Extract the href of the first product link on the page."""
        hrefs = await p.evaluate("""
            () => {
                const links = document.querySelectorAll('a[href*="/products/"]');
                for (const link of links) {
                    const href = link.getAttribute('href');
                    if (href && !href.includes('products.json') && !href.includes('#')) {
                        return href;
                    }
                }
                return null;
            }
        """)
        return hrefs

    # Strategy 1: Look for product links on current page (homepage)
    href = await _extract_product_href(page)
    if href:
        try:
            full_url = href if href.startswith("http") else f"{base_url}{href}"
            await page.goto(full_url, wait_until="domcontentloaded", timeout=TIER2_NAV_TIMEOUT)
            if "/products/" in page.url:
                return True
        except Exception:
            pass

    # Strategy 2: Try /collections/all
    try:
        await page.goto(f"{base_url}/collections/all", wait_until="domcontentloaded", timeout=TIER2_NAV_TIMEOUT)
        href = await _extract_product_href(page)
        if href:
            full_url = href if href.startswith("http") else f"{base_url}{href}"
            await page.goto(full_url, wait_until="domcontentloaded", timeout=TIER2_NAV_TIMEOUT)
            if "/products/" in page.url:
                return True
    except Exception:
        pass

    # Strategy 3: Try /collections, then first collection, then first product
    try:
        await page.goto(f"{base_url}/collections", wait_until="domcontentloaded", timeout=TIER2_NAV_TIMEOUT)
        col_href = await page.evaluate("""
            () => {
                const links = document.querySelectorAll('a[href*="/collections/"]');
                for (const link of links) {
                    const href = link.getAttribute('href');
                    if (href && href !== '/collections' && href !== '/collections/') {
                        return href;
                    }
                }
                return null;
            }
        """)
        if col_href:
            full_col = col_href if col_href.startswith("http") else f"{base_url}{col_href}"
            await page.goto(full_col, wait_until="domcontentloaded", timeout=TIER2_NAV_TIMEOUT)
            href = await _extract_product_href(page)
            if href:
                full_url = href if href.startswith("http") else f"{base_url}{href}"
                await page.goto(full_url, wait_until="domcontentloaded", timeout=TIER2_NAV_TIMEOUT)
                if "/products/" in page.url:
                    return True
    except Exception:
        pass

    return False


# ---------------------------------------------------------------------------
# Helper: Click Add to Cart
# ---------------------------------------------------------------------------

async def _click_add_to_cart(page: Page, notes: list) -> bool:
    """Find and click the Add to Cart button."""
    for selector in ATC_SELECTORS:
        try:
            btn = await page.query_selector(selector)
            if btn and await btn.is_visible():
                await btn.click()
                notes.append(f"ATC via: {selector}")
                return True
        except Exception:
            continue

    # Fallback: try any visible submit button on the page
    try:
        buttons = await page.query_selector_all('button[type="submit"], input[type="submit"]')
        for btn in buttons:
            text = (await btn.text_content() or "").lower()
            if any(kw in text for kw in ["add", "cart", "bag", "buy"]):
                if await btn.is_visible():
                    await btn.click()
                    notes.append(f"ATC via submit fallback: {text[:30]}")
                    return True
    except Exception:
        pass

    return False


# ---------------------------------------------------------------------------
# Helper: Click Checkout button
# ---------------------------------------------------------------------------

async def _click_checkout(page: Page, base_url: str, notes: list) -> bool:
    """Find and click the Checkout button, or navigate to cart then checkout."""

    # First, try checkout selectors directly (cart drawer may be open)
    for selector in CHECKOUT_SELECTORS:
        try:
            btn = await page.query_selector(selector)
            if btn and await btn.is_visible():
                await btn.click()
                await page.wait_for_load_state("domcontentloaded", timeout=TIER2_NAV_TIMEOUT)
                notes.append(f"Checkout via: {selector}")
                return True
        except Exception:
            continue

    # If no checkout button found, navigate to /cart and try again
    try:
        await page.goto(f"{base_url}/cart", wait_until="domcontentloaded", timeout=TIER2_NAV_TIMEOUT)
        await asyncio.sleep(1)

        for selector in CHECKOUT_SELECTORS:
            try:
                btn = await page.query_selector(selector)
                if btn and await btn.is_visible():
                    await btn.click()
                    await page.wait_for_load_state("domcontentloaded", timeout=TIER2_NAV_TIMEOUT)
                    notes.append(f"Checkout from /cart via: {selector}")
                    return True
            except Exception:
                continue

        # Last resort: direct navigation
        await page.goto(
            f"{base_url}/checkout?skip_shop_pay=true",
            wait_until="domcontentloaded",
            timeout=TIER2_NAV_TIMEOUT,
        )
        if "checkout" in page.url.lower():
            notes.append("Checkout via direct /checkout navigation")
            return True

    except Exception:
        pass

    return False


# ---------------------------------------------------------------------------
# Helper: Handle Shop Pay redirect
# ---------------------------------------------------------------------------

async def _handle_shop_pay(page: Page, domain: str, notes: list) -> bool:
    """Attempt to bypass Shop Pay and reach native Shopify checkout."""

    # Strategy 1: Look for guest checkout button
    guest_selectors = [
        'button:has-text("guest")',
        'a:has-text("guest")',
        'button:has-text("without Shop Pay")',
        'button:has-text("Continue without")',
        'a:has-text("Continue without")',
    ]
    for selector in guest_selectors:
        try:
            btn = await page.query_selector(selector)
            if btn and await btn.is_visible():
                await btn.click()
                await page.wait_for_load_state("domcontentloaded", timeout=TIER2_NAV_TIMEOUT)
                notes.append("Bypassed Shop Pay via guest checkout button")
                return True
        except Exception:
            continue

    # Strategy 2: Direct navigation with skip_shop_pay
    try:
        await page.goto(
            f"https://{domain}/checkout?skip_shop_pay=true",
            wait_until="domcontentloaded",
            timeout=TIER2_NAV_TIMEOUT,
        )
        if "shop.app" not in page.url and "shopify.com/pay" not in page.url:
            notes.append("Bypassed Shop Pay via direct URL with skip_shop_pay")
            return True
    except Exception:
        pass

    # Strategy 3: Try the checkout subdomain if known
    checkout_sub = enriched_get_checkout_subdomain(domain)
    if checkout_sub:
        try:
            await page.goto(
                f"https://{checkout_sub}",
                wait_until="domcontentloaded",
                timeout=TIER2_NAV_TIMEOUT,
            )
            notes.append(f"Used checkout subdomain: {checkout_sub}")
            return True
        except Exception:
            pass

    return False


def enriched_get_checkout_subdomain(domain: str) -> str | None:
    """Extract checkout subdomain from domain. Simple heuristic."""
    # Strip www. if present
    clean = domain.replace("www.", "")
    return f"checkout.{clean}"


# ---------------------------------------------------------------------------
# Helper: Dismiss cookie banners
# ---------------------------------------------------------------------------

async def _dismiss_cookie_banner(page: Page):
    """Best-effort cookie banner dismissal."""
    for selector in COOKIE_DISMISS_SELECTORS:
        try:
            btn = await page.query_selector(selector)
            if btn and await btn.is_visible():
                await btn.click()
                await asyncio.sleep(0.5)
                return
        except Exception:
            continue


# ---------------------------------------------------------------------------
# Helper: Enhance parse results with live Playwright checkbox state
# ---------------------------------------------------------------------------

async def _enhance_with_playwright_state(page: Page, parse_result):
    """Use Playwright to check live checkbox states (catches JS-rendered state).

    The HTML parser reads the static `checked` attribute, but JS may toggle
    checkboxes after page load. This reads the live DOM state.
    """
    try:
        live_states = await page.evaluate("""
            () => {
                const checkboxes = document.querySelectorAll('input[type="checkbox"]');
                const results = {};
                for (const cb of checkboxes) {
                    if (cb.id) {
                        results[cb.id] = cb.checked;
                    }
                }
                return results;
            }
        """)

        # Update email checkbox state if we have live data
        if parse_result.email_checkbox and parse_result.email_checkbox.element_id:
            eid = parse_result.email_checkbox.element_id
            if eid in live_states:
                parse_result.email_checkbox.pre_ticked = live_states[eid]

        # Update SMS checkbox state
        if parse_result.sms_checkbox and parse_result.sms_checkbox.element_id:
            sid = parse_result.sms_checkbox.element_id
            if sid in live_states:
                parse_result.sms_checkbox.pre_ticked = live_states[sid]

    except Exception:
        pass  # Non-critical enhancement
