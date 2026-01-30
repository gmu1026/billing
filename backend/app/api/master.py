import csv
import io

from fastapi import APIRouter, Depends, File, Query, UploadFile
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.alibaba import AccountCode, BPCode, ContractCode, CostCenter, TaxCode

router = APIRouter(prefix="/api/master", tags=["master"])


def clean_string(value: str | None) -> str | None:
    """문자열 정리"""
    if not value:
        return None
    cleaned = value.strip()
    return cleaned if cleaned else None


# ===== BP Code =====


@router.post("/bp-codes/upload")
async def upload_bp_codes(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """BP Code 마스터 업로드 (BP_CODE.CSV)"""
    content = await file.read()
    text = content.decode("utf-8-sig")

    reader = csv.DictReader(io.StringIO(text))
    inserted = 0
    updated = 0
    errors = []

    for i, row in enumerate(reader):
        try:
            bp_number = clean_string(row.get("BP 번호"))
            if not bp_number:
                continue

            existing = db.query(BPCode).filter(BPCode.bp_number == bp_number).first()

            data = {
                "company_code": clean_string(row.get("회사 코드")) or "1100",
                "bp_number": bp_number,
                "bp_group": clean_string(row.get("BP 그룹")),
                "bp_group_name": clean_string(row.get("BP 그룹 이름")),
                "name_local": clean_string(row.get("이름 1 (Local)")),
                "name_local_2": clean_string(row.get("이름 2 (Local)")),
                "name_english": clean_string(row.get("이름 3 (English)")),
                "search_key": clean_string(row.get("검색어1")),
                "country": clean_string(row.get("국")),
                "road_address_1": clean_string(row.get("도로 주소 1")),
                "road_address_2": clean_string(row.get("도로 주소 2")),
                "postal_code": clean_string(row.get("우편번호")),
                "tax_number_country": clean_string(row.get("세금번호 국가")),
                "tax_number": clean_string(row.get("세금번호")),
                "business_type": clean_string(row.get("업태")),
                "business_item": clean_string(row.get("종목")),
                "representative": clean_string(row.get("대표자명")),
                "contact_name": clean_string(row.get("담당자 이름")),
                "contact_email": clean_string(row.get("담당자 전자메일 주소")),
                "contact_phone": clean_string(row.get("담당자 전화번호")),
                "ar_account": clean_string(row.get("매출 채권과목")),
                "ap_account": clean_string(row.get("매입 채무과목")),
            }

            if existing:
                for key, value in data.items():
                    setattr(existing, key, value)
                updated += 1
            else:
                db.add(BPCode(**data))
                inserted += 1

        except Exception as e:
            errors.append(f"Row {i + 2}: {str(e)}")

    db.commit()

    return {
        "success": len(errors) == 0,
        "inserted": inserted,
        "updated": updated,
        "errors": errors[:20],
    }


@router.get("/bp-codes")
def get_bp_codes(
    search: str | None = Query(None, description="BP번호, 이름, 사업자번호 검색"),
    limit: int = Query(50, le=500),
    db: Session = Depends(get_db),
):
    """BP Code 목록 조회"""
    query = db.query(BPCode)

    if search:
        search_term = f"%{search}%"
        query = query.filter(
            (BPCode.bp_number.like(search_term))
            | (BPCode.name_local.like(search_term))
            | (BPCode.tax_number.like(search_term))
            | (BPCode.search_key.like(search_term))
        )

    data = query.order_by(BPCode.bp_number).limit(limit).all()

    return [
        {
            "bp_number": d.bp_number,
            "name": d.name_local,
            "road_address": d.road_address_1,
            "tax_number": d.tax_number,
            "representative": d.representative,
            # 전표용 조합 필드
            "display": f"{d.bp_number}/{d.name_local or ''}/{d.road_address_1 or ''}/{d.tax_number or ''}/{d.representative or ''}",
        }
        for d in data
    ]


@router.get("/bp-codes/{bp_number}")
def get_bp_code_detail(bp_number: str, db: Session = Depends(get_db)):
    """BP Code 상세 조회"""
    bp = db.query(BPCode).filter(BPCode.bp_number == bp_number).first()
    if not bp:
        return {"error": "BP Code not found"}

    return {
        "bp_number": bp.bp_number,
        "name_local": bp.name_local,
        "name_english": bp.name_english,
        "road_address_1": bp.road_address_1,
        "tax_number": bp.tax_number,
        "representative": bp.representative,
        "contact_name": bp.contact_name,
        "contact_email": bp.contact_email,
        "ar_account": bp.ar_account,
        "ap_account": bp.ap_account,
    }


# ===== Account Code =====


@router.post("/account-codes/upload")
async def upload_account_codes(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """계정코드 마스터 업로드"""
    content = await file.read()
    text = content.decode("utf-8-sig")

    reader = csv.DictReader(io.StringIO(text))
    inserted = 0
    errors = []

    for i, row in enumerate(reader):
        try:
            hkont = clean_string(row.get("계정코드"))
            if not hkont:
                continue

            existing = db.query(AccountCode).filter(AccountCode.hkont == hkont).first()
            if existing:
                continue

            account = AccountCode(
                hkont=hkont,
                name_short=clean_string(row.get("계정명(short)")),
                name_long=clean_string(row.get("계정명(long)")),
                account_group=clean_string(row.get("계정그룹")),
                currency=clean_string(row.get("관리통화")) or "KRW",
            )
            db.add(account)
            inserted += 1

        except Exception as e:
            errors.append(f"Row {i + 2}: {str(e)}")

    db.commit()

    return {"success": len(errors) == 0, "inserted": inserted, "errors": errors[:20]}


@router.get("/account-codes")
def get_account_codes(
    search: str | None = Query(None),
    db: Session = Depends(get_db),
):
    """계정코드 목록 조회"""
    query = db.query(AccountCode)

    if search:
        search_term = f"%{search}%"
        query = query.filter(
            (AccountCode.hkont.like(search_term))
            | (AccountCode.name_short.like(search_term))
            | (AccountCode.name_long.like(search_term))
        )

    return [
        {
            "hkont": d.hkont,
            "name_short": d.name_short,
            "name_long": d.name_long,
            "account_group": d.account_group,
        }
        for d in query.order_by(AccountCode.hkont).limit(100).all()
    ]


# ===== Tax Code =====


@router.post("/tax-codes/upload")
async def upload_tax_codes(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """세금코드 마스터 업로드"""
    content = await file.read()
    text = content.decode("utf-8-sig")

    reader = csv.DictReader(io.StringIO(text))
    inserted = 0

    for row in reader:
        # 매출 세금코드
        sales_code = clean_string(row.get("세금 코드"))
        sales_desc = clean_string(row.get("내용"))
        if sales_code:
            existing = db.query(TaxCode).filter(TaxCode.code == sales_code).first()
            if not existing:
                db.add(TaxCode(code=sales_code, description=sales_desc, is_sales=True))
                inserted += 1

        # 매입 세금코드 (같은 행의 다른 컬럼)
        purchase_code = clean_string(row.get("세금 코드.1"))
        purchase_desc = clean_string(row.get("내용.1"))
        if purchase_code:
            existing = db.query(TaxCode).filter(TaxCode.code == purchase_code).first()
            if not existing:
                db.add(TaxCode(code=purchase_code, description=purchase_desc, is_sales=False))
                inserted += 1

    db.commit()

    return {"success": True, "inserted": inserted}


@router.get("/tax-codes")
def get_tax_codes(
    is_sales: bool | None = Query(None, description="True=매출, False=매입"),
    db: Session = Depends(get_db),
):
    """세금코드 목록 조회"""
    query = db.query(TaxCode)
    if is_sales is not None:
        query = query.filter(TaxCode.is_sales == is_sales)

    return [
        {"code": d.code, "description": d.description, "is_sales": d.is_sales}
        for d in query.order_by(TaxCode.code).all()
    ]


# ===== Cost Center =====


@router.post("/cost-centers/upload")
async def upload_cost_centers(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """부서(코스트센터) 마스터 업로드"""
    content = await file.read()
    text = content.decode("utf-8-sig")

    reader = csv.DictReader(io.StringIO(text))
    inserted = 0

    for row in reader:
        cost_center = clean_string(row.get("코스트 센터"))
        if not cost_center:
            continue

        existing = db.query(CostCenter).filter(CostCenter.cost_center == cost_center).first()
        if existing:
            continue

        cc = CostCenter(
            company_code=clean_string(row.get("회사 코드")) or "1100",
            cost_center=cost_center,
            name=clean_string(row.get("부서명")),
            profit_center=clean_string(row.get("손익 센터")),
            profit_center_name=clean_string(row.get("손익 센터 명")),
            source_system=clean_string(row.get("Source 시스템")),
        )
        db.add(cc)
        inserted += 1

    db.commit()

    return {"success": True, "inserted": inserted}


@router.get("/cost-centers")
def get_cost_centers(
    search: str | None = Query(None),
    db: Session = Depends(get_db),
):
    """코스트센터 목록 조회"""
    query = db.query(CostCenter)

    if search:
        search_term = f"%{search}%"
        query = query.filter(
            (CostCenter.cost_center.like(search_term)) | (CostCenter.name.like(search_term))
        )

    return [
        {
            "cost_center": d.cost_center,
            "name": d.name,
            "profit_center": d.profit_center,
            "profit_center_name": d.profit_center_name,
        }
        for d in query.order_by(CostCenter.cost_center).all()
    ]


# ===== Contract Code =====


@router.post("/contracts/upload")
async def upload_contracts(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """계약번호 마스터 업로드"""
    content = await file.read()
    text = content.decode("utf-8-sig")

    reader = csv.DictReader(io.StringIO(text))
    inserted = 0

    for row in reader:
        sales_contract = list(row.values())[0]  # 첫 번째 컬럼
        sales_contract = clean_string(sales_contract)
        if not sales_contract:
            continue

        existing = (
            db.query(ContractCode).filter(ContractCode.sales_contract == sales_contract).first()
        )
        if existing:
            continue

        # 벤더 추출 (매출ALI999 -> alibaba)
        vendor = None
        if "ALI" in sales_contract:
            vendor = "alibaba"
        elif "GCP" in sales_contract:
            vendor = "gcp"
        elif "GWS" in sales_contract:
            vendor = "gws"
        elif "AKA" in sales_contract:
            vendor = "akamai"
        elif "ORA" in sales_contract:
            vendor = "oracle"

        description = clean_string(list(row.values())[1]) if len(row.values()) > 1 else None

        contract = ContractCode(
            sales_contract=sales_contract,
            description=description,
            vendor=vendor,
        )
        db.add(contract)
        inserted += 1

    db.commit()

    return {"success": True, "inserted": inserted}


@router.get("/contracts")
def get_contracts(
    vendor: str | None = Query(None),
    db: Session = Depends(get_db),
):
    """계약번호 목록 조회"""
    query = db.query(ContractCode)

    if vendor:
        query = query.filter(ContractCode.vendor == vendor)

    return [
        {
            "sales_contract": d.sales_contract,
            "purchase_contract": d.purchase_contract,
            "description": d.description,
            "vendor": d.vendor,
        }
        for d in query.order_by(ContractCode.sales_contract).all()
    ]
