import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { billingProfileApi, contractBillingProfileApi, hbApi, masterApi } from '../api/client';
import { Card, Input, Alert, Spinner, Table, Th, Td } from '../components/ui';

type Tab = 'contracts' | 'companies' | 'deposits';

interface BillingProfile {
  id: number;
  company_seq: number;
  company_name: string;
  vendor: string;
  payment_type: string;
  has_sales_agreement: boolean;
  has_purchase_agreement: boolean;
  currency: string;
  hkont_sales: string | null;
  hkont_purchase: string | null;
  ar_account: string | null;
  ap_account: string | null;
  note: string | null;
}

interface ContractProfile {
  id: number;
  contract_seq: number;
  contract_name: string;
  company_seq: number;
  company_name: string;
  vendor: string;
  payment_type: string;
  tax_code: string;
  has_sales_agreement: boolean;
  has_purchase_agreement: boolean;
  currency: string;
  exchange_rate_type: string | null;
  custom_exchange_rate_date: string | null;
  hkont_sales: string | null;
  hkont_purchase: string | null;
  ar_account: string | null;
  ap_account: string | null;
  rounding_rule_override: string | null;
  note: string | null;
}

interface ContractWithProfile {
  contract_seq: number;
  contract_name: string;
  corporation: string;
  discount_rate: number;
  sales_person: string | null;
  sales_contract_code: string | null;
  has_profile: boolean;
  profile: {
    id: number;
    payment_type: string;
    currency: string;
    has_sales_agreement: boolean;
    has_purchase_agreement: boolean;
    rounding_rule_override: string | null;
  } | null;
}

interface Deposit {
  id: number;
  profile_id: number | null;
  contract_profile_id: number | null;
  contract_name: string | null;
  company_name: string | null;
  vendor: string;
  deposit_date: string;
  amount: number;
  currency: string;
  exchange_rate: number | null;
  remaining_amount: number;
  is_exhausted: boolean;
  reference: string | null;
  description: string | null;
}

interface Company {
  seq: number;
  name: string;
  vendor: string;
  is_overseas: boolean;
  default_currency: string;
}

interface AccountCode {
  hkont: string;
  name_short: string;
  name_long: string;
  account_group: string;
}

const ROUNDING_RULES = [
  { value: '', label: '벤더 기본값 사용' },
  { value: 'floor', label: '버림 (FLOOR)' },
  { value: 'round_half_up', label: '반올림 (ROUND_HALF_UP)' },
  { value: 'ceiling', label: '올림 (CEILING)' },
];

// 결제 방식 - 부가세코드 연동
const PAYMENT_TYPES = [
  { value: 'tax_invoice', label: '세금계산서', taxCode: 'A1' },
  { value: 'deposit', label: '예치금', taxCode: 'A1' },
  { value: 'card', label: '카드결제', taxCode: 'A3' },
  { value: 'reverse_issue', label: '역발행', taxCode: 'A1' },
  { value: 'overseas_invoice', label: '해외인보이스', taxCode: 'B1' },
];

// 해외인보이스 환율 적용 기준
const EXCHANGE_RATE_TYPES = [
  { value: 'billing_date', label: '빌링월 말일' },
  { value: 'document_date', label: '전표 증빙일' },
  { value: 'custom_date', label: '수동 지정' },
];

export default function BillingProfile() {
  const queryClient = useQueryClient();
  const [activeTab, setActiveTab] = useState<Tab>('contracts');
  const [showForm, setShowForm] = useState(false);
  const [showContractForm, setShowContractForm] = useState(false);
  const [showDepositForm, setShowDepositForm] = useState(false);
  const [selectedProfile, setSelectedProfile] = useState<BillingProfile | null>(null);
  const [selectedContractProfile, setSelectedContractProfile] = useState<ContractProfile | null>(null);
  const [selectedCompanySeq, setSelectedCompanySeq] = useState<string>('');
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  // Form states for company profile
  const [formData, setFormData] = useState({
    company_seq: '',
    vendor: 'alibaba',
    payment_type: 'tax_invoice',
    has_sales_agreement: false,
    has_purchase_agreement: false,
    currency: 'KRW',
    hkont_sales: '',
    hkont_purchase: '',
    ar_account: '',
    ap_account: '',
    note: '',
  });

  // Form states for contract profile
  const [contractFormData, setContractFormData] = useState({
    contract_seq: '',
    vendor: 'alibaba',
    payment_type: 'tax_invoice',
    has_sales_agreement: false,
    has_purchase_agreement: false,
    currency: 'KRW',
    exchange_rate_type: '',
    custom_exchange_rate_date: '',
    hkont_sales: '',
    hkont_purchase: '',
    ar_account: '',
    ap_account: '',
    rounding_rule_override: '',
    note: '',
  });

  const [depositFormData, setDepositFormData] = useState({
    profileType: 'contract' as 'company' | 'contract',
    profile_id: '',
    deposit_date: new Date().toISOString().slice(0, 10),
    amount: '',
    currency: 'KRW',
    exchange_rate: '',
    reference: '',
    description: '',
  });

  const [editingDeposit, setEditingDeposit] = useState<Deposit | null>(null);
  const [editDepositFormData, setEditDepositFormData] = useState({
    deposit_date: '',
    amount: '',
    currency: 'KRW',
    exchange_rate: '',
    reference: '',
    description: '',
  });

  // Queries
  const { data: profiles, isLoading: profilesLoading } = useQuery({
    queryKey: ['billingProfiles'],
    queryFn: () => billingProfileApi.getProfiles().then((res) => res.data as BillingProfile[]),
    enabled: activeTab === 'companies' || activeTab === 'deposits',
  });

  const { data: contractProfiles, isLoading: contractProfilesLoading } = useQuery({
    queryKey: ['contractBillingProfiles'],
    queryFn: () => contractBillingProfileApi.getProfiles().then((res) => res.data as ContractProfile[]),
    enabled: activeTab === 'contracts' || activeTab === 'deposits',
  });

  const { data: contractsWithProfiles, isLoading: contractsLoading } = useQuery({
    queryKey: ['contractsWithProfiles', selectedCompanySeq],
    queryFn: () =>
      contractBillingProfileApi
        .getByCompany(parseInt(selectedCompanySeq))
        .then((res) => res.data as { company_name: string; is_overseas: boolean; contracts: ContractWithProfile[] }),
    enabled: activeTab === 'contracts' && !!selectedCompanySeq,
  });

  const { data: companyDeposits, isLoading: companyDepositsLoading } = useQuery({
    queryKey: ['companyDeposits'],
    queryFn: () => billingProfileApi.getDeposits({ include_exhausted: true }).then((res) => res.data as Deposit[]),
    enabled: activeTab === 'deposits',
    staleTime: 0,
  });

  const { data: contractDeposits, isLoading: contractDepositsLoading } = useQuery({
    queryKey: ['contractDeposits'],
    queryFn: () => contractBillingProfileApi.getDeposits({ include_exhausted: true }).then((res) => res.data as Deposit[]),
    enabled: activeTab === 'deposits',
    staleTime: 0,
  });

  const deposits = [...(companyDeposits ?? []), ...(contractDeposits ?? [])].sort(
    (a, b) => a.deposit_date.localeCompare(b.deposit_date)
  );
  const depositsLoading = companyDepositsLoading || contractDepositsLoading;

  const { data: companies } = useQuery({
    queryKey: ['hbCompanies'],
    queryFn: () => hbApi.getCompanies({}).then((res) => res.data as Company[]),
  });

  const { data: accountCodes } = useQuery({
    queryKey: ['accountCodes'],
    queryFn: () => masterApi.getAccountCodes().then((res) => res.data as AccountCode[]),
  });

  // Mutations for company profiles
  const createProfile = useMutation({
    mutationFn: (data: typeof formData) =>
      billingProfileApi.createProfile({
        company_seq: parseInt(data.company_seq),
        vendor: data.vendor,
        payment_type: data.payment_type,
        has_sales_agreement: data.has_sales_agreement,
        has_purchase_agreement: data.has_purchase_agreement,
        currency: data.currency,
        hkont_sales: data.hkont_sales || undefined,
        hkont_purchase: data.hkont_purchase || undefined,
        ar_account: data.ar_account || undefined,
        ap_account: data.ap_account || undefined,
        note: data.note || undefined,
      }),
    onSuccess: () => {
      setMessage({ type: 'success', text: '청구 프로필이 생성되었습니다.' });
      setShowForm(false);
      resetForm();
      queryClient.invalidateQueries({ queryKey: ['billingProfiles'] });
    },
    onError: (error: Error) => {
      setMessage({ type: 'error', text: error.message || '프로필 생성 실패' });
    },
  });

  const updateProfile = useMutation({
    mutationFn: ({ id, data }: { id: number; data: Partial<typeof formData> }) =>
      billingProfileApi.updateProfile(id, {
        payment_type: data.payment_type,
        has_sales_agreement: data.has_sales_agreement,
        has_purchase_agreement: data.has_purchase_agreement,
        currency: data.currency,
        hkont_sales: data.hkont_sales || undefined,
        hkont_purchase: data.hkont_purchase || undefined,
        ar_account: data.ar_account || undefined,
        ap_account: data.ap_account || undefined,
        note: data.note || undefined,
      }),
    onSuccess: () => {
      setMessage({ type: 'success', text: '프로필이 수정되었습니다.' });
      setShowForm(false);
      setSelectedProfile(null);
      resetForm();
      queryClient.invalidateQueries({ queryKey: ['billingProfiles'] });
    },
  });

  const deleteProfile = useMutation({
    mutationFn: (id: number) => billingProfileApi.deleteProfile(id),
    onSuccess: () => {
      setMessage({ type: 'success', text: '프로필이 삭제되었습니다.' });
      queryClient.invalidateQueries({ queryKey: ['billingProfiles'] });
    },
    onError: (error: Error) => {
      setMessage({ type: 'error', text: error.message || '삭제 실패 (예치금이 있으면 삭제 불가)' });
    },
  });

  // Mutations for contract profiles
  const createContractProfile = useMutation({
    mutationFn: (data: typeof contractFormData) =>
      contractBillingProfileApi.createProfile({
        contract_seq: parseInt(data.contract_seq),
        vendor: data.vendor,
        payment_type: data.payment_type,
        has_sales_agreement: data.has_sales_agreement,
        has_purchase_agreement: data.has_purchase_agreement,
        currency: data.currency,
        exchange_rate_type: data.exchange_rate_type || undefined,
        custom_exchange_rate_date: data.custom_exchange_rate_date || undefined,
        hkont_sales: data.hkont_sales || undefined,
        hkont_purchase: data.hkont_purchase || undefined,
        ar_account: data.ar_account || undefined,
        ap_account: data.ap_account || undefined,
        rounding_rule_override: data.rounding_rule_override || undefined,
        note: data.note || undefined,
      }),
    onSuccess: () => {
      setMessage({ type: 'success', text: '계약 청구 프로필이 생성되었습니다.' });
      setShowContractForm(false);
      resetContractForm();
      queryClient.invalidateQueries({ queryKey: ['contractBillingProfiles'] });
      queryClient.invalidateQueries({ queryKey: ['contractsWithProfiles'] });
    },
    onError: (error: Error) => {
      setMessage({ type: 'error', text: error.message || '프로필 생성 실패' });
    },
  });

  const updateContractProfile = useMutation({
    mutationFn: ({ id, data }: { id: number; data: Partial<typeof contractFormData> }) =>
      contractBillingProfileApi.updateProfile(id, {
        payment_type: data.payment_type,
        has_sales_agreement: data.has_sales_agreement,
        has_purchase_agreement: data.has_purchase_agreement,
        currency: data.currency,
        exchange_rate_type: data.exchange_rate_type || undefined,
        custom_exchange_rate_date: data.custom_exchange_rate_date || undefined,
        hkont_sales: data.hkont_sales || undefined,
        hkont_purchase: data.hkont_purchase || undefined,
        ar_account: data.ar_account || undefined,
        ap_account: data.ap_account || undefined,
        rounding_rule_override: data.rounding_rule_override || undefined,
        note: data.note || undefined,
      }),
    onSuccess: () => {
      setMessage({ type: 'success', text: '계약 프로필이 수정되었습니다.' });
      setShowContractForm(false);
      setSelectedContractProfile(null);
      resetContractForm();
      queryClient.invalidateQueries({ queryKey: ['contractBillingProfiles'] });
      queryClient.invalidateQueries({ queryKey: ['contractsWithProfiles'] });
    },
  });

  const deleteContractProfile = useMutation({
    mutationFn: (id: number) => contractBillingProfileApi.deleteProfile(id),
    onSuccess: () => {
      setMessage({ type: 'success', text: '계약 프로필이 삭제되었습니다.' });
      queryClient.invalidateQueries({ queryKey: ['contractBillingProfiles'] });
      queryClient.invalidateQueries({ queryKey: ['contractsWithProfiles'] });
    },
    onError: (error: Error) => {
      setMessage({ type: 'error', text: error.message || '삭제 실패 (예치금이 있으면 삭제 불가)' });
    },
  });

  const createDeposit = useMutation({
    mutationFn: (data: typeof depositFormData) => {
      const payload = {
        deposit_date: data.deposit_date,
        amount: parseFloat(data.amount),
        currency: data.currency,
        exchange_rate: data.exchange_rate ? parseFloat(data.exchange_rate) : undefined,
        reference: data.reference || undefined,
        description: data.description || undefined,
      };
      if (data.profileType === 'contract') {
        return contractBillingProfileApi.createDeposit({
          contract_profile_id: parseInt(data.profile_id),
          ...payload,
        });
      }
      return billingProfileApi.createDeposit({
        profile_id: parseInt(data.profile_id),
        ...payload,
      });
    },
    onSuccess: () => {
      setMessage({ type: 'success', text: '예치금이 등록되었습니다.' });
      setShowDepositForm(false);
      resetDepositForm();
      queryClient.invalidateQueries({ queryKey: ['companyDeposits'] });
      queryClient.invalidateQueries({ queryKey: ['contractDeposits'] });
    },
  });

  const updateDeposit = useMutation({
    mutationFn: ({ deposit, data }: { deposit: Deposit; data: typeof editDepositFormData }) => {
      const payload = {
        deposit_date: data.deposit_date,
        amount: data.amount ? parseFloat(data.amount) : undefined,
        currency: data.currency,
        exchange_rate: data.exchange_rate ? parseFloat(data.exchange_rate) : undefined,
        reference: data.reference || undefined,
        description: data.description || undefined,
      };
      if (deposit.contract_profile_id) {
        return contractBillingProfileApi.updateDeposit(deposit.id, payload);
      }
      return billingProfileApi.updateDeposit(deposit.id, payload);
    },
    onSuccess: () => {
      setMessage({ type: 'success', text: '예치금이 수정되었습니다.' });
      setEditingDeposit(null);
      queryClient.invalidateQueries({ queryKey: ['companyDeposits'] });
      queryClient.invalidateQueries({ queryKey: ['contractDeposits'] });
    },
    onError: () => {
      setMessage({ type: 'error', text: '예치금 수정에 실패했습니다.' });
    },
  });

  const resetForm = () => {
    setFormData({
      company_seq: '',
      vendor: 'alibaba',
      payment_type: 'tax_invoice',
      has_sales_agreement: false,
      has_purchase_agreement: false,
      currency: 'KRW',
      hkont_sales: '',
      hkont_purchase: '',
      ar_account: '',
      ap_account: '',
      note: '',
    });
  };

  const resetContractForm = () => {
    setContractFormData({
      contract_seq: '',
      vendor: 'alibaba',
      payment_type: 'tax_invoice',
      has_sales_agreement: false,
      has_purchase_agreement: false,
      currency: 'KRW',
      exchange_rate_type: '',
      custom_exchange_rate_date: '',
      hkont_sales: '',
      hkont_purchase: '',
      ar_account: '',
      ap_account: '',
      rounding_rule_override: '',
      note: '',
    });
  };

  const resetDepositForm = () => {
    setDepositFormData({
      profileType: 'contract',
      profile_id: '',
      deposit_date: new Date().toISOString().slice(0, 10),
      amount: '',
      currency: 'KRW',
      exchange_rate: '',
      reference: '',
      description: '',
    });
  };

  const handleEditProfile = (profile: BillingProfile) => {
    setSelectedProfile(profile);
    setFormData({
      company_seq: profile.company_seq.toString(),
      vendor: profile.vendor,
      payment_type: profile.payment_type,
      has_sales_agreement: profile.has_sales_agreement,
      has_purchase_agreement: profile.has_purchase_agreement,
      currency: profile.currency,
      hkont_sales: profile.hkont_sales || '',
      hkont_purchase: profile.hkont_purchase || '',
      ar_account: profile.ar_account || '',
      ap_account: profile.ap_account || '',
      note: profile.note || '',
    });
    setShowForm(true);
  };

  const handleEditContractProfile = (profile: ContractProfile) => {
    setSelectedContractProfile(profile);
    setContractFormData({
      contract_seq: profile.contract_seq.toString(),
      vendor: profile.vendor,
      payment_type: profile.payment_type,
      has_sales_agreement: profile.has_sales_agreement,
      has_purchase_agreement: profile.has_purchase_agreement,
      currency: profile.currency,
      exchange_rate_type: profile.exchange_rate_type || '',
      custom_exchange_rate_date: profile.custom_exchange_rate_date || '',
      hkont_sales: profile.hkont_sales || '',
      hkont_purchase: profile.hkont_purchase || '',
      ar_account: profile.ar_account || '',
      ap_account: profile.ap_account || '',
      rounding_rule_override: profile.rounding_rule_override || '',
      note: profile.note || '',
    });
    setShowContractForm(true);
  };

  const handleAddContractProfile = (contractSeq: number) => {
    const company = contractsWithProfiles;
    resetContractForm();
    setSelectedContractProfile(null);
    setContractFormData((prev) => ({
      ...prev,
      contract_seq: contractSeq.toString(),
      currency: company?.is_overseas ? 'USD' : 'KRW',
    }));
    setShowContractForm(true);
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (selectedProfile) {
      updateProfile.mutate({ id: selectedProfile.id, data: formData });
    } else {
      createProfile.mutate(formData);
    }
  };

  const handleContractSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (selectedContractProfile) {
      updateContractProfile.mutate({ id: selectedContractProfile.id, data: contractFormData });
    } else {
      createContractProfile.mutate(contractFormData);
    }
  };

  const handleDepositSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    createDeposit.mutate(depositFormData);
  };

  const handleEditDeposit = (deposit: Deposit) => {
    setEditingDeposit(deposit);
    setEditDepositFormData({
      deposit_date: deposit.deposit_date,
      amount: deposit.amount.toString(),
      currency: deposit.currency,
      exchange_rate: deposit.exchange_rate?.toString() ?? '',
      reference: deposit.reference ?? '',
      description: deposit.description ?? '',
    });
  };

  const handleEditDepositSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!editingDeposit) return;
    updateDeposit.mutate({ deposit: editingDeposit, data: editDepositFormData });
  };

  const tabs = [
    { id: 'contracts' as Tab, label: '계약별 프로필' },
    { id: 'companies' as Tab, label: '회사별 프로필 (레거시)' },
    { id: 'deposits' as Tab, label: '예치금 관리' },
  ];

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-bold text-gray-800">청구 설정 & 예치금</h2>
        <div className="flex gap-2">
          {activeTab === 'contracts' && selectedCompanySeq && (
            <button
              onClick={() => {
                resetContractForm();
                setSelectedContractProfile(null);
                setShowContractForm(true);
              }}
              className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
            >
              + 계약 프로필 추가
            </button>
          )}
          {activeTab === 'companies' && (
            <button
              onClick={() => {
                resetForm();
                setSelectedProfile(null);
                setShowForm(true);
              }}
              className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
            >
              + 프로필 추가
            </button>
          )}
          {activeTab === 'deposits' && (
            <button
              onClick={() => {
                resetDepositForm();
                setShowDepositForm(true);
              }}
              className="px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700"
            >
              + 예치금 등록
            </button>
          )}
        </div>
      </div>

      {message && (
        <Alert type={message.type}>
          {message.text}
          <button
            onClick={() => setMessage(null)}
            className="ml-4 text-sm underline"
          >
            닫기
          </button>
        </Alert>
      )}

      {/* Tabs */}
      <div className="border-b border-gray-200">
        <nav className="flex gap-4">
          {tabs.map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`py-2 px-4 border-b-2 font-medium text-sm ${
                activeTab === tab.id
                  ? 'border-blue-500 text-blue-600'
                  : 'border-transparent text-gray-500 hover:text-gray-700'
              }`}
            >
              {tab.label}
            </button>
          ))}
        </nav>
      </div>

      {/* Contract Profile Form Modal */}
      {showContractForm && (
        <Card title={selectedContractProfile ? '계약 프로필 수정' : '새 계약 청구 프로필'}>
          <form onSubmit={handleContractSubmit} className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">계약</label>
                {selectedContractProfile ? (
                  <div className="w-full border rounded-lg px-3 py-2 bg-gray-50">
                    {selectedContractProfile.contract_name}
                  </div>
                ) : (
                  <select
                    value={contractFormData.contract_seq}
                    onChange={(e) => setContractFormData({ ...contractFormData, contract_seq: e.target.value })}
                    className="w-full border rounded-lg px-3 py-2"
                    required
                  >
                    <option value="">선택...</option>
                    {contractsWithProfiles?.contracts
                      .filter((c) => !c.has_profile)
                      .map((c) => (
                        <option key={c.contract_seq} value={c.contract_seq.toString()}>
                          {c.contract_name} ({c.corporation})
                        </option>
                      ))}
                  </select>
                )}
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">벤더</label>
                <select
                  value={contractFormData.vendor}
                  onChange={(e) => setContractFormData({ ...contractFormData, vendor: e.target.value })}
                  className="w-full border rounded-lg px-3 py-2"
                  disabled={!!selectedContractProfile}
                >
                  <option value="alibaba">Alibaba Cloud</option>
                  <option value="gcp">GCP</option>
                  <option value="akamai">Akamai</option>
                </select>
              </div>
            </div>

            <div className="grid grid-cols-3 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">결제 방식</label>
                <select
                  value={contractFormData.payment_type}
                  onChange={(e) => setContractFormData({ ...contractFormData, payment_type: e.target.value })}
                  className="w-full border rounded-lg px-3 py-2"
                >
                  {PAYMENT_TYPES.map((pt) => (
                    <option key={pt.value} value={pt.value}>
                      {pt.label} ({pt.taxCode})
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">기본 통화</label>
                <select
                  value={contractFormData.currency}
                  onChange={(e) => setContractFormData({ ...contractFormData, currency: e.target.value })}
                  className="w-full border rounded-lg px-3 py-2"
                >
                  <option value="KRW">KRW (원화)</option>
                  <option value="USD">USD (달러)</option>
                  <option value="CNY">CNY (위안)</option>
                  <option value="JPY">JPY (엔화)</option>
                  <option value="SGD">SGD (싱가포르달러)</option>
                </select>
              </div>
              <div className="flex items-end gap-4">
                <label className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    checked={contractFormData.has_sales_agreement}
                    onChange={(e) => setContractFormData({ ...contractFormData, has_sales_agreement: e.target.checked })}
                    className="rounded"
                  />
                  <span className="text-sm">매출 약정</span>
                </label>
                <label className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    checked={contractFormData.has_purchase_agreement}
                    onChange={(e) => setContractFormData({ ...contractFormData, has_purchase_agreement: e.target.checked })}
                    className="rounded"
                  />
                  <span className="text-sm">매입 약정</span>
                </label>
              </div>
            </div>

            {/* 해외인보이스 환율 적용 설정 */}
            {contractFormData.payment_type === 'overseas_invoice' && (
              <div className="grid grid-cols-2 gap-4 p-3 bg-blue-50 border border-blue-200 rounded-lg">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">환율 적용 기준</label>
                  <select
                    value={contractFormData.exchange_rate_type}
                    onChange={(e) => setContractFormData({ ...contractFormData, exchange_rate_type: e.target.value })}
                    className="w-full border rounded-lg px-3 py-2"
                  >
                    <option value="">선택...</option>
                    {EXCHANGE_RATE_TYPES.map((ert) => (
                      <option key={ert.value} value={ert.value}>
                        {ert.label}
                      </option>
                    ))}
                  </select>
                </div>
                {contractFormData.exchange_rate_type === 'custom_date' && (
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">환율 적용일</label>
                    <input
                      type="date"
                      value={contractFormData.custom_exchange_rate_date}
                      onChange={(e) => setContractFormData({ ...contractFormData, custom_exchange_rate_date: e.target.value })}
                      className="w-full border rounded-lg px-3 py-2"
                    />
                  </div>
                )}
              </div>
            )}

            <div className="grid grid-cols-3 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">라운딩 규칙</label>
                <select
                  value={contractFormData.rounding_rule_override}
                  onChange={(e) => setContractFormData({ ...contractFormData, rounding_rule_override: e.target.value })}
                  className="w-full border rounded-lg px-3 py-2"
                >
                  {ROUNDING_RULES.map((rule) => (
                    <option key={rule.value} value={rule.value}>
                      {rule.label}
                    </option>
                  ))}
                </select>
              </div>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">매출 계정코드</label>
                <select
                  value={contractFormData.hkont_sales}
                  onChange={(e) => setContractFormData({ ...contractFormData, hkont_sales: e.target.value })}
                  className="w-full border rounded-lg px-3 py-2"
                >
                  <option value="">선택...</option>
                  {accountCodes?.map((ac) => (
                    <option key={ac.hkont} value={ac.hkont}>
                      {ac.hkont} - {ac.name_short}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">매입 계정코드</label>
                <select
                  value={contractFormData.hkont_purchase}
                  onChange={(e) => setContractFormData({ ...contractFormData, hkont_purchase: e.target.value })}
                  className="w-full border rounded-lg px-3 py-2"
                >
                  <option value="">선택...</option>
                  {accountCodes?.map((ac) => (
                    <option key={ac.hkont} value={ac.hkont}>
                      {ac.hkont} - {ac.name_short}
                    </option>
                  ))}
                </select>
              </div>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">채권과목</label>
                <select
                  value={contractFormData.ar_account}
                  onChange={(e) => setContractFormData({ ...contractFormData, ar_account: e.target.value })}
                  className="w-full border rounded-lg px-3 py-2"
                >
                  <option value="">선택...</option>
                  {accountCodes?.map((ac) => (
                    <option key={ac.hkont} value={ac.hkont}>
                      {ac.hkont} - {ac.name_short}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">채무과목</label>
                <select
                  value={contractFormData.ap_account}
                  onChange={(e) => setContractFormData({ ...contractFormData, ap_account: e.target.value })}
                  className="w-full border rounded-lg px-3 py-2"
                >
                  <option value="">선택...</option>
                  {accountCodes?.map((ac) => (
                    <option key={ac.hkont} value={ac.hkont}>
                      {ac.hkont} - {ac.name_short}
                    </option>
                  ))}
                </select>
              </div>
            </div>

            <Input
              label="메모"
              value={contractFormData.note}
              onChange={(e) => setContractFormData({ ...contractFormData, note: e.target.value })}
            />

            <div className="flex gap-2 justify-end">
              <button
                type="button"
                onClick={() => {
                  setShowContractForm(false);
                  setSelectedContractProfile(null);
                }}
                className="px-4 py-2 border rounded-lg hover:bg-gray-50"
              >
                취소
              </button>
              <button
                type="submit"
                className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
                disabled={createContractProfile.isPending || updateContractProfile.isPending}
              >
                {selectedContractProfile ? '수정' : '생성'}
              </button>
            </div>
          </form>
        </Card>
      )}

      {/* Company Profile Form Modal */}
      {showForm && (
        <Card title={selectedProfile ? '프로필 수정' : '새 청구 프로필'}>
          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">회사</label>
                <select
                  value={formData.company_seq}
                  onChange={(e) => {
                    const selectedSeq = e.target.value;
                    const selectedCompany = companies?.find((c) => c.seq.toString() === selectedSeq);
                    const defaultCurrency = selectedCompany?.is_overseas ? 'USD' : 'KRW';
                    setFormData({ ...formData, company_seq: selectedSeq, currency: defaultCurrency });
                  }}
                  className="w-full border rounded-lg px-3 py-2"
                  disabled={!!selectedProfile}
                  required
                >
                  <option value="">선택...</option>
                  {companies?.map((c) => (
                    <option key={c.seq} value={c.seq.toString()}>
                      {c.name} {c.is_overseas ? `(해외-${c.default_currency})` : ''}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">벤더</label>
                <select
                  value={formData.vendor}
                  onChange={(e) => setFormData({ ...formData, vendor: e.target.value })}
                  className="w-full border rounded-lg px-3 py-2"
                  disabled={!!selectedProfile}
                >
                  <option value="alibaba">Alibaba Cloud</option>
                  <option value="gcp">GCP</option>
                  <option value="akamai">Akamai</option>
                </select>
              </div>
            </div>

            <div className="grid grid-cols-3 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">결제 방식</label>
                <select
                  value={formData.payment_type}
                  onChange={(e) => setFormData({ ...formData, payment_type: e.target.value })}
                  className="w-full border rounded-lg px-3 py-2"
                >
                  {PAYMENT_TYPES.map((pt) => (
                    <option key={pt.value} value={pt.value}>
                      {pt.label} ({pt.taxCode})
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">기본 통화</label>
                <select
                  value={formData.currency}
                  onChange={(e) => setFormData({ ...formData, currency: e.target.value })}
                  className="w-full border rounded-lg px-3 py-2"
                >
                  <option value="KRW">KRW (원화)</option>
                  <option value="USD">USD (달러)</option>
                  <option value="CNY">CNY (위안)</option>
                  <option value="JPY">JPY (엔화)</option>
                  <option value="SGD">SGD (싱가포르달러)</option>
                </select>
              </div>
              <div className="flex items-end gap-4">
                <label className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    checked={formData.has_sales_agreement}
                    onChange={(e) => setFormData({ ...formData, has_sales_agreement: e.target.checked })}
                    className="rounded"
                  />
                  <span className="text-sm">매출 약정</span>
                </label>
                <label className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    checked={formData.has_purchase_agreement}
                    onChange={(e) => setFormData({ ...formData, has_purchase_agreement: e.target.checked })}
                    className="rounded"
                  />
                  <span className="text-sm">매입 약정</span>
                </label>
              </div>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">매출 계정코드</label>
                <select
                  value={formData.hkont_sales}
                  onChange={(e) => setFormData({ ...formData, hkont_sales: e.target.value })}
                  className="w-full border rounded-lg px-3 py-2"
                >
                  <option value="">선택...</option>
                  {accountCodes?.map((ac) => (
                    <option key={ac.hkont} value={ac.hkont}>
                      {ac.hkont} - {ac.name_short}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">매입 계정코드</label>
                <select
                  value={formData.hkont_purchase}
                  onChange={(e) => setFormData({ ...formData, hkont_purchase: e.target.value })}
                  className="w-full border rounded-lg px-3 py-2"
                >
                  <option value="">선택...</option>
                  {accountCodes?.map((ac) => (
                    <option key={ac.hkont} value={ac.hkont}>
                      {ac.hkont} - {ac.name_short}
                    </option>
                  ))}
                </select>
              </div>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">채권과목</label>
                <select
                  value={formData.ar_account}
                  onChange={(e) => setFormData({ ...formData, ar_account: e.target.value })}
                  className="w-full border rounded-lg px-3 py-2"
                >
                  <option value="">선택...</option>
                  {accountCodes?.map((ac) => (
                    <option key={ac.hkont} value={ac.hkont}>
                      {ac.hkont} - {ac.name_short}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">채무과목</label>
                <select
                  value={formData.ap_account}
                  onChange={(e) => setFormData({ ...formData, ap_account: e.target.value })}
                  className="w-full border rounded-lg px-3 py-2"
                >
                  <option value="">선택...</option>
                  {accountCodes?.map((ac) => (
                    <option key={ac.hkont} value={ac.hkont}>
                      {ac.hkont} - {ac.name_short}
                    </option>
                  ))}
                </select>
              </div>
            </div>

            <Input
              label="메모"
              value={formData.note}
              onChange={(e) => setFormData({ ...formData, note: e.target.value })}
            />

            <div className="flex gap-2 justify-end">
              <button
                type="button"
                onClick={() => {
                  setShowForm(false);
                  setSelectedProfile(null);
                }}
                className="px-4 py-2 border rounded-lg hover:bg-gray-50"
              >
                취소
              </button>
              <button
                type="submit"
                className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
                disabled={createProfile.isPending || updateProfile.isPending}
              >
                {selectedProfile ? '수정' : '생성'}
              </button>
            </div>
          </form>
        </Card>
      )}

      {/* Deposit Form Modal */}
      {showDepositForm && (
        <Card title="예치금 등록">
          <form onSubmit={handleDepositSubmit} className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">프로필 유형</label>
                <select
                  value={depositFormData.profileType}
                  onChange={(e) =>
                    setDepositFormData({
                      ...depositFormData,
                      profileType: e.target.value as 'company' | 'contract',
                      profile_id: '',
                    })
                  }
                  className="w-full border rounded-lg px-3 py-2"
                >
                  <option value="contract">계약별 프로필</option>
                  <option value="company">회사별 프로필 (레거시)</option>
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">청구 프로필</label>
                <select
                  value={depositFormData.profile_id}
                  onChange={(e) => setDepositFormData({ ...depositFormData, profile_id: e.target.value })}
                  className="w-full border rounded-lg px-3 py-2"
                  required
                >
                  <option value="">선택...</option>
                  {depositFormData.profileType === 'contract'
                    ? contractProfiles?.map((p) => (
                        <option key={p.id} value={p.id.toString()}>
                          {p.company_name} - {p.contract_name} ({p.vendor})
                        </option>
                      ))
                    : profiles?.map((p) => (
                        <option key={p.id} value={p.id.toString()}>
                          {p.company_name} ({p.vendor})
                        </option>
                      ))}
                </select>
              </div>
              <Input
                label="충전일"
                type="date"
                value={depositFormData.deposit_date}
                onChange={(e) => setDepositFormData({ ...depositFormData, deposit_date: e.target.value })}
                required
              />
            </div>

            <div className="grid grid-cols-3 gap-4">
              <Input
                label="충전 금액"
                type="number"
                value={depositFormData.amount}
                onChange={(e) => setDepositFormData({ ...depositFormData, amount: e.target.value })}
                required
              />
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">통화</label>
                <select
                  value={depositFormData.currency}
                  onChange={(e) => setDepositFormData({ ...depositFormData, currency: e.target.value })}
                  className="w-full border rounded-lg px-3 py-2"
                >
                  <option value="KRW">KRW</option>
                  <option value="USD">USD</option>
                  <option value="CNY">CNY</option>
                  <option value="JPY">JPY</option>
                  <option value="SGD">SGD</option>
                </select>
              </div>
              <Input
                label="환율 (해외용)"
                type="number"
                step="0.01"
                value={depositFormData.exchange_rate}
                onChange={(e) => setDepositFormData({ ...depositFormData, exchange_rate: e.target.value })}
                placeholder="USD의 경우 입력"
              />
            </div>

            <div className="grid grid-cols-2 gap-4">
              <Input
                label="참조번호"
                value={depositFormData.reference}
                onChange={(e) => setDepositFormData({ ...depositFormData, reference: e.target.value })}
                placeholder="입금 참조번호 등"
              />
              <Input
                label="설명"
                value={depositFormData.description}
                onChange={(e) => setDepositFormData({ ...depositFormData, description: e.target.value })}
              />
            </div>

            <div className="flex gap-2 justify-end">
              <button
                type="button"
                onClick={() => setShowDepositForm(false)}
                className="px-4 py-2 border rounded-lg hover:bg-gray-50"
              >
                취소
              </button>
              <button
                type="submit"
                className="px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700"
                disabled={createDeposit.isPending}
              >
                등록
              </button>
            </div>
          </form>
        </Card>
      )}

      {/* Contract Profiles Tab */}
      {activeTab === 'contracts' && (
        <>
          {/* Company Selection */}
          <Card title="회사 선택">
            <div className="flex gap-4 items-end">
              <div className="flex-1">
                <label className="block text-sm font-medium text-gray-700 mb-1">회사 선택</label>
                <select
                  value={selectedCompanySeq}
                  onChange={(e) => setSelectedCompanySeq(e.target.value)}
                  className="w-full border rounded-lg px-3 py-2"
                >
                  <option value="">회사를 선택하세요...</option>
                  {companies?.map((c) => (
                    <option key={c.seq} value={c.seq.toString()}>
                      {c.name} {c.is_overseas ? `(해외-${c.default_currency})` : ''}
                    </option>
                  ))}
                </select>
              </div>
            </div>
          </Card>

          {/* Contracts with Profile Status */}
          {selectedCompanySeq && (
            <Card title={`계약 목록 - ${contractsWithProfiles?.company_name || ''}`}>
              {contractsLoading ? (
                <div className="flex justify-center py-8">
                  <Spinner />
                </div>
              ) : contractsWithProfiles?.contracts && contractsWithProfiles.contracts.length > 0 ? (
                <>
                  <div className="mb-4 flex gap-4 text-sm">
                    <span className="text-gray-600">
                      총 {contractsWithProfiles.contracts.length}개 계약
                    </span>
                    <span className="text-green-600">
                      프로필 설정됨: {contractsWithProfiles.contracts.filter((c) => c.has_profile).length}
                    </span>
                    <span className="text-orange-600">
                      미설정: {contractsWithProfiles.contracts.filter((c) => !c.has_profile).length}
                    </span>
                  </div>
                  <Table>
                    <thead>
                      <tr>
                        <Th>계약명</Th>
                        <Th>법인</Th>
                        <Th>할인율</Th>
                        <Th>담당자</Th>
                        <Th>프로필 상태</Th>
                        <Th>작업</Th>
                      </tr>
                    </thead>
                    <tbody>
                      {contractsWithProfiles.contracts.map((contract) => (
                        <tr key={contract.contract_seq}>
                          <Td>{contract.contract_name}</Td>
                          <Td>
                            <span className={`px-2 py-1 rounded text-xs ${
                              contract.corporation === 'international'
                                ? 'bg-blue-100 text-blue-800'
                                : 'bg-red-100 text-red-800'
                            }`}>
                              {contract.corporation}
                            </span>
                          </Td>
                          <Td>{contract.discount_rate}%</Td>
                          <Td>{contract.sales_person || '-'}</Td>
                          <Td>
                            {contract.has_profile ? (
                              <span className="px-2 py-1 rounded text-xs bg-green-100 text-green-800">
                                설정됨 ({contract.profile?.payment_type})
                              </span>
                            ) : (
                              <span className="px-2 py-1 rounded text-xs bg-gray-100 text-gray-600">
                                미설정
                              </span>
                            )}
                          </Td>
                          <Td>
                            {contract.has_profile ? (
                              <div className="flex gap-1">
                                <button
                                  onClick={() => {
                                    // Load full profile and edit
                                    contractBillingProfileApi.getProfile(contract.profile!.id).then((res) => {
                                      handleEditContractProfile(res.data);
                                    });
                                  }}
                                  className="px-2 py-1 text-xs bg-blue-100 text-blue-700 rounded hover:bg-blue-200"
                                >
                                  수정
                                </button>
                                <button
                                  onClick={() => {
                                    if (confirm('삭제하시겠습니까?')) {
                                      deleteContractProfile.mutate(contract.profile!.id);
                                    }
                                  }}
                                  className="px-2 py-1 text-xs bg-red-100 text-red-700 rounded hover:bg-red-200"
                                >
                                  삭제
                                </button>
                              </div>
                            ) : (
                              <button
                                onClick={() => handleAddContractProfile(contract.contract_seq)}
                                className="px-2 py-1 text-xs bg-green-100 text-green-700 rounded hover:bg-green-200"
                              >
                                프로필 추가
                              </button>
                            )}
                          </Td>
                        </tr>
                      ))}
                    </tbody>
                  </Table>
                </>
              ) : (
                <p className="text-gray-500 text-center py-8">등록된 계약이 없습니다.</p>
              )}
            </Card>
          )}

          {/* All Contract Profiles Summary */}
          {!selectedCompanySeq && (
            <Card title="계약별 프로필 목록">
              {contractProfilesLoading ? (
                <div className="flex justify-center py-8">
                  <Spinner />
                </div>
              ) : contractProfiles && contractProfiles.length > 0 ? (
                <Table>
                  <thead>
                    <tr>
                      <Th>회사명</Th>
                      <Th>계약명</Th>
                      <Th>벤더</Th>
                      <Th>결제방식</Th>
                      <Th>통화</Th>
                      <Th>라운딩</Th>
                      <Th>작업</Th>
                    </tr>
                  </thead>
                  <tbody>
                    {contractProfiles.map((profile) => (
                      <tr key={profile.id}>
                        <Td>{profile.company_name}</Td>
                        <Td>{profile.contract_name}</Td>
                        <Td>{profile.vendor}</Td>
                        <Td>
                          {(() => {
                            const pt = PAYMENT_TYPES.find((p) => p.value === profile.payment_type);
                            const colorClass =
                              profile.payment_type === 'overseas_invoice'
                                ? 'bg-blue-100 text-blue-800'
                                : profile.payment_type === 'card'
                                ? 'bg-yellow-100 text-yellow-800'
                                : profile.payment_type === 'deposit'
                                ? 'bg-green-100 text-green-800'
                                : 'bg-gray-100 text-gray-800';
                            return (
                              <span className={`px-2 py-1 rounded text-xs ${colorClass}`}>
                                {pt?.label || profile.payment_type} ({profile.tax_code})
                              </span>
                            );
                          })()}
                        </Td>
                        <Td>{profile.currency}</Td>
                        <Td className="text-xs">
                          {profile.rounding_rule_override
                            ? ROUNDING_RULES.find((r) => r.value === profile.rounding_rule_override)?.label
                            : '-'}
                        </Td>
                        <Td>
                          <div className="flex gap-1">
                            <button
                              onClick={() => handleEditContractProfile(profile)}
                              className="px-2 py-1 text-xs bg-blue-100 text-blue-700 rounded hover:bg-blue-200"
                            >
                              수정
                            </button>
                            <button
                              onClick={() => {
                                if (confirm('삭제하시겠습니까?')) {
                                  deleteContractProfile.mutate(profile.id);
                                }
                              }}
                              className="px-2 py-1 text-xs bg-red-100 text-red-700 rounded hover:bg-red-200"
                            >
                              삭제
                            </button>
                          </div>
                        </Td>
                      </tr>
                    ))}
                  </tbody>
                </Table>
              ) : (
                <p className="text-gray-500 text-center py-8">
                  등록된 계약 프로필이 없습니다. 위에서 회사를 선택하여 계약별 프로필을 추가하세요.
                </p>
              )}
            </Card>
          )}
        </>
      )}

      {/* Company Profiles Tab (Legacy) */}
      {activeTab === 'companies' && (
        <Card title="회사별 청구 프로필 목록">
          <div className="mb-4 p-3 bg-yellow-50 border border-yellow-200 rounded-lg text-sm text-yellow-800">
            회사별 프로필은 레거시 기능입니다. 새 프로필은 '계약별 프로필' 탭에서 등록하세요.
          </div>
          {profilesLoading ? (
            <div className="flex justify-center py-8">
              <Spinner />
            </div>
          ) : profiles && profiles.length > 0 ? (
            <Table>
              <thead>
                <tr>
                  <Th>회사명</Th>
                  <Th>벤더</Th>
                  <Th>결제방식</Th>
                  <Th>통화</Th>
                  <Th>약정</Th>
                  <Th>계정코드</Th>
                  <Th>작업</Th>
                </tr>
              </thead>
              <tbody>
                {profiles.map((profile) => (
                  <tr key={profile.id}>
                    <Td>{profile.company_name}</Td>
                    <Td>{profile.vendor}</Td>
                    <Td>
                      {(() => {
                        const pt = PAYMENT_TYPES.find((p) => p.value === profile.payment_type);
                        const colorClass =
                          profile.payment_type === 'overseas_invoice'
                            ? 'bg-blue-100 text-blue-800'
                            : profile.payment_type === 'card'
                            ? 'bg-yellow-100 text-yellow-800'
                            : profile.payment_type === 'deposit'
                            ? 'bg-green-100 text-green-800'
                            : 'bg-gray-100 text-gray-800';
                        return (
                          <span className={`px-2 py-1 rounded text-xs ${colorClass}`}>
                            {pt?.label || profile.payment_type} ({pt?.taxCode || 'A1'})
                          </span>
                        );
                      })()}
                    </Td>
                    <Td>{profile.currency}</Td>
                    <Td>
                      {profile.has_sales_agreement && <span className="text-blue-600 mr-1">매출</span>}
                      {profile.has_purchase_agreement && <span className="text-orange-600">매입</span>}
                      {!profile.has_sales_agreement && !profile.has_purchase_agreement && '-'}
                    </Td>
                    <Td className="text-xs">
                      {profile.hkont_sales && <div>매출: {profile.hkont_sales}</div>}
                      {profile.hkont_purchase && <div>매입: {profile.hkont_purchase}</div>}
                      {!profile.hkont_sales && !profile.hkont_purchase && '-'}
                    </Td>
                    <Td>
                      <div className="flex gap-1">
                        <button
                          onClick={() => handleEditProfile(profile)}
                          className="px-2 py-1 text-xs bg-blue-100 text-blue-700 rounded hover:bg-blue-200"
                        >
                          수정
                        </button>
                        <button
                          onClick={() => {
                            if (confirm('삭제하시겠습니까?')) {
                              deleteProfile.mutate(profile.id);
                            }
                          }}
                          className="px-2 py-1 text-xs bg-red-100 text-red-700 rounded hover:bg-red-200"
                        >
                          삭제
                        </button>
                      </div>
                    </Td>
                  </tr>
                ))}
              </tbody>
            </Table>
          ) : (
            <p className="text-gray-500 text-center py-8">등록된 청구 프로필이 없습니다.</p>
          )}
        </Card>
      )}

      {/* Deposits Tab */}
      {activeTab === 'deposits' && (
        <>
          <Card title="예치금 내역">
            {depositsLoading ? (
              <div className="flex justify-center py-8">
                <Spinner />
              </div>
            ) : deposits && deposits.length > 0 ? (
              <Table>
                <thead>
                  <tr>
                    <Th>회사명</Th>
                    <Th>계약명</Th>
                    <Th>충전일</Th>
                    <Th>충전액</Th>
                    <Th>통화</Th>
                    <Th>환율</Th>
                    <Th>잔액</Th>
                    <Th>상태</Th>
                    <Th>참조</Th>
                    <Th></Th>
                  </tr>
                </thead>
                <tbody>
                  {deposits.map((deposit) => (
                    <tr key={deposit.id} className={deposit.is_exhausted ? 'bg-gray-50' : ''}>
                      <Td>{deposit.company_name || '-'}</Td>
                      <Td className="text-sm text-gray-500">{deposit.contract_name || '-'}</Td>
                      <Td>{deposit.deposit_date}</Td>
                      <Td className="text-right font-mono">
                        {deposit.amount.toLocaleString()}
                      </Td>
                      <Td>{deposit.currency}</Td>
                      <Td>{deposit.exchange_rate?.toLocaleString() || '-'}</Td>
                      <Td className="text-right font-mono">
                        {deposit.remaining_amount.toLocaleString()}
                      </Td>
                      <Td>
                        <span
                          className={`px-2 py-1 rounded text-xs ${
                            deposit.is_exhausted
                              ? 'bg-gray-100 text-gray-600'
                              : 'bg-green-100 text-green-800'
                          }`}
                        >
                          {deposit.is_exhausted ? '소진' : '사용가능'}
                        </span>
                      </Td>
                      <Td className="text-sm text-gray-500">{deposit.reference || '-'}</Td>
                      <Td>
                        <button
                          onClick={() => handleEditDeposit(deposit)}
                          className="text-blue-600 hover:text-blue-800 text-sm"
                        >
                          수정
                        </button>
                      </Td>
                    </tr>
                  ))}
                </tbody>
              </Table>
            ) : (
              <p className="text-gray-500 text-center py-8">등록된 예치금이 없습니다.</p>
            )}
          </Card>

          {/* 예치금 수정 모달 */}
          {editingDeposit && (
            <Card title="예치금 수정">
              <div className="mb-3 text-sm text-gray-600">
                <span className="font-medium">{editingDeposit.company_name}</span>
                {editingDeposit.contract_name && (
                  <span className="ml-2 text-gray-400">/ {editingDeposit.contract_name}</span>
                )}
              </div>
              <form onSubmit={handleEditDepositSubmit} className="space-y-4">
                <div className="grid grid-cols-2 gap-4">
                  <Input
                    label="충전일"
                    type="date"
                    value={editDepositFormData.deposit_date}
                    onChange={(e) => setEditDepositFormData({ ...editDepositFormData, deposit_date: e.target.value })}
                    required
                  />
                  <Input
                    label="충전 금액"
                    type="number"
                    value={editDepositFormData.amount}
                    onChange={(e) => setEditDepositFormData({ ...editDepositFormData, amount: e.target.value })}
                    required
                  />
                </div>
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">통화</label>
                    <select
                      value={editDepositFormData.currency}
                      onChange={(e) => setEditDepositFormData({ ...editDepositFormData, currency: e.target.value })}
                      className="w-full border rounded-lg px-3 py-2"
                    >
                      <option value="KRW">KRW</option>
                      <option value="USD">USD</option>
                      <option value="CNY">CNY</option>
                      <option value="JPY">JPY</option>
                      <option value="SGD">SGD</option>
                    </select>
                  </div>
                  <Input
                    label="환율 (해외용)"
                    type="number"
                    step="0.01"
                    value={editDepositFormData.exchange_rate}
                    onChange={(e) => setEditDepositFormData({ ...editDepositFormData, exchange_rate: e.target.value })}
                  />
                </div>
                <div className="grid grid-cols-2 gap-4">
                  <Input
                    label="참조번호"
                    value={editDepositFormData.reference}
                    onChange={(e) => setEditDepositFormData({ ...editDepositFormData, reference: e.target.value })}
                  />
                  <Input
                    label="설명"
                    value={editDepositFormData.description}
                    onChange={(e) => setEditDepositFormData({ ...editDepositFormData, description: e.target.value })}
                  />
                </div>
                <div className="flex gap-2 justify-end">
                  <button
                    type="button"
                    onClick={() => setEditingDeposit(null)}
                    className="px-4 py-2 border rounded-lg hover:bg-gray-50"
                  >
                    취소
                  </button>
                  <button
                    type="submit"
                    className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
                    disabled={updateDeposit.isPending}
                  >
                    저장
                  </button>
                </div>
              </form>
            </Card>
          )}
        </>
      )}
    </div>
  );
}
