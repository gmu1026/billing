"""공통 유틸리티 함수"""


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
