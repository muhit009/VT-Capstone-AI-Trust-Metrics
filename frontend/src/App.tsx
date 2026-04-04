import { Routes, Route, Navigate } from 'react-router-dom';
import Layout from '@/components/layout/Layout';
import Home from '@/pages/Home';

import AnalystChat from '@/pages/AnalystChat';
import FlaggedOutputs from '@/pages/FlaggedOutputs';
import Analytics from '@/pages/Analytics';
import Settings from '@/pages/Settings';

function App() {
  return (
    <Routes>
      <Route path="/" element={<Layout />}>
        <Route index element={<Home />} />
      </Route>

      <Route path="/dashboard" element={<Navigate to="/dashboard/chat" replace />} />

      <Route path="/dashboard/chat" element={<AnalystChat />} />
      <Route path="/dashboard/flagged" element={<FlaggedOutputs />} />
      <Route path="/dashboard/analytics" element={<Analytics />} />
      <Route path="/dashboard/settings" element={<Settings />} />
    </Routes>
  );
}

export default App;