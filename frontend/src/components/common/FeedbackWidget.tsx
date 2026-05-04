import { useState, useEffect } from 'react';
import { feedbackService } from '../../services/api';

interface FeedbackWidgetProps {
  queryId: string;
}

type Decision = 'accepted' | 'review' | 'rejected';
type SubmitStatus = 'idle' | 'submitting' | 'submitted' | 'error';

const STORAGE_KEY_PREFIX = 'feedback_submitted_';

const DECISION_OPTIONS: {
  value: Decision;
  label: string;
  baseStyle: string;
  activeStyle: string;
}[] = [
  {
    value: 'accepted',
    label: 'Accept',
    baseStyle: 'border-gray-300 text-gray-700 hover:bg-gray-50',
    activeStyle: 'border-emerald-500 bg-emerald-50 text-emerald-700',
  },
  {
    value: 'review',
    label: 'Review',
    baseStyle: 'border-gray-300 text-gray-700 hover:bg-gray-50',
    activeStyle: 'border-amber-500 bg-amber-50 text-amber-700',
  },
  {
    value: 'rejected',
    label: 'Reject',
    baseStyle: 'border-gray-300 text-gray-700 hover:bg-gray-50',
    activeStyle: 'border-rose-500 bg-rose-50 text-rose-700',
  },
];

export default function FeedbackWidget({ queryId }: FeedbackWidgetProps) {
  const [decision, setDecision] = useState<Decision | null>(null);
  const [rating, setRating] = useState<1 | -1 | null>(null);
  const [comment, setComment] = useState('');
  const [submitStatus, setSubmitStatus] = useState<SubmitStatus>('idle');
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [alreadySubmitted, setAlreadySubmitted] = useState(false);

  useEffect(() => {
    const submitted = localStorage.getItem(`${STORAGE_KEY_PREFIX}${queryId}`);
    setAlreadySubmitted(!!submitted);
    setDecision(null);
    setRating(null);
    setComment('');
    setSubmitStatus('idle');
    setErrorMessage(null);
  }, [queryId]);

  const handleSubmit = async () => {
    if (!decision) return;

    setSubmitStatus('submitting');
    setErrorMessage(null);

    try {
      await feedbackService.submit(queryId, {
        status: decision,
        feedback_rating: rating ?? undefined,
        feedback_comment: comment.trim() || undefined,
      });
      localStorage.setItem(`${STORAGE_KEY_PREFIX}${queryId}`, '1');
      setAlreadySubmitted(true);
      setSubmitStatus('submitted');
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to submit feedback.';
      setErrorMessage(message);
      setSubmitStatus('error');
    }
  };

  if (alreadySubmitted && submitStatus !== 'submitted') {
    return (
      <p className="text-sm italic text-gray-400" data-testid="already-submitted">
        Decision already submitted for this response.
      </p>
    );
  }

  if (submitStatus === 'submitted') {
    return (
      <div
        role="status"
        aria-live="polite"
        className="rounded-md bg-green-50 px-3 py-2 text-sm text-green-800"
        data-testid="feedback-confirmation"
      >
        Decision logged successfully.
      </div>
    );
  }

  const isDisabled = submitStatus === 'submitting';

  return (
    <div className="space-y-3" data-testid="feedback-widget">
      <p className="text-sm font-medium text-gray-500">Decision</p>

      {/* Accept / Review / Reject */}
      <div className="flex gap-2">
        {DECISION_OPTIONS.map(({ value, label, baseStyle, activeStyle }) => (
          <button
            key={value}
            type="button"
            aria-pressed={decision === value}
            onClick={() => setDecision(value)}
            disabled={isDisabled}
            className={[
              'rounded-md border px-3 py-1.5 text-sm font-medium transition-colors',
              'disabled:cursor-not-allowed disabled:opacity-50',
              decision === value ? activeStyle : baseStyle,
            ].join(' ')}
          >
            {label}
          </button>
        ))}
      </div>

      {decision && (
        <div className="space-y-3">
          {/* Optional thumbs rating */}
          <div>
            <p className="mb-1.5 text-xs text-gray-500">Rating (optional)</p>
            <div className="flex gap-2">
              <button
                type="button"
                aria-pressed={rating === 1}
                onClick={() => setRating(rating === 1 ? null : 1)}
                disabled={isDisabled}
                className={[
                  'flex items-center gap-1 rounded-md border px-2.5 py-1 text-xs font-medium transition-colors',
                  'disabled:cursor-not-allowed disabled:opacity-50',
                  rating === 1
                    ? 'border-emerald-500 bg-emerald-50 text-emerald-700'
                    : 'border-gray-300 text-gray-600 hover:bg-gray-50',
                ].join(' ')}
                aria-label="Helpful"
              >
                <ThumbUpIcon /> Helpful
              </button>
              <button
                type="button"
                aria-pressed={rating === -1}
                onClick={() => setRating(rating === -1 ? null : -1)}
                disabled={isDisabled}
                className={[
                  'flex items-center gap-1 rounded-md border px-2.5 py-1 text-xs font-medium transition-colors',
                  'disabled:cursor-not-allowed disabled:opacity-50',
                  rating === -1
                    ? 'border-rose-400 bg-rose-50 text-rose-700'
                    : 'border-gray-300 text-gray-600 hover:bg-gray-50',
                ].join(' ')}
                aria-label="Unhelpful"
              >
                <ThumbDownIcon /> Unhelpful
              </button>
            </div>
          </div>

          {/* Optional comment */}
          <div>
            <label htmlFor="feedback-comment" className="mb-1.5 block text-xs text-gray-500">
              Comment (optional)
            </label>
            <textarea
              id="feedback-comment"
              rows={2}
              value={comment}
              onChange={(e) => setComment(e.target.value)}
              disabled={isDisabled}
              placeholder="Add context for this decision..."
              className="block w-full rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:cursor-not-allowed disabled:opacity-50"
            />
          </div>

          {errorMessage && (
            <p role="alert" className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">
              {errorMessage}
            </p>
          )}

          <button
            type="button"
            onClick={handleSubmit}
            disabled={isDisabled}
            className="rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {isDisabled ? 'Submitting…' : 'Submit Decision'}
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
      className="h-3.5 w-3.5"
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
      className="h-3.5 w-3.5"
      aria-hidden="true"
    >
      <path d="M18.905 12.75a1.25 1.25 0 0 1-2.5 0v-7.5a1.25 1.25 0 0 1 2.5 0v7.5ZM8.905 17v1.3c0 .268-.14.526-.395.607A2 2 0 0 1 5.905 17c0-.995.182-1.948.514-2.826A1 1 0 0 0 5.905 13h-3.5a1 1 0 0 1-1-1c0-.447.14-.86.378-1.197l.5-1.5A1 1 0 0 1 3.21 8.55H14.905a1 1 0 0 1 1 1V12a1 1 0 0 1-.316.724l-4.71 4.32a1 1 0 0 1-1.974-.044Z" />
    </svg>
  );
}
