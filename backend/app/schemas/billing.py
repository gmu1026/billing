from datetime import datetime

from pydantic import BaseModel


class BillingDataCreate(BaseModel):
    vendor: str
    billing_month: str  # YYYY-MM
    service_name: str | None = None
    account_id: str | None = None
    amount: float
    currency: str = "KRW"
    raw_data: str | None = None


class BillingDataResponse(BillingDataCreate):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True


class BillingUploadResponse(BaseModel):
    success: bool
    total_records: int
    inserted_records: int
    errors: list[str] = []


class PresetGroupCreate(BaseModel):
    name: str
    description: str | None = None
    vendor: str | None = None


class PresetGroupResponse(PresetGroupCreate):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True


class PresetItemCreate(BaseModel):
    group_id: int
    day_rule: int = 1
    text_template: str
    hkont: str | None = None
    kostl: str | None = None
    fixed_amount: float | None = None
    contract_id: str | None = None
    holiday_rule: str = "exact"


class PresetItemResponse(PresetItemCreate):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True
