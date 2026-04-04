"""
generation_confidence.py — Signal 2: Generation Confidence (Mistral-specific)

Converts per-token log-probabilities from Mistral into a normalized confidence
score in [0, 1], filtering Mistral special tokens before computing the mean.

Formula (from confidence_signals.md):
    raw_mean_prob  = mean( exp(logprob_t) for t in non_special_tokens )
    score          = clip( (raw_mean_prob - 0.3) / 0.6, 0.0, 1.0 )

Confidence levels (applied to raw_mean_prob before normalization):
    HIGHLY_CONFIDENT : raw_mean > 0.8
    MODERATE         : 0.5 < raw_mean <= 0.8
    UNCERTAIN        : raw_mean <= 0.5

Normalization constants [0.3, 0.9] are provisional and will be calibrated
against real HPC runs in Sprint 4.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Optional

from .config import GEN_CONF_RAW_MIN, GEN_CONF_RAW_MAX

# ---------------------------------------------------------------------------
# Mistral special tokens — filtered before computing mean probability
# ---------------------------------------------------------------------------
MISTRAL_SPECIAL_TOKENS: frozenset[str] = frozenset({
    "<s>", "</s>", "[INST]", "[/INST]", "<<SYS>>", "<</SYS>>",
    "<unk>", "<pad>", "<|im_start|>", "<|im_end|>", "<0x0A>",
})

# Confidence level labels
HIGHLY_CONFIDENT = "HIGHLY_CONFIDENT"
MODERATE         = "MODERATE"
UNCERTAIN        = "UNCERTAIN"


def _classify(raw_mean: float) -> str:
    if raw_mean > 0.8:
        return HIGHLY_CONFIDENT
    if raw_mean > 0.5:
        return MODERATE
    return UNCERTAIN


def _normalize(raw_mean: float) -> float:
    return max(0.0, min(1.0,
        (raw_mean - GEN_CONF_RAW_MIN) / (GEN_CONF_RAW_MAX - GEN_CONF_RAW_MIN)
    ))


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------

@dataclass
class GenConfidenceResult:
    score:         float            # normalized [0,1] — fed to fusion
    level:         str              # HIGHLY_CONFIDENT | MODERATE | UNCERTAIN
    raw_mean_prob: float            # mean probability before normalization
    num_tokens:    int              # token count after filtering
    num_filtered:  int              # special tokens removed
    min_prob:      float
    max_prob:      float
    warning:       Optional[str]    # set on empty/degraded input
    token_details: list[dict] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Scorer
# ---------------------------------------------------------------------------

class GenerationConfidenceScorer:
    """
    Compute Generation Confidence from per-token log-probabilities.

    Mistral-specific: special tokens are filtered before computing the mean.
    The scorer is stateless; call compute() or from_ollama() once per result.
    """

    def from_ollama(self, ollama_response: dict) -> GenConfidenceResult:
        """
        Parse a raw Ollama /api/generate response dict and compute confidence.

        Expects the response to contain:
            - "context_logprobs"  (list of dicts with "logprob" and "token"), OR
            - "logprobs"          (list of floats) with optional "tokens"

        Ollama returns logprobs under different keys depending on version/model.
        We try the structured form first, then fall back to a plain list.

        Parameters
        ----------
        ollama_response : dict
            Raw response dict from ollama_client.generate().

        Returns
        -------
        GenConfidenceResult
        """
        # Structured form: list of {"token": str, "logprob": float}
        context_logprobs = ollama_response.get("context_logprobs")
        if context_logprobs and isinstance(context_logprobs, list):
            logprobs = [entry["logprob"] for entry in context_logprobs]
            tokens   = [entry.get("token", "") for entry in context_logprobs]
            return self.compute(logprobs, tokens=tokens)

        # Plain list form
        logprobs = ollama_response.get("logprobs", [])
        tokens   = ollama_response.get("tokens")
        return self.compute(logprobs, tokens=tokens)

    def compute(
        self,
        logprobs: list[float],
        tokens: list[str] | None = None,
        include_token_details: bool = False,
    ) -> GenConfidenceResult:
        """
        Compute generation confidence from already-extracted logprobs.

        Parameters
        ----------
        logprobs : list[float]
            Per-token log-probabilities (natural log).
        tokens : list[str], optional
            Parallel token strings. Used for special-token filtering and audit.
        include_token_details : bool
            If True, populate token_details in the result.

        Returns
        -------
        GenConfidenceResult
            Degraded (score=0.0, level=UNCERTAIN) if input is empty or all
            tokens are special tokens — no exception raised.
        """
        # Pair logprobs with tokens (or None placeholders)
        paired = list(zip(logprobs, tokens)) if tokens else [(lp, None) for lp in logprobs]
        num_total = len(paired)

        # Filter special tokens
        filtered = [
            (lp, tok)
            for lp, tok in paired
            if tok is None or tok not in MISTRAL_SPECIAL_TOKENS
        ]
        num_filtered = num_total - len(filtered)

        # Handle empty / all-filtered
        if not filtered:
            warning = (
                "All tokens were Mistral special tokens — score degraded."
                if num_total > 0
                else "logprobs list was empty — score degraded."
            )
            return GenConfidenceResult(
                score=0.0,
                level=UNCERTAIN,
                raw_mean_prob=0.0,
                num_tokens=0,
                num_filtered=num_filtered,
                min_prob=0.0,
                max_prob=0.0,
                warning=warning,
            )

        probs    = [math.exp(lp) for lp, _ in filtered]
        raw_mean = round(sum(probs) / len(probs), 6)
        normalized = _normalize(raw_mean)
        level      = _classify(raw_mean)

        details: list[dict] = []
        if include_token_details:
            for (lp, tok), p in zip(filtered, probs):
                details.append({"token": tok, "logprob": lp, "prob": round(p, 6)})

        return GenConfidenceResult(
            score=round(normalized, 6),
            level=level,
            raw_mean_prob=raw_mean,
            num_tokens=len(probs),
            num_filtered=num_filtered,
            min_prob=round(min(probs), 6),
            max_prob=round(max(probs), 6),
            warning=None,
            token_details=details,
        )


# Module-level singleton
generation_confidence_scorer = GenerationConfidenceScorer()
