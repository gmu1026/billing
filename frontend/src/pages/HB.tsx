import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { hbApi, masterApi } from '../api/client';
import { Card, Button, Input, FileUpload, Alert, Spinner, Badge, Table, Th, Td } from '../components/ui';
import type { HBCompany, HBContract, HBAccount, BPCode, UploadResponse } from '../types';

type Tab = 'companies' | 'contracts' | 'accounts';

export default function HB() {
  const queryClient = useQueryClient();
  const [activeTab, setActiveTab] = useState<Tab>('companies');
  const [search, setSearch] = useState('');
  const [uploadResult, setUploadResult] = useState<UploadResponse | null>(null);

  // 회사 편집
  const [editingCompany, setEditingCompany] = useState<number | null>(null);
  const [editBpNumber, setEditBpNumber] = useState('');

  // BP 검색
  const [bpSearch, setBpSearch] = useState('');
  const { data: bpCodes } = useQuery({
    queryKey: ['bpCodes', bpSearch],
    queryFn: () => masterApi.getBPCodes({ search: bpSearch, limit: 10 }).then((res) => res.data as BPCode[]),
    enabled: bpSearch.length >= 2,
  });

  // Companies
  const { data: companies, isLoading: companiesLoading } = useQuery({
    queryKey: ['hbCompanies', search],
    queryFn: () => hbApi.getCompanies({ search: search || undefined }).then((res) => res.data as HBCompany[]),
    enabled: activeTab === 'companies',
  });

  // Contracts
  const { data: contracts, isLoading: contractsLoading } = useQuery({
    queryKey: ['hbContracts', search],
    queryFn: () => hbApi.getContracts({ search: search || undefined }).then((res) => res.data as HBContract[]),
    enabled: activeTab === 'contracts',
  });

  // Accounts
  const { data: accounts, isLoading: accountsLoading } = useQuery({
    queryKey: ['hbAccounts', search],
    queryFn: () => hbApi.getAccounts({ search: search || undefined }).then((res) => res.data as HBAccount[]),
    enabled: activeTab === 'accounts',
  });

  // Upload mutations
  const uploadCompanies = useMutation({
    mutationFn: (file: File) => hbApi.uploadCompanies(file),
    onSuccess: (res) => {
      setUploadResult(res.data);
      queryClient.invalidateQueries({ queryKey: ['hbCompanies'] });
    },
  });

  const uploadContracts = useMutation({
    mutationFn: (file: File) => hbApi.uploadContracts(file),
    onSuccess: (res) => {
      setUploadResult(res.data);
      queryClient.invalidateQueries({ queryKey: ['hbContracts'] });
    },
  });

  const uploadAccounts = useMutation({
    mutationFn: (file: File) => hbApi.uploadAccounts(file),
    onSuccess: (res) => {
      setUploadResult(res.data);
      queryClient.invalidateQueries({ queryKey: ['hbAccounts'] });
    },
  });

  // Update company BP
  const updateCompany = useMutation({
    mutationFn: ({ seq, bp_number }: { seq: number; bp_number: string }) =>
      hbApi.updateCompany(seq, { bp_number }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['hbCompanies'] });
      setEditingCompany(null);
      setEditBpNumber('');
    },
  });

  const tabs = [
    { id: 'companies' as Tab, label: '회사', count: companies?.length },
    { id: 'contracts' as Tab, label: '계약', count: contracts?.length },
    { id: 'accounts' as Tab, label: '계정 (UID)', count: accounts?.length },
  ];

  return (
    <div className="space-y-6">
      <h2 className="text-2xl font-bold text-gray-800">HB 연동 데이터</h2>

      {/* Upload Section */}
      <Card title="JSON 파일 업로드">
        <div className="flex flex-wrap gap-4">
          <FileUpload
            label="회사 (hb_company)"
            accept=".json"
            onFileSelect={(file) => uploadCompanies.mutate(file)}
            disabled={uploadCompanies.isPending}
          />
          <FileUpload
            label="계약 (hb_contract)"
            accept=".json"
            onFileSelect={(file) => uploadContracts.mutate(file)}
            disabled={uploadContracts.isPending}
          />
          <FileUpload
            label="계정 (hb_account)"
            accept=".json"
            onFileSelect={(file) => uploadAccounts.mutate(file)}
            disabled={uploadAccounts.isPending}
          />
        </div>

        {uploadResult && (
          <div className="mt-4">
            <Alert type={uploadResult.success ? 'success' : 'error'}>
              {uploadResult.success ? (
                <>업로드 완료: {uploadResult.inserted}건 추가, {uploadResult.updated}건 업데이트</>
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
              {tab.count !== undefined && (
                <span className="ml-2 text-xs bg-gray-100 px-2 py-0.5 rounded-full">
                  {tab.count}
                </span>
              )}
            </button>
          ))}
        </nav>
      </div>

      {/* Search */}
      <div className="flex gap-4">
        <Input
          placeholder="검색..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="max-w-xs"
        />
      </div>

      {/* Companies Tab */}
      {activeTab === 'companies' && (
        <Card>
          {companiesLoading ? (
            <div className="flex justify-center py-8"><Spinner /></div>
          ) : companies && companies.length > 0 ? (
            <Table>
              <thead>
                <tr>
                  <Th>SEQ</Th>
                  <Th>회사명</Th>
                  <Th>사업자번호</Th>
                  <Th>대표자</Th>
                  <Th>BP 번호</Th>
                  <Th>담당자</Th>
                  <Th></Th>
                </tr>
              </thead>
              <tbody>
                {companies.map((c) => (
                  <tr key={c.seq} className="hover:bg-gray-50">
                    <Td className="text-gray-500">{c.seq}</Td>
                    <Td className="font-medium">{c.name}</Td>
                    <Td className="font-mono text-xs">{c.license || '-'}</Td>
                    <Td>{c.ceo_name || '-'}</Td>
                    <Td>
                      {editingCompany === c.seq ? (
                        <div className="flex flex-col gap-1">
                          <Input
                            value={editBpNumber}
                            onChange={(e) => {
                              setEditBpNumber(e.target.value);
                              setBpSearch(e.target.value);
                            }}
                            placeholder="BP번호 입력"
                            className="w-32"
                          />
                          {bpCodes && bpCodes.length > 0 && (
                            <div className="absolute mt-10 bg-white border rounded-lg shadow-lg z-10 max-h-40 overflow-auto">
                              {bpCodes.map((bp) => (
                                <button
                                  key={bp.bp_number}
                                  onClick={() => {
                                    setEditBpNumber(bp.bp_number);
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
                      ) : c.bp_number ? (
                        <Badge variant="success">{c.bp_number}</Badge>
                      ) : (
                        <Badge variant="warning">미매핑</Badge>
                      )}
                    </Td>
                    <Td className="text-sm text-gray-500">{c.manager_name || '-'}</Td>
                    <Td>
                      {editingCompany === c.seq ? (
                        <div className="flex gap-1">
                          <Button
                            size="sm"
                            onClick={() => updateCompany.mutate({ seq: c.seq, bp_number: editBpNumber })}
                            disabled={updateCompany.isPending}
                          >
                            저장
                          </Button>
                          <Button
                            size="sm"
                            variant="ghost"
                            onClick={() => {
                              setEditingCompany(null);
                              setEditBpNumber('');
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
                            setEditingCompany(c.seq);
                            setEditBpNumber(c.bp_number || '');
                          }}
                        >
                          BP 매핑
                        </Button>
                      )}
                    </Td>
                  </tr>
                ))}
              </tbody>
            </Table>
          ) : (
            <div className="text-center py-8 text-gray-500">데이터가 없습니다.</div>
          )}
        </Card>
      )}

      {/* Contracts Tab */}
      {activeTab === 'contracts' && (
        <Card>
          {contractsLoading ? (
            <div className="flex justify-center py-8"><Spinner /></div>
          ) : contracts && contracts.length > 0 ? (
            <Table>
              <thead>
                <tr>
                  <Th>SEQ</Th>
                  <Th>계약명</Th>
                  <Th>회사</Th>
                  <Th>법인</Th>
                  <Th>영업담당</Th>
                  <Th>매출계약번호</Th>
                  <Th>상태</Th>
                </tr>
              </thead>
              <tbody>
                {contracts.map((c) => (
                  <tr key={c.seq} className="hover:bg-gray-50">
                    <Td className="text-gray-500">{c.seq}</Td>
                    <Td className="font-medium">{c.name}</Td>
                    <Td>{c.company_name || '-'}</Td>
                    <Td>
                      <Badge>{c.corporation || '-'}</Badge>
                    </Td>
                    <Td>{c.sales_person || '-'}</Td>
                    <Td className="font-mono text-xs">
                      {c.sales_contract_code || <span className="text-gray-400">미설정</span>}
                    </Td>
                    <Td>
                      <Badge variant={c.enabled ? 'success' : 'default'}>
                        {c.enabled ? '활성' : '비활성'}
                      </Badge>
                    </Td>
                  </tr>
                ))}
              </tbody>
            </Table>
          ) : (
            <div className="text-center py-8 text-gray-500">데이터가 없습니다.</div>
          )}
        </Card>
      )}

      {/* Accounts Tab */}
      {activeTab === 'accounts' && (
        <Card>
          {accountsLoading ? (
            <div className="flex justify-center py-8"><Spinner /></div>
          ) : accounts && accounts.length > 0 ? (
            <Table>
              <thead>
                <tr>
                  <Th>UID</Th>
                  <Th>이름</Th>
                  <Th>원본 이름</Th>
                  <Th>마스터 ID</Th>
                  <Th>법인</Th>
                  <Th>상태</Th>
                </tr>
              </thead>
              <tbody>
                {accounts.map((a) => (
                  <tr key={a.id} className="hover:bg-gray-50">
                    <Td className="font-mono text-xs">{a.id}</Td>
                    <Td className="font-medium">{a.name || '-'}</Td>
                    <Td className="text-sm text-gray-500 max-w-xs truncate">{a.original_name || '-'}</Td>
                    <Td className="font-mono text-xs">{a.master_id || '-'}</Td>
                    <Td><Badge>{a.corporation || '-'}</Badge></Td>
                    <Td>
                      <Badge variant={a.is_active ? 'success' : 'default'}>
                        {a.is_active ? '활성' : '비활성'}
                      </Badge>
                    </Td>
                  </tr>
                ))}
              </tbody>
            </Table>
          ) : (
            <div className="text-center py-8 text-gray-500">데이터가 없습니다.</div>
          )}
        </Card>
      )}
    </div>
  );
}
