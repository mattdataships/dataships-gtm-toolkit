from __future__ import annotations

"""Data models for checkout consent audit."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional


@dataclass
class ConsentCheckbox:
    """A single consent element found on the checkout page."""
    checkbox_type: str          # "email", "sms", "other", "phone_field_subscribe"
    found: bool
    pre_ticked: Optional[bool]  # None if not a checkbox (e.g., phone field)
    label_text: Optional[str]   # Actual text captured
    element_id: Optional[str]   # The HTML id attribute
    detection_method: str       # "standard_id", "checkbox_scan", "phone_field", "custom_element"


@dataclass
class AuditResult:
    """Complete audit result for a single domain."""
    domain: str
    merchant_name: str = ""
    country_code: str = ""
    checkout_url: Optional[str] = None
    email_checkbox: Optional[ConsentCheckbox] = None
    sms_checkbox: Optional[ConsentCheckbox] = None
    other_consent_elements: list = field(default_factory=list)
    confidence_score: float = 0.0
    tier_used: int = 3
    has_checkout_blocks: bool = False
    has_dataships: bool = False
    notes: str = ""
    error: Optional[str] = None
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_row(self) -> dict:
        """Convert to a flat dict for CSV output."""
        import json

        email = self.email_checkbox
        sms = self.sms_checkbox

        other_json = ""
        if self.other_consent_elements:
            other_json = json.dumps([
                {
                    "type": c.checkbox_type,
                    "preticked": c.pre_ticked,
                    "text": c.label_text,
                    "method": c.detection_method,
                }
                for c in self.other_consent_elements
            ])

        return {
            "domain": self.domain,
            "merchant_name": self.merchant_name,
            "country_code": self.country_code,
            "checkout_url": self.checkout_url or "",
            "email_found": email.found if email else False,
            "email_preticked": email.pre_ticked if email else "",
            "email_language": email.label_text if email else "",
            "email_element_id": email.element_id if email else "",
            "email_detection_method": email.detection_method if email else "",
            "sms_found": sms.found if sms else False,
            "sms_preticked": sms.pre_ticked if sms else "",
            "sms_language": sms.label_text if sms else "",
            "sms_element_id": sms.element_id if sms else "",
            "sms_detection_method": sms.detection_method if sms else "",
            "other_consent_elements": other_json,
            "other_consent_count": len(self.other_consent_elements),
            "confidence_score": self.confidence_score,
            "tier_used": self.tier_used,
            "has_checkout_blocks": self.has_checkout_blocks,
            "has_dataships": self.has_dataships,
            "notes": self.notes,
            "error": self.error or "",
            "timestamp": self.timestamp,
        }
