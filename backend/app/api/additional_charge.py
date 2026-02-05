"""
추가 비용 관리 API (RAW 빌링 외 추가 비용)
"""

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models.billing_profile import AdditionalCharge, ChargeType, RecurrenceType
from app.models.hb import HBContract

router = APIRouter(prefix="/api/additional-charges", tags=["additional-charges"])


# ===== Request/Response 모델 =====


class AdditionalChargeCreate(BaseModel):
    contract_seq: int
    name: str
    description: str | None = None
    charge_type: str = ChargeType.OTHER.value
    amount: float  # 음수 = 차감
    currency: str = "USD"
    recurrence_type: str = RecurrenceType.ONE_TIME.value
    start_date: date | None = None
    end_date: date | None = None
    applies_to_sales: bool = True
    applies_to_purchase: bool = False


class AdditionalChargeUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    charge_type: str | None = None
    amount: float | None = None
    currency: str | None = None
    recurrence_type: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    applies_to_sales: bool | None = None
    applies_to_purchase: bool | None = None
    is_active: bool | None = None


# ===== API 엔드포인트 =====


@router.post("/")
def create_additional_charge(data: AdditionalChargeCreate, db: Session = Depends(get_db)):
    """추가 비용 생성"""
    # 계약 존재 확인
    contract = db.query(HBContract).filter(HBContract.seq == data.contract_seq).first()
    if not contract:
        raise HTTPException(status_code=404, detail="Contract not found")

    charge = AdditionalCharge(**data.model_dump())
    db.add(charge)
    db.commit()
    db.refresh(charge)

    return {
        "success": True,
        "id": charge.id,
        "message": f"추가 비용 '{charge.name}'이(가) 생성되었습니다.",
    }


@router.get("/")
def get_additional_charges(
    contract_seq: int | None = Query(None),
    charge_type: str | None = Query(None),
    is_active: bool | None = Query(None),
    limit: int = Query(100, le=500),
    offset: int = Query(0),
    db: Session = Depends(get_db),
):
    """추가 비용 목록 조회"""
    query = db.query(AdditionalCharge).options(joinedload(AdditionalCharge.contract))

    if contract_seq is not None:
        query = query.filter(AdditionalCharge.contract_seq == contract_seq)
    if charge_type is not None:
        query = query.filter(AdditionalCharge.charge_type == charge_type)
    if is_active is not None:
        query = query.filter(AdditionalCharge.is_active == is_active)

    total = query.count()
    charges = query.order_by(AdditionalCharge.created_at.desc()).offset(offset).limit(limit).all()

    return {
        "total": total,
        "data": [
            {
                "id": c.id,
                "contract_seq": c.contract_seq,
                "contract_name": c.contract.name if c.contract else None,
                "company_name": c.contract.company.name if c.contract and c.contract.company else None,
                "name": c.name,
                "description": c.description,
                "charge_type": c.charge_type,
                "amount": c.amount,
                "currency": c.currency,
                "recurrence_type": c.recurrence_type,
                "start_date": str(c.start_date) if c.start_date else None,
                "end_date": str(c.end_date) if c.end_date else None,
                "applies_to_sales": c.applies_to_sales,
                "applies_to_purchase": c.applies_to_purchase,
                "is_active": c.is_active,
                "created_at": c.created_at.isoformat() if c.created_at else None,
            }
            for c in charges
        ],
    }


@router.get("/{charge_id}")
def get_additional_charge(charge_id: int, db: Session = Depends(get_db)):
    """추가 비용 상세 조회"""
    charge = (
        db.query(AdditionalCharge)
        .options(joinedload(AdditionalCharge.contract))
        .filter(AdditionalCharge.id == charge_id)
        .first()
    )
    if not charge:
        raise HTTPException(status_code=404, detail="Additional charge not found")

    return {
        "id": charge.id,
        "contract_seq": charge.contract_seq,
        "contract_name": charge.contract.name if charge.contract else None,
        "company_name": charge.contract.company.name if charge.contract and charge.contract.company else None,
        "name": charge.name,
        "description": charge.description,
        "charge_type": charge.charge_type,
        "amount": charge.amount,
        "currency": charge.currency,
        "recurrence_type": charge.recurrence_type,
        "start_date": str(charge.start_date) if charge.start_date else None,
        "end_date": str(charge.end_date) if charge.end_date else None,
        "applies_to_sales": charge.applies_to_sales,
        "applies_to_purchase": charge.applies_to_purchase,
        "is_active": charge.is_active,
        "created_at": charge.created_at.isoformat() if charge.created_at else None,
        "updated_at": charge.updated_at.isoformat() if charge.updated_at else None,
    }


@router.patch("/{charge_id}")
def update_additional_charge(
    charge_id: int, data: AdditionalChargeUpdate, db: Session = Depends(get_db)
):
    """추가 비용 수정"""
    charge = db.query(AdditionalCharge).filter(AdditionalCharge.id == charge_id).first()
    if not charge:
        raise HTTPException(status_code=404, detail="Additional charge not found")

    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(charge, key, value)

    db.commit()
    return {"success": True, "id": charge_id}


@router.delete("/{charge_id}")
def delete_additional_charge(charge_id: int, db: Session = Depends(get_db)):
    """추가 비용 삭제"""
    charge = db.query(AdditionalCharge).filter(AdditionalCharge.id == charge_id).first()
    if not charge:
        raise HTTPException(status_code=404, detail="Additional charge not found")

    db.delete(charge)
    db.commit()
    return {"success": True, "deleted_id": charge_id}


@router.get("/by-contract/{contract_seq}")
def get_charges_by_contract(
    contract_seq: int,
    include_inactive: bool = Query(False),
    db: Session = Depends(get_db),
):
    """계약별 추가 비용 조회"""
    query = db.query(AdditionalCharge).filter(AdditionalCharge.contract_seq == contract_seq)

    if not include_inactive:
        query = query.filter(AdditionalCharge.is_active == True)

    charges = query.order_by(AdditionalCharge.charge_type, AdditionalCharge.created_at.desc()).all()

    # 유형별 집계
    total_credit = sum(c.amount for c in charges if c.charge_type == ChargeType.CREDIT.value)
    total_fee = sum(
        c.amount
        for c in charges
        if c.charge_type in (ChargeType.SUPPORT_FEE.value, ChargeType.SETUP_FEE.value, ChargeType.OTHER.value)
    )

    return {
        "contract_seq": contract_seq,
        "summary": {
            "total_credit": total_credit,  # 음수
            "total_fee": total_fee,  # 양수
            "net_adjustment": total_credit + total_fee,
        },
        "charges": [
            {
                "id": c.id,
                "name": c.name,
                "charge_type": c.charge_type,
                "amount": c.amount,
                "currency": c.currency,
                "recurrence_type": c.recurrence_type,
                "start_date": str(c.start_date) if c.start_date else None,
                "end_date": str(c.end_date) if c.end_date else None,
                "applies_to_sales": c.applies_to_sales,
                "applies_to_purchase": c.applies_to_purchase,
                "is_active": c.is_active,
            }
            for c in charges
        ],
    }


def get_applicable_charges(
    db: Session,
    contract_seq: int,
    billing_cycle: str,
    slip_type: str,
) -> list[AdditionalCharge]:
    """
    특정 정산월/전표유형에 적용되는 추가 비용 목록 조회

    Args:
        db: DB 세션
        contract_seq: 계약 seq
        billing_cycle: 정산월 (YYYYMM)
        slip_type: 전표 유형 (sales/purchase)

    Returns:
        적용 가능한 AdditionalCharge 목록
    """
    # 정산월을 날짜 범위로 변환
    year = int(billing_cycle[:4])
    month = int(billing_cycle[4:6])
    cycle_start = date(year, month, 1)
    if month == 12:
        cycle_end = date(year + 1, 1, 1)
    else:
        cycle_end = date(year, month + 1, 1)

    query = db.query(AdditionalCharge).filter(
        AdditionalCharge.contract_seq == contract_seq,
        AdditionalCharge.is_active == True,
    )

    # 매출/매입 적용 필터
    if slip_type == "sales":
        query = query.filter(AdditionalCharge.applies_to_sales == True)
    else:  # purchase
        query = query.filter(AdditionalCharge.applies_to_purchase == True)

    charges = query.all()

    # 반복 유형 및 기간 체크하여 필터링
    applicable = []
    for c in charges:
        if c.recurrence_type == RecurrenceType.RECURRING.value:
            # 매월 반복: start_date 이후, end_date 이전인지 체크
            if c.start_date and c.start_date > cycle_start:
                continue
            if c.end_date and c.end_date < cycle_start:
                continue
            applicable.append(c)

        elif c.recurrence_type == RecurrenceType.ONE_TIME.value:
            # 일회성: start_date가 정산월 내인지 체크
            if c.start_date:
                if cycle_start <= c.start_date < cycle_end:
                    applicable.append(c)
            else:
                # start_date 없으면 적용 안함 (수동 확인 필요)
                pass

        elif c.recurrence_type == RecurrenceType.PERIOD.value:
            # 기간 지정: 정산월이 start~end 범위 내인지 체크
            if c.start_date and c.end_date:
                if c.start_date <= cycle_start and cycle_end <= c.end_date:
                    applicable.append(c)
                elif c.start_date <= cycle_start < c.end_date:
                    # 부분 적용 (마지막 달)
                    applicable.append(c)
                elif cycle_start <= c.start_date < cycle_end:
                    # 부분 적용 (첫 달)
                    applicable.append(c)

    return applicable
