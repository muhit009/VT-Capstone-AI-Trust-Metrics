import type { GroundCheckResponse } from '@/api/types';

export const CHAT_SESSIONS_STORAGE_KEY = 'chat_sessions';
export const ACTIVE_CHAT_SESSION_STORAGE_KEY = 'active_chat_session';
export const CHAT_SESSIONS_UPDATED_EVENT = 'chat-sessions-updated';

const MAX_SESSIONS = 25;

export interface StoredChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  response: GroundCheckResponse | null;
}

export interface ChatSessionRecord {
  id: string;
  title: string;
  createdAt: string;
  updatedAt: string;
  messages: StoredChatMessage[];
}

function isObject(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null;
}

function toStoredChatMessage(value: unknown): StoredChatMessage | null {
  if (!isObject(value)) return null;
  if (value.role !== 'user' && value.role !== 'assistant') return null;
  if (typeof value.id !== 'string' || typeof value.content !== 'string') return null;

  return {
    id: value.id,
    role: value.role,
    content: value.content,
    response: isObject(value.response) ? (value.response as unknown as GroundCheckResponse) : null,
  };
}

function normalizeTimestamp(value: unknown, fallback: string) {
  return typeof value === 'string' && value ? value : fallback;
}

function buildSessionTitle(messages: StoredChatMessage[]) {
  const firstUserMessage = messages.find((message) => message.role === 'user')?.content?.trim();
  if (!firstUserMessage) return 'New chat';

  return firstUserMessage.length > 56
    ? `${firstUserMessage.slice(0, 53).trimEnd()}...`
    : firstUserMessage;
}

function normalizeSession(value: unknown): ChatSessionRecord | null {
  if (!isObject(value) || typeof value.id !== 'string') return null;

  const parsedMessages = Array.isArray(value.messages)
    ? value.messages
        .map(toStoredChatMessage)
        .filter((message): message is StoredChatMessage => message !== null)
    : [];

  const fallbackTimestamp = new Date().toISOString();

  return {
    id: value.id,
    title:
      typeof value.title === 'string' && value.title
        ? value.title
        : buildSessionTitle(parsedMessages),
    createdAt: normalizeTimestamp(value.createdAt, fallbackTimestamp),
    updatedAt: normalizeTimestamp(value.updatedAt, fallbackTimestamp),
    messages: parsedMessages,
  };
}

function emitSessionsUpdated() {
  if (typeof window === 'undefined') return;
  window.dispatchEvent(new CustomEvent(CHAT_SESSIONS_UPDATED_EVENT));
}

function writeChatSessions(sessions: ChatSessionRecord[]) {
  if (typeof window === 'undefined') return;

  window.localStorage.setItem(CHAT_SESSIONS_STORAGE_KEY, JSON.stringify(sessions));
  emitSessionsUpdated();
}

export function createChatSessionId() {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return crypto.randomUUID();
  }

  return `session-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
}

export function readChatSessions(): ChatSessionRecord[] {
  if (typeof window === 'undefined') return [];

  try {
    const raw = window.localStorage.getItem(CHAT_SESSIONS_STORAGE_KEY);
    if (!raw) return [];

    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];

    return parsed
      .map(normalizeSession)
      .filter((session): session is ChatSessionRecord => session !== null)
      .sort((left, right) => right.updatedAt.localeCompare(left.updatedAt));
  } catch {
    return [];
  }
}

export function readChatSession(sessionId: string) {
  return readChatSessions().find((session) => session.id === sessionId) ?? null;
}

export function setActiveChatSessionId(sessionId: string | null) {
  if (typeof window === 'undefined') return;

  if (sessionId) {
    window.localStorage.setItem(ACTIVE_CHAT_SESSION_STORAGE_KEY, sessionId);
  } else {
    window.localStorage.removeItem(ACTIVE_CHAT_SESSION_STORAGE_KEY);
  }
}

export function readActiveChatSessionId() {
  if (typeof window === 'undefined') return null;
  return window.localStorage.getItem(ACTIVE_CHAT_SESSION_STORAGE_KEY);
}

export function saveChatSession(session: {
  id: string;
  createdAt?: string;
  messages: StoredChatMessage[];
}) {
  if (typeof window === 'undefined') return [];

  const allSessions = readChatSessions();
  const existingSession = allSessions.find((entry) => entry.id === session.id) ?? null;
  const existing = allSessions.filter((entry) => entry.id !== session.id);
  const createdAt = session.createdAt ?? existingSession?.createdAt;
  const timestamp = new Date().toISOString();

  const nextRecord: ChatSessionRecord = {
    id: session.id,
    title: buildSessionTitle(session.messages),
    createdAt: createdAt ?? timestamp,
    updatedAt: timestamp,
    messages: session.messages,
  };

  const next = [nextRecord, ...existing].slice(0, MAX_SESSIONS);
  writeChatSessions(next);
  setActiveChatSessionId(session.id);

  return next;
}
