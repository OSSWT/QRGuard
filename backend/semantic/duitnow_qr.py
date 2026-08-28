"""Strict recognition of Malaysian DuitNow EMV QR payloads.

This mirrors the Flutter-side parser so the backend and UI agree that a valid
DuitNow code is a payment payload, not plain text.  Format validity is not proof
that the recipient is trustworthy; Structural evidence and the user's payment
app confirmation remain separate safeguards.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

MALAYSIA_AID = "A0000006150001"


@dataclass(frozen=True)
class DuitNowInfo:
    recipient_name: str
    merchant_category_code: str
    amount: Optional[str]

    @property
    def is_person_to_person(self) -> bool:
        return self.merchant_category_code == "0000"


def parse_duitnow(payload: str) -> Optional[DuitNowInfo]:
    """Return verified display metadata, or ``None`` for any invalid payload."""
    if not isinstance(payload, str) or len(payload) < 20 or not _valid_crc(payload):
        return None
    root = _parse_tlv(payload)
    if root is None or root.get("00") != "02" or root.get("53") != "458":
        return None
    if root.get("58") != "MY":
        return None

    has_duitnow_aid = False
    for tag in range(26, 52):
        template = root.get(f"{tag:02d}")
        if template is None:
            continue
        account = _parse_tlv(template)
        if account is not None and account.get("00") == MALAYSIA_AID:
            has_duitnow_aid = True
            break
    if not has_duitnow_aid:
        return None

    category = root.get("52", "")
    recipient = root.get("59", "").strip()
    amount = root.get("54")
    if len(category) != 4 or not category.isdigit() or not recipient:
        return None
    if amount is not None:
        whole, dot, fraction = amount.partition(".")
        if not whole.isdigit() or len(whole) > 10:
            return None
        if dot and (not fraction.isdigit() or not 1 <= len(fraction) <= 2):
            return None
    return DuitNowInfo(recipient, category, amount)


def _parse_tlv(value: str) -> Optional[dict[str, str]]:
    fields: dict[str, str] = {}
    offset = 0
    while offset < len(value):
        if offset + 4 > len(value):
            return None
        tag = value[offset : offset + 2]
        length_text = value[offset + 2 : offset + 4]
        if not length_text.isdigit():
            return None
        length = int(length_text)
        start = offset + 4
        end = start + length
        if end > len(value):
            return None
        fields[tag] = value[start:end]
        offset = end
    return fields


def _valid_crc(payload: str) -> bool:
    if len(payload) < 8 or payload[-8:-4] != "6304":
        return False
    try:
        expected = int(payload[-4:], 16)
    except ValueError:
        return False
    crc = 0xFFFF
    for byte in payload[:-4].encode("utf-8"):
        crc ^= byte << 8
        for _ in range(8):
            crc = (
                ((crc << 1) ^ 0x1021) & 0xFFFF if crc & 0x8000 else (crc << 1) & 0xFFFF
            )
    return crc == expected
