"""Tests for transform layer — documents, sale_lines, payments."""

from tikitaka_dwh.transform.documents import build_documents
from tikitaka_dwh.transform.sale_lines import build_sale_lines
from tikitaka_dwh.transform.payments import build_payments
from tikitaka_dwh.transform.dimensions import (
    build_dim_store,
    build_dim_pos,
    build_dim_operator,
    build_dim_product,
    build_dim_customer,
)


def test_build_documents_row_count(sample_docs: list):
    df = build_documents(sample_docs)
    assert len(df) == 5


def test_build_documents_required_columns(sample_docs: list):
    df = build_documents(sample_docs)
    for col in ("id", "doc_date", "doc_type", "doc_sum"):
        assert col in df.columns, f"Missing column: {col}"


def test_build_documents_doc_types(sample_docs: list):
    df = build_documents(sample_docs)
    types = set(df["doc_type"].tolist())
    assert "sale" in types
    assert "z_report" in types
    assert "x_report" in types


def test_build_documents_utc_conversion(sample_docs: list):
    df = build_documents(sample_docs)
    # Riga is UTC+2 in March (EET/no DST yet), so 10:30 local -> 08:30 UTC
    sale_row = df[df["id"] == 1001].iloc[0]
    assert sale_row["doc_datetime_utc"].hour == 8
    assert sale_row["doc_datetime_utc"].minute == 30


def test_build_sale_lines_only_sales(sample_docs: list):
    df = build_sale_lines(sample_docs)
    # 3 sale docs: 8 + 3 + 2 = 13 lines
    assert len(df) == 13


def test_build_sale_lines_pan_not_present(sample_docs: list):
    df = build_sale_lines(sample_docs)
    assert "card_pan" not in df.columns


def test_build_payments_masks_pan(sample_docs: list):
    df = build_payments(sample_docs)
    # doc 1003 has a card payment with full PAN
    masked = df[df["doc_id"] == 1003]["card_pan_masked"].iloc[0]
    assert masked is not None
    assert masked.endswith("1234")
    assert "111111111" not in str(masked)


def test_build_payments_split_tender(sample_docs: list):
    df = build_payments(sample_docs)
    pmts_1005 = df[df["doc_id"] == 1005]
    assert len(pmts_1005) == 2


def test_dim_store_unique_keys(sample_docs: list):
    df = build_dim_store(sample_docs)
    assert df["store_number"].nunique() == len(df)


def test_dim_pos_unique_keys(sample_docs: list):
    df = build_dim_pos(sample_docs)
    assert df["pos_id"].nunique() == len(df)


def test_dim_operator_unique_keys(sample_docs: list):
    df = build_dim_operator(sample_docs)
    assert df["operator_id"].nunique() == len(df)


def test_dim_product_unique_keys(sample_docs: list):
    df = build_dim_product(sample_docs)
    assert df["product_code"].nunique() == len(df)


def test_dim_customer_kinds(sample_docs: list):
    df = build_dim_customer(sample_docs)
    kinds = set(df["customer_kind"].tolist())
    assert "loyalty" in kinds
    assert "b2b" in kinds
