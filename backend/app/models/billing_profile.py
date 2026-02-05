"""
회사별 및 계약별 청구 설정 및 예치금 관리 모델
추가 비용, 분할 청구, 일할 계산 기능 포함
"""

from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.hb import HBCompany, HBContract, HBVendorAccount


class PaymentType(str, Enum):
    """결제 방식 - 부가세코드 연동"""

    DEPOSIT = "deposit"  # 예치금 → A1
    TAX_INVOICE = "tax_invoice"  # 세금계산서 → A1
    CARD = "card"  # 카드결제 → A3
    REVERSE_ISSUE = "reverse_issue"  # 역발행 → A1
    OVERSEAS_INVOICE = "overseas_invoice"  # 해외인보이스 → B1


# 결제 방식별 부가세코드 매핑
PAYMENT_TYPE_TAX_CODE = {
    PaymentType.DEPOSIT.value: "A1",
    PaymentType.TAX_INVOICE.value: "A1",
    PaymentType.CARD.value: "A3",
    PaymentType.REVERSE_ISSUE.value: "A1",
    PaymentType.OVERSEAS_INVOICE.value: "B1",
}


class CompanyBillingProfile(Base):
    """회사+CSP별 청구 설정"""

    __tablename__ = "company_billing_profiles"
    __table_args__ = (
        UniqueConstraint("company_seq", "vendor", name="uq_company_vendor"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    company_seq: Mapped[int] = mapped_column(Integer, ForeignKey("hb_companies.seq"), index=True)
    vendor: Mapped[str] = mapped_column(String(50), index=True)  # alibaba, gcp, etc.

    # 결제 방식 (부가세코드 연동)
    payment_type: Mapped[str] = mapped_column(String(20), default=PaymentType.TAX_INVOICE.value)

    # 약정 여부
    has_sales_agreement: Mapped[bool] = mapped_column(Boolean, default=False)  # 매출 약정
    has_purchase_agreement: Mapped[bool] = mapped_column(Boolean, default=False)  # 매입 약정

    # 통화 설정
    currency: Mapped[str] = mapped_column(String(10), default="KRW")

    # 계정코드 (회사별 커스텀, 없으면 기본값 사용)
    hkont_sales: Mapped[str | None] = mapped_column(String(20))  # 매출 계정
    hkont_purchase: Mapped[str | None] = mapped_column(String(20))  # 매입 계정
    ar_account: Mapped[str | None] = mapped_column(String(20))  # 채권과목
    ap_account: Mapped[str | None] = mapped_column(String(20))  # 채무과목

    # 메모
    note: Mapped[str | None] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    # Relationships
    deposits: Mapped[list["Deposit"]] = relationship("Deposit", back_populates="profile")


class Deposit(Base):
    """예치금 충전 기록"""

    __tablename__ = "deposits"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # 회사별 프로필 (레거시)
    profile_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("company_billing_profiles.id"), index=True)

    # 계약별 프로필 (신규)
    contract_profile_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("contract_billing_profiles.id"), index=True
    )

    # 충전 정보
    deposit_date: Mapped[date] = mapped_column(Date, index=True)
    amount: Mapped[float] = mapped_column(Float)  # 충전 금액
    currency: Mapped[str] = mapped_column(String(10), default="KRW")
    exchange_rate: Mapped[float | None] = mapped_column(Float)  # 해외: 충전 시점 환율

    # 잔액 추적 (FIFO용)
    remaining_amount: Mapped[float] = mapped_column(Float)  # 남은 금액
    is_exhausted: Mapped[bool] = mapped_column(Boolean, default=False)  # 소진 완료

    # 참조
    reference: Mapped[str | None] = mapped_column(String(100))  # 입금 참조번호 등
    description: Mapped[str | None] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    # Relationships
    profile: Mapped["CompanyBillingProfile | None"] = relationship(
        "CompanyBillingProfile", back_populates="deposits"
    )
    contract_profile: Mapped["ContractBillingProfile | None"] = relationship(
        "ContractBillingProfile",
        back_populates="deposits",
        foreign_keys=[contract_profile_id],
    )
    usages: Mapped[list["DepositUsage"]] = relationship("DepositUsage", back_populates="deposit")


class ExchangeRateType(str, Enum):
    """해외인보이스 환율 적용 기준"""

    BILLING_DATE = "billing_date"  # 빌링월 말일
    DOCUMENT_DATE = "document_date"  # 전표 증빙일
    CUSTOM_DATE = "custom_date"  # 수동 지정


class ContractBillingProfile(Base):
    """계약별 청구 설정 (계약 단위로 프로필 관리)"""

    __tablename__ = "contract_billing_profiles"
    __table_args__ = (
        UniqueConstraint("contract_seq", "vendor", name="uq_contract_vendor"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    contract_seq: Mapped[int] = mapped_column(Integer, ForeignKey("hb_contracts.seq"), index=True)
    vendor: Mapped[str] = mapped_column(String(50), index=True)  # alibaba, gcp, etc.

    # 결제 방식 (부가세코드 연동)
    payment_type: Mapped[str] = mapped_column(String(20), default=PaymentType.TAX_INVOICE.value)

    # 약정 여부
    has_sales_agreement: Mapped[bool] = mapped_column(Boolean, default=False)  # 매출 약정
    has_purchase_agreement: Mapped[bool] = mapped_column(Boolean, default=False)  # 매입 약정

    # 통화 설정
    currency: Mapped[str] = mapped_column(String(10), default="KRW")

    # 해외인보이스 환율 적용 설정
    exchange_rate_type: Mapped[str | None] = mapped_column(String(20))  # 환율 적용 기준
    custom_exchange_rate_date: Mapped[date | None] = mapped_column(Date)  # 수동 지정 시 환율 적용일

    # 계정코드 (계약별 커스텀)
    hkont_sales: Mapped[str | None] = mapped_column(String(20))  # 매출 계정
    hkont_purchase: Mapped[str | None] = mapped_column(String(20))  # 매입 계정
    ar_account: Mapped[str | None] = mapped_column(String(20))  # 채권과목
    ap_account: Mapped[str | None] = mapped_column(String(20))  # 채무과목

    # 라운딩 규칙 오버라이드 (None이면 벤더 기본값 사용)
    rounding_rule_override: Mapped[str | None] = mapped_column(String(20))

    # 일할 계산 오버라이드 (enabled/disabled/None=벤더설정 따름)
    pro_rata_override: Mapped[str | None] = mapped_column(String(20))

    # 메모
    note: Mapped[str | None] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    # Relationships
    contract: Mapped["HBContract"] = relationship("HBContract", back_populates="billing_profiles")
    deposits: Mapped[list["Deposit"]] = relationship(
        "Deposit",
        back_populates="contract_profile",
        foreign_keys="Deposit.contract_profile_id",
    )


class DepositUsage(Base):
    """예치금 사용 기록"""

    __tablename__ = "deposit_usages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    deposit_id: Mapped[int] = mapped_column(Integer, ForeignKey("deposits.id"), index=True)

    # 사용 정보
    usage_date: Mapped[date] = mapped_column(Date, index=True)
    amount: Mapped[float] = mapped_column(Float)  # 사용 금액
    amount_krw: Mapped[float | None] = mapped_column(Float)  # KRW 환산액 (해외의 경우)

    # 빌링 연결
    billing_cycle: Mapped[str | None] = mapped_column(String(10))  # YYYYMM
    slip_batch_id: Mapped[str | None] = mapped_column(String(50))  # 전표 배치 ID

    # 참조
    uid: Mapped[str | None] = mapped_column(String(50))  # 빌링 UID
    description: Mapped[str | None] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    # Relationships
    deposit: Mapped["Deposit"] = relationship("Deposit", back_populates="usages")


# ===== 추가 비용 모델 =====


class ChargeType(str, Enum):
    """추가 비용 유형"""

    CREDIT = "credit"  # 크레딧 (음수 = 차감)
    SUPPORT_FEE = "support_fee"  # 서포트 비용
    SETUP_FEE = "setup_fee"  # 셋업 비용
    OTHER = "other"  # 기타


class RecurrenceType(str, Enum):
    """반복 유형"""

    RECURRING = "recurring"  # 매월 반복
    ONE_TIME = "one_time"  # 일회성
    PERIOD = "period"  # 기간 지정


class AdditionalCharge(Base):
    """추가 비용 항목 (RAW 빌링 외 추가 비용)"""

    __tablename__ = "additional_charges"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    contract_seq: Mapped[int] = mapped_column(Integer, ForeignKey("hb_contracts.seq"), index=True)

    # 품목 정보
    name: Mapped[str] = mapped_column(String(200))  # 품목명
    description: Mapped[str | None] = mapped_column(Text)

    # 비용 유형
    charge_type: Mapped[str] = mapped_column(String(20), default=ChargeType.OTHER.value)

    # 금액 (음수 = 차감, 예: 크레딧)
    amount: Mapped[float] = mapped_column(Float)
    currency: Mapped[str] = mapped_column(String(10), default="USD")

    # 반복 유형 및 기간
    recurrence_type: Mapped[str] = mapped_column(String(20), default=RecurrenceType.ONE_TIME.value)
    start_date: Mapped[date | None] = mapped_column(Date)  # 적용 시작일
    end_date: Mapped[date | None] = mapped_column(Date)  # 적용 종료일 (PERIOD 타입용)

    # 적용 대상
    applies_to_sales: Mapped[bool] = mapped_column(Boolean, default=True)  # 매출전표 적용
    applies_to_purchase: Mapped[bool] = mapped_column(Boolean, default=False)  # 매입전표 적용

    # 활성화 여부
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    # Relationships
    contract: Mapped["HBContract"] = relationship("HBContract", back_populates="additional_charges")


# ===== 분할 청구 모델 =====


class SplitType(str, Enum):
    """분할 유형"""

    PERCENTAGE = "percentage"  # 비율로 분할
    FIXED_AMOUNT = "fixed_amount"  # 고정 금액


class SplitBillingRule(Base):
    """분할 청구 규칙 (1 UID → N 법인 배분)"""

    __tablename__ = "split_billing_rules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # 원본 소스
    source_account_id: Mapped[str] = mapped_column(String(50), ForeignKey("hb_vendor_accounts.id"), index=True)
    source_contract_seq: Mapped[int] = mapped_column(Integer, ForeignKey("hb_contracts.seq"), index=True)

    # 규칙 이름 (관리용)
    name: Mapped[str | None] = mapped_column(String(200))

    # 적용 기간
    effective_from: Mapped[date | None] = mapped_column(Date)  # 적용 시작일
    effective_to: Mapped[date | None] = mapped_column(Date)  # 적용 종료일

    # 활성화 여부
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    # Relationships
    source_account: Mapped["HBVendorAccount"] = relationship("HBVendorAccount")
    source_contract: Mapped["HBContract"] = relationship("HBContract", back_populates="split_rules")
    allocations: Mapped[list["SplitBillingAllocation"]] = relationship(
        "SplitBillingAllocation", back_populates="rule", cascade="all, delete-orphan"
    )


class SplitBillingAllocation(Base):
    """분할 청구 배분 대상"""

    __tablename__ = "split_billing_allocations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    rule_id: Mapped[int] = mapped_column(Integer, ForeignKey("split_billing_rules.id"), index=True)

    # 배분 대상 회사
    target_company_seq: Mapped[int] = mapped_column(Integer, ForeignKey("hb_companies.seq"), index=True)

    # 분할 방식
    split_type: Mapped[str] = mapped_column(String(20), default=SplitType.PERCENTAGE.value)
    split_value: Mapped[float] = mapped_column(Float)  # 비율(%) 또는 고정금액(USD)

    # 우선순위 (고정금액 분할 시 순서 결정)
    priority: Mapped[int] = mapped_column(Integer, default=0)

    # 메모
    note: Mapped[str | None] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    # Relationships
    rule: Mapped["SplitBillingRule"] = relationship("SplitBillingRule", back_populates="allocations")
    target_company: Mapped["HBCompany"] = relationship("HBCompany")


# ===== 일할 계산 모델 =====


class ProRataPeriod(Base):
    """일할 계산 기간 (월 중간 시작/종료 계약의 일할 적용)"""

    __tablename__ = "pro_rata_periods"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    contract_seq: Mapped[int] = mapped_column(Integer, ForeignKey("hb_contracts.seq"), index=True)

    # 정산월
    billing_cycle: Mapped[str] = mapped_column(String(10), index=True)  # YYYYMM

    # 일할 기간
    start_day: Mapped[int] = mapped_column(Integer)  # 시작일 (1~31)
    end_day: Mapped[int] = mapped_column(Integer)  # 종료일 (1~31)

    # 계산된 일수
    total_days: Mapped[int] = mapped_column(Integer)  # 해당 월 총 일수
    active_days: Mapped[int] = mapped_column(Integer)  # 활성 일수

    # 일할 비율 (active_days / total_days)
    ratio: Mapped[float] = mapped_column(Float)

    # 수동 등록 여부 (자동 계산 vs 수동 입력)
    is_manual: Mapped[bool] = mapped_column(Boolean, default=False)

    # 메모
    note: Mapped[str | None] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    # Relationships
    contract: Mapped["HBContract"] = relationship("HBContract", back_populates="pro_rata_periods")
