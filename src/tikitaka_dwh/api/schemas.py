"""Pydantic models for Tikitaka REST API responses."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, field_validator


class ApiPayment(BaseModel):
    model_config = {"extra": "allow"}

    payment_type: str | None = None
    payment_method: str | None = None
    amount: float | None = None
    card_type: str | None = None
    card_pan: str | None = None
    card_tid: str | None = None
    card_reference_number: str | None = None
    gift_card_number: str | None = None


class ApiSoldProduct(BaseModel):
    model_config = {"extra": "allow"}

    product_code: str | None = None
    product_name: str | None = None
    department: str | None = None
    quantity: float | None = None
    unit: str | None = None
    price: float | None = None
    product_sum: float | None = None
    discount: float | None = None
    product_discount: float | None = None
    discount_type: str | None = None
    excise: float | None = None
    sum_without_vat: float | None = None
    vat_sum: float | None = None
    vat_rate: float | None = None
    vat_title: str | None = None
    total_sum: float | None = None
    row_type: str | None = None
    pos_code: str | None = None


class ApiDocument(BaseModel):
    model_config = {"extra": "allow"}

    id: int
    doc_uid: int | None = None
    doc_num: int | None = None
    doc_datetime: str | None = None
    doc_sha: str | None = None
    dok_operation: str | None = None
    store_number: str | None = None
    title: str | None = None
    device_serial_number: str | None = None
    id_device: int | None = None
    non_fiscal: bool | None = None
    id_device_fiscof: Any | None = None
    doc_sum: float | None = None
    operator_id: str | None = None
    operator_name: str | None = None
    payments: list[ApiPayment] = Field(default_factory=list)
    payment_type: str | None = None
    payment_method: str | None = None
    currency: str | None = None
    card_type: str | None = None
    card_pan: str | None = None
    card_tid: str | None = None
    card_reference_number: str | None = None
    gift_card_number: str | None = None
    client_reg_number: str | None = None
    client_title: str | None = None
    customer_card_name: str | None = None
    customer_card_number: str | None = None
    sold_products: list[ApiSoldProduct] = Field(default_factory=list)
    doc: str | None = None  # raw XML

    @field_validator("payments", "sold_products", mode="before")
    @classmethod
    def _null_to_empty_list(cls, v: Any) -> Any:
        return v if v is not None else []


class ApiListResponse(BaseModel):
    model_config = {"extra": "allow"}

    total: int
    results: list[ApiDocument]
