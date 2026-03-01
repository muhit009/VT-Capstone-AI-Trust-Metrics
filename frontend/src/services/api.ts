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

// ── Example resource functions ────────────────────────────────────────────────

export const metricsService = {
  getAll: () => apiClient.get<Metric[]>('/metrics'),
  getById: (id: string) => apiClient.get<Metric>(`/metrics/${id}`),
  create: (data: Omit<Metric, 'id'>) => apiClient.post<Metric>('/metrics', data),
  update: (id: string, data: Partial<Metric>) => apiClient.put<Metric>(`/metrics/${id}`, data),
  delete: (id: string) => apiClient.delete(`/metrics/${id}`),
};
