function Home() {
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

      <section className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
        {/* Placeholder cards — replace with real content */}
        {['Metric A', 'Metric B', 'Metric C'].map((title) => (
          <div key={title} className="card">
            <h2 className="text-lg font-semibold text-gray-800">{title}</h2>
            <p className="mt-2 text-sm text-gray-500">
              Description of this trust metric goes here.
            </p>
          </div>
        ))}
      </section>
    </div>
  );
}

export default Home;
