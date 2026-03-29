from __future__ import annotations

import importlib
import re
import sys

import pytest


def _simple_sent_tokenize(text: str) -> list[str]:
    # Split sentence endings without breaking decimal-like strings such as "8.8".
    return [
        part.strip()
        for part in re.split(r"(?<=[!?])\s+|(?<=\.)\s+(?=[A-Z])", text)
        if part.strip()
    ]


@pytest.fixture
def grounding_module(monkeypatch):
    class FakePipeline:
        def __init__(self):
            # Keep a call log so batching behavior can be asserted.
            self.calls: list[list[str]] = []

        def __call__(self, inputs: list[str]) -> list[list[dict]]:
            self.calls.append(list(inputs))
            results = []
            for text in inputs:
                chunk, claim = text.split(" [SEP] ", 1)

                # Return deterministic entailment scores so the grounding formula is testable.
                if "45 N·m" in claim and "45 N·m" in chunk:
                    entailment = 0.92
                elif "class 8.8" in claim and "class 8.8" in chunk:
                    entailment = 0.83
                else:
                    entailment = 0.12

                off_score = round((1.0 - entailment) / 2.0, 6)
                results.append([
                    {"label": "CONTRADICTION", "score": off_score},
                    {"label": "ENTAILMENT", "score": entailment},
                    {"label": "NEUTRAL", "score": off_score},
                ])
            return results

    monkeypatch.setattr("nltk.download", lambda *args, **kwargs: True)
    monkeypatch.setattr("transformers.pipeline", lambda *args, **kwargs: FakePipeline())

    # Reload the module so it picks up the fake pipeline during import.
    sys.modules.pop("confidence.grounding_scorer", None)
    module = importlib.import_module("confidence.grounding_scorer")
    monkeypatch.setattr(module.nltk, "sent_tokenize", _simple_sent_tokenize)
    module._FakePipeline = FakePipeline
    return module


def _build_scorer(module):
    # Bypass __init__ to avoid loading the real NLI model in unit tests.
    scorer = object.__new__(module.GroundingScorer)
    scorer._nli = module._FakePipeline()
    return scorer


def test_grounding_score_uses_max_entailment_per_claim(grounding_module):
    scorer = _build_scorer(grounding_module)

    answer = (
        "The maximum torque for M10 bolts is 45 N·m. "
        "This applies to class 8.8 bolts."
    )
    chunks = [
        "The maximum torque for M10 bolts is 45 N·m according to the fastener table.",
        "The specification applies to class 8.8 bolts in structural applications.",
    ]

    result = scorer.compute(answer, chunks)

    # Each claim should match its best chunk, then the score averages those maxima.
    assert result.grounding_score == pytest.approx(0.875, abs=1e-6)
    assert result.num_claims == 2
    assert result.supported_claims == 2
    assert result.claim_details[0].best_supporting_chunk_idx == 0
    assert result.claim_details[1].best_supporting_chunk_idx == 1


def test_no_extractable_claims_returns_zero_score(grounding_module):
    scorer = _build_scorer(grounding_module)

    result = scorer.compute("Sure.", ["Any supporting chunk would be ignored."])

    assert result.grounding_score == 0.0
    assert result.num_claims == 0
    assert result.supported_claims == 0
    assert result.claim_details == []


def test_empty_chunks_returns_zero_without_invalid_chunk_index(grounding_module):
    scorer = _build_scorer(grounding_module)

    answer = (
        "The maximum torque for M10 bolts is 45 N·m. "
        "This applies to class 8.8 bolts."
    )
    result = scorer.compute(answer, [])

    # Empty retrieval should not invent a supporting chunk index.
    assert result.grounding_score == 0.0
    assert result.num_claims == 2
    assert result.supported_claims == 0
    assert all(detail.best_supporting_chunk_idx is None for detail in result.claim_details)
    assert all(detail.max_entailment == 0.0 for detail in result.claim_details)


def test_nli_pairs_are_batched_for_all_claim_chunk_combinations(grounding_module):
    scorer = _build_scorer(grounding_module)

    answer = (
        "The maximum torque for M10 bolts is 45 N·m. "
        "This applies to class 8.8 bolts."
    )
    chunks = [
        "The maximum torque for M10 bolts is 45 N·m according to the fastener table.",
        "The specification applies to class 8.8 bolts in structural applications.",
    ]

    scorer.compute(answer, chunks)

    # Two claims x two chunks should produce one batched call with four pairs.
    assert len(scorer._nli.calls) == 1
    assert len(scorer._nli.calls[0]) == 4
    assert scorer._nli.calls[0][0] == (
        "The maximum torque for M10 bolts is 45 N·m according to the fastener table. "
        "[SEP] The maximum torque for M10 bolts is 45 N·m."
    )


def test_extract_claims_splits_sentences_and_filters_short_text(grounding_module):
    scorer = _build_scorer(grounding_module)

    claims = scorer._extract_claims(
        "Sure. The torque limit is 45 N·m. This applies to class 8.8 bolts."
    )

    # Short filler text should be dropped, leaving only factual claims.
    assert claims == [
        "The torque limit is 45 N·m.",
        "This applies to class 8.8 bolts.",
    ]


def test_extract_claims_handles_bullets_and_numbered_lists(grounding_module):
    scorer = _build_scorer(grounding_module)

    claims = scorer._extract_claims(
        "1. The torque limit is 45 N·m.\n"
        "2) This applies to class 8.8 bolts.\n"
        "- Zinc-coated fasteners follow the same specification."
    )

    # List formatting should normalize into plain claim strings.
    assert claims == [
        "The torque limit is 45 N·m.",
        "This applies to class 8.8 bolts.",
        "Zinc-coated fasteners follow the same specification.",
    ]


def test_extract_entailment_returns_zero_when_label_is_missing(grounding_module):
    scorer = _build_scorer(grounding_module)

    entailment = scorer._extract_entailment([
        {"label": "CONTRADICTION", "score": 0.6},
        {"label": "NEUTRAL", "score": 0.4},
    ])

    # Missing entailment output should degrade safely to zero support.
    assert entailment == 0.0