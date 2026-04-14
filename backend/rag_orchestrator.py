"""
rag_orchestrator.py
RAG pipeline orchestration — Retrieval → Prompt → LLM.

Wires together:
  - RetrievalPipeline  (retrieval.py)           — embed + search + cite
  - ModelService       (services/model_service.py) — LLM generation
  - Prompt templates   (defined below)           — system + RAG prompt construction

Public API
----------
rag_orchestrator.run(query, db_session, top_k) -> RAGResponse
rag_orchestrator.run_retrieval_only(query, top_k) -> List[Citation]
rag_orchestrator.render_prompt(query, citations) -> str   # debug / tests

Design note
-----------
LangChain is used only for ChatPromptTemplate and StrOutputParser.
We do not use LangChain's built-in retrievers or LLM wrappers — the project
has well-tested implementations in retrieval.py and model_service.py.
Confidence scoring is handled separately by confidence/engine.py and called
in routers/query.py after run() returns, keeping the orchestrator focused
on Retrieval + Generation only.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import List, Optional

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

from retrieval import RetrievalPipeline, Citation, retrieval_pipeline
from models.schemas import InferenceRequest, ConfidenceMetrics


# ---------------------------------------------------------------------------
# Prompt templates
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """\
You are a precise engineering assistant. Answer the user's question using \
ONLY the information in the provided context. If the context does not \
contain enough information to answer the question, say so explicitly — \
do not guess or use outside knowledge.

Always be concise and cite the source document and page number when making \
a specific factual claim (e.g. "per Materials_Handbook.pdf p.12").
"""

RAG_PROMPT_TEMPLATE = """\
{context}

Question: {question}

Answer:"""

# Full prompt: system message + RAG user message
RAG_CHAT_PROMPT = ChatPromptTemplate.from_messages([
    ("system", SYSTEM_PROMPT),
    ("human", RAG_PROMPT_TEMPLATE),
])

# Fallback prompt used when no documents are retrieved
NO_CONTEXT_PROMPT = ChatPromptTemplate.from_messages([
    ("system", SYSTEM_PROMPT),
    ("human", (
        "No relevant documents were found for the following question. "
        "Inform the user that you cannot answer without source documents.\n\n"
        "Question: {question}\n\nAnswer:"
    )),
])


# ---------------------------------------------------------------------------
# RAGResponse — typed return value
# ---------------------------------------------------------------------------

@dataclass
class RAGResponse:
    """
    Full output of a RAG pipeline run.

    answer         → GroundCheckResponse.answer
    citations      → GroundCheckResponse.citations
    retrieved_chunks → GroundCheckResponse.metadata.retrieved_chunks
    confidence     → legacy InferenceResponse.confidence (may be None for vLLM path)
    """
    query:              str
    answer:             str
    citations:          List[Citation]
    confidence:         Optional[ConfidenceMetrics]
    model_name:         str
    retrieved_chunks:   int
    processing_time_ms: int
    prompt_used:        str = field(repr=False)  # for debugging / audit

    def citations_as_dicts(self) -> List[dict]:
        """Serialize citations to GroundCheck JSON schema shape."""
        return [c.to_dict() for c in self.citations]

    def generation_confidence_score(self) -> Optional[float]:
        """Convenience accessor for the confidence signal float."""
        return self.confidence.score if self.confidence else None


# ---------------------------------------------------------------------------
# RAGOrchestrator
# ---------------------------------------------------------------------------

class RAGOrchestrator:
    """
    Orchestrates the RAG pipeline: Retrieve → Prompt → Generate.

    Confidence scoring is NOT done here — it is performed by
    confidence/engine.py in the router after run() returns, so that
    the confidence result is available for both response building and
    database logging without duplicating the computation.

    Parameters
    ----------
    retrieval_pl : RetrievalPipeline
        Instance to use for retrieval. Defaults to the module singleton.
    model_svc : ModelService | None
        Instance to use for generation. If None, run() raises RuntimeError.
    similarity_threshold : float
        Passed through to the retrieval pipeline.
    """

    def __init__(
        self,
        retrieval_pl: RetrievalPipeline = None,
        model_svc=None,
        similarity_threshold: float = 0.0,
    ):
        self._retrieval = retrieval_pl or RetrievalPipeline(
            similarity_threshold=similarity_threshold
        )
        self._model_svc = model_svc  # injected in main.py lifespan
        self._output_parser = StrOutputParser()

    # ------------------------------------------------------------------
    # Full RAG run
    # ------------------------------------------------------------------

    def run(
        self,
        query: str,
        db_session,
        top_k: int = 5,
    ) -> RAGResponse:
        """
        Execute the full Retrieval → Prompt → LLM pipeline.

        Parameters
        ----------
        query      : User's natural language question.
        db_session : Active SQLAlchemy session (passed to ModelService).
        top_k      : Number of chunks to retrieve.

        Returns
        -------
        RAGResponse with answer, citations, model metadata, and timing.
        Confidence scoring is left to the caller (routers/query.py).
        """
        if self._model_svc is None:
            raise RuntimeError(
                "RAGOrchestrator has no model_svc. "
                "Inject a ModelService instance before calling run()."
            )

        t_start = time.monotonic()

        # Step 1 — Retrieve
        citations = self._retrieval.retrieve(query, top_k=top_k)
        context   = self._retrieval.format_context(citations)

        # Step 2 — Build prompt
        prompt_template  = RAG_CHAT_PROMPT if citations else NO_CONTEXT_PROMPT
        rendered_messages = prompt_template.format_messages(
            context=context,
            question=query,
        )
        prompt_str = "\n".join(
            f"{m.type.upper()}: {m.content}" for m in rendered_messages
        )

        # Step 3 — Generate
        inference_response = self._model_svc.generate(
            InferenceRequest(prompt=prompt_str),
            db_session,
        )

        processing_time_ms = int((time.monotonic() - t_start) * 1000)

        return RAGResponse(
            query=query,
            answer=inference_response.generated_text,
            citations=citations,
            confidence=inference_response.confidence,
            model_name=inference_response.model_name,
            retrieved_chunks=len(citations),
            processing_time_ms=processing_time_ms,
            prompt_used=prompt_str,
        )

    # ------------------------------------------------------------------
    # Retrieval-only (no LLM call — useful for testing / grounding score)
    # ------------------------------------------------------------------

    def run_retrieval_only(
        self,
        query: str,
        top_k: int = 5,
    ) -> List[Citation]:
        """
        Run only the retrieval step. No LLM call, no DB session needed.
        Useful for computing grounding score independently of generation.
        """
        return self._retrieval.retrieve(query, top_k=top_k)

    # ------------------------------------------------------------------
    # Prompt rendering (for debugging / unit tests)
    # ------------------------------------------------------------------

    def render_prompt(self, query: str, citations: List[Citation]) -> str:
        """Return the rendered prompt string without running the LLM."""
        context  = self._retrieval.format_context(citations)
        template = RAG_CHAT_PROMPT if citations else NO_CONTEXT_PROMPT
        messages = template.format_messages(context=context, question=query)
        return "\n".join(f"{m.type.upper()}: {m.content}" for m in messages)


# ---------------------------------------------------------------------------
# Module-level singleton
# model_svc is injected in main.py lifespan to avoid loading the LLM at import.
# ---------------------------------------------------------------------------

rag_orchestrator = RAGOrchestrator(
    retrieval_pl=retrieval_pipeline,
    similarity_threshold=0.0,
)
