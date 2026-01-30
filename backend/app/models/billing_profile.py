"""
회사별 청구 설정 및 예치금 관리 모델
"""

from datetime import date, datetime
from enum import Enum

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class PaymentType(str, Enum):
    POSTPAID = "postpaid"  # 후불
    DEPOSIT = "deposit"  # 예치금
    BOTH = "both"  # 둘 다 사용


class CompanyBillingProfile(Base):
    """회사+CSP별 청구 설정"""

    __tablename__ = "company_billing_profiles"
    __table_args__ = (
        UniqueConstraint("company_seq", "vendor", name="uq_company_vendor"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    company_seq: Mapped[int] = mapped_column(Integer, ForeignKey("hb_companies.seq"), index=True)
    vendor: Mapped[str] = mapped_column(String(50), index=True)  # alibaba, gcp, etc.

    # 결제 방식
    payment_type: Mapped[str] = mapped_column(String(20), default=PaymentType.POSTPAID.value)

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
    profile_id: Mapped[int] = mapped_column(Integer, ForeignKey("company_billing_profiles.id"), index=True)

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
    profile: Mapped["CompanyBillingProfile"] = relationship("CompanyBillingProfile", back_populates="deposits")
    usages: Mapped[list["DepositUsage"]] = relationship("DepositUsage", back_populates="deposit")


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
