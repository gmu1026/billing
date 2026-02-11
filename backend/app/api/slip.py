"""
전표 생성 및 관리 API
"""

import csv
import io
import uuid
from datetime import date, datetime, timedelta
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models.alibaba import AlibabaBilling, BPCode
from app.models.billing_profile import (
    CompanyBillingProfile,
    ContractBillingProfile,
    Deposit,
    DepositUsage,
    PAYMENT_TYPE_TAX_CODE,
)
from app.models.hb import AccountContractMapping, HBCompany, HBContract, HBVendorAccount
from app.utils import apply_rounding, round_decimal
from app.models.slip import (
    ExchangeRate,
    ExchangeRateDateRule,
    ExchangeRateType,
    RoundingRule,
    SlipConfig,
    SlipRecord,
    SlipSourceType,
)

router = APIRouter(prefix="/api/slip", tags=["slip"])


def _upsert_exchange_rate(db: Session, row: dict) -> bool:
    """환율 row를 upsert하고, 신규 삽입이면 True, 업데이트면 False 반환"""
    rate_date_str = row.get("date")
    if not rate_date_str:
        return False

    rate_date = datetime.strptime(rate_date_str, "%Y-%m-%d").date()
    currency_code = row.get("code", "USD")

    existing = (
        db.query(ExchangeRate)
        .filter(
            ExchangeRate.rate_date == rate_date,
            ExchangeRate.currency_from == currency_code,
            ExchangeRate.currency_to == "KRW",
        )
        .first()
    )

    basic_rate = float(row.get("basic_rate", 0))
    send_rate = float(row.get("send_rate", 0))
    buy_rate = float(row.get("buy_rate", 0))
    sell_rate = float(row.get("sell_rate", 0))

    if existing:
        existing.rate = basic_rate
        existing.basic_rate = basic_rate
        existing.send_rate = send_rate
        existing.buy_rate = buy_rate
        existing.sell_rate = sell_rate
        existing.source = "hb"
        return False
    else:
        db.add(
            ExchangeRate(
                rate_date=rate_date,
                currency_from=currency_code,
                currency_to="KRW",
                rate=basic_rate,
                basic_rate=basic_rate,
                send_rate=send_rate,
                buy_rate=buy_rate,
                sell_rate=sell_rate,
                source="hb",
            )
        )
        return True


class ExchangeRateCreate(BaseModel):
    rate: float
    rate_date: date
    currency_from: str = "USD"
    currency_to: str = "KRW"
    basic_rate: float | None = None
    send_rate: float | None = None
    buy_rate: float | None = None
    sell_rate: float | None = None
    source: str | None = None


@router.post("/exchange-rates")
def create_exchange_rate(data: ExchangeRateCreate, db: Session = Depends(get_db)):
    """환율 등록"""
    # 같은 날짜/통화 쌍이 있으면 업데이트
    existing = (
        db.query(ExchangeRate)
        .filter(
            ExchangeRate.rate_date == data.rate_date,
            ExchangeRate.currency_from == data.currency_from,
            ExchangeRate.currency_to == data.currency_to,
        )
        .first()
    )

    if existing:
        existing.rate = data.rate
        existing.basic_rate = data.basic_rate
        existing.send_rate = data.send_rate
        existing.buy_rate = data.buy_rate
        existing.sell_rate = data.sell_rate
        existing.source = data.source
    else:
        db.add(ExchangeRate(**data.model_dump()))

    db.commit()
    return {"success": True, "rate": data.rate, "date": str(data.rate_date)}


@router.get("/exchange-rates")
def get_exchange_rates(
    year_month: str | None = Query(None, description="YYYYMM 형식"),
    db: Session = Depends(get_db),
):
    """환율 목록 조회"""
    query = db.query(ExchangeRate)

    if year_month:
        # YYYYMM -> 해당 월의 환율
        year = int(year_month[:4])
        month = int(year_month[4:6])
        start_date = date(year, month, 1)
        if month == 12:
            end_date = date(year + 1, 1, 1)
        else:
            end_date = date(year, month + 1, 1)
        query = query.filter(
            ExchangeRate.rate_date >= start_date, ExchangeRate.rate_date < end_date
        )

    rates = query.order_by(ExchangeRate.rate_date.desc()).limit(100).all()

    return [
        {
            "id": r.id,
            "rate": r.rate,
            "basic_rate": r.basic_rate,
            "send_rate": r.send_rate,
            "buy_rate": r.buy_rate,
            "sell_rate": r.sell_rate,
            "rate_date": str(r.rate_date),
            "currency_from": r.currency_from,
            "currency_to": r.currency_to,
            "source": r.source,
        }
        for r in rates
    ]


@router.get("/exchange-rates/latest")
def get_latest_exchange_rate(
    currency_from: str = Query("USD"),
    currency_to: str = Query("KRW"),
    db: Session = Depends(get_db),
):
    """최신 환율 조회"""
    rate = (
        db.query(ExchangeRate)
        .filter(
            ExchangeRate.currency_from == currency_from,
            ExchangeRate.currency_to == currency_to,
        )
        .order_by(ExchangeRate.rate_date.desc())
        .first()
    )

    if not rate:
        return {"found": False, "message": "No exchange rate found"}

    return {
        "found": True,
        "rate": rate.rate,
        "basic_rate": rate.basic_rate,
        "send_rate": rate.send_rate,
        "rate_date": str(rate.rate_date),
        "source": rate.source,
    }


@router.get("/exchange-rates/by-date")
def get_exchange_rate_by_date(
    rate_date: date = Query(..., description="환율 조회 날짜"),
    currency_from: str = Query("USD"),
    currency_to: str = Query("KRW"),
    db: Session = Depends(get_db),
):
    """특정 날짜 환율 조회"""
    rate = (
        db.query(ExchangeRate)
        .filter(
            ExchangeRate.rate_date == rate_date,
            ExchangeRate.currency_from == currency_from,
            ExchangeRate.currency_to == currency_to,
        )
        .first()
    )

    if not rate:
        return {"found": False, "message": f"No exchange rate found for {rate_date}"}

    return {
        "found": True,
        "rate": rate.rate,
        "basic_rate": rate.basic_rate,
        "send_rate": rate.send_rate,
        "rate_date": str(rate.rate_date),
        "source": rate.source,
    }


@router.get("/exchange-rates/calculate-date")
def calculate_rate_date(
    vendor: str = Query("alibaba"),
    slip_type: str = Query(..., description="sales 또는 purchase"),
    document_date: date = Query(..., description="증빙일"),
    billing_cycle: str | None = Query(None, description="정산월 (YYYYMM)"),
    db: Session = Depends(get_db),
):
    """벤더 설정에 따른 환율 적용일 계산"""
    config = db.query(SlipConfig).filter(SlipConfig.vendor == vendor).first()

    # 기본값 설정
    if slip_type == "sales":
        rule = (
            config.exchange_rate_rule_sales if config else ExchangeRateDateRule.DOCUMENT_DATE.value
        )
        rate_type = config.exchange_rate_type_sales if config else ExchangeRateType.SEND_RATE.value
    else:  # purchase
        rule = (
            config.exchange_rate_rule_purchase
            if config
            else ExchangeRateDateRule.DOCUMENT_DATE.value
        )
        rate_type = (
            config.exchange_rate_type_purchase if config else ExchangeRateType.BASIC_RATE.value
        )

    # 환율 적용일 계산
    rate_date = calculate_exchange_rate_date(rule, document_date, billing_cycle)

    # 해당 날짜의 환율 조회
    rate_record = (
        db.query(ExchangeRate)
        .filter(
            ExchangeRate.rate_date == rate_date,
            ExchangeRate.currency_from == "USD",
            ExchangeRate.currency_to == "KRW",
        )
        .first()
    )

    rate_value = None
    if rate_record:
        if rate_type == ExchangeRateType.SEND_RATE.value:
            rate_value = rate_record.send_rate or rate_record.basic_rate
        elif rate_type == ExchangeRateType.BUY_RATE.value:
            rate_value = rate_record.buy_rate or rate_record.basic_rate
        elif rate_type == ExchangeRateType.SELL_RATE.value:
            rate_value = rate_record.sell_rate or rate_record.basic_rate
        else:  # basic_rate
            rate_value = rate_record.basic_rate or rate_record.rate

    return {
        "vendor": vendor,
        "slip_type": slip_type,
        "document_date": str(document_date),
        "billing_cycle": billing_cycle,
        "rule": rule,
        "rate_type": rate_type,
        "rate_date": str(rate_date),
        "rate": rate_value,
        "found": rate_value is not None,
        "source": rate_record.source if rate_record else None,
    }


@router.get("/exchange-rates/first-of-month")
def get_first_of_month_rate(
    year_month: str = Query(..., description="YYYYMM 형식"),
    currency_from: str = Query("USD"),
    currency_to: str = Query("KRW"),
    db: Session = Depends(get_db),
):
    """월 1일자 환율 조회 (해외 매출/청구용)"""
    year = int(year_month[:4])
    month = int(year_month[4:6])
    first_day = date(year, month, 1)

    rate = (
        db.query(ExchangeRate)
        .filter(
            ExchangeRate.rate_date == first_day,
            ExchangeRate.currency_from == currency_from,
            ExchangeRate.currency_to == currency_to,
        )
        .first()
    )

    if not rate:
        return {"found": False, "message": f"No exchange rate found for {first_day}"}

    return {
        "found": True,
        "basic_rate": rate.basic_rate,
        "send_rate": rate.send_rate,
        "rate_date": str(rate.rate_date),
        "source": rate.source,
    }


@router.post("/exchange-rates/import-json")
def import_exchange_rates_from_json(db: Session = Depends(get_db)):
    """JSON 파일에서 HB 환율 데이터 가져오기"""
    import json
    import os

    json_path = os.path.join(os.path.dirname(__file__), "../../data/import/hb/hb_exchange.json")

    if not os.path.exists(json_path):
        raise HTTPException(status_code=404, detail="Exchange rate JSON file not found")

    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # JSON 구조: data.data.rows[]
    rows = data.get("data", {}).get("data", {}).get("rows", [])
    if not rows:
        raise HTTPException(status_code=400, detail="No exchange rate data in JSON")

    imported = 0
    updated = 0

    for row in rows:
        is_new = _upsert_exchange_rate(db, row)
        if row.get("date"):
            if is_new:
                imported += 1
            else:
                updated += 1

    db.commit()

    return {
        "success": True,
        "imported": imported,
        "updated": updated,
        "total_processed": len(rows),
    }


class HBExchangeSyncRequest(BaseModel):
    cookie: str | None = None  # connect.sid 쿠키 (없으면 기본값 사용)
    limit: int = 31  # 가져올 일수


@router.post("/exchange-rates/sync-hb")
def sync_exchange_rates_from_hb(
    data: HBExchangeSyncRequest,
    db: Session = Depends(get_db),
):
    """HB API에서 환율 데이터 직접 동기화"""
    import requests

    HB_API_URL = "https://alibabacloud.hyperbilling.kr/admin/api/v1/ccy/exchangerate"
    DEFAULT_COOKIE = "connect.sid=s%3AF6rpskNNDIRY7bSFJtOI17WKw6sJP_88.io0TefWAC56UJEXNIM51lg1%2BWTbZagMP6HPNzqtpQAw"

    params = {
        "page": 1,
        "sort": "-date",
        "limit": data.limit,
        "withCountAll": "true",
        "code": "USD",
    }
    headers = {
        "Cookie": data.cookie or DEFAULT_COOKIE,
    }

    try:
        response = requests.get(HB_API_URL, params=params, headers=headers, timeout=30)
        response.raise_for_status()
        api_data = response.json()
    except requests.RequestException as e:
        raise HTTPException(status_code=502, detail=f"HB API 요청 실패: {str(e)}")

    # API 응답 구조: data.rows[] 또는 data.data.rows[]
    rows = []
    if api_data.get("success"):
        inner_data = api_data.get("data", {})
        if isinstance(inner_data, dict) and "rows" in inner_data:
            rows = inner_data.get("rows", [])
        elif isinstance(inner_data, dict) and "data" in inner_data:
            rows = inner_data.get("data", {}).get("rows", [])

    if not rows:
        raise HTTPException(status_code=400, detail="No exchange rate data from HB API")

    imported = 0
    updated = 0

    for row in rows:
        is_new = _upsert_exchange_rate(db, row)
        if row.get("date"):
            if is_new:
                imported += 1
            else:
                updated += 1

    db.commit()

    return {
        "success": True,
        "imported": imported,
        "updated": updated,
        "total_processed": len(rows),
    }


def calculate_exchange_rate_date(
    rule: str,
    document_date: date,
    billing_cycle: str | None = None,
) -> date:
    """환율 규칙에 따라 환율 적용일 계산"""
    if rule == ExchangeRateDateRule.DOCUMENT_DATE.value:
        return document_date

    elif rule == ExchangeRateDateRule.FIRST_OF_DOCUMENT_MONTH.value:
        # 증빙일이 속한 월의 1일
        return date(document_date.year, document_date.month, 1)

    elif rule == ExchangeRateDateRule.FIRST_OF_DOCUMENT_MONTH.value:
        # 정산월 1일
        if billing_cycle:
            year = int(billing_cycle[:4])
            month = int(billing_cycle[4:6])
            return date(year, month, 1)
        # billing_cycle 없으면 증빙일 월 1일
        return date(document_date.year, document_date.month, 1)

    elif rule == ExchangeRateDateRule.LAST_OF_PREV_MONTH.value:
        # 증빙일 기준 전월 말일
        first_of_month = date(document_date.year, document_date.month, 1)
        from datetime import timedelta

        return first_of_month - timedelta(days=1)

    else:  # custom 또는 기타
        return document_date


def _sync_exchange_rates_from_hb_internal(db: Session, limit: int = 50) -> int:
    """HB API에서 환율 데이터 동기화 (내부 헬퍼)"""
    import requests

    HB_API_URL = "https://alibabacloud.hyperbilling.kr/admin/api/v1/ccy/exchangerate"
    DEFAULT_COOKIE = "connect.sid=s%3AF6rpskNNDIRY7bSFJtOI17WKw6sJP_88.io0TefWAC56UJEXNIM51lg1%2BWTbZagMP6HPNzqtpQAw"

    params = {
        "page": 1,
        "sort": "-date",
        "limit": limit,
        "withCountAll": "true",
        "code": "USD",
    }
    headers = {"Cookie": DEFAULT_COOKIE}

    try:
        response = requests.get(HB_API_URL, params=params, headers=headers, timeout=30)
        response.raise_for_status()
        api_data = response.json()
    except Exception:
        return 0

    rows = []
    if api_data.get("success"):
        inner_data = api_data.get("data", {})
        if isinstance(inner_data, dict) and "rows" in inner_data:
            rows = inner_data.get("rows", [])
        elif isinstance(inner_data, dict) and "data" in inner_data:
            rows = inner_data.get("data", {}).get("rows", [])

    if not rows:
        return 0

    for row in rows:
        _upsert_exchange_rate(db, row)

    db.commit()
    return len(rows)


def _get_exchange_rate_for_slip(
    db: Session,
    document_date: date,
    slip_type: str,
    is_overseas: bool = False,
    currency_from: str = "USD",
) -> dict:
    """
    전표 유형에 따른 환율 자동 조회

    환율 사용 규칙:
    - 해외 매출/청구: 월 1일자 basic_rate (원화 환산)
    - 원화 해외 (KRW가 아닌 경우): 증빙일자 basic_rate
    - 매출: 증빙일자 send_rate

    Returns:
        {"rate": float, "rate_type": str, "rate_date": date}
    """
    # 1. 해외법인: 증빙월 1일자 매매기준율 (basic_rate)
    if is_overseas:
        first_day = date(document_date.year, document_date.month, 1)
        rate_record = (
            db.query(ExchangeRate)
            .filter(
                ExchangeRate.rate_date == first_day,
                ExchangeRate.currency_from == currency_from,
                ExchangeRate.currency_to == "KRW",
            )
            .first()
        )

        if rate_record and rate_record.basic_rate:
            return {
                "rate": rate_record.basic_rate,
                "rate_type": "basic_rate",
                "rate_date": first_day,
            }

    # 2. 매출전표: 증빙일자 send_rate
    if slip_type == "sales":
        rate_record = (
            db.query(ExchangeRate)
            .filter(
                ExchangeRate.rate_date == document_date,
                ExchangeRate.currency_from == currency_from,
                ExchangeRate.currency_to == "KRW",
            )
            .first()
        )

        if rate_record and rate_record.send_rate:
            return {
                "rate": rate_record.send_rate,
                "rate_type": "send_rate",
                "rate_date": document_date,
            }

    # 3. 매입/원가전표 또는 fallback: 증빙일자 basic_rate
    rate_record = (
        db.query(ExchangeRate)
        .filter(
            ExchangeRate.rate_date == document_date,
            ExchangeRate.currency_from == currency_from,
            ExchangeRate.currency_to == "KRW",
        )
        .first()
    )

    if rate_record:
        return {
            "rate": rate_record.basic_rate or rate_record.rate,
            "rate_type": "basic_rate",
            "rate_date": document_date,
        }

    return {"rate": None, "rate_type": None, "rate_date": None}


def _ensure_exchange_rate(
    db: Session,
    document_date: date,
    slip_type: str,
    is_overseas: bool = False,
) -> dict:
    """
    환율 조회, 없으면 HB API에서 가져온 후 재조회

    Returns:
        {"rate": float, "rate_type": str, "rate_date": date, "synced": bool}
    """
    result = _get_exchange_rate_for_slip(db, document_date, slip_type, is_overseas)

    if result["rate"] is None:
        # 환율 데이터 없음 -> HB API에서 동기화
        synced = _sync_exchange_rates_from_hb_internal(db, limit=50)
        if synced > 0:
            result = _get_exchange_rate_for_slip(db, document_date, slip_type, is_overseas)
            result["synced"] = True
        else:
            result["synced"] = False
    else:
        result["synced"] = False

    return result


@router.get("/config/{vendor}")
def get_slip_config(vendor: str, db: Session = Depends(get_db)):
    """벤더별 전표 설정 조회"""
    config = db.query(SlipConfig).filter(SlipConfig.vendor == vendor).first()

    if not config:
        # 기본값 반환
        return {
            "vendor": vendor,
            "bukrs": "1100",
            "prctr": "10000003",
            "hkont_sales": "41021010",
            "hkont_sales_export": "41021020",
            "hkont_purchase": "42021010",
            "ar_account_default": "11060110",
            "ap_account_default": "21120110",
            "zzref2": "IBABA001",
            "sgtxt_template": "Alibaba_Cloud_{MM}월_{TYPE}",
            "rounding_rule": RoundingRule.FLOOR.value,
            # 환율 규칙 기본값
            "exchange_rate_rule_sales": ExchangeRateDateRule.DOCUMENT_DATE.value,
            "exchange_rate_type_sales": ExchangeRateType.SEND_RATE.value,
            "exchange_rate_rule_purchase": ExchangeRateDateRule.DOCUMENT_DATE.value,
            "exchange_rate_type_purchase": ExchangeRateType.BASIC_RATE.value,
            "exchange_rate_rule_overseas": ExchangeRateDateRule.FIRST_OF_DOCUMENT_MONTH.value,
            "exchange_rate_type_overseas": ExchangeRateType.BASIC_RATE.value,
        }

    return {
        "vendor": config.vendor,
        "bukrs": config.bukrs,
        "prctr": config.prctr,
        "hkont_sales": config.hkont_sales,
        "hkont_sales_export": config.hkont_sales_export,
        "hkont_purchase": config.hkont_purchase,
        "ar_account_default": config.ar_account_default,
        "ap_account_default": config.ap_account_default,
        "zzref2": config.zzref2,
        "sgtxt_template": config.sgtxt_template,
        "rounding_rule": config.rounding_rule,
        # 환율 규칙
        "exchange_rate_rule_sales": config.exchange_rate_rule_sales
        or ExchangeRateDateRule.DOCUMENT_DATE.value,
        "exchange_rate_type_sales": config.exchange_rate_type_sales
        or ExchangeRateType.SEND_RATE.value,
        "exchange_rate_rule_purchase": config.exchange_rate_rule_purchase
        or ExchangeRateDateRule.DOCUMENT_DATE.value,
        "exchange_rate_type_purchase": config.exchange_rate_type_purchase
        or ExchangeRateType.BASIC_RATE.value,
        "exchange_rate_rule_overseas": config.exchange_rate_rule_overseas
        or ExchangeRateDateRule.FIRST_OF_DOCUMENT_MONTH.value,
        "exchange_rate_type_overseas": config.exchange_rate_type_overseas
        or ExchangeRateType.BASIC_RATE.value,
    }


class SlipConfigUpdate(BaseModel):
    bukrs: str | None = None
    prctr: str | None = None
    hkont_sales: str | None = None
    hkont_sales_export: str | None = None
    hkont_purchase: str | None = None
    ar_account_default: str | None = None
    ap_account_default: str | None = None
    zzref2: str | None = None
    sgtxt_template: str | None = None
    rounding_rule: str | None = None
    # 환율 규칙
    exchange_rate_rule_sales: str | None = None
    exchange_rate_type_sales: str | None = None
    exchange_rate_rule_purchase: str | None = None
    exchange_rate_type_purchase: str | None = None
    exchange_rate_rule_overseas: str | None = None
    exchange_rate_type_overseas: str | None = None


@router.put("/config/{vendor}")
def update_slip_config(vendor: str, data: SlipConfigUpdate, db: Session = Depends(get_db)):
    """벤더별 전표 설정 업데이트"""
    config = db.query(SlipConfig).filter(SlipConfig.vendor == vendor).first()

    if not config:
        config = SlipConfig(vendor=vendor)
        db.add(config)

    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(config, key, value)

    db.commit()
    return {"success": True, "vendor": vendor}


class SlipGenerateRequest(BaseModel):
    billing_cycle: str  # YYYYMM
    slip_type: Literal["sales", "purchase"]  # sales=매출(enduser), purchase=매입(reseller)
    document_date: date  # 증빙일/전기일
    exchange_rate: float | None = None  # 환율 (없으면 자동 조회)
    overseas_exchange_rate: float | None = (
        None  # 해외법인 원화환산 환율 (수동 지정, 없으면 증빙월 1일 매매기준율)
    )
    invoice_number: str | None = None  # 인보이스 번호 (수기)
    auto_exchange_rate: bool = True  # 환율 자동 조회 여부
    include_additional_charges: bool = True  # 추가 비용 포함 여부
    apply_pro_rata: bool = True  # 일할 계산 적용 여부
    apply_split_billing: bool = True  # 분할 청구 적용 여부
    overseas_exchange_rate_input: float | None = None  # 해외 인보이스 기본 환율 (계약별 설정 없을 때 사용)


@router.post("/generate")
def generate_slips(data: SlipGenerateRequest, db: Session = Depends(get_db)):
    """
    전표 생성

    1. 빌링 데이터에서 UID별 금액 합산
    2. UID → Contract → Company → BP 정보 조회
    3. 전표 레코드 생성
    """
    billing_type = "enduser" if data.slip_type == "sales" else "reseller"
    batch_id = str(uuid.uuid4())[:8]

    # 전표 설정 조회 (없으면 기본값으로 생성 및 저장)
    config = db.query(SlipConfig).filter(SlipConfig.vendor == "alibaba").first()
    if not config:
        config = SlipConfig(
            vendor="alibaba",
            bukrs="1100",
            prctr="10000003",
            hkont_sales="41021010",
            hkont_sales_export="41021020",
            hkont_purchase="42021010",
            ar_account_default="11060110",
            ap_account_default="21120110",
            zzref2="IBABA001",
            sgtxt_template="Alibaba_Cloud_{MM}월_{TYPE}",
            rounding_rule=RoundingRule.FLOOR.value,
        )
        db.add(config)
        db.commit()

    # 벤더별 라운딩 규칙
    rounding_rule = config.rounding_rule or RoundingRule.FLOOR.value

    # 빌링 데이터 UID별 합산
    if billing_type == "reseller":
        # Reseller: linked_user_id 기준
        billing_summary = (
            db.query(
                AlibabaBilling.linked_user_id.label("uid"),
                func.sum(AlibabaBilling.calculated_amount).label("total_amount"),
            )
            .filter(
                AlibabaBilling.billing_type == "reseller",
                AlibabaBilling.billing_cycle == data.billing_cycle,
            )
            .group_by(AlibabaBilling.linked_user_id)
            .all()
        )
    else:
        # Enduser: user_id 기준
        billing_summary = (
            db.query(
                AlibabaBilling.user_id.label("uid"),
                func.sum(AlibabaBilling.calculated_amount).label("total_amount"),
            )
            .filter(
                AlibabaBilling.billing_type == "enduser",
                AlibabaBilling.billing_cycle == data.billing_cycle,
            )
            .group_by(AlibabaBilling.user_id)
            .all()
        )

    if not billing_summary:
        raise HTTPException(
            status_code=404,
            detail=f"No billing data found for {data.billing_cycle} ({billing_type})",
        )

    # 환율 자동 조회 (국내용 기본 환율)
    exchange_rate_info = None
    exchange_rate_synced = False
    domestic_exchange_rate = data.exchange_rate  # 사용자 지정 환율

    if data.auto_exchange_rate and not domestic_exchange_rate:
        # 국내용: 매출=send_rate, 매입=basic_rate
        exchange_rate_info = _ensure_exchange_rate(
            db, data.document_date, data.slip_type, is_overseas=False
        )
        if exchange_rate_info["rate"]:
            domestic_exchange_rate = exchange_rate_info["rate"]
            exchange_rate_synced = exchange_rate_info.get("synced", False)

    # 해외용 환율 (증빙월 1일자 매매기준율)
    overseas_exchange_rate = data.overseas_exchange_rate  # 수동 지정
    overseas_rate_info = None
    if not overseas_exchange_rate and data.auto_exchange_rate:
        overseas_rate_info = _ensure_exchange_rate(
            db, data.document_date, data.slip_type, is_overseas=True
        )
        if overseas_rate_info["rate"]:
            overseas_exchange_rate = overseas_rate_info["rate"]

    # 적요 생성
    month = data.billing_cycle[4:6]
    type_text = "매출" if data.slip_type == "sales" else "매입"
    sgtxt = config.sgtxt_template.replace("{MM}", month).replace("{TYPE}", type_text)

    slips_created = []
    slips_no_mapping = []
    internal_cost_list = []  # 내부비용 별도 집계
    overseas_slips = []  # 해외법인 전표 별도 집계
    seqno = 1

    for billing in billing_summary:
        uid = billing.uid
        # 소수점 2자리 반올림 (ROUND_HALF_UP)
        amount_usd = round_decimal(float(billing.total_amount or 0), 2)

        if amount_usd <= 0:
            continue

        # KRW 변환 (라운딩 규칙 적용, 환율 없으면 그대로 KRW로 사용)
        if domestic_exchange_rate and domestic_exchange_rate > 0:
            amount_krw = apply_rounding(amount_usd * domestic_exchange_rate, rounding_rule)
        else:
            # 환율 없으면 USD 금액을 그대로 KRW로 사용
            amount_krw = apply_rounding(amount_usd, rounding_rule)

        # UID로 계약/회사 정보 조회
        account = (
            db.query(HBVendorAccount)
            .options(
                joinedload(HBVendorAccount.contract_mappings)
                .joinedload(AccountContractMapping.contract)
                .joinedload(HBContract.company)
            )
            .filter(HBVendorAccount.id == uid)
            .first()
        )

        # 계약 정보 (첫 번째 활성 계약 사용)
        contract = None
        company = None
        bp_number = None

        if account and account.contract_mappings:
            for mapping in account.contract_mappings:
                if mapping.contract and mapping.contract.enabled:
                    contract = mapping.contract
                    company = contract.company
                    break

        if company:
            bp_number = company.bp_number

        # BP 자동 매핑 (국내/해외 공통 - bp_number가 없는 경우)
        if not bp_number and company:
            if company.license:
                matched_bp = db.query(BPCode).filter(BPCode.tax_number == company.license).first()
                if matched_bp:
                    bp_number = matched_bp.bp_number
                    company.bp_number = bp_number

            if not bp_number and company.name:
                matched_bp = (
                    db.query(BPCode)
                    .filter(
                        (BPCode.name_local == company.name) | (BPCode.name_english == company.name)
                    )
                    .first()
                )
                if matched_bp:
                    bp_number = matched_bp.bp_number
                    company.bp_number = bp_number

        # 내부비용 체크
        is_internal = company.is_internal_cost if company else False

        if is_internal:
            # 내부비용인 경우
            internal_cost_list.append(
                {
                    "uid": uid,
                    "amount_usd": round(amount_usd, 2),
                    "amount_krw": amount_krw,
                    "company_name": company.name if company else None,
                    "contract_name": contract.name if contract else None,
                }
            )
            # 매출전표: 완전 제외
            # 매입전표: 전표에는 안넣지만 집계만 함
            continue

        # 해외법인 여부 및 통화 결정
        is_overseas = company.is_overseas if company else False
        slip_currency = "KRW"  # 기본값
        slip_amount = amount_krw  # 기본값: KRW 환산액
        slip_amount_krw = amount_krw  # 원화환산액 (DMBTR_C)
        applied_exchange_rate = domestic_exchange_rate  # 적용된 환율

        if is_overseas and company:
            # 해외법인: 통화금액(WRBTR)은 USD, 원화환산액(DMBTR_C)은 계약별 환율 결정 후 계산
            slip_currency = "USD"  # 해외법인은 무조건 USD
            slip_amount = apply_rounding(amount_usd, rounding_rule, decimals=2)  # USD 금액 (소수점 2자리)
            slip_amount_krw = None  # 원화환산액은 청구 프로필 로딩 후 계산

        # 청구 프로필 조회 (우선순위: 계약별 > 회사별)
        contract_billing_profile = None
        company_billing_profile = None
        effective_rounding_rule = rounding_rule  # 기본값

        # 1. 계약별 청구 프로필 조회
        if contract:
            contract_billing_profile = (
                db.query(ContractBillingProfile)
                .filter(
                    ContractBillingProfile.contract_seq == contract.seq,
                    ContractBillingProfile.vendor == "alibaba",
                )
                .first()
            )
            # 계약 프로필의 라운딩 오버라이드 적용
            if contract_billing_profile and contract_billing_profile.rounding_rule_override:
                effective_rounding_rule = contract_billing_profile.rounding_rule_override

        # 2. 회사별 청구 프로필 조회 (계약별 프로필이 없는 경우)
        if not contract_billing_profile and company:
            company_billing_profile = (
                db.query(CompanyBillingProfile)
                .filter(
                    CompanyBillingProfile.company_seq == company.seq,
                    CompanyBillingProfile.vendor == "alibaba",
                )
                .first()
            )

        # 유효한 청구 프로필 (계약별 우선)
        billing_profile = contract_billing_profile or company_billing_profile

        # 해외법인 계약별 환율 결정
        # 우선순위: 1) 계약별 프로필 환율 설정 → 2) 슬립 생성 시 지정 해외 환율 → 3) 글로벌 해외 환율
        if is_overseas:
            effective_overseas_rate = None  # 아직 미결정

            # 1. 계약별 청구 프로필 환율 설정 확인
            if contract_billing_profile and (
                contract_billing_profile.exchange_rate_type or contract_billing_profile.custom_exchange_rate_date
            ):
                rate_lookup_date = contract_billing_profile.custom_exchange_rate_date
                if not rate_lookup_date and contract_billing_profile.exchange_rate_type:
                    rule = contract_billing_profile.exchange_rate_type
                    if rule == "document_date":
                        rate_lookup_date = data.document_date
                    elif rule == "first_of_document_month":
                        rate_lookup_date = data.document_date.replace(day=1)
                    elif rule == "first_of_billing_month":
                        year = int(data.billing_cycle[:4])
                        month = int(data.billing_cycle[4:6])
                        rate_lookup_date = date(year, month, 1)
                    elif rule == "last_of_prev_month":
                        rate_lookup_date = data.document_date.replace(day=1) - timedelta(days=1)
                    else:
                        rate_lookup_date = data.document_date

                if rate_lookup_date:
                    contract_rate_record = (
                        db.query(ExchangeRate)
                        .filter(
                            ExchangeRate.rate_date == rate_lookup_date,
                            ExchangeRate.currency_from == "USD",
                            ExchangeRate.currency_to == "KRW",
                        )
                        .first()
                    )
                    if contract_rate_record:
                        rate_val = contract_rate_record.basic_rate or contract_rate_record.rate
                        if rate_val:
                            effective_overseas_rate = float(rate_val)

            # 2. 계약별 환율 없으면 슬립 생성 시 지정한 해외 환율 사용
            if effective_overseas_rate is None and data.overseas_exchange_rate_input:
                effective_overseas_rate = data.overseas_exchange_rate_input

            # 3. 그것도 없으면 글로벌 해외 환율 사용
            if effective_overseas_rate is None:
                effective_overseas_rate = overseas_exchange_rate

            # 원화환산액 계산 (effective_overseas_rate 사용, 반올림 적용)
            if effective_overseas_rate and effective_overseas_rate > 0:
                # 해외 인보이스 원화환산은 반올림 적용 (소수점 없이)
                slip_amount_krw = apply_rounding(
                    amount_usd * effective_overseas_rate, "round_half_up"
                )
                applied_exchange_rate = effective_overseas_rate
            else:
                slip_amount_krw = None  # 환율 없으면 원화환산액 없음
        else:
            effective_overseas_rate = overseas_exchange_rate  # 국내는 해외 환율 불필요

        # 해외 예치금 FIFO 환율 적용
        # 계약별 청구 프로필이 있고, 해외법인(non-KRW)이고, USD 금액이 있는 경우
        if is_overseas and contract_billing_profile and amount_usd > 0:
            available_deposits = (
                db.query(Deposit)
                .filter(
                    Deposit.contract_profile_id == contract_billing_profile.id,
                    Deposit.is_exhausted == False,
                    Deposit.currency != "KRW",
                )
                .order_by(Deposit.deposit_date)
                .all()
            )

            if available_deposits:
                remaining_usd = amount_usd
                fifo_krw = 0.0

                for dep in available_deposits:
                    if remaining_usd <= 0:
                        break

                    use = min(remaining_usd, dep.remaining_amount)
                    rate = dep.exchange_rate if dep.exchange_rate else (effective_overseas_rate or 0)
                    # 해외 인보이스 원화환산은 반올림 적용
                    portion_krw = float(apply_rounding(use * rate, "round_half_up"))
                    fifo_krw += portion_krw

                    # 잔액 차감 및 소진 처리
                    dep.remaining_amount -= use
                    if dep.remaining_amount <= 0:
                        dep.remaining_amount = 0
                        dep.is_exhausted = True

                    # 사용 기록 생성 (배치 ID 연결)
                    db.add(
                        DepositUsage(
                            deposit_id=dep.id,
                            usage_date=data.document_date,
                            amount=use,
                            amount_krw=int(portion_krw),
                            billing_cycle=data.billing_cycle,
                            slip_batch_id=batch_id,
                            uid=uid,
                            description=f"전표 생성 ({data.billing_cycle})",
                        )
                    )

                    remaining_usd -= use

                # 예치금 부족분은 계약별 유효 환율로 원화 환산 (반올림 적용)
                if remaining_usd > 0:
                    fallback_rate = effective_overseas_rate or 0
                    fifo_krw += float(
                        apply_rounding(remaining_usd * fallback_rate, "round_half_up")
                    )

                slip_amount_krw = int(fifo_krw)

        # 계정코드 결정 (우선순위: 청구프로필 > BP코드 > 해외법인수출 > 기본값)
        ar_account = (
            config.ar_account_default if data.slip_type == "sales" else config.ap_account_default
        )

        # 해외법인인 경우 수출 계정코드 사용
        if is_overseas and data.slip_type == "sales":
            hkont = config.hkont_sales_export or "41021020"
        else:
            hkont = config.hkont_sales if data.slip_type == "sales" else config.hkont_purchase

        # 1. 청구 프로필에 계정코드가 있으면 사용 (해외법인도 프로필 우선)
        if billing_profile:
            if data.slip_type == "sales":
                if billing_profile.ar_account:
                    ar_account = billing_profile.ar_account
                if billing_profile.hkont_sales:
                    hkont = billing_profile.hkont_sales
            else:
                if billing_profile.ap_account:
                    ar_account = billing_profile.ap_account
                if billing_profile.hkont_purchase:
                    hkont = billing_profile.hkont_purchase

        # 2. BP 코드에 계정코드가 있으면 사용 (청구프로필 없는 경우)
        if bp_number and not billing_profile:
            bp = db.query(BPCode).filter(BPCode.bp_number == bp_number).first()
            if bp:
                if data.slip_type == "sales" and bp.ar_account:
                    ar_account = bp.ar_account
                elif data.slip_type == "purchase" and bp.ap_account:
                    ar_account = bp.ap_account

        # 라운딩 규칙 적용 (계약 프로필 오버라이드가 있으면 다시 계산)
        if contract_billing_profile and contract_billing_profile.rounding_rule_override:
            if data.exchange_rate and data.exchange_rate > 0:
                amount_krw = apply_rounding(
                    amount_usd * data.exchange_rate, effective_rounding_rule
                )
            else:
                amount_krw = apply_rounding(amount_usd, effective_rounding_rule)

            if is_overseas and company:
                slip_amount = apply_rounding(amount_usd, effective_rounding_rule)
            else:
                slip_amount = amount_krw

        # 계약번호 (없으면 기본값 사용)
        sales_contract = (
            contract.sales_contract_code
            if contract and contract.sales_contract_code
            else "매출ALI999"
        )
        purchase_contract = (
            sales_contract.replace("매출", "매입") if "매출" in sales_contract else "매입ALI999"
        )

        # 부가세코드 (결제 방식에 따라 결정)
        tax_code = "A1"  # 기본값
        if billing_profile and billing_profile.payment_type:
            tax_code = PAYMENT_TYPE_TAX_CODE.get(billing_profile.payment_type, "A1")

        split_applied = False
        split_slips_info = []

        if data.apply_split_billing:
            split_result = _calculate_split_amounts(db, uid, amount_usd, data.billing_cycle)
            if split_result and split_result["allocations"]:
                split_applied = True
                # 분할 대상별 전표 생성
                for alloc in split_result["allocations"]:
                    alloc_amount_usd = alloc["allocated_amount_usd"]
                    if alloc_amount_usd <= 0:
                        continue

                    # 배분 대상 회사 정보 조회
                    target_company = (
                        db.query(HBCompany)
                        .filter(HBCompany.seq == alloc["target_company_seq"])
                        .first()
                    )
                    target_bp = alloc["target_company_bp"]

                    # 일할 계산 적용 (분할 후 금액에 적용)
                    final_amount_usd = alloc_amount_usd
                    pro_rata_applied = None
                    original_usd = None

                    if data.apply_pro_rata and contract:
                        pro_rata_ratio = _get_pro_rata_ratio(
                            db, contract.seq, data.billing_cycle, config, contract_billing_profile
                        )
                        if pro_rata_ratio and pro_rata_ratio < 1.0:
                            original_usd = final_amount_usd
                            final_amount_usd = round_decimal(final_amount_usd * pro_rata_ratio, 2)
                            pro_rata_applied = pro_rata_ratio

                    # KRW 변환
                    target_is_overseas = target_company.is_overseas if target_company else False
                    if target_is_overseas:
                        # 해외법인 원화환산은 반올림 적용
                        final_amount_krw = apply_rounding(
                            final_amount_usd * (effective_overseas_rate or 1),
                            "round_half_up",
                        )
                        final_slip_currency = "USD"  # 해외법인은 무조건 USD
                        final_dmbtr_c = final_amount_krw
                        final_wrbtr = apply_rounding(
                            final_amount_usd, effective_rounding_rule, decimals=2
                        )  # 외화 소수점 2자리
                    else:
                        final_amount_krw = apply_rounding(
                            final_amount_usd * (domestic_exchange_rate or 1),
                            effective_rounding_rule,
                        )
                        final_slip_currency = "KRW"
                        final_dmbtr_c = None
                        final_wrbtr = final_amount_krw

                    # 분할 전표 생성
                    split_slip = SlipRecord(
                        batch_id=batch_id,
                        slip_type=data.slip_type,
                        vendor="alibaba",
                        billing_cycle=data.billing_cycle,
                        source_type=SlipSourceType.SPLIT.value,
                        seqno=seqno,
                        bukrs=config.bukrs,
                        bldat=data.document_date,
                        budat=data.document_date,
                        waers=final_slip_currency,
                        sgtxt=sgtxt,
                        partner=target_bp,
                        partner_name=target_company.name if target_company else None,
                        ar_account=ar_account,
                        hkont=config.hkont_sales_export if target_is_overseas else hkont,
                        tax_code=tax_code,
                        wrbtr=final_wrbtr,
                        wrbtr_usd=final_amount_usd,
                        dmbtr_c=final_dmbtr_c,
                        exchange_rate=effective_overseas_rate
                        if target_is_overseas
                        else domestic_exchange_rate,
                        prctr=config.prctr,
                        zzcon=target_bp,
                        zzsconid=sales_contract,
                        zzpconid=purchase_contract,
                        zzsempnm=contract.sales_person if contract else None,
                        zzref2=config.zzref2,
                        zzinvno=data.invoice_number,
                        uid=uid,
                        contract_seq=contract.seq if contract else None,
                        company_seq=alloc["target_company_seq"],
                        split_rule_id=split_result["rule_id"],
                        split_allocation_id=alloc["allocation_id"],
                        pro_rata_ratio=pro_rata_applied,
                        original_amount=original_usd,
                    )
                    db.add(split_slip)
                    seqno += 1

                    split_slips_info.append(
                        {
                            "target_company": alloc["target_company_name"],
                            "amount_usd": final_amount_usd,
                            "bp_number": target_bp,
                        }
                    )

                    if not target_bp:
                        slips_no_mapping.append(
                            {
                                "uid": uid,
                                "amount_usd": round(final_amount_usd, 2),
                                "amount_krw": final_amount_krw,
                                "account_name": account.name if account else None,
                                "contract_name": contract.name if contract else None,
                                "company_name": target_company.name if target_company else None,
                                "split": True,
                            }
                        )
                    else:
                        slips_created.append(
                            {
                                "seqno": seqno - 1,
                                "uid": uid,
                                "bp_number": target_bp,
                                "amount_krw": final_amount_krw,
                                "split": True,
                            }
                        )

        # 분할 적용되지 않은 경우 기존 로직 실행
        if not split_applied:
            pro_rata_applied = None
            original_amount_usd = None

            if data.apply_pro_rata and contract:
                pro_rata_ratio = _get_pro_rata_ratio(
                    db, contract.seq, data.billing_cycle, config, contract_billing_profile
                )
                if pro_rata_ratio and pro_rata_ratio < 1.0:
                    original_amount_usd = amount_usd
                    amount_usd = round_decimal(amount_usd * pro_rata_ratio, 2)
                    pro_rata_applied = pro_rata_ratio

                    # KRW 재계산
                    if domestic_exchange_rate and domestic_exchange_rate > 0:
                        amount_krw = apply_rounding(
                            amount_usd * domestic_exchange_rate, effective_rounding_rule
                        )
                    else:
                        amount_krw = apply_rounding(amount_usd, effective_rounding_rule)

                    if is_overseas:
                        slip_amount = apply_rounding(amount_usd, effective_rounding_rule, decimals=2)
                        if effective_overseas_rate and effective_overseas_rate > 0:
                            # 해외 인보이스 원화환산은 반올림 적용
                            slip_amount_krw = apply_rounding(
                                amount_usd * effective_overseas_rate, "round_half_up"
                            )
                    else:
                        slip_amount = amount_krw

            # 전표 레코드 생성
            slip = SlipRecord(
                batch_id=batch_id,
                slip_type=data.slip_type,
                vendor="alibaba",
                billing_cycle=data.billing_cycle,
                source_type=SlipSourceType.BILLING.value,
                seqno=seqno,
                bukrs=config.bukrs,
                bldat=data.document_date,
                budat=data.document_date,
                waers=slip_currency,
                sgtxt=sgtxt,
                partner=bp_number,
                partner_name=company.name if company else None,
                ar_account=ar_account,
                hkont=hkont,
                tax_code=tax_code,
                wrbtr=slip_amount,
                wrbtr_usd=amount_usd,
                dmbtr_c=slip_amount_krw if is_overseas else None,
                exchange_rate=applied_exchange_rate,
                prctr=config.prctr,
                zzcon=bp_number,
                zzsconid=sales_contract,
                zzpconid=purchase_contract,
                zzsempnm=contract.sales_person if contract else None,
                zzref2=config.zzref2,
                zzinvno=data.invoice_number,
                uid=uid,
                contract_seq=contract.seq if contract else None,
                company_seq=company.seq if company else None,
                pro_rata_ratio=pro_rata_applied,
                original_amount=original_amount_usd,
            )

            db.add(slip)
            seqno += 1

            if not bp_number:
                slips_no_mapping.append(
                    {
                        "uid": uid,
                        "amount_usd": round(amount_usd, 2),
                        "amount_krw": amount_krw,
                        "account_name": account.name if account else None,
                        "contract_name": contract.name if contract else None,
                        "company_name": company.name if company else None,
                    }
                )
            else:
                slips_created.append(
                    {
                        "seqno": seqno - 1,
                        "uid": uid,
                        "bp_number": bp_number,
                        "amount_krw": amount_krw,
                    }
                )

        # 해외법인 별도 집계
        if is_overseas and not split_applied:
            overseas_slips.append(
                {
                    "uid": uid,
                    "amount_usd": round(amount_usd, 2),
                    "amount_krw": slip_amount_krw,
                    "exchange_rate": applied_exchange_rate,
                    "currency": slip_currency,
                    "company_name": company.name if company else None,
                }
            )

    additional_charge_slips = []
    if data.include_additional_charges:
        # 해당 정산월에 적용되는 추가 비용 조회 (모든 계약 대상)
        processed_contracts = set()
        for billing in billing_summary:
            uid = billing.uid
            account = (
                db.query(HBVendorAccount)
                .options(
                    joinedload(HBVendorAccount.contract_mappings).joinedload(
                        AccountContractMapping.contract
                    )
                )
                .filter(HBVendorAccount.id == uid)
                .first()
            )

            if not account or not account.contract_mappings:
                continue

            for mapping in account.contract_mappings:
                if not mapping.contract or not mapping.contract.enabled:
                    continue
                contract = mapping.contract
                if contract.seq in processed_contracts:
                    continue
                processed_contracts.add(contract.seq)

                # 해당 계약의 추가 비용 조회
                charges = _get_applicable_additional_charges(
                    db, contract.seq, data.billing_cycle, data.slip_type
                )
                if not charges:
                    continue

                company = contract.company
                for charge in charges:
                    charge_amount_usd = charge.amount
                    if charge_amount_usd == 0:
                        continue

                    # KRW 변환
                    if domestic_exchange_rate and domestic_exchange_rate > 0:
                        charge_amount_krw = apply_rounding(
                            charge_amount_usd * domestic_exchange_rate, rounding_rule
                        )
                    else:
                        charge_amount_krw = apply_rounding(charge_amount_usd, rounding_rule)

                    bp_number = company.bp_number if company else None

                    # 추가 비용 전표 적요
                    charge_sgtxt = f"{sgtxt}_{charge.name}"

                    charge_slip = SlipRecord(
                        batch_id=batch_id,
                        slip_type=data.slip_type,
                        vendor="alibaba",
                        billing_cycle=data.billing_cycle,
                        source_type=SlipSourceType.ADDITIONAL_CHARGE.value,
                        seqno=seqno,
                        bukrs=config.bukrs,
                        bldat=data.document_date,
                        budat=data.document_date,
                        waers="KRW",
                        sgtxt=charge_sgtxt,
                        partner=bp_number,
                        partner_name=company.name if company else None,
                        ar_account=config.ar_account_default
                        if data.slip_type == "sales"
                        else config.ap_account_default,
                        hkont=config.hkont_sales
                        if data.slip_type == "sales"
                        else config.hkont_purchase,
                        tax_code="A1",
                        wrbtr=charge_amount_krw,
                        wrbtr_usd=charge_amount_usd,
                        exchange_rate=domestic_exchange_rate,
                        prctr=config.prctr,
                        zzcon=bp_number,
                        zzsconid=contract.sales_contract_code or "매출ALI999",
                        zzpconid=(contract.sales_contract_code or "매출ALI999").replace(
                            "매출", "매입"
                        ),
                        zzsempnm=contract.sales_person,
                        zzref2=config.zzref2,
                        zzinvno=data.invoice_number,
                        uid=None,
                        contract_seq=contract.seq,
                        company_seq=company.seq if company else None,
                        additional_charge_id=charge.id,
                    )
                    db.add(charge_slip)
                    seqno += 1

                    additional_charge_slips.append(
                        {
                            "charge_name": charge.name,
                            "charge_type": charge.charge_type,
                            "amount_usd": charge_amount_usd,
                            "amount_krw": charge_amount_krw,
                            "company_name": company.name if company else None,
                        }
                    )

    db.commit()

    # 내부비용 합계 계산
    internal_cost_total_usd = sum(item["amount_usd"] for item in internal_cost_list)
    internal_cost_total_krw = sum(item["amount_krw"] for item in internal_cost_list)

    result = {
        "success": True,
        "batch_id": batch_id,
        "billing_cycle": data.billing_cycle,
        "slip_type": data.slip_type,
        "exchange_rate": {
            "domestic": domestic_exchange_rate,
            "overseas": overseas_exchange_rate,
            "overseas_source": "manual" if data.overseas_exchange_rate else "auto",
            "overseas_rate_date": str(overseas_rate_info.get("rate_date"))
            if overseas_rate_info and overseas_rate_info.get("rate_date")
            else (
                str(date(data.document_date.year, data.document_date.month, 1))
                if overseas_exchange_rate
                else None
            ),
            "rate_type": exchange_rate_info.get("rate_type") if exchange_rate_info else "manual",
            "rate_date": str(exchange_rate_info.get("rate_date"))
            if exchange_rate_info and exchange_rate_info.get("rate_date")
            else str(data.document_date),
            "synced_from_hb": exchange_rate_synced,
        },
        "total_slips": seqno - 1,
        "slips_with_bp": len(slips_created),
        "slips_no_bp": len(slips_no_mapping),
        "no_mapping_details": slips_no_mapping[:20],
    }

    # 내부비용이 있는 경우 별도 표시
    if internal_cost_list:
        result["internal_cost"] = {
            "count": len(internal_cost_list),
            "total_usd": round(internal_cost_total_usd, 2),
            "total_krw": internal_cost_total_krw,
            "details": internal_cost_list[:20],
        }

    # 해외법인이 있는 경우 별도 표시
    if overseas_slips:
        overseas_total_usd = sum(item["amount_usd"] for item in overseas_slips)
        overseas_total_krw = sum(item["amount_krw"] or 0 for item in overseas_slips)
        result["overseas"] = {
            "count": len(overseas_slips),
            "total_usd": round(overseas_total_usd, 2),
            "total_krw": int(overseas_total_krw),
            "exchange_rate": overseas_exchange_rate,
            "exchange_rate_source": "manual" if data.overseas_exchange_rate else "auto",
            "details": overseas_slips[:20],
        }

    # 추가 비용이 있는 경우 별도 표시
    if additional_charge_slips:
        total_charge_usd = sum(item["amount_usd"] for item in additional_charge_slips)
        total_charge_krw = sum(item["amount_krw"] for item in additional_charge_slips)
        result["additional_charges"] = {
            "count": len(additional_charge_slips),
            "total_usd": round(total_charge_usd, 2),
            "total_krw": total_charge_krw,
            "details": additional_charge_slips[:20],
        }

    return result


@router.get("/")
def get_slips(
    batch_id: str | None = Query(None),
    billing_cycle: str | None = Query(None),
    slip_type: str | None = Query(None),
    has_bp: bool | None = Query(None),
    limit: int = Query(100, le=1000),
    offset: int = Query(0),
    db: Session = Depends(get_db),
):
    """전표 목록 조회"""
    query = db.query(SlipRecord)

    if batch_id:
        query = query.filter(SlipRecord.batch_id == batch_id)
    if billing_cycle:
        query = query.filter(SlipRecord.billing_cycle == billing_cycle)
    if slip_type:
        query = query.filter(SlipRecord.slip_type == slip_type)
    if has_bp is True:
        query = query.filter(SlipRecord.partner.isnot(None))
    elif has_bp is False:
        query = query.filter(SlipRecord.partner.is_(None))

    total = query.count()
    slips = query.order_by(SlipRecord.seqno).offset(offset).limit(limit).all()

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "data": [
            {
                "id": s.id,
                "batch_id": s.batch_id,
                "seqno": s.seqno,
                "slip_type": s.slip_type,
                "billing_cycle": s.billing_cycle,
                "partner": s.partner,
                "partner_name": s.partner_name,
                "wrbtr": s.wrbtr,
                "wrbtr_usd": s.wrbtr_usd,
                "sgtxt": s.sgtxt,
                "zzsconid": s.zzsconid,
                "uid": s.uid,
                "is_confirmed": s.is_confirmed,
            }
            for s in slips
        ],
    }


@router.get("/batches")
def get_slip_batches(db: Session = Depends(get_db)):
    """전표 배치 목록"""
    batches = (
        db.query(
            SlipRecord.batch_id,
            SlipRecord.billing_cycle,
            SlipRecord.slip_type,
            func.count(SlipRecord.id).label("count"),
            func.sum(SlipRecord.wrbtr).label("total_krw"),
            func.min(SlipRecord.created_at).label("created_at"),
        )
        .group_by(SlipRecord.batch_id, SlipRecord.billing_cycle, SlipRecord.slip_type)
        .order_by(func.min(SlipRecord.created_at).desc())
        .all()
    )

    return [
        {
            "batch_id": b.batch_id,
            "billing_cycle": b.billing_cycle,
            "slip_type": b.slip_type,
            "count": b.count,
            "total_krw": int(b.total_krw or 0),
            "created_at": b.created_at.isoformat() if b.created_at else None,
        }
        for b in batches
    ]


class SlipUpdate(BaseModel):
    partner: str | None = None
    ar_account: str | None = None
    wrbtr: float | None = None
    dmbtr_c: float | None = None  # 원화환산액 (해외법인용, 수동 수정)
    exchange_rate: float | None = None  # 적용 환율 (수동 수정)
    zzsconid: str | None = None
    zzpconid: str | None = None
    zzsempnm: str | None = None
    zzinvno: str | None = None


@router.patch("/{slip_id}")
def update_slip(slip_id: int, data: SlipUpdate, db: Session = Depends(get_db)):
    """전표 수정"""
    slip = db.query(SlipRecord).filter(SlipRecord.id == slip_id).first()
    if not slip:
        raise HTTPException(status_code=404, detail="Slip not found")

    if slip.is_confirmed:
        raise HTTPException(status_code=400, detail="Cannot modify confirmed slip")

    update_data = data.model_dump(exclude_unset=True)

    # partner 변경 시 zzcon도 함께 변경
    if "partner" in update_data:
        update_data["zzcon"] = update_data["partner"]
        # BP 이름 조회
        bp = db.query(BPCode).filter(BPCode.bp_number == update_data["partner"]).first()
        if bp:
            update_data["partner_name"] = bp.name_local

    # zzsconid 변경 시 zzpconid도 함께 변경
    if "zzsconid" in update_data:
        update_data["zzpconid"] = update_data["zzsconid"].replace("매출", "매입")

    for key, value in update_data.items():
        setattr(slip, key, value)

    db.commit()
    return {"success": True, "id": slip_id}


@router.post("/confirm/{batch_id}")
def confirm_slips(batch_id: str, db: Session = Depends(get_db)):
    """배치 전표 확정"""
    slips = db.query(SlipRecord).filter(SlipRecord.batch_id == batch_id).all()

    if not slips:
        raise HTTPException(status_code=404, detail="Batch not found")

    # BP 없는 전표 확인
    no_bp = [s for s in slips if not s.partner]
    if no_bp:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot confirm: {len(no_bp)} slips without BP mapping",
        )

    for slip in slips:
        slip.is_confirmed = True

    db.commit()
    return {"success": True, "confirmed": len(slips)}


def _format_amount(amount: float, currency: str) -> str | int:
    """통화에 따른 금액 포맷팅 - KRW는 정수, 외화는 소수점 2자리"""
    if currency == "KRW":
        return int(amount)
    return f"{amount:.2f}"


def _get_common_slip_fields(slip: SlipRecord, db: Session) -> dict:
    """전표 공통 필드 추출"""
    tax_number = ""
    if slip.partner:
        bp = db.query(BPCode).filter(BPCode.bp_number == slip.partner).first()
        if bp:
            tax_number = bp.tax_number or ""

    dmbtr_c = ""
    if slip.waers != "KRW" and slip.dmbtr_c:
        dmbtr_c = int(slip.dmbtr_c)

    wrbtr_display = _format_amount(slip.wrbtr, slip.waers)
    bldat = slip.bldat.strftime("%Y%m%d") if slip.bldat else ""
    budat = slip.budat.strftime("%Y%m%d") if slip.budat else ""

    return {
        "tax_number": tax_number,
        "dmbtr_c": dmbtr_c,
        "wrbtr_display": wrbtr_display,
        "bldat": bldat,
        "budat": budat,
    }


def _build_sales_row(slip: SlipRecord, f: dict) -> list:
    return [
        slip.seqno,
        slip.bukrs,
        f["bldat"],
        f["budat"],
        slip.waers,
        slip.xblnr or "",
        slip.sgtxt or "",
        slip.partner or "",
        slip.ar_account or "",
        slip.hkont or "",
        f["wrbtr_display"],
        f["dmbtr_c"],
        slip.prctr or "",
        slip.zzcon or "",
        slip.zzsconid or "",
        slip.zzpconid or "",
        slip.zzsempno or "",
        slip.zzsempnm or "",
        slip.zzref2 or "",
        slip.zzref or "",
        slip.zzinvno or "",
        slip.zzdepgno or "",
        "",
        f["tax_number"],
        slip.partner_name or "",
    ]


def _build_cost_row(slip: SlipRecord, f: dict) -> list:
    return [
        slip.seqno,
        slip.bukrs,
        f["bldat"],
        f["budat"],
        slip.waers,
        slip.xblnr or "",
        slip.sgtxt or "",
        slip.hkont or "",
        slip.ar_account or "",
        f["wrbtr_display"],
        f["dmbtr_c"],
        slip.prctr or "",
        slip.zzcon or "",
        slip.zzpconid or "",
        slip.zzsconid or "",
        slip.zzsempno or "",
        slip.zzsempnm or "",
        slip.zzref2 or "",
        slip.zzinvno or "",
        slip.partner or "",
        slip.zzref or "",
        "",
        f["tax_number"],
        slip.partner_name or "",
    ]


def _build_billing_row(slip: SlipRecord, f: dict) -> list:
    return [
        slip.seqno,
        slip.bukrs,
        f["bldat"],
        f["budat"],
        slip.waers,
        slip.xblnr or "",
        slip.sgtxt or "",
        slip.partner or "",
        slip.ar_account or "",
        slip.hkont or "",
        f["wrbtr_display"],
        f["dmbtr_c"],
        slip.tax_code or "A1",
        "",
        "",
        slip.prctr or "",
        slip.zzcon or "",
        slip.zzsconid or "",
        slip.zzsempno or "",
        slip.zzsempnm or "",
        slip.zzref2 or "",
        slip.zzref or "",
        slip.zzinvno or "",
        "",
        "",
        slip.zzdepgno or "",
        "",
        f["tax_number"],
        slip.partner_name or "",
        f["wrbtr_display"],
    ]


_EXPORT_CONFIGS = {
    "sales": {
        "headers": [
            "SEQNO",
            "BUKRS(회사코드)",
            "BLDAT(증빙일)",
            "BUDAT(전표적용일)",
            "WAERS(통화)",
            "XBLNR(참조)",
            "SGTXT(전표적요)",
            "PARTNER(거래처)",
            "채권계정",
            "HKONT(매출계정)",
            "WRBTR(통화금액)",
            "DMBTR_C(원화금액)",
            "PRCTR(부서코드)",
            "ZZCON(매출고객)",
            "ZZSCONID(매출계약번호)",
            "ZZPCONID(매입계약번호)",
            "ZZSEMPNO(영업사원사번)",
            "ZZSEMPNM(영업사원명)",
            "ZZREF2(오퍼링)",
            "ZZREF(세금계산서 승인번호)",
            "ZZINVNO(인보이스)",
            "ZZDEPGNO(예치금그룹번호)",
            "",
            "사업자번호",
            "거래처명",
        ],
        "row_builder": _build_sales_row,
    },
    "cost": {
        "headers": [
            "SEQNO",
            "BUKRS(회사코드)",
            "BLDAT(증빙일)",
            "BUDAT(전기일)",
            "WAERS(통화)",
            "XBLNR(참조)",
            "BKTXT(전표적요)",
            "HKONT(원가계정)",
            "HKONT(상대계정)",
            "WRBTR(통화금액)",
            "DMBTR_C(원화금액)",
            "KOSTL(코스트센터)",
            "ZZCON(매출고객)",
            "ZZPCONID(매입계약번호)",
            "매출계약번호",
            "ZZSEMPNO(영업사원사번)",
            "ZZSEMPNM(영업사원명)",
            "ZZREF2(오퍼링)",
            "ZZINVNO(인보이스)",
            "ZZLIFNR(구매처)",
            "ZZREF(세금계산서승인번호)",
            "",
            "사업자번호",
            "거래처명",
        ],
        "row_builder": _build_cost_row,
    },
    "billing": {
        "headers": [
            "SEQNO",
            "BUKRS(회사코드)",
            "BLDAT(세금계산서발행일)",
            "BUDAT(전표적용일)",
            "WAERS(통화)",
            "XBLNR(참조)",
            "SGTXT(전표적요)",
            "PARTNER(거래처)",
            "HKONT(차변계정)",
            "HKONT(대변계정)",
            "WRBTR(통화금액)",
            "DMBTR_C(원화금액)",
            "MWSKZ(부가세코드)",
            "부가세액(거래통화)",
            "ZTERM(수금조건)",
            "PRCTR(부서코드)",
            "ZZCON(매출고객)",
            "ZZSCONID(매출계약번호)",
            "ZZSEMPNO(영업사원사번)",
            "ZZSEMPNM(영업사원명)",
            "ZZREF2(오퍼링)",
            "ZZREF(세금계산서 승인번호)",
            "ZZINVNO(인보이스)",
            "ZZREF3(고객담당자명)",
            "ZZSETKEY(고객담당자email)",
            "ZZDEPGNO(예치금그룹번호)",
            "",
            "사업자번호",
            "사명",
            "공급가",
        ],
        "row_builder": _build_billing_row,
    },
}


def _export_slips(slips: list[SlipRecord], db: Session, slip_type: str) -> tuple[list, list]:
    """통합 전표 내보내기"""
    if slip_type in ("purchase", "cost"):
        config = _EXPORT_CONFIGS["cost"]
    elif slip_type == "billing":
        config = _EXPORT_CONFIGS["billing"]
    else:
        config = _EXPORT_CONFIGS["sales"]

    row_builder = config["row_builder"]
    rows = []
    for slip in slips:
        fields = _get_common_slip_fields(slip, db)
        rows.append(row_builder(slip, fields))

    return config["headers"], rows


@router.get("/export/{batch_id}")
def export_slips_csv(batch_id: str, db: Session = Depends(get_db)):
    """전표 CSV 내보내기 (전표 유형별 양식 적용)"""
    slips = (
        db.query(SlipRecord)
        .filter(SlipRecord.batch_id == batch_id)
        .order_by(SlipRecord.seqno)
        .all()
    )

    if not slips:
        raise HTTPException(status_code=404, detail="Batch not found")

    slip_type = slips[0].slip_type if slips else "sales"
    headers, rows = _export_slips(slips, db, slip_type)

    # CSV 생성
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(headers)
    for row in rows:
        writer.writerow(row)

    # 파일 응답
    output.seek(0)
    billing_cycle = slips[0].billing_cycle if slips else ""
    filename = f"{slip_type}_{billing_cycle}_{batch_id}.csv"

    # BOM 추가 (Excel 한글 호환)
    content = "\ufeff" + output.getvalue()

    return StreamingResponse(
        io.BytesIO(content.encode("utf-8-sig")),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.delete("/batch/{batch_id}")
def delete_batch(batch_id: str, db: Session = Depends(get_db)):
    """배치 전표 삭제"""
    slips = db.query(SlipRecord).filter(SlipRecord.batch_id == batch_id).all()

    if not slips:
        raise HTTPException(status_code=404, detail="Batch not found")

    # 확정된 전표가 있으면 삭제 불가
    confirmed = [s for s in slips if s.is_confirmed]
    if confirmed:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot delete: {len(confirmed)} slips are confirmed",
        )

    # 예치금 사용 기록 복원 (이 배치로 차감된 예치금 되돌리기)
    usages = db.query(DepositUsage).filter(DepositUsage.slip_batch_id == batch_id).all()
    for usage in usages:
        dep = db.query(Deposit).filter(Deposit.id == usage.deposit_id).first()
        if dep:
            dep.remaining_amount += usage.amount
            dep.is_exhausted = False
        db.delete(usage)

    count = len(slips)
    for slip in slips:
        db.delete(slip)

    db.commit()
    return {"success": True, "deleted": count}


def _get_applicable_additional_charges(
    db: Session,
    contract_seq: int,
    billing_cycle: str,
    slip_type: str,
) -> list:
    """특정 정산월/전표유형에 적용되는 추가 비용 조회"""
    from app.api.additional_charge import get_applicable_charges

    return get_applicable_charges(db, contract_seq, billing_cycle, slip_type)


def _get_pro_rata_ratio(
    db: Session,
    contract_seq: int,
    billing_cycle: str,
    config: SlipConfig,
    contract_profile,
) -> float | None:
    """전표 생성 시 일할 비율 조회"""
    from app.api.pro_rata import get_pro_rata_ratio

    pro_rata_enabled = config.pro_rata_enabled if hasattr(config, "pro_rata_enabled") else True
    pro_rata_override = (
        contract_profile.pro_rata_override
        if contract_profile and hasattr(contract_profile, "pro_rata_override")
        else None
    )

    return get_pro_rata_ratio(db, contract_seq, billing_cycle, pro_rata_enabled, pro_rata_override)


def _get_split_rule(
    db: Session,
    uid: str,
    billing_cycle: str,
):
    """분할 청구 규칙 조회"""
    from app.api.split_billing import get_split_rule_for_uid

    return get_split_rule_for_uid(db, uid, billing_cycle)


def _calculate_split_amounts(
    db: Session,
    uid: str,
    amount_usd: float,
    billing_cycle: str,
) -> dict | None:
    """분할 청구 금액 계산"""
    from app.api.split_billing import calculate_split_amounts

    return calculate_split_amounts(db, uid, amount_usd, billing_cycle)


def _create_slip_record(
    db: Session,
    batch_id: str,
    slip_type: str,
    vendor: str,
    billing_cycle: str,
    seqno: int,
    config: SlipConfig,
    document_date: date,
    sgtxt: str,
    amount_usd: float,
    amount_krw: int,
    exchange_rate: float | None,
    company,
    contract,
    bp_number: str | None,
    billing_profile,
    invoice_number: str | None,
    uid: str | None = None,
    source_type: str = SlipSourceType.BILLING.value,
    additional_charge_id: int | None = None,
    split_rule_id: int | None = None,
    split_allocation_id: int | None = None,
    pro_rata_ratio: float | None = None,
    original_amount: float | None = None,
    is_overseas: bool = False,
    slip_currency: str = "KRW",
    dmbtr_c: float | None = None,
) -> SlipRecord:
    """전표 레코드 생성 헬퍼"""
    # 계정코드 결정
    ar_account = config.ar_account_default if slip_type == "sales" else config.ap_account_default

    if is_overseas and slip_type == "sales":
        hkont = config.hkont_sales_export or "41021020"
    else:
        hkont = config.hkont_sales if slip_type == "sales" else config.hkont_purchase

    # 청구 프로필에 계정코드가 있으면 사용
    if billing_profile:
        if slip_type == "sales":
            if billing_profile.ar_account:
                ar_account = billing_profile.ar_account
            if billing_profile.hkont_sales:
                hkont = billing_profile.hkont_sales
        else:
            if billing_profile.ap_account:
                ar_account = billing_profile.ap_account
            if billing_profile.hkont_purchase:
                hkont = billing_profile.hkont_purchase

    # 계약번호
    sales_contract = (
        contract.sales_contract_code if contract and contract.sales_contract_code else "매출ALI999"
    )
    purchase_contract = (
        sales_contract.replace("매출", "매입") if "매출" in sales_contract else "매입ALI999"
    )

    # 부가세코드
    tax_code = "A1"
    if billing_profile and billing_profile.payment_type:
        tax_code = PAYMENT_TYPE_TAX_CODE.get(billing_profile.payment_type, "A1")

    slip = SlipRecord(
        batch_id=batch_id,
        slip_type=slip_type,
        vendor=vendor,
        billing_cycle=billing_cycle,
        source_type=source_type,
        seqno=seqno,
        bukrs=config.bukrs,
        bldat=document_date,
        budat=document_date,
        waers=slip_currency,
        sgtxt=sgtxt,
        partner=bp_number,
        partner_name=company.name if company else None,
        ar_account=ar_account,
        hkont=hkont,
        tax_code=tax_code,
        wrbtr=amount_krw if slip_currency == "KRW" else amount_usd,
        wrbtr_usd=amount_usd,
        dmbtr_c=dmbtr_c,
        exchange_rate=exchange_rate,
        prctr=config.prctr,
        zzcon=bp_number,
        zzsconid=sales_contract,
        zzpconid=purchase_contract,
        zzsempnm=contract.sales_person if contract else None,
        zzref2=config.zzref2,
        zzinvno=invoice_number,
        uid=uid,
        contract_seq=contract.seq if contract else None,
        company_seq=company.seq if company else None,
        additional_charge_id=additional_charge_id,
        split_rule_id=split_rule_id,
        split_allocation_id=split_allocation_id,
        pro_rata_ratio=pro_rata_ratio,
        original_amount=original_amount,
    )

    db.add(slip)
    return slip
