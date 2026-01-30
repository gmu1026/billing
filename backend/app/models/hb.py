"""
HB (Hubble) 연동 데이터 모델

관계:
- Company (1) --- (*) Contract
- Contract (*) --- (*) VendorAccount (through AccountContractMapping)
- Company (1) --- (0..1) BPCode (매핑)
- VendorAccount.id = AlibabaBilling.user_id 또는 linked_user_id
"""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class HBCompany(Base):
    """회사 정보 (HB company)"""

    __tablename__ = "hb_companies"

    seq: Mapped[int] = mapped_column(Integer, primary_key=True)  # HB의 seq 그대로 사용
    vendor: Mapped[str] = mapped_column(String(50), index=True, default="alibaba")  # service_type
    name: Mapped[str] = mapped_column(String(200))
    license: Mapped[str | None] = mapped_column(String(50), index=True)  # 사업자번호
    address: Mapped[str | None] = mapped_column(String(500))
    ceo_name: Mapped[str | None] = mapped_column(String(100))
    phone: Mapped[str | None] = mapped_column(String(50))
    email: Mapped[str | None] = mapped_column(String(200))
    website: Mapped[str | None] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text)

    # 사업자 정보
    business_status: Mapped[str | None] = mapped_column(String(100))  # 업태
    business_type: Mapped[str | None] = mapped_column(String(100))  # 종목
    industry: Mapped[str | None] = mapped_column(String(100))
    industry_segment: Mapped[str | None] = mapped_column(String(100))

    # HB 고유 필드
    hb_customer_code: Mapped[str | None] = mapped_column(String(50))  # HB의 customer_code
    hb_type: Mapped[int | None] = mapped_column(Integer)  # 1: 내부, 2: 외부 등
    hb_status: Mapped[int | None] = mapped_column(Integer)

    # 담당자 정보
    manager_name: Mapped[str | None] = mapped_column(String(100))
    manager_email: Mapped[str | None] = mapped_column(String(200))
    manager_tel: Mapped[str | None] = mapped_column(String(50))

    # BP 코드 매핑 (수동 연결)
    bp_number: Mapped[str | None] = mapped_column(String(20), index=True)

    # 내부비용 여부 (매출전표 제외, 매입전표 별도 집계)
    is_internal_cost: Mapped[bool] = mapped_column(Boolean, default=False)

    # 해외법인 여부 (사업자번호 형식으로 구분 가능)
    is_overseas: Mapped[bool] = mapped_column(Boolean, default=False)

    # 기본 통화
    default_currency: Mapped[str] = mapped_column(String(10), default="KRW")

    # 메타데이터
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    hb_created_at: Mapped[datetime | None] = mapped_column(DateTime)
    hb_updated_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    # Relationships
    contracts: Mapped[list["HBContract"]] = relationship("HBContract", back_populates="company")


class HBContract(Base):
    """계약 정보 (HB contract)"""

    __tablename__ = "hb_contracts"

    seq: Mapped[int] = mapped_column(Integer, primary_key=True)  # HB의 seq 그대로 사용
    vendor: Mapped[str] = mapped_column(String(50), index=True, default="alibaba")
    name: Mapped[str] = mapped_column(String(200))
    company_name: Mapped[str | None] = mapped_column(String(200))  # 원본 company 이름

    # 회사 연결
    company_seq: Mapped[int | None] = mapped_column(Integer, ForeignKey("hb_companies.seq"))
    company: Mapped["HBCompany | None"] = relationship("HBCompany", back_populates="contracts")

    # 계약 정보
    corporation: Mapped[str | None] = mapped_column(String(50))  # international/china
    charge_currency: Mapped[str] = mapped_column(String(10), default="USD")
    discount_rate: Mapped[float] = mapped_column(Float, default=0)
    exchange_type: Mapped[str | None] = mapped_column(String(50))

    # 담당자 (영업사원)
    sales_person: Mapped[str | None] = mapped_column(String(100))  # the_person_in_charge

    # 이메일 수신자
    email_to: Mapped[str | None] = mapped_column(Text)  # JSON array
    email_cc: Mapped[str | None] = mapped_column(Text)  # JSON array

    # 전표 관련 설정
    sales_contract_code: Mapped[str | None] = mapped_column(String(30))  # 매출계약번호 (예: 매출ALI999)
    tax_invoice_month: Mapped[str | None] = mapped_column(String(20))  # next_month / current_month

    # 상태
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    is_auto_reseller_margin: Mapped[bool] = mapped_column(Boolean, default=True)

    # HB 메타데이터
    hb_created_at: Mapped[datetime | None] = mapped_column(DateTime)
    hb_updated_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    # Relationships
    account_mappings: Mapped[list["AccountContractMapping"]] = relationship(
        "AccountContractMapping", back_populates="contract"
    )


class HBVendorAccount(Base):
    """클라우드 벤더 계정 (HB account) - UID"""

    __tablename__ = "hb_vendor_accounts"

    id: Mapped[str] = mapped_column(String(50), primary_key=True)  # UID
    vendor: Mapped[str] = mapped_column(String(50), index=True, default="alibaba")
    name: Mapped[str | None] = mapped_column(String(300))
    original_name: Mapped[str | None] = mapped_column(String(300))
    description: Mapped[str | None] = mapped_column(Text)
    nickname: Mapped[str | None] = mapped_column(String(100))

    # 마스터 계정 (서브 계정인 경우)
    master_id: Mapped[str | None] = mapped_column(String(50), index=True)

    # 법인 구분
    corporation: Mapped[str | None] = mapped_column(String(50))  # international/china

    # 상태
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # HB 메타데이터
    hb_created_at: Mapped[datetime | None] = mapped_column(DateTime)
    hb_updated_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    # Relationships
    contract_mappings: Mapped[list["AccountContractMapping"]] = relationship(
        "AccountContractMapping", back_populates="account"
    )


class AccountContractMapping(Base):
    """계정-계약 매핑 (N:N)"""

    __tablename__ = "account_contract_mappings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    account_id: Mapped[str] = mapped_column(String(50), ForeignKey("hb_vendor_accounts.id"), index=True)
    contract_seq: Mapped[int] = mapped_column(Integer, ForeignKey("hb_contracts.seq"), index=True)

    # 매핑 타입 (all: 전체, specific: 특정 프로젝트만 등)
    mapping_type: Mapped[str] = mapped_column(String(20), default="all")
    projects: Mapped[str | None] = mapped_column(Text)  # JSON array of project IDs

    # 수동 매핑 여부
    is_manual: Mapped[bool] = mapped_column(Boolean, default=False)

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    # Relationships
    account: Mapped["HBVendorAccount"] = relationship("HBVendorAccount", back_populates="contract_mappings")
    contract: Mapped["HBContract"] = relationship("HBContract", back_populates="account_mappings")
