import { Routes, Route, Navigate } from 'react-router-dom';
import Layout from '@/components/layout/Layout';
import DashboardLayout from '@/components/dashboard/DashboardLayout';
import Home from '@/pages/Home';

import AnalystChat from '@/pages/AnalystChat';
import FlaggedOutputs from '@/pages/FlaggedOutputs';
import Analytics from '@/pages/Analytics';
import Documents from '@/pages/Documents';
import Settings from '@/pages/Settings';

function App() {
  return (
    <Routes>
      <Route path="/" element={<Layout />}>
        <Route index element={<Home />} />
      </Route>

      <Route path="/dashboard" element={<DashboardLayout />}>
        <Route index element={<Navigate to="/dashboard/chat" replace />} />
        <Route path="chat" element={<AnalystChat />} />
        <Route path="flagged" element={<FlaggedOutputs />} />
        <Route path="analytics" element={<Analytics />} />
        <Route path="documents" element={<Documents />} />
        <Route path="settings" element={<Settings />} />
      </Route>
    </Routes>
  );
}

export default App;
