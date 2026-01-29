from datetime import date, datetime

from sqlalchemy import Date, DateTime, Integer, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class BillingData(Base):
    """빌링 데이터 (CSV/JSON 업로드용)"""

    __tablename__ = "billing_data"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    vendor: Mapped[str] = mapped_column(String(50), index=True)  # 벤더명 (예: alibaba)
    billing_month: Mapped[str] = mapped_column(String(7), index=True)  # YYYY-MM 형식
    service_name: Mapped[str | None] = mapped_column(String(100))  # 서비스명
    account_id: Mapped[str | None] = mapped_column(String(50))  # 계정 ID
    amount: Mapped[float] = mapped_column(Numeric(15, 2))  # 금액
    currency: Mapped[str] = mapped_column(String(3), default="KRW")  # 통화
    raw_data: Mapped[str | None] = mapped_column(String(2000))  # 원본 JSON 데이터
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class PresetGroup(Base):
    """프리셋 그룹"""

    __tablename__ = "preset_groups"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)  # 그룹명
    description: Mapped[str | None] = mapped_column(String(255))
    vendor: Mapped[str | None] = mapped_column(String(50), index=True)  # 연관 벤더
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class PresetItem(Base):
    """프리셋 아이템"""

    __tablename__ = "preset_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    group_id: Mapped[int] = mapped_column(Integer, index=True)  # FK to preset_groups
    day_rule: Mapped[int] = mapped_column(Integer, default=1)  # 매월 N일
    text_template: Mapped[str] = mapped_column(String(255))  # 적요 템플릿
    hkont: Mapped[str | None] = mapped_column(String(10))  # 계정코드
    kostl: Mapped[str | None] = mapped_column(String(10))  # 코스트센터
    fixed_amount: Mapped[float | None] = mapped_column(Numeric(15, 2))  # 고정금액
    contract_id: Mapped[str | None] = mapped_column(String(50))  # 외부 API 계약 ID
    holiday_rule: Mapped[str] = mapped_column(String(10), default="exact")  # forward/backward/exact
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
