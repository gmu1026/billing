// Billing
export interface BillingSummaryItem {
  uid: string;
  user_name: string | null;
  total_amount: number;
  record_count: number;
}

export interface BillingSummary {
  billing_type: string;
  billing_cycle: string | null;
  total_amount: number;
  user_count: number;
  by_user: BillingSummaryItem[];
}

// BP Code
export interface BPCode {
  bp_number: string;
  name: string | null;
  road_address: string | null;
  tax_number: string | null;
  representative: string | null;
  display: string;
}

// HB Company
export interface HBCompany {
  seq: number;
  name: string;
  license: string | null;
  address: string | null;
  ceo_name: string | null;
  bp_number: string | null;
  manager_name: string | null;
  is_active: boolean;
}

// HB Contract
export interface HBContract {
  seq: number;
  name: string;
  company_name: string | null;
  company_seq: number | null;
  corporation: string | null;
  sales_person: string | null;
  discount_rate: number;
  enabled: boolean;
  sales_contract_code: string | null;
}

export interface HBContractDetail extends HBContract {
  vendor: string;
  charge_currency: string;
  exchange_type: string | null;
  company: {
    seq: number;
    name: string;
    bp_number: string | null;
  } | null;
  accounts: {
    id: string;
    name: string | null;
    mapping_type: string;
    is_manual: boolean;
  }[];
}

// HB Account
export interface HBAccount {
  id: string;
  name: string | null;
  original_name: string | null;
  master_id: string | null;
  corporation: string | null;
  is_active: boolean;
}

// Slip
export interface SlipRecord {
  id: number;
  batch_id: string;
  seqno: number;
  slip_type: string;
  billing_cycle: string;
  partner: string | null;
  partner_name: string | null;
  wrbtr: number;
  wrbtr_usd: number;
  sgtxt: string | null;
  zzsconid: string | null;
  uid: string | null;
  is_confirmed: boolean;
}

export interface SlipBatch {
  batch_id: string;
  billing_cycle: string;
  slip_type: string;
  count: number;
  total_krw: number;
  created_at: string | null;
}

export interface ExchangeRate {
  id: number;
  rate: number;
  rate_date: string;
  currency_from: string;
  currency_to: string;
  source: string | null;
}

// API Response
export interface UploadResponse {
  success: boolean;
  inserted?: number;
  updated?: number;
  total_rows?: number;
  errors?: string[];
}

export interface GenerateResponse {
  success: boolean;
  batch_id: string;
  billing_cycle: string;
  slip_type: string;
  exchange_rate: number;
  total_slips: number;
  slips_with_bp: number;
  slips_no_bp: number;
  no_mapping_details: {
    uid: string;
    amount_usd: number;
    amount_krw: number;
    account_name: string | null;
    contract_name: string | null;
    company_name: string | null;
  }[];
}
