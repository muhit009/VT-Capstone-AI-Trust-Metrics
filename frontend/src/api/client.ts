import axios from 'axios';
import { ApiError } from './errors';

// ── Axios instance ────────────────────────────────────────────────────────────

export const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL ?? '/api',
  headers: { 'Content-Type': 'application/json' },
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
      response?: { status?: number; data?: { message?: string; code?: string; details?: unknown } };
      message?: string;
    };

    const httpStatus = axiosErr.response?.status;
    const responseData = axiosErr.response?.data;
    const message = responseData?.message ?? axiosErr.message ?? 'An unexpected error occurred';
    const code = responseData?.code;
    const details = responseData?.details;

    return Promise.reject(new ApiError(message, { code, httpStatus, details }));
  },
);
