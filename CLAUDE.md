# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Slip Automation System** (전표 자동화 시스템) - 클라우드 벤더(Alibaba 등) 빌링 데이터를 기반으로 회계 전표를 자동 생성하는 시스템

## Commands

### Backend (UV + FastAPI)
```bash
cd backend
uv sync                                    # Install dependencies
uv run uvicorn app.main:app --reload       # Run dev server (localhost:8000)
uv run pytest                              # Run tests
uv run ruff check . && uv run ruff format . # Lint & format
```

### Frontend (Vite + React)
```bash
cd frontend
npm install        # Install dependencies
npm run dev        # Run dev server (localhost:5173)
npm run build      # Production build
```

## Architecture

### Project Structure
```
billing/
├── backend/
│   └── app/
│       ├── api/
│       │   ├── alibaba.py    # 빌링 데이터 API
│       │   ├── master.py     # 마스터 데이터 API
│       │   ├── hb.py         # HB 연동 API
│       │   └── slip.py       # 전표 생성/관리 API
│       ├── models/
│       │   ├── alibaba.py    # 빌링 + 마스터 모델
│       │   ├── hb.py         # HB 연동 모델
│       │   └── slip.py       # 전표 모델
│       └── main.py
├── frontend/
└── data_sample/
```

### Database Models

**빌링 데이터**: `alibaba_billing`

**마스터 데이터**: `bp_codes`, `account_codes`, `tax_codes`, `cost_centers`, `contract_codes`

**HB 연동**: `hb_companies`, `hb_contracts`, `hb_vendor_accounts`, `account_contract_mappings`

**전표**: `slip_records`, `exchange_rates`, `slip_configs`

### API Endpoints

**빌링** (`/api/alibaba`)
- `POST /upload/{billing_type}` - 업로드 (enduser/reseller)
- `GET /summary` - UID별 합계

**마스터** (`/api/master`)
- BP코드, 계정코드, 세금코드, 부서코드, 계약번호 CRUD

**HB 연동** (`/api/hb`)
- Company, Contract, Account 업로드/조회/수정
- `GET /billing-lookup?uid=xxx` - UID로 전표 정보 조회

**전표** (`/api/slip`)
- `POST /exchange-rates` - 환율 등록
- `GET /config/{vendor}` - 전표 설정 조회
- `POST /generate` - 전표 생성
- `GET /` - 전표 목록 조회
- `GET /batches` - 배치 목록
- `PATCH /{slip_id}` - 전표 수정
- `POST /confirm/{batch_id}` - 전표 확정
- `GET /export/{batch_id}` - CSV 내보내기
- `DELETE /batch/{batch_id}` - 배치 삭제

## Business Logic

### 전표 생성 흐름
```
1. 환율 등록
   POST /api/slip/exchange-rates
   {"rate": 1450.0, "rate_date": "2026-01-09"}

2. 전표 생성
   POST /api/slip/generate
   {
     "billing_cycle": "202512",
     "slip_type": "sales",        // sales=매출, purchase=매입
     "document_date": "2026-01-09",
     "exchange_rate": 1450.0,
     "invoice_number": "SIGM12601000001860"
   }

3. BP 없는 전표 수정 (수동 매핑)
   PATCH /api/slip/{slip_id}
   {"partner": "100930"}

4. 전표 확정
   POST /api/slip/confirm/{batch_id}

5. CSV 내보내기
   GET /api/slip/export/{batch_id}
```

### 금액 계산
- **Enduser (매출)**: `pretax_cost` × 환율 (원단위 절사)
- **Reseller (매입)**: `(original_cost - discount - spn_deducted)` × 환율

### 전표 고정값 (Alibaba)
| 필드 | 값 |
|------|-----|
| BUKRS | 1100 |
| WAERS | KRW |
| PRCTR | 10000003 |
| HKONT (매출) | 41021010 |
| HKONT (매입) | 42021010 |
| 채권과목 | 11060110 (기본) |
| ZZREF2 | IBABA001 |

### 계약번호
- 매출: `매출ALI999` → 매입: `매입ALI999`

## Tech Stack
- **Backend:** Python 3.12, FastAPI, SQLAlchemy 2.0, UV
- **Frontend:** React 18, TypeScript, Vite, Tailwind CSS
- **Database:** SQLite (dev)
