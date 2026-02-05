"""
분할 청구 관리 API (1 UID → N 법인 배분)
"""

from datetime import date
from decimal import ROUND_DOWN, ROUND_HALF_UP, Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models.billing_profile import SplitBillingAllocation, SplitBillingRule, SplitType
from app.models.hb import HBCompany, HBContract, HBVendorAccount

router = APIRouter(prefix="/api/split-billing", tags=["split-billing"])


# ===== Request/Response 모델 =====


class AllocationCreate(BaseModel):
    target_company_seq: int
    split_type: str = SplitType.PERCENTAGE.value
    split_value: float  # 비율(%) 또는 고정금액
    priority: int = 0
    note: str | None = None


class SplitRuleCreate(BaseModel):
    source_account_id: str  # UID
    source_contract_seq: int
    name: str | None = None
    effective_from: date | None = None
    effective_to: date | None = None
    allocations: list[AllocationCreate]


class SplitRuleUpdate(BaseModel):
    name: str | None = None
    effective_from: date | None = None
    effective_to: date | None = None
    is_active: bool | None = None


class AllocationUpdate(BaseModel):
    target_company_seq: int | None = None
    split_type: str | None = None
    split_value: float | None = None
    priority: int | None = None
    note: str | None = None


class SimulateRequest(BaseModel):
    source_account_id: str  # UID
    amount_usd: float
    billing_cycle: str  # YYYYMM


# ===== API 엔드포인트 =====


@router.post("/rules")
def create_split_rule(data: SplitRuleCreate, db: Session = Depends(get_db)):
    """분할 청구 규칙 생성"""
    # 소스 계정 확인
    account = db.query(HBVendorAccount).filter(HBVendorAccount.id == data.source_account_id).first()
    if not account:
        raise HTTPException(status_code=404, detail="Source account (UID) not found")

    # 소스 계약 확인
    contract = db.query(HBContract).filter(HBContract.seq == data.source_contract_seq).first()
    if not contract:
        raise HTTPException(status_code=404, detail="Source contract not found")

    # 배분 대상 검증
    total_percentage = 0
    for alloc in data.allocations:
        company = db.query(HBCompany).filter(HBCompany.seq == alloc.target_company_seq).first()
        if not company:
            raise HTTPException(status_code=404, detail=f"Target company {alloc.target_company_seq} not found")
        if alloc.split_type == SplitType.PERCENTAGE.value:
            total_percentage += alloc.split_value

    # 비율 합계 검증 (100% 초과 불가)
    if total_percentage > 100:
        raise HTTPException(status_code=400, detail=f"Total percentage ({total_percentage}%) exceeds 100%")

    # 규칙 생성
    rule = SplitBillingRule(
        source_account_id=data.source_account_id,
        source_contract_seq=data.source_contract_seq,
        name=data.name or f"Split rule for {data.source_account_id}",
        effective_from=data.effective_from,
        effective_to=data.effective_to,
    )
    db.add(rule)
    db.flush()  # ID 생성

    # 배분 생성
    for alloc in data.allocations:
        allocation = SplitBillingAllocation(
            rule_id=rule.id,
            target_company_seq=alloc.target_company_seq,
            split_type=alloc.split_type,
            split_value=alloc.split_value,
            priority=alloc.priority,
            note=alloc.note,
        )
        db.add(allocation)

    db.commit()
    db.refresh(rule)

    return {
        "success": True,
        "id": rule.id,
        "allocation_count": len(data.allocations),
        "message": f"분할 청구 규칙이 생성되었습니다 ({len(data.allocations)}개 배분 대상).",
    }


@router.get("/rules")
def get_split_rules(
    source_account_id: str | None = Query(None),
    source_contract_seq: int | None = Query(None),
    is_active: bool | None = Query(None),
    limit: int = Query(100, le=500),
    offset: int = Query(0),
    db: Session = Depends(get_db),
):
    """분할 청구 규칙 목록 조회"""
    query = (
        db.query(SplitBillingRule)
        .options(
            joinedload(SplitBillingRule.source_account),
            joinedload(SplitBillingRule.source_contract),
            joinedload(SplitBillingRule.allocations).joinedload(SplitBillingAllocation.target_company),
        )
    )

    if source_account_id:
        query = query.filter(SplitBillingRule.source_account_id == source_account_id)
    if source_contract_seq:
        query = query.filter(SplitBillingRule.source_contract_seq == source_contract_seq)
    if is_active is not None:
        query = query.filter(SplitBillingRule.is_active == is_active)

    total = query.count()
    rules = query.order_by(SplitBillingRule.created_at.desc()).offset(offset).limit(limit).all()

    return {
        "total": total,
        "data": [
            {
                "id": r.id,
                "name": r.name,
                "source_account_id": r.source_account_id,
                "source_account_name": r.source_account.name if r.source_account else None,
                "source_contract_seq": r.source_contract_seq,
                "source_contract_name": r.source_contract.name if r.source_contract else None,
                "effective_from": str(r.effective_from) if r.effective_from else None,
                "effective_to": str(r.effective_to) if r.effective_to else None,
                "is_active": r.is_active,
                "allocation_count": len(r.allocations),
                "allocations": [
                    {
                        "id": a.id,
                        "target_company_seq": a.target_company_seq,
                        "target_company_name": a.target_company.name if a.target_company else None,
                        "split_type": a.split_type,
                        "split_value": a.split_value,
                        "priority": a.priority,
                    }
                    for a in sorted(r.allocations, key=lambda x: (x.priority, x.id))
                ],
            }
            for r in rules
        ],
    }


@router.get("/rules/{rule_id}")
def get_split_rule(rule_id: int, db: Session = Depends(get_db)):
    """분할 청구 규칙 상세 조회"""
    rule = (
        db.query(SplitBillingRule)
        .options(
            joinedload(SplitBillingRule.source_account),
            joinedload(SplitBillingRule.source_contract).joinedload(HBContract.company),
            joinedload(SplitBillingRule.allocations).joinedload(SplitBillingAllocation.target_company),
        )
        .filter(SplitBillingRule.id == rule_id)
        .first()
    )
    if not rule:
        raise HTTPException(status_code=404, detail="Split billing rule not found")

    return {
        "id": rule.id,
        "name": rule.name,
        "source_account_id": rule.source_account_id,
        "source_account_name": rule.source_account.name if rule.source_account else None,
        "source_contract_seq": rule.source_contract_seq,
        "source_contract_name": rule.source_contract.name if rule.source_contract else None,
        "source_company_name": (
            rule.source_contract.company.name if rule.source_contract and rule.source_contract.company else None
        ),
        "effective_from": str(rule.effective_from) if rule.effective_from else None,
        "effective_to": str(rule.effective_to) if rule.effective_to else None,
        "is_active": rule.is_active,
        "allocations": [
            {
                "id": a.id,
                "target_company_seq": a.target_company_seq,
                "target_company_name": a.target_company.name if a.target_company else None,
                "target_company_bp": a.target_company.bp_number if a.target_company else None,
                "split_type": a.split_type,
                "split_value": a.split_value,
                "priority": a.priority,
                "note": a.note,
            }
            for a in sorted(rule.allocations, key=lambda x: (x.priority, x.id))
        ],
        "created_at": rule.created_at.isoformat() if rule.created_at else None,
        "updated_at": rule.updated_at.isoformat() if rule.updated_at else None,
    }


@router.patch("/rules/{rule_id}")
def update_split_rule(
    rule_id: int, data: SplitRuleUpdate, db: Session = Depends(get_db)
):
    """분할 청구 규칙 수정"""
    rule = db.query(SplitBillingRule).filter(SplitBillingRule.id == rule_id).first()
    if not rule:
        raise HTTPException(status_code=404, detail="Split billing rule not found")

    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(rule, key, value)

    db.commit()
    return {"success": True, "id": rule_id}


@router.delete("/rules/{rule_id}")
def delete_split_rule(rule_id: int, db: Session = Depends(get_db)):
    """분할 청구 규칙 삭제 (배분도 함께 삭제)"""
    rule = db.query(SplitBillingRule).filter(SplitBillingRule.id == rule_id).first()
    if not rule:
        raise HTTPException(status_code=404, detail="Split billing rule not found")

    db.delete(rule)
    db.commit()
    return {"success": True, "deleted_id": rule_id}


# ===== 배분 관리 =====


@router.post("/rules/{rule_id}/allocations")
def add_allocation(
    rule_id: int, data: AllocationCreate, db: Session = Depends(get_db)
):
    """배분 대상 추가"""
    rule = db.query(SplitBillingRule).filter(SplitBillingRule.id == rule_id).first()
    if not rule:
        raise HTTPException(status_code=404, detail="Split billing rule not found")

    company = db.query(HBCompany).filter(HBCompany.seq == data.target_company_seq).first()
    if not company:
        raise HTTPException(status_code=404, detail="Target company not found")

    allocation = SplitBillingAllocation(
        rule_id=rule_id,
        target_company_seq=data.target_company_seq,
        split_type=data.split_type,
        split_value=data.split_value,
        priority=data.priority,
        note=data.note,
    )
    db.add(allocation)
    db.commit()
    db.refresh(allocation)

    return {"success": True, "id": allocation.id}


@router.patch("/allocations/{allocation_id}")
def update_allocation(
    allocation_id: int, data: AllocationUpdate, db: Session = Depends(get_db)
):
    """배분 대상 수정"""
    allocation = (
        db.query(SplitBillingAllocation)
        .filter(SplitBillingAllocation.id == allocation_id)
        .first()
    )
    if not allocation:
        raise HTTPException(status_code=404, detail="Allocation not found")

    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(allocation, key, value)

    db.commit()
    return {"success": True, "id": allocation_id}


@router.delete("/allocations/{allocation_id}")
def delete_allocation(allocation_id: int, db: Session = Depends(get_db)):
    """배분 대상 삭제"""
    allocation = (
        db.query(SplitBillingAllocation)
        .filter(SplitBillingAllocation.id == allocation_id)
        .first()
    )
    if not allocation:
        raise HTTPException(status_code=404, detail="Allocation not found")

    db.delete(allocation)
    db.commit()
    return {"success": True, "deleted_id": allocation_id}


# ===== 시뮬레이션 =====


@router.post("/simulate")
def simulate_split(data: SimulateRequest, db: Session = Depends(get_db)):
    """분할 청구 시뮬레이션"""
    result = calculate_split_amounts(
        db, data.source_account_id, data.amount_usd, data.billing_cycle
    )

    if not result:
        return {
            "success": False,
            "message": "No active split rule found for this account",
            "source_account_id": data.source_account_id,
            "amount_usd": data.amount_usd,
        }

    return {
        "success": True,
        "source_account_id": data.source_account_id,
        "original_amount_usd": data.amount_usd,
        "billing_cycle": data.billing_cycle,
        "rule_id": result["rule_id"],
        "rule_name": result["rule_name"],
        "split_results": result["allocations"],
        "remaining_amount": result["remaining"],
    }


def calculate_split_amounts(
    db: Session,
    source_account_id: str,
    amount_usd: float,
    billing_cycle: str,
) -> dict | None:
    """
    분할 청구 금액 계산

    Args:
        db: DB 세션
        source_account_id: 원본 UID
        amount_usd: 원본 금액 (USD)
        billing_cycle: 정산월 (YYYYMM)

    Returns:
        None: 분할 규칙 없음
        dict: 분할 결과
    """
    # 정산월을 날짜로 변환
    year = int(billing_cycle[:4])
    month = int(billing_cycle[4:6])
    cycle_date = date(year, month, 1)

    # 해당 UID의 활성 분할 규칙 조회
    rule = (
        db.query(SplitBillingRule)
        .options(
            joinedload(SplitBillingRule.allocations).joinedload(SplitBillingAllocation.target_company)
        )
        .filter(
            SplitBillingRule.source_account_id == source_account_id,
            SplitBillingRule.is_active == True,
        )
        .first()
    )

    if not rule:
        return None

    # 유효 기간 체크
    if rule.effective_from and rule.effective_from > cycle_date:
        return None
    if rule.effective_to and rule.effective_to < cycle_date:
        return None

    # 배분 계산
    allocations = sorted(rule.allocations, key=lambda x: (x.priority, x.id))
    results = []
    remaining = Decimal(str(amount_usd))

    for alloc in allocations:
        if remaining <= 0:
            break

        if alloc.split_type == SplitType.FIXED_AMOUNT.value:
            # 고정 금액
            alloc_amount = min(Decimal(str(alloc.split_value)), remaining)
        else:  # percentage
            # 비율 (원본 금액 기준)
            alloc_amount = (Decimal(str(amount_usd)) * Decimal(str(alloc.split_value)) / Decimal("100")).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )
            alloc_amount = min(alloc_amount, remaining)

        remaining -= alloc_amount

        results.append({
            "allocation_id": alloc.id,
            "target_company_seq": alloc.target_company_seq,
            "target_company_name": alloc.target_company.name if alloc.target_company else None,
            "target_company_bp": alloc.target_company.bp_number if alloc.target_company else None,
            "split_type": alloc.split_type,
            "split_value": alloc.split_value,
            "allocated_amount_usd": float(alloc_amount),
        })

    return {
        "rule_id": rule.id,
        "rule_name": rule.name,
        "allocations": results,
        "remaining": float(remaining.quantize(Decimal("0.01"), rounding=ROUND_DOWN)),
    }


def get_split_rule_for_uid(
    db: Session,
    uid: str,
    billing_cycle: str,
) -> SplitBillingRule | None:
    """
    특정 UID, 정산월에 적용되는 분할 규칙 조회 (헬퍼 함수)
    """
    year = int(billing_cycle[:4])
    month = int(billing_cycle[4:6])
    cycle_date = date(year, month, 1)

    rule = (
        db.query(SplitBillingRule)
        .options(
            joinedload(SplitBillingRule.allocations).joinedload(SplitBillingAllocation.target_company)
        )
        .filter(
            SplitBillingRule.source_account_id == uid,
            SplitBillingRule.is_active == True,
        )
        .first()
    )

    if not rule:
        return None

    # 유효 기간 체크
    if rule.effective_from and rule.effective_from > cycle_date:
        return None
    if rule.effective_to and rule.effective_to < cycle_date:
        return None

    return rule
