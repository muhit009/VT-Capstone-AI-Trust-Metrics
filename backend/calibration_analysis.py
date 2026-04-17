"""
calibration_analysis.py — GroundCheck Calibration Testing & ECE Calculation

Measures how well GroundCheck's confidence scores align with actual answer
accuracy using Expected Calibration Error (ECE) methodology.

Calibration concept
-------------------
A well-calibrated system is correct ~80% of the time when it predicts 80%
confidence.  ECE is the weighted average gap between predicted confidence and
observed accuracy across equal-width bins:

    ECE = Σ_b  (|B_b| / n)  *  |avg_conf(B_b) − accuracy(B_b)|

Usage
-----
# Run against the live API (default: http://localhost:8000)
python calibration_analysis.py

# Specify a different API URL
python calibration_analysis.py --api-url http://localhost:8000

# Limit to a subset of questions (useful for quick smoke tests)
python calibration_analysis.py --max-questions 20

# Change the similarity threshold for counting an answer as correct
python calibration_analysis.py --threshold 0.65

Output files  (all written to ./calibration_outputs/)
-----------------------------------------------------
calibration_plot.png        — reliability diagram + tier accuracy chart
calibration_report.json     — full machine-readable metrics + per-question records
calibration_summary.txt     — human-readable console summary saved to disk
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import requests

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Optional heavy imports — degrade gracefully when unavailable
# ---------------------------------------------------------------------------
try:
    import matplotlib
    matplotlib.use("Agg")   # non-interactive backend — safe on HPC / headless
    import matplotlib.pyplot as plt
    import matplotlib.patches as mpatches
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False
    logger.warning("matplotlib not found — calibration plot will be skipped.")

try:
    from sentence_transformers import SentenceTransformer
    from sklearn.metrics.pairwise import cosine_similarity as sk_cosine
    SEMANTIC_AVAILABLE = True
    _SEMANTIC_MODEL: Optional[SentenceTransformer] = None
except ImportError:
    SEMANTIC_AVAILABLE = False
    logger.warning(
        "sentence-transformers / scikit-learn not found — "
        "falling back to token-overlap F1 accuracy metric."
    )

# ---------------------------------------------------------------------------
# Constants — match confidence/config.py
# ---------------------------------------------------------------------------
TIER_HIGH_THRESHOLD   = 70
TIER_MEDIUM_THRESHOLD = 40

N_BINS = 10                          # 10 equal-width bins: 0-10, 10-20, …, 90-100
ECE_TARGET            = 0.15        # acceptance criterion (ticket 6.8)
HIGH_TIER_ACC_TARGET  = 0.80        # HIGH tier accuracy target
LOW_TIER_ACC_TARGET   = 0.50        # LOW tier accuracy upper bound
SEPARATION_TARGET     = 30.0        # HIGH − LOW accuracy gap (percentage points)

SEMANTIC_MODEL_NAME  = "all-MiniLM-L6-v2"   # already shipped in the backend
SEMANTIC_THRESHOLD   = 0.70                  # cosine similarity → "correct"
TOKEN_F1_THRESHOLD   = 0.40                  # fallback word-overlap F1

DEFAULT_DATASET_PATH = Path(__file__).parent / "validation_dataset.json"
DEFAULT_OUTPUT_DIR   = Path(__file__).parent / "calibration_outputs"

QUESTION_TYPES = ["factual_lookup", "multi_step", "out_of_scope", "edge_case"]


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class QAPair:
    """One validation example loaded from validation_dataset.json."""
    id:                      str
    question:                str
    correct_answer:          str
    question_type:           str
    difficulty:              str
    expected_confidence_tier: str
    source_document:         Optional[str] = None
    page_number:             Optional[int] = None
    notes:                   str = ""


@dataclass
class PredictionRecord:
    """One prediction collected from GroundCheck for a single QAPair."""
    qa_id:                   str
    question:                str
    predicted_answer:        str
    correct_answer:          str
    confidence_score:        int     # 0–100 (integer from fused engine)
    confidence_tier:         str     # HIGH | MEDIUM | LOW
    expected_tier:           str     # from dataset
    tier_correct:            bool    # confidence_tier == expected_tier
    is_correct:              bool    # answer similarity >= threshold
    similarity_score:        float   # cosine or token-F1
    question_type:           str
    difficulty:              str
    source_document:         Optional[str]
    processing_time_ms:      int = 0
    status:                  str = "success"
    degraded:                bool = False


@dataclass
class BinStats:
    """Aggregated calibration statistics for one confidence bin."""
    bin_lower:       int     # e.g. 60
    bin_upper:       int     # e.g. 70
    count:           int
    avg_confidence:  float   # mean predicted confidence in bin [0, 1]
    accuracy:        float   # fraction correct in bin [0, 1]
    calibration_gap: float   # |avg_confidence − accuracy|

    @property
    def label(self) -> str:
        return f"{self.bin_lower}–{self.bin_upper}"


@dataclass
class TierMetrics:
    """Accuracy metrics for one confidence tier."""
    tier:     str
    count:    int
    accuracy: Optional[float]   # None if count == 0
    target:   Optional[float]   # acceptance target, or None if no target for this tier


@dataclass
class CalibrationMetrics:
    """All calibration metrics for one evaluation run."""
    # Primary ECE
    ece:                   float
    ece_pass:              bool

    # Tier metrics
    high_tier:    TierMetrics
    medium_tier:  TierMetrics
    low_tier:     TierMetrics
    tier_separation:       Optional[float]   # HIGH acc − LOW acc (percentage points)
    separation_pass:       bool

    # Overall counts
    total_predictions:     int
    total_correct:         int
    overall_accuracy:      float

    # Tier prediction accuracy (did the score map to the expected tier?)
    tier_prediction_accuracy: float

    # Per question-type accuracy
    per_type_accuracy:     Dict[str, float]

    # Bin-level data for plots
    bin_stats:             List[BinStats] = field(default_factory=list)

    def passes_all(self) -> bool:
        high_ok = (self.high_tier.accuracy is None or
                   self.high_tier.accuracy >= HIGH_TIER_ACC_TARGET)
        low_ok  = (self.low_tier.accuracy  is None or
                   self.low_tier.accuracy  <  LOW_TIER_ACC_TARGET)
        return self.ece_pass and high_ok and low_ok and self.separation_pass

    def summary_dict(self) -> dict:
        """Compact dict for the top-level JSON report."""
        return {
            "ece":                     self.ece,
            "ece_pass":                self.ece_pass,
            "total_predictions":       self.total_predictions,
            "total_correct":           self.total_correct,
            "overall_accuracy":        self.overall_accuracy,
            "tier_prediction_accuracy": self.tier_prediction_accuracy,
            "high_tier_accuracy":      self.high_tier.accuracy,
            "high_tier_count":         self.high_tier.count,
            "medium_tier_accuracy":    self.medium_tier.accuracy,
            "medium_tier_count":       self.medium_tier.count,
            "low_tier_accuracy":       self.low_tier.accuracy,
            "low_tier_count":          self.low_tier.count,
            "tier_separation_pp":      self.tier_separation,
            "separation_pass":         self.separation_pass,
            "per_type_accuracy":       self.per_type_accuracy,
            "passes_all":              self.passes_all(),
        }


# ---------------------------------------------------------------------------
# Accuracy helpers
# ---------------------------------------------------------------------------

def _get_semantic_model() -> Optional["SentenceTransformer"]:
    global _SEMANTIC_MODEL
    if not SEMANTIC_AVAILABLE:
        return None
    if _SEMANTIC_MODEL is None:
        logger.info("Loading semantic similarity model '%s' …", SEMANTIC_MODEL_NAME)
        _SEMANTIC_MODEL = SentenceTransformer(SEMANTIC_MODEL_NAME)
    return _SEMANTIC_MODEL


def token_overlap_f1(pred: str, ref: str) -> float:
    """
    Word-level unigram F1 (SQuAD-style) — fallback when sentence-transformers
    is unavailable.
    """
    pred_tokens = set(pred.lower().split())
    ref_tokens  = set(ref.lower().split())
    if not pred_tokens or not ref_tokens:
        return 0.0
    common = pred_tokens & ref_tokens
    if not common:
        return 0.0
    precision = len(common) / len(pred_tokens)
    recall    = len(common) / len(ref_tokens)
    return 2 * precision * recall / (precision + recall)


def compute_similarity(text_a: str, text_b: str) -> float:
    """
    Return a similarity score in [0, 1] between two answer strings.
    Uses cosine similarity via SentenceTransformer when available,
    falls back to token F1 otherwise.
    """
    model = _get_semantic_model()
    if model is not None:
        embs = model.encode([text_a, text_b], normalize_embeddings=True)
        return float(sk_cosine([embs[0]], [embs[1]])[0][0])
    return token_overlap_f1(text_a, text_b)


def is_correct(
    predicted: str,
    reference: str,
    threshold: float = SEMANTIC_THRESHOLD,
) -> Tuple[bool, float]:
    """
    Returns (correct: bool, similarity: float).

    For out-of-scope questions the reference answer typically starts with
    "This information is not available in the corpus."  If the predicted
    answer also expresses inability to answer, similarity will be high.
    """
    if not predicted.strip():
        return False, 0.0
    sim       = compute_similarity(predicted, reference)
    effective = threshold if SEMANTIC_AVAILABLE else TOKEN_F1_THRESHOLD
    return (sim >= effective), round(sim, 4)


# ---------------------------------------------------------------------------
# ECE Calculator
# ---------------------------------------------------------------------------

class ECECalculator:
    """
    Computes Expected Calibration Error using equal-width bins.

    ECE = Σ_b  (n_b / n)  *  |avg_conf(b) − acc(b)|
    """

    def __init__(self, n_bins: int = N_BINS):
        self.n_bins = n_bins
        self.edges  = np.linspace(0, 100, n_bins + 1)   # 0, 10, 20, …, 100

    def _bin_index(self, score: int) -> int:
        if score >= 100:
            return self.n_bins - 1
        return int(score // (100 / self.n_bins))

    def compute(
        self,
        predictions: List[PredictionRecord],
    ) -> Tuple[float, List[BinStats]]:
        """
        Compute ECE and per-bin statistics.

        Returns
        -------
        (ece: float, bin_stats: List[BinStats])
        """
        if not predictions:
            raise ValueError("No predictions provided to ECECalculator.")

        n = len(predictions)
        # bins[i] → list of (confidence_fraction, is_correct)
        bins: List[List[Tuple[float, bool]]] = [[] for _ in range(self.n_bins)]

        for rec in predictions:
            idx = self._bin_index(rec.confidence_score)
            bins[idx].append((rec.confidence_score / 100.0, rec.is_correct))

        bin_stats: List[BinStats] = []
        ece = 0.0

        for i, bin_data in enumerate(bins):
            lo  = int(self.edges[i])
            hi  = int(self.edges[i + 1])
            cnt = len(bin_data)

            if cnt == 0:
                bin_stats.append(BinStats(
                    bin_lower=lo, bin_upper=hi, count=0,
                    avg_confidence=0.0, accuracy=0.0, calibration_gap=0.0,
                ))
                continue

            avg_conf = float(np.mean([c for c, _ in bin_data]))
            accuracy = float(np.mean([int(ok) for _, ok in bin_data]))
            gap      = abs(avg_conf - accuracy)
            ece     += (cnt / n) * gap

            bin_stats.append(BinStats(
                bin_lower=lo, bin_upper=hi, count=cnt,
                avg_confidence=round(avg_conf, 4),
                accuracy=round(accuracy, 4),
                calibration_gap=round(gap, 4),
            ))

        return round(ece, 4), bin_stats


# ---------------------------------------------------------------------------
# Calibration Plotter
# ---------------------------------------------------------------------------

class CalibrationPlotter:
    """Generates the reliability diagram and tier accuracy bar chart."""

    TIER_COLORS = {
        "HIGH":   "#2ca02c",   # green
        "MEDIUM": "#ff7f0e",   # orange
        "LOW":    "#d62728",   # red
    }

    @staticmethod
    def plot(
        metrics:     CalibrationMetrics,
        output_path: Path,
    ) -> None:
        if not MATPLOTLIB_AVAILABLE:
            logger.warning("matplotlib unavailable — skipping calibration plot.")
            return

        fig, axes = plt.subplots(1, 2, figsize=(15, 6))
        title = (
            f"GroundCheck Calibration  |  ECE = {metrics.ece:.4f}  "
            f"({'PASS' if metrics.ece_pass else 'FAIL'})"
        )
        fig.suptitle(title, fontsize=13, fontweight="bold")

        # ---- Left panel: Reliability diagram --------------------------------
        ax = axes[0]
        populated = [b for b in metrics.bin_stats if b.count > 0]

        # Bar for observed accuracy, shaded gap for calibration error
        for b in populated:
            center = (b.bin_lower + b.bin_upper) / 2 / 100
            width  = (b.bin_upper - b.bin_lower) / 100 * 0.85
            # Blue bar = observed accuracy
            ax.bar(center, b.accuracy, width=width,
                   color="#4C72B0", alpha=0.7, align="center")
            # Red overlay = gap between confidence and accuracy
            gap_color = "#d62728" if b.avg_confidence > b.accuracy else "#2ca02c"
            ax.bar(
                center,
                b.avg_confidence - b.accuracy,
                width=width,
                bottom=b.accuracy,
                color=gap_color,
                alpha=0.4,
                hatch="///",
            )
            # Annotate count
            ax.text(
                center, min(b.avg_confidence, b.accuracy) / 2 + 0.01,
                str(b.count),
                ha="center", va="bottom", fontsize=7, color="white",
                fontweight="bold",
            )

        # Perfect calibration diagonal
        ax.plot([0, 1], [0, 1], "k--", linewidth=1.5, label="Perfect calibration")
        ax.set_xlabel("Mean predicted confidence", fontsize=11)
        ax.set_ylabel("Observed accuracy", fontsize=11)
        ax.set_title("Reliability Diagram", fontsize=12)
        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1.05)
        ax.set_xticks(np.arange(0, 1.1, 0.1))
        ax.set_yticks(np.arange(0, 1.1, 0.1))
        ax.grid(True, alpha=0.3)

        # Legend patches
        over_patch  = mpatches.Patch(color="#d62728", alpha=0.5, hatch="///",
                                     label="Overconfident gap")
        under_patch = mpatches.Patch(color="#2ca02c", alpha=0.5, hatch="///",
                                     label="Underconfident gap")
        acc_patch   = mpatches.Patch(color="#4C72B0", alpha=0.7,
                                     label="Observed accuracy")
        ax.legend(handles=[acc_patch, over_patch, under_patch,
                            mpatches.Patch(color="none", label="──── Perfect calib.")],
                  fontsize=8, loc="upper left")

        # ECE annotation
        ece_text = f"ECE = {metrics.ece:.4f}"
        pass_text = "PASS ✓" if metrics.ece_pass else f"FAIL ✗ (target < {ECE_TARGET})"
        ax.text(0.97, 0.05,
                f"{ece_text}\n{pass_text}",
                transform=ax.transAxes, fontsize=9, ha="right",
                bbox=dict(boxstyle="round,pad=0.4", facecolor="lightyellow",
                          edgecolor="gray", alpha=0.9))

        # ---- Right panel: Tier accuracy bar chart ---------------------------
        ax2 = axes[1]
        tier_data = [
            ("HIGH\n(≥70)", metrics.high_tier),
            ("MEDIUM\n(40–69)", metrics.medium_tier),
            ("LOW\n(<40)", metrics.low_tier),
        ]
        labels   = [t[0] for t in tier_data]
        accs     = [(t[1].accuracy or 0.0) for t in tier_data]
        counts   = [t[1].count for t in tier_data]
        colors   = [CalibrationPlotter.TIER_COLORS[t[1].tier] for t in tier_data]

        bars = ax2.bar(labels, accs, color=colors, alpha=0.75,
                       edgecolor="black", width=0.5)

        # Target reference lines
        ax2.axhline(HIGH_TIER_ACC_TARGET, color="#2ca02c", linestyle="--",
                    linewidth=1.5, label=f"HIGH target ({HIGH_TIER_ACC_TARGET:.0%})")
        ax2.axhline(LOW_TIER_ACC_TARGET, color="#d62728", linestyle="--",
                    linewidth=1.5, label=f"LOW target (<{LOW_TIER_ACC_TARGET:.0%})")

        # Annotate bars
        for bar, acc, cnt in zip(bars, accs, counts):
            ax2.text(
                bar.get_x() + bar.get_width() / 2,
                acc + 0.015,
                f"{acc:.1%}\n(n={cnt})",
                ha="center", va="bottom", fontsize=9,
            )

        # Tier separation annotation
        if metrics.tier_separation is not None:
            sep_str = (
                f"Tier separation: {metrics.tier_separation:+.1f} pp  "
                f"({'PASS ✓' if metrics.separation_pass else 'FAIL ✗'})"
            )
            ax2.text(0.5, -0.12, sep_str, transform=ax2.transAxes,
                     ha="center", fontsize=9,
                     color="#2ca02c" if metrics.separation_pass else "#d62728")

        ax2.set_ylim(0, 1.15)
        ax2.set_ylabel("Answer accuracy", fontsize=11)
        ax2.set_title("Tier-Specific Answer Accuracy", fontsize=12)
        ax2.legend(fontsize=9, loc="upper right")
        ax2.grid(True, alpha=0.3, axis="y")

        plt.tight_layout()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        plt.savefig(output_path, dpi=150, bbox_inches="tight")
        plt.close(fig)
        logger.info("Calibration plot saved → %s", output_path)


# ---------------------------------------------------------------------------
# GroundCheck API Client
# ---------------------------------------------------------------------------

class GroundCheckClient:
    """Thin wrapper around POST /api/v1/query."""

    def __init__(self, base_url: str = "http://localhost:8000", timeout: int = 180):
        self.base_url = base_url.rstrip("/")
        self.timeout  = timeout

    def health_check(self) -> bool:
        try:
            r = requests.get(f"{self.base_url}/v1/health", timeout=10)
            return r.status_code < 500
        except requests.RequestException:
            return False

    def query(self, question: str, top_k: int = 5) -> dict:
        """Submit one query; raises requests.HTTPError on 4xx / 5xx."""
        r = requests.post(
            f"{self.base_url}/api/v1/query",
            json={"query": question, "top_k": top_k},
            timeout=self.timeout,
        )
        r.raise_for_status()
        return r.json()


# ---------------------------------------------------------------------------
# Calibration Runner
# ---------------------------------------------------------------------------

class CalibrationRunner:
    """
    Orchestrates the full calibration evaluation:

    1. Load validation dataset from validation_dataset.json
    2. Submit each question to GroundCheck via the REST API
    3. Score answer accuracy with semantic similarity
    4. Compute ECE and tier metrics
    5. Generate reliability diagram and tier accuracy chart
    6. Write JSON report and console summary
    """

    def __init__(
        self,
        api_url:    str   = "http://localhost:8000",
        top_k:      int   = 5,
        delay_s:    float = 0.5,
        threshold:  float = SEMANTIC_THRESHOLD,
        output_dir: Path  = DEFAULT_OUTPUT_DIR,
    ):
        self.client      = GroundCheckClient(api_url)
        self.top_k       = top_k
        self.delay_s     = delay_s
        self.threshold   = threshold
        self.output_dir  = output_dir
        self.ece_calc    = ECECalculator()
        self.plotter     = CalibrationPlotter()

    # ---- Dataset loading ---------------------------------------------------

    @staticmethod
    def load_dataset(path: Path, max_questions: Optional[int] = None) -> List[QAPair]:
        """Load validation_dataset.json → List[QAPair]."""
        with open(path) as f:
            raw = json.load(f)

        # Support both flat list and {metadata, questions} formats
        items = raw if isinstance(raw, list) else raw.get("questions", [])

        pairs: List[QAPair] = []
        for item in items:
            pairs.append(QAPair(
                id=item.get("id", "?"),
                question=item.get("question", item.get("query", "")),
                correct_answer=item["correct_answer"],
                question_type=item.get("question_type", "general"),
                difficulty=item.get("difficulty", "medium"),
                expected_confidence_tier=item.get("expected_confidence_tier", "MEDIUM"),
                source_document=item.get("source_document"),
                page_number=item.get("page_number"),
                notes=item.get("notes", ""),
            ))

        if max_questions and len(pairs) > max_questions:
            pairs = pairs[:max_questions]
            logger.info("Truncated dataset to %d questions.", max_questions)

        logger.info("Loaded %d validation questions from %s", len(pairs), path)
        return pairs

    # ---- Prediction collection --------------------------------------------

    def _query_one(self, pair: QAPair) -> Optional[PredictionRecord]:
        """Submit one question; return PredictionRecord or None on failure."""
        try:
            t0   = time.monotonic()
            resp = self.client.query(pair.question, top_k=self.top_k)
            elapsed = int((time.monotonic() - t0) * 1000)

            predicted  = resp.get("answer") or ""
            score      = int(resp.get("confidence", {}).get("final_score", 0))
            tier       = resp.get("confidence", {}).get("tier", "LOW")
            degraded   = resp.get("confidence", {}).get("degraded", False)
            status     = resp.get("status", "success")

            correct, sim = is_correct(predicted, pair.correct_answer, self.threshold)

            return PredictionRecord(
                qa_id=pair.id,
                question=pair.question,
                predicted_answer=predicted,
                correct_answer=pair.correct_answer,
                confidence_score=score,
                confidence_tier=tier,
                expected_tier=pair.expected_confidence_tier,
                tier_correct=(tier == pair.expected_confidence_tier),
                is_correct=correct,
                similarity_score=sim,
                question_type=pair.question_type,
                difficulty=pair.difficulty,
                source_document=pair.source_document,
                processing_time_ms=elapsed,
                status=status,
                degraded=bool(degraded),
            )

        except requests.HTTPError as e:
            logger.error("HTTP error on question %s: %s", pair.id, e)
        except requests.ConnectionError:
            logger.error("Cannot connect to API for question %s", pair.id)
        except Exception as e:
            logger.error("Unexpected error on question %s: %s", pair.id, e, exc_info=True)
        return None

    def collect_predictions(self, pairs: List[QAPair]) -> List[PredictionRecord]:
        """Run all questions through GroundCheck and collect PredictionRecords."""
        records: List[PredictionRecord] = []
        for i, pair in enumerate(pairs, 1):
            logger.info(
                "[%d/%d] %-6s  %s",
                i, len(pairs), pair.id, pair.question[:70],
            )
            rec = self._query_one(pair)
            if rec:
                mark = "✓" if rec.is_correct else "✗"
                tier_mark = "=" if rec.tier_correct else "≠"
                logger.info(
                    "         ans=%s  score=%3d (%s)  tier%s%s  sim=%.3f",
                    mark, rec.confidence_score, rec.confidence_tier,
                    tier_mark, rec.expected_tier, rec.similarity_score,
                )
                records.append(rec)
            else:
                logger.warning("         !! Skipped — no valid response")

            if i < len(pairs):
                time.sleep(self.delay_s)

        logger.info(
            "\nCollected %d/%d predictions  (%.0f%% success rate)",
            len(records), len(pairs),
            100 * len(records) / max(len(pairs), 1),
        )
        return records

    # ---- Metrics -----------------------------------------------------------

    @staticmethod
    def _tier_metrics(
        records: List[PredictionRecord],
        tier:    str,
        target:  Optional[float],
    ) -> TierMetrics:
        subset = [r for r in records if r.confidence_tier == tier]
        if not subset:
            return TierMetrics(tier=tier, count=0, accuracy=None, target=target)
        acc = round(float(np.mean([int(r.is_correct) for r in subset])), 4)
        return TierMetrics(tier=tier, count=len(subset), accuracy=acc, target=target)

    def compute_metrics(
        self,
        records: List[PredictionRecord],
    ) -> CalibrationMetrics:
        """Compute all calibration metrics from collected PredictionRecords."""
        if not records:
            raise ValueError("No predictions to evaluate.")

        ece, bin_stats = self.ece_calc.compute(records)

        high   = self._tier_metrics(records, "HIGH",   HIGH_TIER_ACC_TARGET)
        medium = self._tier_metrics(records, "MEDIUM", None)
        low    = self._tier_metrics(records, "LOW",    LOW_TIER_ACC_TARGET)

        # Tier separation in percentage points
        separation: Optional[float] = None
        if high.accuracy is not None and low.accuracy is not None:
            separation = round((high.accuracy - low.accuracy) * 100, 2)
        sep_pass = (separation is None) or (separation >= SEPARATION_TARGET)

        # Overall accuracy
        n_correct = sum(int(r.is_correct) for r in records)
        overall   = round(n_correct / len(records), 4)

        # Tier prediction accuracy
        n_tier_correct = sum(int(r.tier_correct) for r in records)
        tier_acc       = round(n_tier_correct / len(records), 4)

        # Per question-type accuracy
        per_type: Dict[str, float] = {}
        for qtype in QUESTION_TYPES:
            subset = [r for r in records if r.question_type == qtype]
            if subset:
                per_type[qtype] = round(
                    float(np.mean([int(r.is_correct) for r in subset])), 4
                )

        return CalibrationMetrics(
            ece=ece,
            ece_pass=(ece < ECE_TARGET),
            high_tier=high,
            medium_tier=medium,
            low_tier=low,
            tier_separation=separation,
            separation_pass=sep_pass,
            total_predictions=len(records),
            total_correct=n_correct,
            overall_accuracy=overall,
            tier_prediction_accuracy=tier_acc,
            per_type_accuracy=per_type,
            bin_stats=bin_stats,
        )

    # ---- Output ------------------------------------------------------------

    def save_report(
        self,
        metrics: CalibrationMetrics,
        records: List[PredictionRecord],
        path:    Path,
    ) -> None:
        report = {
            "summary": metrics.summary_dict(),
            "acceptance_criteria": {
                "ece_target":                ECE_TARGET,
                "high_tier_accuracy_min":    HIGH_TIER_ACC_TARGET,
                "low_tier_accuracy_max":     LOW_TIER_ACC_TARGET,
                "tier_separation_min_pp":    SEPARATION_TARGET,
            },
            "pass_fail": {
                "ece":            metrics.ece_pass,
                "high_tier":      (metrics.high_tier.accuracy is None or
                                   metrics.high_tier.accuracy >= HIGH_TIER_ACC_TARGET),
                "low_tier":       (metrics.low_tier.accuracy  is None or
                                   metrics.low_tier.accuracy  <  LOW_TIER_ACC_TARGET),
                "tier_separation": metrics.separation_pass,
                "overall":         metrics.passes_all(),
            },
            "bins": [asdict(b) for b in metrics.bin_stats],
            "predictions": [asdict(r) for r in records],
        }
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            json.dump(report, f, indent=2, default=str)
        logger.info("Calibration report saved → %s", path)

    @staticmethod
    def _pass_fail(flag: bool) -> str:
        return "PASS ✓" if flag else "FAIL ✗"

    def print_and_save_summary(
        self,
        metrics: CalibrationMetrics,
        path:    Path,
    ) -> None:
        def fmt_acc(v: Optional[float]) -> str:
            return f"{v:.1%}" if v is not None else "N/A (no samples)"

        high_ok = (metrics.high_tier.accuracy is None or
                   metrics.high_tier.accuracy >= HIGH_TIER_ACC_TARGET)
        low_ok  = (metrics.low_tier.accuracy  is None or
                   metrics.low_tier.accuracy  <  LOW_TIER_ACC_TARGET)

        lines = [
            "",
            "=" * 65,
            "  GROUNDCHECK CALIBRATION RESULTS",
            "=" * 65,
            f"  Similarity metric : {'semantic (cosine)' if SEMANTIC_AVAILABLE else 'token overlap F1'}",
            f"  Total predictions : {metrics.total_predictions}",
            f"  Overall accuracy  : {fmt_acc(metrics.overall_accuracy)}",
            f"  Tier pred. acc.   : {fmt_acc(metrics.tier_prediction_accuracy)}",
            "",
            f"  ECE (target < {ECE_TARGET})  :  {metrics.ece:.4f}  "
            f"{self._pass_fail(metrics.ece_pass)}",
            "",
            "  Answer accuracy by confidence tier:",
            f"    HIGH   (≥70,  n={metrics.high_tier.count:3d})  :  "
            f"{fmt_acc(metrics.high_tier.accuracy)}  "
            f"(target ≥{HIGH_TIER_ACC_TARGET:.0%})  {self._pass_fail(high_ok)}",
            f"    MEDIUM (40–69,n={metrics.medium_tier.count:3d})  :  "
            f"{fmt_acc(metrics.medium_tier.accuracy)}  (no target)",
            f"    LOW    (<40,  n={metrics.low_tier.count:3d})  :  "
            f"{fmt_acc(metrics.low_tier.accuracy)}  "
            f"(target <{LOW_TIER_ACC_TARGET:.0%})   {self._pass_fail(low_ok)}",
            "",
        ]

        if metrics.tier_separation is not None:
            lines.append(
                f"  Tier separation   :  {metrics.tier_separation:+.1f} pp  "
                f"(target ≥{SEPARATION_TARGET:.0f} pp)  "
                f"{self._pass_fail(metrics.separation_pass)}"
            )

        if metrics.per_type_accuracy:
            lines.append("")
            lines.append("  Answer accuracy by question type:")
            for qtype, acc in metrics.per_type_accuracy.items():
                lines.append(f"    {qtype:<20s}  {acc:.1%}")

        lines += [
            "",
            "-" * 65,
            "  Calibration bins (non-empty only):",
            f"    {'Bin':>8s}  {'Count':>5s}  {'Avg conf':>9s}  "
            f"{'Accuracy':>9s}  {'Gap':>6s}",
        ]
        for b in metrics.bin_stats:
            if b.count > 0:
                lines.append(
                    f"    {b.label:>8s}  {b.count:>5d}  "
                    f"{b.avg_confidence:>8.1%}  {b.accuracy:>8.1%}  "
                    f"{b.calibration_gap:>5.4f}"
                )

        lines += [
            "",
            "=" * 65,
            f"  OVERALL  :  {self._pass_fail(metrics.passes_all())}",
            "=" * 65,
            "",
        ]

        text = "\n".join(lines)
        print(text)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            f.write(text)
        logger.info("Summary saved → %s", path)

    # ---- Main run ----------------------------------------------------------

    def run(
        self,
        dataset_path: Path = DEFAULT_DATASET_PATH,
        max_questions: Optional[int] = None,
    ) -> CalibrationMetrics:
        """
        Full calibration pipeline:
        load → predict → score → ECE → plot → report → summary.

        Returns CalibrationMetrics.
        """
        # 1. Health check
        if not self.client.health_check():
            logger.error(
                "GroundCheck API is not reachable at %s.\n"
                "Start the backend first:  uvicorn main:app --reload",
                self.client.base_url,
            )
            sys.exit(1)
        logger.info("API reachable at %s", self.client.base_url)

        # 2. Load dataset
        pairs = self.load_dataset(dataset_path, max_questions=max_questions)

        # 3. Collect predictions
        records = self.collect_predictions(pairs)
        if not records:
            logger.error("No predictions collected — cannot compute metrics.")
            sys.exit(1)

        # 4. Compute metrics
        metrics = self.compute_metrics(records)

        # 5. Generate outputs
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.plotter.plot(metrics, self.output_dir / "calibration_plot.png")
        self.save_report(metrics, records, self.output_dir / "calibration_report.json")
        self.print_and_save_summary(metrics, self.output_dir / "calibration_summary.txt")

        return metrics


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="GroundCheck calibration testing and ECE calculation.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument(
        "--dataset",
        type=Path,
        default=DEFAULT_DATASET_PATH,
        help="Path to the validation dataset JSON file.",
    )
    p.add_argument(
        "--api-url",
        default="http://localhost:8000",
        help="Base URL of the GroundCheck backend API.",
    )
    p.add_argument(
        "--top-k",
        type=int,
        default=5,
        help="Number of document chunks to retrieve per query.",
    )
    p.add_argument(
        "--max-questions",
        type=int,
        default=None,
        help="Limit evaluation to the first N questions (useful for quick tests).",
    )
    p.add_argument(
        "--threshold",
        type=float,
        default=SEMANTIC_THRESHOLD,
        help="Similarity threshold above which an answer is counted as correct.",
    )
    p.add_argument(
        "--delay",
        type=float,
        default=0.5,
        help="Seconds to wait between API calls.",
    )
    p.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="Directory for output files (plot, report, summary).",
    )
    return p.parse_args()


def main() -> None:
    args = _parse_args()

    if not args.dataset.exists():
        logger.error("Dataset file not found: %s", args.dataset)
        sys.exit(1)

    runner = CalibrationRunner(
        api_url=args.api_url,
        top_k=args.top_k,
        delay_s=args.delay,
        threshold=args.threshold,
        output_dir=args.output_dir,
    )

    metrics = runner.run(
        dataset_path=args.dataset,
        max_questions=args.max_questions,
    )

    # Exit with non-zero code if calibration targets are not met
    sys.exit(0 if metrics.passes_all() else 1)


if __name__ == "__main__":
    main()
