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

export interface DocumentsListResponse {
  documents: string[];
  total: number;
}

export interface DocumentUploadResponse {
  filename: string;
  file_type: string;
  page_count: number;
  chunk_count: number;
  embedding_dim: number;
  status: string;
}

export interface DocumentDeleteResponse {
  filename: string;
  chunks_deleted: number;
  status: string;
}

export const documentsService = {
  list: () => apiClient.get('/v1/documents/') as Promise<DocumentsListResponse>,
  upload: (file: File) => {
    const formData = new FormData();
    formData.append('file', file);

    return apiClient.post('/v1/documents/upload', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    }) as Promise<DocumentUploadResponse>;
  },
  delete: (filename: string) =>
    apiClient.delete(
      `/v1/documents/${encodeURIComponent(filename)}`,
    ) as Promise<DocumentDeleteResponse>,
};

export interface WeightResponse {
  weight_grounding:  number;
  weight_generation: number;
  is_default:        boolean;
  updated_at?:       string | null;
}

export const weightsService = {
  get:   ()                                                                => apiClient.get<WeightResponse>('/api/v1/weights'),
  save:  (weight_grounding: number, weight_generation: number)             => apiClient.put<WeightResponse>('/api/v1/weights', { weight_grounding, weight_generation }),
  reset: ()                                                                => apiClient.delete<WeightResponse>('/api/v1/weights'),
};
