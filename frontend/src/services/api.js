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
  (error) => {
    const message = error.response?.data?.message ?? error.message ?? 'An unexpected error occurred';
    return Promise.reject(new Error(message));
  }
);

// ── Example resource functions ────────────────────────────────────────────────

export const metricsService = {
  getAll: () => apiClient.get('/metrics'),
  getById: (id) => apiClient.get(`/metrics/${id}`),
  create: (data) => apiClient.post('/metrics', data),
  update: (id, data) => apiClient.put(`/metrics/${id}`, data),
  delete: (id) => apiClient.delete(`/metrics/${id}`),
};
