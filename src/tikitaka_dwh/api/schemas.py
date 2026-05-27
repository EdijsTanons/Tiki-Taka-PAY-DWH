"""Pydantic models for Tikitaka REST API responses."""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator


class ApiPayment(BaseModel):
    model_config = {"extra": "allow"}

    payment_type: Optional[str] = None
    payment_method: Optional[str] = None
    amount: Optional[float] = None
    card_type: Optional[str] = None
    card_pan: Optional[str] = None
    card_tid: Optional[str] = None
    card_reference_number: Optional[str] = None
    gift_card_number: Optional[str] = None


class ApiSoldProduct(BaseModel):
    model_config = {"extra": "allow"}

    product_code: Optional[str] = None
    product_name: Optional[str] = None
    department: Optional[str] = None
    quantity: Optional[float] = None
    unit: Optional[str] = None
    price: Optional[float] = None
    product_sum: Optional[float] = None
    discount: Optional[float] = None
    product_discount: Optional[float] = None
    discount_type: Optional[str] = None
    excise: Optional[float] = None
    sum_without_vat: Optional[float] = None
    vat_sum: Optional[float] = None
    vat_rate: Optional[float] = None
    vat_title: Optional[str] = None
    total_sum: Optional[float] = None
    row_type: Optional[str] = None
    pos_code: Optional[str] = None


class ApiDocument(BaseModel):
    model_config = {"extra": "allow"}

    id: int
    doc_uid: Optional[int] = None
    doc_num: Optional[int] = None
    doc_datetime: Optional[str] = None
    doc_sha: Optional[str] = None
    dok_operation: Optional[str] = None
    store_number: Optional[str] = None
    title: Optional[str] = None
    device_serial_number: Optional[str] = None
    id_device: Optional[int] = None
    non_fiscal: Optional[bool] = None
    id_device_fiscof: Optional[Any] = None
    doc_sum: Optional[float] = None
    operator_id: Optional[str] = None
    operator_name: Optional[str] = None
    payments: list[ApiPayment] = Field(default_factory=list)
    payment_type: Optional[str] = None
    payment_method: Optional[str] = None
    currency: Optional[str] = None
    card_type: Optional[str] = None
    card_pan: Optional[str] = None
    card_tid: Optional[str] = None
    card_reference_number: Optional[str] = None
    gift_card_number: Optional[str] = None
    client_reg_number: Optional[str] = None
    client_title: Optional[str] = None
    customer_card_name: Optional[str] = None
    customer_card_number: Optional[str] = None
    sold_products: list[ApiSoldProduct] = Field(default_factory=list)
    doc: Optional[str] = None  # raw XML

    @field_validator("payments", "sold_products", mode="before")
    @classmethod
    def _null_to_empty_list(cls, v: Any) -> Any:
        return v if v is not None else []


class ApiListResponse(BaseModel):
    model_config = {"extra": "allow"}

    total: int
    results: list[ApiDocument]
