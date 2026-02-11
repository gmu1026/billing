"""
전표 관련 모델
"""

from datetime import date, datetime
from enum import Enum
from typing import Any

from sqlalchemy import JSON, Boolean, Date, DateTime, Float, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class RoundingRule(str, Enum):
    """금액 라운딩 규칙"""

    FLOOR = "floor"  # 버림 (기본값)
    ROUND_HALF_UP = "round_half_up"  # 반올림
    CEILING = "ceiling"  # 올림


class ExchangeRateDateRule(str, Enum):
    """환율 적용일 규칙"""

    DOCUMENT_DATE = "document_date"  # 증빙일 기준
    FIRST_OF_DOCUMENT_MONTH = "first_of_document_month"  # 증빙일이 속한 월 1일
    FIRST_OF_BILLING_MONTH = "first_of_billing_month"  # 정산월 1일
    LAST_OF_PREV_MONTH = "last_of_prev_month"  # 전월 말일 (증빙일 기준)
    CUSTOM = "custom"  # 사용자 지정일


class ExchangeRateType(str, Enum):
    """환율 종류"""

    BASIC_RATE = "basic_rate"  # 기준환율
    SEND_RATE = "send_rate"  # 송금환율
    BUY_RATE = "buy_rate"  # 매입환율
    SELL_RATE = "sell_rate"  # 매도환율


class SlipSourceType(str, Enum):
    """전표 원본 유형"""

    BILLING = "billing"  # RAW 빌링 데이터
    ADDITIONAL_CHARGE = "additional_charge"  # 추가 비용
    SPLIT = "split"  # 분할 청구


class SlipRecord(Base):
    """생성된 전표 레코드"""

    __tablename__ = "slip_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # 전표 식별
    batch_id: Mapped[str] = mapped_column(String(50), index=True)  # 생성 배치 ID
    slip_type: Mapped[str] = mapped_column(String(20), index=True)  # sales(매출) / purchase(매입)
    vendor: Mapped[str] = mapped_column(String(50), default="alibaba")
    billing_cycle: Mapped[str] = mapped_column(String(10), index=True)  # YYYYMM

    # 원본 유형 (billing/additional_charge/split)
    source_type: Mapped[str] = mapped_column(String(30), default=SlipSourceType.BILLING.value)

    # 전표 필드
    seqno: Mapped[int] = mapped_column(Integer)  # 순번
    bukrs: Mapped[str] = mapped_column(String(10), default="1100")  # 회사코드
    bldat: Mapped[date] = mapped_column(Date)  # 증빙일
    budat: Mapped[date] = mapped_column(Date)  # 전기일
    waers: Mapped[str] = mapped_column(String(10), default="KRW")  # 통화
    xblnr: Mapped[str | None] = mapped_column(String(50))  # 참조
    sgtxt: Mapped[str | None] = mapped_column(String(200))  # 전표적요

    # 거래처
    partner: Mapped[str | None] = mapped_column(String(20))  # BP번호
    partner_name: Mapped[str | None] = mapped_column(String(200))  # 거래처명

    # 계정
    ar_account: Mapped[str | None] = mapped_column(String(20))  # 채권/채무과목
    hkont: Mapped[str | None] = mapped_column(String(20))  # 계정과목
    tax_code: Mapped[str | None] = mapped_column(String(10))  # 부가세코드 (A1, A3, B1 등)

    # 금액
    wrbtr: Mapped[float] = mapped_column(Float, default=0)  # 통화금액 (해외: USD, 국내: KRW)
    wrbtr_usd: Mapped[float] = mapped_column(Float, default=0)  # USD 원본 금액
    dmbtr_c: Mapped[float | None] = mapped_column(Float)  # 원화환산액 (해외법인용 DMBTR_C)
    exchange_rate: Mapped[float | None] = mapped_column(Float)  # 적용 환율

    # 조직
    prctr: Mapped[str | None] = mapped_column(String(20))  # 부서코드

    # 계약 정보
    zzcon: Mapped[str | None] = mapped_column(String(20))  # 거래처코드
    zzsconid: Mapped[str | None] = mapped_column(String(30))  # 매출계약번호
    zzpconid: Mapped[str | None] = mapped_column(String(30))  # 매입계약번호
    zzsempno: Mapped[str | None] = mapped_column(String(20))  # 영업사원번호
    zzsempnm: Mapped[str | None] = mapped_column(String(50))  # 영업사원명
    zzref2: Mapped[str | None] = mapped_column(String(50))  # 거래명
    zzref: Mapped[str | None] = mapped_column(String(50))  # 세금계산서 관리번호
    zzinvno: Mapped[str | None] = mapped_column(String(50))  # 인보이스
    zzdepgno: Mapped[str | None] = mapped_column(String(50))  # 예치금그룹번호

    # 원본 데이터 참조
    uid: Mapped[str | None] = mapped_column(String(50), index=True)  # 알리바바 UID
    contract_seq: Mapped[int | None] = mapped_column(Integer)  # HB 계약 seq
    company_seq: Mapped[int | None] = mapped_column(Integer)  # HB 회사 seq

    # 추가 비용/분할 청구 참조
    additional_charge_id: Mapped[int | None] = mapped_column(Integer, index=True)  # 추가 비용 ID
    split_rule_id: Mapped[int | None] = mapped_column(Integer, index=True)  # 분할 규칙 ID
    split_allocation_id: Mapped[int | None] = mapped_column(Integer, index=True)  # 분할 배분 ID

    # 일할 계산 정보
    pro_rata_ratio: Mapped[float | None] = mapped_column(Float)  # 적용된 일할 비율
    original_amount: Mapped[float | None] = mapped_column(Float)  # 일할 계산 전 원본 금액

    # 상태
    is_confirmed: Mapped[bool] = mapped_column(Boolean, default=False)  # 확정 여부
    is_exported: Mapped[bool] = mapped_column(Boolean, default=False)  # 내보내기 완료

    # 메타데이터
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


class ExchangeRate(Base):
    """환율 정보"""

    __tablename__ = "exchange_rates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    currency_from: Mapped[str] = mapped_column(String(10), default="USD")
    currency_to: Mapped[str] = mapped_column(String(10), default="KRW")
    rate: Mapped[float] = mapped_column(Float)  # 기본 환율 (레거시 호환)
    rate_date: Mapped[date] = mapped_column(Date, index=True)

    # HB 환율 정보
    basic_rate: Mapped[float | None] = mapped_column(Float)  # 기준환율 (해외 매출 원화환산)
    send_rate: Mapped[float | None] = mapped_column(Float)  # 송금환율 (매출 증빙일자)
    buy_rate: Mapped[float | None] = mapped_column(Float)  # 매입환율
    sell_rate: Mapped[float | None] = mapped_column(Float)  # 매도환율

    source: Mapped[str | None] = mapped_column(String(50))  # 환율 출처 (hb, manual 등)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class SlipConfig(Base):
    """전표 생성 설정 (벤더별)"""

    __tablename__ = "slip_configs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    vendor: Mapped[str] = mapped_column(String(50), unique=True, index=True)

    # 고정값
    bukrs: Mapped[str] = mapped_column(String(10), default="1100")
    prctr: Mapped[str] = mapped_column(String(20), default="10000003")
    hkont_sales: Mapped[str] = mapped_column(String(20), default="41021010")  # 매출 계정 (국내)
    hkont_sales_export: Mapped[str] = mapped_column(
        String(20), default="41021020"
    )  # 매출 계정 (수출)
    hkont_purchase: Mapped[str] = mapped_column(String(20), default="42021010")  # 매입 계정
    ar_account_default: Mapped[str] = mapped_column(String(20), default="11060110")  # 기본 채권과목
    ap_account_default: Mapped[str] = mapped_column(String(20), default="21120110")  # 기본 채무과목
    zzref2: Mapped[str] = mapped_column(String(50), default="IBABA001")  # 거래명
    sgtxt_template: Mapped[str] = mapped_column(String(200), default="Alibaba_Cloud_{MM}월_{TYPE}")

    # 라운딩 규칙 (기본: 버림)
    rounding_rule: Mapped[str] = mapped_column(String(20), default=RoundingRule.FLOOR.value)

    # 환율 적용 규칙 (매출)
    exchange_rate_rule_sales: Mapped[str] = mapped_column(
        String(30), default=ExchangeRateDateRule.DOCUMENT_DATE.value
    )
    exchange_rate_type_sales: Mapped[str] = mapped_column(
        String(20), default=ExchangeRateType.SEND_RATE.value
    )

    # 환율 적용 규칙 (매입)
    exchange_rate_rule_purchase: Mapped[str] = mapped_column(
        String(30), default=ExchangeRateDateRule.DOCUMENT_DATE.value
    )
    exchange_rate_type_purchase: Mapped[str] = mapped_column(
        String(20), default=ExchangeRateType.BASIC_RATE.value
    )

    # 해외법인 환율 규칙 (원화환산용)
    exchange_rate_rule_overseas: Mapped[str] = mapped_column(
        String(30), default=ExchangeRateDateRule.FIRST_OF_DOCUMENT_MONTH.value
    )
    exchange_rate_type_overseas: Mapped[str] = mapped_column(
        String(20), default=ExchangeRateType.BASIC_RATE.value
    )

    # 일할 계산 설정
    pro_rata_enabled: Mapped[bool] = mapped_column(Boolean, default=True)  # 일할 계산 활성화
    pro_rata_calculation: Mapped[str] = mapped_column(
        String(30), default="calendar_days"
    )  # 계산 방식: calendar_days (달력일수), business_days (영업일수)

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


class SlipTemplate(Base):
    """전표 템플릿 (양식 정의)"""

    __tablename__ = "slip_templates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100))  # 템플릿명 (예: "매출전표양식")
    slip_type: Mapped[str] = mapped_column(String(20), index=True)  # sales, billing, purchase

    # 컬럼 구성 (순서 포함)
    columns: Mapped[dict[str, Any]] = mapped_column(
        JSON
    )  # [{"name": "SEQNO", "header": "SEQNO", ...}, ...]

    # 고정값 (벤더별로 다를 수 있으나 양식에서 추출한 기본값)
    fixed_values: Mapped[dict[str, Any]] = mapped_column(
        JSON
    )  # {"BUKRS": "1100", "PRCTR": "10000003", ...}

    # 계정 매핑 (국내/해외 등 조건별)
    account_mappings: Mapped[dict[str, Any]] = mapped_column(JSON)
    # {
    #   "domestic": {"receivable": "11060110", "revenue": "41021010"},
    #   "overseas": {"receivable": "21120110", "revenue": "41021020"}
    # }

    # 계약번호 패턴
    contract_pattern: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    # {"sales": "매출ALI999", "purchase": "매입ALI999"}

    # 전표적요 템플릿
    description_template: Mapped[str | None] = mapped_column(String(200))
    # "Alibaba Cloud {month}월 이용료"

    # 원본 파일명 (참조용)
    source_file: Mapped[str | None] = mapped_column(String(200))

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )
