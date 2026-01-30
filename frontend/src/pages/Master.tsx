import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { masterApi } from '../api/client';
import { Card, Input, FileUpload, Alert, Spinner, Table, Th, Td } from '../components/ui';
import type { BPCode, UploadResponse } from '../types';

type Tab = 'bp' | 'account' | 'contract';

export default function Master() {
  const queryClient = useQueryClient();
  const [activeTab, setActiveTab] = useState<Tab>('bp');
  const [search, setSearch] = useState('');
  const [uploadResult, setUploadResult] = useState<UploadResponse | null>(null);

  // BP Codes
  const { data: bpCodes, isLoading: bpLoading } = useQuery({
    queryKey: ['bpCodes', search],
    queryFn: () => masterApi.getBPCodes({ search: search || undefined, limit: 100 }).then((res) => res.data as BPCode[]),
    enabled: activeTab === 'bp',
  });

  // Account Codes
  const { data: accountCodes, isLoading: accountLoading } = useQuery({
    queryKey: ['accountCodes', search],
    queryFn: () => masterApi.getAccountCodes({ search: search || undefined }).then((res) => res.data),
    enabled: activeTab === 'account',
  });

  // Contracts
  const { data: contracts, isLoading: contractsLoading } = useQuery({
    queryKey: ['masterContracts'],
    queryFn: () => masterApi.getContracts({ vendor: 'alibaba' }).then((res) => res.data),
    enabled: activeTab === 'contract',
  });

  // Upload mutations
  const uploadBP = useMutation({
    mutationFn: (file: File) => masterApi.uploadBPCodes(file),
    onSuccess: (res) => {
      setUploadResult(res.data);
      queryClient.invalidateQueries({ queryKey: ['bpCodes'] });
    },
  });

  const uploadAccount = useMutation({
    mutationFn: (file: File) => masterApi.uploadAccountCodes(file),
    onSuccess: (res) => {
      setUploadResult(res.data);
      queryClient.invalidateQueries({ queryKey: ['accountCodes'] });
    },
  });

  const uploadContracts = useMutation({
    mutationFn: (file: File) => masterApi.uploadContracts(file),
    onSuccess: (res) => {
      setUploadResult(res.data);
      queryClient.invalidateQueries({ queryKey: ['masterContracts'] });
    },
  });

  const tabs = [
    { id: 'bp' as Tab, label: 'BP 코드 (거래처)' },
    { id: 'account' as Tab, label: '계정코드' },
    { id: 'contract' as Tab, label: '계약번호' },
  ];

  return (
    <div className="space-y-6">
      <h2 className="text-2xl font-bold text-gray-800">마스터 데이터</h2>

      {/* Upload Section */}
      <Card title="마스터 데이터 업로드">
        <div className="flex flex-wrap gap-4">
          <FileUpload
            label="BP 코드 (CSV)"
            accept=".csv"
            onFileSelect={(file) => uploadBP.mutate(file)}
            disabled={uploadBP.isPending}
          />
          <FileUpload
            label="계정코드 (CSV)"
            accept=".csv"
            onFileSelect={(file) => uploadAccount.mutate(file)}
            disabled={uploadAccount.isPending}
          />
          <FileUpload
            label="계약번호 (CSV)"
            accept=".csv"
            onFileSelect={(file) => uploadContracts.mutate(file)}
            disabled={uploadContracts.isPending}
          />
        </div>

        {uploadResult && (
          <div className="mt-4">
            <Alert type={uploadResult.success ? 'success' : 'error'}>
              {uploadResult.success ? (
                <>업로드 완료: {uploadResult.inserted}건 추가, {uploadResult.updated || 0}건 업데이트</>
              ) : (
                <>업로드 실패: {uploadResult.errors?.join(', ')}</>
              )}
            </Alert>
          </div>
        )}
      </Card>

      {/* Tab Navigation */}
      <div className="border-b border-gray-200">
        <nav className="flex gap-4">
          {tabs.map((tab) => (
            <button
              key={tab.id}
              onClick={() => {
                setActiveTab(tab.id);
                setSearch('');
              }}
              className={`px-4 py-2 text-sm font-medium border-b-2 -mb-px transition-colors ${
                activeTab === tab.id
                  ? 'border-blue-600 text-blue-600'
                  : 'border-transparent text-gray-500 hover:text-gray-700'
              }`}
            >
              {tab.label}
            </button>
          ))}
        </nav>
      </div>

      {/* Search */}
      {activeTab !== 'contract' && (
        <div className="flex gap-4">
          <Input
            placeholder="검색..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="max-w-xs"
          />
        </div>
      )}

      {/* BP Codes Tab */}
      {activeTab === 'bp' && (
        <Card>
          {bpLoading ? (
            <div className="flex justify-center py-8"><Spinner /></div>
          ) : bpCodes && bpCodes.length > 0 ? (
            <Table>
              <thead>
                <tr>
                  <Th>BP 번호</Th>
                  <Th>이름</Th>
                  <Th>사업자번호</Th>
                  <Th>대표자</Th>
                  <Th>주소</Th>
                </tr>
              </thead>
              <tbody>
                {bpCodes.map((bp) => (
                  <tr key={bp.bp_number} className="hover:bg-gray-50">
                    <Td className="font-mono">{bp.bp_number}</Td>
                    <Td className="font-medium">{bp.name || '-'}</Td>
                    <Td className="font-mono text-sm">{bp.tax_number || '-'}</Td>
                    <Td>{bp.representative || '-'}</Td>
                    <Td className="text-sm text-gray-500 max-w-xs truncate">
                      {bp.road_address || '-'}
                    </Td>
                  </tr>
                ))}
              </tbody>
            </Table>
          ) : (
            <div className="text-center py-8 text-gray-500">
              데이터가 없습니다. BP_CODE.CSV 파일을 업로드해주세요.
            </div>
          )}
        </Card>
      )}

      {/* Account Codes Tab */}
      {activeTab === 'account' && (
        <Card>
          {accountLoading ? (
            <div className="flex justify-center py-8"><Spinner /></div>
          ) : accountCodes && accountCodes.length > 0 ? (
            <Table>
              <thead>
                <tr>
                  <Th>계정코드</Th>
                  <Th>계정명 (Short)</Th>
                  <Th>계정명 (Long)</Th>
                  <Th>그룹</Th>
                </tr>
              </thead>
              <tbody>
                {accountCodes.map((acc: any) => (
                  <tr key={acc.hkont} className="hover:bg-gray-50">
                    <Td className="font-mono">{acc.hkont}</Td>
                    <Td className="font-medium">{acc.name || '-'}</Td>
                    <Td>{acc.name_long || '-'}</Td>
                    <Td className="text-sm text-gray-500">{acc.group || '-'}</Td>
                  </tr>
                ))}
              </tbody>
            </Table>
          ) : (
            <div className="text-center py-8 text-gray-500">
              데이터가 없습니다. 계정코드.CSV 파일을 업로드해주세요.
            </div>
          )}
        </Card>
      )}

      {/* Contracts Tab */}
      {activeTab === 'contract' && (
        <Card>
          {contractsLoading ? (
            <div className="flex justify-center py-8"><Spinner /></div>
          ) : contracts && contracts.length > 0 ? (
            <Table>
              <thead>
                <tr>
                  <Th>매출계약번호</Th>
                  <Th>매입계약번호</Th>
                  <Th>설명</Th>
                  <Th>벤더</Th>
                </tr>
              </thead>
              <tbody>
                {contracts.map((c: any) => (
                  <tr key={c.sales_contract} className="hover:bg-gray-50">
                    <Td className="font-mono">{c.sales_contract}</Td>
                    <Td className="font-mono">{c.purchase_contract}</Td>
                    <Td>{c.description || '-'}</Td>
                    <Td className="text-sm text-gray-500">{c.vendor || '-'}</Td>
                  </tr>
                ))}
              </tbody>
            </Table>
          ) : (
            <div className="text-center py-8 text-gray-500">
              데이터가 없습니다. 매출계약번호.CSV 파일을 업로드해주세요.
            </div>
          )}
        </Card>
      )}
    </div>
  );
}
