"""
일할 계산 관리 API
"""

import calendar
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models.billing_profile import ProRataPeriod
from app.models.hb import HBContract

router = APIRouter(prefix="/api/pro-rata", tags=["pro-rata"])


# ===== Request/Response 모델 =====


class ProRataPeriodCreate(BaseModel):
    contract_seq: int
    billing_cycle: str  # YYYYMM
    start_day: int  # 1~31
    end_day: int  # 1~31
    note: str | None = None


class ProRataPeriodUpdate(BaseModel):
    start_day: int | None = None
    end_day: int | None = None
    note: str | None = None


class ProRataCalculateRequest(BaseModel):
    contract_seq: int
    billing_cycle: str  # YYYYMM


# ===== Helper 함수 =====


def get_days_in_month(year: int, month: int) -> int:
    """해당 월의 총 일수"""
    return calendar.monthrange(year, month)[1]


def calculate_pro_rata_ratio(
    billing_cycle: str,
    start_day: int,
    end_day: int,
) -> dict:
    """
    일할 비율 계산

    Returns:
        {
            "total_days": int,  # 월 총 일수
            "active_days": int,  # 활성 일수
            "ratio": float,  # 비율
        }
    """
    year = int(billing_cycle[:4])
    month = int(billing_cycle[4:6])
    total_days = get_days_in_month(year, month)

    # 일수 범위 보정
    start_day = max(1, min(start_day, total_days))
    end_day = max(1, min(end_day, total_days))

    if start_day > end_day:
        # 잘못된 범위
        active_days = 0
    else:
        active_days = end_day - start_day + 1

    ratio = active_days / total_days if total_days > 0 else 0

    return {
        "total_days": total_days,
        "active_days": active_days,
        "ratio": round(ratio, 6),
    }


def auto_calculate_pro_rata(
    db: Session,
    contract_seq: int,
    billing_cycle: str,
) -> dict | None:
    """
    계약 시작/종료일 기반 자동 일할 계산

    Returns:
        None: 일할 계산 불필요 (전체 월)
        dict: 일할 계산 필요 시 상세 정보
    """
    contract = (
        db.query(HBContract)
        .filter(HBContract.seq == contract_seq)
        .first()
    )
    if not contract:
        return None

    year = int(billing_cycle[:4])
    month = int(billing_cycle[4:6])
    total_days = get_days_in_month(year, month)
    cycle_start = date(year, month, 1)
    cycle_end = date(year, month, total_days)

    start_day = 1
    end_day = total_days

    # 계약 시작일 체크
    if contract.contract_start_date:
        if contract.contract_start_date > cycle_end:
            # 계약 시작 전
            return {
                "total_days": total_days,
                "active_days": 0,
                "ratio": 0.0,
                "reason": "contract_not_started",
            }
        if contract.contract_start_date > cycle_start:
            # 월 중간 시작
            start_day = contract.contract_start_date.day

    # 계약 종료일 체크
    if contract.contract_end_date:
        if contract.contract_end_date < cycle_start:
            # 계약 종료됨
            return {
                "total_days": total_days,
                "active_days": 0,
                "ratio": 0.0,
                "reason": "contract_ended",
            }
        if contract.contract_end_date < cycle_end:
            # 월 중간 종료
            end_day = contract.contract_end_date.day

    # 전체 월인지 확인
    if start_day == 1 and end_day == total_days:
        return None  # 일할 계산 불필요

    active_days = end_day - start_day + 1
    ratio = active_days / total_days

    return {
        "start_day": start_day,
        "end_day": end_day,
        "total_days": total_days,
        "active_days": active_days,
        "ratio": round(ratio, 6),
        "reason": "partial_month",
    }


# ===== API 엔드포인트 =====


@router.post("/periods")
def create_pro_rata_period(data: ProRataPeriodCreate, db: Session = Depends(get_db)):
    """일할 기간 수동 등록"""
    # 계약 존재 확인
    contract = db.query(HBContract).filter(HBContract.seq == data.contract_seq).first()
    if not contract:
        raise HTTPException(status_code=404, detail="Contract not found")

    # 기존 기간 확인 (중복 방지)
    existing = (
        db.query(ProRataPeriod)
        .filter(
            ProRataPeriod.contract_seq == data.contract_seq,
            ProRataPeriod.billing_cycle == data.billing_cycle,
        )
        .first()
    )
    if existing:
        raise HTTPException(
            status_code=400,
            detail=f"Pro rata period already exists for {data.billing_cycle}. Use PATCH to update.",
        )

    # 비율 계산
    calc = calculate_pro_rata_ratio(data.billing_cycle, data.start_day, data.end_day)

    period = ProRataPeriod(
        contract_seq=data.contract_seq,
        billing_cycle=data.billing_cycle,
        start_day=data.start_day,
        end_day=data.end_day,
        total_days=calc["total_days"],
        active_days=calc["active_days"],
        ratio=calc["ratio"],
        is_manual=True,
        note=data.note,
    )
    db.add(period)
    db.commit()
    db.refresh(period)

    return {
        "success": True,
        "id": period.id,
        "ratio": period.ratio,
        "message": f"일할 비율 {period.ratio:.2%} ({period.active_days}/{period.total_days}일) 등록됨",
    }


@router.get("/periods")
def get_pro_rata_periods(
    contract_seq: int | None = Query(None),
    billing_cycle: str | None = Query(None),
    limit: int = Query(100, le=500),
    offset: int = Query(0),
    db: Session = Depends(get_db),
):
    """일할 기간 목록 조회"""
    query = db.query(ProRataPeriod).options(joinedload(ProRataPeriod.contract))

    if contract_seq is not None:
        query = query.filter(ProRataPeriod.contract_seq == contract_seq)
    if billing_cycle is not None:
        query = query.filter(ProRataPeriod.billing_cycle == billing_cycle)

    total = query.count()
    periods = query.order_by(
        ProRataPeriod.billing_cycle.desc(), ProRataPeriod.created_at.desc()
    ).offset(offset).limit(limit).all()

    return {
        "total": total,
        "data": [
            {
                "id": p.id,
                "contract_seq": p.contract_seq,
                "contract_name": p.contract.name if p.contract else None,
                "billing_cycle": p.billing_cycle,
                "start_day": p.start_day,
                "end_day": p.end_day,
                "total_days": p.total_days,
                "active_days": p.active_days,
                "ratio": p.ratio,
                "is_manual": p.is_manual,
                "note": p.note,
            }
            for p in periods
        ],
    }


@router.get("/periods/{period_id}")
def get_pro_rata_period(period_id: int, db: Session = Depends(get_db)):
    """일할 기간 상세 조회"""
    period = (
        db.query(ProRataPeriod)
        .options(joinedload(ProRataPeriod.contract))
        .filter(ProRataPeriod.id == period_id)
        .first()
    )
    if not period:
        raise HTTPException(status_code=404, detail="Pro rata period not found")

    return {
        "id": period.id,
        "contract_seq": period.contract_seq,
        "contract_name": period.contract.name if period.contract else None,
        "billing_cycle": period.billing_cycle,
        "start_day": period.start_day,
        "end_day": period.end_day,
        "total_days": period.total_days,
        "active_days": period.active_days,
        "ratio": period.ratio,
        "is_manual": period.is_manual,
        "note": period.note,
        "created_at": period.created_at.isoformat() if period.created_at else None,
        "updated_at": period.updated_at.isoformat() if period.updated_at else None,
    }


@router.patch("/periods/{period_id}")
def update_pro_rata_period(
    period_id: int, data: ProRataPeriodUpdate, db: Session = Depends(get_db)
):
    """일할 기간 수정"""
    period = db.query(ProRataPeriod).filter(ProRataPeriod.id == period_id).first()
    if not period:
        raise HTTPException(status_code=404, detail="Pro rata period not found")

    update_data = data.model_dump(exclude_unset=True)

    # start_day/end_day가 변경되면 비율 재계산
    new_start = update_data.get("start_day", period.start_day)
    new_end = update_data.get("end_day", period.end_day)

    if "start_day" in update_data or "end_day" in update_data:
        calc = calculate_pro_rata_ratio(period.billing_cycle, new_start, new_end)
        period.start_day = new_start
        period.end_day = new_end
        period.total_days = calc["total_days"]
        period.active_days = calc["active_days"]
        period.ratio = calc["ratio"]

    if "note" in update_data:
        period.note = update_data["note"]

    db.commit()
    return {"success": True, "id": period_id, "ratio": period.ratio}


@router.delete("/periods/{period_id}")
def delete_pro_rata_period(period_id: int, db: Session = Depends(get_db)):
    """일할 기간 삭제"""
    period = db.query(ProRataPeriod).filter(ProRataPeriod.id == period_id).first()
    if not period:
        raise HTTPException(status_code=404, detail="Pro rata period not found")

    db.delete(period)
    db.commit()
    return {"success": True, "deleted_id": period_id}


@router.get("/calculate")
def calculate_pro_rata(
    contract_seq: int = Query(..., description="계약 seq"),
    billing_cycle: str = Query(..., description="정산월 (YYYYMM)"),
    db: Session = Depends(get_db),
):
    """
    일할 비율 계산 (수동 등록 > 자동 계산 우선순위)

    Returns:
        - ratio: 적용할 일할 비율 (1.0 = 일할 계산 불필요)
        - source: "manual" | "auto" | "none"
    """
    # 1. 수동 등록된 기간 확인
    manual_period = (
        db.query(ProRataPeriod)
        .filter(
            ProRataPeriod.contract_seq == contract_seq,
            ProRataPeriod.billing_cycle == billing_cycle,
        )
        .first()
    )
    if manual_period:
        return {
            "contract_seq": contract_seq,
            "billing_cycle": billing_cycle,
            "ratio": manual_period.ratio,
            "source": "manual",
            "details": {
                "start_day": manual_period.start_day,
                "end_day": manual_period.end_day,
                "total_days": manual_period.total_days,
                "active_days": manual_period.active_days,
            },
        }

    # 2. 자동 계산
    auto_result = auto_calculate_pro_rata(db, contract_seq, billing_cycle)
    if auto_result:
        return {
            "contract_seq": contract_seq,
            "billing_cycle": billing_cycle,
            "ratio": auto_result["ratio"],
            "source": "auto",
            "details": auto_result,
        }

    # 3. 일할 계산 불필요 (전체 월)
    year = int(billing_cycle[:4])
    month = int(billing_cycle[4:6])
    total_days = get_days_in_month(year, month)

    return {
        "contract_seq": contract_seq,
        "billing_cycle": billing_cycle,
        "ratio": 1.0,
        "source": "none",
        "details": {
            "total_days": total_days,
            "active_days": total_days,
            "reason": "full_month",
        },
    }


def get_pro_rata_ratio(
    db: Session,
    contract_seq: int,
    billing_cycle: str,
    pro_rata_enabled: bool = True,
    pro_rata_override: str | None = None,
) -> float | None:
    """
    전표 생성 시 일할 비율 조회 (헬퍼 함수)

    Args:
        db: DB 세션
        contract_seq: 계약 seq
        billing_cycle: 정산월
        pro_rata_enabled: 벤더 설정의 일할 계산 활성화 여부
        pro_rata_override: 계약별 일할 계산 오버라이드 (enabled/disabled/None)

    Returns:
        float | None: 일할 비율 (None = 일할 계산 불필요, 1.0과 동일)
    """
    # 계약 오버라이드 확인
    if pro_rata_override == "disabled":
        return None
    if pro_rata_override != "enabled" and not pro_rata_enabled:
        return None

    # 수동 기간 확인
    manual_period = (
        db.query(ProRataPeriod)
        .filter(
            ProRataPeriod.contract_seq == contract_seq,
            ProRataPeriod.billing_cycle == billing_cycle,
        )
        .first()
    )
    if manual_period:
        return manual_period.ratio if manual_period.ratio < 1.0 else None

    # 자동 계산
    auto_result = auto_calculate_pro_rata(db, contract_seq, billing_cycle)
    if auto_result and auto_result["ratio"] < 1.0:
        return auto_result["ratio"]

    return None
