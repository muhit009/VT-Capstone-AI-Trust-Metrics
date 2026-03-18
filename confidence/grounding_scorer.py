"""
grounding_scorer.py — Signal 1: Grounding Score

Measures whether the claims in an AI answer are supported by the
retrieved document chunks using Natural Language Inference (NLI).

Model  : cross-encoder/nli-deberta-v3-small  (CPU inference)
Formula: (1/N) * sum_i( max_j( entailment(claim_i, chunk_j) ) )

Per confidence_signals.md:
- Claims are extracted via sentence splitting (NLTK, Option A for v1.0)
- Entailment index = 1  (label order: contradiction=0, entailment=1, neutral=2)
- Supported-claim threshold = 0.5 (reporting only, not used in scoring)
"""
from __future__ import annotations

import nltk
from dataclasses import dataclass, field
from transformers import pipeline

from .config import NLI_MODEL, TOP_K_CHUNKS, MIN_CLAIM_WORDS

# Download NLTK tokenizer data on first use (silent if already present)
nltk.download("punkt", quiet=True)
nltk.download("punkt_tab", quiet=True)


SUPPORTED_THRESHOLD = 0.5   # a claim is "supported" for reporting if max entailment > this


@dataclass
class ClaimDetail:
    claim:                    str
    max_entailment:           float
    best_supporting_chunk_idx: int
    supported:                bool   # max_entailment > SUPPORTED_THRESHOLD


@dataclass
class GroundingResult:
    grounding_score:   float          # 0.0–1.0
    num_claims:        int
    supported_claims:  int
    claim_details:     list[ClaimDetail] = field(default_factory=list)


class GroundingScorer:
    """
    Score how well an answer is grounded in retrieved chunks.

    Load once at startup; reuse across requests.
    """

    def __init__(self, model_name: str = NLI_MODEL):
        # device=-1 → CPU  (GPU left entirely for the LLM)
        self._nli = pipeline(
            "text-classification",
            model=model_name,
            device=-1,
            top_k=None,          # return all labels so we can pick entailment
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def compute(
        self,
        answer: str,
        chunks: list[str],
        top_k: int = TOP_K_CHUNKS,
    ) -> GroundingResult:
        """
        Parameters
        ----------
        answer : str
            Generated answer text.
        chunks : list[str]
            Retrieved document chunks (at most top_k are used).
        top_k  : int
            Cap on how many chunks to score against.

        Returns
        -------
        GroundingResult
        """
        chunks = chunks[:top_k]
        claims = self._extract_claims(answer)

        if not claims:
            return GroundingResult(
                grounding_score=0.0,
                num_claims=0,
                supported_claims=0,
            )

        claim_details: list[ClaimDetail] = []

        for claim in claims:
            max_ent   = 0.0
            best_idx  = 0

            for j, chunk in enumerate(chunks):
                ent = self._entailment_score(claim, chunk)
                if ent > max_ent:
                    max_ent  = ent
                    best_idx = j

            claim_details.append(ClaimDetail(
                claim=claim,
                max_entailment=round(max_ent, 6),
                best_supporting_chunk_idx=best_idx,
                supported=max_ent > SUPPORTED_THRESHOLD,
            ))

        grounding_score = sum(c.max_entailment for c in claim_details) / len(claim_details)
        supported_count = sum(1 for c in claim_details if c.supported)

        return GroundingResult(
            grounding_score=round(grounding_score, 6),
            num_claims=len(claim_details),
            supported_claims=supported_count,
            claim_details=claim_details,
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _extract_claims(self, text: str) -> list[str]:
        """Sentence-split the answer and filter trivially short sentences."""
        sentences = nltk.sent_tokenize(text)
        return [
            s.strip() for s in sentences
            if len(s.split()) >= MIN_CLAIM_WORDS
        ]

    def _entailment_score(self, claim: str, chunk: str) -> float:
        """Return the entailment probability for (claim, chunk) via NLI."""
        # Cross-encoder expects a single string "premise [SEP] hypothesis"
        # The pipeline handles tokenization; we just pass premise + hypothesis.
        results = self._nli(f"{chunk} [SEP] {claim}")
        # results is a list of dicts: [{"label": ..., "score": ...}, ...]
        for item in results[0]:
            if item["label"].upper() == "ENTAILMENT":
                return float(item["score"])
        return 0.0


# Module-level singleton (loaded once at startup)
grounding_scorer = GroundingScorer()
