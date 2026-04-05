// ── Core domain types ─────────────────────────────────────────────────────────

export interface Metric {
  id: string;
  name: string;
  value: number;
  description?: string;
}

// ── GroundCheck types (aligned with OpenAPI spec) ────────────────────────────

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
