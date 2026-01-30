"""
전표 생성 및 관리 API
"""

import csv
import io
import uuid
from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query


def round_decimal(value: float, places: int = 2) -> float:
    """소수점 정확한 반올림 (ROUND_HALF_UP)"""
    d = Decimal(str(value))
    return float(d.quantize(Decimal(10) ** -places, rounding=ROUND_HALF_UP))
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models.alibaba import AlibabaBilling, BPCode
from app.models.billing_profile import CompanyBillingProfile
from app.models.hb import AccountContractMapping, HBCompany, HBContract, HBVendorAccount
from app.models.slip import ExchangeRate, SlipConfig, SlipRecord

router = APIRouter(prefix="/api/slip", tags=["slip"])


# ===== 환율 관리 =====


class ExchangeRateCreate(BaseModel):
    rate: float
    rate_date: date
    currency_from: str = "USD"
    currency_to: str = "KRW"
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
        "rate_date": str(rate.rate_date),
        "source": rate.source,
    }


# ===== 전표 설정 =====


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
            "hkont_purchase": "42021010",
            "ar_account_default": "11060110",
            "ap_account_default": "21120110",
            "zzref2": "IBABA001",
            "sgtxt_template": "Alibaba_Cloud_{MM}월_{TYPE}",
        }

    return {
        "vendor": config.vendor,
        "bukrs": config.bukrs,
        "prctr": config.prctr,
        "hkont_sales": config.hkont_sales,
        "hkont_purchase": config.hkont_purchase,
        "ar_account_default": config.ar_account_default,
        "ap_account_default": config.ap_account_default,
        "zzref2": config.zzref2,
        "sgtxt_template": config.sgtxt_template,
    }


class SlipConfigUpdate(BaseModel):
    bukrs: str | None = None
    prctr: str | None = None
    hkont_sales: str | None = None
    hkont_purchase: str | None = None
    ar_account_default: str | None = None
    ap_account_default: str | None = None
    zzref2: str | None = None
    sgtxt_template: str | None = None


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


# ===== 전표 생성 =====


class SlipGenerateRequest(BaseModel):
    billing_cycle: str  # YYYYMM
    slip_type: Literal["sales", "purchase"]  # sales=매출(enduser), purchase=매입(reseller)
    document_date: date  # 증빙일/전기일
    exchange_rate: float | None = None  # 환율 (없으면 USD를 그대로 KRW로 사용)
    invoice_number: str | None = None  # 인보이스 번호 (수기)


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
            hkont_purchase="42021010",
            ar_account_default="11060110",
            ap_account_default="21120110",
            zzref2="IBABA001",
            sgtxt_template="Alibaba_Cloud_{MM}월_{TYPE}",
        )
        db.add(config)
        db.commit()

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

        # KRW 변환 (반올림 ROUND_HALF_UP, 환율 없으면 그대로 KRW로 사용)
        if data.exchange_rate and data.exchange_rate > 0:
            amount_krw = int(round_decimal(amount_usd * data.exchange_rate, 0))
        else:
            # 환율 없으면 USD 금액을 그대로 KRW로 사용
            amount_krw = int(round_decimal(amount_usd, 0))

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

        # 내부비용 체크
        is_internal = company.is_internal_cost if company else False

        if is_internal:
            # 내부비용인 경우
            internal_cost_list.append({
                "uid": uid,
                "amount_usd": round(amount_usd, 2),
                "amount_krw": amount_krw,
                "company_name": company.name if company else None,
                "contract_name": contract.name if contract else None,
            })
            # 매출전표: 완전 제외
            # 매입전표: 전표에는 안넣지만 집계만 함
            continue

        # 해외법인 여부 및 통화 결정
        is_overseas = company.is_overseas if company else False
        slip_currency = "KRW"  # 기본값
        slip_amount = amount_krw  # 기본값: KRW 환산액

        if is_overseas and company:
            # 해외법인: 원화 환산 없이 USD 금액 사용
            slip_currency = company.default_currency or "USD"
            slip_amount = int(round_decimal(amount_usd, 0))  # USD 금액 (소수점 제거)

        # 회사별 청구 프로필 조회 (커스텀 계정코드)
        billing_profile = None
        if company:
            billing_profile = (
                db.query(CompanyBillingProfile)
                .filter(
                    CompanyBillingProfile.company_seq == company.seq,
                    CompanyBillingProfile.vendor == "alibaba",
                )
                .first()
            )

        # 계정코드 결정 (우선순위: 청구프로필 > BP코드 > 기본값)
        ar_account = config.ar_account_default if data.slip_type == "sales" else config.ap_account_default
        hkont = config.hkont_sales if data.slip_type == "sales" else config.hkont_purchase

        # 1. 청구 프로필에 계정코드가 있으면 사용
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

        # 계약번호 (없으면 기본값 사용)
        sales_contract = (
            contract.sales_contract_code
            if contract and contract.sales_contract_code
            else "매출ALI999"
        )
        purchase_contract = sales_contract.replace("매출", "매입") if "매출" in sales_contract else "매입ALI999"

        # 전표 레코드 생성
        slip = SlipRecord(
            batch_id=batch_id,
            slip_type=data.slip_type,
            vendor="alibaba",
            billing_cycle=data.billing_cycle,
            seqno=seqno,
            bukrs=config.bukrs,
            bldat=data.document_date,
            budat=data.document_date,
            waers=slip_currency,  # 해외: USD 등, 국내: KRW
            sgtxt=sgtxt,
            partner=bp_number,
            partner_name=company.name if company else None,
            ar_account=ar_account,
            hkont=hkont,  # 청구프로필 또는 기본값
            wrbtr=slip_amount,  # 해외: USD 금액, 국내: KRW 환산액
            wrbtr_usd=amount_usd,
            exchange_rate=data.exchange_rate if not is_overseas else None,  # 해외는 환율 불필요
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
        )

        db.add(slip)
        seqno += 1

        if not bp_number:
            slips_no_mapping.append({
                "uid": uid,
                "amount_usd": round(amount_usd, 2),
                "amount_krw": amount_krw,
                "account_name": account.name if account else None,
                "contract_name": contract.name if contract else None,
                "company_name": company.name if company else None,
            })
        else:
            slips_created.append({
                "seqno": seqno - 1,
                "uid": uid,
                "bp_number": bp_number,
                "amount_krw": amount_krw,
            })

        # 해외법인 별도 집계
        if is_overseas:
            overseas_slips.append({
                "uid": uid,
                "amount_usd": round(amount_usd, 2),
                "currency": slip_currency,
                "company_name": company.name if company else None,
            })

    db.commit()

    # 내부비용 합계 계산
    internal_cost_total_usd = sum(item["amount_usd"] for item in internal_cost_list)
    internal_cost_total_krw = sum(item["amount_krw"] for item in internal_cost_list)

    result = {
        "success": True,
        "batch_id": batch_id,
        "billing_cycle": data.billing_cycle,
        "slip_type": data.slip_type,
        "exchange_rate": data.exchange_rate,
        "total_slips": seqno - 1,
        "slips_with_bp": len(slips_created),
        "slips_no_bp": len(slips_no_mapping),
        "no_mapping_details": slips_no_mapping[:20],  # 처음 20개만
    }

    # 내부비용이 있는 경우 별도 표시
    if internal_cost_list:
        result["internal_cost"] = {
            "count": len(internal_cost_list),
            "total_usd": round(internal_cost_total_usd, 2),
            "total_krw": internal_cost_total_krw,
            "details": internal_cost_list[:20],  # 처음 20개만
        }

    # 해외법인이 있는 경우 별도 표시
    if overseas_slips:
        overseas_total_usd = sum(item["amount_usd"] for item in overseas_slips)
        result["overseas"] = {
            "count": len(overseas_slips),
            "total_usd": round(overseas_total_usd, 2),
            "details": overseas_slips[:20],  # 처음 20개만
        }

    return result


# ===== 전표 조회 =====


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


# ===== 전표 수정 =====


class SlipUpdate(BaseModel):
    partner: str | None = None
    ar_account: str | None = None
    wrbtr: float | None = None
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


# ===== 전표 내보내기 =====


@router.get("/export/{batch_id}")
def export_slips(batch_id: str, db: Session = Depends(get_db)):
    """전표 CSV 내보내기"""
    slips = (
        db.query(SlipRecord)
        .filter(SlipRecord.batch_id == batch_id)
        .order_by(SlipRecord.seqno)
        .all()
    )

    if not slips:
        raise HTTPException(status_code=404, detail="Batch not found")

    # CSV 생성
    output = io.StringIO()
    writer = csv.writer(output)

    # 헤더
    headers = [
        "SEQNO",
        "BUKRS(회사코드)",
        "BLDAT(증빙일)",
        "BUDAT(전표기준일)",
        "WAERS(통화)",
        "XBLNR(참조)",
        "SGTXT(전표적요)",
        "PARTNER(거래처)",
        "채권과목",
        "HKONT(계정과목)",
        "WRBTR(통화금액)",
        "DMBTR_C(통화금액)",
        "PRCTR(부서코드)",
        "ZZCON(거래처코드)",
        "ZZSCONID(매출계약번호)",
        "ZZPCONID(매입계약번호)",
        "ZZSEMPNO(영업사원번호)",
        "ZZSEMPNM(영업사원명)",
        "ZZREF2(거래명)",
        "ZZREF(세금계산서 관리번호)",
        "ZZINVNO(인보이스)",
        "ZZDEPGNO(예치금그룹번호)",
        "",
        "사업자번호",
        "거래처명",
    ]
    writer.writerow(headers)

    # 데이터
    for slip in slips:
        # BP 정보 조회
        tax_number = ""
        if slip.partner:
            bp = db.query(BPCode).filter(BPCode.bp_number == slip.partner).first()
            if bp:
                tax_number = bp.tax_number or ""

        row = [
            slip.seqno,
            slip.bukrs,
            slip.bldat.strftime("%Y%m%d") if slip.bldat else "",
            slip.budat.strftime("%Y%m%d") if slip.budat else "",
            slip.waers,
            slip.xblnr or "",
            slip.sgtxt or "",
            slip.partner or "",
            slip.ar_account or "",
            slip.hkont or "",
            int(slip.wrbtr),
            "",  # DMBTR_C (비워둠)
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
            "",  # 빈 컬럼
            tax_number,
            slip.partner_name or "",
        ]
        writer.writerow(row)

    # 파일 응답
    output.seek(0)
    slip_type = slips[0].slip_type if slips else "slip"
    billing_cycle = slips[0].billing_cycle if slips else ""
    filename = f"{slip_type}_{billing_cycle}_{batch_id}.csv"

    # BOM 추가 (Excel 한글 호환)
    content = "\ufeff" + output.getvalue()

    return StreamingResponse(
        io.BytesIO(content.encode("utf-8-sig")),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


# ===== 전표 삭제 =====


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

    count = len(slips)
    for slip in slips:
        db.delete(slip)

    db.commit()
    return {"success": True, "deleted": count}
