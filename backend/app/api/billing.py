import csv
import io
import json
from typing import Literal

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.billing import BillingData
from app.schemas.billing import BillingDataResponse, BillingUploadResponse

router = APIRouter(prefix="/api/billing", tags=["billing"])


@router.post("/upload/{vendor}", response_model=BillingUploadResponse)
async def upload_billing_data(
    vendor: str,
    file: UploadFile = File(...),
    file_type: Literal["csv", "json", "jsonl"] = Query("csv"),
    db: Session = Depends(get_db),
):
    """빌링 데이터 파일 업로드 (CSV, JSON, JSONL 지원)"""
    content = await file.read()
    text = content.decode("utf-8-sig")  # BOM 처리

    records = []
    errors = []

    try:
        if file_type == "csv":
            records = _parse_csv(text)
        elif file_type == "json":
            records = _parse_json(text)
        elif file_type == "jsonl":
            records = _parse_jsonl(text)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"파일 파싱 오류: {str(e)}")

    inserted = 0
    for i, record in enumerate(records):
        try:
            billing = BillingData(
                vendor=vendor,
                billing_month=record.get("billing_month", ""),
                service_name=record.get("service_name"),
                account_id=record.get("account_id"),
                amount=float(record.get("amount", 0)),
                currency=record.get("currency", "KRW"),
                raw_data=json.dumps(record, ensure_ascii=False),
            )
            db.add(billing)
            inserted += 1
        except Exception as e:
            errors.append(f"Row {i + 1}: {str(e)}")

    db.commit()

    return BillingUploadResponse(
        success=len(errors) == 0,
        total_records=len(records),
        inserted_records=inserted,
        errors=errors,
    )


@router.get("/", response_model=list[BillingDataResponse])
def get_billing_data(
    vendor: str | None = Query(None),
    billing_month: str | None = Query(None),
    db: Session = Depends(get_db),
):
    """빌링 데이터 조회"""
    query = db.query(BillingData)

    if vendor:
        query = query.filter(BillingData.vendor == vendor)
    if billing_month:
        query = query.filter(BillingData.billing_month == billing_month)

    return query.order_by(BillingData.created_at.desc()).all()


@router.get("/summary")
def get_billing_summary(
    vendor: str | None = Query(None),
    billing_month: str | None = Query(None),
    db: Session = Depends(get_db),
):
    """빌링 데이터 요약 (금액 합계 등)"""
    query = db.query(BillingData)

    if vendor:
        query = query.filter(BillingData.vendor == vendor)
    if billing_month:
        query = query.filter(BillingData.billing_month == billing_month)

    data = query.all()
    total_amount = sum(float(d.amount) for d in data)

    return {
        "vendor": vendor,
        "billing_month": billing_month,
        "record_count": len(data),
        "total_amount": total_amount,
    }


def _parse_csv(text: str) -> list[dict]:
    reader = csv.DictReader(io.StringIO(text))
    return list(reader)


def _parse_json(text: str) -> list[dict]:
    data = json.loads(text)
    if isinstance(data, list):
        return data
    return [data]


def _parse_jsonl(text: str) -> list[dict]:
    records = []
    for line in text.strip().split("\n"):
        if line.strip():
            records.append(json.loads(line))
    return records
