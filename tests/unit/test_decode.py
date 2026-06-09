"""Tests for transform/decode.py."""

import pytest

from tikitaka_dwh.transform.decode import decode_text, extract_dok_veids, normalize_doc_type


def test_decode_z_parskats():
    assert decode_text("Z p&#x101;rskats") == "Z pārskats"


def test_decode_darljums():
    assert decode_text("dar&#x012B;jums") == "darījums"


def test_decode_already_clean():
    assert decode_text("sale") == "sale"


def test_decode_whitespace_normalization():
    assert decode_text("  foo   bar  ") == "foo bar"


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("darījums", "sale"),
        ("dar&#x012B;jums", "sale"),  # entity-encoded
        ("Z pārskats", "z_report"),
        ("Z p&#x101;rskats", "z_report"),
        ("X pārskats", "x_report"),
        ("X p&#x101;rskats", "x_report"),
        ("inicializācija", "initialization"),
        ("nefiskāls", "non_fiscal"),
        ("nauda", "cash_drawer"),
        ("something_unknown", "unknown"),
    ],
)
def test_normalize_doc_type(raw: str, expected: str):
    assert normalize_doc_type(raw) == expected


def test_extract_dok_veids_encoded():
    xml = '<dok dok_veids="Z p&#x101;rskats" />'
    result = extract_dok_veids(xml)
    assert result == "Z pārskats"


def test_extract_dok_veids_darljums():
    xml = '<dok dok_veids="dar&#x012B;jums" />'
    result = extract_dok_veids(xml)
    assert result == "darījums"


def test_extract_dok_veids_empty():
    assert extract_dok_veids("") is None


def test_extract_dok_veids_malformed_xml():
    assert extract_dok_veids("<broken &") is None
