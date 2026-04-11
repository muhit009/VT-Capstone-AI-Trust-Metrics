import { useMemo, useState } from 'react';
import Sidebar from '@/components/dashboard/Sidebar';
import TopBar from '@/components/dashboard/TopBar';
import ChatInterface from '@/components/dashboard/ChatInterface';
import RightPanel from '@/components/dashboard/RightPanel';
import SettingsPanel from '@/components/dashboard/SettingsPanel';
import { queryService } from '@/services/api';

function buildAssistantText(response) {
  if (!response) return 'No answer returned.';
  return response.answer || 'No answer returned.';
}

export default function AnalystChat() {
  const [activeView, setActiveView] = useState('chat');
  const [messages, setMessages] = useState([]);
  const [draft, setDraft] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [latestResponse, setLatestResponse] = useState(null);
  const [requestError, setRequestError] = useState(null);

  const handleSubmit = async () => {
    const trimmed = draft.trim();
    if (!trimmed || isSubmitting) return;

    const userMessage = {
      id: `user-${Date.now()}`,
      role: 'user',
      content: trimmed,
    };

    setMessages((current) => [...current, userMessage]);
    setDraft('');
    setIsSubmitting(true);
    setRequestError(null);

    try {
      const response = {
  request_id: `mock-${Date.now()}`,
  timestamp: new Date().toISOString(),
  answer:
    'Fuel efficiency comparisons should be normalized by stage length, payload, reserves, and seating assumptions before comparing aircraft families.',
  confidence: {
    score: 78,
    tier: 'MEDIUM',
    degraded: false,
    warning:
      'This answer is useful, but comparisons depend strongly on mission assumptions.',
    signals: {
      grounding_score: 0.72,
      grounding_num_claims: 5,
      grounding_supported: 4,
      gen_confidence_raw: 0.74,
      gen_confidence_normalized: 0.74,
      gen_confidence_level: 'MODERATE',
      grounding_contribution: 0.6,
      gen_conf_contribution: 0.4,
    },
  },
  citations: [
    {
      rank: 1,
      retrieval_score: 0.91,
      text: 'Fuel burn comparisons should be normalized by stage length and payload before comparing aircraft.',
      source: {
        document_name: 'Aircraft Performance Primer',
        section: '2.1',
        page_number: 12,
        revision: 'Rev B',
      },
    },
    {
      rank: 2,
      retrieval_score: 0.84,
      text: 'Mission length changes the share of climb versus cruise, which affects direct fuel-burn comparisons.',
      source: {
        document_name: 'Mission Efficiency Notes',
        section: 'Performance comparison guidance',
        page_number: 4,
        revision: '2025.1',
      },
    },
  ],
  metadata: {
    latency_ms: {
      total: 812,
      retrieval: 120,
      llm_generation: 450,
      grounding_scoring: 90,
      gen_confidence_scoring: 80,
      fusion: 72,
    },
    model: {
      name: 'Grounded RAG Pipeline',
      provider: 'Internal',
      version: 'dev',
      endpoint: '/v1/rag/query',
    },
    retriever: {
      top_k: 5,
      embedding_model: 'text-embedding-preview',
      vector_store: 'pgvector',
    },
  },
};

      const assistantMessage = {
        id: `assistant-${response.request_id}`,
        role: 'assistant',
        content: buildAssistantText(response),
        response,
      };

      setMessages((current) => [...current, assistantMessage]);
      setLatestResponse(response);
    } catch (error) {
      const message =
        error instanceof Error ? error.message : 'Unable to get an answer right now.';

      setRequestError(message);
      setMessages((current) => [
        ...current,
        {
          id: `assistant-error-${Date.now()}`,
          role: 'assistant',
          content:
            'I could not generate a grounded answer for that request. Please try rephrasing the question or check whether the backend is available.',
          response: null,
        },
      ]);
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleReset = () => {
    setMessages([]);
    setLatestResponse(null);
    setRequestError(null);
    setDraft('');
  };

  const visibleMessages = useMemo(() => messages, [messages]);

  return (
    <div className="flex h-screen w-screen overflow-hidden bg-gray-50">
      <Sidebar activeView={activeView} onChangeView={setActiveView} />

      <div className="flex min-w-0 flex-1 flex-col">
        <TopBar />

        {requestError && activeView === 'chat' ? (
          <div className="border-b border-rose-200 bg-rose-50 px-6 py-3 text-sm text-rose-700">
            {requestError}
          </div>
        ) : null}

        <div className="flex min-h-0 flex-1">
          {activeView === 'chat' ? (
            <>
              <ChatInterface
                messages={visibleMessages}
                draft={draft}
                setDraft={setDraft}
                isSubmitting={isSubmitting}
                onSubmit={handleSubmit}
                onReset={handleReset}
              />
              <RightPanel latestResponse={latestResponse} />
            </>
          ) : (
            <SettingsPanel />
          )}
        </div>
      </div>
    </div>
  );
}