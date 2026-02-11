import axios from 'axios';

const api = axios.create({
  baseURL: '/api',
  headers: {
    'Content-Type': 'application/json',
  },
});

// Alibaba Billing
export const alibabaApi = {
  upload: (billingType: 'enduser' | 'reseller', file: File) => {
    const formData = new FormData();
    formData.append('file', file);
    return api.post(`/alibaba/upload/${billingType}`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
  },
  getSummary: (params: { billing_type?: string; billing_cycle?: string }) =>
    api.get('/alibaba/summary', { params }),
  getList: (params: { billing_type?: string; billing_cycle?: string; limit?: number }) =>
    api.get('/alibaba/', { params }),
  delete: (params: { billing_type?: string; billing_cycle?: string }) =>
    api.delete('/alibaba/', { params }),
};

// Master Data
export const masterApi = {
  uploadBPCodes: (file: File) => {
    const formData = new FormData();
    formData.append('file', file);
    return api.post('/master/bp-codes/upload', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
  },
  getBPCodes: (params: { search?: string; limit?: number }) =>
    api.get('/master/bp-codes', { params }),
  uploadAccountCodes: (file: File) => {
    const formData = new FormData();
    formData.append('file', file);
    return api.post('/master/account-codes/upload', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
  },
  getAccountCodes: (params?: { search?: string }) =>
    api.get('/master/account-codes', { params }),
  uploadContracts: (file: File) => {
    const formData = new FormData();
    formData.append('file', file);
    return api.post('/master/contracts/upload', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
  },
  getContracts: (params: { vendor?: string }) =>
    api.get('/master/contracts', { params }),
};

// HB Data
export const hbApi = {
  uploadCompanies: (file: File, vendor = 'alibaba') => {
    const formData = new FormData();
    formData.append('file', file);
    return api.post(`/hb/companies/upload?vendor=${vendor}`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
  },
  getCompanies: (params: { vendor?: string; search?: string; has_bp?: boolean }) =>
    api.get('/hb/companies', { params }),
  updateCompany: (seq: number, data: { bp_number?: string }) =>
    api.patch(`/hb/companies/${seq}`, data),
  uploadContracts: (file: File, vendor = 'alibaba') => {
    const formData = new FormData();
    formData.append('file', file);
    return api.post(`/hb/contracts/upload?vendor=${vendor}`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
  },
  getContracts: (params: { vendor?: string; search?: string; enabled?: boolean }) =>
    api.get('/hb/contracts', { params }),
  getContract: (seq: number) => api.get(`/hb/contracts/${seq}`),
  updateContract: (seq: number, data: { sales_contract_code?: string; sales_person?: string }) =>
    api.patch(`/hb/contracts/${seq}`, data),
  uploadAccounts: (file: File, vendor = 'alibaba') => {
    const formData = new FormData();
    formData.append('file', file);
    return api.post(`/hb/accounts/upload?vendor=${vendor}`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
  },
  getAccounts: (params: { vendor?: string; search?: string; has_contract?: boolean }) =>
    api.get('/hb/accounts', { params }),
  billingLookup: (uid: string, vendor = 'alibaba') =>
    api.get('/hb/billing-lookup', { params: { uid, vendor } }),
  createMapping: (data: { account_id: string; contract_seq: number }) =>
    api.post('/hb/mappings', data),
};

// File Import (로컬 파일 임포트)
export const importApi = {
  scan: () => api.get('/import/scan'),
  importBilling: (billingType: 'enduser' | 'reseller', filename: string) =>
    api.post(`/import/billing/${billingType}`, null, { params: { filename } }),
  importMaster: (masterType: string, filename?: string) =>
    api.post(`/import/master/${masterType}`, null, { params: { filename } }),
  importHB: (dataType: string, filename?: string) =>
    api.post(`/import/hb/${dataType}`, null, { params: { filename } }),
  importAll: () => api.post('/import/all'),
};

// Billing Profile & Deposits
export const billingProfileApi = {
  getProfiles: (params?: { company_seq?: number; vendor?: string }) =>
    api.get('/billing-profile/', { params }),
  getProfile: (id: number) => api.get(`/billing-profile/${id}`),
  createProfile: (data: {
    company_seq: number;
    vendor: string;
    payment_type?: string;
    has_sales_agreement?: boolean;
    has_purchase_agreement?: boolean;
    currency?: string;
    hkont_sales?: string;
    hkont_purchase?: string;
    ar_account?: string;
    ap_account?: string;
    note?: string;
  }) => api.post('/billing-profile/', data),
  updateProfile: (id: number, data: {
    payment_type?: string;
    has_sales_agreement?: boolean;
    has_purchase_agreement?: boolean;
    currency?: string;
    hkont_sales?: string;
    hkont_purchase?: string;
    ar_account?: string;
    ap_account?: string;
    note?: string;
  }) => api.patch(`/billing-profile/${id}`, data),
  deleteProfile: (id: number) => api.delete(`/billing-profile/${id}`),
  // Deposits
  getDeposits: (params?: { profile_id?: number; company_seq?: number; vendor?: string; include_exhausted?: boolean }) =>
    api.get('/billing-profile/deposits', { params }),
  getDeposit: (id: number) => api.get(`/billing-profile/deposits/${id}`),
  createDeposit: (data: {
    profile_id: number;
    deposit_date: string;
    amount: number;
    currency?: string;
    exchange_rate?: number;
    reference?: string;
    description?: string;
  }) => api.post('/billing-profile/deposits', data),
  updateDeposit: (id: number, data: {
    deposit_date?: string;
    amount?: number;
    currency?: string;
    exchange_rate?: number;
    reference?: string;
    description?: string;
  }) => api.patch(`/billing-profile/deposits/${id}`, data),
  useDeposit: (data: {
    deposit_id: number;
    usage_date: string;
    amount: number;
    billing_cycle?: string;
    uid?: string;
    description?: string;
  }) => api.post('/billing-profile/deposits/use', data),
  useDepositFifo: (params: {
    profile_id: number;
    amount: number;
    usage_date: string;
    billing_cycle?: string;
    uid?: string;
    description?: string;
  }) => api.post('/billing-profile/deposits/use-fifo', null, { params }),
  getDepositBalance: (profileId: number) => api.get(`/billing-profile/deposits/balance/${profileId}`),
};

// Contract Billing Profile
export const contractBillingProfileApi = {
  getProfiles: (params?: { company_seq?: number; contract_seq?: number; vendor?: string }) =>
    api.get('/contract-billing-profile/', { params }),
  getByCompany: (companySeq: number, vendor = 'alibaba') =>
    api.get(`/contract-billing-profile/by-company/${companySeq}`, { params: { vendor } }),
  getProfile: (id: number) => api.get(`/contract-billing-profile/${id}`),
  createProfile: (data: {
    contract_seq: number;
    vendor: string;
    payment_type?: string;
    has_sales_agreement?: boolean;
    has_purchase_agreement?: boolean;
    currency?: string;
    exchange_rate_type?: string;
    custom_exchange_rate_date?: string;
    hkont_sales?: string;
    hkont_purchase?: string;
    ar_account?: string;
    ap_account?: string;
    rounding_rule_override?: string;
    note?: string;
  }) => api.post('/contract-billing-profile/', data),
  updateProfile: (id: number, data: {
    payment_type?: string;
    has_sales_agreement?: boolean;
    has_purchase_agreement?: boolean;
    currency?: string;
    exchange_rate_type?: string;
    custom_exchange_rate_date?: string;
    hkont_sales?: string;
    hkont_purchase?: string;
    ar_account?: string;
    ap_account?: string;
    rounding_rule_override?: string;
    note?: string;
  }) => api.patch(`/contract-billing-profile/${id}`, data),
  deleteProfile: (id: number) => api.delete(`/contract-billing-profile/${id}`),
  // Deposits
  getDeposits: (params?: { contract_profile_id?: number; contract_seq?: number; vendor?: string; include_exhausted?: boolean }) =>
    api.get('/contract-billing-profile/deposits', { params }),
  createDeposit: (data: {
    contract_profile_id: number;
    deposit_date: string;
    amount: number;
    currency?: string;
    exchange_rate?: number;
    reference?: string;
    description?: string;
  }) => api.post('/contract-billing-profile/deposits', data),
  updateDeposit: (id: number, data: {
    deposit_date?: string;
    amount?: number;
    currency?: string;
    exchange_rate?: number;
    reference?: string;
    description?: string;
  }) => api.patch(`/contract-billing-profile/deposits/${id}`, data),
  useDepositFifo: (params: {
    contract_profile_id: number;
    amount: number;
    usage_date: string;
    billing_cycle?: string;
    uid?: string;
    description?: string;
  }) => api.post('/contract-billing-profile/deposits/use-fifo', null, { params }),
  getDepositBalance: (contractProfileId: number) => api.get(`/contract-billing-profile/deposits/balance/${contractProfileId}`),
};

// Slip
export const slipApi = {
  createExchangeRate: (data: { rate: number; rate_date: string }) =>
    api.post('/slip/exchange-rates', data),
  getExchangeRates: (params: { year_month?: string }) =>
    api.get('/slip/exchange-rates', { params }),
  getLatestRate: () => api.get('/slip/exchange-rates/latest'),
  getRateByDate: (params: { rate_date: string; currency_from?: string }) =>
    api.get('/slip/exchange-rates/by-date', { params }),
  getFirstOfMonthRate: (params: { year_month: string; currency_from?: string }) =>
    api.get('/slip/exchange-rates/first-of-month', { params }),
  calculateRateDate: (params: {
    vendor?: string;
    slip_type: string;
    document_date: string;
    billing_cycle?: string;
  }) => api.get('/slip/exchange-rates/calculate-date', { params }),
  syncRatesFromHB: (data?: { limit?: number }) =>
    api.post('/slip/exchange-rates/sync-hb', data || {}),
  getConfig: (vendor: string) => api.get(`/slip/config/${vendor}`),
  updateConfig: (vendor: string, data: Record<string, string | boolean>) =>
    api.put(`/slip/config/${vendor}`, data),
  generate: (data: {
    billing_cycle: string;
    slip_type: 'sales' | 'purchase';
    document_date: string;
    exchange_rate?: number;
    invoice_number?: string;
    auto_exchange_rate?: boolean;
    include_additional_charges?: boolean;
    apply_pro_rata?: boolean;
    apply_split_billing?: boolean;
    overseas_exchange_rate_input?: number;  // 해외 인보이스 기본 환율
  }) => api.post('/slip/generate', data),
  getSlips: (params: {
    batch_id?: string;
    billing_cycle?: string;
    slip_type?: string;
    has_bp?: boolean;
    limit?: number;
    offset?: number;
  }) => api.get('/slip/', { params }),
  getBatches: () => api.get('/slip/batches'),
  updateSlip: (slipId: number, data: { partner?: string; wrbtr?: number; zzsconid?: string }) =>
    api.patch(`/slip/${slipId}`, data),
  confirm: (batchId: string) => api.post(`/slip/confirm/${batchId}`),
  export: (batchId: string) => `/api/slip/export/${batchId}`,
  deleteBatch: (batchId: string) => api.delete(`/slip/batch/${batchId}`),
};

// Additional Charges
export const additionalChargeApi = {
  getCharges: (params?: { contract_seq?: number; charge_type?: string; is_active?: boolean }) =>
    api.get('/additional-charges/', { params }),
  getCharge: (id: number) => api.get(`/additional-charges/${id}`),
  createCharge: (data: {
    contract_seq: number;
    name: string;
    description?: string;
    charge_type?: string;
    amount: number;
    currency?: string;
    recurrence_type?: string;
    start_date?: string;
    end_date?: string;
    applies_to_sales?: boolean;
    applies_to_purchase?: boolean;
  }) => api.post('/additional-charges/', data),
  updateCharge: (id: number, data: {
    name?: string;
    description?: string;
    charge_type?: string;
    amount?: number;
    currency?: string;
    recurrence_type?: string;
    start_date?: string;
    end_date?: string;
    applies_to_sales?: boolean;
    applies_to_purchase?: boolean;
    is_active?: boolean;
  }) => api.patch(`/additional-charges/${id}`, data),
  deleteCharge: (id: number) => api.delete(`/additional-charges/${id}`),
  getByContract: (contractSeq: number, includeInactive = false) =>
    api.get(`/additional-charges/by-contract/${contractSeq}`, { params: { include_inactive: includeInactive } }),
};

// Pro Rata
export const proRataApi = {
  getPeriods: (params?: { contract_seq?: number; billing_cycle?: string }) =>
    api.get('/pro-rata/periods', { params }),
  getPeriod: (id: number) => api.get(`/pro-rata/periods/${id}`),
  createPeriod: (data: {
    contract_seq: number;
    billing_cycle: string;
    start_day: number;
    end_day: number;
    note?: string;
  }) => api.post('/pro-rata/periods', data),
  updatePeriod: (id: number, data: { start_day?: number; end_day?: number; note?: string }) =>
    api.patch(`/pro-rata/periods/${id}`, data),
  deletePeriod: (id: number) => api.delete(`/pro-rata/periods/${id}`),
  calculate: (params: { contract_seq: number; billing_cycle: string }) =>
    api.get('/pro-rata/calculate', { params }),
};

// Slip Template
export const slipTemplateApi = {
  scanFiles: () => api.get('/slip/templates/scan-files'),
  analyzeFile: (file: File) => {
    const formData = new FormData();
    formData.append('file', file);
    return api.post('/slip/templates/analyze', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
  },
  analyzePath: (filePath: string) =>
    api.post('/slip/templates/analyze-path', null, { params: { file_path: filePath } }),
  importFile: (file: File, name?: string) => {
    const formData = new FormData();
    formData.append('file', file);
    return api.post('/slip/templates/import', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
      params: name ? { name } : undefined,
    });
  },
  importPath: (filePath: string, name?: string) =>
    api.post('/slip/templates/import-path', null, { params: { file_path: filePath, name } }),
  getTemplates: (params?: { slip_type?: string; active_only?: boolean }) =>
    api.get('/slip/templates/', { params }),
  getTemplate: (id: number) => api.get(`/slip/templates/${id}`),
  createTemplate: (data: {
    name: string;
    slip_type: string;
    columns: Record<string, unknown>[];
    fixed_values: Record<string, unknown>;
    account_mappings: Record<string, Record<string, string>>;
    contract_pattern?: Record<string, string>;
    description_template?: string;
    source_file?: string;
  }) => api.post('/slip/templates/', data),
  updateTemplate: (id: number, data: {
    name?: string;
    columns?: Record<string, unknown>[];
    fixed_values?: Record<string, unknown>;
    account_mappings?: Record<string, Record<string, string>>;
    contract_pattern?: Record<string, string>;
    description_template?: string;
    is_active?: boolean;
  }) => api.patch(`/slip/templates/${id}`, data),
  deleteTemplate: (id: number) => api.delete(`/slip/templates/${id}`),
  // Profile extraction
  extractProfilesFile: (file: File) => {
    const formData = new FormData();
    formData.append('file', file);
    return api.post('/slip/templates/extract-profiles', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
  },
  extractProfilesPath: (filePath: string) =>
    api.post('/slip/templates/extract-profiles-path', null, { params: { file_path: filePath } }),
  applyProfiles: (data: {
    profiles: Record<string, unknown>[];
    vendor?: string;
    overwrite?: boolean;
  }) => api.post('/slip/templates/apply-profiles', data),
};

// Split Billing
export const splitBillingApi = {
  getRules: (params?: { source_account_id?: string; source_contract_seq?: number; is_active?: boolean }) =>
    api.get('/split-billing/rules', { params }),
  getRule: (id: number) => api.get(`/split-billing/rules/${id}`),
  createRule: (data: {
    source_account_id: string;
    source_contract_seq: number;
    name?: string;
    effective_from?: string;
    effective_to?: string;
    allocations: {
      target_company_seq: number;
      split_type?: string;
      split_value: number;
      priority?: number;
      note?: string;
    }[];
  }) => api.post('/split-billing/rules', data),
  updateRule: (id: number, data: {
    name?: string;
    effective_from?: string;
    effective_to?: string;
    is_active?: boolean;
  }) => api.patch(`/split-billing/rules/${id}`, data),
  deleteRule: (id: number) => api.delete(`/split-billing/rules/${id}`),
  addAllocation: (ruleId: number, data: {
    target_company_seq: number;
    split_type?: string;
    split_value: number;
    priority?: number;
    note?: string;
  }) => api.post(`/split-billing/rules/${ruleId}/allocations`, data),
  updateAllocation: (allocationId: number, data: {
    target_company_seq?: number;
    split_type?: string;
    split_value?: number;
    priority?: number;
    note?: string;
  }) => api.patch(`/split-billing/allocations/${allocationId}`, data),
  deleteAllocation: (allocationId: number) => api.delete(`/split-billing/allocations/${allocationId}`),
  simulate: (data: { source_account_id: string; amount_usd: number; billing_cycle: string }) =>
    api.post('/split-billing/simulate', data),
};

export default api;
