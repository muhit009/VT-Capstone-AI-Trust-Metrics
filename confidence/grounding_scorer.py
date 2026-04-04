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

import logging
import re
from dataclasses import dataclass, field

import nltk
from transformers import pipeline

from .config import NLI_MODEL, TOP_K_CHUNKS, MIN_CLAIM_WORDS

logger = logging.getLogger(__name__)

# Download NLTK tokenizer data on first use (silent if already present)
nltk.download("punkt",     quiet=True)
nltk.download("punkt_tab", quiet=True)

SUPPORTED_THRESHOLD = 0.5   # a claim is "supported" for reporting if max entailment > this
ENTAILMENT_LABEL    = "ENTAILMENT"   # expected label from DeBERTa NLI output


@dataclass
class ClaimDetail:
    claim:                     str
    max_entailment:            float
    best_supporting_chunk_idx: int
    supported:                 bool   # max_entailment > SUPPORTED_THRESHOLD


@dataclass
class GroundingResult:
    grounding_score:  float          # 0.0–1.0
    num_claims:       int
    supported_claims: int
    claim_details:    list[ClaimDetail] = field(default_factory=list)


class GroundingScorer:
    """
    Score how well an answer is grounded in retrieved chunks.

    Load once at startup; reuse across requests.
    """

    def __init__(self, model_name: str = NLI_MODEL):
        logger.info("Loading NLI model: %s", model_name)
        # device=-1 → CPU  (GPU left entirely for the LLM)
        self._nli = pipeline(
            "text-classification",
            model=model_name,
            device=-1,
            top_k=None,          # return all labels so we can pick entailment
        )
        logger.info("NLI model loaded.")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def compute(
        self,
        answer: str,
        chunks: list[str],
        top_k:  int = TOP_K_CHUNKS,
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
        logger.info("Extracted %d claims from answer (%d chars)", len(claims), len(answer))

        if not claims:
            logger.warning("No claims extracted from answer — grounding score = 0.0")
            return GroundingResult(
                grounding_score=0.0,
                num_claims=0,
                supported_claims=0,
            )

        # Build all (claim, chunk) pairs for batch inference
        pairs   = [(claim, chunk) for claim in claims for chunk in chunks]
        inputs  = [f"{chunk} [SEP] {claim}" for claim, chunk in pairs]

        logger.debug("Running NLI batch inference on %d pairs", len(inputs))
        batch_results = self._nli(inputs)

        # Reshape results: [num_claims][num_chunks]
        n_chunks      = len(chunks)
        claim_details: list[ClaimDetail] = []

        for i, claim in enumerate(claims):
            max_ent  = 0.0
            best_idx = 0

            for j in range(n_chunks):
                result_idx = i * n_chunks + j
                ent = self._extract_entailment(batch_results[result_idx])
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

        logger.info("Grounding score: %.4f (%d/%d claims supported)",
                    grounding_score, supported_count, len(claim_details))

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
        """
        Split answer into individual verifiable claims.

        Handles:
        - Regular sentences (via NLTK)
        - Numbered lists  (1. item  /  1) item)
        - Bullet points   (- item  /  • item  /  * item)
        - Filters trivially short sentences (< MIN_CLAIM_WORDS words)
        """
        # Normalize bullet points and numbered lists into newline-separated items
        text = re.sub(r'(?m)^\s*[\-\•\*]\s+', '\n', text)
        text = re.sub(r'(?m)^\s*\d+[\.\)]\s+', '\n', text)

        sentences = nltk.sent_tokenize(text)

        # Also split on newlines in case bullet normalization created multi-line chunks
        expanded = []
        for s in sentences:
            for part in s.split('\n'):
                part = part.strip()
                if part:
                    expanded.append(part)

        claims = [s for s in expanded if len(s.split()) >= MIN_CLAIM_WORDS]
        logger.debug("Claims after filtering: %s", claims)
        return claims

    def _extract_entailment(self, label_scores: list[dict]) -> float:
        """Extract entailment probability from NLI pipeline output."""
        for item in label_scores:
            if item["label"].upper() == ENTAILMENT_LABEL:
                return float(item["score"])
        # Fallback: if label not found, log a warning and return 0
        labels = [item["label"] for item in label_scores]
        logger.warning(
            "Entailment label '%s' not found in model output. "
            "Available labels: %s. Returning 0.0.",
            ENTAILMENT_LABEL, labels
        )
        return 0.0


# Module-level singleton (loaded once at startup)
grounding_scorer = GroundingScorer()
