import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { billingProfileApi, hbApi, masterApi } from '../api/client';
import { Card, Input, Alert, Spinner, Table, Th, Td } from '../components/ui';

type Tab = 'profiles' | 'deposits';

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

interface Deposit {
  id: number;
  profile_id: number;
  company_name: string;
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

export default function BillingProfile() {
  const queryClient = useQueryClient();
  const [activeTab, setActiveTab] = useState<Tab>('profiles');
  const [showForm, setShowForm] = useState(false);
  const [showDepositForm, setShowDepositForm] = useState(false);
  const [selectedProfile, setSelectedProfile] = useState<BillingProfile | null>(null);
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  // Form states
  const [formData, setFormData] = useState({
    company_seq: '',
    vendor: 'alibaba',
    payment_type: 'postpaid',
    has_sales_agreement: false,
    has_purchase_agreement: false,
    currency: 'KRW',
    hkont_sales: '',
    hkont_purchase: '',
    ar_account: '',
    ap_account: '',
    note: '',
  });

  const [depositFormData, setDepositFormData] = useState({
    profile_id: '',
    deposit_date: new Date().toISOString().slice(0, 10),
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
  });

  const { data: deposits, isLoading: depositsLoading } = useQuery({
    queryKey: ['deposits'],
    queryFn: () => billingProfileApi.getDeposits({ include_exhausted: true }).then((res) => res.data as Deposit[]),
    enabled: activeTab === 'deposits',
  });

  const { data: companies } = useQuery({
    queryKey: ['hbCompanies'],
    queryFn: () => hbApi.getCompanies({}).then((res) => res.data as Company[]),
  });

  const { data: accountCodes } = useQuery({
    queryKey: ['accountCodes'],
    queryFn: () => masterApi.getAccountCodes().then((res) => res.data as AccountCode[]),
  });

  // Mutations
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

  const createDeposit = useMutation({
    mutationFn: (data: typeof depositFormData) =>
      billingProfileApi.createDeposit({
        profile_id: parseInt(data.profile_id),
        deposit_date: data.deposit_date,
        amount: parseFloat(data.amount),
        currency: data.currency,
        exchange_rate: data.exchange_rate ? parseFloat(data.exchange_rate) : undefined,
        reference: data.reference || undefined,
        description: data.description || undefined,
      }),
    onSuccess: () => {
      setMessage({ type: 'success', text: '예치금이 등록되었습니다.' });
      setShowDepositForm(false);
      resetDepositForm();
      queryClient.invalidateQueries({ queryKey: ['deposits'] });
    },
  });

  const resetForm = () => {
    setFormData({
      company_seq: '',
      vendor: 'alibaba',
      payment_type: 'postpaid',
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

  const resetDepositForm = () => {
    setDepositFormData({
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

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (selectedProfile) {
      updateProfile.mutate({ id: selectedProfile.id, data: formData });
    } else {
      createProfile.mutate(formData);
    }
  };

  const handleDepositSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    createDeposit.mutate(depositFormData);
  };

  const tabs = [
    { id: 'profiles' as Tab, label: '청구 프로필' },
    { id: 'deposits' as Tab, label: '예치금 관리' },
  ];

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-bold text-gray-800">청구 설정 & 예치금</h2>
        <div className="flex gap-2">
          {activeTab === 'profiles' && (
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

      {/* Profile Form Modal */}
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
                    // 해외법인이면 USD를 기본값으로
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
                  <option value="postpaid">후불</option>
                  <option value="deposit">예치금</option>
                  <option value="both">후불+예치금</option>
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
                  <option value="">기본값 (41021010)</option>
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
                  <option value="">기본값 (42021010)</option>
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
                  <option value="">기본값 (11060110)</option>
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
                  <option value="">기본값 (21120110)</option>
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
                <label className="block text-sm font-medium text-gray-700 mb-1">청구 프로필</label>
                <select
                  value={depositFormData.profile_id}
                  onChange={(e) => setDepositFormData({ ...depositFormData, profile_id: e.target.value })}
                  className="w-full border rounded-lg px-3 py-2"
                  required
                >
                  <option value="">선택...</option>
                  {profiles?.map((p) => (
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

      {/* Profiles List */}
      {activeTab === 'profiles' && (
        <Card title="청구 프로필 목록">
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
                      <span
                        className={`px-2 py-1 rounded text-xs ${
                          profile.payment_type === 'deposit'
                            ? 'bg-green-100 text-green-800'
                            : profile.payment_type === 'both'
                            ? 'bg-purple-100 text-purple-800'
                            : 'bg-gray-100 text-gray-800'
                        }`}
                      >
                        {profile.payment_type === 'postpaid'
                          ? '후불'
                          : profile.payment_type === 'deposit'
                          ? '예치금'
                          : '후불+예치금'}
                      </span>
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
                      {!profile.hkont_sales && !profile.hkont_purchase && '기본값'}
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

      {/* Deposits List */}
      {activeTab === 'deposits' && (
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
                  <Th>충전일</Th>
                  <Th>충전액</Th>
                  <Th>통화</Th>
                  <Th>환율</Th>
                  <Th>잔액</Th>
                  <Th>상태</Th>
                  <Th>참조</Th>
                </tr>
              </thead>
              <tbody>
                {deposits.map((deposit) => (
                  <tr key={deposit.id} className={deposit.is_exhausted ? 'bg-gray-50' : ''}>
                    <Td>{deposit.company_name}</Td>
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
                  </tr>
                ))}
              </tbody>
            </Table>
          ) : (
            <p className="text-gray-500 text-center py-8">등록된 예치금이 없습니다.</p>
          )}
        </Card>
      )}
    </div>
  );
}
