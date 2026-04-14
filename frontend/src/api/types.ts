// Backend-aligned API contract for GroundCheck responses.
// Matches backend/response_models.py (schema v1.0.0).

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
  gen_confidence_level: string | null;
  grounding_contribution: number | null;
  gen_conf_contribution: number | null;
}

export interface FusionWeights {
  grounding: number;
  generation: number;
}

export interface ConfidenceData {
  final_score: number;
  tier: 'HIGH' | 'MEDIUM' | 'LOW';
  signals: ConfidenceSignals;
  weights: FusionWeights | null;
  explanation: string;
  warnings: string[] | null;
  degraded: boolean;
}

export interface CitationModel {
  citation_id: string;
  document: string;
  page: number | null;
  section: string | null;
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
  schema_version: string;
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
  error: ErrorInfo | null;
  status: 'success' | 'partial_success' | 'error';
}

export interface FeedbackRequest {
  status: string;
  rationale?: string;
  feedback_rating?: number;
  feedback_comment?: string;
  user_id?: string;
}

export interface FeedbackResponse {
  query_id: string;
  decision_id: string;
  status: string;
  feedback_rating: number | null;
  created_at: string | null;
}
