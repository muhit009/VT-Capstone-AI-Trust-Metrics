import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { vi, describe, it, expect, beforeEach } from 'vitest';
import QueryInput from './QueryInput';
import * as api from '../../services/api';
import type { GroundCheckResponse } from '../../services/api';

vi.mock('../../services/api', () => ({
  queryService: { submit: vi.fn() },
}));

const mockSubmit = vi.mocked(api.queryService.submit);

const mockResponse: GroundCheckResponse = {
  query_id: 'q_20260315_143210_abc123',
  query: 'test query',
  answer: 'test answer',
  confidence: {
    final_score: 91,
    tier: 'HIGH',
    signals: { grounding_score: 0.95, generation_confidence: 0.82 },
    weights: { grounding: 0.7, generation: 0.3 },
    explanation: 'HIGH confidence.',
    warnings: null,
    degraded: false,
  },
  citations: [],
  metadata: {
    model: 'mistralai/Mistral-7B-Instruct-v0.2',
    nli_model: 'cross-encoder/nli-deberta-v3-small',
    timestamp: '2026-03-15T14:32:10Z',
    processing_time_ms: 1247,
    retrieved_chunks: 5,
  },
  status: 'success',
};

describe('QueryInput', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders input, submit, and clear buttons', () => {
    render(<QueryInput />);
    expect(screen.getByRole('textbox')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /submit/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /clear/i })).toBeInTheDocument();
  });

  it('shows validation error when submitted empty', async () => {
    render(<QueryInput />);
    await userEvent.click(screen.getByRole('button', { name: /submit/i }));
    expect(await screen.findByRole('alert')).toHaveTextContent(/cannot be empty/i);
    expect(mockSubmit).not.toHaveBeenCalled();
  });

  it('shows validation error when query exceeds max length', async () => {
    render(<QueryInput />);
    const textarea = screen.getByRole('textbox');
    fireEvent.change(textarea, { target: { value: 'a'.repeat(4097) } });
    await userEvent.click(screen.getByRole('button', { name: /submit/i }));
    expect(await screen.findByRole('alert')).toHaveTextContent(/4096 characters/i);
    expect(mockSubmit).not.toHaveBeenCalled();
  });

  it('calls queryService.submit with the entered query', async () => {
    mockSubmit.mockResolvedValue(mockResponse);
    render(<QueryInput />);
    fireEvent.change(screen.getByRole('textbox'), { target: { value: 'What is yield strength?' } });
    await userEvent.click(screen.getByRole('button', { name: /submit/i }));
    await waitFor(() => expect(mockSubmit).toHaveBeenCalledWith({ query: 'What is yield strength?' }));
  });

  it('calls onResult callback with API response', async () => {
    mockSubmit.mockResolvedValue(mockResponse);
    const onResult = vi.fn();
    render(<QueryInput onResult={onResult} />);
    fireEvent.change(screen.getByRole('textbox'), { target: { value: 'What is yield strength?' } });
    await userEvent.click(screen.getByRole('button', { name: /submit/i }));
    await waitFor(() => expect(onResult).toHaveBeenCalledWith(mockResponse));
  });

  it('shows loading state while submitting', async () => {
    let resolve!: (v: GroundCheckResponse) => void;
    mockSubmit.mockReturnValue(new Promise((r) => { resolve = r; }));
    render(<QueryInput />);
    await userEvent.type(screen.getByRole('textbox'), 'test query');
    await userEvent.click(screen.getByRole('button', { name: /submit/i }));
    expect(await screen.findByRole('button', { name: /submitting/i })).toBeDisabled();
    resolve(mockResponse);
  });

  it('displays API error message on failure', async () => {
    mockSubmit.mockRejectedValue(new Error('Service unavailable'));
    render(<QueryInput />);
    fireEvent.change(screen.getByRole('textbox'), { target: { value: 'test query' } });
    await userEvent.click(screen.getByRole('button', { name: /submit/i }));
    expect(await screen.findByRole('alert')).toHaveTextContent(/service unavailable/i);
  });

  it('clears the input when Clear is clicked', async () => {
    render(<QueryInput />);
    const textarea = screen.getByRole('textbox');
    fireEvent.change(textarea, { target: { value: 'some text' } });
    expect(textarea).toHaveValue('some text');
    await userEvent.click(screen.getByRole('button', { name: /clear/i }));
    expect(textarea).toHaveValue('');
  });
});
