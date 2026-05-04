export const placeholderSummary = {
  totalQueries: 24,
  averageConfidence: 78,
  averageGrounding: 0.81,
  averageGeneration: 0.72,
  averageLatencyMs: 914,
  tierCounts: {
    HIGH: 11,
    MEDIUM: 10,
    LOW: 3,
  },
};

export const placeholderRecentResponses = [
  {
    id: 'sample-1',
    query: 'Why do short-haul fuel burn comparisons change so much with stage length?',
    timestampLabel: 'May 2, 2026, 1:25 PM',
    tier: 'HIGH',
    confidence: 84,
    grounding: 0.88,
    generation: 0.75,
    latencyMs: 812,
    answer:
      'Short-haul comparisons are sensitive to stage length because climb and descent make up a larger share of the mission, so reserve, payload, and block-time assumptions matter more.',
  },
  {
    id: 'sample-2',
    query: 'When should a low-confidence answer be escalated for manual review?',
    timestampLabel: 'May 2, 2026, 12:58 PM',
    tier: 'MEDIUM',
    confidence: 67,
    grounding: 0.69,
    generation: 0.64,
    latencyMs: 1046,
    answer:
      'Escalation is most appropriate when the answer contains unsupported claims, conflicting citations, or operational recommendations that depend on missing assumptions.',
  },
  {
    id: 'sample-3',
    query: 'What is driving this response into the LOW confidence tier?',
    timestampLabel: 'May 2, 2026, 12:11 PM',
    tier: 'LOW',
    confidence: 36,
    grounding: 0.31,
    generation: 0.48,
    latencyMs: 905,
    answer:
      'The response fell into LOW confidence because only a small share of extracted claims were supported by retrieved evidence, even though the language model sounded moderately certain.',
  },
];
