// Backend-aligned API contract for GroundCheck responses.

export interface Metric {
  id: string;
  name: string;
  value: number;
  category: string;
  description?: string;
}

export interface ConfidenceSignals {
  grounding_score: number | null;
  grounding_num_claims: number | null;
  grounding_supported: number | null;
  gen_confidence_raw: number | null;
  gen_confidence_normalized: number | null;
  gen_confidence_level: 'HIGHLY_CONFIDENT' | 'MODERATE' | 'UNCERTAIN' | null;
  grounding_contribution: number;
  gen_conf_contribution: number;
}

export interface ConfidenceData {
  score: number;
  tier: 'HIGH' | 'MEDIUM' | 'LOW';
  signals: ConfidenceSignals;
  degraded: boolean;
  warning: string | null;
}

export interface ClaimSupport {
  claim_text: string;
  entailment_score: number;
  supported: boolean;
}

export interface CitationSource {
  document_id?: string | null;
  document_name: string;
  section?: string | null;
  page_number?: number | null;
  revision?: string | null;
  last_updated?: string | null;
}

export interface CitationModel {
  rank: number;
  chunk_index: number;
  text: string;
  source: CitationSource;
  retrieval_score: number;
  claim_support?: ClaimSupport[];
}

export interface LatencyBreakdown {
  total: number;
  retrieval?: number | null;
  llm_generation?: number | null;
  grounding_scoring?: number | null;
  gen_confidence_scoring?: number | null;
  fusion?: number | null;
}

export interface ModelInfo {
  provider?: string | null;
  name?: string | null;
  version?: string | null;
  endpoint?: string | null;
}

export interface RetrieverInfo {
  top_k?: number | null;
  embedding_model?: string | null;
  vector_store?: string | null;
}

export interface ResponseMetadata {
  latency_ms: LatencyBreakdown;
  model: ModelInfo;
  retriever: RetrieverInfo;
}

export interface ErrorInfo {
  code: string;
  message: string;
  details?: unknown;
  retryable?: boolean;
  frontend_action?: string;
  http_status?: number;
}

export interface GroundCheckResponse {
  status: 'ok';
  request_id: string;
  timestamp: string;
  query: string;
  answer: string;
  confidence: ConfidenceData;
  citations: CitationModel[];
  metadata: ResponseMetadata;
}

export interface GroundCheckErrorResponse {
  status: 'error';
  request_id: string;
  timestamp: string;
  error: ErrorInfo;
}

export interface RAGInferenceRequest {
  query: string;
  top_k?: number;
  max_new_tokens?: number;
  temperature?: number;
  top_p?: number;
  repetition_penalty?: number;
}

export type FeedbackRating = 'helpful' | 'unhelpful';

export interface FeedbackRequest {
  query_id: string;
  rating: FeedbackRating;
  comment?: string;
}

export interface FeedbackResponse {
  success: boolean;
  message: string;
}