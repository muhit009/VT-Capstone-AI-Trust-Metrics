import { useEffect, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import ChatInterface from '@/components/dashboard/ChatInterface';
import RightPanel from '@/components/dashboard/RightPanel';
import { queryService } from '@/services/api';
import { saveQueryToHistory } from '@/services/queryHistory';
import {
  createChatSessionId,
  readActiveChatSessionId,
  readChatSession,
  readChatSessions,
  saveChatSession,
  setActiveChatSessionId,
} from '@/services/chatSessions';

function buildAssistantText(response) {
  if (!response) return 'No answer returned.';
  return prepareAssistantMarkdown(response.answer || 'No answer returned.');
}

function prepareAssistantMarkdown(value) {
  const normalized = String(value ?? '')
    .replace(/\r\n/g, '\n')
    .replace(/\n{2,}EVIDENCE USED[\s\S]*$/i, '')
    .replace(/\n{3,}/g, '\n\n')
    .trim();

  return normalized || 'No answer returned.';
}

function getLatestResponse(messages) {
  for (let index = messages.length - 1; index >= 0; index -= 1) {
    if (messages[index].role === 'assistant' && messages[index].response) {
      return messages[index].response;
    }
  }

  return null;
}

export default function AnalystChat() {
  const [searchParams, setSearchParams] = useSearchParams();
  const requestedSessionId = searchParams.get('session');
  const [activeSessionId, setActiveSessionId] = useState(null);
  const [sessionCreatedAt, setSessionCreatedAt] = useState(null);
  const [messages, setMessages] = useState([]);
  const [draft, setDraft] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [latestResponse, setLatestResponse] = useState(null);
  const [requestError, setRequestError] = useState(null);

  useEffect(() => {
    const availableSessions = readChatSessions();
    const fallbackSessionId = requestedSessionId
      || readActiveChatSessionId()
      || availableSessions[0]?.id
      || createChatSessionId();

    const storedSession = readChatSession(fallbackSessionId);

    if (storedSession) {
      setActiveSessionId(storedSession.id);
      setSessionCreatedAt(storedSession.createdAt);
      setMessages(storedSession.messages);
      setLatestResponse(getLatestResponse(storedSession.messages));
      setRequestError(null);
      setDraft('');
      setActiveChatSessionId(storedSession.id);

      if (!requestedSessionId) {
        setSearchParams({ session: storedSession.id }, { replace: true });
      }

      return;
    }

    setActiveSessionId(fallbackSessionId);
    setSessionCreatedAt(null);
    setMessages([]);
    setLatestResponse(null);
    setRequestError(null);
    setDraft('');
    setActiveChatSessionId(fallbackSessionId);

    if (requestedSessionId !== fallbackSessionId) {
      setSearchParams({ session: fallbackSessionId }, { replace: true });
    }
  }, [requestedSessionId, setSearchParams]);

  const persistSession = (sessionId, nextMessages, createdAt = sessionCreatedAt) => {
    const sessions = saveChatSession({
      id: sessionId,
      createdAt: createdAt ?? undefined,
      messages: nextMessages,
    });
    const savedSession = sessions.find((session) => session.id === sessionId) ?? null;

    if (savedSession) {
      setSessionCreatedAt(savedSession.createdAt);
    }
  };

  const handleSubmit = async () => {
    const trimmed = draft.trim();
    const sessionId = activeSessionId ?? createChatSessionId();
    if (!trimmed || isSubmitting) return;

    const userMessage = {
      id: `user-${Date.now()}`,
      role: 'user',
      content: trimmed,
      response: null,
    };
    const nextMessages = [...messages, userMessage];

    setActiveSessionId(sessionId);
    setMessages(nextMessages);
    setDraft('');
    setIsSubmitting(true);
    setRequestError(null);
    setActiveChatSessionId(sessionId);
    persistSession(sessionId, nextMessages);

    if (requestedSessionId !== sessionId) {
      setSearchParams({ session: sessionId }, { replace: true });
    }

    try {
      const response = await queryService.submit({ query: trimmed, session_id: sessionId });

      const assistantMessage = {
        id: `assistant-${response.query_id}`,
        role: 'assistant',
        content: buildAssistantText(response),
        response,
      };
      const completedMessages = [...nextMessages, assistantMessage];

      setMessages(completedMessages);
      setLatestResponse(response);
      persistSession(sessionId, completedMessages);
      if (response.status === 'success' || response.status === 'partial_success') {
        saveQueryToHistory(response);
      }
    } catch (error) {
      const message =
        error instanceof Error ? error.message : 'Unable to get an answer right now.';

      setRequestError(message);
      const errorMessages = [
        ...nextMessages,
        {
          id: `assistant-error-${Date.now()}`,
          role: 'assistant',
          content:
            'I could not generate a grounded answer for that request. Please try rephrasing the question or check whether the backend is available.',
          response: null,
        },
      ];
      setMessages(errorMessages);
      persistSession(sessionId, errorMessages);
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleReset = () => {
    const nextSessionId = createChatSessionId();
    setActiveSessionId(nextSessionId);
    setSessionCreatedAt(null);
    setMessages([]);
    setLatestResponse(null);
    setRequestError(null);
    setDraft('');
    setActiveChatSessionId(nextSessionId);
    setSearchParams({ session: nextSessionId }, { replace: true });
  };

  return (
    <>
      {requestError ? (
        <div className="border-b border-rose-200 bg-rose-50 px-6 py-3 text-sm text-rose-700">
          {requestError}
        </div>
      ) : null}

      <div className="flex min-h-0 flex-1">
        <ChatInterface
          messages={messages}
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
