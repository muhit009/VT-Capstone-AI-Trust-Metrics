"""
explanation_generator.py — Human-readable explanations for confidence scores.

Turns the raw signal values from the confidence engine into 2-3 sentence
plain-English summaries that tell the user what the score means and what
they should do with the answer.

No Jinja2 needed — the templates are simple enough to handle with plain
string formatting.
"""
from __future__ import annotations

from typing import Optional


def generate_explanation(
    score: int,
    tier: str,
    grounding_score: Optional[float] = None,
    grounding_num_claims: Optional[int] = None,
    grounding_supported: Optional[int] = None,
    gen_confidence_level: Optional[str] = None,
    gen_confidence_normalized: Optional[float] = None,
    degraded: bool = False,
) -> str:
    """
    Generate a 2-3 sentence plain-English explanation for a confidence result.

    Parameters
    ----------
    score                    : Final fused score (0–100).
    tier                     : "HIGH", "MEDIUM", or "LOW".
    grounding_score          : Fraction of claims supported by documents (0–1).
    grounding_num_claims     : Total claims extracted from the answer.
    grounding_supported      : Claims with entailment score above 0.5.
    gen_confidence_level     : "HIGHLY_CONFIDENT", "MODERATE", or "UNCERTAIN".
    gen_confidence_normalized: Normalized generation confidence (0–1), used as
                               fallback if gen_confidence_level is not available.
    degraded                 : True if one signal was unavailable.

    Returns
    -------
    str — 2 to 3 sentences, plain English, no jargon.
    """
    parts = []

    # ------------------------------------------------------------------
    # Sentence 1 — Grounding (what the documents say about this answer)
    # ------------------------------------------------------------------
    if grounding_score is not None:
        claim_detail = _claim_detail(grounding_num_claims, grounding_supported)

        if grounding_score >= 0.8:
            parts.append(
                f"The answer is strongly supported by the retrieved documents{claim_detail}."
            )
        elif grounding_score >= 0.5:
            parts.append(
                f"The answer is partially supported by the retrieved documents{claim_detail}."
            )
        else:
            parts.append(
                f"The retrieved documents provide little support for this answer{claim_detail}."
            )
    else:
        parts.append("Document grounding could not be assessed.")

    # ------------------------------------------------------------------
    # Sentence 2 — Generation confidence (how sure the model was)
    # ------------------------------------------------------------------
    if gen_confidence_level is not None:
        parts.append(_gen_conf_sentence(gen_confidence_level))
    elif gen_confidence_normalized is not None:
        # Derive a level from the normalized value if the level string is absent
        if gen_confidence_normalized >= 0.8:
            parts.append(_gen_conf_sentence("HIGHLY_CONFIDENT"))
        elif gen_confidence_normalized >= 0.5:
            parts.append(_gen_conf_sentence("MODERATE"))
        else:
            parts.append(_gen_conf_sentence("UNCERTAIN"))
    elif degraded:
        parts.append("Generation confidence was unavailable for this query.")

    # ------------------------------------------------------------------
    # Sentence 3 — Action recommendation (what the user should do)
    # ------------------------------------------------------------------
    parts.append(_action(tier))

    return " ".join(p for p in parts if p)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _claim_detail(num_claims: Optional[int], supported: Optional[int]) -> str:
    """Return ' (X of Y claims verified)' if both values are present."""
    if num_claims is not None and supported is not None:
        noun = "claim" if num_claims == 1 else "claims"
        return f" ({supported} of {num_claims} {noun} verified)"
    return ""


def _gen_conf_sentence(level: str) -> str:
    return {
        "HIGHLY_CONFIDENT": "The model generated the response with high confidence.",
        "MODERATE":         "The model showed moderate confidence during generation.",
        "UNCERTAIN":        "The model was uncertain while generating the response.",
    }.get(level, f"Generation confidence: {level}.")


def _action(tier: str) -> str:
    return {
        "HIGH":   "This answer is safe to use.",
        "MEDIUM": "Verify the key claims before acting on this answer.",
        "LOW":    "Do not rely on this answer without additional verification.",
    }.get(tier, "")
