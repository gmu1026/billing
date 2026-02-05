"""
전표 템플릿 API
- 기존 전표 xlsx 파일을 분석하여 템플릿화
"""

import re
from io import BytesIO
from typing import Any

import numpy as np
import pandas as pd
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.alibaba import BPCode
from app.models.billing_profile import CompanyBillingProfile
from app.models.hb import HBCompany
from app.models.slip import SlipTemplate


def convert_numpy_types(obj: Any) -> Any:
    """numpy 타입을 Python 기본 타입으로 변환"""
    if isinstance(obj, np.integer):
        return int(obj)
    elif isinstance(obj, np.floating):
        return float(obj)
    elif isinstance(obj, np.ndarray):
        return obj.tolist()
    elif isinstance(obj, dict):
        return {k: convert_numpy_types(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [convert_numpy_types(i) for i in obj]
    return obj

router = APIRouter(prefix="/api/slip/templates", tags=["slip-template"])


# === Schemas ===


class ColumnDef(BaseModel):
    """컬럼 정의"""

    index: int  # 컬럼 순서
    name: str  # 내부 필드명 (BUKRS, BLDAT 등)
    header: str  # 원본 헤더 (BUKRS(회사코드) 등)
    data_type: str  # string, number, date
    sample_values: list[Any]  # 샘플 값 (최대 5개)


class TemplateAnalysis(BaseModel):
    """템플릿 분석 결과"""

    slip_type: str  # sales, billing, purchase (추정)
    columns: list[ColumnDef]
    fixed_values: dict[str, Any]
    account_mappings: dict[str, dict[str, str]]
    contract_pattern: dict[str, str] | None
    description_template: str | None
    row_count: int


class TemplateCreate(BaseModel):
    """템플릿 생성 요청"""

    name: str
    slip_type: str
    columns: list[dict[str, Any]]
    fixed_values: dict[str, Any]
    account_mappings: dict[str, dict[str, str]]
    contract_pattern: dict[str, str] | None = None
    description_template: str | None = None
    source_file: str | None = None


class TemplateUpdate(BaseModel):
    """템플릿 수정 요청"""

    name: str | None = None
    columns: list[dict[str, Any]] | None = None
    fixed_values: dict[str, Any] | None = None
    account_mappings: dict[str, dict[str, str]] | None = None
    contract_pattern: dict[str, str] | None = None
    description_template: str | None = None
    is_active: bool | None = None


class TemplateResponse(BaseModel):
    """템플릿 응답"""

    id: int
    name: str
    slip_type: str
    columns: list[dict[str, Any]]
    fixed_values: dict[str, Any]
    account_mappings: dict[str, dict[str, str]]
    contract_pattern: dict[str, str] | None
    description_template: str | None
    source_file: str | None
    is_active: bool

    class Config:
        from_attributes = True


# === 프로필 추출 스키마 ===


class ExtractedProfile(BaseModel):
    """전표에서 추출된 회사별 프로필"""
    bp_number: str
    tax_number: str | None  # 사업자번호
    company_name: str | None  # 거래처명
    currency: str  # 통화 (KRW/USD)
    is_overseas: bool  # 해외법인 여부
    ar_account: str | None  # 채권계정
    hkont_sales: str | None  # 매출계정
    hkont_purchase: str | None  # 매입/원가계정
    tax_code: str | None  # 부가세코드 (청구전표)
    row_count: int  # 해당 BP의 전표 건수
    # 매칭 정보
    hb_company_seq: int | None = None  # HB 회사 seq
    hb_company_name: str | None = None  # HB 회사명
    existing_profile_id: int | None = None  # 기존 프로필 ID


class ProfileExtractionResult(BaseModel):
    """프로필 추출 결과"""
    slip_type: str
    source_file: str
    total_rows: int
    profiles: list[ExtractedProfile]
    matched_count: int  # HB 매칭된 수
    unmatched_count: int  # 매칭 안 된 수


class ProfileApplyRequest(BaseModel):
    """프로필 적용 요청"""
    profiles: list[dict[str, Any]]  # 적용할 프로필 목록
    vendor: str = "alibaba"
    overwrite: bool = False  # 기존 프로필 덮어쓰기


# === Helper Functions ===


def extract_field_name(header: str) -> str:
    """헤더에서 필드명 추출 (예: 'BUKRS(회사코드)' -> 'BUKRS')"""
    match = re.match(r"^([A-Z_]+)", header)
    if match:
        return match.group(1)
    # 한글 헤더
    name_map = {
        "채권계정": "AR_ACCOUNT",
        "사업자번호": "BIZ_NO",
        "거래처명": "PARTNER_NAME",
        "사명": "COMPANY_NAME",
        "공급가": "SUPPLY_AMOUNT",
        "부가세액": "VAT_AMOUNT",
        "매출계약번호": "ZZSCONID_ALT",
        "추가 수신인": "EXTRA_RECIPIENT",
    }
    return name_map.get(header, header.replace(" ", "_").upper())


def detect_slip_type(columns: list[str]) -> str:
    """컬럼 구성으로 전표 유형 추정"""
    col_set = set(columns)

    # 청구 전표: MWSKZ(부가세코드), ZTERM(수금조건) 있음
    if any("MWSKZ" in c or "부가세코드" in c for c in columns):
        return "billing"

    # 원가 전표: KOSTL(코스트센터), BKTXT(전표적요) 있음
    if any("KOSTL" in c or "코스트센터" in c for c in columns):
        return "purchase"

    if any("BKTXT" in c for c in columns):
        return "purchase"

    # 매출 전표: 채권계정, SGTXT(전표적요) 있음
    if any("채권계정" in c for c in columns):
        return "sales"

    return "sales"  # 기본값


def detect_data_type(series: pd.Series) -> str:
    """데이터 타입 추정"""
    non_null = series.dropna()
    if len(non_null) == 0:
        return "string"

    sample = non_null.iloc[0]

    # 날짜 체크 (8자리 숫자 or datetime)
    if isinstance(sample, (pd.Timestamp, int)):
        if isinstance(sample, int) and 20000000 <= sample <= 20500000:
            return "date"
        if isinstance(sample, pd.Timestamp):
            return "date"

    # 숫자 체크
    if pd.api.types.is_numeric_dtype(series):
        return "number"

    return "string"


def analyze_template(df: pd.DataFrame, filename: str) -> TemplateAnalysis:
    """엑셀 데이터에서 템플릿 분석"""
    columns = []
    fixed_values = {}
    account_mappings = {"domestic": {}, "overseas": {}}

    slip_type = detect_slip_type(list(df.columns))

    for idx, header in enumerate(df.columns):
        if pd.isna(header) or str(header).startswith("Unnamed"):
            continue

        field_name = extract_field_name(str(header))
        data_type = detect_data_type(df.iloc[:, idx])

        # 샘플 값 추출 (최대 5개 고유값)
        unique_vals = df.iloc[:, idx].dropna().unique()[:5]
        sample_values = []
        for v in unique_vals:
            if isinstance(v, pd.Timestamp):
                sample_values.append(v.isoformat())
            else:
                sample_values.append(convert_numpy_types(v))

        columns.append(
            ColumnDef(
                index=idx,
                name=field_name,
                header=str(header),
                data_type=data_type,
                sample_values=sample_values,
            )
        )

        # 고정값 추출 (모든 행이 동일한 값)
        unique_count = df.iloc[:, idx].nunique()
        if unique_count == 1 and field_name not in [
            "SEQNO",
            "BLDAT",
            "BUDAT",
            "WRBTR",
            "DMBTR_C",
        ]:
            val = df.iloc[:, idx].dropna().iloc[0] if len(df.iloc[:, idx].dropna()) > 0 else None
            if val is not None and not pd.isna(val):
                # Timestamp를 문자열로 변환
                if isinstance(val, pd.Timestamp):
                    val = val.strftime("%Y%m%d")
                else:
                    val = convert_numpy_types(val)
                fixed_values[field_name] = val

    # 계정 매핑 분석
    for col_def in columns:
        col_data = df[col_def.header]

        # 통화별 계정 분석
        if col_def.name in ["HKONT", "AR_ACCOUNT", "채권계정"]:
            unique_accounts = col_data.unique()
            if len(unique_accounts) == 2:
                # KRW/USD 행 구분해서 매핑
                waers_col = next((c for c in df.columns if "WAERS" in str(c)), None)
                if waers_col:
                    for acc in unique_accounts:
                        acc_rows = df[col_data == acc]
                        currencies = acc_rows[waers_col].unique()
                        if "KRW" in currencies:
                            if "매출" in col_def.header or col_def.name == "HKONT":
                                account_mappings["domestic"]["revenue"] = str(acc)
                            else:
                                account_mappings["domestic"]["receivable"] = str(acc)
                        elif "USD" in currencies:
                            if "매출" in col_def.header or col_def.name == "HKONT":
                                account_mappings["overseas"]["revenue"] = str(acc)
                            else:
                                account_mappings["overseas"]["receivable"] = str(acc)

    # 채권계정 분석 (매출전표)
    ar_col = next((c for c in columns if c.name == "AR_ACCOUNT" or "채권계정" in c.header), None)
    if ar_col:
        ar_data = df[ar_col.header]
        unique_ar = ar_data.unique()
        waers_col = next((c for c in df.columns if "WAERS" in str(c)), None)
        if waers_col and len(unique_ar) >= 2:
            for acc in unique_ar:
                acc_rows = df[ar_data == acc]
                currencies = acc_rows[waers_col].unique()
                if "KRW" in currencies:
                    account_mappings["domestic"]["receivable"] = str(int(acc)) if pd.notna(acc) else None
                elif "USD" in currencies:
                    account_mappings["overseas"]["receivable"] = str(int(acc)) if pd.notna(acc) else None

    # 매출계정 분석
    hkont_col = next((c for c in columns if "HKONT" in c.name and "매출" in c.header), None)
    if hkont_col:
        hkont_data = df[hkont_col.header]
        unique_hkont = hkont_data.unique()
        waers_col = next((c for c in df.columns if "WAERS" in str(c)), None)
        if waers_col and len(unique_hkont) >= 2:
            for acc in unique_hkont:
                acc_rows = df[hkont_data == acc]
                currencies = acc_rows[waers_col].unique()
                if "KRW" in currencies:
                    account_mappings["domestic"]["revenue"] = str(int(acc)) if pd.notna(acc) else None
                elif "USD" in currencies:
                    account_mappings["overseas"]["revenue"] = str(int(acc)) if pd.notna(acc) else None

    # 계약번호 패턴
    contract_pattern = {}
    sconid_col = next((c for c in columns if "ZZSCONID" in c.name or "매출계약번호" in c.header), None)
    if sconid_col and len(sconid_col.sample_values) > 0:
        contract_pattern["sales"] = str(sconid_col.sample_values[0])

    pconid_col = next((c for c in columns if "ZZPCONID" in c.name or "매입계약번호" in c.header), None)
    if pconid_col and len(pconid_col.sample_values) > 0:
        contract_pattern["purchase"] = str(pconid_col.sample_values[0])

    # 전표적요 템플릿 추출
    desc_col = next((c for c in columns if c.name in ["SGTXT", "BKTXT"]), None)
    desc_template = None
    if desc_col and len(desc_col.sample_values) > 0:
        sample_desc = str(desc_col.sample_values[0])
        # 월 숫자를 {month}로 치환
        desc_template = re.sub(r"(\d{1,2})월", "{month}월", sample_desc)
        desc_template = re.sub(r"\(\d\)", "", desc_template)  # (1) 같은 것 제거

    return TemplateAnalysis(
        slip_type=slip_type,
        columns=columns,
        fixed_values=convert_numpy_types(fixed_values),
        account_mappings=convert_numpy_types(account_mappings),
        contract_pattern=contract_pattern if contract_pattern else None,
        description_template=desc_template,
        row_count=len(df),
    )


# === API Endpoints ===


@router.post("/analyze", response_model=TemplateAnalysis)
async def analyze_slip_template(file: UploadFile = File(...)):
    """
    전표 xlsx 파일을 분석하여 템플릿 정보 추출 (저장하지 않음)
    """
    if not file.filename.endswith((".xlsx", ".xls")):
        raise HTTPException(status_code=400, detail="xlsx 또는 xls 파일만 지원합니다.")

    content = await file.read()
    df = pd.read_excel(BytesIO(content), header=0)

    analysis = analyze_template(df, file.filename)
    return analysis


@router.post("/", response_model=TemplateResponse)
async def create_template(template: TemplateCreate, db: Session = Depends(get_db)):
    """템플릿 저장"""
    db_template = SlipTemplate(
        name=template.name,
        slip_type=template.slip_type,
        columns=template.columns,
        fixed_values=template.fixed_values,
        account_mappings=template.account_mappings,
        contract_pattern=template.contract_pattern,
        description_template=template.description_template,
        source_file=template.source_file,
    )
    db.add(db_template)
    db.commit()
    db.refresh(db_template)
    return db_template


@router.post("/import", response_model=TemplateResponse)
async def import_template(
    file: UploadFile = File(...),
    name: str | None = None,
    db: Session = Depends(get_db),
):
    """
    전표 xlsx 파일을 분석하고 바로 템플릿으로 저장
    """
    if not file.filename.endswith((".xlsx", ".xls")):
        raise HTTPException(status_code=400, detail="xlsx 또는 xls 파일만 지원합니다.")

    content = await file.read()
    df = pd.read_excel(BytesIO(content), header=0)

    analysis = analyze_template(df, file.filename)

    template_name = name or file.filename.replace(".xlsx", "").replace(".xls", "")

    # 동일 slip_type의 기존 템플릿이 있으면 비활성화
    existing = db.execute(
        select(SlipTemplate).where(
            SlipTemplate.slip_type == analysis.slip_type, SlipTemplate.is_active == True
        )
    ).scalars().all()
    for t in existing:
        t.is_active = False

    db_template = SlipTemplate(
        name=template_name,
        slip_type=analysis.slip_type,
        columns=[col.model_dump() for col in analysis.columns],
        fixed_values=analysis.fixed_values,
        account_mappings=analysis.account_mappings,
        contract_pattern=analysis.contract_pattern,
        description_template=analysis.description_template,
        source_file=file.filename,
    )
    db.add(db_template)
    db.commit()
    db.refresh(db_template)
    return db_template


@router.get("/", response_model=list[TemplateResponse])
async def list_templates(
    slip_type: str | None = None,
    active_only: bool = True,
    db: Session = Depends(get_db),
):
    """템플릿 목록 조회"""
    query = select(SlipTemplate)
    if slip_type:
        query = query.where(SlipTemplate.slip_type == slip_type)
    if active_only:
        query = query.where(SlipTemplate.is_active == True)

    templates = db.execute(query.order_by(SlipTemplate.id.desc())).scalars().all()
    return templates


# === 파일 경로 기반 API (동적 라우트보다 먼저 정의) ===


class FileInfo(BaseModel):
    """파일 정보"""
    filename: str
    path: str
    size: int
    slip_type_guess: str | None


@router.get("/scan-files", response_model=list[FileInfo])
async def scan_template_files():
    """data_sample 디렉토리에서 전표 양식 파일 검색"""
    from pathlib import Path

    # data_sample 디렉토리 경로
    base_dir = Path(__file__).parent.parent.parent.parent / "data_sample"

    if not base_dir.exists():
        return []

    files = []
    for f in base_dir.glob("*.xlsx"):
        # 파일명에서 전표 유형 추정
        fname_lower = f.name.lower()
        slip_type_guess = None
        if "매출" in f.name or "sales" in fname_lower:
            slip_type_guess = "sales"
        elif "청구" in f.name or "billing" in fname_lower:
            slip_type_guess = "billing"
        elif "원가" in f.name or "purchase" in fname_lower or "cost" in fname_lower:
            slip_type_guess = "purchase"

        files.append(FileInfo(
            filename=f.name,
            path=str(f),
            size=f.stat().st_size,
            slip_type_guess=slip_type_guess,
        ))

    # 파일명 순 정렬
    files.sort(key=lambda x: x.filename)
    return files


@router.post("/analyze-path", response_model=TemplateAnalysis)
async def analyze_template_from_path(file_path: str):
    """파일 경로에서 전표 템플릿 분석"""
    from pathlib import Path

    path = Path(file_path)
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"파일을 찾을 수 없습니다: {file_path}")

    if not path.suffix.lower() in [".xlsx", ".xls"]:
        raise HTTPException(status_code=400, detail="xlsx 또는 xls 파일만 지원합니다.")

    df = pd.read_excel(path, header=0)
    analysis = analyze_template(df, path.name)
    return analysis


@router.post("/import-path", response_model=TemplateResponse)
async def import_template_from_path(
    file_path: str,
    name: str | None = None,
    db: Session = Depends(get_db),
):
    """파일 경로에서 전표 템플릿 분석 후 저장"""
    from pathlib import Path

    path = Path(file_path)
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"파일을 찾을 수 없습니다: {file_path}")

    if not path.suffix.lower() in [".xlsx", ".xls"]:
        raise HTTPException(status_code=400, detail="xlsx 또는 xls 파일만 지원합니다.")

    df = pd.read_excel(path, header=0)
    analysis = analyze_template(df, path.name)

    template_name = name or path.stem  # 확장자 제외한 파일명

    # 동일 slip_type의 기존 템플릿이 있으면 비활성화
    existing = db.execute(
        select(SlipTemplate).where(
            SlipTemplate.slip_type == analysis.slip_type, SlipTemplate.is_active == True
        )
    ).scalars().all()
    for t in existing:
        t.is_active = False

    db_template = SlipTemplate(
        name=template_name,
        slip_type=analysis.slip_type,
        columns=[col.model_dump() for col in analysis.columns],
        fixed_values=analysis.fixed_values,
        account_mappings=analysis.account_mappings,
        contract_pattern=analysis.contract_pattern,
        description_template=analysis.description_template,
        source_file=path.name,
    )
    db.add(db_template)
    db.commit()
    db.refresh(db_template)
    return db_template


# === 프로필 추출 API ===


def extract_profiles_from_df(df: pd.DataFrame, slip_type: str, db: Session) -> list[ExtractedProfile]:
    """DataFrame에서 BP별 프로필 정보 추출"""
    profiles = []

    # 컬럼명 찾기
    partner_col = next((c for c in df.columns if "PARTNER" in str(c)), None)
    waers_col = next((c for c in df.columns if "WAERS" in str(c)), None)
    tax_no_col = next((c for c in df.columns if "사업자번호" in str(c)), None)
    name_col = next((c for c in df.columns if "거래처명" in str(c) or "사명" in str(c)), None)

    # 계정 컬럼
    ar_col = next((c for c in df.columns if "채권계정" in str(c)), None)
    hkont_sales_col = next((c for c in df.columns if "HKONT" in str(c) and "매출" in str(c)), None)
    hkont_purchase_col = next((c for c in df.columns if "HKONT" in str(c) and ("원가" in str(c) or "상대" in str(c))), None)
    tax_code_col = next((c for c in df.columns if "MWSKZ" in str(c) or "부가세코드" in str(c)), None)

    if not partner_col:
        return profiles

    # BP별 그룹화
    grouped = df.groupby(partner_col)

    for bp, group in grouped:
        if pd.isna(bp):
            continue

        bp_str = str(int(bp)) if isinstance(bp, (int, float)) else str(bp)

        # 통화 (첫 번째 값 또는 가장 많은 값)
        currency = "KRW"
        if waers_col:
            currencies = group[waers_col].dropna()
            if len(currencies) > 0:
                currency = str(currencies.mode().iloc[0]) if len(currencies.mode()) > 0 else str(currencies.iloc[0])

        is_overseas = currency != "KRW"

        # 사업자번호
        tax_number = None
        if tax_no_col:
            tax_vals = group[tax_no_col].dropna()
            if len(tax_vals) > 0:
                tax_number = str(tax_vals.iloc[0])

        # 거래처명
        company_name = None
        if name_col:
            name_vals = group[name_col].dropna()
            if len(name_vals) > 0:
                company_name = str(name_vals.iloc[0])

        # 계정코드 (가장 많이 사용된 값)
        ar_account = None
        if ar_col:
            ar_vals = group[ar_col].dropna()
            if len(ar_vals) > 0:
                ar_account = str(int(ar_vals.mode().iloc[0])) if len(ar_vals.mode()) > 0 else str(int(ar_vals.iloc[0]))

        hkont_sales = None
        if hkont_sales_col:
            hkont_vals = group[hkont_sales_col].dropna()
            if len(hkont_vals) > 0:
                hkont_sales = str(int(hkont_vals.mode().iloc[0])) if len(hkont_vals.mode()) > 0 else str(int(hkont_vals.iloc[0]))

        hkont_purchase = None
        if hkont_purchase_col:
            hkont_vals = group[hkont_purchase_col].dropna()
            if len(hkont_vals) > 0:
                hkont_purchase = str(int(hkont_vals.mode().iloc[0])) if len(hkont_vals.mode()) > 0 else str(int(hkont_vals.iloc[0]))

        tax_code = None
        if tax_code_col:
            tax_vals = group[tax_code_col].dropna()
            if len(tax_vals) > 0:
                tax_code = str(tax_vals.mode().iloc[0]) if len(tax_vals.mode()) > 0 else str(tax_vals.iloc[0])

        # HB 회사 매칭 (BP번호로)
        hb_company = db.execute(
            select(HBCompany).where(HBCompany.bp_number == bp_str)
        ).scalar_one_or_none()

        # 기존 프로필 확인
        existing_profile = None
        if hb_company:
            existing_profile = db.execute(
                select(CompanyBillingProfile).where(
                    CompanyBillingProfile.company_seq == hb_company.seq
                )
            ).scalar_one_or_none()

        profiles.append(ExtractedProfile(
            bp_number=bp_str,
            tax_number=tax_number,
            company_name=company_name,
            currency=currency,
            is_overseas=is_overseas,
            ar_account=ar_account,
            hkont_sales=hkont_sales,
            hkont_purchase=hkont_purchase,
            tax_code=tax_code,
            row_count=len(group),
            hb_company_seq=hb_company.seq if hb_company else None,
            hb_company_name=hb_company.name if hb_company else None,
            existing_profile_id=existing_profile.id if existing_profile else None,
        ))

    # row_count 내림차순 정렬
    profiles.sort(key=lambda x: x.row_count, reverse=True)
    return profiles


@router.post("/extract-profiles", response_model=ProfileExtractionResult)
async def extract_profiles_from_file(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """전표 파일에서 BP별 프로필 정보 추출"""
    if not file.filename.endswith((".xlsx", ".xls")):
        raise HTTPException(status_code=400, detail="xlsx 또는 xls 파일만 지원합니다.")

    content = await file.read()
    df = pd.read_excel(BytesIO(content), header=0)

    # 전표 유형 감지
    slip_type = detect_slip_type(list(df.columns))

    profiles = extract_profiles_from_df(df, slip_type, db)

    matched = sum(1 for p in profiles if p.hb_company_seq is not None)
    unmatched = len(profiles) - matched

    return ProfileExtractionResult(
        slip_type=slip_type,
        source_file=file.filename,
        total_rows=len(df),
        profiles=profiles,
        matched_count=matched,
        unmatched_count=unmatched,
    )


@router.post("/extract-profiles-path", response_model=ProfileExtractionResult)
async def extract_profiles_from_path(
    file_path: str,
    db: Session = Depends(get_db),
):
    """파일 경로에서 BP별 프로필 정보 추출"""
    from pathlib import Path

    path = Path(file_path)
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"파일을 찾을 수 없습니다: {file_path}")

    df = pd.read_excel(path, header=0)

    # 전표 유형 감지
    slip_type = detect_slip_type(list(df.columns))

    profiles = extract_profiles_from_df(df, slip_type, db)

    matched = sum(1 for p in profiles if p.hb_company_seq is not None)
    unmatched = len(profiles) - matched

    return ProfileExtractionResult(
        slip_type=slip_type,
        source_file=path.name,
        total_rows=len(df),
        profiles=profiles,
        matched_count=matched,
        unmatched_count=unmatched,
    )


@router.post("/apply-profiles")
async def apply_profiles(
    request: ProfileApplyRequest,
    db: Session = Depends(get_db),
):
    """추출된 프로필을 BillingProfile로 저장"""
    created = 0
    updated = 0
    skipped = 0

    for profile_data in request.profiles:
        company_seq = profile_data.get("hb_company_seq")
        if not company_seq:
            skipped += 1
            continue

        # 기존 프로필 확인
        existing = db.execute(
            select(CompanyBillingProfile).where(
                CompanyBillingProfile.company_seq == company_seq,
                CompanyBillingProfile.vendor == request.vendor,
            )
        ).scalar_one_or_none()

        if existing:
            if request.overwrite:
                # 업데이트
                if profile_data.get("currency"):
                    existing.currency = profile_data["currency"]
                if profile_data.get("ar_account"):
                    existing.ar_account = profile_data["ar_account"]
                if profile_data.get("hkont_sales"):
                    existing.hkont_sales = profile_data["hkont_sales"]
                if profile_data.get("hkont_purchase"):
                    existing.hkont_purchase = profile_data["hkont_purchase"]
                updated += 1
            else:
                skipped += 1
        else:
            # 신규 생성
            new_profile = CompanyBillingProfile(
                company_seq=company_seq,
                vendor=request.vendor,
                currency=profile_data.get("currency", "KRW"),
                ar_account=profile_data.get("ar_account"),
                hkont_sales=profile_data.get("hkont_sales"),
                hkont_purchase=profile_data.get("hkont_purchase"),
            )
            db.add(new_profile)
            created += 1

    db.commit()

    return {
        "success": True,
        "created": created,
        "updated": updated,
        "skipped": skipped,
    }


# === 동적 라우트 (맨 마지막에 정의) ===


@router.get("/{template_id}", response_model=TemplateResponse)
async def get_template(template_id: int, db: Session = Depends(get_db)):
    """템플릿 상세 조회"""
    template = db.get(SlipTemplate, template_id)
    if not template:
        raise HTTPException(status_code=404, detail="템플릿을 찾을 수 없습니다.")
    return template


@router.patch("/{template_id}", response_model=TemplateResponse)
async def update_template(
    template_id: int, update: TemplateUpdate, db: Session = Depends(get_db)
):
    """템플릿 수정"""
    template = db.get(SlipTemplate, template_id)
    if not template:
        raise HTTPException(status_code=404, detail="템플릿을 찾을 수 없습니다.")

    update_data = update.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(template, key, value)

    db.commit()
    db.refresh(template)
    return template


@router.delete("/{template_id}")
async def delete_template(template_id: int, db: Session = Depends(get_db)):
    """템플릿 삭제"""
    template = db.get(SlipTemplate, template_id)
    if not template:
        raise HTTPException(status_code=404, detail="템플릿을 찾을 수 없습니다.")

    db.delete(template)
    db.commit()
    return {"message": "삭제되었습니다."}
