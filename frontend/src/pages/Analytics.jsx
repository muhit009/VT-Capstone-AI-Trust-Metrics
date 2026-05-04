/* eslint-disable react/prop-types */

import { useEffect, useMemo, useState } from 'react';
import {
  BarChart3,
  Brain,
  CheckCircle2,
  Clock3,
  Gauge,
  ShieldCheck,
  Sparkles,
} from 'lucide-react';
import {
  QUERY_HISTORY_UPDATED_EVENT,
  readSavedQueryHistory,
} from '@/services/queryHistory';

function formatPercent(value) {
  if (value == null || Number.isNaN(value)) return '—';
  return `${Math.round(value * 100)}%`;
}

function formatScore(value) {
  if (value == null || Number.isNaN(value)) return '—';
  return `${Math.round(value)}/100`;
}

function formatLatency(value) {
  if (value == null || Number.isNaN(value)) return '—';
  return `${Math.round(value)} ms`;
}

function formatTimestamp(timestamp) {
  const parsed = new Date(timestamp);
  if (Number.isNaN(parsed.getTime())) return 'Recently';

  return parsed.toLocaleString([], {
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  });
}

function normalizePreviewText(value) {
  return String(value ?? '')
    .replace(/\r\n/g, '\n')
    .replace(/\[([^\]]+)\]\(([^)]+)\)/g, '$1')
    .replace(/^\s{0,3}#{1,6}\s+/gm, '')
    .replace(/^\s*>\s?/gm, '')
    .replace(/^\s*[*-]\s+/gm, '- ')
    .replace(/\*\*([^*]+)\*\*/g, '$1')
    .replace(/__([^_]+)__/g, '$1')
    .replace(/(^|[^\w*])\*([^*\n]+)\*(?=[^\w*]|$)/g, '$1$2')
    .replace(/(^|[^\w_])_([^_\n]+)_(?=[^\w_]|$)/g, '$1$2')
    .replace(/`([^`]+)`/g, '$1')
    .replace(/\n{2,}EVIDENCE USED[\s\S]*$/i, '')
    .replace(/\n+/g, ' ')
    .trim();
}

function average(values) {
  const filtered = values.filter((value) => value != null && !Number.isNaN(value));
  if (!filtered.length) return null;

  return filtered.reduce((sum, value) => sum + value, 0) / filtered.length;
}

function StatCard({ icon: Icon, label, value, helper }) {
  return (
    <div className="rounded-2xl border border-gray-200 bg-white p-5 shadow-sm">
      <div className="flex items-center gap-2 text-sm font-medium text-gray-600">
        <Icon className="h-4 w-4" />
        {label}
      </div>
      <div className="mt-3 text-3xl font-semibold text-gray-900">{value}</div>
      <p className="mt-2 text-xs leading-5 text-gray-500">{helper}</p>
    </div>
  );
}

function tierTone(tier) {
  if (tier === 'HIGH') return 'border-emerald-200 bg-emerald-50 text-emerald-700';
  if (tier === 'MEDIUM') return 'border-amber-200 bg-amber-50 text-amber-700';
  return 'border-rose-200 bg-rose-50 text-rose-700';
}

function TierDistribution({ counts, total }) {
  const tiers = [
    { key: 'HIGH', label: 'High', barClass: 'bg-emerald-500' },
    { key: 'MEDIUM', label: 'Medium', barClass: 'bg-amber-500' },
    { key: 'LOW', label: 'Low', barClass: 'bg-rose-500' },
  ];

  return (
    <section className="rounded-3xl border border-gray-200 bg-white p-6 shadow-sm">
      <div className="flex items-center gap-3">
        <div className="rounded-2xl bg-slate-100 p-2">
          <ShieldCheck className="h-5 w-5 text-slate-700" />
        </div>
        <div>
          <h2 className="text-lg font-semibold text-gray-900">Confidence tier distribution</h2>
          <p className="mt-1 text-sm text-gray-600">
            Example distribution of saved responses across High, Medium, and Low confidence tiers.
          </p>
        </div>
      </div>

      <div className="mt-6 space-y-4">
        {tiers.map((tier) => {
          const count = counts[tier.key] ?? 0;
          const ratio = total ? count / total : 0;

          return (
            <div key={tier.key}>
              <div className="mb-2 flex items-center justify-between text-sm">
                <span className="font-medium text-gray-700">{tier.label}</span>
                <span className="text-gray-900">
                  {count} ({Math.round(ratio * 100)}%)
                </span>
              </div>
              <div className="h-2 overflow-hidden rounded-full bg-gray-100">
                <div
                  className={['h-full rounded-full', tier.barClass].join(' ')}
                  style={{ width: `${ratio * 100}%` }}
                />
              </div>
            </div>
          );
        })}
      </div>
    </section>
  );
}

function RecentResponses({ items }) {
  return (
    <section className="rounded-3xl border border-gray-200 bg-white p-6 shadow-sm">
      <div className="flex items-center gap-3">
        <div className="rounded-2xl bg-slate-100 p-2">
          <Clock3 className="h-5 w-5 text-slate-700" />
        </div>
        <div>
          <h2 className="text-lg font-semibold text-gray-900">Recent queries and responses</h2>
          <p className="mt-1 text-sm text-gray-600">
            Most recent saved responses from this browser workspace.
          </p>
        </div>
      </div>

      {items.length ? (
        <div className="mt-6 space-y-4">
          {items.map((item) => (
            <article key={item.id} className="rounded-2xl border border-gray-200 p-5">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div className="min-w-0 flex-1">
                  <div className="text-sm font-semibold text-gray-900">{item.query}</div>
                  <div className="mt-1 text-xs text-gray-500">{item.timestampLabel}</div>
                </div>

                <div
                  className={[
                    'rounded-full border px-3 py-1 text-xs font-medium',
                    tierTone(item.tier),
                  ].join(' ')}
                >
                  {item.tier} · {item.confidence}/100
                </div>
              </div>

              <p className="mt-4 text-sm leading-6 text-gray-700">{item.answer}</p>

              <div className="mt-4 flex flex-wrap gap-2 text-xs text-gray-600">
                <span className="rounded-full bg-gray-100 px-3 py-1">
                  Grounding {formatPercent(item.grounding)}
                </span>
                <span className="rounded-full bg-gray-100 px-3 py-1">
                  Generation {formatPercent(item.generation)}
                </span>
                <span className="rounded-full bg-gray-100 px-3 py-1">
                  Latency {item.latencyMs} ms
                </span>
              </div>
            </article>
          ))}
        </div>
      ) : (
        <div className="mt-6 rounded-2xl border border-dashed border-gray-300 bg-gray-50 px-5 py-6 text-sm text-gray-600">
          No saved responses yet. Submit a few successful chats and the recent-response panel
          will populate automatically.
        </div>
      )}
    </section>
  );
}

export default function Analytics() {
  const [savedHistory, setSavedHistory] = useState(() => readSavedQueryHistory());

  useEffect(() => {
    const refreshHistory = () => {
      setSavedHistory(readSavedQueryHistory());
    };

    refreshHistory();
    window.addEventListener(QUERY_HISTORY_UPDATED_EVENT, refreshHistory);

    return () => {
      window.removeEventListener(QUERY_HISTORY_UPDATED_EVENT, refreshHistory);
    };
  }, []);

  const analytics = useMemo(() => {
    const totalQueries = savedHistory.length;
    const tierCounts = {
      HIGH: savedHistory.filter((item) => item.confidence.tier === 'HIGH').length,
      MEDIUM: savedHistory.filter((item) => item.confidence.tier === 'MEDIUM').length,
      LOW: savedHistory.filter((item) => item.confidence.tier === 'LOW').length,
    };

    return {
      totalQueries,
      averageConfidence: average(savedHistory.map((item) => item.confidence.finalScore)),
      averageGrounding: average(savedHistory.map((item) => item.confidence.groundingScore)),
      averageGeneration: average(
        savedHistory.map((item) => item.confidence.generationConfidence),
      ),
      averageLatencyMs: average(savedHistory.map((item) => item.metadata.processingTimeMs)),
      tierCounts,
      recentResponses: savedHistory.slice(0, 6).map((item) => ({
        id: item.queryId,
        query: item.query,
        timestampLabel: formatTimestamp(item.timestamp),
        tier: item.confidence.tier ?? 'MEDIUM',
        confidence: item.confidence.finalScore ?? 0,
        grounding: item.confidence.groundingScore ?? 0,
        generation: item.confidence.generationConfidence ?? 0,
        latencyMs: item.metadata.processingTimeMs ?? 0,
        answer: normalizePreviewText(item.answer) || 'No answer saved for this query.',
      })),
    };
  }, [savedHistory]);

  return (
    <div className="flex min-h-0 flex-1 flex-col bg-white">
      <div className="flex-1 overflow-auto px-6 py-6 lg:px-8">
        <div className="mx-auto max-w-6xl space-y-6">
          <div className="rounded-3xl border border-gray-200 bg-white p-8 shadow-sm">
            <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
              <div>
                <p className="text-sm font-semibold uppercase tracking-[0.2em] text-primary-700">
                  Analytics
                </p>
                <h2 className="mt-3 text-3xl font-semibold text-gray-900">
                  Confidence analytics
                </h2>
                <p className="mt-3 max-w-3xl text-base leading-7 text-gray-600">
                  This page summarizes saved response history from this workspace. As successful
                  chats are stored locally, these metrics and recent responses will update without
                  changing the page structure.
                </p>
              </div>

              <div className="rounded-2xl border border-gray-200 bg-gray-50 px-5 py-4 text-sm text-gray-700">
                {analytics.totalQueries ? `${analytics.totalQueries} saved responses` : 'No data yet'}
              </div>
            </div>
          </div>

          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-5">
            <StatCard
              icon={CheckCircle2}
              label="Total saved queries"
              value={`${analytics.totalQueries}`}
              helper="Successful responses saved in local workspace history."
            />
            <StatCard
              icon={Gauge}
              label="Average confidence"
              value={formatScore(analytics.averageConfidence)}
              helper="Average fused confidence score across saved responses."
            />
            <StatCard
              icon={ShieldCheck}
              label="Average grounding"
              value={formatPercent(analytics.averageGrounding)}
              helper="Average evidence-grounding support score."
            />
            <StatCard
              icon={Brain}
              label="Average generation"
              value={formatPercent(analytics.averageGeneration)}
              helper="Average normalized model-side confidence signal."
            />
            <StatCard
              icon={Sparkles}
              label="Average latency"
              value={formatLatency(analytics.averageLatencyMs)}
              helper="Average end-to-end response latency."
            />
          </div>

          <div className="grid gap-6 xl:grid-cols-[minmax(0,0.95fr)_minmax(0,1.25fr)]">
            <TierDistribution counts={analytics.tierCounts} total={analytics.totalQueries} />
            <RecentResponses items={analytics.recentResponses} />
          </div>

          <div className="rounded-3xl border border-dashed border-gray-300 bg-gray-50 px-6 py-5 text-sm text-gray-600 shadow-sm">
            <div className="flex items-center gap-2 font-medium text-gray-700">
              <BarChart3 className="h-4 w-4" />
              Data source
            </div>
            <p className="mt-2 leading-6">
              Analytics currently read from the same saved query history used by this browser
              workspace. If you later move to backend-backed reporting, the page can keep this
              structure and swap only the data source.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
