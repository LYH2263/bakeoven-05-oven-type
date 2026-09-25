from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

OvenType = Literal["tray", "stone"]


class ProductOut(BaseModel):
    id: int
    name: str
    ferment_min: int
    bake_min: int
    oven_type: OvenType
    model_config = {"from_attributes": True}


class ProductUpdate(BaseModel):
    oven_type: OvenType


class OvenOut(BaseModel):
    id: int
    label: str
    capacity_note: str
    oven_type: OvenType
    model_config = {"from_attributes": True}


class OvenUpdate(BaseModel):
    oven_type: OvenType


class BatchOut(BaseModel):
    id: int
    product_id: int
    oven_id: int
    code: str
    start_min: int
    status: str
    product_name: str | None = None
    product_oven_type: OvenType | None = None
    oven_label: str | None = None
    oven_oven_type: OvenType | None = None
    type_mismatch: bool = False
    ferment_end: int | None = None
    bake_end: int | None = None
    model_config = {"from_attributes": True}


class BatchCreate(BaseModel):
    product_id: int
    oven_id: int
    start_min: int = Field(ge=0, le=24 * 60 - 1)
    code: str | None = None


class GanttBlock(BaseModel):
    batch_id: int
    code: str
    oven_id: int
    oven_label: str
    oven_type: OvenType
    phase: str
    start_min: int
    end_min: int


class ConflictOut(BaseModel):
    id: int
    batch_code: str
    oven_id: int
    detail: str
    created_at: datetime
    model_config = {"from_attributes": True}


class WindowOut(BaseModel):
    oven_id: int
    oven_label: str
    oven_type: OvenType
    start_min: int
    end_min: int
    duration_min: int
