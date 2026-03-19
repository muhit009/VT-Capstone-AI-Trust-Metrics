"""
response_models.py
GroundCheck API response — Pydantic v2 models (schema v1.0.0)

Wired to the real confidence engine:
  - confidence/fusion.py        → FusionResult (score, tier, degraded, warning)
  - confidence/grounding_scorer.py → GroundingResult (grounding_score)
  - confidence/generation_confidence.py → GenConfidenceResult (score, level)
  - retrieval.py                → Citation (chunk metadata)

Usage
-----
from response_models import GroundCheckResponse, ResponseBuilder

result = ResponseBuilder.from_rag_run(
    query_id=...,
    query=...,
    rag_response=...,       # RAGResponse from rag_orchestrator
    confidence_result=...,  # ConfidenceResult from confidence_engine
    citations=...,          # List[Citation] from retrieval_pipeline
    processing_time_ms=...,
)
"""

from __future__ import annotations

import datetime
import secrets
from enum import Enum
from typing import Annotated, List, Optional

from pydantic import BaseModel, Field, field_validator, model_validator


# ---------------------------------------------------------------------------
# Enums — match real engine values
# ---------------------------------------------------------------------------

class ResponseStatus(str, Enum):
    SUCCESS         = "success"
    PARTIAL_SUCCESS = "partial_success"
    ERROR           = "error"


class ConfidenceTier(str, Enum):
    """
    Tier thresholds from confidence/config.py:
        HIGH   >= 70
        MEDIUM >= 40
        LOW     < 40
    Note: Issue #86 spec says HIGH>=80 but the real engine uses 70.
    The engine's thresholds take precedence.
    """
    HIGH   = "HIGH"
    MEDIUM = "MEDIUM"
    LOW    = "LOW"


class ErrorCode(str, Enum):
    NO_RELEVANT_DOCUMENTS              = "NO_RELEVANT_DOCUMENTS"
    RETRIEVAL_FAILURE                  = "RETRIEVAL_FAILURE"
    GENERATION_FAILURE                 = "GENERATION_FAILURE"
    NLI_FAILURE                        = "NLI_FAILURE"
    GENERATION_CONFIDENCE_UNAVAILABLE  = "GENERATION_CONFIDENCE_UNAVAILABLE"
    TIMEOUT                            = "TIMEOUT"
    INVALID_QUERY                      = "INVALID_QUERY"
    INTERNAL_ERROR                     = "INTERNAL_ERROR"


class ErrorSeverity(str, Enum):
    WARNING = "warning"
    ERROR   = "error"


# ---------------------------------------------------------------------------
# Constrained types
# ---------------------------------------------------------------------------

UnitFloat   = Annotated[float, Field(ge=0.0, le=1.0)]
Score0to100 = Annotated[int,   Field(ge=0, le=100)]


# ---------------------------------------------------------------------------
# Sub-models
# ---------------------------------------------------------------------------

class ConfidenceSignals(BaseModel):
    """
    Raw signal values before fusion.
    Maps directly from ConfidenceResult.signals (engine.py).
    """
    grounding_score:      Optional[UnitFloat] = Field(
        default=None,
        description="NLI entailment-based document support score (0–1). "
                    "From GroundingScorer. Null if grounding scorer failed."
    )
    generation_confidence: Optional[UnitFloat] = Field(
        default=None,
        description="Normalized mean token probability (0–1). "
                    "From GenerationConfidenceScorer. Null if logprobs unavailable."
    )


class FusionWeights(BaseModel):
    """
    Fusion weights from confidence/config.py (WEIGHT_GROUNDING=0.70, WEIGHT_GEN_CONF=0.30).
    Adjusted to 1.0/0.0 in degraded mode.
    """
    grounding:  float = Field(default=0.7, ge=0.0, le=1.0)
    generation: float = Field(default=0.3, ge=0.0, le=1.0)


class ConfidenceData(BaseModel):
    """
    Fused confidence result.
    Built from FusionResult (fusion.py) + raw signal results.
    """
    final_score: Score0to100 = Field(
        description="Fused 0–100 score. Formula: round(0.7*grounding + 0.3*gen_conf)*100. "
                    "Falls back to single-signal if one is missing (degraded mode)."
    )
    tier: ConfidenceTier = Field(
        description="HIGH>=70, MEDIUM>=40, LOW<40. From fusion.py _tier()."
    )
    signals: ConfidenceSignals
    weights: Optional[FusionWeights] = None
    explanation: str = Field(min_length=1, max_length=2048)
    warnings: Optional[List[str]] = Field(
        default=None,
        description="Non-fatal issues, e.g. one signal unavailable. "
                    "Mirrors FusionResult.warning and ConfidenceResult.warning."
    )
    degraded: bool = Field(
        default=False,
        description="True when one or both signals were unavailable. "
                    "Mirrors FusionResult.degraded."
    )

    @staticmethod
    def tier_from_score(score: int) -> ConfidenceTier:
        """Derive tier using the real engine thresholds (70/40, not 80/50)."""
        if score >= 70:
            return ConfidenceTier.HIGH
        if score >= 40:
            return ConfidenceTier.MEDIUM
        return ConfidenceTier.LOW

    @staticmethod
    def build_explanation(
        fusion_score: int,
        tier: str,
        grounding_score: Optional[float],
        gen_confidence: Optional[float],
        degraded: bool,
        fusion_warning: Optional[str],
    ) -> str:
        """Generate a human-readable explanation string from engine outputs."""
        parts = [f"{tier} confidence (score={fusion_score})."]

        if grounding_score is not None:
            parts.append(f"Grounding score: {grounding_score:.2f} (NLI document support).")
        else:
            parts.append("Grounding score: unavailable.")

        if gen_confidence is not None:
            parts.append(f"Generation confidence: {gen_confidence:.2f} (mean token probability).")
        else:
            parts.append("Generation confidence: unavailable.")

        if degraded and fusion_warning:
            parts.append(f"Degraded mode: {fusion_warning}")

        return " ".join(parts)

    @classmethod
    def from_confidence_result(cls, confidence_result) -> "ConfidenceData":
        """
        Build ConfidenceData directly from a ConfidenceResult (engine.py).

        Parameters
        ----------
        confidence_result : ConfidenceResult
            Output of confidence_engine.score().
        """
        signals = confidence_result.signals
        grounding  = signals.get("grounding_score")
        gen_conf   = signals.get("gen_confidence_normalized")
        degraded   = confidence_result.degraded
        warning    = confidence_result.warning

        # Derive weights from degraded state
        if grounding is not None and gen_conf is not None:
            weights = FusionWeights(grounding=0.7, generation=0.3)
        elif grounding is not None:
            weights = FusionWeights(grounding=1.0, generation=0.0)
        elif gen_conf is not None:
            weights = FusionWeights(grounding=0.0, generation=1.0)
        else:
            weights = None

        tier = ConfidenceTier(confidence_result.tier)
        explanation = cls.build_explanation(
            confidence_result.score, confidence_result.tier,
            grounding, gen_conf, degraded, warning,
        )

        return cls(
            final_score=confidence_result.score,
            tier=tier,
            signals=ConfidenceSignals(
                grounding_score=grounding,
                generation_confidence=gen_conf,
            ),
            weights=weights,
            explanation=explanation,
            warnings=[warning] if warning else None,
            degraded=degraded,
        )


class CitationModel(BaseModel):
    """
    Citation schema for API responses.
    Built from retrieval.Citation.to_dict() output.
    """
    citation_id:      str   = Field(description="Stable ID: <source_slug>__chunk_<N>")
    document:         str   = Field(description="Source document filename.")
    page:             Optional[int]   = Field(default=None, ge=1)
    section:          Optional[str]   = Field(default=None)
    chunk_id:         str   = Field(description="Internal vector store chunk ID.")
    similarity_score: UnitFloat = Field(description="Cosine similarity to query (0–1).")
    entailment_score: Optional[UnitFloat] = Field(
        default=None,
        description="NLI entailment score from grounding scorer (0–1). "
                    "Populated post-grounding if claim_details are available."
    )
    text_excerpt:     str   = Field(description="Chunk text preview (~300 chars).")

    @classmethod
    def from_citation(cls, citation, entailment_score: Optional[float] = None) -> "CitationModel":
        """Build from a retrieval.Citation dataclass instance."""
        d = citation.to_dict()
        return cls(
            citation_id=d["citation_id"],
            document=d["document"],
            page=d["page"],
            section=d["section"],
            chunk_id=d["chunk_id"],
            similarity_score=d["similarity_score"],
            entailment_score=entailment_score,
            text_excerpt=d["text_excerpt"],
        )


class ResponseMetadata(BaseModel):
    """Processing metadata for observability and audit."""
    model:               str  = Field(description="LLM identifier.")
    nli_model:           Optional[str] = Field(default=None, description="NLI model used for grounding.")
    timestamp:           datetime.datetime = Field(description="ISO 8601 UTC response timestamp.")
    processing_time_ms:  int  = Field(ge=0)
    retrieved_chunks:    Optional[int] = Field(default=None, ge=0)
    schema_version:      str  = Field(default="1.0.0")

    @field_validator("timestamp", mode="before")
    @classmethod
    def ensure_utc(cls, v):
        if isinstance(v, str):
            return datetime.datetime.fromisoformat(v.replace("Z", "+00:00"))
        if isinstance(v, datetime.datetime) and v.tzinfo is None:
            return v.replace(tzinfo=datetime.timezone.utc)
        return v


class ErrorInfo(BaseModel):
    code:     ErrorCode     = Field(description="Machine-readable error code.")
    message:  str           = Field(min_length=1, max_length=1024)
    severity: ErrorSeverity
    details:  Optional[str] = Field(default=None, max_length=4096)


# ---------------------------------------------------------------------------
# Root response model
# ---------------------------------------------------------------------------

class GroundCheckResponse(BaseModel):
    """
    Root GroundCheck API response (schema v1.0.0).

    Serialize with:
        response.model_dump(mode="json", exclude_none=True)
    """
    model_config = {"str_strip_whitespace": True}

    query_id:   str  = Field(pattern=r"^q_\d{8}_\d{6}_[a-z0-9]{6}$")
    query:      str  = Field(min_length=1, max_length=4096)
    answer:     Optional[str] = Field(default=None, max_length=32768)
    confidence: ConfidenceData
    citations:  List[CitationModel] = Field(default_factory=list)
    metadata:   ResponseMetadata
    error:      Optional[ErrorInfo] = None
    status:     ResponseStatus

    @model_validator(mode="after")
    def validate_status_consistency(self) -> "GroundCheckResponse":
        if self.status == ResponseStatus.ERROR:
            if self.answer is not None:
                raise ValueError("answer must be null when status='error'.")
            if self.error is None:
                raise ValueError("error must be present when status='error'.")
        if self.status == ResponseStatus.PARTIAL_SUCCESS and self.error is None:
            raise ValueError("error must be present when status='partial_success'.")
        if self.status == ResponseStatus.SUCCESS and self.error is not None:
            raise ValueError("error must be absent when status='success'.")
        return self


# ---------------------------------------------------------------------------
# ResponseBuilder — converts engine outputs → GroundCheckResponse
# ---------------------------------------------------------------------------

class ResponseBuilder:
    """
    Factory that assembles a GroundCheckResponse from real engine outputs.
    This is the main integration point called by routers/inference.py.
    """

    @staticmethod
    def make_query_id() -> str:
        """Generate a unique query ID in the required format."""
        ts = datetime.datetime.now(datetime.timezone.utc)
        return f"q_{ts.strftime('%Y%m%d_%H%M%S')}_{secrets.token_hex(3)}"

    @staticmethod
    def _enrich_citations(citations, grounding_result) -> List[CitationModel]:
        """
        Merge retrieval Citations with grounding entailment scores.

        If grounding_result has claim_details, we match each citation chunk
        to its best entailment score. Falls back gracefully if unavailable.
        """
        if grounding_result is None or not grounding_result.claim_details:
            return [CitationModel.from_citation(c) for c in citations]

        # Build chunk_index → best entailment score mapping
        chunk_entailment: dict[int, float] = {}
        for detail in grounding_result.claim_details:
            idx = detail.best_supporting_chunk_idx
            existing = chunk_entailment.get(idx, 0.0)
            chunk_entailment[idx] = max(existing, detail.max_entailment)

        result = []
        for i, citation in enumerate(citations):
            ent = chunk_entailment.get(i)
            result.append(CitationModel.from_citation(citation, entailment_score=ent))
        return result

    @classmethod
    def from_rag_run(
        cls,
        *,
        query: str,
        answer: str,
        citations: list,
        confidence_result,          # ConfidenceResult from confidence_engine.score()
        grounding_result=None,      # GroundingResult from grounding_scorer (for entailment enrichment)
        model_name: str,
        processing_time_ms: int,
        retrieved_chunks: int,
        nli_model: Optional[str] = "cross-encoder/nli-deberta-v3-small",
        query_id: Optional[str] = None,
    ) -> "GroundCheckResponse":
        """
        Build a full success or partial_success GroundCheckResponse.

        Parameters
        ----------
        query               : Original user query string.
        answer              : Generated answer from LLM.
        citations           : List[Citation] from retrieval_pipeline.retrieve().
        confidence_result   : ConfidenceResult from confidence_engine.score().
        grounding_result    : GroundingResult from grounding_scorer (optional, for entailment).
        model_name          : LLM model identifier string.
        processing_time_ms  : Total wall-clock time.
        retrieved_chunks    : Chunks retrieved before filtering.
        nli_model           : NLI model name for metadata.
        query_id            : Pre-generated query ID (auto-generated if None).
        """
        qid = query_id or cls.make_query_id()
        confidence_data = ConfidenceData.from_confidence_result(confidence_result)
        enriched_citations = cls._enrich_citations(citations, grounding_result)

        status = (
            ResponseStatus.PARTIAL_SUCCESS if confidence_result.degraded
            else ResponseStatus.SUCCESS
        )

        error = None
        if confidence_result.degraded and confidence_result.warning:
            # Map degraded signal warnings to appropriate error codes
            warning = confidence_result.warning
            if "Grounding" in warning:
                code = ErrorCode.NLI_FAILURE
            else:
                code = ErrorCode.GENERATION_CONFIDENCE_UNAVAILABLE
            error = ErrorInfo(
                code=code,
                message=warning,
                severity=ErrorSeverity.WARNING,
            )

        return GroundCheckResponse(
            query_id=qid,
            query=query,
            answer=answer,
            confidence=confidence_data,
            citations=enriched_citations,
            metadata=ResponseMetadata(
                model=model_name,
                nli_model=nli_model,
                timestamp=datetime.datetime.now(datetime.timezone.utc),
                processing_time_ms=processing_time_ms,
                retrieved_chunks=retrieved_chunks,
            ),
            error=error,
            status=status,
        )

    @classmethod
    def error_response(
        cls,
        *,
        query: str,
        error_code: ErrorCode,
        error_message: str,
        model_name: str,
        processing_time_ms: int = 0,
        query_id: Optional[str] = None,
    ) -> "GroundCheckResponse":
        """Build an error response when no answer could be produced."""
        qid = query_id or cls.make_query_id()
        return GroundCheckResponse(
            query_id=qid,
            query=query,
            answer=None,
            confidence=ConfidenceData(
                final_score=0,
                tier=ConfidenceTier.LOW,
                signals=ConfidenceSignals(
                    grounding_score=None,
                    generation_confidence=None,
                ),
                explanation="No answer generated.",
                degraded=True,
                warnings=["No answer produced — confidence score unavailable."],
            ),
            citations=[],
            metadata=ResponseMetadata(
                model=model_name,
                timestamp=datetime.datetime.now(datetime.timezone.utc),
                processing_time_ms=processing_time_ms,
                retrieved_chunks=0,
            ),
            error=ErrorInfo(
                code=error_code,
                message=error_message,
                severity=ErrorSeverity.ERROR,
            ),
            status=ResponseStatus.ERROR,
        )
    