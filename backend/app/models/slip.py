"""
전표 관련 모델
"""

from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, Float, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class SlipRecord(Base):
    """생성된 전표 레코드"""

    __tablename__ = "slip_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # 전표 식별
    batch_id: Mapped[str] = mapped_column(String(50), index=True)  # 생성 배치 ID
    slip_type: Mapped[str] = mapped_column(String(20), index=True)  # sales(매출) / purchase(매입)
    vendor: Mapped[str] = mapped_column(String(50), default="alibaba")
    billing_cycle: Mapped[str] = mapped_column(String(10), index=True)  # YYYYMM

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

    # 금액
    wrbtr: Mapped[float] = mapped_column(Float, default=0)  # 통화금액 (KRW)
    wrbtr_usd: Mapped[float] = mapped_column(Float, default=0)  # 원화금액 (USD)
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

    # 상태
    is_confirmed: Mapped[bool] = mapped_column(Boolean, default=False)  # 확정 여부
    is_exported: Mapped[bool] = mapped_column(Boolean, default=False)  # 내보내기 완료

    # 메타데이터
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


class ExchangeRate(Base):
    """환율 정보"""

    __tablename__ = "exchange_rates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    currency_from: Mapped[str] = mapped_column(String(10), default="USD")
    currency_to: Mapped[str] = mapped_column(String(10), default="KRW")
    rate: Mapped[float] = mapped_column(Float)
    rate_date: Mapped[date] = mapped_column(Date, index=True)
    source: Mapped[str | None] = mapped_column(String(50))  # 환율 출처
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class SlipConfig(Base):
    """전표 생성 설정 (벤더별)"""

    __tablename__ = "slip_configs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    vendor: Mapped[str] = mapped_column(String(50), unique=True, index=True)

    # 고정값
    bukrs: Mapped[str] = mapped_column(String(10), default="1100")
    prctr: Mapped[str] = mapped_column(String(20), default="10000003")
    hkont_sales: Mapped[str] = mapped_column(String(20), default="41021010")  # 매출 계정
    hkont_purchase: Mapped[str] = mapped_column(String(20), default="42021010")  # 매입 계정
    ar_account_default: Mapped[str] = mapped_column(String(20), default="11060110")  # 기본 채권과목
    ap_account_default: Mapped[str] = mapped_column(String(20), default="21120110")  # 기본 채무과목
    zzref2: Mapped[str] = mapped_column(String(50), default="IBABA001")  # 거래명
    sgtxt_template: Mapped[str] = mapped_column(String(200), default="Alibaba_Cloud_{MM}월_{TYPE}")

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
