import { Outlet, useLocation } from 'react-router-dom';
import Sidebar from '@/components/dashboard/Sidebar';
import TopBar from '@/components/dashboard/TopBar';

const viewMeta: Record<string, { title: string; description: string }> = {
  '/dashboard/chat': {
    title: 'Aircraft Q&A',
    description:
      'Grounded answers for Boeing new hires learning airplane concepts and comparisons.',
  },
  '/dashboard/analytics': {
    title: 'Confidence Analytics',
    description:
      'Confidence trends and recent saved responses based on your locally saved query history.',
  },
  '/dashboard/documents': {
    title: 'Document Management',
    description:
      'View, upload, refresh, and delete the source documents available to the retrieval pipeline.',
  },
  '/dashboard/settings': {
    title: 'Workspace Settings',
    description:
      'Configure assistant behavior, evidence display, and confidence settings for this workspace.',
  },
  '/dashboard/flagged': {
    title: 'Flagged Outputs',
    description:
      'Review low-confidence or policy-sensitive responses that may need analyst attention.',
  },
};

function getViewMeta(pathname: string) {
  return viewMeta[pathname] ?? viewMeta['/dashboard/chat'];
}

export default function DashboardLayout() {
  const location = useLocation();
  const { title, description } = getViewMeta(location.pathname);

  return (
    <div className="flex h-screen w-screen overflow-hidden bg-gray-50">
      <Sidebar />

      <div className="flex min-w-0 flex-1 flex-col">
        <TopBar title={title} description={description} />
        <Outlet />
      </div>
    </div>
  );
}
