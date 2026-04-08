"""
engine.py — Top-level Confidence Engine

This is the single integration point the backend team will call.
Everything else in this package is an implementation detail.

Usage (by backend team, post-integration):
    from confidence import confidence_engine
    result = confidence_engine.score(answer, chunks, logprobs)

Usage (local dev, via dev/local_pipeline.py):
    Uses ollama_client to obtain answer + logprobs locally, then calls score().
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

from .grounding_scorer        import grounding_scorer
from .generation_confidence   import generation_confidence_scorer
from .fusion                  import fuse
from .explanation_generator   import generate_explanation

logger = logging.getLogger(__name__)


@dataclass
class ConfidenceResult:
    score:   int            # 0–100
    tier:    str            # "HIGH" | "MEDIUM" | "LOW"
    signals: dict           # raw signal values for audit trail
    degraded: bool
    warning:  Optional[str]
    explanation: str            # human-readable summary

    def to_dict(self) -> dict:
        return {
            "score":    self.score,
            "tier":     self.tier,
            "signals":  self.signals,
            "degraded": self.degraded,
            "warning":  self.warning,
            "explanation": self.explanation,
        }


class ConfidenceEngine:
    """
    Orchestrates Signal 1 + Signal 2 computation and fusion.

    Both scorers are loaded once at instantiation (model weights cached).
    """

    def score(
        self,
        answer:   str,
        chunks:   list[str],
        logprobs: list[float],
    ) -> ConfidenceResult:
        """
        Compute the full confidence score for one RAG inference result.

        Parameters
        ----------
        answer   : Generated answer text from the LLM.
        chunks   : Retrieved document chunks (list of strings, up to 5).
        logprobs : Per-token log-probabilities from the LLM generation.

        Returns
        -------
        ConfidenceResult
        """
        logger.info("Scoring answer (%d chars) against %d chunks with %d logprobs",
                    len(answer), len(chunks), len(logprobs))

        # --- Signal 1: Grounding Score --------------------------------------
        grounding_result = None
        grounding_score  = None
        try:
            grounding_result = grounding_scorer.compute(answer, chunks)
            grounding_score  = grounding_result.grounding_score
            logger.info("Grounding score: %.4f (%d/%d claims supported)",
                        grounding_score,
                        grounding_result.supported_claims,
                        grounding_result.num_claims)
        except Exception as e:
            logger.error("Grounding scorer failed: %s", e, exc_info=True)

        # --- Signal 2: Generation Confidence --------------------------------
        gen_result     = None
        gen_confidence = None
        try:
            gen_result     = generation_confidence_scorer.compute(logprobs)
            gen_confidence = gen_result.score
            logger.info("Generation confidence: raw=%.4f normalized=%.4f level=%s",
                        gen_result.raw_mean_prob, gen_confidence, gen_result.level)
        except Exception as e:
            logger.error("Gen confidence scorer failed: %s", e, exc_info=True)

        # --- Fusion ---------------------------------------------------------
        fusion = fuse(grounding_score, gen_confidence)
        logger.info("Fusion result: score=%d tier=%s degraded=%s",
                    fusion.score, fusion.tier, fusion.degraded)

        # --- Build audit signals dict ---------------------------------------
        signals = {
            "grounding_score":           grounding_score,
            "grounding_num_claims":      grounding_result.num_claims if grounding_result else None,
            "grounding_supported":       grounding_result.supported_claims if grounding_result else None,
            "gen_confidence_raw":        gen_result.raw_mean_prob if gen_result else None,
            "gen_confidence_normalized": gen_confidence,
            "gen_confidence_level":      gen_result.level if gen_result else None,
            "grounding_contribution":    fusion.grounding_contribution,
            "gen_conf_contribution":     fusion.gen_conf_contribution,
        }

        explanation = generate_explanation(
            score=fusion.score,
            tier=fusion.tier,
            grounding_score=grounding_score,
            grounding_num_claims=grounding_result.num_claims if grounding_result else None,
            grounding_supported=grounding_result.supported_claims if grounding_result else None,
            gen_confidence_level=gen_result.level if gen_result else None,
            gen_confidence_normalized=gen_confidence,
            degraded=fusion.degraded,
        )
        logger.info("Explanation: %s", explanation)

        return ConfidenceResult(
            score=fusion.score,
            tier=fusion.tier,
            signals=signals,
            degraded=fusion.degraded,
            warning=fusion.warning,
            explanation=explanation,
        )


# Module-level singleton
confidence_engine = ConfidenceEngine()
