"""
파일 기반 임포트 API

프로젝트 폴더의 data/import 디렉토리에 파일을 놓으면 임포트할 수 있습니다.

폴더 구조:
  data/import/
    ├── billing/           # 빌링 데이터
    │   ├── enduser/       # 매출 (Enduser)
    │   └── reseller/      # 매입 (Reseller)
    ├── master/            # 마스터 데이터
    │   ├── bp_code.csv
    │   ├── account_code.csv
    │   ├── tax_code.csv
    │   ├── cost_center.csv
    │   └── contract.csv
    └── hb/                # HB 연동 데이터
        ├── company.json
        ├── contract.json
        └── account.json
"""

import csv
import json
import re
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Depends, Query


def is_korean_tax_number(tax_number: str | None) -> bool:
    """한국 사업자등록번호 형식 확인 (xxx-xx-xxxxx 또는 10자리 숫자)"""
    if not tax_number:
        return False

    # 하이픈 제거 후 확인
    normalized = tax_number.replace("-", "").strip()

    # 10자리 숫자인지 확인
    if re.match(r"^\d{10}$", normalized):
        return True

    return False


def detect_overseas_company(license_no: str | None) -> tuple[bool, str]:
    """사업자번호로 해외법인 여부 감지 -> (is_overseas, default_currency)"""
    if not license_no:
        return False, "KRW"

    # 한국 사업자번호 형식이면 국내
    if is_korean_tax_number(license_no):
        return False, "KRW"

    # 국가코드 접두사로 통화 결정 (예: US-xxx, JP-xxx, SG-xxx)
    upper_license = license_no.upper().strip()

    currency_map = {
        "US": "USD",
        "JP": "JPY",
        "SG": "SGD",
        "HK": "HKD",
        "CN": "CNY",
        "TW": "TWD",
        "VN": "VND",
        "TH": "THB",
        "MY": "MYR",
        "ID": "IDR",
        "PH": "PHP",
        "IN": "INR",
        "AU": "AUD",
        "NZ": "NZD",
        "EU": "EUR",
        "GB": "GBP",
        "DE": "EUR",
        "FR": "EUR",
    }

    # 국가코드 접두사 확인 (예: US-123456, JP123456)
    for country_code, currency in currency_map.items():
        if upper_license.startswith(f"{country_code}-") or upper_license.startswith(country_code):
            return True, currency

    # 숫자가 아닌 문자로 시작하면 해외로 간주 (기본 USD)
    if not upper_license[0].isdigit():
        return True, "USD"

    # 10자리가 아니면 해외로 간주
    normalized = license_no.replace("-", "").strip()
    if not re.match(r"^\d{10}$", normalized):
        return True, "USD"

    return False, "KRW"


from sqlalchemy.orm import Session

from app.database import get_db
from app.models.alibaba import (
    AccountCode,
    AlibabaBilling,
    BPCode,
    ContractCode,
    CostCenter,
    TaxCode,
)
from app.models.hb import HBCompany, HBContract, HBVendorAccount
from app.utils import clean_string, parse_float

router = APIRouter(prefix="/api/import", tags=["file-import"])

IMPORT_DIR = Path(__file__).parent.parent.parent.parent / "data" / "import"


def read_file_with_encoding(file_path: Path) -> str:
    """여러 인코딩을 시도하여 파일 읽기"""
    encodings = ["utf-8-sig", "utf-8", "cp949", "euc-kr", "latin-1"]

    for encoding in encodings:
        try:
            return file_path.read_text(encoding=encoding)
        except UnicodeDecodeError:
            continue

    return file_path.read_text(encoding="utf-8", errors="ignore")


@router.get("/scan")
def scan_import_folder():
    """임포트 폴더의 파일 목록 스캔"""
    if not IMPORT_DIR.exists():
        IMPORT_DIR.mkdir(parents=True, exist_ok=True)
        # 하위 폴더도 생성
        (IMPORT_DIR / "billing" / "enduser").mkdir(parents=True, exist_ok=True)
        (IMPORT_DIR / "billing" / "reseller").mkdir(parents=True, exist_ok=True)
        (IMPORT_DIR / "master").mkdir(parents=True, exist_ok=True)
        (IMPORT_DIR / "hb").mkdir(parents=True, exist_ok=True)

    files = {
        "billing": {
            "enduser": [],
            "reseller": [],
        },
        "master": [],
        "hb": [],
    }

    # 빌링 파일 스캔
    enduser_dir = IMPORT_DIR / "billing" / "enduser"
    if enduser_dir.exists():
        files["billing"]["enduser"] = [f.name for f in enduser_dir.glob("*.csv")]

    reseller_dir = IMPORT_DIR / "billing" / "reseller"
    if reseller_dir.exists():
        files["billing"]["reseller"] = [f.name for f in reseller_dir.glob("*.csv")]

    # 마스터 파일 스캔
    master_dir = IMPORT_DIR / "master"
    if master_dir.exists():
        files["master"] = [f.name for f in master_dir.glob("*.csv")]

    # HB 파일 스캔
    hb_dir = IMPORT_DIR / "hb"
    if hb_dir.exists():
        files["hb"] = [f.name for f in hb_dir.glob("*.json")]

    return {
        "import_dir": str(IMPORT_DIR),
        "files": files,
    }


@router.post("/billing/{billing_type}")
def import_billing_file(
    billing_type: Literal["enduser", "reseller"],
    filename: str = Query(..., description="파일명 (예: 202512_billing.csv)"),
    db: Session = Depends(get_db),
):
    """빌링 CSV 파일 임포트"""
    file_path = IMPORT_DIR / "billing" / billing_type / filename

    if not file_path.exists():
        return {"success": False, "error": f"파일을 찾을 수 없습니다: {file_path}"}

    text = read_file_with_encoding(file_path)
    reader = csv.DictReader(text.splitlines())

    inserted = 0
    errors = []

    for i, row in enumerate(reader):
        try:
            original_cost = parse_float(row.get("Original Cost", "0"))
            spn_deducted = parse_float(row.get("SPN Deducted Price", "0"))
            discount = parse_float(row.get("Discount", "0"))
            coupon_deduct = parse_float(row.get("Coupon Deduct", "0"))
            pretax_cost = parse_float(row.get("Pretax Cost(Before Round Down Discount)", "0"))

            # 원본 그대로 저장 (반올림은 전표 생성 시에만)
            if billing_type == "reseller":
                calculated = original_cost - discount - spn_deducted
            else:
                calculated = pretax_cost

            billing = AlibabaBilling(
                billing_type=billing_type,
                billing_cycle=clean_string(row.get("Billing Cycle")),
                consume_time=clean_string(row.get("Consume Time")),
                user_id=clean_string(row.get("User ID", "")),
                user_name=clean_string(row.get("User Name")),
                user_account=clean_string(row.get("User Account")),
                linked_user_id=clean_string(row.get("Linked User ID")),
                linked_user_name=clean_string(row.get("Linked User Name")),
                linked_user_account=clean_string(row.get("Linked User Account")),
                bill_source=clean_string(row.get("Bill Source")),
                order_type=clean_string(row.get("Order Type")),
                charge_type=clean_string(row.get("Charge Type")),
                billing_type_detail=clean_string(row.get("Billing Type")),
                product_code=clean_string(row.get("Product Code")),
                product_name=clean_string(row.get("Product Name")),
                instance_id=clean_string(row.get("Instance ID")),
                instance_name=clean_string(row.get("Instance Name")),
                instance_config=clean_string(row.get("Instance Configuration")),
                instance_tag=clean_string(row.get("Instance Tag")),
                region=clean_string(row.get("Region")),
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
        "filename": filename,
        "inserted": inserted,
        "errors": errors[:20],
    }


@router.post("/master/{master_type}")
def import_master_file(
    master_type: Literal["bp_code", "account_code", "tax_code", "cost_center", "contract"],
    filename: str = Query(None, description="파일명 (미지정 시 기본 파일명 사용)"),
    db: Session = Depends(get_db),
):
    """마스터 데이터 CSV 파일 임포트"""
    default_filenames = {
        "bp_code": "BP_CODE.csv",
        "account_code": "계정코드.csv",
        "tax_code": "세금코드.csv",
        "cost_center": "부서코드.csv",
        "contract": "매출계약번호.csv",
    }

    actual_filename = filename or default_filenames.get(master_type)
    file_path = IMPORT_DIR / "master" / actual_filename

    if not file_path.exists():
        return {"success": False, "error": f"파일을 찾을 수 없습니다: {file_path}"}

    text = read_file_with_encoding(file_path)
    reader = csv.DictReader(text.splitlines())

    inserted = 0
    updated = 0
    errors = []

    if master_type == "bp_code":
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

    elif master_type == "account_code":
        for i, row in enumerate(reader):
            try:
                hkont = clean_string(row.get("계정코드"))
                if not hkont:
                    continue

                existing = db.query(AccountCode).filter(AccountCode.hkont == hkont).first()
                if existing:
                    continue

                db.add(
                    AccountCode(
                        hkont=hkont,
                        name_short=clean_string(row.get("계정명(short)")),
                        name_long=clean_string(row.get("계정명(long)")),
                        account_group=clean_string(row.get("계정그룹")),
                        currency=clean_string(row.get("관리통화")) or "KRW",
                    )
                )
                inserted += 1
            except Exception as e:
                errors.append(f"Row {i + 2}: {str(e)}")

    elif master_type == "tax_code":
        for row in reader:
            sales_code = clean_string(row.get("세금 코드"))
            sales_desc = clean_string(row.get("내용"))
            if sales_code:
                existing = db.query(TaxCode).filter(TaxCode.code == sales_code).first()
                if not existing:
                    db.add(TaxCode(code=sales_code, description=sales_desc, is_sales=True))
                    inserted += 1

            purchase_code = clean_string(row.get("세금 코드.1"))
            purchase_desc = clean_string(row.get("내용.1"))
            if purchase_code:
                existing = db.query(TaxCode).filter(TaxCode.code == purchase_code).first()
                if not existing:
                    db.add(TaxCode(code=purchase_code, description=purchase_desc, is_sales=False))
                    inserted += 1

    elif master_type == "cost_center":
        for row in reader:
            cost_center = clean_string(row.get("코스트 센터"))
            if not cost_center:
                continue

            existing = db.query(CostCenter).filter(CostCenter.cost_center == cost_center).first()
            if existing:
                continue

            db.add(
                CostCenter(
                    company_code=clean_string(row.get("회사 코드")) or "1100",
                    cost_center=cost_center,
                    name=clean_string(row.get("부서명")),
                    profit_center=clean_string(row.get("손익 센터")),
                    profit_center_name=clean_string(row.get("손익 센터 명")),
                    source_system=clean_string(row.get("Source 시스템")),
                )
            )
            inserted += 1

    elif master_type == "contract":
        for row in reader:
            sales_contract = list(row.values())[0]
            sales_contract = clean_string(sales_contract)
            if not sales_contract:
                continue

            existing = (
                db.query(ContractCode).filter(ContractCode.sales_contract == sales_contract).first()
            )
            if existing:
                continue

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

            db.add(
                ContractCode(
                    sales_contract=sales_contract,
                    description=description,
                    vendor=vendor,
                )
            )
            inserted += 1

    db.commit()

    return {
        "success": len(errors) == 0,
        "master_type": master_type,
        "filename": actual_filename,
        "inserted": inserted,
        "updated": updated,
        "errors": errors[:20],
    }


@router.post("/hb/{data_type}")
def import_hb_file(
    data_type: Literal["company", "contract", "account"],
    filename: str = Query(None, description="파일명 (미지정 시 기본 파일명 사용)"),
    db: Session = Depends(get_db),
):
    """HB JSON 파일 임포트

    JSON 구조: {"success": true, "data": [...]}
    """
    default_filenames = {
        "company": "hb_company.json",
        "contract": "hb_contract.json",
        "account": "hb_account.json",
    }

    actual_filename = filename or default_filenames.get(data_type)
    file_path = IMPORT_DIR / "hb" / actual_filename

    if not file_path.exists():
        return {"success": False, "error": f"파일을 찾을 수 없습니다: {file_path}"}

    text = read_file_with_encoding(file_path)
    raw_data = json.loads(text)

    # {"success": true, "data": [...]} 구조 처리
    if isinstance(raw_data, dict) and "data" in raw_data:
        data = raw_data["data"]
    elif isinstance(raw_data, list):
        data = raw_data
    else:
        data = [raw_data]

    inserted = 0
    updated = 0
    accounts_inserted = 0

    if data_type == "company":
        bp_matched = 0
        overseas_detected = 0

        for item in data:
            seq = item.get("seq")
            if not seq:
                continue

            existing = db.query(HBCompany).filter(HBCompany.seq == seq).first()

            # 사업자등록번호로 BP 코드 매칭 및 해외법인 감지
            license_no = item.get("license")
            bp_number = None
            is_overseas, default_currency = detect_overseas_company(license_no)
            if is_overseas:
                overseas_detected += 1

            if license_no:
                # 사업자번호 정규화 (하이픈 제거)
                normalized_license = license_no.replace("-", "").strip()
                # BP 코드에서 tax_number로 검색
                bp = (
                    db.query(BPCode)
                    .filter(BPCode.tax_number.like(f"%{normalized_license}%"))
                    .first()
                )
                if bp:
                    bp_number = bp.bp_number
                    bp_matched += 1

            record_data = {
                "seq": seq,
                "vendor": item.get("service_type", "alibaba"),
                "name": item.get("name"),
                "license": license_no,
                "address": item.get("address"),
                "ceo_name": item.get("ceo_name"),
                "phone": item.get("phone"),
                "email": item.get("email"),
                "website": item.get("website"),
                "description": item.get("description"),
                "business_status": item.get("business_status"),  # 업태
                "business_type": item.get("business_type"),  # 종목
                "industry": item.get("industry"),
                "industry_segment": item.get("industry_segment"),
                "hb_customer_code": item.get("customer_code"),
                "hb_type": item.get("type"),
                "hb_status": item.get("status"),
                # 담당자 정보 (manager.xxx 형태)
                "manager_name": item.get("manager.name"),
                "manager_email": item.get("manager.email"),
                "manager_tel": item.get("manager.tel"),
                # BP 매칭
                "bp_number": bp_number,
                # 내부비용 여부
                "is_internal_cost": item.get("is_internal_cost", False),
                # 해외법인 여부 (자동 감지)
                "is_overseas": is_overseas,
                "default_currency": default_currency,
            }

            if existing:
                for key, value in record_data.items():
                    if key != "seq" and value is not None:
                        setattr(existing, key, value)
                updated += 1
            else:
                db.add(HBCompany(**record_data))
                inserted += 1

        db.commit()
        return {
            "success": True,
            "data_type": data_type,
            "filename": actual_filename,
            "inserted": inserted,
            "updated": updated,
            "bp_matched": bp_matched,
            "overseas_detected": overseas_detected,
        }

    elif data_type == "contract":
        # 이미 처리된 UID 추적 (중복 삽입 방지)
        processed_uids: set[str] = set()
        from app.models.hb import AccountContractMapping

        for item in data:
            seq = item.get("seq")
            if not seq:
                continue

            existing = db.query(HBContract).filter(HBContract.seq == seq).first()

            # to, cc 이메일 리스트를 JSON 문자열로 변환
            email_to = (
                json.dumps(item.get("to", []), ensure_ascii=False) if item.get("to") else None
            )
            email_cc = (
                json.dumps(item.get("cc", []), ensure_ascii=False) if item.get("cc") else None
            )

            record_data = {
                "seq": seq,
                "vendor": "alibaba",
                "name": item.get("name"),
                "company_name": item.get("company"),  # 원본 company 이름
                "company_seq": item.get("company_seq"),
                "charge_currency": item.get("charge_currency", "USD"),
                "discount_rate": item.get("discount_rate", 0),
                "exchange_type": item.get("exchange_type"),
                "sales_person": item.get("the_person_in_charge"),  # 영업담당
                "email_to": email_to,
                "email_cc": email_cc,
                "tax_invoice_month": "next_month" if item.get("is_next_month") else "current_month",
                "enabled": item.get("enabled", True),
                "is_auto_reseller_margin": item.get("is_auto_reseller_margin", True),
            }

            if existing:
                for key, value in record_data.items():
                    if key != "seq" and value is not None:
                        setattr(existing, key, value)
                updated += 1
            else:
                db.add(HBContract(**record_data))
                inserted += 1

            # 계약에 연결된 계정(UID)들도 함께 저장
            accounts = item.get("accounts", [])
            for acc in accounts:
                account_id = str(acc.get("id", ""))
                if not account_id:
                    continue

                # 이번 세션에서 이미 처리한 UID인지 확인
                if account_id not in processed_uids:
                    # DB에 존재하는지 확인
                    existing_acc = (
                        db.query(HBVendorAccount).filter(HBVendorAccount.id == account_id).first()
                    )
                    if not existing_acc:
                        db.add(
                            HBVendorAccount(
                                id=account_id,
                                vendor="alibaba",
                                name=item.get("name"),  # 계약명을 계정명으로 사용
                                is_active=True,
                            )
                        )
                        accounts_inserted += 1
                    processed_uids.add(account_id)

                # 계정-계약 매핑 생성
                existing_mapping = (
                    db.query(AccountContractMapping)
                    .filter(
                        AccountContractMapping.account_id == account_id,
                        AccountContractMapping.contract_seq == seq,
                    )
                    .first()
                )

                if not existing_mapping:
                    mapping_type = acc.get("type", "all")
                    projects = (
                        json.dumps(acc.get("projects", []), ensure_ascii=False)
                        if acc.get("projects")
                        else None
                    )
                    db.add(
                        AccountContractMapping(
                            account_id=account_id,
                            contract_seq=seq,
                            mapping_type=mapping_type,
                            projects=projects,
                        )
                    )

    elif data_type == "account":
        # hb_account.json은 HB 사용자 데이터이므로 스킵
        # 실제 Vendor Account(UID)는 contract의 accounts 배열에서 가져옴
        return {
            "success": True,
            "data_type": data_type,
            "filename": actual_filename,
            "message": "hb_account.json은 HB 사용자 데이터입니다. UID 정보는 contract 임포트 시 자동 생성됩니다.",
            "inserted": 0,
            "updated": 0,
        }

    db.commit()

    result = {
        "success": True,
        "data_type": data_type,
        "filename": actual_filename,
        "inserted": inserted,
        "updated": updated,
    }

    if accounts_inserted > 0:
        result["accounts_inserted"] = accounts_inserted

    return result


@router.post("/all")
def import_all_files(db: Session = Depends(get_db)):
    """모든 파일 일괄 임포트"""
    results = []

    # 마스터 데이터 임포트
    for master_type in ["bp_code", "account_code", "tax_code", "cost_center", "contract"]:
        result = import_master_file(master_type, None, db)
        results.append({"type": f"master/{master_type}", **result})

    # HB 데이터 임포트
    for hb_type in ["company", "contract", "account"]:
        result = import_hb_file(hb_type, None, db)
        results.append({"type": f"hb/{hb_type}", **result})

    # 빌링 데이터 임포트
    for billing_type in ["enduser", "reseller"]:
        billing_dir = IMPORT_DIR / "billing" / billing_type
        if billing_dir.exists():
            for csv_file in billing_dir.glob("*.csv"):
                result = import_billing_file(billing_type, csv_file.name, db)
                results.append({"type": f"billing/{billing_type}", **result})

    return {
        "success": all(r.get("success", False) for r in results if "error" not in r),
        "results": results,
    }
