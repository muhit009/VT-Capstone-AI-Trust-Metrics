export default function TopBar() {
  return (
    <div className="flex h-16 items-center justify-between border-b border-gray-200 bg-white px-6">
      <div>
        <h1 className="text-xl font-semibold text-gray-900">Aircraft Q&A</h1>
        <p className="text-sm text-gray-500">
          Grounded answers for Boeing new hires learning airplane concepts and comparisons.
        </p>
      </div>

      <div className="flex items-center gap-3 border-l border-gray-200 pl-5">
        <div className="flex h-9 w-9 items-center justify-center rounded-full bg-blue-100 text-sm font-semibold text-blue-700">
          BJ
        </div>
        <div className="text-sm font-medium text-gray-700">Boeing New Hire</div>
      </div>
    </div>
  );
}