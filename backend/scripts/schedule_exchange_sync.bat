@echo off
REM HB 환율 동기화 배치 스크립트
REM Windows Task Scheduler에서 매일 09:00 KST에 실행
REM
REM Task Scheduler 설정:
REM 1. 작업 스케줄러 열기 (taskschd.msc)
REM 2. 작업 만들기 > 트리거: 매일 09:00
REM 3. 동작: 프로그램 시작 > 이 배치 파일 경로 지정

cd /d D:\자동화\py\billing\backend
uv run python scripts/sync_exchange_rates.py --days 7

echo 환율 동기화 완료: %date% %time%
