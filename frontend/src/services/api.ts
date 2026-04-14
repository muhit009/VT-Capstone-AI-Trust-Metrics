export { apiClient } from '../api/client';
export type {
  Metric,
  ConfidenceSignals,
  ConfidenceData,
  ClaimSupport,
  CitationSource,
  CitationModel,
  LatencyBreakdown,
  ModelInfo,
  RetrieverInfo,
  ResponseMetadata,
  ErrorInfo,
  GroundCheckResponse,
  GroundCheckErrorResponse,
  RAGInferenceRequest,
  FeedbackRating,
  FeedbackRequest,
  FeedbackResponse,
} from '../api/types';

import { apiClient } from '../api/client';
import type {
  Metric,
  GroundCheckResponse,
  RAGInferenceRequest,
  FeedbackRequest,
  FeedbackResponse,
} from '../api/types';

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

export const feedbackService = {
  submit: (request: FeedbackRequest) =>
    apiClient.post('/v1/feedback', request) as Promise<FeedbackResponse>,
};