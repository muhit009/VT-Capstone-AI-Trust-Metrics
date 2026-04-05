// ── ApiError ──────────────────────────────────────────────────────────────────

export class ApiError extends Error {
  readonly code: string;
  readonly httpStatus?: number;
  readonly details?: unknown;

  constructor(
    message: string,
    options?: { code?: string; httpStatus?: number; details?: unknown },
  ) {
    super(message);
    this.name = 'ApiError';
    this.code = options?.code ?? 'UNKNOWN';
    this.httpStatus = options?.httpStatus;
    this.details = options?.details;
  }
}

// ── Type guards & parsers ─────────────────────────────────────────────────────

export function isApiError(error: unknown): error is ApiError {
  return error instanceof ApiError;
}

/** Normalize any thrown value into an ApiError. */
export function parseApiError(error: unknown): ApiError {
  if (isApiError(error)) return error;
  if (error instanceof Error) return new ApiError(error.message);
  return new ApiError('An unexpected error occurred');
}

/** Extract a display-safe message from any thrown value. */
export function getErrorMessage(error: unknown): string {
  if (error instanceof Error) return error.message;
  return 'An unexpected error occurred';
}

// ── Retry logic ───────────────────────────────────────────────────────────────

const RETRYABLE_HTTP_STATUSES = new Set([429, 500, 502, 503, 504]);

function isRetryableError(error: unknown): boolean {
  if (isApiError(error) && error.httpStatus !== undefined) {
    return RETRYABLE_HTTP_STATUSES.has(error.httpStatus);
  }
  return false;
}

interface RetryOptions {
  /** Maximum number of retry attempts (default: 3). */
  retries?: number;
  /** Base delay in ms; each retry multiplies by attempt number (default: 500). */
  baseDelayMs?: number;
}

/**
 * Wraps an async function with exponential-backoff retry on retryable errors
 * (429, 5xx). Non-retryable errors are rethrown immediately.
 */
export async function withRetry<T>(fn: () => Promise<T>, options: RetryOptions = {}): Promise<T> {
  const { retries = 3, baseDelayMs = 500 } = options;

  for (let attempt = 0; attempt <= retries; attempt++) {
    try {
      return await fn();
    } catch (error) {
      const isLast = attempt === retries;
      if (isLast || !isRetryableError(error)) throw error;
      await new Promise<void>((resolve) => setTimeout(resolve, baseDelayMs * (attempt + 1)));
    }
  }

  // Unreachable — TypeScript needs the explicit throw.
  throw new ApiError('Retry attempts exhausted');
}
