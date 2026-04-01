import { useState } from 'react';
import QueryInput from '../components/common/QueryInput';
import FeedbackWidget from '../components/common/FeedbackWidget';
import type { GroundCheckResponse } from '../services/api';

function Home() {
  const [result, setResult] = useState<GroundCheckResponse | null>(null);

  return (
    <div className="space-y-8">
      <section className="text-center">
        <h1 className="text-4xl font-bold tracking-tight text-gray-900 sm:text-5xl">
          AI Trust Metrics
        </h1>
        <p className="mx-auto mt-4 max-w-2xl text-lg text-gray-600">
          Virginia Tech Capstone Project — measuring and visualizing trust in AI systems.
        </p>
      </section>

      <section className="mx-auto max-w-2xl">
        <QueryInput onResult={setResult} />
      </section>

      {result && (
        <section className="mx-auto max-w-2xl space-y-4">
          <div className="rounded-md border border-gray-200 bg-white p-4 shadow-sm">
            <p className="text-sm font-medium text-gray-500">Answer</p>
            <p className="mt-1 text-gray-900">{result.answer ?? 'No answer produced.'}</p>
          </div>

          <div className="rounded-md border border-gray-200 bg-white p-4 shadow-sm">
            <p className="text-sm font-medium text-gray-500">Confidence</p>
            <p className="mt-1 text-2xl font-bold text-gray-900">
              {result.confidence.final_score}
              <span className="ml-2 text-sm font-medium text-gray-500">
                {result.confidence.tier}
              </span>
            </p>
            <p className="mt-1 text-sm text-gray-600">{result.confidence.explanation}</p>
          </div>

          {result.citations.length > 0 && (
            <div className="rounded-md border border-gray-200 bg-white p-4 shadow-sm">
              <p className="mb-2 text-sm font-medium text-gray-500">
                Citations ({result.citations.length})
              </p>
              <ul className="space-y-2">
                {result.citations.map((c) => (
                  <li key={c.citation_id} className="text-sm text-gray-700">
                    <span className="font-medium">{c.document}</span>
                    {c.page != null && <span className="text-gray-400"> · p.{c.page}</span>}
                    <p className="mt-0.5 text-gray-500 italic">"{c.text_excerpt}"</p>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {result.error && (
            <p className="rounded-md bg-yellow-50 px-3 py-2 text-sm text-yellow-800">
              {result.error.message}
            </p>
          )}

          <div className="rounded-md border border-gray-200 bg-white p-4 shadow-sm">
            <FeedbackWidget queryId={result.query_id} />
          </div>
        </section>
      )}
    </div>
  );
}

export default Home;
