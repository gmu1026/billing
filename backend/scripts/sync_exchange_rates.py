"""
HB API에서 환율 정보를 가져와 DB에 저장하는 배치 스크립트

실행 스케줄: 매일 KST AM 09:00
- Windows Task Scheduler 또는 cron으로 실행

사용법:
    python scripts/sync_exchange_rates.py
    python scripts/sync_exchange_rates.py --days 30  # 최근 30일 데이터
"""

import argparse
import json
import os
import sys
from datetime import date, datetime

import requests

# 프로젝트 루트를 path에 추가
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import SessionLocal
from app.models.slip import ExchangeRate


# HB API 설정
HB_API_URL = "https://alibabacloud.hyperbilling.kr/admin/api/v1/ccy/exchangerate"
HB_COOKIE = "connect.sid=s%3AF6rpskNNDIRY7bSFJtOI17WKw6sJP_88.io0TefWAC56UJEXNIM51lg1%2BWTbZagMP6HPNzqtpQAw"


def fetch_exchange_rates_from_hb(limit: int = 31) -> list[dict]:
    """HB API에서 환율 데이터 가져오기"""
    params = {
        "page": 1,
        "sort": "-date",
        "limit": limit,
        "withCountAll": "true",
        "code": "USD",
    }
    headers = {
        "Cookie": HB_COOKIE,
    }

    try:
        response = requests.get(HB_API_URL, params=params, headers=headers, timeout=30)
        response.raise_for_status()
        data = response.json()

        # API 응답 구조: data.rows[] 또는 data.data.rows[]
        if data.get("success"):
            inner_data = data.get("data", {})
            if isinstance(inner_data, dict) and "rows" in inner_data:
                return inner_data.get("rows", [])
            elif isinstance(inner_data, dict) and "data" in inner_data:
                return inner_data.get("data", {}).get("rows", [])
        return []
    except requests.RequestException as e:
        print(f"[ERROR] HB API 요청 실패: {e}")
        return []


def fetch_exchange_rates_from_json() -> list[dict]:
    """JSON 파일에서 환율 데이터 가져오기 (fallback)"""
    json_path = os.path.join(
        os.path.dirname(__file__), "../../data/import/hb/hb_exchange.json"
    )

    if not os.path.exists(json_path):
        print(f"[WARN] JSON 파일 없음: {json_path}")
        return []

    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    return data.get("data", {}).get("data", {}).get("rows", [])


def sync_exchange_rates(use_api: bool = True, limit: int = 31):
    """환율 데이터 동기화"""
    print(f"[INFO] 환율 동기화 시작 - {datetime.now().isoformat()}")

    # 데이터 가져오기
    if use_api:
        print("[INFO] HB API에서 환율 데이터 가져오기...")
        rows = fetch_exchange_rates_from_hb(limit)
        if not rows:
            print("[WARN] API 실패, JSON 파일로 fallback...")
            rows = fetch_exchange_rates_from_json()
    else:
        print("[INFO] JSON 파일에서 환율 데이터 가져오기...")
        rows = fetch_exchange_rates_from_json()

    if not rows:
        print("[ERROR] 환율 데이터 없음")
        return {"success": False, "error": "No exchange rate data"}

    # DB 저장
    db = SessionLocal()
    imported = 0
    updated = 0

    try:
        for row in rows:
            rate_date_str = row.get("date")
            if not rate_date_str:
                continue

            rate_date = datetime.strptime(rate_date_str, "%Y-%m-%d").date()
            currency_code = row.get("code", "USD")

            # 기존 데이터 확인
            existing = (
                db.query(ExchangeRate)
                .filter(
                    ExchangeRate.rate_date == rate_date,
                    ExchangeRate.currency_from == currency_code,
                    ExchangeRate.currency_to == "KRW",
                )
                .first()
            )

            basic_rate = float(row.get("basic_rate", 0))
            send_rate = float(row.get("send_rate", 0))
            buy_rate = float(row.get("buy_rate", 0))
            sell_rate = float(row.get("sell_rate", 0))

            if existing:
                existing.rate = basic_rate
                existing.basic_rate = basic_rate
                existing.send_rate = send_rate
                existing.buy_rate = buy_rate
                existing.sell_rate = sell_rate
                existing.source = "hb"
                updated += 1
            else:
                new_rate = ExchangeRate(
                    rate_date=rate_date,
                    currency_from=currency_code,
                    currency_to="KRW",
                    rate=basic_rate,
                    basic_rate=basic_rate,
                    send_rate=send_rate,
                    buy_rate=buy_rate,
                    sell_rate=sell_rate,
                    source="hb",
                )
                db.add(new_rate)
                imported += 1

        db.commit()
        print(f"[INFO] 동기화 완료 - 신규: {imported}, 업데이트: {updated}")
        return {"success": True, "imported": imported, "updated": updated}

    except Exception as e:
        db.rollback()
        print(f"[ERROR] DB 저장 실패: {e}")
        return {"success": False, "error": str(e)}
    finally:
        db.close()


def main():
    parser = argparse.ArgumentParser(description="HB 환율 데이터 동기화")
    parser.add_argument(
        "--days", type=int, default=31, help="가져올 일수 (기본: 31)"
    )
    parser.add_argument(
        "--json-only", action="store_true", help="API 대신 JSON 파일만 사용"
    )
    args = parser.parse_args()

    result = sync_exchange_rates(use_api=not args.json_only, limit=args.days)
    print(f"[RESULT] {result}")


if __name__ == "__main__":
    main()
