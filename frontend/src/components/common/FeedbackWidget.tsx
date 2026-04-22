import { useState, useEffect } from 'react';
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
      <p className="text-sm text-gray-400 italic" data-testid="already-submitted">
        Feedback already submitted for this response.
      </p>
    );
  }

  if (status === 'submitted') {
    return (
      <div
        role="status"
        aria-live="polite"
        className="rounded-md bg-green-50 px-3 py-2 text-sm text-green-800"
        data-testid="feedback-confirmation"
      >
        Thank you for your feedback!
      </div>
    );
  }

  return (
    <div className="space-y-3" data-testid="feedback-widget">
      <p className="text-sm font-medium text-gray-500">Was this answer helpful?</p>

      <div className="flex gap-2">
        <button
          type="button"
          aria-pressed={rating === 'helpful'}
          onClick={() => setRating('helpful')}
          disabled={status === 'submitting'}
          className={[
            'flex items-center gap-1 rounded-md border px-3 py-1.5 text-sm font-medium transition-colors',
            'disabled:cursor-not-allowed disabled:opacity-50',
            rating === 'helpful'
              ? 'border-green-500 bg-green-50 text-green-700'
              : 'border-gray-300 text-gray-700 hover:bg-gray-50',
          ].join(' ')}
          aria-label="Helpful"
        >
          <ThumbUpIcon />
          Helpful
        </button>

        <button
          type="button"
          aria-pressed={rating === 'unhelpful'}
          onClick={() => setRating('unhelpful')}
          disabled={status === 'submitting'}
          className={[
            'flex items-center gap-1 rounded-md border px-3 py-1.5 text-sm font-medium transition-colors',
            'disabled:cursor-not-allowed disabled:opacity-50',
            rating === 'unhelpful'
              ? 'border-red-400 bg-red-50 text-red-700'
              : 'border-gray-300 text-gray-700 hover:bg-gray-50',
          ].join(' ')}
          aria-label="Unhelpful"
        >
          <ThumbDownIcon />
          Unhelpful
        </button>
      </div>

      {rating && (
        <div className="space-y-2">
          <label htmlFor="feedback-comment" className="block text-sm text-gray-600">
            Additional comments (optional)
          </label>
          <textarea
            id="feedback-comment"
            rows={3}
            value={comment}
            onChange={(e) => setComment(e.target.value)}
            disabled={status === 'submitting'}
            placeholder="Tell us more about your experience..."
            className="block w-full rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:cursor-not-allowed disabled:opacity-50"
          />

          {errorMessage && (
            <p role="alert" className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">
              {errorMessage}
            </p>
          )}

          <button
            type="button"
            onClick={handleSubmit}
            disabled={status === 'submitting'}
            className="rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {status === 'submitting' ? 'Submitting…' : 'Submit Feedback'}
          </button>
        </div>
      )}
    </div>
  );
}

function ThumbUpIcon() {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 20 20"
      fill="currentColor"
      className="h-4 w-4"
      aria-hidden="true"
    >
      <path d="M1 8.25a1.25 1.25 0 1 1 2.5 0v7.5a1.25 1.25 0 0 1-2.5 0v-7.5ZM11 3V1.7c0-.268.14-.526.395-.607A2 2 0 0 1 14 3c0 .995-.182 1.948-.514 2.826A1 1 0 0 0 14 7h3.5a1 1 0 0 1 1 1c0 .447-.14.86-.378 1.197l-.5 1.5a1 1 0 0 1-.928.753H5a1 1 0 0 1-1-1V8a1 1 0 0 1 .316-.724l4.71-4.32A1 1 0 0 1 11 3Z" />
    </svg>
  );
}

function ThumbDownIcon() {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 20 20"
      fill="currentColor"
      className="h-4 w-4"
      aria-hidden="true"
    >
      <path d="M18.905 12.75a1.25 1.25 0 0 1-2.5 0v-7.5a1.25 1.25 0 0 1 2.5 0v7.5ZM8.905 17v1.3c0 .268-.14.526-.395.607A2 2 0 0 1 5.905 17c0-.995.182-1.948.514-2.826A1 1 0 0 0 5.905 13h-3.5a1 1 0 0 1-1-1c0-.447.14-.86.378-1.197l.5-1.5A1 1 0 0 1 3.21 8.55H14.905a1 1 0 0 1 1 1V12a1 1 0 0 1-.316.724l-4.71 4.32a1 1 0 0 1-1.974-.044Z" />
    </svg>
  );
}