// src/components/dashboard/RightPanel.jsx
import { useMemo, useState } from 'react';
import {
  TrendingUp,
  Search,
  FileText,
  Globe,
  Building2,
  ExternalLink,
  Pin,
  Plus,
  ChevronLeft,
  ChevronRight,
} from 'lucide-react';

const signals = [
  { name: 'Evidence Coverage', value: 68, impact: 'negative', contribution: '-8' },
  { name: 'Source Quality', value: 85, impact: 'positive', contribution: '+12' },
  { name: 'Consistency', value: 71, impact: 'positive', contribution: '+5' },
  { name: 'Retrieval Relevance', value: 89, impact: 'positive', contribution: '+15' },
  { name: 'Model Uncertainty', value: 42, impact: 'negative', contribution: '-12' },
  { name: 'Recency', value: 55, impact: 'negative', contribution: '-6' },
  { name: 'Hallucination Risk', value: 78, impact: 'positive', contribution: '+8' },
];

const evidenceItems = [
  {
    id: '1',
    title: 'Aircraft Performance Primer',
    type: 'pdf',
    section: 'Page 12, Section 2.1',
    relevance: 92,
    snippet:
      'Fuel burn comparisons should be normalized by stage length and payload to avoid misleading conclusions...',
  },
  {
    id: '2',
    title: 'Internal Engineering Notes',
    type: 'internal',
    section: 'Entry #204',
    relevance: 87,
    snippet:
      'Short-haul vs long-haul efficiency differs due to climb/cruise proportions; evaluate per seat-mile...',
  },
  {
    id: '3',
    title: 'Widebody vs Narrowbody Overview',
    type: 'web',
    section: 'Design Goals',
    relevance: 81,
    snippet:
      'Long-range aircraft design emphasizes weight, aerodynamics, and systems integration over long segments...',
  },
];

function SourceIcon({ type }) {
  const Icon = type === 'pdf' ? FileText : type === 'web' ? Globe : Building2;
  return <Icon className="w-4 h-4 text-gray-600" />;
}

function ProgressBar({ value }) {
  return (
    <div className="h-2 w-full rounded-full bg-gray-100 overflow-hidden">
      <div className="h-full bg-gray-900" style={{ width: `${value}%` }} />
    </div>
  );
}

export default function RightPanel() {
  const [collapsed, setCollapsed] = useState(false);
  const [tab, setTab] = useState('confidence');
  const [onlyCited, setOnlyCited] = useState(false);
  const [query, setQuery] = useState('');

  const filteredEvidence = useMemo(() => {
    let items = evidenceItems;
    if (query.trim()) {
      const q = query.toLowerCase();
      items = items.filter(
        (e) =>
          e.title.toLowerCase().includes(q) ||
          e.snippet.toLowerCase().includes(q) ||
          e.section.toLowerCase().includes(q)
      );
    }
    // onlyCited is placeholder (kept for UI)
    return items;
  }, [query, onlyCited]);

  const tabs = [
    { id: 'confidence', label: 'Confidence' },
    { id: 'signals', label: 'Signals' },
    { id: 'evidence', label: 'Evidence' },
  ];

  return (
    <aside
      className={[
        'relative border-l border-gray-200 bg-gray-50 hidden lg:flex flex-col transition-all duration-300',
        collapsed ? 'w-16' : 'w-[420px]',
      ].join(' ')}
    >
      {/* Collapse Toggle (same style as left sidebar) */}
      <button
        onClick={() => setCollapsed(!collapsed)}
        className="absolute -left-3 top-20 w-6 h-6 rounded-full bg-white border border-gray-200 shadow-sm flex items-center justify-center hover:bg-gray-50 transition-colors"
        aria-label="Toggle trust panel"
      >
        {collapsed ? (
          <ChevronLeft className="w-4 h-4 text-gray-600" />
        ) : (
          <ChevronRight className="w-4 h-4 text-gray-600" />
        )}
      </button>

      {/* Header / Tabs */}
      <div className="p-6 pb-3">
        <div className="flex items-center justify-between">
          {!collapsed ? (
            <h2 className="text-sm font-semibold text-gray-900">Trust Panel</h2>
          ) : (
            <div className="w-full text-center text-xs font-semibold text-gray-700">Trust</div>
          )}
        </div>

        {/* Tabs (collapsed = vertical icon-like buttons, expanded = normal tabs) */}
        {!collapsed ? (
          <div className="mt-3 flex gap-2">
            {tabs.map((t) => (
              <button
                key={t.id}
                onClick={() => setTab(t.id)}
                className={[
                  'text-xs px-3 py-2 rounded-lg border transition-colors',
                  tab === t.id
                    ? 'bg-white border-gray-200 text-gray-900'
                    : 'bg-transparent border-transparent text-gray-600 hover:bg-gray-100',
                ].join(' ')}
              >
                {t.label}
              </button>
            ))}
          </div>
        ) : (
          <div className="mt-3 flex flex-col gap-2">
            {tabs.map((t) => (
              <button
                key={t.id}
                onClick={() => setTab(t.id)}
                title={t.label}
                className={[
                  'mx-auto w-10 h-10 rounded-xl border transition-colors text-xs',
                  tab === t.id
                    ? 'bg-white border-gray-200 text-gray-900'
                    : 'bg-transparent border-transparent text-gray-600 hover:bg-gray-100',
                ].join(' ')}
              >
                {t.label[0]}
              </button>
            ))}
          </div>
        )}
      </div>

      {/* Content */}
      {!collapsed && (
        <div className="flex-1 overflow-auto px-6 pb-6 space-y-4">
          {tab === 'confidence' && (
            <>
              <div className="rounded-xl border border-gray-200 bg-white p-5 shadow-sm">
                <div className="flex items-start justify-between">
                  <div>
                    <div className="text-4xl font-bold text-gray-900">74</div>
                    <div className="text-sm text-gray-600">out of 100</div>
                  </div>
                  <span className="text-xs px-2 py-1 rounded-full bg-amber-50 border border-amber-200 text-amber-800 font-medium">
                    Medium Confidence
                  </span>
                </div>

                <div className="mt-4 flex items-center gap-2 text-sm text-gray-600">
                  <TrendingUp className="w-4 h-4 text-green-600" />
                  <span className="text-green-700 font-medium">+3</span>
                  <span>vs previous run</span>
                </div>

                <div className="mt-4 flex flex-wrap gap-2">
                  <span className="text-xs px-2 py-1 rounded-full bg-red-50 border border-red-200 text-red-700">
                    Low coverage
                  </span>
                  <span className="text-xs px-2 py-1 rounded-full bg-orange-50 border border-orange-200 text-orange-700">
                    Outdated sources
                  </span>
                </div>
              </div>

              <div className="rounded-xl border border-gray-200 bg-white p-5 shadow-sm">
                <h3 className="text-sm font-semibold text-gray-900 mb-3">Notes</h3>
                <p className="text-sm text-gray-600">
                  Confidence is medium due to strong relevance and source quality, but weaker coverage/recency
                  signals. Fuel efficiency depends on mission assumptions.
                </p>
              </div>
            </>
          )}

          {tab === 'signals' && (
            <div className="rounded-xl border border-gray-200 bg-white p-5 shadow-sm">
              <h3 className="text-sm font-semibold text-gray-900 mb-4">Signal Breakdown</h3>
              <div className="space-y-4">
                {signals.map((s) => (
                  <div key={s.name}>
                    <div className="flex items-center justify-between text-sm">
                      <span className="text-gray-700">{s.name}</span>
                      <span className="text-gray-900 font-medium">{s.value}%</span>
                    </div>
                    <div className="mt-2 flex items-center gap-3">
                      <div className="flex-1">
                        <ProgressBar value={s.value} />
                      </div>
                      <span
                        className={[
                          'text-xs font-semibold',
                          s.impact === 'positive' ? 'text-green-700' : 'text-red-700',
                        ].join(' ')}
                      >
                        {s.contribution}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {tab === 'evidence' && (
            <div className="rounded-xl border border-gray-200 bg-white p-5 shadow-sm">
              <div className="flex items-center justify-between mb-3">
                <h3 className="text-sm font-semibold text-gray-900">Evidence</h3>
                <button className="text-xs px-2 py-1 rounded-md hover:bg-gray-100 text-gray-600 inline-flex items-center gap-1">
                  <Plus className="w-3.5 h-3.5" /> Add
                </button>
              </div>

              <div className="relative mb-3">
                <Search className="w-4 h-4 text-gray-400 absolute left-3 top-2.5" />
                <input
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  placeholder="Search evidence..."
                  className="w-full pl-9 pr-3 py-2 text-sm rounded-lg border border-gray-200 focus:outline-none focus:ring-2 focus:ring-primary-500"
                />
              </div>

              <label className="flex items-center gap-2 text-sm text-gray-600 mb-3">
                <input
                  type="checkbox"
                  checked={onlyCited}
                  onChange={(e) => setOnlyCited(e.target.checked)}
                />
                Only cited
              </label>

              <div className="space-y-3">
                {filteredEvidence.map((e) => (
                  <div key={e.id} className="rounded-lg border border-gray-200 p-3 hover:bg-gray-50">
                    <div className="flex items-start justify-between gap-2">
                      <div className="min-w-0">
                        <div className="flex items-center gap-2">
                          <SourceIcon type={e.type} />
                          <div className="text-sm font-medium text-gray-900 truncate">{e.title}</div>
                        </div>
                        <div className="text-xs text-gray-500 mt-1">{e.section}</div>
                      </div>
                      <div className="text-xs font-semibold text-gray-900">{e.relevance}%</div>
                    </div>

                    <p className="text-sm text-gray-600 mt-2 line-clamp-2">{e.snippet}</p>

                    <div className="mt-3 flex items-center gap-2">
                      <button className="text-xs px-2 py-1 rounded-md border border-gray-200 hover:bg-white inline-flex items-center gap-1">
                        <ExternalLink className="w-3.5 h-3.5" /> Open
                      </button>
                      <button className="text-xs px-2 py-1 rounded-md border border-gray-200 hover:bg-white inline-flex items-center gap-1">
                        <Pin className="w-3.5 h-3.5" /> Pin
                      </button>
                    </div>
                  </div>
                ))}
              </div>

              <div className="mt-4 rounded-lg border border-gray-200 bg-gray-50 p-3">
                <div className="text-xs font-medium text-gray-700 mb-1">Preview</div>
                <div className="text-sm text-gray-600">
                  Select an evidence item to preview the document snippet here.
                </div>
              </div>
            </div>
          )}
        </div>
      )}
    </aside>
  );
}