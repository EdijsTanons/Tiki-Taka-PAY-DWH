"""HTML entity decoding and document type normalization."""

from __future__ import annotations

import html
import re
import xml.etree.ElementTree as ET
from typing import Any


def decode_text(s: str) -> str:
    """Unescape HTML entities and normalize whitespace."""
    return re.sub(r"\s+", " ", html.unescape(s)).strip()


_DOC_TYPE_MAP: dict[str, str] = {
    "darījums": "sale",
    "darijums": "sale",
    "z pārskats": "z_report",
    "z parskats": "z_report",
    "x pārskats": "x_report",
    "x parskats": "x_report",
    "inicializācija": "initialization",
    "inicializacija": "initialization",
    "nefiskāls": "non_fiscal",
    "nefiskals": "non_fiscal",
    "nauda": "cash_drawer",
}


def normalize_doc_type(raw: str) -> str:
    """Map Latvian document type to English code."""
    key = decode_text(raw).lower()
    return _DOC_TYPE_MAP.get(key, "unknown")


def parse_doc_xml(xml_str: str) -> dict[str, Any]:
    """Extract top-level attributes from the raw <doc> XML string."""
    result: dict[str, Any] = {}
    if not xml_str:
        return result
    try:
        root = ET.fromstring(xml_str)
        result = dict(root.attrib)
    except ET.ParseError:
        pass
    return result


def extract_dok_veids(xml_str: str) -> str | None:
    attrs = parse_doc_xml(xml_str)
    raw = attrs.get("dok_veids") or attrs.get("dokVeids")
    if raw is None:
        return None
    return decode_text(raw)


# ── Z report ceka_saturs parsers ─────────────────────────────────────────────
# Latvian diacritics are often garbled in stored XML, so patterns use `.{0,N}`
# wildcards where the garbled characters appear.

# First "KOP." line with "|  amount" → trading total
_Z_TOTAL_RE = re.compile(r"KOP.{0,3}\s*\|\s*([\d]+\.[\d]{2})")
# "Anulātie darījumi  |  N|  amount"
_Z_CANCELLED_RE = re.compile(r"Anul[^\|]+\|\s*(\d+)\|\s*([\d.]+)")
# "Atmaksas darījumi  |  N|  amount"
_Z_REFUND_RE = re.compile(r"Atmaks[^\|]+\|\s*(\d+)\|\s*(-?[\d.]+)")
# "Ielikts KOP.  amount EUR"
_Z_CASH_IN_RE = re.compile(r"Ielikts\s+KOP.{0,3}\s+([\d]+\.[\d]{2})")
# "Izņemts KOP.  amount EUR"
_Z_CASH_OUT_RE = re.compile(r"Iz.{0,3}mts\s+KOP.{0,3}\s+([\d]+\.[\d]{2})")
# VAT rows: "A  | 21.0 |  237.65 |  49.95"
_Z_VAT_ROW_RE = re.compile(
    r"^\s*([A-E])\s*\|\s*([\d.]+|-)\s*\|\s*([\d.]+)\s*\|\s*([\d.]+)",
    re.MULTILINE,
)


def extract_z_report_data(raw_xml: str) -> dict[str, Any]:
    """Parse ceka_saturs from a Z report XML into structured data.

    All fields are None / empty-list on parse failure — never raises.
    """
    result: dict[str, Any] = {
        "total": None,
        "cancelled_count": None,
        "cancelled_amount": None,
        "refund_count": None,
        "cash_in": None,
        "cash_out": None,
        "vat_rows": [],
    }
    if not raw_xml:
        return result
    try:
        root = ET.fromstring(raw_xml)
        ceka = root.find("ceka_saturs")
        if ceka is None or not ceka.text:
            return result
        text = html.unescape(ceka.text)

        m = _Z_TOTAL_RE.search(text)
        if m:
            result["total"] = float(m.group(1))

        m = _Z_CANCELLED_RE.search(text)
        if m:
            result["cancelled_count"] = int(m.group(1))
            result["cancelled_amount"] = float(m.group(2))

        m = _Z_REFUND_RE.search(text)
        if m:
            result["refund_count"] = int(m.group(1))

        m = _Z_CASH_IN_RE.search(text)
        if m:
            result["cash_in"] = float(m.group(1))

        m = _Z_CASH_OUT_RE.search(text)
        if m:
            result["cash_out"] = float(m.group(1))

        for vm in _Z_VAT_ROW_RE.finditer(text):
            code, rate_str, taxable, vat = vm.groups()
            result["vat_rows"].append({
                "code": code,
                "rate": None if rate_str == "-" else float(rate_str),
                "taxable": float(taxable),
                "vat": float(vat),
            })
    except Exception:
        pass
    return result
