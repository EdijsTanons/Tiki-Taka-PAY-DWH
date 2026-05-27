"""Tests for api/schemas.py — parse the sample fixture."""

from tikitaka_dwh.api.schemas import ApiListResponse


def test_parse_fixture(sample_response: dict):
    resp = ApiListResponse.model_validate(sample_response)
    assert resp.total == 5
    assert len(resp.results) == 5


def test_sale_doc_has_products(sample_docs: list):
    sale = next(d for d in sample_docs if d["id"] == 1001)
    doc = next(d for d in [ApiListResponse.model_validate({"total": 1, "results": [sale]}).results[0]])
    assert len(doc.sold_products) == 8
    assert len(doc.payments) == 1


def test_z_report_has_no_products(sample_docs: list):
    z = next(d for d in sample_docs if d["id"] == 1002)
    from tikitaka_dwh.api.schemas import ApiDocument
    doc = ApiDocument.model_validate(z)
    assert doc.sold_products == []
