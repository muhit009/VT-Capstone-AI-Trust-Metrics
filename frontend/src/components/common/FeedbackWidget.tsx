import { useState, useEffect } from 'react';
import { ThumbsDown, ThumbsUp } from 'lucide-react';
import { feedbackService } from '../../services/api';

interface FeedbackWidgetProps {
  queryId: string;
}

type SubmitStatus = 'idle' | 'submitting' | 'submitted' | 'error';

const STORAGE_KEY_PREFIX = 'feedback_submitted_';

export default function FeedbackWidget({ queryId }: FeedbackWidgetProps) {
  const [rating, setRating] = useState<'helpful' | 'unhelpful' | null>(null);
  const [comment, setComment] = useState('');
  const [status, setStatus] = useState<SubmitStatus>('idle');
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [alreadySubmitted, setAlreadySubmitted] = useState(false);
  const showCommentComposer = rating !== null;

  useEffect(() => {
    const submitted = localStorage.getItem(`${STORAGE_KEY_PREFIX}${queryId}`);
    setAlreadySubmitted(!!submitted);
    // Reset form when queryId changes
    setRating(null);
    setComment('');
    setStatus('idle');
    setErrorMessage(null);
  }, [queryId]);

  const handleSubmit = async () => {
    if (!rating) return;

    setStatus('submitting');
    setErrorMessage(null);

    try {
      await feedbackService.submit(queryId, {
        status: rating === 'helpful' ? 'accepted' : 'rejected',
        feedback_rating: rating === 'helpful' ? 1 : -1,
        feedback_comment: comment.trim() || undefined,
      });
      localStorage.setItem(`${STORAGE_KEY_PREFIX}${queryId}`, '1');
      setAlreadySubmitted(true);
      setStatus('submitted');
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to submit feedback.';
      setErrorMessage(message);
      setStatus('error');
    }
  };

  if (alreadySubmitted && status !== 'submitted') {
    return (
      <div
        className="inline-flex items-center rounded-full border border-gray-200 bg-gray-50 px-3 py-1 text-xs text-gray-500"
        data-testid="already-submitted"
      >
        Feedback submitted
      </div>
    );
  }

  if (status === 'submitted') {
    return (
      <div
        role="status"
        aria-live="polite"
        className="inline-flex items-center rounded-full border border-emerald-200 bg-emerald-50 px-3 py-1.5 text-xs font-medium text-emerald-800"
        data-testid="feedback-confirmation"
      >
        Thank you for your feedback!
      </div>
    );
  }

  return (
    <div className="space-y-3" data-testid="feedback-widget">
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-xs font-medium text-gray-500">Rate response</span>

        <button
          type="button"
          aria-pressed={rating === 'helpful'}
          onClick={() => setRating('helpful')}
          disabled={status === 'submitting'}
          className={[
            'inline-flex items-center gap-1.5 rounded-lg border px-3 py-1.5 text-xs font-medium transition-colors',
            'disabled:cursor-not-allowed disabled:opacity-50',
            rating === 'helpful'
              ? 'border-emerald-300 bg-emerald-50 text-emerald-700'
              : 'border-gray-300 text-gray-700 hover:bg-gray-50',
          ].join(' ')}
          aria-label="Helpful"
        >
          <ThumbsUp className="h-3.5 w-3.5" />
          Helpful
        </button>

        <button
          type="button"
          aria-pressed={rating === 'unhelpful'}
          onClick={() => setRating('unhelpful')}
          disabled={status === 'submitting'}
          className={[
            'inline-flex items-center gap-1.5 rounded-lg border px-3 py-1.5 text-xs font-medium transition-colors',
            'disabled:cursor-not-allowed disabled:opacity-50',
            rating === 'unhelpful'
              ? 'border-rose-300 bg-rose-50 text-rose-700'
              : 'border-gray-300 text-gray-700 hover:bg-gray-50',
          ].join(' ')}
          aria-label="Unhelpful"
        >
          <ThumbsDown className="h-3.5 w-3.5" />
          Unhelpful
        </button>
      </div>

      {showCommentComposer ? (
        <div className="space-y-2 rounded-2xl border border-gray-200 bg-gray-50 p-3">
          <label htmlFor={`feedback-comment-${queryId}`} className="block text-xs font-medium text-gray-600">
            Additional comments (optional)
          </label>
          <textarea
            id={`feedback-comment-${queryId}`}
            rows={3}
            value={comment}
            onChange={(e) => setComment(e.target.value)}
            disabled={status === 'submitting'}
            placeholder="Tell us more about your experience..."
            className="block w-full rounded-xl border border-gray-300 bg-white px-3 py-2 text-sm shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:cursor-not-allowed disabled:opacity-50"
          />

          {errorMessage && (
            <p role="alert" className="rounded-xl bg-red-50 px-3 py-2 text-sm text-red-700">
              {errorMessage}
            </p>
          )}

          <div className="flex flex-wrap items-center gap-2">
            <button
              type="button"
              onClick={handleSubmit}
              disabled={status === 'submitting'}
              className="rounded-lg bg-blue-600 px-4 py-2 text-xs font-medium text-white hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {status === 'submitting' ? 'Submitting…' : 'Submit feedback'}
            </button>

            <button
              type="button"
              onClick={() => {
                setRating(null);
                setComment('');
                setErrorMessage(null);
                setStatus('idle');
              }}
              disabled={status === 'submitting'}
              className="rounded-lg border border-gray-300 px-3 py-2 text-xs font-medium text-gray-700 hover:bg-white disabled:cursor-not-allowed disabled:opacity-50"
            >
              Cancel
            </button>
          </div>
        </div>
      ) : null}
    </div>
  );
}
