from datetime import datetime

from sqlalchemy import DateTime, Integer, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class AccountCode(Base):
    """계정코드 마스터"""

    __tablename__ = "account_codes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    hkont: Mapped[str] = mapped_column(String(10), unique=True, index=True)  # 계정코드
    name: Mapped[str] = mapped_column(String(100))  # 계정명
    description: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class CostCenter(Base):
    """코스트센터 마스터"""

    __tablename__ = "cost_centers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    kostl: Mapped[str] = mapped_column(String(10), unique=True, index=True)  # 코스트센터 코드
    name: Mapped[str] = mapped_column(String(100))  # 부서명
    profit_center: Mapped[str | None] = mapped_column(String(10))  # 손익센터
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class TaxCode(Base):
    """세금코드 마스터"""

    __tablename__ = "tax_codes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    mwskz: Mapped[str] = mapped_column(String(5), unique=True, index=True)  # 세금코드
    name: Mapped[str] = mapped_column(String(100))  # 세금코드명
    rate: Mapped[float] = mapped_column(Numeric(5, 2))  # 세율 (예: 10.00)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class Customer(Base):
    """거래처 마스터"""

    __tablename__ = "customers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    partner: Mapped[str] = mapped_column(String(20), unique=True, index=True)  # 거래처 코드
    name: Mapped[str] = mapped_column(String(100))  # 거래처명
    business_number: Mapped[str | None] = mapped_column(String(20))  # 사업자번호
    contact_email: Mapped[str | None] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
