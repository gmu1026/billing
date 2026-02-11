import { useState, useEffect } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useSearchParams } from 'react-router-dom';
import { slipApi, masterApi } from '../api/client';
import { Card, Button, Input, Select, Alert, Spinner, Badge, Table, Th, Td } from '../components/ui';
import type { SlipRecord, SlipBatch, GenerateResponse, BPCode } from '../types';

interface SlipConfig {
  vendor: string;
  bukrs: string;
  prctr: string;
  hkont_sales: string;
  hkont_purchase: string;
  ar_account_default: string;
  ap_account_default: string;
  zzref2: string;
  sgtxt_template: string;
  rounding_rule: string;
  // 환율 규칙
  exchange_rate_rule_sales: string;
  exchange_rate_type_sales: string;
  exchange_rate_rule_purchase: string;
  exchange_rate_type_purchase: string;
  exchange_rate_rule_overseas: string;
  exchange_rate_type_overseas: string;
}

const EXCHANGE_RATE_RULES = [
  { value: 'document_date', label: '증빙일' },
  { value: 'first_of_document_month', label: '증빙월 1일' },
  { value: 'first_of_billing_month', label: '정산월 1일' },
  { value: 'last_of_prev_month', label: '전월 말일' },
];

const EXCHANGE_RATE_TYPES = [
  { value: 'basic_rate', label: '기준환율' },
  { value: 'send_rate', label: '송금환율' },
  { value: 'buy_rate', label: '매입환율' },
  { value: 'sell_rate', label: '매도환율' },
];

const ROUNDING_RULES = [
  { value: 'floor', label: '버림 (FLOOR)' },
  { value: 'round_half_up', label: '반올림 (ROUND_HALF_UP)' },
  { value: 'ceiling', label: '올림 (CEILING)' },
];

export default function Slip() {
  const queryClient = useQueryClient();
  const [searchParams] = useSearchParams();

  // Generate form
  const [billingCycle, setBillingCycle] = useState(() => {
    const d = new Date();
    d.setMonth(d.getMonth() - 1);
    return d.toISOString().slice(0, 7).replace('-', '');
  });
  const [slipType, setSlipType] = useState<'sales' | 'purchase'>('sales');
  const [documentDate, setDocumentDate] = useState(() => new Date().toISOString().slice(0, 10));
  const [exchangeRate, setExchangeRate] = useState('');
  const [invoiceNumber, setInvoiceNumber] = useState('');

  // View state
  const [selectedBatch, setSelectedBatch] = useState<string | null>(searchParams.get('batch_id'));
  const [generateResult, setGenerateResult] = useState<GenerateResponse | null>(null);

  // Slip edit
  const [editingSlip, setEditingSlip] = useState<number | null>(null);
  const [editPartner, setEditPartner] = useState('');
  const [bpSearch, setBpSearch] = useState('');

  // Config
  const [showConfig, setShowConfig] = useState(false);

  // Overseas exchange rate (해외 인보이스 환율)
  const [overseasExchangeRate, setOverseasExchangeRate] = useState('');

  // Exchange rate by date and slip type
  const [rateLoading, setRateLoading] = useState(false);
  const [rateDate, setRateDate] = useState(''); // 환율 적용일 (자동 계산됨)
  const [rateDateRule, setRateDateRule] = useState(''); // 적용된 규칙
  const [rateInfo, setRateInfo] = useState<{
    rate: number;
    rate_type: string;
    rate_date: string;
    source?: string;
  } | null>(null);

  // Fetch exchange rate when documentDate, slipType, or billingCycle changes
  useEffect(() => {
    const fetchRate = async () => {
      if (!documentDate) return;

      setRateLoading(true);
      setRateInfo(null);
      setRateDate('');
      setRateDateRule('');

      try {
        // 벤더 설정에 따른 환율 적용일 및 환율 조회
        const res = await slipApi.calculateRateDate({
          vendor: 'alibaba',
          slip_type: slipType,
          document_date: documentDate,
          billing_cycle: billingCycle,
        });
        const data = res.data;

        setRateDate(data.rate_date);
        setRateDateRule(data.rule);

        if (data.found && data.rate) {
          setExchangeRate(String(data.rate));
          setRateInfo({
            rate: data.rate,
            rate_type: data.rate_type,
            rate_date: data.rate_date,
            source: data.source,
          });
        } else {
          // 환율이 없으면 HB에서 동기화 시도
          try {
            const syncRes = await slipApi.syncRatesFromHB({ limit: 50 });
            if (syncRes.data.success && (syncRes.data.imported > 0 || syncRes.data.updated > 0)) {
              // 재조회
              const retryRes = await slipApi.calculateRateDate({
                vendor: 'alibaba',
                slip_type: slipType,
                document_date: documentDate,
                billing_cycle: billingCycle,
              });
              if (retryRes.data.found && retryRes.data.rate) {
                setExchangeRate(String(retryRes.data.rate));
                setRateInfo({
                  rate: retryRes.data.rate,
                  rate_type: retryRes.data.rate_type,
                  rate_date: retryRes.data.rate_date,
                  source: 'hb (synced)',
                });
              } else {
                setExchangeRate('');
                setRateInfo(null);
              }
            } else {
              setExchangeRate('');
              setRateInfo(null);
            }
          } catch {
            setExchangeRate('');
            setRateInfo(null);
          }
        }
      } catch (err) {
        console.error('Failed to fetch exchange rate:', err);
        setExchangeRate('');
        setRateInfo(null);
      } finally {
        setRateLoading(false);
      }
    };

    fetchRate();
  }, [documentDate, slipType, billingCycle]);

  // Batches
  const { data: batches } = useQuery({
    queryKey: ['slipBatches'],
    queryFn: () => slipApi.getBatches().then((res) => res.data as SlipBatch[]),
  });

  // Slips for selected batch
  const { data: slipsData, isLoading: slipsLoading } = useQuery({
    queryKey: ['slips', selectedBatch],
    queryFn: () =>
      slipApi
        .getSlips({ batch_id: selectedBatch!, limit: 500 })
        .then((res) => res.data as { total: number; data: SlipRecord[] }),
    enabled: !!selectedBatch,
  });

  // BP codes search
  const { data: bpCodes } = useQuery({
    queryKey: ['bpCodes', bpSearch],
    queryFn: () => masterApi.getBPCodes({ search: bpSearch, limit: 10 }).then((res) => res.data as BPCode[]),
    enabled: bpSearch.length >= 2,
  });

  // Slip config
  const { data: slipConfig, isLoading: configLoading } = useQuery({
    queryKey: ['slipConfig', 'alibaba'],
    queryFn: () => slipApi.getConfig('alibaba').then((res) => res.data as SlipConfig),
    enabled: showConfig,
  });

  // Update config mutation
  const updateConfigMutation = useMutation({
    mutationFn: (data: Partial<SlipConfig>) => slipApi.updateConfig('alibaba', data as Record<string, string>),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['slipConfig'] });
      alert('설정이 저장되었습니다.');
    },
  });

  // Generate slips
  const generateMutation = useMutation({
    mutationFn: () =>
      slipApi.generate({
        billing_cycle: billingCycle,
        slip_type: slipType,
        document_date: documentDate,
        exchange_rate: exchangeRate ? Number(exchangeRate) : undefined,
        invoice_number: invoiceNumber || undefined,
        auto_exchange_rate: true,
        overseas_exchange_rate_input: overseasExchangeRate ? Number(overseasExchangeRate) : undefined,
      }),
    onSuccess: (res) => {
      setGenerateResult(res.data);
      setSelectedBatch(res.data.batch_id);
      queryClient.invalidateQueries({ queryKey: ['slipBatches'] });
      queryClient.invalidateQueries({ queryKey: ['slips'] });
    },
    onError: (err: any) => {
      alert(err.response?.data?.detail || '전표 생성 실패');
    },
  });

  // Update slip
  const updateSlipMutation = useMutation({
    mutationFn: ({ id, partner }: { id: number; partner: string }) =>
      slipApi.updateSlip(id, { partner }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['slips', selectedBatch] });
      setEditingSlip(null);
      setEditPartner('');
    },
  });

  // Confirm batch
  const confirmMutation = useMutation({
    mutationFn: (batchId: string) => slipApi.confirm(batchId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['slips', selectedBatch] });
      alert('전표가 확정되었습니다.');
    },
    onError: (err: any) => {
      alert(err.response?.data?.detail || '확정 실패');
    },
  });

  // Delete batch
  const deleteMutation = useMutation({
    mutationFn: (batchId: string) => slipApi.deleteBatch(batchId),
    onSuccess: () => {
      setSelectedBatch(null);
      queryClient.invalidateQueries({ queryKey: ['slipBatches'] });
      alert('삭제되었습니다.');
    },
    onError: (err: any) => {
      alert(err.response?.data?.detail || '삭제 실패');
    },
  });

  const handleGenerate = () => {
    // 환율 자동 조회가 활성화되어 있으므로 환율이 없어도 진행 가능
    // 백엔드에서 자동으로 환율을 조회함
    generateMutation.mutate();
  };

  const monthOptions = Array.from({ length: 12 }, (_, i) => {
    const d = new Date();
    d.setMonth(d.getMonth() - i);
    const value = d.toISOString().slice(0, 7).replace('-', '');
    const label = `${d.getFullYear()}년 ${d.getMonth() + 1}월`;
    return { value, label };
  });

  const slips = slipsData?.data || [];
  const slipsWithoutBp = slips.filter((s) => !s.partner);
  const currentBatch = batches?.find((b) => b.batch_id === selectedBatch);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-bold text-gray-800">전표 생성</h2>
        <button
          onClick={() => setShowConfig(!showConfig)}
          className="px-4 py-2 text-sm border rounded-lg hover:bg-gray-50"
        >
          {showConfig ? '설정 닫기' : '전표 설정'}
        </button>
      </div>

      {/* Slip Config */}
      {showConfig && (
        <Card title="전표 설정 (Alibaba)">
          {configLoading ? (
            <div className="flex justify-center py-4"><Spinner /></div>
          ) : slipConfig ? (
            <div className="space-y-4">
              <div className="grid grid-cols-3 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">라운딩 규칙</label>
                  <select
                    value={slipConfig.rounding_rule}
                    onChange={(e) => updateConfigMutation.mutate({ rounding_rule: e.target.value })}
                    className="w-full border rounded-lg px-3 py-2"
                    disabled={updateConfigMutation.isPending}
                  >
                    {ROUNDING_RULES.map((rule) => (
                      <option key={rule.value} value={rule.value}>
                        {rule.label}
                      </option>
                    ))}
                  </select>
                  <p className="text-xs text-gray-500 mt-1">
                    USD → KRW 환산 시 적용되는 라운딩 규칙
                  </p>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">회사코드 (BUKRS)</label>
                  <input
                    type="text"
                    value={slipConfig.bukrs}
                    onChange={(e) => updateConfigMutation.mutate({ bukrs: e.target.value })}
                    className="w-full border rounded-lg px-3 py-2 bg-gray-50"
                    readOnly
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">부서코드 (PRCTR)</label>
                  <input
                    type="text"
                    value={slipConfig.prctr}
                    onChange={(e) => updateConfigMutation.mutate({ prctr: e.target.value })}
                    className="w-full border rounded-lg px-3 py-2 bg-gray-50"
                    readOnly
                  />
                </div>
              </div>
              <div className="grid grid-cols-4 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">매출 계정</label>
                  <input
                    type="text"
                    value={slipConfig.hkont_sales}
                    className="w-full border rounded-lg px-3 py-2 bg-gray-50"
                    readOnly
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">매입 계정</label>
                  <input
                    type="text"
                    value={slipConfig.hkont_purchase}
                    className="w-full border rounded-lg px-3 py-2 bg-gray-50"
                    readOnly
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">기본 채권과목</label>
                  <input
                    type="text"
                    value={slipConfig.ar_account_default}
                    className="w-full border rounded-lg px-3 py-2 bg-gray-50"
                    readOnly
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">기본 채무과목</label>
                  <input
                    type="text"
                    value={slipConfig.ap_account_default}
                    className="w-full border rounded-lg px-3 py-2 bg-gray-50"
                    readOnly
                  />
                </div>
              </div>

              {/* 환율 규칙 설정 */}
              <div className="border-t pt-4 mt-4">
                <h4 className="text-sm font-medium text-gray-700 mb-3">환율 규칙</h4>
                <div className="grid grid-cols-3 gap-4">
                  {/* 매출 환율 규칙 */}
                  <div className="p-3 bg-blue-50 rounded-lg">
                    <h5 className="text-xs font-medium text-blue-700 mb-2">매출 전표</h5>
                    <div className="space-y-2">
                      <div>
                        <label className="block text-xs text-gray-600 mb-1">적용일 규칙</label>
                        <select
                          value={slipConfig.exchange_rate_rule_sales}
                          onChange={(e) => updateConfigMutation.mutate({ exchange_rate_rule_sales: e.target.value })}
                          className="w-full border rounded px-2 py-1 text-sm"
                          disabled={updateConfigMutation.isPending}
                        >
                          {EXCHANGE_RATE_RULES.map((rule) => (
                            <option key={rule.value} value={rule.value}>{rule.label}</option>
                          ))}
                        </select>
                      </div>
                      <div>
                        <label className="block text-xs text-gray-600 mb-1">환율 종류</label>
                        <select
                          value={slipConfig.exchange_rate_type_sales}
                          onChange={(e) => updateConfigMutation.mutate({ exchange_rate_type_sales: e.target.value })}
                          className="w-full border rounded px-2 py-1 text-sm"
                          disabled={updateConfigMutation.isPending}
                        >
                          {EXCHANGE_RATE_TYPES.map((type) => (
                            <option key={type.value} value={type.value}>{type.label}</option>
                          ))}
                        </select>
                      </div>
                    </div>
                  </div>

                  {/* 매입 환율 규칙 */}
                  <div className="p-3 bg-amber-50 rounded-lg">
                    <h5 className="text-xs font-medium text-amber-700 mb-2">매입 전표</h5>
                    <div className="space-y-2">
                      <div>
                        <label className="block text-xs text-gray-600 mb-1">적용일 규칙</label>
                        <select
                          value={slipConfig.exchange_rate_rule_purchase}
                          onChange={(e) => updateConfigMutation.mutate({ exchange_rate_rule_purchase: e.target.value })}
                          className="w-full border rounded px-2 py-1 text-sm"
                          disabled={updateConfigMutation.isPending}
                        >
                          {EXCHANGE_RATE_RULES.map((rule) => (
                            <option key={rule.value} value={rule.value}>{rule.label}</option>
                          ))}
                        </select>
                      </div>
                      <div>
                        <label className="block text-xs text-gray-600 mb-1">환율 종류</label>
                        <select
                          value={slipConfig.exchange_rate_type_purchase}
                          onChange={(e) => updateConfigMutation.mutate({ exchange_rate_type_purchase: e.target.value })}
                          className="w-full border rounded px-2 py-1 text-sm"
                          disabled={updateConfigMutation.isPending}
                        >
                          {EXCHANGE_RATE_TYPES.map((type) => (
                            <option key={type.value} value={type.value}>{type.label}</option>
                          ))}
                        </select>
                      </div>
                    </div>
                  </div>

                  {/* 해외법인 환율 규칙 */}
                  <div className="p-3 bg-purple-50 rounded-lg">
                    <h5 className="text-xs font-medium text-purple-700 mb-2">해외법인 (원화환산)</h5>
                    <div className="space-y-2">
                      <div>
                        <label className="block text-xs text-gray-600 mb-1">적용일 규칙</label>
                        <select
                          value={slipConfig.exchange_rate_rule_overseas}
                          onChange={(e) => updateConfigMutation.mutate({ exchange_rate_rule_overseas: e.target.value })}
                          className="w-full border rounded px-2 py-1 text-sm"
                          disabled={updateConfigMutation.isPending}
                        >
                          {EXCHANGE_RATE_RULES.map((rule) => (
                            <option key={rule.value} value={rule.value}>{rule.label}</option>
                          ))}
                        </select>
                      </div>
                      <div>
                        <label className="block text-xs text-gray-600 mb-1">환율 종류</label>
                        <select
                          value={slipConfig.exchange_rate_type_overseas}
                          onChange={(e) => updateConfigMutation.mutate({ exchange_rate_type_overseas: e.target.value })}
                          className="w-full border rounded px-2 py-1 text-sm"
                          disabled={updateConfigMutation.isPending}
                        >
                          {EXCHANGE_RATE_TYPES.map((type) => (
                            <option key={type.value} value={type.value}>{type.label}</option>
                          ))}
                        </select>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
              <div className="text-xs text-gray-500">
                회사코드, 계정코드 등 기타 설정은 시스템 관리자에게 문의하세요.
              </div>
            </div>
          ) : null}
        </Card>
      )}

      {/* Generate Form */}
      <Card title="전표 생성">
        <div className="grid grid-cols-2 md:grid-cols-7 gap-4">
          <Select
            label="정산월"
            value={billingCycle}
            onChange={(e) => setBillingCycle(e.target.value)}
            options={monthOptions}
          />
          <Select
            label="유형"
            value={slipType}
            onChange={(e) => setSlipType(e.target.value as any)}
            options={[
              { value: 'sales', label: '매출 (Enduser)' },
              { value: 'purchase', label: '매입 (Reseller)' },
            ]}
          />
          <Input
            label="증빙일"
            type="date"
            value={documentDate}
            onChange={(e) => setDocumentDate(e.target.value)}
          />
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              환율 적용일
              {rateLoading && <span className="ml-2 text-blue-500 text-xs">조회중...</span>}
            </label>
            <Input
              type="date"
              value={rateDate}
              onChange={(e) => {
                setRateDate(e.target.value);
                // 수동 변경 시 해당 날짜로 환율 재조회
                slipApi.getRateByDate({ rate_date: e.target.value }).then(res => {
                  if (res.data.found) {
                    const rate = slipType === 'sales'
                      ? (res.data.send_rate || res.data.basic_rate)
                      : res.data.basic_rate;
                    if (rate) {
                      setExchangeRate(String(rate));
                      setRateInfo({
                        rate,
                        rate_type: slipType === 'sales' ? 'send_rate' : 'basic_rate',
                        rate_date: res.data.rate_date,
                        source: res.data.source,
                      });
                    }
                  }
                });
              }}
              disabled={rateLoading}
            />
            {rateDateRule && (
              <p className="text-xs text-gray-500 mt-1">
                {EXCHANGE_RATE_RULES.find(r => r.value === rateDateRule)?.label || rateDateRule}
              </p>
            )}
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              환율 (USD/KRW)
            </label>
            <Input
              type="number"
              value={exchangeRate}
              onChange={(e) => setExchangeRate(e.target.value)}
              placeholder="자동 조회"
              disabled={rateLoading}
            />
            {rateInfo ? (
              <p className="text-xs text-green-600 mt-1">
                {EXCHANGE_RATE_TYPES.find(t => t.value === rateInfo.rate_type)?.label || rateInfo.rate_type}
                {rateInfo.source?.includes('hb') && ' - HB'}
              </p>
            ) : !rateLoading && rateDate && !exchangeRate ? (
              <p className="text-xs text-amber-600 mt-1">
                {rateDate} 환율 없음
              </p>
            ) : null}
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              해외 인보이스 환율
            </label>
            <Input
              type="number"
              value={overseasExchangeRate}
              onChange={(e) => setOverseasExchangeRate(e.target.value)}
              placeholder="미입력 시 자동"
            />
            <p className="text-xs text-gray-500 mt-1">
              계약별 환율 미설정 시 적용
            </p>
          </div>
          <Input
            label="인보이스 번호"
            value={invoiceNumber}
            onChange={(e) => setInvoiceNumber(e.target.value)}
            placeholder="SIGM..."
          />
        </div>
        <div className="mt-4">
          <Button onClick={handleGenerate} disabled={generateMutation.isPending}>
            {generateMutation.isPending ? '생성 중...' : '전표 생성'}
          </Button>
        </div>

        {generateResult && (
          <div className="mt-4">
            <Alert type={generateResult.slips_no_bp > 0 ? 'warning' : 'success'}>
              <div className="font-medium">
                전표 생성 완료: {generateResult.total_slips}건
              </div>
              <div className="text-sm mt-1">
                BP 매핑됨: {generateResult.slips_with_bp}건 /
                미매핑: {generateResult.slips_no_bp}건
              </div>
              {generateResult.exchange_rate && (
                <div className="text-sm mt-1 text-gray-600">
                  적용 환율: {generateResult.exchange_rate.domestic?.toLocaleString()} ({generateResult.exchange_rate.rate_type})
                  {generateResult.exchange_rate.overseas && (
                    <span className="ml-2">/ 해외: {generateResult.exchange_rate.overseas?.toLocaleString()}</span>
                  )}
                  {generateResult.exchange_rate.synced_from_hb && (
                    <span className="ml-2 text-blue-500">(HB 동기화됨)</span>
                  )}
                </div>
              )}
              {generateResult.slips_no_bp > 0 && (
                <div className="text-sm mt-2">
                  미매핑 건은 아래 목록에서 수동으로 BP를 지정해주세요.
                </div>
              )}
            </Alert>
          </div>
        )}
      </Card>

      {/* Batch Selection */}
      <Card title="전표 배치 목록">
        <div className="flex flex-wrap gap-2">
          {batches?.map((batch) => (
            <button
              key={batch.batch_id}
              onClick={() => setSelectedBatch(batch.batch_id)}
              className={`px-3 py-2 rounded-lg border text-sm transition-colors ${
                selectedBatch === batch.batch_id
                  ? 'bg-blue-50 border-blue-300 text-blue-700'
                  : 'bg-white border-gray-200 hover:bg-gray-50'
              }`}
            >
              <div className="font-mono text-xs">{batch.batch_id}</div>
              <div className="flex items-center gap-2 mt-1">
                <Badge variant={batch.slip_type === 'sales' ? 'success' : 'warning'}>
                  {batch.slip_type === 'sales' ? '매출' : '매입'}
                </Badge>
                <span>{batch.billing_cycle}</span>
                <span className="text-gray-500">{batch.count}건</span>
              </div>
            </button>
          ))}
          {(!batches || batches.length === 0) && (
            <div className="text-gray-500 text-sm">생성된 배치가 없습니다.</div>
          )}
        </div>
      </Card>

      {/* Slip List */}
      {selectedBatch && (
        <Card
          title={`전표 목록 - ${selectedBatch}`}
          action={
            <div className="flex gap-2">
              <a
                href={slipApi.export(selectedBatch)}
                download
                className="inline-flex items-center px-3 py-1.5 bg-green-600 text-white rounded-lg text-sm hover:bg-green-700"
              >
                CSV 다운로드
              </a>
              <Button
                size="sm"
                onClick={() => confirmMutation.mutate(selectedBatch)}
                disabled={confirmMutation.isPending || slipsWithoutBp.length > 0}
              >
                확정
              </Button>
              <Button
                size="sm"
                variant="danger"
                onClick={() => {
                  if (confirm('이 배치를 삭제하시겠습니까?')) {
                    deleteMutation.mutate(selectedBatch);
                  }
                }}
                disabled={deleteMutation.isPending}
              >
                삭제
              </Button>
            </div>
          }
        >
          {slipsWithoutBp.length > 0 && (
            <Alert type="warning" title={`BP 미매핑: ${slipsWithoutBp.length}건`}>
              아래 표에서 BP가 없는 전표를 수정해주세요. BP 미매핑 상태에서는 확정할 수 없습니다.
            </Alert>
          )}

          {slipsLoading ? (
            <div className="flex justify-center py-8"><Spinner /></div>
          ) : slips.length > 0 ? (
            <div className="mt-4 overflow-x-auto">
              <Table>
                <thead>
                  <tr>
                    <Th>NO</Th>
                    <Th>UID</Th>
                    <Th>거래처 (BP)</Th>
                    <Th>거래처명</Th>
                    <Th className="text-right">금액 (KRW)</Th>
                    <Th className="text-right">금액 (USD)</Th>
                    <Th>계약번호</Th>
                    <Th>상태</Th>
                    <Th></Th>
                  </tr>
                </thead>
                <tbody>
                  {slips.map((slip) => (
                    <tr
                      key={slip.id}
                      className={`hover:bg-gray-50 ${!slip.partner ? 'bg-yellow-50' : ''}`}
                    >
                      <Td className="text-gray-500">{slip.seqno}</Td>
                      <Td className="font-mono text-xs">{slip.uid || '-'}</Td>
                      <Td>
                        {editingSlip === slip.id ? (
                          <div className="relative">
                            <Input
                              value={editPartner}
                              onChange={(e) => {
                                setEditPartner(e.target.value);
                                setBpSearch(e.target.value);
                              }}
                              placeholder="BP번호"
                              className="w-28"
                            />
                            {bpCodes && bpCodes.length > 0 && (
                              <div className="absolute top-full left-0 mt-1 bg-white border rounded-lg shadow-lg z-10 max-h-40 overflow-auto w-64">
                                {bpCodes.map((bp) => (
                                  <button
                                    key={bp.bp_number}
                                    onClick={() => {
                                      setEditPartner(bp.bp_number);
                                      setBpSearch('');
                                    }}
                                    className="block w-full text-left px-3 py-2 text-sm hover:bg-gray-100"
                                  >
                                    <span className="font-mono">{bp.bp_number}</span>
                                    <span className="text-gray-500 ml-2">{bp.name}</span>
                                  </button>
                                ))}
                              </div>
                            )}
                          </div>
                        ) : slip.partner ? (
                          <span className="font-mono text-sm">{slip.partner}</span>
                        ) : (
                          <Badge variant="warning">미매핑</Badge>
                        )}
                      </Td>
                      <Td className="max-w-xs truncate">{slip.partner_name || '-'}</Td>
                      <Td className="text-right font-medium">
                        ₩{slip.wrbtr.toLocaleString()}
                      </Td>
                      <Td className="text-right text-gray-500">
                        ${slip.wrbtr_usd.toLocaleString(undefined, { minimumFractionDigits: 2 })}
                      </Td>
                      <Td className="font-mono text-xs">{slip.zzsconid || '-'}</Td>
                      <Td>
                        <Badge variant={slip.is_confirmed ? 'success' : 'default'}>
                          {slip.is_confirmed ? '확정' : '대기'}
                        </Badge>
                      </Td>
                      <Td>
                        {!slip.is_confirmed && (
                          editingSlip === slip.id ? (
                            <div className="flex gap-1">
                              <Button
                                size="sm"
                                onClick={() =>
                                  updateSlipMutation.mutate({ id: slip.id, partner: editPartner })
                                }
                                disabled={updateSlipMutation.isPending}
                              >
                                저장
                              </Button>
                              <Button
                                size="sm"
                                variant="ghost"
                                onClick={() => {
                                  setEditingSlip(null);
                                  setEditPartner('');
                                }}
                              >
                                취소
                              </Button>
                            </div>
                          ) : (
                            <Button
                              size="sm"
                              variant="ghost"
                              onClick={() => {
                                setEditingSlip(slip.id);
                                setEditPartner(slip.partner || '');
                              }}
                            >
                              수정
                            </Button>
                          )
                        )}
                      </Td>
                    </tr>
                  ))}
                </tbody>
              </Table>
            </div>
          ) : (
            <div className="text-center py-8 text-gray-500">전표가 없습니다.</div>
          )}

          {currentBatch && (
            <div className="mt-4 flex justify-between items-center text-sm text-gray-600 border-t pt-4">
              <span>총 {slipsData?.total || 0}건</span>
              <span className="font-medium">
                합계: ₩{slips.reduce((sum, s) => sum + s.wrbtr, 0).toLocaleString()}
              </span>
            </div>
          )}
        </Card>
      )}
    </div>
  );
}
