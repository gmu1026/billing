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

// Slip
export const slipApi = {
  createExchangeRate: (data: { rate: number; rate_date: string }) =>
    api.post('/slip/exchange-rates', data),
  getExchangeRates: (params: { year_month?: string }) =>
    api.get('/slip/exchange-rates', { params }),
  getLatestRate: () => api.get('/slip/exchange-rates/latest'),
  getConfig: (vendor: string) => api.get(`/slip/config/${vendor}`),
  updateConfig: (vendor: string, data: Record<string, string>) =>
    api.put(`/slip/config/${vendor}`, data),
  generate: (data: {
    billing_cycle: string;
    slip_type: 'sales' | 'purchase';
    document_date: string;
    exchange_rate: number;
    invoice_number?: string;
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

export default api;
