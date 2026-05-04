import type { GroundCheckResponse } from '@/api/types';

export const QUERY_HISTORY_STORAGE_KEY = 'saved_query_history';
export const QUERY_HISTORY_UPDATED_EVENT = 'query-history-updated';

const MAX_HISTORY_ITEMS = 50;

export interface SavedQueryHistoryItem {
  queryId: string;
  query: string;
  answer: string;
  timestamp: string;
  confidence: {
    finalScore: number | null;
    tier: 'HIGH' | 'MEDIUM' | 'LOW' | null;
    groundingScore: number | null;
    generationConfidence: number | null;
  };
  metadata: {
    processingTimeMs: number | null;
    retrievedChunks: number | null;
  };
}

function isObject(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null;
}

function normalizeNumber(value: unknown): number | null {
  return typeof value === 'number' && Number.isFinite(value) ? value : null;
}

function normalizeTier(value: unknown): SavedQueryHistoryItem['confidence']['tier'] {
  return value === 'HIGH' || value === 'MEDIUM' || value === 'LOW' ? value : null;
}

function normalizeHistoryItem(value: unknown): SavedQueryHistoryItem | null {
  if (!isObject(value)) return null;

  const confidence = isObject(value.confidence) ? value.confidence : {};
  const metadata = isObject(value.metadata) ? value.metadata : {};

  if (typeof value.queryId !== 'string' || typeof value.query !== 'string') {
    return null;
  }

  return {
    queryId: value.queryId,
    query: value.query,
    answer: typeof value.answer === 'string' ? value.answer : '',
    timestamp:
      typeof value.timestamp === 'string' && value.timestamp
        ? value.timestamp
        : new Date().toISOString(),
    confidence: {
      finalScore: normalizeNumber(confidence.finalScore),
      tier: normalizeTier(confidence.tier),
      groundingScore: normalizeNumber(confidence.groundingScore),
      generationConfidence: normalizeNumber(confidence.generationConfidence),
    },
    metadata: {
      processingTimeMs: normalizeNumber(metadata.processingTimeMs),
      retrievedChunks: normalizeNumber(metadata.retrievedChunks),
    },
  };
}

function emitHistoryUpdated() {
  if (typeof window === 'undefined') return;
  window.dispatchEvent(new CustomEvent(QUERY_HISTORY_UPDATED_EVENT));
}

export function readSavedQueryHistory(): SavedQueryHistoryItem[] {
  if (typeof window === 'undefined') return [];

  try {
    const raw = window.localStorage.getItem(QUERY_HISTORY_STORAGE_KEY);
    if (!raw) return [];

    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];

    return parsed
      .map(normalizeHistoryItem)
      .filter((item): item is SavedQueryHistoryItem => item !== null);
  } catch {
    return [];
  }
}

export function saveQueryToHistory(response: GroundCheckResponse): SavedQueryHistoryItem[] {
  if (typeof window === 'undefined') return [];

  const item: SavedQueryHistoryItem = {
    queryId: response.query_id,
    query: response.query,
    answer: response.answer ?? '',
    timestamp: response.metadata?.timestamp ?? new Date().toISOString(),
    confidence: {
      finalScore: normalizeNumber(response.confidence?.final_score),
      tier: normalizeTier(response.confidence?.tier),
      groundingScore: normalizeNumber(response.confidence?.signals?.grounding_score),
      generationConfidence: normalizeNumber(
        response.confidence?.signals?.gen_confidence_normalized,
      ),
    },
    metadata: {
      processingTimeMs: normalizeNumber(response.metadata?.processing_time_ms),
      retrievedChunks: normalizeNumber(response.metadata?.retrieved_chunks),
    },
  };

  const existing = readSavedQueryHistory().filter((entry) => entry.queryId !== item.queryId);
  const next = [item, ...existing].slice(0, MAX_HISTORY_ITEMS);

  window.localStorage.setItem(QUERY_HISTORY_STORAGE_KEY, JSON.stringify(next));
  emitHistoryUpdated();

  return next;
}
