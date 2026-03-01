import { Bell, Settings as SettingsIcon } from 'lucide-react';

export default function TopBar() {
  return (
    <div className="h-16 bg-white border-b border-gray-200 flex items-center justify-between px-6">
      <div className="flex items-center gap-4">
        <h1 className="text-xl font-semibold text-gray-900">Chat</h1>
      </div>

      <div className="flex items-center gap-3">
        <button className="relative inline-flex items-center justify-center w-9 h-9 rounded-lg hover:bg-gray-50">
          <Bell className="w-5 h-5 text-gray-600" />
          <span className="absolute top-2 right-2 w-2 h-2 bg-red-500 rounded-full" />
        </button>
        <button className="inline-flex items-center justify-center w-9 h-9 rounded-lg hover:bg-gray-50">
          <SettingsIcon className="w-5 h-5 text-gray-600" />
        </button>

        <div className="w-px h-6 bg-gray-200" />

        <div className="flex items-center gap-2 cursor-pointer hover:opacity-80 transition-opacity">
          <div className="w-8 h-8 rounded-full bg-primary-100 text-primary-700 flex items-center justify-center text-sm font-medium">
            BJ
          </div>
          <span className="text-sm text-gray-700">Boeing New Hire</span>
        </div>
      </div>
    </div>
  );
}