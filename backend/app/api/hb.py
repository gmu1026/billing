"""
HB (Hubble) 데이터 관리 API

- Company, Contract, VendorAccount CRUD
- JSON 파일 업로드 (HB API 응답 형식)
- 수동 매핑 관리
"""

import json
from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from pydantic import BaseModel
from sqlalchemy import or_
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models.hb import AccountContractMapping, HBCompany, HBContract, HBVendorAccount

router = APIRouter(prefix="/api/hb", tags=["hb"])


def parse_datetime(value: str | None) -> datetime | None:
    """ISO 형식 문자열을 datetime으로 변환"""
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


# ===== Company =====


class CompanyCreate(BaseModel):
    seq: int | None = None  # 수동 등록 시 auto
    vendor: str = "alibaba"
    name: str
    license: str | None = None
    address: str | None = None
    ceo_name: str | None = None
    phone: str | None = None
    email: str | None = None
    business_status: str | None = None
    business_type: str | None = None
    manager_name: str | None = None
    manager_email: str | None = None
    bp_number: str | None = None  # BP 코드 매핑


class CompanyUpdate(BaseModel):
    name: str | None = None
    license: str | None = None
    address: str | None = None
    ceo_name: str | None = None
    bp_number: str | None = None
    is_active: bool | None = None


@router.post("/companies/upload")
async def upload_companies(
    file: UploadFile = File(...),
    vendor: str = Query("alibaba"),
    db: Session = Depends(get_db),
):
    """회사 데이터 JSON 업로드 (HB API 응답 형식)"""
    content = await file.read()
    data = json.loads(content.decode("utf-8"))

    if isinstance(data, dict) and "data" in data:
        items = data["data"]
    elif isinstance(data, list):
        items = data
    else:
        raise HTTPException(status_code=400, detail="Invalid JSON format")

    inserted = 0
    updated = 0

    for item in items:
        seq = item.get("seq")
        if not seq:
            continue

        existing = db.query(HBCompany).filter(HBCompany.seq == seq).first()

        company_data = {
            "seq": seq,
            "vendor": vendor,
            "name": item.get("name", ""),
            "license": item.get("license"),
            "address": item.get("address"),
            "ceo_name": item.get("ceo_name"),
            "phone": item.get("phone"),
            "email": item.get("email"),
            "website": item.get("website"),
            "description": item.get("description"),
            "business_status": item.get("business_status"),
            "business_type": item.get("business_type"),
            "industry": item.get("industry"),
            "industry_segment": item.get("industry_segment"),
            "hb_customer_code": item.get("customer_code"),
            "hb_type": item.get("type"),
            "hb_status": item.get("status"),
            "manager_name": item.get("manager.name"),
            "manager_email": item.get("manager.email"),
            "manager_tel": item.get("manager.tel"),
            "hb_created_at": parse_datetime(item.get("created_at")),
            "hb_updated_at": parse_datetime(item.get("updated_at")),
        }

        if existing:
            for key, value in company_data.items():
                if key != "seq":
                    setattr(existing, key, value)
            updated += 1
        else:
            db.add(HBCompany(**company_data))
            inserted += 1

    db.commit()

    return {"success": True, "inserted": inserted, "updated": updated}


@router.get("/companies")
def get_companies(
    vendor: str = Query("alibaba"),
    search: str | None = Query(None),
    has_bp: bool | None = Query(None, description="BP 매핑 여부 필터"),
    limit: int = Query(100, le=500),
    db: Session = Depends(get_db),
):
    """회사 목록 조회"""
    query = db.query(HBCompany).filter(HBCompany.vendor == vendor)

    if search:
        search_term = f"%{search}%"
        query = query.filter(
            or_(
                HBCompany.name.like(search_term),
                HBCompany.license.like(search_term),
                HBCompany.hb_customer_code.like(search_term),
            )
        )

    if has_bp is True:
        query = query.filter(HBCompany.bp_number.isnot(None))
    elif has_bp is False:
        query = query.filter(HBCompany.bp_number.is_(None))

    companies = query.order_by(HBCompany.name).limit(limit).all()

    return [
        {
            "seq": c.seq,
            "name": c.name,
            "license": c.license,
            "address": c.address,
            "ceo_name": c.ceo_name,
            "bp_number": c.bp_number,
            "manager_name": c.manager_name,
            "is_active": c.is_active,
        }
        for c in companies
    ]


@router.get("/companies/{seq}")
def get_company(seq: int, db: Session = Depends(get_db)):
    """회사 상세 조회"""
    company = (
        db.query(HBCompany)
        .options(joinedload(HBCompany.contracts))
        .filter(HBCompany.seq == seq)
        .first()
    )
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")

    return {
        "seq": company.seq,
        "vendor": company.vendor,
        "name": company.name,
        "license": company.license,
        "address": company.address,
        "ceo_name": company.ceo_name,
        "phone": company.phone,
        "email": company.email,
        "business_status": company.business_status,
        "business_type": company.business_type,
        "manager_name": company.manager_name,
        "manager_email": company.manager_email,
        "bp_number": company.bp_number,
        "hb_customer_code": company.hb_customer_code,
        "is_active": company.is_active,
        "contracts": [
            {"seq": c.seq, "name": c.name, "enabled": c.enabled}
            for c in company.contracts
        ],
    }


@router.patch("/companies/{seq}")
def update_company(seq: int, data: CompanyUpdate, db: Session = Depends(get_db)):
    """회사 정보 수정 (BP 매핑 등)"""
    company = db.query(HBCompany).filter(HBCompany.seq == seq).first()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")

    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(company, key, value)

    db.commit()
    return {"success": True, "seq": seq}


@router.post("/companies", response_model=dict)
def create_company(data: CompanyCreate, db: Session = Depends(get_db)):
    """회사 수동 등록"""
    if data.seq:
        existing = db.query(HBCompany).filter(HBCompany.seq == data.seq).first()
        if existing:
            raise HTTPException(status_code=400, detail="Company seq already exists")

    # seq 자동 생성 (수동 등록용)
    if not data.seq:
        max_seq = db.query(HBCompany).order_by(HBCompany.seq.desc()).first()
        data.seq = (max_seq.seq + 1) if max_seq else 1

    company = HBCompany(**data.model_dump())
    db.add(company)
    db.commit()

    return {"success": True, "seq": company.seq}


# ===== Contract =====


@router.post("/contracts/upload")
async def upload_contracts(
    file: UploadFile = File(...),
    vendor: str = Query("alibaba"),
    db: Session = Depends(get_db),
):
    """계약 데이터 JSON 업로드 (HB API 응답 형식)"""
    content = await file.read()
    data = json.loads(content.decode("utf-8"))

    if isinstance(data, dict) and "data" in data:
        items = data["data"]
    elif isinstance(data, list):
        items = data
    else:
        raise HTTPException(status_code=400, detail="Invalid JSON format")

    inserted = 0
    updated = 0
    account_mappings_created = 0

    for item in items:
        seq = item.get("seq")
        if not seq:
            continue

        existing = db.query(HBContract).filter(HBContract.seq == seq).first()

        contract_data = {
            "seq": seq,
            "vendor": vendor,
            "name": item.get("name", ""),
            "company_name": item.get("company"),
            "company_seq": item.get("company_seq"),
            "corporation": item.get("corporation"),
            "charge_currency": item.get("charge_currency", "USD"),
            "discount_rate": item.get("discount_rate", 0),
            "exchange_type": item.get("exchange_type"),
            "sales_person": item.get("the_person_in_charge"),
            "email_to": json.dumps(item.get("to", []), ensure_ascii=False),
            "email_cc": json.dumps(item.get("cc", []), ensure_ascii=False),
            "tax_invoice_month": item.get("tax_invoice_issuance_month"),
            "enabled": item.get("enabled", True),
            "is_auto_reseller_margin": item.get("is_auto_reseller_margin", True),
            "hb_created_at": parse_datetime(item.get("created_at")),
            "hb_updated_at": parse_datetime(item.get("updated_at")),
        }

        if existing:
            for key, value in contract_data.items():
                if key != "seq":
                    setattr(existing, key, value)
            updated += 1
        else:
            db.add(HBContract(**contract_data))
            inserted += 1

        # Account 매핑 처리
        accounts = item.get("accounts", [])
        for acc in accounts:
            account_id = acc.get("id")
            if not account_id:
                continue

            # 기존 매핑 확인
            existing_mapping = (
                db.query(AccountContractMapping)
                .filter(
                    AccountContractMapping.account_id == account_id,
                    AccountContractMapping.contract_seq == seq,
                )
                .first()
            )

            if not existing_mapping:
                mapping = AccountContractMapping(
                    account_id=account_id,
                    contract_seq=seq,
                    mapping_type=acc.get("type", "all"),
                    projects=json.dumps(acc.get("projects", []), ensure_ascii=False),
                    is_manual=False,
                )
                db.add(mapping)
                account_mappings_created += 1

    db.commit()

    return {
        "success": True,
        "contracts": {"inserted": inserted, "updated": updated},
        "account_mappings_created": account_mappings_created,
    }


@router.get("/contracts")
def get_contracts(
    vendor: str = Query("alibaba"),
    search: str | None = Query(None),
    company_seq: int | None = Query(None),
    enabled: bool | None = Query(None),
    limit: int = Query(100, le=500),
    db: Session = Depends(get_db),
):
    """계약 목록 조회"""
    query = db.query(HBContract).filter(HBContract.vendor == vendor)

    if search:
        search_term = f"%{search}%"
        query = query.filter(
            or_(
                HBContract.name.like(search_term),
                HBContract.company_name.like(search_term),
            )
        )

    if company_seq:
        query = query.filter(HBContract.company_seq == company_seq)

    if enabled is not None:
        query = query.filter(HBContract.enabled == enabled)

    contracts = query.order_by(HBContract.name).limit(limit).all()

    return [
        {
            "seq": c.seq,
            "name": c.name,
            "company_name": c.company_name,
            "company_seq": c.company_seq,
            "corporation": c.corporation,
            "sales_person": c.sales_person,
            "discount_rate": c.discount_rate,
            "enabled": c.enabled,
            "sales_contract_code": c.sales_contract_code,
        }
        for c in contracts
    ]


@router.get("/contracts/{seq}")
def get_contract(seq: int, db: Session = Depends(get_db)):
    """계약 상세 조회 (연결된 계정 포함)"""
    contract = (
        db.query(HBContract)
        .options(
            joinedload(HBContract.company),
            joinedload(HBContract.account_mappings).joinedload(AccountContractMapping.account),
        )
        .filter(HBContract.seq == seq)
        .first()
    )

    if not contract:
        raise HTTPException(status_code=404, detail="Contract not found")

    return {
        "seq": contract.seq,
        "vendor": contract.vendor,
        "name": contract.name,
        "company_name": contract.company_name,
        "company_seq": contract.company_seq,
        "company": {
            "seq": contract.company.seq,
            "name": contract.company.name,
            "bp_number": contract.company.bp_number,
        }
        if contract.company
        else None,
        "corporation": contract.corporation,
        "charge_currency": contract.charge_currency,
        "discount_rate": contract.discount_rate,
        "exchange_type": contract.exchange_type,
        "sales_person": contract.sales_person,
        "sales_contract_code": contract.sales_contract_code,
        "enabled": contract.enabled,
        "accounts": [
            {
                "id": m.account_id,
                "name": m.account.name if m.account else None,
                "mapping_type": m.mapping_type,
                "is_manual": m.is_manual,
            }
            for m in contract.account_mappings
        ],
    }


class ContractUpdate(BaseModel):
    sales_contract_code: str | None = None  # 매출계약번호 설정
    sales_person: str | None = None
    enabled: bool | None = None


@router.patch("/contracts/{seq}")
def update_contract(seq: int, data: ContractUpdate, db: Session = Depends(get_db)):
    """계약 정보 수정"""
    contract = db.query(HBContract).filter(HBContract.seq == seq).first()
    if not contract:
        raise HTTPException(status_code=404, detail="Contract not found")

    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(contract, key, value)

    db.commit()
    return {"success": True, "seq": seq}


# ===== VendorAccount =====


@router.post("/accounts/upload")
async def upload_accounts(
    file: UploadFile = File(...),
    vendor: str = Query("alibaba"),
    db: Session = Depends(get_db),
):
    """계정(UID) 데이터 JSON 업로드 (HB API 응답 형식)"""
    content = await file.read()
    data = json.loads(content.decode("utf-8"))

    if isinstance(data, dict) and "data" in data:
        items = data["data"]
    elif isinstance(data, list):
        items = data
    else:
        raise HTTPException(status_code=400, detail="Invalid JSON format")

    inserted = 0
    updated = 0

    for item in items:
        account_id = item.get("id")
        if not account_id:
            continue

        existing = db.query(HBVendorAccount).filter(HBVendorAccount.id == account_id).first()

        account_data = {
            "id": account_id,
            "vendor": vendor,
            "name": item.get("name"),
            "original_name": item.get("original_name"),
            "description": item.get("description"),
            "nickname": item.get("nickname"),
            "master_id": item.get("master_id"),
            "corporation": item.get("corporation"),
            "is_active": item.get("active", True),
            "hb_created_at": parse_datetime(item.get("created_at")),
            "hb_updated_at": parse_datetime(item.get("updated_at")),
        }

        if existing:
            for key, value in account_data.items():
                if key != "id":
                    setattr(existing, key, value)
            updated += 1
        else:
            db.add(HBVendorAccount(**account_data))
            inserted += 1

    db.commit()

    return {"success": True, "inserted": inserted, "updated": updated}


@router.get("/accounts")
def get_accounts(
    vendor: str = Query("alibaba"),
    search: str | None = Query(None),
    has_contract: bool | None = Query(None, description="계약 연결 여부"),
    limit: int = Query(100, le=1000),
    db: Session = Depends(get_db),
):
    """계정(UID) 목록 조회"""
    query = db.query(HBVendorAccount).filter(HBVendorAccount.vendor == vendor)

    if search:
        search_term = f"%{search}%"
        query = query.filter(
            or_(
                HBVendorAccount.id.like(search_term),
                HBVendorAccount.name.like(search_term),
                HBVendorAccount.original_name.like(search_term),
            )
        )

    if has_contract is True:
        query = query.join(AccountContractMapping)
    elif has_contract is False:
        query = query.outerjoin(AccountContractMapping).filter(
            AccountContractMapping.id.is_(None)
        )

    accounts = query.order_by(HBVendorAccount.name).limit(limit).all()

    return [
        {
            "id": a.id,
            "name": a.name,
            "original_name": a.original_name,
            "master_id": a.master_id,
            "corporation": a.corporation,
            "is_active": a.is_active,
        }
        for a in accounts
    ]


@router.get("/accounts/{account_id}")
def get_account(account_id: str, db: Session = Depends(get_db)):
    """계정 상세 조회 (연결된 계약 포함)"""
    account = (
        db.query(HBVendorAccount)
        .options(
            joinedload(HBVendorAccount.contract_mappings).joinedload(
                AccountContractMapping.contract
            )
        )
        .filter(HBVendorAccount.id == account_id)
        .first()
    )

    if not account:
        raise HTTPException(status_code=404, detail="Account not found")

    return {
        "id": account.id,
        "vendor": account.vendor,
        "name": account.name,
        "original_name": account.original_name,
        "master_id": account.master_id,
        "corporation": account.corporation,
        "is_active": account.is_active,
        "contracts": [
            {
                "seq": m.contract.seq,
                "name": m.contract.name,
                "company_name": m.contract.company_name,
                "mapping_type": m.mapping_type,
                "is_manual": m.is_manual,
            }
            for m in account.contract_mappings
            if m.contract
        ],
    }


# ===== Account-Contract Mapping =====


class MappingCreate(BaseModel):
    account_id: str
    contract_seq: int
    mapping_type: str = "all"


@router.post("/mappings")
def create_mapping(data: MappingCreate, db: Session = Depends(get_db)):
    """계정-계약 수동 매핑 생성"""
    # 중복 확인
    existing = (
        db.query(AccountContractMapping)
        .filter(
            AccountContractMapping.account_id == data.account_id,
            AccountContractMapping.contract_seq == data.contract_seq,
        )
        .first()
    )

    if existing:
        raise HTTPException(status_code=400, detail="Mapping already exists")

    # 계정 존재 확인
    account = db.query(HBVendorAccount).filter(HBVendorAccount.id == data.account_id).first()
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")

    # 계약 존재 확인
    contract = db.query(HBContract).filter(HBContract.seq == data.contract_seq).first()
    if not contract:
        raise HTTPException(status_code=404, detail="Contract not found")

    mapping = AccountContractMapping(
        account_id=data.account_id,
        contract_seq=data.contract_seq,
        mapping_type=data.mapping_type,
        is_manual=True,
    )
    db.add(mapping)
    db.commit()

    return {"success": True, "id": mapping.id}


@router.delete("/mappings/{mapping_id}")
def delete_mapping(mapping_id: int, db: Session = Depends(get_db)):
    """계정-계약 매핑 삭제"""
    mapping = db.query(AccountContractMapping).filter(AccountContractMapping.id == mapping_id).first()
    if not mapping:
        raise HTTPException(status_code=404, detail="Mapping not found")

    db.delete(mapping)
    db.commit()

    return {"success": True}


# ===== 빌링 데이터 연결 조회 =====


@router.get("/billing-lookup")
def lookup_billing_info(
    uid: str = Query(..., description="Alibaba UID (user_id 또는 linked_user_id)"),
    vendor: str = Query("alibaba"),
    db: Session = Depends(get_db),
):
    """
    UID로 전표 작성에 필요한 정보 조회

    Returns: 계정 → 계약 → 회사 → BP 코드 연결 정보
    """
    account = (
        db.query(HBVendorAccount)
        .options(
            joinedload(HBVendorAccount.contract_mappings)
            .joinedload(AccountContractMapping.contract)
            .joinedload(HBContract.company)
        )
        .filter(HBVendorAccount.id == uid, HBVendorAccount.vendor == vendor)
        .first()
    )

    if not account:
        return {
            "found": False,
            "uid": uid,
            "message": "UID not found in vendor accounts",
        }

    # 연결된 계약들
    contracts = []
    for mapping in account.contract_mappings:
        contract = mapping.contract
        if not contract:
            continue

        company = contract.company
        contracts.append({
            "contract_seq": contract.seq,
            "contract_name": contract.name,
            "sales_contract_code": contract.sales_contract_code,
            "purchase_contract_code": contract.sales_contract_code.replace("매출", "매입")
            if contract.sales_contract_code
            else None,
            "sales_person": contract.sales_person,
            "corporation": contract.corporation,
            "company_seq": company.seq if company else None,
            "company_name": company.name if company else contract.company_name,
            "bp_number": company.bp_number if company else None,
            "license": company.license if company else None,
        })

    return {
        "found": True,
        "uid": uid,
        "account_name": account.name,
        "master_id": account.master_id,
        "contracts": contracts,
    }
