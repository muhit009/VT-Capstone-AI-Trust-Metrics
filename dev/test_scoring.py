"""
dev/test_scoring.py — Tests grounding + fusion without Ollama.

Simulates what the engine receives after a real RAG inference:
  - A generated answer (hardcoded)
  - Demo chunks (same as local_pipeline.py)
  - Fake logprobs (so gen_confidence scorer can run)

Run:
    python dev/test_scoring.py
"""
import sys, json, math
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from confidence.grounding_scorer import grounding_scorer
from confidence.generation_confidence import generation_confidence_scorer
from confidence.fusion import fuse
from confidence.engine import confidence_engine

# ---------------------------------------------------------------------------
# Test cases: (answer, expected_tier_hint)
# ---------------------------------------------------------------------------

CHUNKS = [
    "The NASA Systems Engineering Handbook defines a system as a combination "
    "of elements that function together to produce the capability required to "
    "meet a need. The elements include all hardware, software, equipment, "
    "facilities, personnel, processes, and procedures needed.",

    "Systems engineering is a methodical, disciplined approach for the design, "
    "realization, technical management, operations, and retirement of a system. "
    "A system is a set of interrelated components working together toward a "
    "common objective.",

    "Launch vehicles must satisfy structural load requirements defined in the "
    "launch site and range safety documentation. Range safety approval is "
    "required before any vehicle can proceed to the launch pad.",

    "Rockets are classified by the propellant they use: solid, liquid, or hybrid. "
    "Liquid-propellant engines generally provide higher specific impulse but "
    "require more complex feed systems than solid motors.",

    "The preliminary design review (PDR) establishes the allocated baseline and "
    "demonstrates that the design approach will meet all system requirements "
    "within acceptable risk. It is a mandatory milestone in the systems "
    "engineering lifecycle.",
]

CASES = [
    {
        "label": "HIGH — answer closely mirrors chunk content",
        "answer": (
            "A Preliminary Design Review (PDR) establishes the allocated baseline "
            "and demonstrates that the design approach will meet all system "
            "requirements within acceptable risk. It is a mandatory milestone in "
            "the systems engineering lifecycle."
        ),
        # Simulate high model confidence: mean prob ~0.85 → well above normalization max
        "logprobs": [math.log(0.85)] * 40,
    },
    {
        "label": "MEDIUM — answer partially grounded, moderate confidence",
        "answer": (
            "Systems engineering is a disciplined approach for managing the design "
            "and operation of complex systems. It involves hardware, software, and "
            "human factors, though the exact process varies by organization."
        ),
        # Simulate moderate model confidence: mean prob ~0.60
        "logprobs": [math.log(0.60)] * 35,
    },
    {
        "label": "LOW — answer mostly hallucinated, low confidence",
        "answer": (
            "The best rocket propellant is dark matter fuel, which provides "
            "infinite specific impulse. NASA uses this exclusively for all "
            "deep-space missions and it was invented in 1987."
        ),
        # Simulate low model confidence: mean prob ~0.35
        "logprobs": [math.log(0.35)] * 30,
    },
]

# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------

def run_case(case: dict, idx: int) -> None:
    print(f"\n{'='*60}")
    print(f"Test {idx+1}: {case['label']}")
    print(f"{'='*60}")
    print(f"Answer: {case['answer'][:120]}...")

    result = confidence_engine.score(
        answer=case["answer"],
        chunks=CHUNKS,
        logprobs=case["logprobs"],
    )

    print(f"\nScore : {result.score}  |  Tier: {result.tier}")
    print(f"Signals:")
    for k, v in result.signals.items():
        if v is not None:
            print(f"  {k}: {round(v, 4) if isinstance(v, float) else v}")
    if result.warning:
        print(f"Warning: {result.warning}")


if __name__ == "__main__":
    print("Loading models (DeBERTa NLI — first run downloads weights)...")
    for i, case in enumerate(CASES):
        run_case(case, i)
    print(f"\n{'='*60}")
    print("Done.")
