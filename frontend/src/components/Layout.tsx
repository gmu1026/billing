import { useState } from 'react';
import { Link, useLocation } from 'react-router-dom';

const navItems = [
  { path: '/', label: '대시보드', icon: '📊' },
  { path: '/import', label: '파일 임포트', icon: '📥' },
  { path: '/billing', label: '빌링 데이터', icon: '📁' },
  { path: '/hb', label: 'HB 연동', icon: '🔗' },
  { path: '/slip', label: '전표 생성', icon: '📝' },
  { path: '/billing-profile', label: '청구/예치금', icon: '💰' },
  { path: '/master', label: '마스터 데이터', icon: '⚙️' },
];

export default function Layout({ children }: { children: React.ReactNode }) {
  const location = useLocation();
  const [sidebarOpen, setSidebarOpen] = useState(true);

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white border-b border-gray-200 fixed top-0 left-0 right-0 z-10">
        <div className="flex items-center justify-between px-4 h-14">
          <div className="flex items-center gap-4">
            <button
              onClick={() => setSidebarOpen(!sidebarOpen)}
              className="p-2 hover:bg-gray-100 rounded-lg"
            >
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
              </svg>
            </button>
            <h1 className="text-lg font-semibold text-gray-800">전표 자동화 시스템</h1>
          </div>
          <div className="text-sm text-gray-500">Alibaba Cloud Billing</div>
        </div>
      </header>

      {/* Sidebar */}
      <aside
        className={`fixed top-14 left-0 bottom-0 bg-white border-r border-gray-200 transition-all duration-200 z-10 ${
          sidebarOpen ? 'w-52' : 'w-0 overflow-hidden'
        }`}
      >
        <nav className="p-2">
          {navItems.map((item) => (
            <Link
              key={item.path}
              to={item.path}
              className={`flex items-center gap-3 px-3 py-2.5 rounded-lg mb-1 text-sm transition-colors ${
                location.pathname === item.path
                  ? 'bg-blue-50 text-blue-700 font-medium'
                  : 'text-gray-600 hover:bg-gray-100'
              }`}
            >
              <span>{item.icon}</span>
              <span>{item.label}</span>
            </Link>
          ))}
        </nav>
      </aside>

      {/* Main Content */}
      <main
        className={`pt-14 transition-all duration-200 ${sidebarOpen ? 'ml-52' : 'ml-0'}`}
      >
        <div className="p-6">{children}</div>
      </main>
    </div>
  );
}
