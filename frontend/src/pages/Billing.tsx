import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { alibabaApi } from '../api/client';
import { Card, Button, Select, FileUpload, Alert, Spinner, Table, Th, Td } from '../components/ui';
import type { BillingSummary, UploadResponse } from '../types';

export default function Billing() {
  const queryClient = useQueryClient();
  const [billingType, setBillingType] = useState<'enduser' | 'reseller'>('enduser');
  const [billingCycle, setBillingCycle] = useState(() => {
    const d = new Date();
    d.setMonth(d.getMonth() - 1);
    return d.toISOString().slice(0, 7).replace('-', '');
  });
  const [uploadResult, setUploadResult] = useState<UploadResponse | null>(null);

  // 빌링 요약 조회
  const { data: summary, isLoading } = useQuery({
    queryKey: ['billingSummary', billingType, billingCycle],
    queryFn: () =>
      alibabaApi
        .getSummary({ billing_type: billingType, billing_cycle: billingCycle })
        .then((res) => res.data as BillingSummary),
  });

  // 파일 업로드
  const uploadMutation = useMutation({
    mutationFn: (file: File) => alibabaApi.upload(billingType, file),
    onSuccess: (res) => {
      setUploadResult(res.data);
      queryClient.invalidateQueries({ queryKey: ['billingSummary'] });
    },
    onError: (err: any) => {
      setUploadResult({
        success: false,
        errors: [err.response?.data?.detail || '업로드 실패'],
      });
    },
  });

  // 데이터 삭제
  const deleteMutation = useMutation({
    mutationFn: () => alibabaApi.delete({ billing_type: billingType, billing_cycle: billingCycle }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['billingSummary'] });
      alert('삭제되었습니다.');
    },
  });

  const handleDelete = () => {
    if (confirm(`${billingCycle} ${billingType} 데이터를 삭제하시겠습니까?`)) {
      deleteMutation.mutate();
    }
  };

  // 월 옵션 생성 (최근 12개월)
  const monthOptions = Array.from({ length: 12 }, (_, i) => {
    const d = new Date();
    d.setMonth(d.getMonth() - i);
    const value = d.toISOString().slice(0, 7).replace('-', '');
    const label = `${d.getFullYear()}년 ${d.getMonth() + 1}월`;
    return { value, label };
  });

  return (
    <div className="space-y-6">
      <h2 className="text-2xl font-bold text-gray-800">빌링 데이터</h2>

      {/* Upload Section */}
      <Card title="빌링 데이터 업로드">
        <div className="flex flex-wrap items-end gap-4">
          <Select
            label="정산월"
            value={billingCycle}
            onChange={(e) => setBillingCycle(e.target.value)}
            options={monthOptions}
            className="w-40"
          />
          <Select
            label="유형"
            value={billingType}
            onChange={(e) => setBillingType(e.target.value as any)}
            options={[
              { value: 'enduser', label: 'Enduser (매출)' },
              { value: 'reseller', label: 'Reseller (매입)' },
            ]}
            className="w-40"
          />
          <FileUpload
            label={uploadMutation.isPending ? '업로드 중...' : 'CSV 업로드'}
            accept=".csv"
            onFileSelect={(file) => uploadMutation.mutate(file)}
            disabled={uploadMutation.isPending}
          />
        </div>

        {uploadResult && (
          <div className="mt-4">
            <Alert type={uploadResult.success ? 'success' : 'error'}>
              {uploadResult.success ? (
                <>
                  업로드 완료: {uploadResult.inserted || uploadResult.total_rows}건 처리됨
                </>
              ) : (
                <>
                  업로드 실패
                  {uploadResult.errors?.map((e, i) => (
                    <div key={i} className="text-xs mt-1">{e}</div>
                  ))}
                </>
              )}
            </Alert>
          </div>
        )}
      </Card>

      {/* Summary Section */}
      <Card
        title={`빌링 요약 - ${billingCycle} ${billingType === 'enduser' ? '매출' : '매입'}`}
        action={
          summary && summary.user_count > 0 && (
            <Button
              variant="danger"
              size="sm"
              onClick={handleDelete}
              disabled={deleteMutation.isPending}
            >
              데이터 삭제
            </Button>
          )
        }
      >
        {isLoading ? (
          <div className="flex justify-center py-8">
            <Spinner />
          </div>
        ) : summary ? (
          <>
            {/* Stats */}
            <div className="grid grid-cols-3 gap-4 mb-6">
              <div className="bg-gray-50 rounded-lg p-4">
                <div className="text-sm text-gray-500">UID 수</div>
                <div className="text-xl font-bold">{summary.user_count}</div>
              </div>
              <div className="bg-gray-50 rounded-lg p-4">
                <div className="text-sm text-gray-500">총 금액 (USD)</div>
                <div className="text-xl font-bold">
                  ${summary.total_amount.toLocaleString(undefined, { minimumFractionDigits: 2 })}
                </div>
              </div>
              <div className="bg-gray-50 rounded-lg p-4">
                <div className="text-sm text-gray-500">평균 금액</div>
                <div className="text-xl font-bold">
                  ${summary.user_count > 0
                    ? (summary.total_amount / summary.user_count).toLocaleString(undefined, {
                        minimumFractionDigits: 2,
                      })
                    : '0'}
                </div>
              </div>
            </div>

            {/* User List */}
            {summary.by_user.length > 0 ? (
              <Table>
                <thead>
                  <tr>
                    <Th>UID</Th>
                    <Th>이름</Th>
                    <Th className="text-right">금액 (USD)</Th>
                    <Th className="text-right">레코드 수</Th>
                  </tr>
                </thead>
                <tbody>
                  {summary.by_user.slice(0, 50).map((item) => (
                    <tr key={item.uid} className="hover:bg-gray-50">
                      <Td className="font-mono text-xs">{item.uid}</Td>
                      <Td>{item.user_name || '-'}</Td>
                      <Td className="text-right font-medium">
                        ${item.total_amount.toLocaleString(undefined, { minimumFractionDigits: 2 })}
                      </Td>
                      <Td className="text-right text-gray-500">{item.record_count}</Td>
                    </tr>
                  ))}
                </tbody>
              </Table>
            ) : (
              <div className="text-center py-8 text-gray-500">
                데이터가 없습니다. CSV 파일을 업로드해주세요.
              </div>
            )}

            {summary.by_user.length > 50 && (
              <div className="text-center text-sm text-gray-500 mt-4">
                외 {summary.by_user.length - 50}건
              </div>
            )}
          </>
        ) : null}
      </Card>
    </div>
  );
}
