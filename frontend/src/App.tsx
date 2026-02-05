import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import Layout from './components/Layout';
import Dashboard from './pages/Dashboard';
import Import from './pages/Import';
import Billing from './pages/Billing';
import HB from './pages/HB';
import Slip from './pages/Slip';
import SlipTemplate from './pages/SlipTemplate';
import Master from './pages/Master';
import BillingProfile from './pages/BillingProfile';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 1000 * 60, // 1 minute
      retry: 1,
    },
  },
});

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Layout>
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/import" element={<Import />} />
            <Route path="/billing" element={<Billing />} />
            <Route path="/hb" element={<HB />} />
            <Route path="/slip" element={<Slip />} />
            <Route path="/slip-template" element={<SlipTemplate />} />
            <Route path="/master" element={<Master />} />
            <Route path="/billing-profile" element={<BillingProfile />} />
          </Routes>
        </Layout>
      </BrowserRouter>
    </QueryClientProvider>
  );
}
