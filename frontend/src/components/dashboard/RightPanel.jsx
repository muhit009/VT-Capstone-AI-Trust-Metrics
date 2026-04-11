import { useMemo, useState } from 'react';
import {
  FileText,
  Gauge,
  TriangleAlert,
  ShieldCheck,
  Clock3,
  ChevronDown,
  ChevronUp,
  Brain,
  Info,
} from 'lucide-react';

const tierTone = {
  HIGH: 'text-emerald-700 bg-emerald-50 border-emerald-200',
  MEDIUM: 'text-amber-700 bg-amber-50 border-amber-200',
  LOW: 'text-rose-700 bg-rose-50 border-rose-200',
};

function toPercent(value) {
  if (value == null || Number.isNaN(value)) return null;
  return value <= 1 ? value * 100 : value;
}

function formatPercent(value) {
  const percent = toPercent(value);
  return percent == null ? '—' : `${Math.round(percent)}%`;
}

function safeRate(numerator, denominator) {
  if (
    numerator == null ||
    denominator == null ||
    denominator === 0 ||
    Number.isNaN(numerator) ||
    Number.isNaN(denominator)
  ) {
    return null;
  }
  return (numerator / denominator) * 100;
}

function PanelSection({ title, defaultOpen = true, children }) {
  const [open, setOpen] = useState(defaultOpen);

  return (
    <div className="rounded-3xl border border-gray-200 bg-white shadow-sm">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center justify-between px-5 py-4 text-left"
      >
        <div className="text-sm font-semibold text-gray-900">{title}</div>
        {open ? (
          <ChevronUp className="h-4 w-4 text-gray-500" />
        ) : (
          <ChevronDown className="h-4 w-4 text-gray-500" />
        )}
      </button>

      {open ? <div className="border-t border-gray-200 p-5">{children}</div> : null}
    </div>
  );
}

function StatCard({ icon: Icon, label, value, helper }) {
  return (
    <div className="rounded-2xl border border-gray-200 bg-white p-4 shadow-sm">
      <div className="flex items-center gap-2 text-sm font-medium text-gray-600">
        <Icon className="h-4 w-4" /> {label}
      </div>
      <div className="mt-3 text-2xl font-semibold text-gray-900">{value}</div>
      {helper ? <p className="mt-1 text-xs leading-5 text-gray-500">{helper}</p> : null}
    </div>
  );
}

function ProgressRow({ label, value, helper }) {
  const percent = toPercent(value);
  const normalized =
    typeof percent === 'number' ? Math.max(0, Math.min(100, Math.round(percent))) : null;

  return (
    <div>
      <div className="mb-1 flex items-center justify-between text-sm">
        <span className="text-gray-700">{label}</span>
        <span className="font-medium text-gray-900">
          {normalized == null ? '—' : `${normalized}%`}
        </span>
      </div>
      <div className="h-2 overflow-hidden rounded-full bg-gray-100">
        <div
          className="h-full rounded-full bg-slate-900"
          style={{ width: `${normalized ?? 0}%` }}
        />
      </div>
      {helper ? <div className="mt-1 text-xs text-gray-500">{helper}</div> : null}
    </div>
  );
}

function buildExplanation(confidence, citations) {
  const supported = confidence?.signals?.grounding_supported ?? null;
  const totalClaims = confidence?.signals?.grounding_num_claims ?? null;
  const grounding = formatPercent(confidence?.signals?.grounding_score);
  const generation = formatPercent(confidence?.signals?.gen_confidence_normalized);
  const tier = confidence?.tier ?? 'UNKNOWN';
  const label = confidence?.signals?.gen_confidence_level ?? 'Unavailable';
  const citationCount = citations?.length ?? 0;

  const summary = `Overall confidence is ${tier.toLowerCase()} because the system found ${citationCount} retrieved source${citationCount === 1 ? '' : 's'}, grounding scored ${grounding}, and generation confidence scored ${generation}.`;

  const bullets = [
    totalClaims != null && supported != null
      ? `${supported} of ${totalClaims} extracted claims were supported by the retrieved evidence.`
      : 'Claim-support data was not fully available for this response.',
    `The language model self-confidence label was ${label}.`,
    confidence?.warning
      ? `Warning: ${confidence.warning}`
      : 'No extra warning was attached to this response.',
  ];

  return { summary, bullets };
}

const previewResponse = {
  confidence: {
    score: 74,
    tier: 'MEDIUM',
    degraded: false,
    warning:
      'This answer is useful, but fuel-efficiency comparisons depend heavily on mission assumptions and normalization variables.',
    signals: {
      grounding_score: 0.68,
      grounding_num_claims: 5,
      grounding_supported: 4,
      gen_confidence_raw: 0.71,
      gen_confidence_normalized: 0.71,
      gen_confidence_level: 'MODERATE',
      grounding_contribution: 0.55,
      gen_conf_contribution: 0.45,
    },
  },
  citations: [
    {
      rank: 1,
      retrieval_score: 0.92,
      text: 'Fuel burn comparisons should be normalized by stage length, reserves, payload, and seating assumptions before comparing aircraft families.',
      source: {
        document_name: 'Aircraft Performance Primer',
        section: 'Section 2.1',
        page_number: 12,
        revision: 'Rev B',
      },
    },
    {
      rank: 2,
      retrieval_score: 0.86,
      text: 'Short-haul and long-haul fuel efficiency differ because climb and cruise proportions change significantly across mission lengths.',
      source: {
        document_name: 'Internal Engineering Notes',
        section: 'Entry #204',
        page_number: null,
        revision: '2025.09',
      },
    },
  ],
  metadata: {
    latency_ms: {
      total: 842,
      retrieval: 123,
      llm_generation: 472,
      grounding_scoring: 88,
      gen_confidence_scoring: 79,
      fusion: 80,
    },
    model: {
      name: 'Grounded RAG Pipeline',
      provider: 'Internal',
      version: 'preview',
      endpoint: '/v1/rag/query',
    },
    retriever: {
      top_k: 5,
      embedding_model: 'text-embedding-preview',
      vector_store: 'pgvector',
    },
  },
  request_id: 'preview-request',
  timestamp: new Date().toISOString(),
};

export default function RightPanel({ latestResponse }) {
  const data = latestResponse || previewResponse;
  const isPreview = !latestResponse;

  const { confidence, citations, metadata, request_id, timestamp } = data;

  const claimSupportRate = safeRate(
    confidence?.signals?.grounding_supported,
    confidence?.signals?.grounding_num_claims,
  );

  const explanation = useMemo(
    () => buildExplanation(confidence, citations),
    [confidence, citations],
  );

  return (
    <aside className="hidden h-full w-[420px] shrink-0 overflow-auto border-l border-gray-200 bg-slate-50 xl:block">
      <div className="space-y-5 p-6">
        {isPreview ? (
          <div className="rounded-2xl border border-dashed border-gray-300 bg-white px-4 py-3 text-sm text-gray-600">
            Preview mode: this is the intended confidence and evidence layout until the backend response is live.
          </div>
        ) : null}

        <PanelSection title="Confidence summary" defaultOpen>
          <div className="flex items-start justify-between gap-3">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.2em] text-gray-500">
                Current answer
              </p>
              <h2 className="mt-2 text-lg font-semibold text-gray-900">Confidence summary</h2>
            </div>

            <div
              className={[
                'rounded-full border px-3 py-1 text-sm font-semibold',
                tierTone[confidence.tier],
              ].join(' ')}
            >
              {confidence.tier}
            </div>
          </div>

          <div className="mt-4 grid grid-cols-2 gap-3">
            <StatCard
              icon={Gauge}
              label="Overall"
              value={`${confidence.score}/100`}
              helper="Final fused confidence score."
            />
            <StatCard
              icon={Clock3}
              label="Latency"
              value={`${metadata?.latency_ms?.total ?? '—'} ms`}
              helper="End-to-end response time."
            />
          </div>

          {confidence.warning ? (
            <div className="mt-4 rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
              <div className="flex items-start gap-2">
                <TriangleAlert className="mt-0.5 h-4 w-4 shrink-0" />
                <span>{confidence.warning}</span>
              </div>
            </div>
          ) : null}
        </PanelSection>

        <PanelSection title="Signal breakdown" defaultOpen>
          <div className="mb-4 flex items-center gap-2">
            <ShieldCheck className="h-4 w-4 text-gray-600" />
            <h3 className="text-sm font-semibold text-gray-900">
              Metrics feeding the confidence score
            </h3>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <StatCard
              icon={Info}
              label="Supported claims"
              value={`${confidence.signals?.grounding_supported ?? 0}/${confidence.signals?.grounding_num_claims ?? 0}`}
              helper="Evidence-backed claims out of total extracted claims."
            />
            <StatCard
              icon={FileText}
              label="Citations"
              value={`${citations?.length ?? 0}`}
              helper="Retrieved evidence chunks used for the answer."
            />
          </div>

          <div className="mt-5 space-y-4">
            <ProgressRow
              label="Grounding score"
              value={confidence.signals?.grounding_score}
              helper="How well the answer is supported by retrieved evidence."
            />
            <ProgressRow
              label="Generation confidence"
              value={confidence.signals?.gen_confidence_normalized}
              helper="Model-side confidence after normalization."
            />
            <ProgressRow
              label="Claim support rate"
              value={claimSupportRate}
              helper="Share of extracted claims supported by evidence."
            />
            <ProgressRow
              label="Grounding contribution"
              value={confidence.signals?.grounding_contribution}
              helper="Relative contribution from evidence-grounding."
            />
            <ProgressRow
              label="Generation contribution"
              value={confidence.signals?.gen_conf_contribution}
              helper="Relative contribution from model confidence."
            />
          </div>

          <div className="mt-5 rounded-2xl bg-gray-50 p-4 text-sm text-gray-700">
            <div className="font-medium text-gray-900">Generation label</div>
            <div className="mt-1">
              {confidence.signals?.gen_confidence_level ?? 'Unavailable'}
            </div>
          </div>
        </PanelSection>

        <PanelSection title="Retrieved evidence" defaultOpen>
          <div className="mb-4 flex items-center gap-2">
            <FileText className="h-4 w-4 text-gray-600" />
            <h3 className="text-sm font-semibold text-gray-900">Sources and citations</h3>
          </div>

          <div className="space-y-3">
            {citations?.length ? (
              citations.map((citation) => (
                <div
                  key={`${request_id}-${citation.rank}`}
                  className="rounded-2xl border border-gray-200 p-4"
                >
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <div className="text-sm font-medium text-gray-900">
                        [{citation.rank}] {citation.source.document_name}
                      </div>
                      <div className="mt-1 text-xs text-gray-500">
                        {citation.source.section || 'Section unavailable'}
                        {citation.source.page_number ? ` · p.${citation.source.page_number}` : ''}
                        {citation.source.revision ? ` · ${citation.source.revision}` : ''}
                      </div>
                    </div>

                    <div className="rounded-full bg-gray-100 px-2.5 py-1 text-xs font-medium text-gray-700">
                      {Math.round((citation.retrieval_score ?? 0) * 100)}%
                    </div>
                  </div>

                  <p className="mt-3 text-sm leading-6 text-gray-700">{citation.text}</p>
                </div>
              ))
            ) : (
              <div className="rounded-2xl border border-dashed border-gray-300 p-4 text-sm text-gray-600">
                No citations were returned for this answer.
              </div>
            )}
          </div>
        </PanelSection>

        <PanelSection title="Response explanation" defaultOpen>
          <div className="mb-4 flex items-center gap-2">
            <Brain className="h-4 w-4 text-gray-600" />
            <h3 className="text-sm font-semibold text-gray-900">
              Human-readable confidence explanation
            </h3>
          </div>

          <div className="rounded-2xl bg-gray-50 p-4 text-sm leading-6 text-gray-700">
            {explanation.summary}
          </div>

          <ul className="mt-4 space-y-2 text-sm leading-6 text-gray-700">
            {explanation.bullets.map((item) => (
              <li key={item} className="rounded-xl border border-gray-200 bg-white px-3 py-3">
                {item}
              </li>
            ))}
          </ul>
        </PanelSection>

        <PanelSection title="Request metadata" defaultOpen>
          <div className="space-y-4 text-sm text-gray-700">
            <div className="rounded-2xl bg-gray-50 p-4">
              <div className="text-xs font-semibold uppercase tracking-wide text-gray-500">
                Request info
              </div>
              <div className="mt-2 space-y-1">
                <div>
                  <span className="font-medium text-gray-900">Request ID:</span> {request_id}
                </div>
                <div>
                  <span className="font-medium text-gray-900">Timestamp:</span>{' '}
                  {new Date(timestamp).toLocaleString()}
                </div>
              </div>
            </div>

            <div className="rounded-2xl bg-gray-50 p-4">
              <div className="text-xs font-semibold uppercase tracking-wide text-gray-500">
                Model
              </div>
              <div className="mt-2 space-y-1">
                <div>
                  <span className="font-medium text-gray-900">Name:</span>{' '}
                  {metadata?.model?.name || 'Unknown model'}
                </div>
                <div>
                  <span className="font-medium text-gray-900">Provider:</span>{' '}
                  {metadata?.model?.provider || 'Unknown provider'}
                </div>
                <div>
                  <span className="font-medium text-gray-900">Version:</span>{' '}
                  {metadata?.model?.version || '—'}
                </div>
                <div>
                  <span className="font-medium text-gray-900">Endpoint:</span>{' '}
                  {metadata?.model?.endpoint || '—'}
                </div>
              </div>
            </div>

            <div className="rounded-2xl bg-gray-50 p-4">
              <div className="text-xs font-semibold uppercase tracking-wide text-gray-500">
                Retriever
              </div>
              <div className="mt-2 space-y-1">
                <div>
                  <span className="font-medium text-gray-900">top_k:</span>{' '}
                  {metadata?.retriever?.top_k ?? '—'}
                </div>
                <div>
                  <span className="font-medium text-gray-900">Embedding model:</span>{' '}
                  {metadata?.retriever?.embedding_model || '—'}
                </div>
                <div>
                  <span className="font-medium text-gray-900">Vector store:</span>{' '}
                  {metadata?.retriever?.vector_store || '—'}
                </div>
              </div>
            </div>

            <div className="rounded-2xl bg-gray-50 p-4">
              <div className="text-xs font-semibold uppercase tracking-wide text-gray-500">
                Latency breakdown
              </div>
              <div className="mt-2 grid grid-cols-2 gap-x-4 gap-y-1 text-sm">
                <div>Retrieval: {metadata?.latency_ms?.retrieval ?? '—'} ms</div>
                <div>Generation: {metadata?.latency_ms?.llm_generation ?? '—'} ms</div>
                <div>Grounding scoring: {metadata?.latency_ms?.grounding_scoring ?? '—'} ms</div>
                <div>
                  Gen-conf scoring: {metadata?.latency_ms?.gen_confidence_scoring ?? '—'} ms
                </div>
                <div>Fusion: {metadata?.latency_ms?.fusion ?? '—'} ms</div>
                <div>Total: {metadata?.latency_ms?.total ?? '—'} ms</div>
              </div>
            </div>
          </div>
        </PanelSection>

        <div className="rounded-3xl border border-gray-200 bg-white p-5 shadow-sm">
          <div className="mb-4 text-sm font-semibold text-gray-900">Confidence guide</div>

          <div className="space-y-3 text-sm leading-6 text-gray-600">
            <div className="rounded-2xl bg-emerald-50 px-4 py-3">
              <span className="font-medium text-emerald-700">High</span>: grounded enough to reuse,
              still verify critical specs.
            </div>

            <div className="rounded-2xl bg-amber-50 px-4 py-3">
              <span className="font-medium text-amber-700">Medium</span>: useful draft answer,
              verify assumptions and evidence.
            </div>

            <div className="rounded-2xl bg-rose-50 px-4 py-3">
              <span className="font-medium text-rose-700">Low</span>: treat as unsafe until
              confirmed from source docs.
            </div>
          </div>
        </div>
      </div>
    </aside>
  );
}