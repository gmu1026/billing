import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { importApi } from '../api/client';
import { Card, Button, Alert, Spinner, Badge, Table, Th, Td } from '../components/ui';

interface ScanResult {
  import_dir: string;
  files: {
    billing: {
      enduser: string[];
      reseller: string[];
    };
    master: string[];
    hb: string[];
  };
}

interface ImportResult {
  success: boolean;
  type?: string;
  filename?: string;
  inserted?: number;
  updated?: number;
  errors?: string[];
  error?: string;
}

export default function Import() {
  const queryClient = useQueryClient();
  const [results, setResults] = useState<ImportResult[]>([]);

  const { data: scanResult, isLoading } = useQuery({
    queryKey: ['importScan'],
    queryFn: () => importApi.scan().then((res) => res.data as ScanResult),
  });

  const importBillingMutation = useMutation({
    mutationFn: ({ type, filename }: { type: 'enduser' | 'reseller'; filename: string }) =>
      importApi.importBilling(type, filename),
    onSuccess: (res) => {
      setResults((prev) => [...prev, res.data]);
      queryClient.invalidateQueries({ queryKey: ['importScan'] });
      queryClient.invalidateQueries({ queryKey: ['billingSummary'] });
    },
  });

  const importMasterMutation = useMutation({
    mutationFn: ({ type, filename }: { type: string; filename?: string }) =>
      importApi.importMaster(type, filename),
    onSuccess: (res) => {
      setResults((prev) => [...prev, res.data]);
      queryClient.invalidateQueries({ queryKey: ['importScan'] });
    },
  });

  const importHBMutation = useMutation({
    mutationFn: ({ type, filename }: { type: string; filename?: string }) =>
      importApi.importHB(type, filename),
    onSuccess: (res) => {
      setResults((prev) => [...prev, res.data]);
      queryClient.invalidateQueries({ queryKey: ['importScan'] });
    },
  });

  const importAllMutation = useMutation({
    mutationFn: () => importApi.importAll(),
    onSuccess: (res) => {
      setResults(res.data.results);
      queryClient.invalidateQueries({ queryKey: ['importScan'] });
    },
  });

  // 파일명에서 마스터 유형 감지 (대소문자 무시)
  const detectMasterType = (filename: string): string | null => {
    const lower = filename.toLowerCase();
    if (lower.includes('bp_code') || lower.includes('bp코드')) return 'bp_code';
    if (lower.includes('계정코드') || lower.includes('account')) return 'account_code';
    if (lower.includes('세금코드') || lower.includes('tax')) return 'tax_code';
    if (lower.includes('부서코드') || lower.includes('cost')) return 'cost_center';
    if (lower.includes('계약번호') || lower.includes('contract')) return 'contract';
    return null;
  };

  const getMasterTypeLabel = (type: string | null): string => {
    const labels: Record<string, string> = {
      'bp_code': 'BP코드',
      'account_code': '계정코드',
      'tax_code': '세금코드',
      'cost_center': '부서코드',
      'contract': '계약번호',
    };
    return type ? labels[type] || type : '알 수 없음';
  };

  // HB 파일명에서 유형 감지
  const detectHBType = (filename: string): string | null => {
    const lower = filename.toLowerCase();
    if (lower.includes('company')) return 'company';
    if (lower.includes('contract')) return 'contract';
    if (lower.includes('account')) return 'account';
    return null;
  };

  const getHBTypeLabel = (type: string | null): string => {
    const labels: Record<string, string> = {
      'company': '회사',
      'contract': '계약',
      'account': '계정',
    };
    return type ? labels[type] || type : '알 수 없음';
  };

  const isPending =
    importBillingMutation.isPending ||
    importMasterMutation.isPending ||
    importHBMutation.isPending ||
    importAllMutation.isPending;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-bold text-gray-800">파일 임포트</h2>
        <Button onClick={() => importAllMutation.mutate()} disabled={isPending}>
          {importAllMutation.isPending ? '임포트 중...' : '전체 임포트'}
        </Button>
      </div>

      {/* Import Directory Info */}
      <Card title="임포트 폴더">
        {isLoading ? (
          <Spinner />
        ) : (
          <div className="space-y-2">
            <p className="text-sm text-gray-600">
              아래 폴더에 파일을 넣고 임포트 버튼을 클릭하세요.
            </p>
            <code className="block bg-gray-100 p-3 rounded text-sm font-mono break-all">
              {scanResult?.import_dir}
            </code>
          </div>
        )}
      </Card>

      {/* Results */}
      {results.length > 0 && (
        <Card title="임포트 결과">
          <div className="space-y-2">
            {results.map((r, i) => (
              <Alert key={i} type={r.success ? 'success' : 'error'}>
                <div className="flex items-center gap-2">
                  <Badge variant={r.success ? 'success' : 'danger'}>
                    {r.type || r.filename}
                  </Badge>
                  {r.success ? (
                    <span>
                      추가: {r.inserted || 0}건
                      {r.updated ? `, 업데이트: ${r.updated}건` : ''}
                    </span>
                  ) : (
                    <span>{r.error || r.errors?.join(', ')}</span>
                  )}
                </div>
              </Alert>
            ))}
            <Button variant="ghost" size="sm" onClick={() => setResults([])}>
              결과 지우기
            </Button>
          </div>
        </Card>
      )}

      {/* Billing Files */}
      <Card title="빌링 데이터 (CSV)">
        <div className="grid grid-cols-2 gap-6">
          <div>
            <h4 className="font-medium text-gray-700 mb-2">매출 (Enduser)</h4>
            <p className="text-xs text-gray-500 mb-2">
              폴더: <code>billing/enduser/</code>
            </p>
            {scanResult?.files.billing.enduser.length ? (
              <Table>
                <thead>
                  <tr>
                    <Th>파일명</Th>
                    <Th></Th>
                  </tr>
                </thead>
                <tbody>
                  {scanResult.files.billing.enduser.map((f) => (
                    <tr key={f}>
                      <Td className="font-mono text-sm">{f}</Td>
                      <Td>
                        <Button
                          size="sm"
                          onClick={() => importBillingMutation.mutate({ type: 'enduser', filename: f })}
                          disabled={isPending}
                        >
                          임포트
                        </Button>
                      </Td>
                    </tr>
                  ))}
                </tbody>
              </Table>
            ) : (
              <p className="text-sm text-gray-400">파일 없음</p>
            )}
          </div>

          <div>
            <h4 className="font-medium text-gray-700 mb-2">매입 (Reseller)</h4>
            <p className="text-xs text-gray-500 mb-2">
              폴더: <code>billing/reseller/</code>
            </p>
            {scanResult?.files.billing.reseller.length ? (
              <Table>
                <thead>
                  <tr>
                    <Th>파일명</Th>
                    <Th></Th>
                  </tr>
                </thead>
                <tbody>
                  {scanResult.files.billing.reseller.map((f) => (
                    <tr key={f}>
                      <Td className="font-mono text-sm">{f}</Td>
                      <Td>
                        <Button
                          size="sm"
                          onClick={() => importBillingMutation.mutate({ type: 'reseller', filename: f })}
                          disabled={isPending}
                        >
                          임포트
                        </Button>
                      </Td>
                    </tr>
                  ))}
                </tbody>
              </Table>
            ) : (
              <p className="text-sm text-gray-400">파일 없음</p>
            )}
          </div>
        </div>
      </Card>

      {/* Master Files */}
      <Card title="마스터 데이터 (CSV)">
        <p className="text-xs text-gray-500 mb-2">
          폴더: <code>master/</code>
        </p>
        {scanResult?.files.master.length ? (
          <Table>
            <thead>
              <tr>
                <Th>파일명</Th>
                <Th>유형</Th>
                <Th></Th>
              </tr>
            </thead>
            <tbody>
              {scanResult.files.master.map((f) => {
                const masterType = detectMasterType(f);
                return (
                  <tr key={f}>
                    <Td className="font-mono text-sm">{f}</Td>
                    <Td>
                      <Badge>{getMasterTypeLabel(masterType)}</Badge>
                    </Td>
                    <Td>
                      <Button
                        size="sm"
                        onClick={() =>
                          importMasterMutation.mutate({
                            type: masterType || 'bp_code',
                            filename: f,
                          })
                        }
                        disabled={isPending || !masterType}
                      >
                        임포트
                      </Button>
                    </Td>
                  </tr>
                );
              })}
            </tbody>
          </Table>
        ) : (
          <p className="text-sm text-gray-400">파일 없음</p>
        )}
      </Card>

      {/* HB Files */}
      <Card title="HB 연동 데이터 (JSON)">
        <p className="text-xs text-gray-500 mb-2">
          폴더: <code>hb/</code>
        </p>
        {scanResult?.files.hb.length ? (
          <Table>
            <thead>
              <tr>
                <Th>파일명</Th>
                <Th>유형</Th>
                <Th></Th>
              </tr>
            </thead>
            <tbody>
              {scanResult.files.hb.map((f) => {
                const hbType = detectHBType(f);
                return (
                  <tr key={f}>
                    <Td className="font-mono text-sm">{f}</Td>
                    <Td>
                      <Badge>{getHBTypeLabel(hbType)}</Badge>
                    </Td>
                    <Td>
                      <Button
                        size="sm"
                        onClick={() =>
                          importHBMutation.mutate({
                            type: hbType || 'company',
                            filename: f,
                          })
                        }
                        disabled={isPending || !hbType}
                      >
                        임포트
                      </Button>
                    </Td>
                  </tr>
                );
              })}
            </tbody>
          </Table>
        ) : (
          <p className="text-sm text-gray-400">파일 없음</p>
        )}
      </Card>
    </div>
  );
}
