import { useState, useEffect } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useSearchParams } from 'react-router-dom';
import { slipApi, masterApi } from '../api/client';
import { Card, Button, Input, Select, Alert, Spinner, Badge, Table, Th, Td } from '../components/ui';
import type { SlipRecord, SlipBatch, GenerateResponse, BPCode } from '../types';

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

  // Latest exchange rate
  const { data: latestRate } = useQuery({
    queryKey: ['latestRate'],
    queryFn: () => slipApi.getLatestRate().then((res) => res.data),
  });

  useEffect(() => {
    if (latestRate?.found && !exchangeRate) {
      setExchangeRate(String(latestRate.rate));
    }
  }, [latestRate]);

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

  // Create exchange rate
  const createRateMutation = useMutation({
    mutationFn: (rate: number) => slipApi.createExchangeRate({ rate, rate_date: documentDate }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['latestRate'] }),
  });

  // Generate slips
  const generateMutation = useMutation({
    mutationFn: () =>
      slipApi.generate({
        billing_cycle: billingCycle,
        slip_type: slipType,
        document_date: documentDate,
        exchange_rate: Number(exchangeRate),
        invoice_number: invoiceNumber || undefined,
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
    if (!exchangeRate || Number(exchangeRate) <= 0) {
      alert('환율을 입력해주세요.');
      return;
    }
    // Save exchange rate
    createRateMutation.mutate(Number(exchangeRate));
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
      <h2 className="text-2xl font-bold text-gray-800">전표 생성</h2>

      {/* Generate Form */}
      <Card title="전표 생성">
        <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
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
          <Input
            label="환율 (USD/KRW)"
            type="number"
            value={exchangeRate}
            onChange={(e) => setExchangeRate(e.target.value)}
            placeholder={latestRate?.found ? `최근: ${latestRate.rate}` : '환율 입력'}
          />
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
