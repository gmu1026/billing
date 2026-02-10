"""
회사별 청구 설정 및 예치금 관리 API
"""

from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.billing_profile import CompanyBillingProfile, Deposit, DepositUsage, PaymentType
from app.models.hb import HBCompany

router = APIRouter(prefix="/api/billing-profile", tags=["billing-profile"])


def round_decimal(value: float, places: int = 2) -> float:
    """소수점 정확한 반올림 (ROUND_HALF_UP)"""
    d = Decimal(str(value))
    return float(d.quantize(Decimal(10) ** -places, rounding=ROUND_HALF_UP))


# ===== Pydantic Models =====


class BillingProfileCreate(BaseModel):
    company_seq: int
    vendor: str
    payment_type: str = PaymentType.TAX_INVOICE.value
    has_sales_agreement: bool = False
    has_purchase_agreement: bool = False
    currency: str = "KRW"
    hkont_sales: str | None = None
    hkont_purchase: str | None = None
    ar_account: str | None = None
    ap_account: str | None = None
    note: str | None = None


class BillingProfileUpdate(BaseModel):
    payment_type: str | None = None
    has_sales_agreement: bool | None = None
    has_purchase_agreement: bool | None = None
    currency: str | None = None
    hkont_sales: str | None = None
    hkont_purchase: str | None = None
    ar_account: str | None = None
    ap_account: str | None = None
    note: str | None = None


class DepositCreate(BaseModel):
    profile_id: int
    deposit_date: date
    amount: float
    currency: str = "KRW"
    exchange_rate: float | None = None
    reference: str | None = None
    description: str | None = None


class DepositUpdate(BaseModel):
    deposit_date: date | None = None
    amount: float | None = None
    currency: str | None = None
    exchange_rate: float | None = None
    reference: str | None = None
    description: str | None = None


class DepositUsageCreate(BaseModel):
    deposit_id: int
    usage_date: date
    amount: float
    billing_cycle: str | None = None
    slip_batch_id: str | None = None
    uid: str | None = None
    description: str | None = None


# ===== 예치금 관리 (먼저 정의 - 라우트 우선순위) =====


@router.get("/deposits")
def get_deposits(
    profile_id: int | None = Query(None),
    company_seq: int | None = Query(None),
    vendor: str | None = Query(None),
    include_exhausted: bool = Query(False),
    db: Session = Depends(get_db),
):
    """예치금 목록 조회"""
    query = db.query(Deposit).filter(Deposit.profile_id.isnot(None))

    if profile_id:
        query = query.filter(Deposit.profile_id == profile_id)
    elif company_seq and vendor:
        profile = (
            db.query(CompanyBillingProfile)
            .filter(CompanyBillingProfile.company_seq == company_seq, CompanyBillingProfile.vendor == vendor)
            .first()
        )
        if profile:
            query = query.filter(Deposit.profile_id == profile.id)

    if not include_exhausted:
        query = query.filter(Deposit.is_exhausted == False)

    deposits = query.order_by(Deposit.deposit_date).all()

    result = []
    for d in deposits:
        profile = db.query(CompanyBillingProfile).filter(CompanyBillingProfile.id == d.profile_id).first()
        company = db.query(HBCompany).filter(HBCompany.seq == profile.company_seq).first() if profile else None

        result.append({
            "id": d.id,
            "profile_id": d.profile_id,
            "company_name": company.name if company else None,
            "vendor": profile.vendor if profile else None,
            "deposit_date": str(d.deposit_date),
            "amount": d.amount,
            "currency": d.currency,
            "exchange_rate": d.exchange_rate,
            "remaining_amount": round_decimal(d.remaining_amount, 2),
            "is_exhausted": d.is_exhausted,
            "reference": d.reference,
            "description": d.description,
        })

    return result


@router.patch("/deposits/{deposit_id}")
def update_deposit(deposit_id: int, data: DepositUpdate, db: Session = Depends(get_db)):
    """예치금 수정"""
    deposit = db.query(Deposit).filter(Deposit.id == deposit_id, Deposit.profile_id.isnot(None)).first()
    if not deposit:
        raise HTTPException(status_code=404, detail="Deposit not found")

    if data.deposit_date is not None:
        deposit.deposit_date = data.deposit_date
    if data.currency is not None:
        deposit.currency = data.currency
    if data.exchange_rate is not None:
        deposit.exchange_rate = data.exchange_rate
    if data.reference is not None:
        deposit.reference = data.reference
    if data.description is not None:
        deposit.description = data.description

    # 금액 변경 시 잔액 비례 조정
    if data.amount is not None and data.amount != deposit.amount:
        diff = data.amount - deposit.amount
        new_remaining = deposit.remaining_amount + diff
        deposit.amount = data.amount
        if new_remaining <= 0:
            deposit.remaining_amount = 0
            deposit.is_exhausted = True
        else:
            deposit.remaining_amount = new_remaining
            deposit.is_exhausted = False

    db.commit()
    db.refresh(deposit)

    profile = db.query(CompanyBillingProfile).filter(CompanyBillingProfile.id == deposit.profile_id).first()
    company = db.query(HBCompany).filter(HBCompany.seq == profile.company_seq).first() if profile else None

    return {
        "id": deposit.id,
        "profile_id": deposit.profile_id,
        "company_name": company.name if company else None,
        "vendor": profile.vendor if profile else None,
        "deposit_date": str(deposit.deposit_date),
        "amount": deposit.amount,
        "currency": deposit.currency,
        "exchange_rate": deposit.exchange_rate,
        "remaining_amount": round_decimal(deposit.remaining_amount, 2),
        "is_exhausted": deposit.is_exhausted,
        "reference": deposit.reference,
        "description": deposit.description,
    }


@router.post("/deposits")
def create_deposit(data: DepositCreate, db: Session = Depends(get_db)):
    """예치금 충전 등록"""
    profile = db.query(CompanyBillingProfile).filter(CompanyBillingProfile.id == data.profile_id).first()
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")

    deposit = Deposit(
        profile_id=data.profile_id,
        deposit_date=data.deposit_date,
        amount=data.amount,
        currency=data.currency,
        exchange_rate=data.exchange_rate,
        remaining_amount=data.amount,  # 초기 잔액 = 충전액
        reference=data.reference,
        description=data.description,
    )
    db.add(deposit)
    db.commit()
    db.refresh(deposit)

    return {"success": True, "id": deposit.id, "remaining_amount": deposit.remaining_amount}


@router.post("/deposits/use")
def use_deposit(data: DepositUsageCreate, db: Session = Depends(get_db)):
    """예치금 사용 (단일 예치금에서 차감)"""
    deposit = db.query(Deposit).filter(Deposit.id == data.deposit_id).first()
    if not deposit:
        raise HTTPException(status_code=404, detail="Deposit not found")

    if deposit.is_exhausted:
        raise HTTPException(status_code=400, detail="Deposit is already exhausted")

    if data.amount > deposit.remaining_amount:
        raise HTTPException(
            status_code=400,
            detail=f"Insufficient balance. Available: {deposit.remaining_amount}, Requested: {data.amount}",
        )

    # 사용 기록 생성
    amount_krw = None
    if deposit.currency != "KRW" and deposit.exchange_rate:
        amount_krw = round_decimal(data.amount * deposit.exchange_rate, 0)

    usage = DepositUsage(
        deposit_id=data.deposit_id,
        usage_date=data.usage_date,
        amount=data.amount,
        amount_krw=amount_krw,
        billing_cycle=data.billing_cycle,
        slip_batch_id=data.slip_batch_id,
        uid=data.uid,
        description=data.description,
    )
    db.add(usage)

    # 잔액 차감
    deposit.remaining_amount -= data.amount
    if deposit.remaining_amount <= 0:
        deposit.remaining_amount = 0
        deposit.is_exhausted = True

    db.commit()

    return {
        "success": True,
        "usage_id": usage.id,
        "remaining_amount": round_decimal(deposit.remaining_amount, 2),
        "is_exhausted": deposit.is_exhausted,
    }


@router.post("/deposits/use-fifo")
def use_deposit_fifo(
    profile_id: int,
    amount: float,
    usage_date: date,
    billing_cycle: str | None = None,
    slip_batch_id: str | None = None,
    uid: str | None = None,
    description: str | None = None,
    db: Session = Depends(get_db),
):
    """예치금 FIFO 사용 (가장 오래된 예치금부터 차감)"""
    profile = db.query(CompanyBillingProfile).filter(CompanyBillingProfile.id == profile_id).first()
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")

    # 사용 가능한 예치금 조회 (FIFO: 날짜순)
    deposits = (
        db.query(Deposit)
        .filter(Deposit.profile_id == profile_id, Deposit.is_exhausted == False)
        .order_by(Deposit.deposit_date)
        .all()
    )

    total_available = sum(d.remaining_amount for d in deposits)
    if amount > total_available:
        raise HTTPException(
            status_code=400,
            detail=f"Insufficient balance. Available: {total_available}, Requested: {amount}",
        )

    remaining_to_use = amount
    usages_created = []

    for deposit in deposits:
        if remaining_to_use <= 0:
            break

        use_from_this = min(remaining_to_use, deposit.remaining_amount)

        # 사용 기록 생성
        amount_krw = None
        if deposit.currency != "KRW" and deposit.exchange_rate:
            amount_krw = round_decimal(use_from_this * deposit.exchange_rate, 0)

        usage = DepositUsage(
            deposit_id=deposit.id,
            usage_date=usage_date,
            amount=use_from_this,
            amount_krw=amount_krw,
            billing_cycle=billing_cycle,
            slip_batch_id=slip_batch_id,
            uid=uid,
            description=description,
        )
        db.add(usage)

        # 잔액 차감
        deposit.remaining_amount -= use_from_this
        if deposit.remaining_amount <= 0:
            deposit.remaining_amount = 0
            deposit.is_exhausted = True

        usages_created.append({
            "deposit_id": deposit.id,
            "deposit_date": str(deposit.deposit_date),
            "amount_used": use_from_this,
            "exchange_rate": deposit.exchange_rate,
            "amount_krw": amount_krw,
        })

        remaining_to_use -= use_from_this

    db.commit()

    # 최종 잔액 계산
    new_balance = (
        db.query(func.sum(Deposit.remaining_amount))
        .filter(Deposit.profile_id == profile_id, Deposit.is_exhausted == False)
        .scalar()
    ) or 0

    return {
        "success": True,
        "amount_used": amount,
        "usages": usages_created,
        "remaining_balance": round_decimal(new_balance, 2),
    }


@router.get("/deposits/balance/{profile_id}")
def get_deposit_balance(profile_id: int, db: Session = Depends(get_db)):
    """예치금 잔액 조회"""
    profile = db.query(CompanyBillingProfile).filter(CompanyBillingProfile.id == profile_id).first()
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")

    company = db.query(HBCompany).filter(HBCompany.seq == profile.company_seq).first()

    # 통화별 잔액
    deposits = (
        db.query(Deposit)
        .filter(Deposit.profile_id == profile_id, Deposit.is_exhausted == False)
        .all()
    )

    balance_by_currency = {}
    for d in deposits:
        if d.currency not in balance_by_currency:
            balance_by_currency[d.currency] = 0
        balance_by_currency[d.currency] += d.remaining_amount

    return {
        "profile_id": profile_id,
        "company_name": company.name if company else None,
        "vendor": profile.vendor,
        "balance_by_currency": {k: round_decimal(v, 2) for k, v in balance_by_currency.items()},
        "total_deposits": len(deposits),
    }


@router.get("/deposits/{deposit_id}")
def get_deposit_detail(deposit_id: int, db: Session = Depends(get_db)):
    """예치금 상세 조회 (사용 내역 포함)"""
    deposit = db.query(Deposit).filter(Deposit.id == deposit_id).first()
    if not deposit:
        raise HTTPException(status_code=404, detail="Deposit not found")

    profile = db.query(CompanyBillingProfile).filter(CompanyBillingProfile.id == deposit.profile_id).first()
    company = db.query(HBCompany).filter(HBCompany.seq == profile.company_seq).first() if profile else None

    usages = db.query(DepositUsage).filter(DepositUsage.deposit_id == deposit_id).order_by(DepositUsage.usage_date).all()

    return {
        "id": deposit.id,
        "profile_id": deposit.profile_id,
        "company_name": company.name if company else None,
        "vendor": profile.vendor if profile else None,
        "deposit_date": str(deposit.deposit_date),
        "amount": deposit.amount,
        "currency": deposit.currency,
        "exchange_rate": deposit.exchange_rate,
        "remaining_amount": round_decimal(deposit.remaining_amount, 2),
        "is_exhausted": deposit.is_exhausted,
        "reference": deposit.reference,
        "description": deposit.description,
        "usages": [
            {
                "id": u.id,
                "usage_date": str(u.usage_date),
                "amount": u.amount,
                "amount_krw": u.amount_krw,
                "billing_cycle": u.billing_cycle,
                "uid": u.uid,
                "description": u.description,
            }
            for u in usages
        ],
    }


# ===== 청구 프로필 =====


@router.get("/")
def get_billing_profiles(
    company_seq: int | None = Query(None),
    vendor: str | None = Query(None),
    db: Session = Depends(get_db),
):
    """청구 프로필 목록 조회"""
    query = db.query(CompanyBillingProfile)

    if company_seq:
        query = query.filter(CompanyBillingProfile.company_seq == company_seq)
    if vendor:
        query = query.filter(CompanyBillingProfile.vendor == vendor)

    profiles = query.order_by(CompanyBillingProfile.company_seq).all()

    result = []
    for p in profiles:
        company = db.query(HBCompany).filter(HBCompany.seq == p.company_seq).first()
        result.append({
            "id": p.id,
            "company_seq": p.company_seq,
            "company_name": company.name if company else None,
            "vendor": p.vendor,
            "payment_type": p.payment_type,
            "has_sales_agreement": p.has_sales_agreement,
            "has_purchase_agreement": p.has_purchase_agreement,
            "currency": p.currency,
            "hkont_sales": p.hkont_sales,
            "hkont_purchase": p.hkont_purchase,
            "ar_account": p.ar_account,
            "ap_account": p.ap_account,
            "note": p.note,
        })

    return result


@router.post("/")
def create_billing_profile(data: BillingProfileCreate, db: Session = Depends(get_db)):
    """청구 프로필 생성"""
    # 중복 체크
    existing = (
        db.query(CompanyBillingProfile)
        .filter(
            CompanyBillingProfile.company_seq == data.company_seq,
            CompanyBillingProfile.vendor == data.vendor,
        )
        .first()
    )
    if existing:
        raise HTTPException(status_code=400, detail="Profile already exists for this company and vendor")

    profile = CompanyBillingProfile(**data.model_dump())
    db.add(profile)
    db.commit()
    db.refresh(profile)

    return {"success": True, "id": profile.id}


@router.get("/{profile_id}")
def get_billing_profile(profile_id: int, db: Session = Depends(get_db)):
    """청구 프로필 상세 조회"""
    profile = db.query(CompanyBillingProfile).filter(CompanyBillingProfile.id == profile_id).first()
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")

    company = db.query(HBCompany).filter(HBCompany.seq == profile.company_seq).first()

    # 예치금 잔액 계산
    deposit_balance = (
        db.query(func.sum(Deposit.remaining_amount))
        .filter(Deposit.profile_id == profile_id, Deposit.is_exhausted == False)
        .scalar()
    ) or 0

    return {
        "id": profile.id,
        "company_seq": profile.company_seq,
        "company_name": company.name if company else None,
        "is_overseas": company.is_overseas if company else False,
        "vendor": profile.vendor,
        "payment_type": profile.payment_type,
        "has_sales_agreement": profile.has_sales_agreement,
        "has_purchase_agreement": profile.has_purchase_agreement,
        "currency": profile.currency,
        "hkont_sales": profile.hkont_sales,
        "hkont_purchase": profile.hkont_purchase,
        "ar_account": profile.ar_account,
        "ap_account": profile.ap_account,
        "note": profile.note,
        "deposit_balance": round_decimal(deposit_balance, 2),
    }


@router.patch("/{profile_id}")
def update_billing_profile(profile_id: int, data: BillingProfileUpdate, db: Session = Depends(get_db)):
    """청구 프로필 수정"""
    profile = db.query(CompanyBillingProfile).filter(CompanyBillingProfile.id == profile_id).first()
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")

    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(profile, key, value)

    db.commit()
    return {"success": True, "id": profile_id}


@router.delete("/{profile_id}")
def delete_billing_profile(profile_id: int, db: Session = Depends(get_db)):
    """청구 프로필 삭제"""
    profile = db.query(CompanyBillingProfile).filter(CompanyBillingProfile.id == profile_id).first()
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")

    # 연관된 예치금 확인
    has_deposits = db.query(Deposit).filter(Deposit.profile_id == profile_id).first()
    if has_deposits:
        raise HTTPException(status_code=400, detail="Cannot delete profile with deposit records")

    db.delete(profile)
    db.commit()
    return {"success": True}
