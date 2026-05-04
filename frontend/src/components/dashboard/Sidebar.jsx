import { useEffect, useState } from 'react';
import {
  MessageSquare,
  ChartColumn,
  FileText,
  Settings,
  ChevronLeft,
  ChevronRight,
  Plus,
} from 'lucide-react';
import { useLocation, useNavigate } from 'react-router-dom';
import boeingLogo from '@/assets/boeinglogo.png';
import {
  QUERY_HISTORY_UPDATED_EVENT,
  readSavedQueryHistory,
} from '@/services/queryHistory';

const navItems = [
  { id: 'chat', label: 'Chat', icon: MessageSquare, to: '/dashboard/chat' },
  { id: 'analytics', label: 'Analytics', icon: ChartColumn, to: '/dashboard/analytics' },
  { id: 'documents', label: 'Documents', icon: FileText, to: '/dashboard/documents' },
  { id: 'settings', label: 'Settings', icon: Settings, to: '/dashboard/settings' },
];

function formatRelativeTime(timestamp) {
  const parsed = new Date(timestamp);
  if (Number.isNaN(parsed.getTime())) return 'Recently';

  const diffMs = Date.now() - parsed.getTime();
  const diffMinutes = Math.max(0, Math.floor(diffMs / (1000 * 60)));

  if (diffMinutes < 1) return 'Just now';
  if (diffMinutes < 60) return `${diffMinutes} minute${diffMinutes === 1 ? '' : 's'} ago`;

  const diffHours = Math.floor(diffMinutes / 60);
  if (diffHours < 24) return `${diffHours} hour${diffHours === 1 ? '' : 's'} ago`;

  const diffDays = Math.floor(diffHours / 24);
  if (diffDays === 1) return 'Yesterday';
  if (diffDays < 7) return `${diffDays} days ago`;

  return parsed.toLocaleDateString();
}

function toConversationItems(history) {
  return history.map((entry) => ({
    id: entry.queryId,
    title: entry.query,
    time: formatRelativeTime(entry.timestamp),
  }));
}

export default function Sidebar() {
  const [collapsed, setCollapsed] = useState(false);
  const [savedConversations, setSavedConversations] = useState(() =>
    toConversationItems(readSavedQueryHistory()),
  );
  const location = useLocation();
  const navigate = useNavigate();

  useEffect(() => {
    const refreshHistory = () => {
      setSavedConversations(toConversationItems(readSavedQueryHistory()));
    };

    refreshHistory();
    window.addEventListener(QUERY_HISTORY_UPDATED_EVENT, refreshHistory);

    return () => {
      window.removeEventListener(QUERY_HISTORY_UPDATED_EVENT, refreshHistory);
    };
  }, []);

  return (
    <aside
      className={[
        'hidden h-full shrink-0 border-r border-gray-200 bg-white xl:flex xl:flex-col transition-all duration-200',
        collapsed ? 'w-24' : 'w-[320px]',
      ].join(' ')}
    >
      {!collapsed ? (
        <div className="border-b border-gray-200 p-5">
          <div className="flex items-start justify-between gap-4">
            <div className="flex min-w-0 items-start gap-4">
              <div className="mt-0.5 flex h-14 w-14 shrink-0 items-center justify-center bg-transparent">
                <img
                  src={boeingLogo}
                  alt="Boeing logo"
                  className="h-12 w-12 object-contain"
                />
              </div>

              <div className="min-w-0">
                <div className="text-[18px] font-semibold leading-7 text-gray-900">
                  Boeing Aircraft Assistant
                </div>
                <div className="text-sm text-gray-500">New-hire Q&A workspace</div>
              </div>
            </div>

            <button
              type="button"
              onClick={() => setCollapsed(true)}
              className="shrink-0 rounded-xl border border-gray-200 p-2 text-gray-600 hover:bg-gray-50"
              aria-label="Collapse sidebar"
            >
              <ChevronLeft className="h-4 w-4" />
            </button>
          </div>
        </div>
      ) : (
        <div className="border-b border-gray-200 py-5">
          <div className="flex flex-col items-center justify-center gap-5">
            <div className="flex w-full justify-center">
              <img
                src={boeingLogo}
                alt="Boeing logo"
                className="block h-16 w-16 object-contain"
              />
            </div>

            <button
              type="button"
              onClick={() => setCollapsed(false)}
              className="flex h-14 w-14 items-center justify-center rounded-2xl border border-gray-200 text-gray-600 hover:bg-gray-50"
              aria-label="Expand sidebar"
            >
              <ChevronRight className="h-5 w-5" />
            </button>
          </div>
        </div>
      )}

      <div className="p-4">
        <button
          type="button"
          onClick={() => navigate('/dashboard/chat')}
          className={[
            'flex items-center justify-center gap-2 rounded-xl bg-primary-600 text-sm font-medium text-white hover:bg-primary-700',
            collapsed ? 'h-16 w-full' : 'w-full px-4 py-3',
          ].join(' ')}
        >
          <Plus className="h-4 w-4" />
          {!collapsed ? 'New Analysis' : null}
        </button>
      </div>

      <div className="px-3">
        <nav className="space-y-1">
          {navItems.map((item) => {
            const Icon = item.icon;
            const isActive = location.pathname === item.to;

            return (
              <button
                key={item.id}
                type="button"
                onClick={() => navigate(item.to)}
                className={[
                  'flex w-full items-center rounded-xl text-sm transition',
                  collapsed ? 'justify-center px-0 py-4' : 'gap-3 px-3 py-3',
                  isActive
                    ? 'bg-primary-50 text-primary-700'
                    : 'text-gray-700 hover:bg-gray-50',
                ].join(' ')}
              >
                <Icon className="h-5 w-5 shrink-0" />
                {!collapsed ? <span>{item.label}</span> : null}
              </button>
            );
          })}
        </nav>
      </div>

      {!collapsed ? (
        <div className="mt-4 flex min-h-0 flex-1 flex-col border-t border-gray-200 px-4 py-5">
          <div className="mb-3 text-xs font-semibold uppercase tracking-[0.15em] text-gray-500">
            Conversations
          </div>

          {savedConversations.length ? (
            <div className="space-y-1 overflow-auto pr-1">
              {savedConversations.map((conversation) => (
                <button
                  key={conversation.id}
                  type="button"
                  onClick={() => navigate('/dashboard/chat')}
                  className="w-full rounded-xl px-3 py-3 text-left hover:bg-gray-50"
                >
                  <div className="truncate text-sm font-medium text-gray-800">
                    {conversation.title}
                  </div>
                  <div className="mt-1 text-xs text-gray-500">{conversation.time}</div>
                </button>
              ))}
            </div>
          ) : (
            <div className="rounded-2xl border border-dashed border-gray-300 bg-gray-50 px-4 py-5 text-sm text-gray-600">
              Conversation history is not available yet. Start a chat to begin building
              history.
            </div>
          )}
        </div>
      ) : null}
    </aside>
  );
}
