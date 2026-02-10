"""
계약별 청구 설정 및 예치금 관리 API
"""

from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.billing_profile import (
    ContractBillingProfile,
    Deposit,
    DepositUsage,
    ExchangeRateType,
    PAYMENT_TYPE_TAX_CODE,
    PaymentType,
)
from app.models.hb import HBCompany, HBContract

router = APIRouter(prefix="/api/contract-billing-profile", tags=["contract-billing-profile"])


def round_decimal(value: float, places: int = 2) -> float:
    """소수점 정확한 반올림 (ROUND_HALF_UP)"""
    d = Decimal(str(value))
    return float(d.quantize(Decimal(10) ** -places, rounding=ROUND_HALF_UP))


# ===== Pydantic Models =====


class ContractBillingProfileCreate(BaseModel):
    contract_seq: int
    vendor: str
    payment_type: str = PaymentType.TAX_INVOICE.value
    has_sales_agreement: bool = False
    has_purchase_agreement: bool = False
    currency: str = "KRW"
    exchange_rate_type: str | None = None  # 해외인보이스용 환율 적용 기준
    custom_exchange_rate_date: date | None = None  # 수동 지정 시 환율 적용일
    hkont_sales: str | None = None
    hkont_purchase: str | None = None
    ar_account: str | None = None
    ap_account: str | None = None
    rounding_rule_override: str | None = None
    note: str | None = None


class ContractBillingProfileUpdate(BaseModel):
    payment_type: str | None = None
    has_sales_agreement: bool | None = None
    has_purchase_agreement: bool | None = None
    currency: str | None = None
    exchange_rate_type: str | None = None
    custom_exchange_rate_date: date | None = None
    hkont_sales: str | None = None
    hkont_purchase: str | None = None
    ar_account: str | None = None
    ap_account: str | None = None
    rounding_rule_override: str | None = None
    note: str | None = None


class ContractDepositCreate(BaseModel):
    contract_profile_id: int
    deposit_date: date
    amount: float
    currency: str = "KRW"
    exchange_rate: float | None = None
    reference: str | None = None
    description: str | None = None


class ContractDepositUpdate(BaseModel):
    deposit_date: date | None = None
    amount: float | None = None
    currency: str | None = None
    exchange_rate: float | None = None
    reference: str | None = None
    description: str | None = None


# ===== 계약별 프로필 =====


@router.get("/")
def get_contract_billing_profiles(
    company_seq: int | None = Query(None),
    contract_seq: int | None = Query(None),
    vendor: str | None = Query(None),
    db: Session = Depends(get_db),
):
    """계약별 청구 프로필 목록 조회"""
    query = db.query(ContractBillingProfile)

    if contract_seq:
        query = query.filter(ContractBillingProfile.contract_seq == contract_seq)
    if vendor:
        query = query.filter(ContractBillingProfile.vendor == vendor)

    # company_seq로 필터링할 경우 Contract를 통해 조회
    if company_seq:
        contract_seqs = [
            c.seq
            for c in db.query(HBContract.seq).filter(HBContract.company_seq == company_seq).all()
        ]
        query = query.filter(ContractBillingProfile.contract_seq.in_(contract_seqs))

    profiles = query.order_by(ContractBillingProfile.contract_seq).all()

    result = []
    for p in profiles:
        contract = db.query(HBContract).filter(HBContract.seq == p.contract_seq).first()
        company = db.query(HBCompany).filter(HBCompany.seq == contract.company_seq).first() if contract else None

        result.append({
            "id": p.id,
            "contract_seq": p.contract_seq,
            "contract_name": contract.name if contract else None,
            "company_seq": contract.company_seq if contract else None,
            "company_name": company.name if company else None,
            "vendor": p.vendor,
            "payment_type": p.payment_type,
            "tax_code": PAYMENT_TYPE_TAX_CODE.get(p.payment_type, "A1"),
            "has_sales_agreement": p.has_sales_agreement,
            "has_purchase_agreement": p.has_purchase_agreement,
            "currency": p.currency,
            "exchange_rate_type": p.exchange_rate_type,
            "custom_exchange_rate_date": str(p.custom_exchange_rate_date) if p.custom_exchange_rate_date else None,
            "hkont_sales": p.hkont_sales,
            "hkont_purchase": p.hkont_purchase,
            "ar_account": p.ar_account,
            "ap_account": p.ap_account,
            "rounding_rule_override": p.rounding_rule_override,
            "note": p.note,
        })

    return result


@router.get("/by-company/{company_seq}")
def get_contracts_with_profiles(
    company_seq: int,
    vendor: str = Query("alibaba"),
    db: Session = Depends(get_db),
):
    """회사별 계약 + 프로필 현황 조회"""
    company = db.query(HBCompany).filter(HBCompany.seq == company_seq).first()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")

    contracts = (
        db.query(HBContract)
        .filter(HBContract.company_seq == company_seq, HBContract.vendor == vendor, HBContract.enabled == True)
        .order_by(HBContract.name)
        .all()
    )

    result = []
    for c in contracts:
        profile = (
            db.query(ContractBillingProfile)
            .filter(
                ContractBillingProfile.contract_seq == c.seq,
                ContractBillingProfile.vendor == vendor,
            )
            .first()
        )

        result.append({
            "contract_seq": c.seq,
            "contract_name": c.name,
            "corporation": c.corporation,
            "discount_rate": c.discount_rate,
            "sales_person": c.sales_person,
            "sales_contract_code": c.sales_contract_code,
            "has_profile": profile is not None,
            "profile": {
                "id": profile.id,
                "payment_type": profile.payment_type,
                "tax_code": PAYMENT_TYPE_TAX_CODE.get(profile.payment_type, "A1"),
                "currency": profile.currency,
                "exchange_rate_type": profile.exchange_rate_type,
                "has_sales_agreement": profile.has_sales_agreement,
                "has_purchase_agreement": profile.has_purchase_agreement,
                "rounding_rule_override": profile.rounding_rule_override,
            } if profile else None,
        })

    return {
        "company_seq": company_seq,
        "company_name": company.name,
        "is_overseas": company.is_overseas,
        "contracts": result,
        "total_contracts": len(result),
        "with_profile": sum(1 for c in result if c["has_profile"]),
    }


@router.post("/")
def create_contract_billing_profile(data: ContractBillingProfileCreate, db: Session = Depends(get_db)):
    """계약별 청구 프로필 생성"""
    # 계약 존재 확인
    contract = db.query(HBContract).filter(HBContract.seq == data.contract_seq).first()
    if not contract:
        raise HTTPException(status_code=404, detail="Contract not found")

    # 중복 체크
    existing = (
        db.query(ContractBillingProfile)
        .filter(
            ContractBillingProfile.contract_seq == data.contract_seq,
            ContractBillingProfile.vendor == data.vendor,
        )
        .first()
    )
    if existing:
        raise HTTPException(status_code=400, detail="Profile already exists for this contract and vendor")

    profile = ContractBillingProfile(**data.model_dump())
    db.add(profile)
    db.commit()
    db.refresh(profile)

    return {"success": True, "id": profile.id}


@router.get("/{profile_id}")
def get_contract_billing_profile(profile_id: int, db: Session = Depends(get_db)):
    """계약별 청구 프로필 상세 조회"""
    profile = db.query(ContractBillingProfile).filter(ContractBillingProfile.id == profile_id).first()
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")

    contract = db.query(HBContract).filter(HBContract.seq == profile.contract_seq).first()
    company = db.query(HBCompany).filter(HBCompany.seq == contract.company_seq).first() if contract else None

    # 예치금 잔액 계산
    deposit_balance = (
        db.query(func.sum(Deposit.remaining_amount))
        .filter(Deposit.contract_profile_id == profile_id, Deposit.is_exhausted == False)
        .scalar()
    ) or 0

    return {
        "id": profile.id,
        "contract_seq": profile.contract_seq,
        "contract_name": contract.name if contract else None,
        "company_seq": contract.company_seq if contract else None,
        "company_name": company.name if company else None,
        "is_overseas": company.is_overseas if company else False,
        "vendor": profile.vendor,
        "payment_type": profile.payment_type,
        "tax_code": PAYMENT_TYPE_TAX_CODE.get(profile.payment_type, "A1"),
        "has_sales_agreement": profile.has_sales_agreement,
        "has_purchase_agreement": profile.has_purchase_agreement,
        "currency": profile.currency,
        "exchange_rate_type": profile.exchange_rate_type,
        "custom_exchange_rate_date": str(profile.custom_exchange_rate_date) if profile.custom_exchange_rate_date else None,
        "hkont_sales": profile.hkont_sales,
        "hkont_purchase": profile.hkont_purchase,
        "ar_account": profile.ar_account,
        "ap_account": profile.ap_account,
        "rounding_rule_override": profile.rounding_rule_override,
        "note": profile.note,
        "deposit_balance": round_decimal(deposit_balance, 2),
    }


@router.patch("/{profile_id}")
def update_contract_billing_profile(
    profile_id: int, data: ContractBillingProfileUpdate, db: Session = Depends(get_db)
):
    """계약별 청구 프로필 수정"""
    profile = db.query(ContractBillingProfile).filter(ContractBillingProfile.id == profile_id).first()
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")

    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(profile, key, value)

    db.commit()
    return {"success": True, "id": profile_id}


@router.delete("/{profile_id}")
def delete_contract_billing_profile(profile_id: int, db: Session = Depends(get_db)):
    """계약별 청구 프로필 삭제"""
    profile = db.query(ContractBillingProfile).filter(ContractBillingProfile.id == profile_id).first()
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")

    # 연관된 예치금 확인
    has_deposits = db.query(Deposit).filter(Deposit.contract_profile_id == profile_id).first()
    if has_deposits:
        raise HTTPException(status_code=400, detail="Cannot delete profile with deposit records")

    db.delete(profile)
    db.commit()
    return {"success": True}


# ===== 계약 프로필용 예치금 관리 =====


@router.get("/deposits")
def get_contract_deposits(
    contract_profile_id: int | None = Query(None),
    contract_seq: int | None = Query(None),
    vendor: str | None = Query(None),
    include_exhausted: bool = Query(False),
    db: Session = Depends(get_db),
):
    """계약 프로필용 예치금 목록 조회"""
    query = db.query(Deposit).filter(Deposit.contract_profile_id.isnot(None))

    if contract_profile_id:
        query = query.filter(Deposit.contract_profile_id == contract_profile_id)
    elif contract_seq and vendor:
        profile = (
            db.query(ContractBillingProfile)
            .filter(
                ContractBillingProfile.contract_seq == contract_seq,
                ContractBillingProfile.vendor == vendor,
            )
            .first()
        )
        if profile:
            query = query.filter(Deposit.contract_profile_id == profile.id)

    if not include_exhausted:
        query = query.filter(Deposit.is_exhausted == False)

    deposits = query.order_by(Deposit.deposit_date).all()

    result = []
    for d in deposits:
        profile = db.query(ContractBillingProfile).filter(ContractBillingProfile.id == d.contract_profile_id).first()
        contract = db.query(HBContract).filter(HBContract.seq == profile.contract_seq).first() if profile else None
        company = db.query(HBCompany).filter(HBCompany.seq == contract.company_seq).first() if contract else None

        result.append({
            "id": d.id,
            "contract_profile_id": d.contract_profile_id,
            "contract_name": contract.name if contract else None,
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
def update_contract_deposit(deposit_id: int, data: ContractDepositUpdate, db: Session = Depends(get_db)):
    """계약 프로필 예치금 수정"""
    deposit = db.query(Deposit).filter(Deposit.id == deposit_id, Deposit.contract_profile_id.isnot(None)).first()
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

    profile = db.query(ContractBillingProfile).filter(ContractBillingProfile.id == deposit.contract_profile_id).first()
    contract = db.query(HBContract).filter(HBContract.seq == profile.contract_seq).first() if profile else None
    company = db.query(HBCompany).filter(HBCompany.seq == contract.company_seq).first() if contract else None

    return {
        "id": deposit.id,
        "contract_profile_id": deposit.contract_profile_id,
        "contract_name": contract.name if contract else None,
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
def create_contract_deposit(data: ContractDepositCreate, db: Session = Depends(get_db)):
    """계약 프로필용 예치금 충전 등록"""
    profile = db.query(ContractBillingProfile).filter(ContractBillingProfile.id == data.contract_profile_id).first()
    if not profile:
        raise HTTPException(status_code=404, detail="Contract profile not found")

    deposit = Deposit(
        contract_profile_id=data.contract_profile_id,
        profile_id=None,  # 회사 프로필 아님
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


@router.post("/deposits/use-fifo")
def use_contract_deposit_fifo(
    contract_profile_id: int,
    amount: float,
    usage_date: date,
    billing_cycle: str | None = None,
    slip_batch_id: str | None = None,
    uid: str | None = None,
    description: str | None = None,
    db: Session = Depends(get_db),
):
    """계약 프로필용 예치금 FIFO 사용"""
    profile = db.query(ContractBillingProfile).filter(ContractBillingProfile.id == contract_profile_id).first()
    if not profile:
        raise HTTPException(status_code=404, detail="Contract profile not found")

    # 사용 가능한 예치금 조회 (FIFO: 날짜순)
    deposits = (
        db.query(Deposit)
        .filter(Deposit.contract_profile_id == contract_profile_id, Deposit.is_exhausted == False)
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
        .filter(Deposit.contract_profile_id == contract_profile_id, Deposit.is_exhausted == False)
        .scalar()
    ) or 0

    return {
        "success": True,
        "amount_used": amount,
        "usages": usages_created,
        "remaining_balance": round_decimal(new_balance, 2),
    }


@router.get("/deposits/balance/{contract_profile_id}")
def get_contract_deposit_balance(contract_profile_id: int, db: Session = Depends(get_db)):
    """계약 프로필용 예치금 잔액 조회"""
    profile = db.query(ContractBillingProfile).filter(ContractBillingProfile.id == contract_profile_id).first()
    if not profile:
        raise HTTPException(status_code=404, detail="Contract profile not found")

    contract = db.query(HBContract).filter(HBContract.seq == profile.contract_seq).first()
    company = db.query(HBCompany).filter(HBCompany.seq == contract.company_seq).first() if contract else None

    # 통화별 잔액
    deposits = (
        db.query(Deposit)
        .filter(Deposit.contract_profile_id == contract_profile_id, Deposit.is_exhausted == False)
        .all()
    )

    balance_by_currency = {}
    for d in deposits:
        if d.currency not in balance_by_currency:
            balance_by_currency[d.currency] = 0
        balance_by_currency[d.currency] += d.remaining_amount

    return {
        "contract_profile_id": contract_profile_id,
        "contract_name": contract.name if contract else None,
        "company_name": company.name if company else None,
        "vendor": profile.vendor,
        "balance_by_currency": {k: round_decimal(v, 2) for k, v in balance_by_currency.items()},
        "total_deposits": len(deposits),
    }
