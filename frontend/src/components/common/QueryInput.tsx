import { useForm } from 'react-hook-form';
import { queryService, GroundCheckResponse } from '../../services/api';

const MAX_QUERY_LENGTH = 4096;

interface QueryFormValues {
  query: string;
}

interface QueryInputProps {
  onResult?: (result: GroundCheckResponse) => void;
}

export default function QueryInput({ onResult }: QueryInputProps) {
  const {
    register,
    handleSubmit,
    reset,
    watch,
    setError,
    formState: { errors, isSubmitting },
  } = useForm<QueryFormValues>({ defaultValues: { query: '' } });

  const queryValue = watch('query');

  const onSubmit = async (data: QueryFormValues) => {
    try {
      const result = await queryService.submit({ query: data.query });
      onResult?.(result);
    } catch (err) {
      const message = err instanceof Error ? err.message : 'An unexpected error occurred';
      setError('root', { message });
    }
  };

  const submitError = errors.root?.message ?? null;

  return (
    <form onSubmit={handleSubmit(onSubmit)} noValidate className="space-y-3">
      <div>
        <label htmlFor="query-input" className="block text-sm font-medium text-gray-700">
          Ask a question
        </label>
        <textarea
          id="query-input"
          rows={3}
          placeholder="e.g. What is the minimum yield strength for ASTM A36 steel?"
          className={[
            'mt-1 block w-full rounded-md border px-3 py-2 text-sm shadow-sm',
            'focus:outline-none focus:ring-2 focus:ring-blue-500',
            errors.query ? 'border-red-400' : 'border-gray-300',
          ].join(' ')}
          {...register('query', {
            required: 'Query cannot be empty.',
            maxLength: {
              value: MAX_QUERY_LENGTH,
              message: `Query must be ${MAX_QUERY_LENGTH} characters or fewer.`,
            },
          })}
        />
        <div className="mt-1 flex justify-between text-xs text-gray-400">
          {errors.query ? (
            <span role="alert" className="text-red-500">
              {errors.query.message}
            </span>
          ) : (
            <span />
          )}
          <span>
            {queryValue.length} / {MAX_QUERY_LENGTH}
          </span>
        </div>
      </div>

      {submitError && (
        <p role="alert" className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">
          {submitError}
        </p>
      )}

      <div className="flex gap-2">
        <button
          type="submit"
          disabled={isSubmitting}
          className="rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {isSubmitting ? 'Submitting…' : 'Submit'}
        </button>
        <button
          type="button"
          onClick={() => reset()}
          disabled={isSubmitting}
          className="rounded-md border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-50"
        >
          Clear
        </button>
      </div>
    </form>
  );
}
