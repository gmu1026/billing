import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { slipApi } from '../api/client';
import { Card, Badge, Spinner } from '../components/ui';
import type { SlipBatch } from '../types';

export default function Dashboard() {
  const { data: batches, isLoading: batchesLoading } = useQuery({
    queryKey: ['slipBatches'],
    queryFn: () => slipApi.getBatches().then((res) => res.data as SlipBatch[]),
  });

  const { data: latestRate } = useQuery({
    queryKey: ['latestRate'],
    queryFn: () => slipApi.getLatestRate().then((res) => res.data),
  });

  const prevMonth = (() => {
    const d = new Date();
    d.setMonth(d.getMonth() - 1);
    return d.toISOString().slice(0, 7).replace('-', '');
  })();

  return (
    <div className="space-y-6">
      <h2 className="text-2xl font-bold text-gray-800">대시보드</h2>

      {/* Quick Stats */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card className="!p-4">
          <div className="text-sm text-gray-500">현재 월</div>
          <div className="text-2xl font-bold text-gray-800">{prevMonth}</div>
        </Card>
        <Card className="!p-4">
          <div className="text-sm text-gray-500">최신 환율 (USD/KRW)</div>
          <div className="text-2xl font-bold text-gray-800">
            {latestRate?.found ? `₩${latestRate.rate.toLocaleString()}` : '-'}
          </div>
          {latestRate?.rate_date && (
            <div className="text-xs text-gray-400">{latestRate.rate_date}</div>
          )}
        </Card>
        <Card className="!p-4">
          <div className="text-sm text-gray-500">전표 배치 수</div>
          <div className="text-2xl font-bold text-gray-800">{batches?.length || 0}</div>
        </Card>
        <Card className="!p-4">
          <div className="text-sm text-gray-500">바로가기</div>
          <div className="flex gap-2 mt-1">
            <Link
              to="/slip"
              className="text-sm text-blue-600 hover:underline"
            >
              전표 생성 →
            </Link>
          </div>
        </Card>
      </div>

      {/* Recent Batches */}
      <Card title="최근 전표 배치">
        {batchesLoading ? (
          <div className="flex justify-center py-8">
            <Spinner />
          </div>
        ) : batches && batches.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b">
                  <th className="px-4 py-3 text-left font-medium text-gray-600">배치 ID</th>
                  <th className="px-4 py-3 text-left font-medium text-gray-600">정산월</th>
                  <th className="px-4 py-3 text-left font-medium text-gray-600">유형</th>
                  <th className="px-4 py-3 text-right font-medium text-gray-600">건수</th>
                  <th className="px-4 py-3 text-right font-medium text-gray-600">합계 (KRW)</th>
                  <th className="px-4 py-3 text-left font-medium text-gray-600">생성일</th>
                  <th className="px-4 py-3 text-left font-medium text-gray-600"></th>
                </tr>
              </thead>
              <tbody>
                {batches.slice(0, 10).map((batch) => (
                  <tr key={batch.batch_id} className="border-b border-gray-100 hover:bg-gray-50">
                    <td className="px-4 py-3 font-mono text-xs">{batch.batch_id}</td>
                    <td className="px-4 py-3">{batch.billing_cycle}</td>
                    <td className="px-4 py-3">
                      <Badge variant={batch.slip_type === 'sales' ? 'success' : 'warning'}>
                        {batch.slip_type === 'sales' ? '매출' : '매입'}
                      </Badge>
                    </td>
                    <td className="px-4 py-3 text-right">{batch.count}</td>
                    <td className="px-4 py-3 text-right font-medium">
                      ₩{batch.total_krw.toLocaleString()}
                    </td>
                    <td className="px-4 py-3 text-gray-500">
                      {batch.created_at ? new Date(batch.created_at).toLocaleDateString() : '-'}
                    </td>
                    <td className="px-4 py-3">
                      <Link
                        to={`/slip?batch_id=${batch.batch_id}`}
                        className="text-blue-600 hover:underline text-xs"
                      >
                        상세
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="text-center py-8 text-gray-500">
            생성된 전표가 없습니다.
            <Link to="/slip" className="text-blue-600 hover:underline ml-2">
              전표 생성하기 →
            </Link>
          </div>
        )}
      </Card>

      {/* Quick Actions */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <Card title="빌링 데이터 업로드">
          <p className="text-sm text-gray-600 mb-4">
            알리바바 클라우드 빌링 CSV 파일을 업로드합니다.
          </p>
          <Link to="/billing">
            <button className="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm hover:bg-blue-700">
              업로드 페이지로 →
            </button>
          </Link>
        </Card>

        <Card title="HB 데이터 관리">
          <p className="text-sm text-gray-600 mb-4">
            회사, 계약, 계정 정보를 관리하고 BP 코드를 매핑합니다.
          </p>
          <Link to="/hb">
            <button className="px-4 py-2 bg-gray-100 text-gray-700 rounded-lg text-sm hover:bg-gray-200">
              HB 연동 페이지로 →
            </button>
          </Link>
        </Card>
      </div>
    </div>
  );
}
