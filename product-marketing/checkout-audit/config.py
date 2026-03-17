"""Configuration constants for checkout consent audit."""

import os

# === Paths ===
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_DIR = os.path.dirname(os.path.dirname(BASE_DIR))
INPUT_CSV = os.path.join(REPO_DIR, "data", "storeleads-tam.csv")
OUTPUT_CSV = os.path.expanduser("~/Downloads/checkout_audit_results.csv")
ERROR_LOG = os.path.expanduser("~/Downloads/checkout_audit_errors.csv")
PROGRESS_FILE = os.path.expanduser("~/Downloads/checkout_audit_progress.txt")

# === Standard Shopify Checkout Selectors ===
STANDARD_EMAIL_ID = "marketing_opt_in"
STANDARD_SMS_ID = "sms_marketing_opt_in"

# === Keyword Classifiers ===
EMAIL_KEYWORDS = [
    "email me", "email", "news and offers", "newsletter", "marketing emails",
    "exclusive deals", "sign me up", "opt-in", "opt in", "promotions",
    "receive email", "email updates",
]
SMS_KEYWORDS = [
    "text me", "sms", "text message", "mobile", "text updates",
    "text with", "receive text", "text news",
]
CONSENT_KEYWORDS = EMAIL_KEYWORDS + SMS_KEYWORDS + [
    "subscribe", "marketing", "consent", "agree to receive",
    "unsubscribe", "opt-in", "opt in",
]

# === Timeouts (milliseconds for Playwright, seconds for httpx) ===
TIER1_HTTPX_TIMEOUT = 15.0
TIER2_PAGE_TIMEOUT = 30000
TIER2_NAV_TIMEOUT = 20000

# === Throttling & Concurrency ===
REQUEST_DELAY_SECONDS = 2.5
CONCURRENT_WORKERS = 8
MAX_RETRIES = 2

# === Browser Config ===
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/122.0.0.0 Safari/537.36"
)
VIEWPORT = {"width": 1280, "height": 800}

# === Add to Cart Button Selectors (priority order) ===
ATC_SELECTORS = [
    'button[name="add"]',
    'button[type="submit"][form*="cart"]',
    'button:has-text("Add to Cart")',
    'button:has-text("Add to Bag")',
    'button:has-text("ADD TO CART")',
    'button:has-text("ADD TO BAG")',
    'input[type="submit"][value*="Add"]',
    '[data-testid="add-to-cart"]',
    '[data-action="add-to-cart"]',
    'button:has-text("Add To Cart")',
]

# === Checkout Button Selectors (priority order) ===
CHECKOUT_SELECTORS = [
    'a[href*="/checkout"]:has-text("Check out")',
    'a[href*="/checkout"]:has-text("Checkout")',
    'button:has-text("Check out")',
    'button:has-text("Checkout")',
    'button:has-text("CHECK OUT")',
    'button:has-text("CHECKOUT")',
    'a[href*="/checkout"]',
    '[data-testid="checkout"]',
    '[data-action="checkout"]',
    '.cart-drawer a[href*="/checkout"]',
    '.mini-cart a[href*="/checkout"]',
]

# === Cookie Banner Dismiss Selectors ===
COOKIE_DISMISS_SELECTORS = [
    'button:has-text("Decline")',
    'button:has-text("Reject")',
    'button:has-text("Deny")',
    'button:has-text("Accept")',
    'button:has-text("Got it")',
    'button:has-text("OK")',
    '[id*="cookie"] button',
    '[class*="cookie"] button:has-text("Close")',
    'button[aria-label="Close"]',
]
