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
│       │   └── master.py     # 마스터 데이터 API (BP, 계정, 세금코드 등)
│       ├── models/
│       │   └── alibaba.py    # SQLAlchemy 모델
│       ├── main.py
│       └── database.py
├── frontend/
├── data_sample/              # 샘플 데이터 (업로드 테스트용)
└── CLAUDE.md
```

### Database Models

| 테이블 | 설명 |
|--------|------|
| `alibaba_billing` | 알리바바 빌링 원본 데이터 (enduser/reseller) |
| `bp_codes` | 거래처 마스터 (BP번호, 이름, 사업자번호, 대표자명 등) |
| `account_codes` | 계정코드 마스터 (HKONT) |
| `tax_codes` | 세금코드 마스터 (매출/매입 구분) |
| `cost_centers` | 부서(코스트센터) 마스터 |
| `contract_codes` | 계약번호 마스터 (매출ALI999 ↔ 매입ALI999) |

### API Endpoints

**알리바바 빌링** (`/api/alibaba`)
| Method | Endpoint | 설명 |
|--------|----------|------|
| POST | `/upload/{billing_type}` | 빌링 데이터 업로드 (enduser/reseller) |
| GET | `/` | 빌링 데이터 조회 |
| GET | `/summary` | UID별 합계 조회 |
| DELETE | `/` | 빌링 데이터 삭제 |

**마스터 데이터** (`/api/master`)
| Method | Endpoint | 설명 |
|--------|----------|------|
| POST | `/bp-codes/upload` | BP Code 업로드 |
| GET | `/bp-codes` | BP Code 검색 |
| POST | `/account-codes/upload` | 계정코드 업로드 |
| POST | `/tax-codes/upload` | 세금코드 업로드 |
| POST | `/cost-centers/upload` | 부서코드 업로드 |
| POST | `/contracts/upload` | 계약번호 업로드 |

## Business Logic

### 빌링 금액 계산
- **Enduser (매출)**: `pretax_cost` 사용
- **Reseller (매입)**: `original_cost - discount - spn_deducted_price` (쿠폰이 메인계정으로 지급되어 발생 계약에 안 걸리는 이슈 대응)

### 전표 고정값 (Alibaba)
| 필드 | 값 |
|------|-----|
| BUKRS (회사코드) | 1100 |
| WAERS (통화) | KRW |
| PRCTR (부서코드) | 10000003 |
| HKONT (계정과목) | 41021010 |
| 채권과목 | 11060110 또는 21120110 |
| ZZSCONID (매출계약번호) | 매출ALI999 |
| ZZPCONID (매입계약번호) | 매입ALI999 |
| ZZREF2 (거래명) | IBABA001 |
| ZZINVNO (인보이스) | 수기 입력 |

### BP코드 표시 형식
`BP번호/이름1/도로주소1/세금번호/대표자명`

## Tech Stack
- **Backend:** Python 3.12, FastAPI, SQLAlchemy 2.0, UV
- **Frontend:** React 18, TypeScript, Vite, Tailwind CSS, TanStack Query/Table
- **Database:** SQLite (dev)
