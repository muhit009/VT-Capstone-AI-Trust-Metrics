// src/components/dashboard/ChatInterface.jsx
import { Copy, Download, Save, Flag as FlagIcon, Paperclip, Send, ChevronDown } from 'lucide-react';

export default function ChatInterface() {
  return (
    <div className="flex-1 min-w-0 flex flex-col bg-white">
      {/* Messages */}
      <div className="flex-1 overflow-auto px-8 py-6">
        <div className="max-w-4xl mx-auto space-y-6">
          {/* User */}
          <div className="flex justify-end">
            <div className="max-w-2xl bg-gray-100 rounded-2xl px-5 py-3">
              <p className="text-gray-900">
                I’m a new Boeing engineer. Can you explain the difference between the 737 MAX and the 787 in
                terms of typical use-case and major design goals? Also, what should I be careful about when
                comparing fuel efficiency?
              </p>
            </div>
          </div>

          {/* Assistant */}
          <div className="flex justify-start">
            <div className="max-w-3xl w-full">
              <div className="bg-white border border-gray-200 rounded-2xl px-6 py-5 shadow-sm">
                <div className="space-y-4 text-gray-900 leading-relaxed">
                  <p>
                    Welcome aboard. At a high level, the <strong>737 MAX</strong> is a single-aisle aircraft
                    optimized for short-to-medium range, high-frequency routes, while the{' '}
                    <strong>787 Dreamliner</strong> is a widebody designed for long-haul efficiency and passenger
                    comfort on longer segments.
                  </p>

                  <p>
                    <strong>Typical use-case:</strong> The 737 MAX is commonly used for high-cycle operations
                    (many takeoffs and landings per day) with quicker turnaround. The 787 is designed for longer
                    stage lengths, where aerodynamic efficiency and weight savings provide bigger benefits over
                    time{' '}
                    <span className="inline-flex items-center justify-center w-6 h-5 text-xs font-medium text-primary-700 bg-primary-50 rounded">
                      [1]
                    </span>
                    .
                  </p>

                  <p>
                    <strong>Design goals:</strong> The 737 MAX emphasizes incremental efficiency improvements
                    within a single-aisle platform, while the 787 emphasizes a more integrated long-range
                    efficiency story (structure, systems, and overall performance) and operational flexibility{' '}
                    <span className="inline-flex items-center justify-center w-6 h-5 text-xs font-medium text-primary-700 bg-primary-50 rounded">
                      [2]
                    </span>
                    .
                  </p>

                  <p>
                    <strong>Fuel efficiency caveat:</strong> Be careful comparing “fuel burn” without normalizing
                    by mission profile and payload (e.g., stage length, reserves, passenger/cargo mix). Aircraft
                    can look more or less efficient depending on the scenario and assumptions{' '}
                    <span className="inline-flex items-center justify-center w-6 h-5 text-xs font-medium text-primary-700 bg-primary-50 rounded">
                      [3]
                    </span>
                    .
                  </p>

                  <p>
                    If you tell me the route length and payload assumptions you’re using, I can help structure a
                    fair comparison and what metrics to use (per seat-mile, per ton-mile, etc.).
                  </p>
                </div>

                {/* Confidence strip */}
                <div className="mt-4 flex flex-wrap items-center gap-2">
                  <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-amber-50 border border-amber-200 text-sm shadow-sm">
                    <span className="font-bold text-amber-900">74</span>
                    <span className="w-1 h-1 rounded-full bg-amber-400" />
                    <span className="font-medium text-amber-800">Medium Confidence</span>
                    <span className="hidden sm:block w-px h-3 bg-amber-200 mx-1" />
                    <span className="hidden sm:block text-amber-700 text-xs">
                      Depends on mission assumptions
                    </span>
                  </div>
                  <button className="h-8 px-3 text-xs rounded-lg text-primary-600 hover:bg-primary-50">
                    View details
                  </button>
                </div>

                {/* Actions */}
                <div className="mt-3 pt-3 border-t border-gray-200 flex flex-wrap items-center gap-2">
                  {[
                    { Icon: Copy, label: 'Copy' },
                    { Icon: Download, label: 'Export' },
                    { Icon: Save, label: 'Save' },
                    { Icon: FlagIcon, label: 'Flag' },
                  ].map(({ Icon, label }) => (
                    <button
                      key={label}
                      className="h-8 px-3 text-xs rounded-lg border border-gray-200 hover:bg-gray-50 inline-flex items-center gap-2"
                    >
                      <Icon className="w-3.5 h-3.5" />
                      {label}
                    </button>
                  ))}
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Input */}
      <div className="sticky bottom-0 border-t border-gray-200 bg-white/95 backdrop-blur-sm px-8 py-6 pb-8 shadow-[0_-8px_30px_rgba(0,0,0,0.04)] z-10">
        <div className="max-w-4xl mx-auto space-y-4">
          {/* Quick actions */}
          <div className="flex flex-wrap gap-2">
            {['Assess risk', 'Explain confidence', 'Show evidence', 'Summarize'].map((action) => (
              <button
                key={action}
                className="text-xs px-3 py-1.5 rounded-full border border-gray-200 bg-white hover:bg-gray-50"
              >
                {action}
              </button>
            ))}
          </div>

          <div className="flex items-end gap-3">
            <button className="h-10 w-10 rounded-lg border border-gray-200 hover:bg-gray-50 inline-flex items-center justify-center">
              <Paperclip className="w-4 h-4 text-gray-600" />
            </button>

            <div className="flex-1">
              <textarea
                rows={2}
                placeholder="Ask a question…"
                className="w-full resize-none rounded-xl border border-gray-200 px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
              />
              <div className="mt-2 flex items-center justify-between">
                <button className="text-xs text-gray-600 hover:text-gray-900 inline-flex items-center gap-1">
                  Model: Default <ChevronDown className="w-3.5 h-3.5" />
                </button>
                <span className="text-xs text-gray-400">Shift + Enter for newline</span>
              </div>
            </div>

            <button className="h-10 px-4 rounded-lg bg-primary-600 hover:bg-primary-700 text-white inline-flex items-center gap-2">
              <Send className="w-4 h-4" />
              Send
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}