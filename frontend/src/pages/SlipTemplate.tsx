import { useState, useEffect, useRef } from 'react';
import { slipTemplateApi } from '../api/client';

interface FileInfo {
  filename: string;
  path: string;
  size: number;
  slip_type_guess: string | null;
}

interface ColumnDef {
  index: number;
  name: string;
  header: string;
  data_type: string;
  sample_values: unknown[];
}

interface TemplateAnalysis {
  slip_type: string;
  columns: ColumnDef[];
  fixed_values: Record<string, unknown>;
  account_mappings: Record<string, Record<string, string>>;
  contract_pattern: Record<string, string> | null;
  description_template: string | null;
  row_count: number;
}

interface SlipTemplate {
  id: number;
  name: string;
  slip_type: string;
  columns: ColumnDef[];
  fixed_values: Record<string, unknown>;
  account_mappings: Record<string, Record<string, string>>;
  contract_pattern: Record<string, string> | null;
  description_template: string | null;
  source_file: string | null;
  is_active: boolean;
}

interface ExtractedProfile {
  bp_number: string;
  tax_number: string | null;
  company_name: string | null;
  currency: string;
  is_overseas: boolean;
  ar_account: string | null;
  hkont_sales: string | null;
  hkont_purchase: string | null;
  tax_code: string | null;
  row_count: number;
  hb_company_seq: number | null;
  hb_company_name: string | null;
  existing_profile_id: number | null;
  selected?: boolean;
}

interface ProfileExtractionResult {
  slip_type: string;
  source_file: string;
  total_rows: number;
  profiles: ExtractedProfile[];
  matched_count: number;
  unmatched_count: number;
}

const SLIP_TYPE_LABELS: Record<string, string> = {
  sales: '매출',
  billing: '청구',
  purchase: '원가',
};

export default function SlipTemplate() {
  const [files, setFiles] = useState<FileInfo[]>([]);
  const [templates, setTemplates] = useState<SlipTemplate[]>([]);
  const [analysis, setAnalysis] = useState<TemplateAnalysis | null>(null);
  const [selectedFile, setSelectedFile] = useState<FileInfo | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<'files' | 'templates' | 'profiles'>('files');
  const [selectedTemplate, setSelectedTemplate] = useState<SlipTemplate | null>(null);
  const [templateName, setTemplateName] = useState('');
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Profile extraction state
  const [profileResult, setProfileResult] = useState<ProfileExtractionResult | null>(null);
  const [selectedProfiles, setSelectedProfiles] = useState<Set<string>>(new Set());
  const [overwriteProfiles, setOverwriteProfiles] = useState(false);

  useEffect(() => {
    loadFiles();
    loadTemplates();
  }, []);

  const loadFiles = async () => {
    try {
      const res = await slipTemplateApi.scanFiles();
      setFiles(res.data);
    } catch (err) {
      console.error('Failed to scan files:', err);
    }
  };

  const loadTemplates = async () => {
    try {
      const res = await slipTemplateApi.getTemplates({ active_only: false });
      setTemplates(res.data);
    } catch (err) {
      console.error('Failed to load templates:', err);
    }
  };

  const handleAnalyzePath = async (file: FileInfo) => {
    setLoading(true);
    setError(null);
    setSelectedFile(file);
    setAnalysis(null);
    setTemplateName(file.filename.replace(/\.(xlsx|xls)$/i, ''));

    try {
      const res = await slipTemplateApi.analyzePath(file.path);
      setAnalysis(res.data);
    } catch (err: unknown) {
      const errorMessage = err instanceof Error ? err.message : '분석 실패';
      setError(errorMessage);
    } finally {
      setLoading(false);
    }
  };

  const handleAnalyzeUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setLoading(true);
    setError(null);
    setSelectedFile(null);
    setAnalysis(null);
    setTemplateName(file.name.replace(/\.(xlsx|xls)$/i, ''));

    try {
      const res = await slipTemplateApi.analyzeFile(file);
      setAnalysis(res.data);
    } catch (err: unknown) {
      const errorMessage = err instanceof Error ? err.message : '분석 실패';
      setError(errorMessage);
    } finally {
      setLoading(false);
    }
  };

  const handleImport = async () => {
    if (!analysis) return;

    setLoading(true);
    setError(null);

    try {
      if (selectedFile) {
        await slipTemplateApi.importPath(selectedFile.path, templateName || undefined);
      } else if (fileInputRef.current?.files?.[0]) {
        await slipTemplateApi.importFile(fileInputRef.current.files[0], templateName || undefined);
      }
      await loadTemplates();
      setAnalysis(null);
      setSelectedFile(null);
      setActiveTab('templates');
      alert('템플릿이 저장되었습니다.');
    } catch (err: unknown) {
      const errorMessage = err instanceof Error ? err.message : '저장 실패';
      setError(errorMessage);
    } finally {
      setLoading(false);
    }
  };

  const handleDeleteTemplate = async (id: number) => {
    if (!confirm('템플릿을 삭제하시겠습니까?')) return;

    try {
      await slipTemplateApi.deleteTemplate(id);
      await loadTemplates();
      if (selectedTemplate?.id === id) {
        setSelectedTemplate(null);
      }
    } catch (err: unknown) {
      const errorMessage = err instanceof Error ? err.message : '삭제 실패';
      alert(errorMessage);
    }
  };

  const handleToggleActive = async (template: SlipTemplate) => {
    try {
      await slipTemplateApi.updateTemplate(template.id, { is_active: !template.is_active });
      await loadTemplates();
    } catch (err: unknown) {
      const errorMessage = err instanceof Error ? err.message : '업데이트 실패';
      alert(errorMessage);
    }
  };

  // Profile extraction handlers
  const handleExtractProfiles = async (file: FileInfo) => {
    setLoading(true);
    setError(null);
    setProfileResult(null);
    setSelectedProfiles(new Set());

    try {
      const res = await slipTemplateApi.extractProfilesPath(file.path);
      setProfileResult(res.data);
      // 기본적으로 매칭된 프로필 모두 선택
      const matched = new Set<string>();
      res.data.profiles.forEach((p: ExtractedProfile) => {
        if (p.hb_company_seq) {
          matched.add(p.bp_number);
        }
      });
      setSelectedProfiles(matched);
    } catch (err: unknown) {
      const errorMessage = err instanceof Error ? err.message : '프로필 추출 실패';
      setError(errorMessage);
    } finally {
      setLoading(false);
    }
  };

  const handleToggleProfileSelect = (bpNumber: string) => {
    const newSelected = new Set(selectedProfiles);
    if (newSelected.has(bpNumber)) {
      newSelected.delete(bpNumber);
    } else {
      newSelected.add(bpNumber);
    }
    setSelectedProfiles(newSelected);
  };

  const handleSelectAllProfiles = (matched: boolean) => {
    if (!profileResult) return;
    const newSelected = new Set<string>();
    profileResult.profiles.forEach(p => {
      if (matched ? p.hb_company_seq : true) {
        newSelected.add(p.bp_number);
      }
    });
    setSelectedProfiles(newSelected);
  };

  const handleApplyProfiles = async () => {
    if (!profileResult || selectedProfiles.size === 0) return;

    const profilesToApply = profileResult.profiles
      .filter(p => selectedProfiles.has(p.bp_number) && p.hb_company_seq)
      .map(p => ({
        hb_company_seq: p.hb_company_seq,
        currency: p.currency,
        ar_account: p.ar_account,
        hkont_sales: p.hkont_sales,
        hkont_purchase: p.hkont_purchase,
      }));

    if (profilesToApply.length === 0) {
      alert('HB 매칭된 프로필만 적용할 수 있습니다.');
      return;
    }

    setLoading(true);
    try {
      const res = await slipTemplateApi.applyProfiles({
        profiles: profilesToApply,
        vendor: 'alibaba',
        overwrite: overwriteProfiles,
      });
      alert(`프로필 적용 완료: 생성 ${res.data.created}, 업데이트 ${res.data.updated}, 스킵 ${res.data.skipped}`);
    } catch (err: unknown) {
      const errorMessage = err instanceof Error ? err.message : '프로필 적용 실패';
      alert(errorMessage);
    } finally {
      setLoading(false);
    }
  };

  const formatBytes = (bytes: number) => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  return (
    <div className="p-6">
      <h1 className="text-2xl font-bold mb-6">전표 템플릿 관리</h1>

      {/* Tabs */}
      <div className="flex border-b mb-6">
        <button
          className={`px-4 py-2 font-medium ${
            activeTab === 'files'
              ? 'border-b-2 border-blue-500 text-blue-600'
              : 'text-gray-500 hover:text-gray-700'
          }`}
          onClick={() => setActiveTab('files')}
        >
          템플릿 가져오기
        </button>
        <button
          className={`px-4 py-2 font-medium ${
            activeTab === 'profiles'
              ? 'border-b-2 border-blue-500 text-blue-600'
              : 'text-gray-500 hover:text-gray-700'
          }`}
          onClick={() => setActiveTab('profiles')}
        >
          프로필 추출
        </button>
        <button
          className={`px-4 py-2 font-medium ${
            activeTab === 'templates'
              ? 'border-b-2 border-blue-500 text-blue-600'
              : 'text-gray-500 hover:text-gray-700'
          }`}
          onClick={() => setActiveTab('templates')}
        >
          저장된 템플릿 ({templates.length})
        </button>
      </div>

      {error && (
        <div className="bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded mb-4">
          {error}
        </div>
      )}

      {/* 템플릿 가져오기 탭 */}
      {activeTab === 'files' && (
        <div className="grid grid-cols-2 gap-6">
          {/* Left: File List */}
          <div className="bg-white rounded-lg shadow p-4">
            <h2 className="text-lg font-semibold mb-4">전표 파일 선택</h2>

            {/* Upload Button */}
            <div className="mb-4">
              <input
                ref={fileInputRef}
                type="file"
                accept=".xlsx,.xls"
                onChange={handleAnalyzeUpload}
                className="hidden"
                id="file-upload"
              />
              <label
                htmlFor="file-upload"
                className="inline-block px-4 py-2 bg-blue-600 text-white rounded cursor-pointer hover:bg-blue-700"
              >
                파일 업로드
              </label>
              <span className="ml-2 text-sm text-gray-500">또는 아래 목록에서 선택</span>
            </div>

            {/* File List from data_sample */}
            <div className="border rounded divide-y max-h-96 overflow-y-auto">
              {files.length === 0 ? (
                <div className="p-4 text-gray-500 text-center">
                  data_sample 폴더에 xlsx 파일이 없습니다.
                </div>
              ) : (
                files.map((file) => (
                  <div
                    key={file.path}
                    className={`p-3 cursor-pointer hover:bg-gray-50 ${
                      selectedFile?.path === file.path ? 'bg-blue-50' : ''
                    }`}
                    onClick={() => handleAnalyzePath(file)}
                  >
                    <div className="font-medium">{file.filename}</div>
                    <div className="text-sm text-gray-500 flex gap-4">
                      <span>{formatBytes(file.size)}</span>
                      {file.slip_type_guess && (
                        <span className="text-blue-600">
                          {SLIP_TYPE_LABELS[file.slip_type_guess] || file.slip_type_guess} 전표 (추정)
                        </span>
                      )}
                    </div>
                  </div>
                ))
              )}
            </div>

            <button
              onClick={loadFiles}
              className="mt-4 text-sm text-blue-600 hover:underline"
            >
              목록 새로고침
            </button>
          </div>

          {/* Right: Analysis Result */}
          <div className="bg-white rounded-lg shadow p-4">
            <h2 className="text-lg font-semibold mb-4">분석 결과</h2>

            {loading && (
              <div className="text-center py-8 text-gray-500">분석 중...</div>
            )}

            {!loading && !analysis && (
              <div className="text-center py-8 text-gray-500">
                파일을 선택하면 분석 결과가 표시됩니다.
              </div>
            )}

            {analysis && (
              <div className="space-y-4">
                {/* Basic Info */}
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700">전표 유형</label>
                    <div className="mt-1 p-2 bg-gray-100 rounded">
                      {SLIP_TYPE_LABELS[analysis.slip_type] || analysis.slip_type}
                    </div>
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700">데이터 행수</label>
                    <div className="mt-1 p-2 bg-gray-100 rounded">
                      {analysis.row_count}행
                    </div>
                  </div>
                </div>

                {/* Fixed Values */}
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    고정값 ({Object.keys(analysis.fixed_values).length}개)
                  </label>
                  <div className="max-h-32 overflow-y-auto border rounded p-2 text-sm font-mono">
                    {Object.entries(analysis.fixed_values).map(([key, value]) => (
                      <div key={key} className="flex gap-2">
                        <span className="text-blue-600">{key}:</span>
                        <span>{String(value)}</span>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Account Mappings */}
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">계정 매핑</label>
                  <div className="grid grid-cols-2 gap-2 text-sm">
                    <div className="border rounded p-2">
                      <div className="font-medium mb-1">국내 (domestic)</div>
                      {Object.entries(analysis.account_mappings.domestic || {}).map(([key, value]) => (
                        <div key={key} className="text-gray-600">
                          {key}: {value}
                        </div>
                      ))}
                    </div>
                    <div className="border rounded p-2">
                      <div className="font-medium mb-1">해외 (overseas)</div>
                      {Object.entries(analysis.account_mappings.overseas || {}).map(([key, value]) => (
                        <div key={key} className="text-gray-600">
                          {key}: {value}
                        </div>
                      ))}
                    </div>
                  </div>
                </div>

                {/* Save */}
                <div className="border-t pt-4 mt-4">
                  <label className="block text-sm font-medium text-gray-700 mb-2">템플릿명</label>
                  <input
                    type="text"
                    value={templateName}
                    onChange={(e) => setTemplateName(e.target.value)}
                    className="w-full border rounded px-3 py-2 mb-4"
                    placeholder="템플릿 이름 입력"
                  />
                  <button
                    onClick={handleImport}
                    disabled={loading}
                    className="w-full px-4 py-2 bg-green-600 text-white rounded hover:bg-green-700 disabled:opacity-50"
                  >
                    템플릿으로 저장
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* 프로필 추출 탭 */}
      {activeTab === 'profiles' && (
        <div className="grid grid-cols-3 gap-6">
          {/* Left: File List */}
          <div className="bg-white rounded-lg shadow p-4">
            <h2 className="text-lg font-semibold mb-4">전표 파일 선택</h2>

            <div className="border rounded divide-y max-h-[600px] overflow-y-auto">
              {files.length === 0 ? (
                <div className="p-4 text-gray-500 text-center">
                  data_sample 폴더에 xlsx 파일이 없습니다.
                </div>
              ) : (
                files.map((file) => (
                  <div
                    key={file.path}
                    className="p-3 cursor-pointer hover:bg-gray-50"
                    onClick={() => handleExtractProfiles(file)}
                  >
                    <div className="font-medium text-sm">{file.filename}</div>
                    <div className="text-xs text-gray-500">
                      {file.slip_type_guess && (
                        <span className="text-blue-600">
                          {SLIP_TYPE_LABELS[file.slip_type_guess]}
                        </span>
                      )}
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>

          {/* Right: Profile List */}
          <div className="col-span-2 bg-white rounded-lg shadow p-4">
            <h2 className="text-lg font-semibold mb-4">추출된 프로필</h2>

            {loading && (
              <div className="text-center py-8 text-gray-500">추출 중...</div>
            )}

            {!loading && !profileResult && (
              <div className="text-center py-8 text-gray-500">
                파일을 선택하면 BP별 프로필 정보가 추출됩니다.
              </div>
            )}

            {profileResult && (
              <div className="space-y-4">
                {/* Summary */}
                <div className="flex items-center gap-4 text-sm">
                  <span className="font-medium">{profileResult.source_file}</span>
                  <span className="text-gray-500">|</span>
                  <span>{SLIP_TYPE_LABELS[profileResult.slip_type]} 전표</span>
                  <span className="text-gray-500">|</span>
                  <span>{profileResult.total_rows}행</span>
                  <span className="text-gray-500">|</span>
                  <span className="text-green-600">{profileResult.matched_count}개 매칭</span>
                  <span className="text-gray-500">|</span>
                  <span className="text-orange-600">{profileResult.unmatched_count}개 미매칭</span>
                </div>

                {/* Selection Controls */}
                <div className="flex items-center gap-4 border-b pb-4">
                  <button
                    onClick={() => handleSelectAllProfiles(true)}
                    className="text-sm text-blue-600 hover:underline"
                  >
                    매칭된 항목 전체 선택
                  </button>
                  <button
                    onClick={() => setSelectedProfiles(new Set())}
                    className="text-sm text-gray-600 hover:underline"
                  >
                    선택 해제
                  </button>
                  <div className="flex-1" />
                  <label className="flex items-center gap-2 text-sm">
                    <input
                      type="checkbox"
                      checked={overwriteProfiles}
                      onChange={(e) => setOverwriteProfiles(e.target.checked)}
                    />
                    기존 프로필 덮어쓰기
                  </label>
                  <button
                    onClick={handleApplyProfiles}
                    disabled={selectedProfiles.size === 0 || loading}
                    className="px-4 py-2 bg-green-600 text-white rounded hover:bg-green-700 disabled:opacity-50"
                  >
                    선택 항목 적용 ({selectedProfiles.size}개)
                  </button>
                </div>

                {/* Profile Table */}
                <div className="max-h-[450px] overflow-y-auto">
                  <table className="w-full text-sm">
                    <thead className="bg-gray-100 sticky top-0">
                      <tr>
                        <th className="px-2 py-2 text-left w-8"></th>
                        <th className="px-2 py-2 text-left">BP</th>
                        <th className="px-2 py-2 text-left">사업자번호</th>
                        <th className="px-2 py-2 text-left">거래처명</th>
                        <th className="px-2 py-2 text-left">통화</th>
                        <th className="px-2 py-2 text-left">채권</th>
                        <th className="px-2 py-2 text-left">매출</th>
                        <th className="px-2 py-2 text-left">매입</th>
                        <th className="px-2 py-2 text-left">세금</th>
                        <th className="px-2 py-2 text-right">건수</th>
                        <th className="px-2 py-2 text-left">HB 매칭</th>
                      </tr>
                    </thead>
                    <tbody>
                      {profileResult.profiles.map((profile) => (
                        <tr
                          key={profile.bp_number}
                          className={`border-t hover:bg-gray-50 ${
                            !profile.hb_company_seq ? 'opacity-50' : ''
                          }`}
                        >
                          <td className="px-2 py-2">
                            <input
                              type="checkbox"
                              checked={selectedProfiles.has(profile.bp_number)}
                              onChange={() => handleToggleProfileSelect(profile.bp_number)}
                              disabled={!profile.hb_company_seq}
                            />
                          </td>
                          <td className="px-2 py-2 font-mono">{profile.bp_number}</td>
                          <td className="px-2 py-2 font-mono text-xs">{profile.tax_number || '-'}</td>
                          <td className="px-2 py-2 truncate max-w-[120px]" title={profile.company_name || ''}>
                            {profile.company_name || '-'}
                          </td>
                          <td className="px-2 py-2">
                            <span className={profile.is_overseas ? 'text-blue-600' : ''}>
                              {profile.currency}
                            </span>
                          </td>
                          <td className="px-2 py-2 font-mono text-xs">{profile.ar_account || '-'}</td>
                          <td className="px-2 py-2 font-mono text-xs">{profile.hkont_sales || '-'}</td>
                          <td className="px-2 py-2 font-mono text-xs">{profile.hkont_purchase || '-'}</td>
                          <td className="px-2 py-2">{profile.tax_code || '-'}</td>
                          <td className="px-2 py-2 text-right">{profile.row_count}</td>
                          <td className="px-2 py-2">
                            {profile.hb_company_seq ? (
                              <span className="text-green-600 text-xs" title={profile.hb_company_name || ''}>
                                {profile.existing_profile_id ? '(기존)' : ''} {profile.hb_company_name?.slice(0, 10)}
                              </span>
                            ) : (
                              <span className="text-orange-500 text-xs">미매칭</span>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* 저장된 템플릿 탭 */}
      {activeTab === 'templates' && (
        <div className="grid grid-cols-2 gap-6">
          {/* Left: Template List */}
          <div className="bg-white rounded-lg shadow p-4">
            <h2 className="text-lg font-semibold mb-4">저장된 템플릿</h2>

            <div className="border rounded divide-y">
              {templates.length === 0 ? (
                <div className="p-4 text-gray-500 text-center">
                  저장된 템플릿이 없습니다.
                </div>
              ) : (
                templates.map((template) => (
                  <div
                    key={template.id}
                    className={`p-3 cursor-pointer hover:bg-gray-50 ${
                      selectedTemplate?.id === template.id ? 'bg-blue-50' : ''
                    }`}
                    onClick={() => setSelectedTemplate(template)}
                  >
                    <div className="flex justify-between items-start">
                      <div>
                        <div className="font-medium">{template.name}</div>
                        <div className="text-sm text-gray-500">
                          {SLIP_TYPE_LABELS[template.slip_type] || template.slip_type} 전표
                          {template.source_file && (
                            <span className="ml-2 text-gray-400">({template.source_file})</span>
                          )}
                        </div>
                      </div>
                      <div className="flex items-center gap-2">
                        <span
                          className={`px-2 py-0.5 text-xs rounded ${
                            template.is_active
                              ? 'bg-green-100 text-green-800'
                              : 'bg-gray-100 text-gray-600'
                          }`}
                        >
                          {template.is_active ? '활성' : '비활성'}
                        </span>
                      </div>
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>

          {/* Right: Template Detail */}
          <div className="bg-white rounded-lg shadow p-4">
            <h2 className="text-lg font-semibold mb-4">템플릿 상세</h2>

            {!selectedTemplate ? (
              <div className="text-center py-8 text-gray-500">
                템플릿을 선택하면 상세 정보가 표시됩니다.
              </div>
            ) : (
              <div className="space-y-4">
                <div className="flex justify-between items-center">
                  <h3 className="text-xl font-medium">{selectedTemplate.name}</h3>
                  <div className="flex gap-2">
                    <button
                      onClick={() => handleToggleActive(selectedTemplate)}
                      className={`px-3 py-1 text-sm rounded ${
                        selectedTemplate.is_active
                          ? 'bg-gray-200 text-gray-700 hover:bg-gray-300'
                          : 'bg-green-600 text-white hover:bg-green-700'
                      }`}
                    >
                      {selectedTemplate.is_active ? '비활성화' : '활성화'}
                    </button>
                    <button
                      onClick={() => handleDeleteTemplate(selectedTemplate.id)}
                      className="px-3 py-1 text-sm bg-red-600 text-white rounded hover:bg-red-700"
                    >
                      삭제
                    </button>
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-4 text-sm">
                  <div>
                    <span className="text-gray-500">전표 유형:</span>{' '}
                    {SLIP_TYPE_LABELS[selectedTemplate.slip_type] || selectedTemplate.slip_type}
                  </div>
                  <div>
                    <span className="text-gray-500">컬럼 수:</span>{' '}
                    {selectedTemplate.columns.length}개
                  </div>
                </div>

                {/* Fixed Values */}
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">고정값</label>
                  <div className="max-h-40 overflow-y-auto border rounded p-2 text-sm font-mono bg-gray-50">
                    {Object.entries(selectedTemplate.fixed_values).map(([key, value]) => (
                      <div key={key}>
                        <span className="text-blue-600">{key}:</span> {String(value)}
                      </div>
                    ))}
                  </div>
                </div>

                {/* Account Mappings */}
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">계정 매핑</label>
                  <div className="grid grid-cols-2 gap-2 text-sm">
                    <div className="border rounded p-2 bg-gray-50">
                      <div className="font-medium mb-1">국내</div>
                      {Object.entries(selectedTemplate.account_mappings.domestic || {}).map(([key, value]) => (
                        <div key={key}>{key}: {value}</div>
                      ))}
                    </div>
                    <div className="border rounded p-2 bg-gray-50">
                      <div className="font-medium mb-1">해외</div>
                      {Object.entries(selectedTemplate.account_mappings.overseas || {}).map(([key, value]) => (
                        <div key={key}>{key}: {value}</div>
                      ))}
                    </div>
                  </div>
                </div>

                {/* Columns */}
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">컬럼 구성</label>
                  <div className="max-h-48 overflow-y-auto border rounded text-sm">
                    <table className="w-full">
                      <thead className="bg-gray-100 sticky top-0">
                        <tr>
                          <th className="px-2 py-1 text-left">#</th>
                          <th className="px-2 py-1 text-left">필드</th>
                          <th className="px-2 py-1 text-left">헤더</th>
                          <th className="px-2 py-1 text-left">타입</th>
                        </tr>
                      </thead>
                      <tbody>
                        {selectedTemplate.columns.map((col) => (
                          <tr key={col.index} className="border-t">
                            <td className="px-2 py-1 text-gray-400">{col.index}</td>
                            <td className="px-2 py-1 font-mono">{col.name}</td>
                            <td className="px-2 py-1 text-gray-600 truncate max-w-xs">{col.header}</td>
                            <td className="px-2 py-1 text-gray-500">{col.data_type}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
