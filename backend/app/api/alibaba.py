import csv
import io
from typing import Literal

from fastapi import APIRouter, Depends, File, Query, UploadFile
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.alibaba import AlibabaBilling
from app.utils import clean_string, decode_csv_content, parse_float

router = APIRouter(prefix="/api/alibaba", tags=["alibaba"])


@router.post("/upload/{billing_type}")
async def upload_alibaba_billing(
    billing_type: Literal["enduser", "reseller"],
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """
    알리바바 빌링 데이터 업로드

    - billing_type: enduser (매출) 또는 reseller (매입)
    - enduser: Pretax Cost 사용
    - reseller: Original Cost - Discount - SPN Deducted Price 사용 (쿠폰 이슈 대응)
    """
    content = await file.read()
    text = decode_csv_content(content)

    reader = csv.DictReader(io.StringIO(text))

    inserted = 0
    errors = []

    for i, row in enumerate(reader):
        try:
            # 금액 파싱
            original_cost = parse_float(row.get("Original Cost", "0"))
            spn_deducted = parse_float(row.get("SPN Deducted Price", "0"))
            discount = parse_float(row.get("Discount", "0"))
            coupon_deduct = parse_float(row.get("Coupon Deduct", "0"))
            pretax_cost = parse_float(row.get("Pretax Cost(Before Round Down Discount)", "0"))

            # 계산된 금액 (전표용) - 원본 그대로 저장
            if billing_type == "reseller":
                # 매입: Original Cost - Discount - SPN Deducted (쿠폰 이슈로 인해)
                calculated = original_cost - discount - spn_deducted
            else:
                # 매출: Pretax Cost 사용
                calculated = pretax_cost

            billing = AlibabaBilling(
                billing_type=billing_type,
                billing_cycle=clean_string(row.get("Billing Cycle")),
                consume_time=clean_string(row.get("Consume Time")),
                # 사용자 정보
                user_id=clean_string(row.get("User ID", "")),
                user_name=clean_string(row.get("User Name")),
                user_account=clean_string(row.get("User Account")),
                # Reseller: Linked User
                linked_user_id=clean_string(row.get("Linked User ID")),
                linked_user_name=clean_string(row.get("Linked User Name")),
                linked_user_account=clean_string(row.get("Linked User Account")),
                # 빌링 분류
                bill_source=clean_string(row.get("Bill Source")),
                order_type=clean_string(row.get("Order Type")),
                charge_type=clean_string(row.get("Charge Type")),
                billing_type_detail=clean_string(row.get("Billing Type")),
                # 상품 정보
                product_code=clean_string(row.get("Product Code")),
                product_name=clean_string(row.get("Product Name")),
                instance_id=clean_string(row.get("Instance ID")),
                instance_name=clean_string(row.get("Instance Name")),
                instance_config=clean_string(row.get("Instance Configuration")),
                instance_tag=clean_string(row.get("Instance Tag")),
                region=clean_string(row.get("Region")),
                # 금액
                original_cost=original_cost,
                spn_deducted_price=spn_deducted,
                spn_id=clean_string(row.get("SPN ID")),
                discount=discount,
                discount_percent=clean_string(row.get("Discount(%)")),
                coupon_deduct=coupon_deduct,
                pretax_cost=pretax_cost,
                currency=clean_string(row.get("Currency")) or "USD",
                calculated_amount=calculated,
            )
            db.add(billing)
            inserted += 1

        except Exception as e:
            errors.append(f"Row {i + 2}: {str(e)}")

    db.commit()

    return {
        "success": len(errors) == 0,
        "billing_type": billing_type,
        "total_rows": inserted + len(errors),
        "inserted": inserted,
        "errors": errors[:20],  # 처음 20개만 반환
    }


@router.get("/")
def get_alibaba_billing(
    billing_type: Literal["enduser", "reseller"] | None = Query(None),
    billing_cycle: str | None = Query(None),
    user_id: str | None = Query(None),
    limit: int = Query(100, le=1000),
    offset: int = Query(0),
    db: Session = Depends(get_db),
):
    """알리바바 빌링 데이터 조회"""
    query = db.query(AlibabaBilling)

    if billing_type:
        query = query.filter(AlibabaBilling.billing_type == billing_type)
    if billing_cycle:
        query = query.filter(AlibabaBilling.billing_cycle == billing_cycle)
    if user_id:
        query = query.filter(
            (AlibabaBilling.user_id == user_id) | (AlibabaBilling.linked_user_id == user_id)
        )

    total = query.count()
    data = query.order_by(AlibabaBilling.id).offset(offset).limit(limit).all()

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "data": [
            {
                "id": d.id,
                "billing_type": d.billing_type,
                "billing_cycle": d.billing_cycle,
                "user_id": d.user_id,
                "user_name": d.user_name,
                "linked_user_id": d.linked_user_id,
                "linked_user_name": d.linked_user_name,
                "product_code": d.product_code,
                "product_name": d.product_name,
                "region": d.region,
                "original_cost": d.original_cost,
                "discount": d.discount,
                "spn_deducted_price": d.spn_deducted_price,
                "pretax_cost": d.pretax_cost,
                "calculated_amount": d.calculated_amount,
                "currency": d.currency,
            }
            for d in data
        ],
    }


@router.get("/summary")
def get_alibaba_summary(
    billing_type: Literal["enduser", "reseller"] | None = Query(None),
    billing_cycle: str | None = Query(None),
    db: Session = Depends(get_db),
):
    """
    알리바바 빌링 요약 (UID별 합계)

    - enduser: linked_user_id 기준으로 그룹핑 (실제 사용 고객)
    - reseller: user_id 기준으로 그룹핑
    """
    query = db.query(AlibabaBilling)

    if billing_type:
        query = query.filter(AlibabaBilling.billing_type == billing_type)
    if billing_cycle:
        query = query.filter(AlibabaBilling.billing_cycle == billing_cycle)

    # UID별 합계
    if billing_type == "reseller":
        # Reseller: linked_user_id 기준 (실제 고객)
        summary = db.query(
            AlibabaBilling.linked_user_id.label("uid"),
            AlibabaBilling.linked_user_name.label("user_name"),
            func.sum(AlibabaBilling.calculated_amount).label("total_amount"),
            func.count(AlibabaBilling.id).label("record_count"),
        ).filter(AlibabaBilling.billing_type == "reseller")
        if billing_cycle:
            summary = summary.filter(AlibabaBilling.billing_cycle == billing_cycle)
        summary = summary.group_by(
            AlibabaBilling.linked_user_id, AlibabaBilling.linked_user_name
        ).all()
    else:
        # Enduser: user_id 기준
        summary = db.query(
            AlibabaBilling.user_id.label("uid"),
            AlibabaBilling.user_name.label("user_name"),
            func.sum(AlibabaBilling.calculated_amount).label("total_amount"),
            func.count(AlibabaBilling.id).label("record_count"),
        ).filter(AlibabaBilling.billing_type == "enduser")
        if billing_cycle:
            summary = summary.filter(AlibabaBilling.billing_cycle == billing_cycle)
        summary = summary.group_by(AlibabaBilling.user_id, AlibabaBilling.user_name).all()

    total_amount = sum(s.total_amount or 0 for s in summary)

    return {
        "billing_type": billing_type or "all",
        "billing_cycle": billing_cycle,
        "total_amount": round(total_amount, 2),
        "user_count": len(summary),
        "by_user": [
            {
                "uid": s.uid,
                "user_name": s.user_name,
                "total_amount": round(s.total_amount or 0, 2),
                "record_count": s.record_count,
            }
            for s in sorted(summary, key=lambda x: x.total_amount or 0, reverse=True)
        ],
    }


@router.delete("/")
def delete_alibaba_billing(
    billing_type: Literal["enduser", "reseller"] | None = Query(None),
    billing_cycle: str | None = Query(None),
    db: Session = Depends(get_db),
):
    """알리바바 빌링 데이터 삭제 (재업로드 전 사용)"""
    query = db.query(AlibabaBilling)

    if billing_type:
        query = query.filter(AlibabaBilling.billing_type == billing_type)
    if billing_cycle:
        query = query.filter(AlibabaBilling.billing_cycle == billing_cycle)

    count = query.count()
    query.delete()
    db.commit()

    return {"deleted": count, "billing_type": billing_type, "billing_cycle": billing_cycle}
