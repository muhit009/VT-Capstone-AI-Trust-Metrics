import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { vi, describe, it, expect, beforeEach, afterEach } from 'vitest';
import FeedbackWidget from './FeedbackWidget';
import * as api from '../../services/api';

vi.mock('../../services/api', () => ({
  feedbackService: { submit: vi.fn() },
}));

const mockSubmit = vi.mocked(api.feedbackService.submit);

const QUERY_ID = 'q_test_001';
const STORAGE_KEY = `feedback_submitted_${QUERY_ID}`;

describe('FeedbackWidget', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
  });

  afterEach(() => {
    localStorage.clear();
  });

  it('renders thumbs up and thumbs down buttons', () => {
    render(<FeedbackWidget queryId={QUERY_ID} />);
    expect(screen.getByRole('button', { name: 'Helpful' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /unhelpful/i })).toBeInTheDocument();
  });

  it('does not show comment field or submit button before rating is selected', () => {
    render(<FeedbackWidget queryId={QUERY_ID} />);
    expect(screen.queryByLabelText(/additional comments/i)).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /submit feedback/i })).not.toBeInTheDocument();
  });

  it('shows comment field and submit button after selecting helpful', async () => {
    render(<FeedbackWidget queryId={QUERY_ID} />);
    await userEvent.click(screen.getByRole('button', { name: 'Helpful' }));
    expect(screen.getByLabelText(/additional comments/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /submit feedback/i })).toBeInTheDocument();
  });

  it('shows comment field and submit button after selecting unhelpful', async () => {
    render(<FeedbackWidget queryId={QUERY_ID} />);
    await userEvent.click(screen.getByRole('button', { name: /unhelpful/i }));
    expect(screen.getByLabelText(/additional comments/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /submit feedback/i })).toBeInTheDocument();
  });

  it('submits feedback with rating and no comment', async () => {
    mockSubmit.mockResolvedValue({ feedback_id: 'fb_001', status: 'ok' });
    render(<FeedbackWidget queryId={QUERY_ID} />);
    await userEvent.click(screen.getByRole('button', { name: 'Helpful' }));
    await userEvent.click(screen.getByRole('button', { name: /submit feedback/i }));
    await waitFor(() =>
      expect(mockSubmit).toHaveBeenCalledWith({
        query_id: QUERY_ID,
        rating: 'helpful',
        comment: undefined,
      })
    );
  });

  it('submits feedback with rating and comment', async () => {
    mockSubmit.mockResolvedValue({ feedback_id: 'fb_002', status: 'ok' });
    render(<FeedbackWidget queryId={QUERY_ID} />);
    await userEvent.click(screen.getByRole('button', { name: /unhelpful/i }));
    await userEvent.type(screen.getByLabelText(/additional comments/i), 'Too vague');
    await userEvent.click(screen.getByRole('button', { name: /submit feedback/i }));
    await waitFor(() =>
      expect(mockSubmit).toHaveBeenCalledWith({
        query_id: QUERY_ID,
        rating: 'unhelpful',
        comment: 'Too vague',
      })
    );
  });

  it('shows confirmation message after successful submission', async () => {
    mockSubmit.mockResolvedValue({ feedback_id: 'fb_003', status: 'ok' });
    render(<FeedbackWidget queryId={QUERY_ID} />);
    await userEvent.click(screen.getByRole('button', { name: 'Helpful' }));
    await userEvent.click(screen.getByRole('button', { name: /submit feedback/i }));
    expect(await screen.findByTestId('feedback-confirmation')).toHaveTextContent(/thank you/i);
  });

  it('writes to localStorage after successful submission', async () => {
    mockSubmit.mockResolvedValue({ feedback_id: 'fb_004', status: 'ok' });
    render(<FeedbackWidget queryId={QUERY_ID} />);
    await userEvent.click(screen.getByRole('button', { name: 'Helpful' }));
    await userEvent.click(screen.getByRole('button', { name: /submit feedback/i }));
    await screen.findByTestId('feedback-confirmation');
    expect(localStorage.getItem(STORAGE_KEY)).toBe('1');
  });

  it('shows already-submitted message when localStorage entry exists', () => {
    localStorage.setItem(STORAGE_KEY, '1');
    render(<FeedbackWidget queryId={QUERY_ID} />);
    expect(screen.getByTestId('already-submitted')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Helpful' })).not.toBeInTheDocument();
  });

  it('does not call submit again if already submitted', () => {
    localStorage.setItem(STORAGE_KEY, '1');
    render(<FeedbackWidget queryId={QUERY_ID} />);
    expect(mockSubmit).not.toHaveBeenCalled();
  });

  it('displays API error message on submission failure', async () => {
    mockSubmit.mockRejectedValue(new Error('Network error'));
    render(<FeedbackWidget queryId={QUERY_ID} />);
    await userEvent.click(screen.getByRole('button', { name: 'Helpful' }));
    await userEvent.click(screen.getByRole('button', { name: /submit feedback/i }));
    expect(await screen.findByRole('alert')).toHaveTextContent(/network error/i);
  });

  it('does not write to localStorage on submission failure', async () => {
    mockSubmit.mockRejectedValue(new Error('Network error'));
    render(<FeedbackWidget queryId={QUERY_ID} />);
    await userEvent.click(screen.getByRole('button', { name: 'Helpful' }));
    await userEvent.click(screen.getByRole('button', { name: /submit feedback/i }));
    await screen.findByRole('alert');
    expect(localStorage.getItem(STORAGE_KEY)).toBeNull();
  });

  it('resets state when queryId prop changes', async () => {
    localStorage.setItem(STORAGE_KEY, '1');
    const { rerender } = render(<FeedbackWidget queryId={QUERY_ID} />);
    expect(screen.getByTestId('already-submitted')).toBeInTheDocument();

    const NEW_ID = 'q_test_002';
    rerender(<FeedbackWidget queryId={NEW_ID} />);
    expect(screen.queryByTestId('already-submitted')).not.toBeInTheDocument();
    expect(screen.getByTestId('feedback-widget')).toBeInTheDocument();
  });
});
