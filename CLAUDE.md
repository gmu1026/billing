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
│       │   ├── alibaba.py           # 빌링 데이터 API
│       │   ├── master.py            # 마스터 데이터 API
│       │   ├── hb.py                # HB 연동 API
│       │   ├── slip.py              # 전표 생성/관리 API
│       │   ├── additional_charge.py # 추가 비용 API
│       │   ├── pro_rata.py          # 일할 계산 API
│       │   └── split_billing.py     # 분할 청구 API
│       ├── models/
│       │   ├── alibaba.py           # 빌링 + 마스터 모델
│       │   ├── hb.py                # HB 연동 모델
│       │   ├── billing_profile.py   # 청구 설정 + 추가 비용 + 분할/일할 모델
│       │   └── slip.py              # 전표 모델
│       └── main.py
├── frontend/
└── data_sample/
```

### Database Models

**빌링 데이터**: `alibaba_billing`

**마스터 데이터**: `bp_codes`, `account_codes`, `tax_codes`, `cost_centers`, `contract_codes`

**HB 연동**: `hb_companies`, `hb_contracts`, `hb_vendor_accounts`, `account_contract_mappings`

**전표**: `slip_records`, `exchange_rates`, `slip_configs`

**청구 설정**: `company_billing_profiles`, `contract_billing_profiles`, `deposits`, `deposit_usages`

**추가 비용/분할/일할**: `additional_charges`, `split_billing_rules`, `split_billing_allocations`, `pro_rata_periods`

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
- `GET /exchange-rates` - 환율 목록 조회
- `GET /exchange-rates/by-date` - 특정 날짜 환율 조회
- `GET /exchange-rates/first-of-month` - 월 1일자 환율 조회
- `POST /exchange-rates/import-json` - JSON 파일에서 환율 import
- `POST /exchange-rates/sync-hb` - HB API에서 환율 동기화
- `GET /config/{vendor}` - 전표 설정 조회
- `POST /generate` - 전표 생성 (추가비용/분할/일할 포함)
- `GET /` - 전표 목록 조회
- `GET /batches` - 배치 목록
- `PATCH /{slip_id}` - 전표 수정
- `POST /confirm/{batch_id}` - 전표 확정
- `GET /export/{batch_id}` - CSV 내보내기 (전표유형별 양식)
- `DELETE /batch/{batch_id}` - 배치 삭제

**추가 비용** (`/api/additional-charges`)
- `POST /` - 추가 비용 생성
- `GET /` - 추가 비용 목록
- `GET /{id}` - 추가 비용 상세
- `PATCH /{id}` - 추가 비용 수정
- `DELETE /{id}` - 추가 비용 삭제
- `GET /by-contract/{seq}` - 계약별 추가 비용 조회

**일할 계산** (`/api/pro-rata`)
- `POST /periods` - 일할 기간 수동 등록
- `GET /periods` - 일할 기간 목록
- `GET /periods/{id}` - 일할 기간 상세
- `PATCH /periods/{id}` - 일할 기간 수정
- `DELETE /periods/{id}` - 일할 기간 삭제
- `GET /calculate` - 일할 비율 계산

**분할 청구** (`/api/split-billing`)
- `POST /rules` - 분할 규칙 생성
- `GET /rules` - 분할 규칙 목록
- `GET /rules/{id}` - 분할 규칙 상세
- `PATCH /rules/{id}` - 분할 규칙 수정
- `DELETE /rules/{id}` - 분할 규칙 삭제
- `POST /rules/{id}/allocations` - 배분 대상 추가
- `PATCH /allocations/{id}` - 배분 대상 수정
- `DELETE /allocations/{id}` - 배분 대상 삭제
- `POST /simulate` - 분할 시뮬레이션

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
     "invoice_number": "SIGM12601000001860",
     "include_additional_charges": true,  // 추가 비용 포함
     "apply_pro_rata": true,              // 일할 계산 적용
     "apply_split_billing": true          // 분할 청구 적용
   }

3. BP 없는 전표 수정 (수동 매핑)
   PATCH /api/slip/{slip_id}
   {"partner": "100930"}

4. 전표 확정
   POST /api/slip/confirm/{batch_id}

5. CSV 내보내기
   GET /api/slip/export/{batch_id}
```

### 전표 생성 로직 (상세)
```
1. UID별 빌링 합산 (기존)
     ↓
2. 분할 청구 확인
   - SplitBillingRule 조회
   - 해당되면 allocations에 따라 금액 분배
   - 각 배분 대상별 별도 SlipRecord 생성
     ↓
3. 일할 계산 적용
   - ProRataPeriod 또는 계약 시작/종료일 기반 자동 계산
   - 금액 × ratio 적용
     ↓
4. 추가 비용 적용
   - AdditionalCharge 조회 (해당 계약, 빌링사이클)
   - 별도 전표 생성 (source_type='additional_charge')
     ↓
5. 환율 변환 및 SlipRecord 생성
```

### 금액 계산
- **Enduser (매출)**: `pretax_cost` × 환율 (원단위 절사)
- **Reseller (매입)**: `(original_cost - discount - spn_deducted)` × 환율

### 전표 고정값 (Alibaba)
| 필드 | 값 |
|------|-----|
| BUKRS | 1100 |
| WAERS | KRW (국내), USD (해외) |
| PRCTR | 10000003 |
| HKONT (매출-국내) | 41021010 |
| HKONT (매출-수출) | 41021020 |
| HKONT (매입) | 42021010 |
| 채권과목 | 11060110 (기본) |
| ZZREF2 | IBABA001 |

### 계약번호
- 매출: `매출ALI999` → 매입: `매입ALI999`

### 환율 관리
HB API에서 환율 데이터를 동기화합니다. 매일 KST 09:00 배치 실행.

```bash
# 환율 동기화 스크립트
cd backend
uv run python scripts/sync_exchange_rates.py --days 7
```

**환율 유형:**
- `basic_rate`: 기준환율 (해외 매출 원화환산용)
- `send_rate`: 송금환율 (매출 증빙일자용)
- `buy_rate`: 매입환율
- `sell_rate`: 매도환율

**환율 적용일 규칙 (CSP별 설정 가능):**
| 규칙 | 설명 |
|------|------|
| `document_date` | 증빙일 기준 |
| `first_of_document_month` | 증빙월 1일 |
| `first_of_billing_month` | 정산월 1일 |
| `last_of_prev_month` | 전월 말일 |

**기본 환율 사용 규칙 (Alibaba):**
| 전표 유형 | 적용일 규칙 | 환율 종류 |
|-----------|-------------|-----------|
| 매출 | 증빙일 | 송금환율 (send_rate) |
| 매입 | 증빙일 | 기준환율 (basic_rate) |
| 해외법인 | 정산월 1일 | 기준환율 (basic_rate) |

> 환율 규칙은 전표 설정 UI에서 CSP별로 변경 가능합니다.

### 해외법인 처리
- `is_overseas=True` 회사는 자동으로:
  - 통화: USD (또는 default_currency)
  - 계정: 수출코드 (41021020)
  - BP: 국가코드로 시작 (예: CN090000705, HK090000743)

### 전표 양식 (CSV Export)
| 전표 유형 | 데이터 열 | 검증용 열 |
|-----------|----------|-----------|
| 매출 (sales) | 22열 | 사업자번호, 거래처명 |
| 원가 (purchase) | 21열 | 사업자번호, 거래처명 |
| 청구 (billing) | 26열 | 사업자번호, 사명, 공급가 |

### 추가 비용 (Additional Charges)
RAW 빌링 데이터 외 추가 비용 항목입니다.

**비용 유형 (charge_type):**
| 유형 | 설명 |
|------|------|
| `credit` | 크레딧 (음수 = 차감) |
| `support_fee` | 서포트 비용 |
| `setup_fee` | 셋업 비용 |
| `other` | 기타 |

**반복 유형 (recurrence_type):**
| 유형 | 설명 |
|------|------|
| `recurring` | 매월 반복 |
| `one_time` | 일회성 |
| `period` | 기간 지정 |

### 분할 청구 (Split Billing)
1개 UID 빌링을 N개 법인에 배분합니다.

**분할 유형 (split_type):**
| 유형 | 설명 |
|------|------|
| `percentage` | 비율로 분할 (%) |
| `fixed_amount` | 고정 금액 (USD) |

### 일할 계산 (Pro Rata)
월 중간 시작/종료 계약의 금액을 일수 비율로 계산합니다.

**적용 우선순위:**
1. 수동 등록 기간 (ProRataPeriod)
2. 계약 시작/종료일 기반 자동 계산
3. 일할 계산 불필요 (ratio = 1.0)

**계약 프로필 오버라이드:**
- `enabled`: 강제 활성화
- `disabled`: 강제 비활성화
- `None`: 벤더 설정 따름

## Tech Stack
- **Backend:** Python 3.12, FastAPI, SQLAlchemy 2.0, UV
- **Frontend:** React 18, TypeScript, Vite, Tailwind CSS
- **Database:** SQLite (dev)
