"""공통 예치금 서비스 (회사별/계약별 공용)"""

from datetime import date

from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.billing_profile import Deposit, DepositUsage
from app.utils import round_decimal


def update_deposit_fields(deposit: Deposit, data) -> None:
    """예치금 공통 필드 수정"""
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


def deposit_fifo_use(
    db: Session,
    filter_column,
    filter_value: int,
    amount: float,
    usage_date: date,
    billing_cycle: str | None = None,
    slip_batch_id: str | None = None,
    uid: str | None = None,
    description: str | None = None,
) -> dict:
    """FIFO 예치금 사용 (공통 로직)

    Args:
        filter_column: Deposit.profile_id 또는 Deposit.contract_profile_id
        filter_value: 해당 컬럼의 값
    """
    deposits = (
        db.query(Deposit)
        .filter(filter_column == filter_value, Deposit.is_exhausted == False)
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

        deposit.remaining_amount -= use_from_this
        if deposit.remaining_amount <= 0:
            deposit.remaining_amount = 0
            deposit.is_exhausted = True

        usages_created.append(
            {
                "deposit_id": deposit.id,
                "deposit_date": str(deposit.deposit_date),
                "amount_used": use_from_this,
                "exchange_rate": deposit.exchange_rate,
                "amount_krw": amount_krw,
            }
        )

        remaining_to_use -= use_from_this

    db.commit()

    new_balance = (
        db.query(func.sum(Deposit.remaining_amount))
        .filter(filter_column == filter_value, Deposit.is_exhausted == False)
        .scalar()
    ) or 0

    return {
        "success": True,
        "amount_used": amount,
        "usages": usages_created,
        "remaining_balance": round_decimal(new_balance, 2),
    }


def get_deposit_balance_info(
    db: Session,
    filter_column,
    filter_value: int,
) -> dict:
    """통화별 예치금 잔액 조회 (공통 로직)"""
    deposits = (
        db.query(Deposit).filter(filter_column == filter_value, Deposit.is_exhausted == False).all()
    )

    balance_by_currency = {}
    for d in deposits:
        if d.currency not in balance_by_currency:
            balance_by_currency[d.currency] = 0
        balance_by_currency[d.currency] += d.remaining_amount

    return {
        "balance_by_currency": {k: round_decimal(v, 2) for k, v in balance_by_currency.items()},
        "total_deposits": len(deposits),
    }
