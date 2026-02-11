"""공통 유틸리티 함수"""

from decimal import ROUND_CEILING, ROUND_DOWN, ROUND_HALF_UP, Decimal


def round_decimal(value: float, places: int = 2) -> float:
    """소수점 정확한 반올림 (ROUND_HALF_UP)"""
    d = Decimal(str(value))
    return float(d.quantize(Decimal(10) ** -places, rounding=ROUND_HALF_UP))


def apply_rounding(amount: float, rule: str, decimals: int = 0) -> int | float:
    """라운딩 규칙에 따른 금액 처리"""
    d = Decimal(str(amount))
    quantize_value = Decimal(10) ** -decimals

    if rule == "ceiling":
        result = d.quantize(quantize_value, rounding=ROUND_CEILING)
    elif rule == "round_half_up":
        result = d.quantize(quantize_value, rounding=ROUND_HALF_UP)
    else:  # floor (default)
        result = d.quantize(quantize_value, rounding=ROUND_DOWN)

    return int(result) if decimals == 0 else float(result)


def parse_float(value: str) -> float:
    """문자열을 float으로 변환 (빈값/오류 시 0 반환)"""
    if not value or value.strip() == "":
        return 0.0
    try:
        return float(value.replace(",", ""))
    except ValueError:
        return 0.0


def clean_string(value: str | None) -> str | None:
    """문자열 정리 (탭, 공백 제거)"""
    if not value:
        return None
    cleaned = value.strip().replace("\t", "")
    return cleaned if cleaned else None


def decode_csv_content(content: bytes) -> str:
    """CSV 파일 바이트를 문자열로 디코딩합니다.

    인코딩 시도 순서: utf-8-sig (BOM 포함 UTF-8) → cp949 (한국어 Windows) → utf-8

    Args:
        content: 파일 바이트 데이터

    Returns:
        디코딩된 문자열

    Raises:
        ValueError: 지원되는 인코딩으로 디코딩에 실패한 경우
    """
    for encoding in ("utf-8-sig", "cp949", "utf-8"):
        try:
            return content.decode(encoding)
        except (UnicodeDecodeError, LookupError):
            continue
    raise ValueError(
        "파일 인코딩을 감지할 수 없습니다. UTF-8 또는 CP949(EUC-KR) 형식으로 저장해 주세요."
    )
