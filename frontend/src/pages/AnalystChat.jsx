import { useMemo, useState } from 'react';
import ChatInterface from '@/components/dashboard/ChatInterface';
import RightPanel from '@/components/dashboard/RightPanel';
import { queryService } from '@/services/api';
import { saveQueryToHistory } from '@/services/queryHistory';

function buildAssistantText(response) {
  if (!response) return 'No answer returned.';
  return response.answer || 'No answer returned.';
}

export default function AnalystChat() {
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
      const response = await queryService.submit({ query: trimmed });

      const assistantMessage = {
        id: `assistant-${response.query_id}`,
        role: 'assistant',
        content: buildAssistantText(response),
        response,
      };

      setMessages((current) => [...current, assistantMessage]);
      setLatestResponse(response);
      if (response.status === 'success' || response.status === 'partial_success') {
        saveQueryToHistory(response);
      }
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
    <>
      {requestError ? (
        <div className="border-b border-rose-200 bg-rose-50 px-6 py-3 text-sm text-rose-700">
          {requestError}
        </div>
      ) : null}

      <div className="flex min-h-0 flex-1">
        <ChatInterface
          messages={visibleMessages}
          draft={draft}
          setDraft={setDraft}
          isSubmitting={isSubmitting}
          onSubmit={handleSubmit}
          onReset={handleReset}
        />
        <RightPanel latestResponse={latestResponse} />
      </div>
    </>
  );
}
