from __future__ import annotations

"""4-layer checkbox detection and classification for Shopify checkout pages.

Layer 1: Standard Shopify IDs (marketing_opt_in, sms_marketing_opt_in)
Layer 2: Full checkbox scan with parent-text walk-up (Checkout Blocks / generic IDs)
Layer 3: Phone field detection (Ridge-style input[type=tel] + Subscribe)
Layer 4: Custom elements (toggle switches, ARIA controls)
"""

from dataclasses import dataclass, field
from typing import Optional
from lxml import html as lxml_html

from config import (
    STANDARD_EMAIL_ID, STANDARD_SMS_ID,
    EMAIL_KEYWORDS, SMS_KEYWORDS, CONSENT_KEYWORDS,
)
from models import ConsentCheckbox


@dataclass
class ParseResult:
    """Result of parsing a checkout page for consent elements."""
    email_checkbox: Optional[ConsentCheckbox] = None
    sms_checkbox: Optional[ConsentCheckbox] = None
    other_consent_elements: list = field(default_factory=list)
    all_checkboxes_found: int = 0
    consent_checkboxes_found: int = 0


def parse_checkout_html(html_content: str, url: str) -> ParseResult:
    """Main entry point. Parse checkout HTML for all consent elements.

    Uses a 4-layer detection strategy, combining results with deduplication.
    """
    try:
        tree = lxml_html.fromstring(html_content)
    except Exception:
        return ParseResult()

    # Layer 1: Standard Shopify IDs (highest confidence)
    standard = _find_standard_checkboxes(tree)

    # Layer 2: Full checkbox scan with parent-text walk-up
    scanned = _scan_all_checkboxes(tree)

    # Layer 3: Phone field subscribe pattern
    phone_fields = _find_phone_subscribe_fields(tree)

    # Layer 4: Custom consent elements (toggles, ARIA)
    custom = _find_custom_consent_elements(tree)

    # Count total checkboxes on page (for diagnostics)
    all_checkboxes = tree.cssselect('input[type="checkbox"]')
    total_checkboxes = len(all_checkboxes)

    # Merge all findings, standard takes priority
    all_found = standard + scanned + phone_fields + custom

    # Deduplicate by element_id, then by label_text
    seen_keys = set()
    deduped = []
    for item in all_found:
        key = item.element_id or (item.label_text or "")[:50]
        if key and key not in seen_keys:
            seen_keys.add(key)
            deduped.append(item)
        elif not key:
            deduped.append(item)

    # Extract primary email and SMS, rest goes to "other"
    email_cb = next((c for c in deduped if c.checkbox_type == "email"), None)
    sms_cb = next(
        (c for c in deduped if c.checkbox_type in ("sms", "phone_field_subscribe")),
        None,
    )
    others = [c for c in deduped if c is not email_cb and c is not sms_cb]

    return ParseResult(
        email_checkbox=email_cb,
        sms_checkbox=sms_cb,
        other_consent_elements=others,
        all_checkboxes_found=total_checkboxes,
        consent_checkboxes_found=len(deduped),
    )


# ---------------------------------------------------------------------------
# Layer 1: Standard Shopify IDs
# ---------------------------------------------------------------------------

def _find_standard_checkboxes(tree) -> list[ConsentCheckbox]:
    """Look for #marketing_opt_in and #sms_marketing_opt_in."""
    results = []

    for checkbox_id, cb_type in [
        (STANDARD_EMAIL_ID, "email"),
        (STANDARD_SMS_ID, "sms"),
    ]:
        elements = tree.cssselect(f'input#{checkbox_id}')
        if not elements:
            elements = tree.cssselect(f'[id="{checkbox_id}"]')
        if not elements:
            continue

        el = elements[0]
        is_checked = el.get("checked") is not None

        # Find label text via label[for]
        labels = tree.cssselect(f'label[for="{checkbox_id}"]')
        label_text = None
        if labels:
            label_text = _clean_text(labels[0].text_content())

        # Fallback: parent text if no label found
        if not label_text:
            label_text = _find_associated_text(tree, el)

        results.append(ConsentCheckbox(
            checkbox_type=cb_type,
            found=True,
            pre_ticked=is_checked,
            label_text=label_text,
            element_id=checkbox_id,
            detection_method="standard_id",
        ))

    return results


# ---------------------------------------------------------------------------
# Layer 2: Full Checkbox Scan (Checkout Blocks / generic IDs)
# ---------------------------------------------------------------------------

def _scan_all_checkboxes(tree) -> list[ConsentCheckbox]:
    """Find ALL input[type=checkbox], classify each by associated text.

    This catches Checkout Blocks patterns with generic IDs like Checkbox0.
    """
    results = []
    all_checkboxes = tree.cssselect('input[type="checkbox"]')

    for cb in all_checkboxes:
        cb_id = cb.get("id", "")

        # Skip standard IDs (already handled in Layer 1)
        if cb_id in (STANDARD_EMAIL_ID, STANDARD_SMS_ID):
            continue

        is_checked = cb.get("checked") is not None

        # Find associated text
        label_text = _find_associated_text(tree, cb)

        # Classify — skip if not consent-related
        cb_type = _classify_consent_text(label_text)
        if cb_type:
            results.append(ConsentCheckbox(
                checkbox_type=cb_type,
                found=True,
                pre_ticked=is_checked,
                label_text=label_text,
                element_id=cb_id or None,
                detection_method="checkbox_scan",
            ))

    return results


# ---------------------------------------------------------------------------
# Layer 3: Phone Field Detection (Ridge-style)
# ---------------------------------------------------------------------------

def _find_phone_subscribe_fields(tree) -> list[ConsentCheckbox]:
    """Detect phone number input + subscribe button pattern (not a checkbox)."""
    results = []
    phone_inputs = tree.cssselect('input[type="tel"]')

    for phone_input in phone_inputs:
        current = phone_input
        for _ in range(3):
            parent = current.getparent()
            if parent is None:
                break
            container_text = (parent.text_content() or "").lower()

            # Check if container has subscribe/SMS-related text
            has_sms_signal = any(
                kw in container_text
                for kw in ["subscribe", "sms", "text message", "opt in", "text me"]
            )
            if not has_sms_signal:
                current = parent
                continue

            # Check for a submit/subscribe button nearby
            buttons = parent.cssselect('button, input[type="submit"]')
            btn_text = " ".join((b.text_content() or "").lower() for b in buttons)
            has_btn = any(
                kw in btn_text
                for kw in ["subscribe", "sign up", "submit", "join", "get"]
            )
            if has_btn:
                results.append(ConsentCheckbox(
                    checkbox_type="phone_field_subscribe",
                    found=True,
                    pre_ticked=None,  # Not a checkbox
                    label_text=_clean_text(parent.text_content())[:200],
                    element_id=phone_input.get("id"),
                    detection_method="phone_field",
                ))
                break
            current = parent

    return results


# ---------------------------------------------------------------------------
# Layer 4: Custom Consent Elements (toggles, ARIA)
# ---------------------------------------------------------------------------

def _find_custom_consent_elements(tree) -> list[ConsentCheckbox]:
    """Find consent-related toggle switches or ARIA role=checkbox/switch elements."""
    results = []

    selectors = [
        '[role="switch"]',
        '[role="checkbox"]',
    ]

    seen_ids = set()
    for selector in selectors:
        elements = tree.cssselect(selector)
        for el in elements:
            el_id = el.get("id", "")

            # Skip if it's a regular input checkbox (already handled)
            if el.tag == "input" and el.get("type") == "checkbox":
                continue

            # Skip duplicates
            if el_id and el_id in seen_ids:
                continue
            seen_ids.add(el_id)

            text = _find_associated_text(tree, el)
            cb_type = _classify_consent_text(text)
            if not cb_type:
                continue

            is_checked = (
                (el.get("aria-checked", "false").lower() == "true")
                or ("checked" in (el.get("class", "")).lower())
                or ("active" in (el.get("class", "")).lower())
            )

            results.append(ConsentCheckbox(
                checkbox_type=cb_type,
                found=True,
                pre_ticked=is_checked,
                label_text=text,
                element_id=el_id or None,
                detection_method="custom_element",
            ))

    return results


# ---------------------------------------------------------------------------
# Text Association & Classification Helpers
# ---------------------------------------------------------------------------

def _find_associated_text(tree, el) -> Optional[str]:
    """Find text associated with an element using multiple strategies.

    Strategy 1: label[for="element_id"]
    Strategy 2: Parent <label> wrapping the element
    Strategy 3: Walk up parent tree (5 levels), look for consent-related text
    Strategy 4: aria-label or aria-describedby
    """
    el_id = el.get("id", "")

    # Strategy 1: label[for]
    if el_id:
        labels = tree.cssselect(f'label[for="{el_id}"]')
        if labels:
            text = _clean_text(labels[0].text_content())
            if text:
                return text

    # Strategy 2: parent label
    parent = el.getparent()
    if parent is not None and parent.tag == "label":
        text = _clean_text(parent.text_content())
        if text:
            return text

    # Strategy 3: walk up parent tree (5 levels)
    current = el
    for _ in range(5):
        parent = current.getparent()
        if parent is None:
            break

        raw_text = parent.text_content() or ""
        text = _clean_text(raw_text)

        # Only accept if it's reasonably sized and consent-related
        if (
            text
            and 10 < len(text) < 500
            and any(kw in text.lower() for kw in CONSENT_KEYWORDS)
        ):
            return text

        current = parent

    # Strategy 4: ARIA attributes
    aria_label = el.get("aria-label", "")
    if aria_label:
        return _clean_text(aria_label)

    aria_desc_id = el.get("aria-describedby", "")
    if aria_desc_id:
        desc_els = tree.cssselect(f'#{aria_desc_id}')
        if desc_els:
            return _clean_text(desc_els[0].text_content())

    return None


def _classify_consent_text(text: Optional[str]) -> Optional[str]:
    """Classify text as email, sms, other consent, or None (not consent).

    Returns None if text doesn't appear consent-related.
    """
    if not text:
        return None

    text_lower = text.lower()

    # Must contain at least one consent signal
    is_consent = any(kw in text_lower for kw in CONSENT_KEYWORDS)
    if not is_consent:
        return None

    # Filter out false positives — skip age verification, gift notes, terms, etc.
    false_positive_signals = [
        "age verification", "i am 21", "i am over", "years old",
        "gift note", "gift message", "save this information",
        "remember me", "keep me signed", "billing address",
        "same as shipping",
    ]
    if any(fp in text_lower for fp in false_positive_signals):
        return None

    # Classify type
    has_sms = any(kw in text_lower for kw in SMS_KEYWORDS)
    has_email = any(kw in text_lower for kw in EMAIL_KEYWORDS)

    if has_sms and not has_email:
        return "sms"
    elif has_email and not has_sms:
        return "email"
    elif has_sms and has_email:
        # Both signals — determine primary from position
        first_sms = min((text_lower.find(kw) for kw in SMS_KEYWORDS if kw in text_lower), default=999)
        first_email = min((text_lower.find(kw) for kw in EMAIL_KEYWORDS if kw in text_lower), default=999)
        return "sms" if first_sms < first_email else "email"
    else:
        return "other"


def _clean_text(text: str) -> str:
    """Collapse whitespace and strip a text string."""
    if not text:
        return ""
    return " ".join(text.split()).strip()
