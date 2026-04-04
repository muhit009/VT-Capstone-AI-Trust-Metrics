import axios from 'axios';

export const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL ?? '/api',
  headers: {
    'Content-Type': 'application/json',
  },
});

// Request interceptor — attach auth token if present
apiClient.interceptors.request.use((config) => {
  const token = localStorage.getItem('token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Response interceptor — unwrap data, handle global errors
apiClient.interceptors.response.use(
  (response) => response.data,
  (error: unknown) => {
    const err = error as { response?: { data?: { message?: string } }; message?: string };
    const message = err.response?.data?.message ?? err.message ?? 'An unexpected error occurred';
    return Promise.reject(new Error(message));
  }
);

// ── Resource service types ────────────────────────────────────────────────────

export interface Metric {
  id: string;
  name: string;
  value: number;
  description?: string;
}

// ── GroundCheck types (from OpenAPI spec) ─────────────────────────────────────

export interface ConfidenceSignals {
  grounding_score: number | null;
  generation_confidence: number | null;
}

export interface FusionWeights {
  grounding: number;
  generation: number;
}

export interface ConfidenceData {
  final_score: number;
  tier: 'HIGH' | 'MEDIUM' | 'LOW';
  signals: ConfidenceSignals;
  weights?: FusionWeights;
  explanation: string;
  warnings: string[] | null;
  degraded: boolean;
}

export interface CitationModel {
  citation_id: string;
  document: string;
  page: number | null;
  section?: string | null;
  chunk_id: string;
  similarity_score: number;
  entailment_score: number | null;
  text_excerpt: string;
}

export interface ResponseMetadata {
  model: string;
  nli_model: string | null;
  timestamp: string;
  processing_time_ms: number;
  retrieved_chunks: number | null;
  schema_version?: string;
}

export interface ErrorInfo {
  code: string;
  message: string;
  severity: 'warning' | 'error';
  details?: string | null;
}

export interface GroundCheckResponse {
  query_id: string;
  query: string;
  answer: string | null;
  confidence: ConfidenceData;
  citations: CitationModel[];
  metadata: ResponseMetadata;
  error?: ErrorInfo;
  status: 'success' | 'partial_success' | 'error';
}

export interface RAGInferenceRequest {
  query: string;
  top_k?: number;
  max_new_tokens?: number;
  temperature?: number;
  top_p?: number;
  repetition_penalty?: number;
}

// ── Example resource functions ────────────────────────────────────────────────

export const metricsService = {
  getAll: () => apiClient.get<Metric[]>('/metrics'),
  getById: (id: string) => apiClient.get<Metric>(`/metrics/${id}`),
  create: (data: Omit<Metric, 'id'>) => apiClient.post<Metric>('/metrics', data),
  update: (id: string, data: Partial<Metric>) => apiClient.put<Metric>(`/metrics/${id}`, data),
  delete: (id: string) => apiClient.delete(`/metrics/${id}`),
};

export const queryService = {
  submit: (request: RAGInferenceRequest) =>
    apiClient.post('/v1/rag/query', request) as Promise<GroundCheckResponse>,
};

// ── Feedback types ────────────────────────────────────────────────────────────

export type FeedbackRating = 'helpful' | 'unhelpful';

export interface FeedbackRequest {
  query_id: string;
  rating: FeedbackRating;
  comment?: string;
}

export interface FeedbackResponse {
  feedback_id: string;
  status: string;
}

export const feedbackService = {
  submit: (request: FeedbackRequest) =>
    apiClient.post('/v1/feedback', request) as Promise<FeedbackResponse>,
};
