// src/components/dashboard/Sidebar.jsx
import { useState } from 'react';
import { NavLink } from 'react-router-dom';
import {
  MessageSquare,
  Flag,
  BarChart3,
  Settings,
  ChevronLeft,
  ChevronRight,
  Plus,
} from 'lucide-react';

const navItems = [
  { icon: MessageSquare, label: 'Chat', to: '/dashboard/chat' },
  { icon: Flag, label: 'Flagged Outputs', to: '/dashboard/flagged' },
  { icon: BarChart3, label: 'Analytics', to: '/dashboard/analytics' },
  { icon: Settings, label: 'Settings', to: '/dashboard/settings' },
];

const historyItems = [
  { id: '1', title: '737 MAX vs 787 overview', timestamp: '2 hours ago' },
  { id: '2', title: 'Fuel burn normalization', timestamp: '5 hours ago' },
  { id: '3', title: 'Range vs payload tradeoffs', timestamp: 'Yesterday' },
  { id: '4', title: 'ETOPS basics', timestamp: '2 days ago' },
  { id: '5', title: 'Wing loading & efficiency', timestamp: '3 days ago' },
];

export default function Sidebar() {
  const [collapsed, setCollapsed] = useState(false);

  return (
    <div
      className={[
        'relative bg-white border-r border-gray-200 flex flex-col transition-all duration-300',
        collapsed ? 'w-16' : 'w-64',
      ].join(' ')}
    >
      {/* Header */}
      <div className="h-16 flex items-center px-4 border-b border-gray-200">
        {!collapsed ? (
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-lg bg-primary-600 flex items-center justify-center">
              <span className="text-white font-semibold text-sm">TM</span>
            </div>
            <span className="font-semibold text-gray-900">Trust Metrics</span>
          </div>
        ) : (
          <div className="w-8 h-8 rounded-lg bg-primary-600 flex items-center justify-center mx-auto">
            <span className="text-white font-semibold text-sm">TM</span>
          </div>
        )}
      </div>

      {/* New Analysis */}
      <div className="p-3">
        <NavLink
          to="/dashboard/chat"
          className={[
            'w-full inline-flex items-center rounded-lg bg-primary-600 hover:bg-primary-700 text-white shadow-sm transition-all h-10',
            collapsed ? 'justify-center px-0' : 'justify-start px-4',
          ].join(' ')}
        >
          <Plus className={`w-4 h-4 ${collapsed ? '' : 'mr-2'}`} />
          {!collapsed && 'New Analysis'}
        </NavLink>
      </div>

      {/* Navigation */}
      <nav className="px-3 space-y-1">
        {navItems.map((item) => (
          <NavLink
            key={item.label}
            to={item.to}
            className={({ isActive }) =>
              [
                'w-full flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition-colors',
                isActive
                  ? 'bg-primary-50 text-primary-700 font-medium'
                  : 'text-gray-700 hover:bg-gray-50',
              ].join(' ')
            }
          >
            <item.icon className="w-5 h-5 flex-shrink-0" />
            {!collapsed && <span>{item.label}</span>}
          </NavLink>
        ))}
      </nav>

      {!collapsed && (
        <>
          <div className="my-3 border-t border-gray-200" />

          {/* History */}
          <div className="flex-1 overflow-hidden flex flex-col px-3">
            <div className="px-3 py-2">
              <span className="text-xs font-medium text-gray-500 uppercase tracking-wide">
                Conversations
              </span>
            </div>

            <div className="flex-1 overflow-auto pr-2 pb-4">
              <div className="space-y-1">
                {historyItems.map((item) => (
                  <button
                    key={item.id}
                    className="w-full text-left px-3 py-2 rounded-lg hover:bg-gray-50 transition-colors"
                  >
                    <div className="text-sm text-gray-900 truncate">{item.title}</div>
                    <div className="text-xs text-gray-500 mt-0.5">{item.timestamp}</div>
                  </button>
                ))}
              </div>
            </div>
          </div>
        </>
      )}

      {/* Collapse Toggle */}
      <button
        onClick={() => setCollapsed(!collapsed)}
        className="absolute -right-3 top-20 w-6 h-6 rounded-full bg-white border border-gray-200 shadow-sm flex items-center justify-center hover:bg-gray-50 transition-colors"
        aria-label="Toggle sidebar"
      >
        {collapsed ? (
          <ChevronRight className="w-4 h-4 text-gray-600" />
        ) : (
          <ChevronLeft className="w-4 h-4 text-gray-600" />
        )}
      </button>
    </div>
  );
}