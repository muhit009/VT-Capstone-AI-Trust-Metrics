import axios from 'axios';
import { ApiError } from './errors';

// ── Axios instance ────────────────────────────────────────────────────────────

export const apiClient = axios.create({
  baseURL: '',
  headers: { 'Content-Type': 'application/json' },
  timeout: 180000, // 3 minutes — Ollama can take 60-90s on first query
});

// ── Request interceptor — attach auth token ───────────────────────────────────

apiClient.interceptors.request.use((config) => {
  const token = localStorage.getItem('token');
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

// ── Response interceptor — unwrap data, map errors to ApiError ────────────────

apiClient.interceptors.response.use(
  (response) => response.data,
  (error: unknown) => {
    const axiosErr = error as {
      response?: {
        status?: number;
        data?: { message?: string; detail?: string; code?: string; details?: unknown };
      };
      message?: string;
    };

    const httpStatus = axiosErr.response?.status;
    const responseData = axiosErr.response?.data;
    const message =
      responseData?.message
      ?? responseData?.detail
      ?? axiosErr.message
      ?? 'An unexpected error occurred';
    const code = responseData?.code;
    const details = responseData?.details;

    return Promise.reject(new ApiError(message, { code, httpStatus, details }));
  },
);
