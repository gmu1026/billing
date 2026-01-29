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
│       │   ├── alibaba.py    # 알리바바 빌링 데이터 API
│       │   ├── master.py     # 마스터 데이터 API (BP, 계정코드 등)
│       │   └── hb.py         # HB 연동 API (Company, Contract, Account)
│       ├── models/
│       │   ├── alibaba.py    # 빌링 + 마스터 모델
│       │   └── hb.py         # HB 연동 모델
│       ├── main.py
│       └── database.py
├── frontend/
├── data_sample/              # 샘플 데이터
└── CLAUDE.md
```

### Database Models

**빌링 데이터**
| 테이블 | 설명 |
|--------|------|
| `alibaba_billing` | 알리바바 빌링 원본 (enduser/reseller) |

**마스터 데이터**
| 테이블 | 설명 |
|--------|------|
| `bp_codes` | 거래처 마스터 (BP번호, 이름, 사업자번호, 대표자명) |
| `account_codes` | 계정코드 마스터 (HKONT) |
| `tax_codes` | 세금코드 마스터 |
| `cost_centers` | 부서(코스트센터) 마스터 |
| `contract_codes` | 계약번호 마스터 |

**HB 연동 (UID ↔ 계약 ↔ 회사 매핑)**
| 테이블 | 설명 |
|--------|------|
| `hb_companies` | 회사 정보 (HB company) |
| `hb_contracts` | 계약 정보 (HB contract) |
| `hb_vendor_accounts` | 클라우드 계정/UID (HB account) |
| `account_contract_mappings` | 계정-계약 N:N 매핑 |

### 데이터 관계
```
AlibabaBilling.user_id/linked_user_id
        ↓ (UID로 조회)
HBVendorAccount.id
        ↓ (N:N 매핑)
HBContract.seq
        ↓ (FK)
HBCompany.seq
        ↓ (수동 매핑)
BPCode.bp_number
```

### API Endpoints

**알리바바 빌링** (`/api/alibaba`)
- `POST /upload/{billing_type}` - 빌링 데이터 업로드
- `GET /` - 빌링 데이터 조회
- `GET /summary` - UID별 합계

**마스터 데이터** (`/api/master`)
- `POST /bp-codes/upload`, `GET /bp-codes` - BP코드
- `POST /account-codes/upload`, `GET /account-codes` - 계정코드
- `POST /tax-codes/upload`, `GET /tax-codes` - 세금코드
- `POST /contracts/upload`, `GET /contracts` - 계약번호

**HB 연동** (`/api/hb`)
- `POST /companies/upload`, `GET /companies`, `PATCH /companies/{seq}` - 회사
- `POST /contracts/upload`, `GET /contracts`, `PATCH /contracts/{seq}` - 계약
- `POST /accounts/upload`, `GET /accounts` - 계정(UID)
- `POST /mappings`, `DELETE /mappings/{id}` - 수동 매핑
- `GET /billing-lookup?uid=xxx` - UID로 전표 정보 조회

## Business Logic

### 빌링 금액 계산
- **Enduser (매출)**: `pretax_cost`
- **Reseller (매입)**: `original_cost - discount - spn_deducted_price`

### 전표 작성 흐름
1. 빌링 데이터 업로드 → `alibaba_billing` 저장
2. UID 기준으로 금액 합산
3. `/api/hb/billing-lookup?uid=xxx`로 계약/회사/BP 정보 조회
4. 전표 데이터 생성 (고정값 + 조회된 정보)

### 전표 고정값 (Alibaba)
| 필드 | 값 |
|------|-----|
| BUKRS | 1100 |
| WAERS | KRW |
| PRCTR | 10000003 |
| HKONT | 41021010 |
| 채권과목 | 11060110 / 21120110 |
| ZZREF2 | IBABA001 |

### 계약번호 변환
- 매출: `매출ALI999` ↔ 매입: `매입ALI999`

## Tech Stack
- **Backend:** Python 3.12, FastAPI, SQLAlchemy 2.0, UV
- **Frontend:** React 18, TypeScript, Vite, Tailwind CSS, TanStack Query/Table
- **Database:** SQLite (dev)
