from datetime import datetime

from sqlalchemy import DateTime, Float, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class AlibabaBilling(Base):
    """알리바바 빌링 원본 데이터"""

    __tablename__ = "alibaba_billing"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    # 기본 정보
    billing_type: Mapped[str] = mapped_column(String(20), index=True)  # enduser / reseller
    billing_cycle: Mapped[str] = mapped_column(String(10), index=True)  # YYYYMM
    consume_time: Mapped[str | None] = mapped_column(String(30))

    # 사용자 정보
    user_id: Mapped[str] = mapped_column(String(50), index=True)
    user_name: Mapped[str | None] = mapped_column(String(100))
    user_account: Mapped[str | None] = mapped_column(String(200))

    # Reseller 전용: Linked User 정보
    linked_user_id: Mapped[str | None] = mapped_column(String(50), index=True)
    linked_user_name: Mapped[str | None] = mapped_column(String(100))
    linked_user_account: Mapped[str | None] = mapped_column(String(200))

    # 빌링 분류
    bill_source: Mapped[str | None] = mapped_column(String(50))
    order_type: Mapped[str | None] = mapped_column(String(50))
    charge_type: Mapped[str | None] = mapped_column(String(50))
    billing_type_detail: Mapped[str | None] = mapped_column(String(50))  # Consume, etc.

    # 상품 정보
    product_code: Mapped[str | None] = mapped_column(String(100))
    product_name: Mapped[str | None] = mapped_column(String(200))
    instance_id: Mapped[str | None] = mapped_column(String(200))
    instance_name: Mapped[str | None] = mapped_column(String(200))
    instance_config: Mapped[str | None] = mapped_column(Text)
    instance_tag: Mapped[str | None] = mapped_column(Text)
    region: Mapped[str | None] = mapped_column(String(100))

    # 금액 정보 (원본 그대로 저장)
    original_cost: Mapped[float] = mapped_column(Float, default=0)
    spn_deducted_price: Mapped[float] = mapped_column(Float, default=0)
    spn_id: Mapped[str | None] = mapped_column(String(100))
    discount: Mapped[float] = mapped_column(Float, default=0)
    discount_percent: Mapped[str | None] = mapped_column(String(20))
    coupon_deduct: Mapped[float] = mapped_column(Float, default=0)
    pretax_cost: Mapped[float] = mapped_column(Float, default=0)
    currency: Mapped[str] = mapped_column(String(10), default="USD")

    # 계산된 금액 (전표용)
    # reseller: original_cost - discount - spn_deducted_price
    # enduser: pretax_cost
    calculated_amount: Mapped[float] = mapped_column(Float, default=0)

    # 메타데이터
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class BPCode(Base):
    """거래처 마스터 (BP Code)"""

    __tablename__ = "bp_codes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_code: Mapped[str] = mapped_column(String(10), default="1100")
    bp_number: Mapped[str] = mapped_column(String(20), unique=True, index=True)  # BP 번호
    bp_group: Mapped[str | None] = mapped_column(String(20))
    bp_group_name: Mapped[str | None] = mapped_column(String(100))

    # 이름 정보
    name_local: Mapped[str | None] = mapped_column(String(200))  # 이름 1 (Local)
    name_local_2: Mapped[str | None] = mapped_column(String(200))  # 이름 2 (Local)
    name_english: Mapped[str | None] = mapped_column(String(200))  # 이름 3 (English)
    search_key: Mapped[str | None] = mapped_column(String(100))  # 검색어1

    # 주소
    country: Mapped[str | None] = mapped_column(String(10))
    road_address_1: Mapped[str | None] = mapped_column(String(300))
    road_address_2: Mapped[str | None] = mapped_column(String(300))
    postal_code: Mapped[str | None] = mapped_column(String(20))

    # 세금/사업자 정보
    tax_number_country: Mapped[str | None] = mapped_column(String(10))
    tax_number: Mapped[str | None] = mapped_column(String(30), index=True)  # 세금번호 (사업자번호)
    business_type: Mapped[str | None] = mapped_column(String(200))  # 업태
    business_item: Mapped[str | None] = mapped_column(String(200))  # 종목
    representative: Mapped[str | None] = mapped_column(String(100))  # 대표자명

    # 담당자
    contact_name: Mapped[str | None] = mapped_column(String(100))
    contact_email: Mapped[str | None] = mapped_column(String(200))
    contact_phone: Mapped[str | None] = mapped_column(String(50))

    # 계정과목
    ar_account: Mapped[str | None] = mapped_column(String(20))  # 매출 채권과목
    ap_account: Mapped[str | None] = mapped_column(String(20))  # 매입 채무과목

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class AccountCode(Base):
    """계정코드 마스터"""

    __tablename__ = "account_codes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    hkont: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    name_short: Mapped[str | None] = mapped_column(String(100))
    name_long: Mapped[str | None] = mapped_column(String(200))
    account_group: Mapped[str | None] = mapped_column(String(50))  # Asset/Liability/PL Account
    currency: Mapped[str] = mapped_column(String(10), default="KRW")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class TaxCode(Base):
    """세금코드 마스터"""

    __tablename__ = "tax_codes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(10), unique=True, index=True)
    description: Mapped[str | None] = mapped_column(String(200))
    is_sales: Mapped[bool] = mapped_column(default=True)  # True=매출, False=매입
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class CostCenter(Base):
    """부서(코스트센터) 마스터"""

    __tablename__ = "cost_centers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_code: Mapped[str] = mapped_column(String(10), default="1100")
    cost_center: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    name: Mapped[str | None] = mapped_column(String(100))
    profit_center: Mapped[str | None] = mapped_column(String(20))
    profit_center_name: Mapped[str | None] = mapped_column(String(100))
    source_system: Mapped[str | None] = mapped_column(String(20))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class ContractCode(Base):
    """계약번호 마스터"""

    __tablename__ = "contract_codes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    sales_contract: Mapped[str] = mapped_column(String(30), unique=True, index=True)  # 매출ALI999
    description: Mapped[str | None] = mapped_column(String(200))
    vendor: Mapped[str | None] = mapped_column(String(50))  # alibaba, gcp, etc.
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    @property
    def purchase_contract(self) -> str:
        """매출 → 매입 계약번호 변환"""
        return self.sales_contract.replace("매출", "매입")
