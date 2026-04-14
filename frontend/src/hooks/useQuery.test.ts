import { renderHook, act, waitFor } from '@testing-library/react';
import { vi, describe, it, expect, beforeEach, afterEach } from 'vitest';
import { useQuery, useMutation } from './useQuery';
import { ApiError } from '../api/errors';

// ── helpers ───────────────────────────────────────────────────────────────────

function resolvedFn<T>(value: T) {
  return (_signal: AbortSignal) => Promise.resolve(value);
}

function rejectedFn(message: string) {
  return (_signal: AbortSignal) => Promise.reject(new Error(message));
}

// ── useQuery ──────────────────────────────────────────────────────────────────

describe('useQuery', () => {
  it('starts in loading state', () => {
    const { result } = renderHook(() => useQuery(resolvedFn('data'), []));
    expect(result.current.isLoading).toBe(true);
    expect(result.current.data).toBeNull();
    expect(result.current.error).toBeNull();
  });

  it('resolves with data on success', async () => {
    const { result } = renderHook(() => useQuery(resolvedFn({ id: 1 }), []));
    await waitFor(() => expect(result.current.isLoading).toBe(false));
    expect(result.current.data).toEqual({ id: 1 });
    expect(result.current.error).toBeNull();
  });

  it('sets error state on failure', async () => {
    const { result } = renderHook(() => useQuery(rejectedFn('Not found'), []));
    await waitFor(() => expect(result.current.isLoading).toBe(false));
    expect(result.current.data).toBeNull();
    expect(result.current.error).toBeInstanceOf(ApiError);
    expect(result.current.error?.message).toBe('Not found');
  });

  it('calls onSuccess callback with data', async () => {
    const onSuccess = vi.fn();
    renderHook(() => useQuery(resolvedFn(42), [], { onSuccess }));
    await waitFor(() => expect(onSuccess).toHaveBeenCalledWith(42));
  });

  it('calls onError callback on failure', async () => {
    const onError = vi.fn();
    renderHook(() => useQuery(rejectedFn('Oops'), [], { onError }));
    await waitFor(() => expect(onError).toHaveBeenCalledWith(expect.any(ApiError)));
  });

  it('does not fetch when enabled is false', async () => {
    const queryFn = vi.fn().mockResolvedValue('x');
    const { result } = renderHook(() => useQuery(queryFn, [], { enabled: false }));
    // Give it a tick to process
    await act(async () => {});
    expect(queryFn).not.toHaveBeenCalled();
    expect(result.current.isLoading).toBe(false);
  });

  it('re-fetches when refetch() is called', async () => {
    const queryFn = vi.fn().mockResolvedValue('result');
    const { result } = renderHook(() => useQuery(queryFn, []));
    await waitFor(() => expect(result.current.isLoading).toBe(false));

    act(() => result.current.refetch());

    await waitFor(() => expect(queryFn).toHaveBeenCalledTimes(2));
    expect(result.current.data).toBe('result');
  });

  it('re-fetches when deps change', async () => {
    const queryFn = vi.fn().mockResolvedValue('v1');
    let dep = 'a';
    const { result, rerender } = renderHook(() => useQuery(queryFn, [dep]));
    await waitFor(() => expect(result.current.isLoading).toBe(false));

    dep = 'b';
    queryFn.mockResolvedValue('v2');
    rerender();

    await waitFor(() => expect(result.current.data).toBe('v2'));
    expect(queryFn).toHaveBeenCalledTimes(2);
  });

  it('passes an AbortSignal to the query function', async () => {
    const queryFn = vi.fn().mockImplementation((_signal: AbortSignal) => Promise.resolve('ok'));
    renderHook(() => useQuery(queryFn, []));
    await waitFor(() => expect(queryFn).toHaveBeenCalledWith(expect.any(AbortSignal)));
  });

  it('aborts in-flight request on unmount', async () => {
    let capturedSignal!: AbortSignal;
    const queryFn = vi.fn().mockImplementation((signal: AbortSignal) => {
      capturedSignal = signal;
      return new Promise(() => {}); // never resolves
    });

    const { unmount } = renderHook(() => useQuery(queryFn, []));
    await act(async () => {});
    expect(capturedSignal.aborted).toBe(false);

    unmount();
    expect(capturedSignal.aborted).toBe(true);
  });
});

// ── useMutation ───────────────────────────────────────────────────────────────

describe('useMutation', () => {
  beforeEach(() => vi.clearAllMocks());
  afterEach(() => vi.restoreAllMocks());

  it('starts in idle state', () => {
    const { result } = renderHook(() => useMutation(vi.fn()));
    expect(result.current.isLoading).toBe(false);
    expect(result.current.data).toBeNull();
    expect(result.current.error).toBeNull();
  });

  it('sets loading while mutation is pending', async () => {
    let resolve!: (v: string) => void;
    const mutationFn = vi.fn().mockReturnValue(new Promise<string>((r) => { resolve = r; }));
    const { result } = renderHook(() => useMutation(mutationFn));

    act(() => { result.current.mutate('input'); });
    expect(result.current.isLoading).toBe(true);

    act(() => resolve('done'));
    await waitFor(() => expect(result.current.isLoading).toBe(false));
  });

  it('resolves data on success', async () => {
    const mutationFn = vi.fn().mockResolvedValue({ id: 'abc' });
    const { result } = renderHook(() => useMutation(mutationFn));

    await act(async () => { await result.current.mutate({}); });

    expect(result.current.data).toEqual({ id: 'abc' });
    expect(result.current.error).toBeNull();
    expect(result.current.isLoading).toBe(false);
  });

  it('sets error state on failure', async () => {
    const mutationFn = vi.fn().mockRejectedValue(new Error('Server error'));
    const { result } = renderHook(() => useMutation(mutationFn));

    await act(async () => {
      await result.current.mutate({}).catch(() => {});
    });

    expect(result.current.error).toBeInstanceOf(ApiError);
    expect(result.current.error?.message).toBe('Server error');
    expect(result.current.isLoading).toBe(false);
  });

  it('calls onSuccess with result', async () => {
    const onSuccess = vi.fn();
    const mutationFn = vi.fn().mockResolvedValue('ok');
    const { result } = renderHook(() => useMutation(mutationFn, { onSuccess }));

    await act(async () => { await result.current.mutate(null); });
    expect(onSuccess).toHaveBeenCalledWith('ok');
  });

  it('calls onError on failure', async () => {
    const onError = vi.fn();
    const mutationFn = vi.fn().mockRejectedValue(new Error('fail'));
    const { result } = renderHook(() => useMutation(mutationFn, { onError }));

    await act(async () => { await result.current.mutate(null).catch(() => {}); });
    expect(onError).toHaveBeenCalledWith(expect.any(ApiError));
  });

  it('reset() clears data, error, and loading', async () => {
    const mutationFn = vi.fn().mockRejectedValue(new Error('fail'));
    const { result } = renderHook(() => useMutation(mutationFn));

    await act(async () => { await result.current.mutate(null).catch(() => {}); });
    expect(result.current.error).not.toBeNull();

    act(() => result.current.reset());
    expect(result.current.error).toBeNull();
    expect(result.current.data).toBeNull();
    expect(result.current.isLoading).toBe(false);
  });

  it('returns the resolved value from mutate()', async () => {
    const mutationFn = vi.fn().mockResolvedValue({ answer: 42 });
    const { result } = renderHook(() => useMutation(mutationFn));

    let returnValue: unknown;
    await act(async () => { returnValue = await result.current.mutate({}); });
    expect(returnValue).toEqual({ answer: 42 });
  });
});
