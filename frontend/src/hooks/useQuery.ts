import { useState, useEffect, useCallback, useRef, type DependencyList } from 'react';
import { parseApiError, type ApiError } from '../api/errors';

// ── useQuery ──────────────────────────────────────────────────────────────────

interface UseQueryOptions<T> {
  /** Set to false to skip the initial fetch (default: true). */
  enabled?: boolean;
  onSuccess?: (data: T) => void;
  onError?: (error: ApiError) => void;
}

export interface UseQueryResult<T> {
  data: T | null;
  isLoading: boolean;
  error: ApiError | null;
  /** Trigger a manual re-fetch without changing deps. */
  refetch: () => void;
}

/**
 * Fetches data on mount and whenever `deps` change. Cancels in-flight requests
 * when deps change or the component unmounts via AbortController.
 *
 * @example
 * const { data, isLoading, error } = useQuery(
 *   (signal) => fetch('/api/things', { signal }).then(r => r.json()),
 *   []
 * );
 */
export function useQuery<T>(
  queryFn: (signal: AbortSignal) => Promise<T>,
  deps: DependencyList,
  options: UseQueryOptions<T> = {},
): UseQueryResult<T> {
  const [data, setData] = useState<T | null>(null);
  const [isLoading, setIsLoading] = useState(options.enabled !== false);
  const [error, setError] = useState<ApiError | null>(null);
  const [refetchKey, setRefetchKey] = useState(0);

  // Keep latest options in a ref so the effect doesn't need them as deps.
  const optionsRef = useRef(options);
  optionsRef.current = options;

  // Keep latest queryFn in a ref to avoid stale closure issues.
  const queryFnRef = useRef(queryFn);
  queryFnRef.current = queryFn;

  useEffect(() => {
    if (optionsRef.current.enabled === false) {
      setIsLoading(false);
      return;
    }

    const controller = new AbortController();
    setIsLoading(true);
    setError(null);

    queryFnRef.current(controller.signal)
      .then((result) => {
        if (controller.signal.aborted) return;
        setData(result);
        setIsLoading(false);
        optionsRef.current.onSuccess?.(result);
      })
      .catch((err: unknown) => {
        if (controller.signal.aborted) return;
        const apiError = parseApiError(err);
        setIsLoading(false);
        setError(apiError);
        optionsRef.current.onError?.(apiError);
      });

    return () => controller.abort();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, refetchKey]);

  const refetch = useCallback(() => setRefetchKey((k) => k + 1), []);

  return { data, isLoading, error, refetch };
}

// ── useMutation ───────────────────────────────────────────────────────────────

interface UseMutationOptions<TResult> {
  onSuccess?: (data: TResult) => void;
  onError?: (error: ApiError) => void;
}

export interface UseMutationResult<TArgs, TResult> {
  mutate: (args: TArgs) => Promise<TResult>;
  isLoading: boolean;
  error: ApiError | null;
  data: TResult | null;
  /** Clear loading / error / data back to initial state. */
  reset: () => void;
}

/**
 * Manages the lifecycle of a mutation (POST / PUT / DELETE). Call `mutate()`
 * to trigger the operation. In-flight requests are cancelled on unmount.
 *
 * @example
 * const { mutate, isLoading, error } = useMutation(queryService.submit);
 * await mutate({ query: 'What is yield strength?' });
 */
export function useMutation<TArgs, TResult>(
  mutationFn: (args: TArgs) => Promise<TResult>,
  options: UseMutationOptions<TResult> = {},
): UseMutationResult<TArgs, TResult> {
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<ApiError | null>(null);
  const [data, setData] = useState<TResult | null>(null);

  const optionsRef = useRef(options);
  optionsRef.current = options;

  const mutationFnRef = useRef(mutationFn);
  mutationFnRef.current = mutationFn;

  // Track whether the component is still mounted to avoid state updates after unmount.
  const mountedRef = useRef(true);
  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
    };
  }, []);

  const mutate = useCallback(async (args: TArgs): Promise<TResult> => {
    setIsLoading(true);
    setError(null);

    try {
      const result = await mutationFnRef.current(args);
      if (mountedRef.current) {
        setData(result);
        setIsLoading(false);
        optionsRef.current.onSuccess?.(result);
      }
      return result;
    } catch (err: unknown) {
      if (mountedRef.current) {
        const apiError = parseApiError(err);
        setIsLoading(false);
        setError(apiError);
        optionsRef.current.onError?.(apiError);
      }
      throw err;
    }
  }, []);

  const reset = useCallback(() => {
    setIsLoading(false);
    setError(null);
    setData(null);
  }, []);

  return { mutate, isLoading, error, data, reset };
}
