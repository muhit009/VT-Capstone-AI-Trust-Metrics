import Sidebar from '@/components/dashboard/Sidebar';
import TopBar from '@/components/dashboard/TopBar';
import ChatInterface from '@/components/dashboard/ChatInterface';
import RightPanel from '@/components/dashboard/RightPanel';

export default function AnalystChat() {
  return (
    <div className="h-screen w-screen overflow-hidden bg-gray-50 flex">
      <Sidebar />

      <div className="flex-1 min-w-0 flex flex-col">
        <TopBar />

        <div className="flex-1 min-h-0 flex">
          <ChatInterface />
          <RightPanel />
        </div>
      </div>
    </div>
  );
}