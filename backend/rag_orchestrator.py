"""
rag_orchestrator.py
LangChain-based RAG pipeline orchestration for GroundCheck (Issue #62).

Wires together the existing components:
  - RetrievalPipeline  (retrieval.py)        — embed + search + cite
  - ModelService       (services/model_service.py) — LLM generation + confidence
  - Prompt templates   (defined below)       — system + RAG prompt construction

Public API
----------
rag_orchestrator.run(query, db_session, top_k) -> RAGResponse
rag_orchestrator.run_retrieval_only(query, top_k) -> List[Citation]

Design notes
------------
LangChain is used for:
  1. Prompt template management (ChatPromptTemplate)
  2. Output parsing (StrOutputParser)
  3. LCEL chain composition (retriever | prompt | llm | parser)

We do NOT use LangChain's built-in retrievers or LLM wrappers because
the project already has well-tested implementations in retrieval.py and
model_service.py. Instead we wrap them as thin LangChain-compatible
callables so the chain can be composed with the | operator.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import List, Optional

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnableLambda, RunnablePassthrough

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

    Matches the shape expected by GroundCheckResponse (Issue #86):
      - answer         → GroundCheckResponse.answer
      - citations      → GroundCheckResponse.citations  (via Citation.to_dict())
      - confidence     → GroundCheckResponse.confidence.signals.generation_confidence
      - retrieved_chunks → GroundCheckResponse.metadata.retrieved_chunks
    """
    query: str
    answer: str
    citations: List[Citation]
    confidence: Optional[ConfidenceMetrics]
    model_name: str
    retrieved_chunks: int
    processing_time_ms: int
    prompt_used: str = field(repr=False)  # full rendered prompt, useful for debugging

    def citations_as_dicts(self) -> List[dict]:
        """Serialize citations to GroundCheck JSON schema shape."""
        return [c.to_dict() for c in self.citations]

    def generation_confidence_score(self) -> Optional[float]:
        """Convenience accessor for the confidence signal float."""
        return self.confidence.score if self.confidence else None


# ---------------------------------------------------------------------------
# LangChain-compatible wrappers for existing components
# ---------------------------------------------------------------------------

def _make_retriever_runnable(pipeline: RetrievalPipeline, top_k: int):
    """
    Wrap RetrievalPipeline.retrieve() as a LangChain RunnableLambda.
    Input:  str (query)
    Output: List[Citation]
    """
    return RunnableLambda(lambda query: pipeline.retrieve(query, top_k=top_k))


def _make_context_formatter(pipeline: RetrievalPipeline):
    """
    Wrap RetrievalPipeline.format_context() as a RunnableLambda.
    Input:  List[Citation]
    Output: str  (formatted context block for prompt injection)
    """
    return RunnableLambda(pipeline.format_context)


def _make_llm_runnable(model_svc, db_session):
    """
    Wrap ModelService.generate() as a RunnableLambda.
    Input:  str (rendered prompt string)
    Output: InferenceResponse
    """
    def _call(prompt_str: str):
        request = InferenceRequest(prompt=prompt_str)
        return model_svc.generate(request, db_session)

    return RunnableLambda(_call)


# ---------------------------------------------------------------------------
# RAGOrchestrator
# ---------------------------------------------------------------------------

class RAGOrchestrator:
    """
    Orchestrates the full RAG pipeline using LangChain LCEL composition.

    Pipeline flow
    -------------
    query (str)
      │
      ├─► Retriever          → List[Citation]
      │        │
      │        └─► ContextFormatter → str (context block)
      │
      ├─► PromptTemplate     → ChatPromptValue  (system + user messages)
      │
      ├─► LLM                → InferenceResponse
      │
      └─► OutputParser       → RAGResponse

    Parameters
    ----------
    retrieval_pl : RetrievalPipeline
        Instance to use for retrieval. Defaults to the module singleton.
    model_svc : ModelService | None
        Instance to use for generation. If None, run() raises unless
        called via run_retrieval_only().
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
        self._model_svc = model_svc  # injected; avoids loading model at import time
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
        query : str
            User's natural language question.
        db_session : sqlalchemy.orm.Session
            Active DB session passed through to ModelService for logging.
        top_k : int
            Number of chunks to retrieve.

        Returns
        -------
        RAGResponse
        """
        if self._model_svc is None:
            raise RuntimeError(
                "RAGOrchestrator has no model_svc. "
                "Pass a ModelService instance to the constructor."
            )

        t_start = time.monotonic()

        # Step 1 — Retrieve
        citations = self._retrieval.retrieve(query, top_k=top_k)
        context = self._retrieval.format_context(citations)

        # Step 2 — Build prompt
        prompt_template = RAG_CHAT_PROMPT if citations else NO_CONTEXT_PROMPT
        rendered_messages = prompt_template.format_messages(
            context=context,
            question=query,
        )
        # Flatten to a single string for ModelService (which takes a prompt str)
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
    # LCEL chain (for inspection / future streaming use)
    # ------------------------------------------------------------------

    def build_chain(self, top_k: int = 5):
        """
        Build and return the full LCEL chain.

        The chain takes a dict {"question": str} and returns a rendered
        prompt string. Useful for inspecting the pipeline or hooking into
        LangChain tooling (e.g. LangSmith tracing).

        Note: LLM generation is NOT included in the LCEL chain because
        ModelService.generate() requires a db_session that isn't known
        at chain-build time. The chain produces the final prompt string;
        pass that to model_svc.generate() manually if needed.
        """
        retriever = _make_retriever_runnable(self._retrieval, top_k)
        formatter = _make_context_formatter(self._retrieval)

        chain = (
            RunnablePassthrough.assign(
                citations=lambda x: retriever.invoke(x["question"]),
            )
            | RunnablePassthrough.assign(
                context=lambda x: formatter.invoke(x["citations"]),
            )
            | RunnablePassthrough.assign(
                prompt=lambda x: RAG_CHAT_PROMPT.format_messages(
                    context=x["context"],
                    question=x["question"],
                )
            )
        )
        return chain

    # ------------------------------------------------------------------
    # Prompt rendering (for debugging / unit tests)
    # ------------------------------------------------------------------

    def render_prompt(self, query: str, citations: List[Citation]) -> str:
        """Return the rendered prompt string without running the LLM."""
        context = self._retrieval.format_context(citations)
        template = RAG_CHAT_PROMPT if citations else NO_CONTEXT_PROMPT
        messages = template.format_messages(context=context, question=query)
        return "\n".join(f"{m.type.upper()}: {m.content}" for m in messages)


# ---------------------------------------------------------------------------
# Module-level singleton
# Note: model_svc is NOT set here to avoid loading the LLM at import time.
# In main.py / routers, inject it after the model is loaded:
#
#   from rag_orchestrator import rag_orchestrator
#   from services.model_service import model_executor
#   rag_orchestrator._model_svc = model_executor
# ---------------------------------------------------------------------------

rag_orchestrator = RAGOrchestrator(
    retrieval_pl=retrieval_pipeline,
    similarity_threshold=0.0,
)