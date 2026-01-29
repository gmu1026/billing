# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a **Slip Automation System** (전표 자동화 시스템) for automating accounting slip/voucher creation. The system replaces manual Excel-based slip creation with a web application that provides:

- Master data management (GL accounts, cost centers, tax codes, customers)
- Smart preset templates for recurring monthly billing slips
- Billing data upload (CSV/JSON/JSONL) for amount reference
- External API integration for contract amounts
- Validation against master data
- Export to Excel/CSV for legacy system uploads

## Commands

### Backend (UV + FastAPI)
```bash
cd backend
uv sync                           # Install dependencies
uv run uvicorn app.main:app --reload  # Run dev server (localhost:8000)
uv run pytest                     # Run tests
uv run ruff check .               # Lint
uv run ruff format .              # Format
```

### Frontend (Vite + React)
```bash
cd frontend
npm install                       # Install dependencies
npm run dev                       # Run dev server (localhost:5173)
npm run build                     # Production build
npm run preview                   # Preview production build
```

## Tech Stack

- **Backend:** Python 3.12, FastAPI, SQLAlchemy, Pydantic (managed by UV)
- **Frontend:** React 18, TypeScript, Vite, Tailwind CSS, TanStack Query/Table
- **Database:** SQLite (dev) / PostgreSQL (prod)

## Architecture

### Project Structure
```
billing/
├── backend/
│   ├── app/
│   │   ├── api/          # API routers
│   │   ├── models/       # SQLAlchemy models
│   │   ├── schemas/      # Pydantic schemas
│   │   ├── services/     # Business logic
│   │   ├── config.py     # Settings
│   │   ├── database.py   # DB connection
│   │   └── main.py       # FastAPI app
│   └── pyproject.toml
├── frontend/
│   └── src/
├── data/                 # Billing data uploads
└── CLAUDE.md
```

### Data Flow

1. **Billing Data Upload:** CSV/JSON/JSONL upload → Parse & store in `billing_data` table → Reference for amount input

2. **Smart Preset Flow:** Select target month → Select preset group → Backend calculates dates, substitutes text templates, fetches amounts → Grid display → User review/edit → Final generation

### Database Schema (Key Tables)

**Master Tables:** `account_codes`, `cost_centers`, `tax_codes`, `customers`

**Billing Tables:**
- `billing_data` - Uploaded billing records (vendor, billing_month, amount, etc.)
- `preset_groups` - Template groups
- `preset_items` - Individual slip rules with day_rule, text_template, holiday_rule

### API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/billing/upload/{vendor}` | Upload billing data (CSV/JSON/JSONL) |
| GET | `/api/billing/` | Query billing data |
| GET | `/api/billing/summary` | Billing data summary |
| GET | `/api/master/accounts` | Account code list |
| GET | `/api/presets` | Preset group list |
| POST | `/api/slips/generate/preset` | Generate slips from preset |
| POST | `/api/slips/export` | Export to Excel/CSV |

## Key Business Logic

- **Date fields:** `BLDAT` (증빙일/document date), `BUDAT` (전기일/posting date)
- **Holiday adjustment:** Forward/Backward/Exact (uses `workalendar` for Korean holidays)
- **Debit/Credit balancing:** UI should show running totals and prevent unbalanced submissions
- **Billing data vendors:** alibaba (first test), others TBD
