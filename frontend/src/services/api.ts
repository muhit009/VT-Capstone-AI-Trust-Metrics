export { apiClient } from '../api/client';
export type {
  Metric,
  ConfidenceSignals,
  ConfidenceData,
  CitationModel,
  ResponseMetadata,
  ErrorInfo,
  GroundCheckResponse,
  FeedbackRequest,
  FeedbackResponse,
} from '../api/types';

import { apiClient } from '../api/client';
import type {
  Metric,
  GroundCheckResponse,
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
  submit: (request: { query: string; top_k?: number }) =>
    apiClient.post('/api/v1/query', request) as Promise<GroundCheckResponse>,
};

export const feedbackService = {
  submit: (queryId: string, payload: { status: string; feedback_rating?: number; feedback_comment?: string }) =>
    apiClient.post(`/api/v1/feedback/${queryId}`, payload) as Promise<FeedbackResponse>,
};