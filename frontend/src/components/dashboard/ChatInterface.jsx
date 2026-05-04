import {
  Loader2,
  Send,
  Copy,
  AlertTriangle,
  CheckCircle2,
  AlertCircle,
  RotateCcw,
} from 'lucide-react';

import FeedbackWidget from '@/components/common/FeedbackWidget';

const tierStyles = {
  HIGH: 'bg-emerald-50 text-emerald-700 border-emerald-200',
  MEDIUM: 'bg-amber-50 text-amber-700 border-amber-200',
  LOW: 'bg-rose-50 text-rose-700 border-rose-200',
};

const tierIcons = {
  HIGH: CheckCircle2,
  MEDIUM: AlertCircle,
  LOW: AlertTriangle,
};

function formatLatency(latency) {
  if (typeof latency !== 'number') return '—';
  return `${latency} ms`;
}

function SourcePill({ citation, rank }) {
  return (
    <div className="inline-flex items-center gap-2 rounded-full border border-gray-200 bg-gray-50 px-3 py-1 text-xs text-gray-700">
      <span className="font-medium">[{rank}]</span>
      <span className="max-w-[220px] truncate">{citation.document}</span>
      {citation.page ? (
        <span className="text-gray-500">p.{citation.page}</span>
      ) : null}
    </div>
  );
}

function AssistantMessage({ message, onCopy }) {
  const response = message.response;
  const tier = response?.confidence?.tier ?? 'MEDIUM';
  const TierIcon = tierIcons[tier] ?? AlertCircle;

  return (
    <div className="flex justify-start">
      <div className="w-full max-w-4xl rounded-2xl border border-gray-200 bg-white p-6 shadow-sm">
        <div className="flex items-start justify-between gap-4">
          <div>
            <p className="text-sm font-semibold text-gray-900">Assistant answer</p>
            {response ? (
              <div className="mt-2 flex flex-wrap items-center gap-2">
                <div
                  className={[
                    'inline-flex items-center gap-2 rounded-full border px-3 py-1 text-xs font-medium',
                    tierStyles[tier],
                  ].join(' ')}
                >
                  <TierIcon className="h-3.5 w-3.5" />
                  {response.confidence.final_score}/100 · {tier}
                </div>

                <div className="text-xs text-gray-500">
                  Latency: {formatLatency(response.metadata?.processing_time_ms)}
                </div>

                {response.confidence.degraded ? (
                  <div className="rounded-full border border-amber-200 bg-amber-50 px-3 py-1 text-xs font-medium text-amber-700">
                    Degraded mode
                  </div>
                ) : null}
              </div>
            ) : null}
          </div>
        </div>

        <div className="mt-4 whitespace-pre-wrap text-[15px] leading-7 text-gray-800">
          {message.content}
        </div>

        {response ? (
          <>
            {response.confidence.warnings?.[0] ? (
              <div className="mt-4 rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
                {response.confidence.warnings[0]}
              </div>
            ) : null}

            <div className="mt-5">
              <div className="mb-2 text-xs font-semibold uppercase tracking-wide text-gray-500">
                Evidence used
              </div>
              <div className="flex flex-wrap gap-2">
                {response.citations?.length ? (
                  response.citations.map((citation, index) => (
                    <SourcePill
                      key={`${response.query_id}-${index}`}
                      citation={citation}
                      rank={index + 1}
                    />
                  ))
                ) : (
                  <div className="text-sm text-gray-500">No citations returned.</div>
                )}
              </div>
            </div>

            <div className="mt-5 border-t border-gray-200 pt-4">
              <div className="flex flex-wrap gap-2">
                <button
                  type="button"
                  onClick={() => onCopy(message.content)}
                  className="inline-flex items-center gap-2 rounded-lg border border-gray-200 px-3 py-2 text-xs font-medium text-gray-700 hover:bg-gray-50"
                >
                  <Copy className="h-3.5 w-3.5" /> Copy answer
                </button>
              </div>

              {response?.query_id ? (
                <div className="mt-4">
                  <FeedbackWidget queryId={response.query_id} />
                </div>
              ) : null}
            </div>
          </>
        ) : null}
      </div>
    </div>
  );
}

export default function ChatInterface({
  messages,
  draft,
  setDraft,
  isSubmitting,
  onSubmit,
  onReset,
}) {
  const handleKeyDown = (event) => {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      onSubmit();
    }
  };

  const handleNewChat = () => {
    onReset();
  };

  return (
    <div className="flex min-h-0 min-w-0 flex-1 flex-col bg-white">
      <div className="flex-1 overflow-auto px-6 py-6 lg:px-8">
        <div className="mx-auto flex max-w-4xl flex-col gap-6">
          {messages.map((message) =>
            message.role === 'user' ? (
              <div key={message.id} className="flex justify-end">
                <div className="max-w-2xl rounded-2xl bg-slate-900 px-5 py-3 text-sm leading-6 text-white shadow-sm">
                  {message.content}
                </div>
              </div>
            ) : (
              <AssistantMessage
                key={message.id}
                message={message}
                onCopy={(text) => navigator.clipboard.writeText(text)}
              />
            ),
          )}

          {isSubmitting ? (
            <div className="flex justify-start">
              <div className="inline-flex items-center gap-3 rounded-2xl border border-gray-200 bg-white px-4 py-3 text-sm text-gray-600 shadow-sm">
                <Loader2 className="h-4 w-4 animate-spin" />
                Generating grounded answer...
              </div>
            </div>
          ) : null}
        </div>
      </div>

      <div className="border-t border-gray-200 bg-white px-6 py-5 lg:px-8">
        <div className="mx-auto max-w-4xl">
          <div className="rounded-2xl border border-gray-200 bg-gray-50 p-3 shadow-sm">
            <textarea
              value={draft}
              onChange={(event) => setDraft(event.target.value)}
              onKeyDown={handleKeyDown}
              rows={3}
              placeholder="Ask about aircraft families, tradeoffs, performance caveats, or where to verify a claim..."
              className="w-full resize-none border-0 bg-transparent px-2 py-2 text-sm text-gray-900 outline-none placeholder:text-gray-400"
            />

            <div className="mt-3 flex items-center justify-between border-t border-gray-200 pt-3">
              <div className="text-xs text-gray-500">Enter to send · Shift+Enter for newline</div>

              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={handleNewChat}
                  disabled={isSubmitting || !messages.length}
                  className="inline-flex items-center gap-2 rounded-lg border border-gray-200 bg-white px-3 py-2 text-xs font-medium text-gray-700 hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  <RotateCcw className="h-3.5 w-3.5" /> New chat
                </button>

                <button
                  type="button"
                  onClick={onSubmit}
                  disabled={isSubmitting || !draft.trim()}
                  className="inline-flex items-center gap-2 rounded-lg bg-primary-600 px-4 py-2 text-sm font-medium text-white hover:bg-primary-700 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  <Send className="h-4 w-4" /> Ask
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}