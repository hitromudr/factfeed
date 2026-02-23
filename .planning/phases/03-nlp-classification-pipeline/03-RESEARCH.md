# Phase 3: NLP Classification Pipeline - Research

**Researched:** 2026-02-23
**Domain:** Hybrid NLP classification (rule-based heuristics + zero-shot transformer inference) for sentence-level fact/opinion labeling
**Confidence:** MEDIUM-HIGH (core transformer API HIGH; calibration approach HIGH via sklearn 1.8 docs; attribution pattern detection MEDIUM; accuracy ceiling on news domain LOW — no domain-specific benchmark exists)

---

## Summary

Phase 3 builds a two-layer classification pipeline on top of the completed ingestion system. The first layer is a rule-based pre-filter implemented with spaCy that handles deterministic cases without invoking the transformer: attributed speech sentences ("The CEO said X") are classified as `mixed`; sentences under 30 tokens, satire-marker sentences, and breaking-news stubs are classified as `unclear`. The second layer is a zero-shot NLI transformer (DeBERTa-v3-base-zeroshot-v2.0) that classifies the remaining sentences as `fact` or `opinion` using carefully chosen hypothesis templates. Confidence scores from the transformer are post-hoc calibrated using temperature scaling.

The 80% accuracy target is achievable on well-formed news prose via zero-shot alone on straightforward sentences, but hard cases (hedging, implied opinion, nuanced attribution) will likely fall below that threshold without a labeled evaluation set and a fine-tuning pass. The project decisions log already identifies this as a blocker: the evaluation set must be built before writing classifier code. This research recommends building a 120+ sentence labeled evaluation set in Wave 0 of the plan, alongside the dependency install, so accuracy can be measured continuously during implementation.

The `Sentence` child table and CASCADE FK already exist from Phase 1 (confirmed in `factfeed/db/models.py`). The classifier writes to it using SQLAlchemy 2.0-style `insert()` with `async_session.execute()` — the legacy `bulk_save_objects` path does not exist on `AsyncSession`.

**Primary recommendation:** Implement in this order: (1) install NLP deps + evaluation dataset, (2) spaCy pre-filter (attribution + unclear gates), (3) transformer classifier with hypothesis templates, (4) temperature-scaled confidence calibration, (5) async DB persistence layer, (6) accuracy gate test.

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| NLP-01 | System classifies each sentence as fact, opinion, mixed, or unclear using hybrid NLP (rule-based heuristics + zero-shot transformer) | DeBERTa-v3-base-zeroshot-v2.0 pipeline API confirmed; spaCy rule-based pre-filter patterns documented; two-layer architecture defined |
| NLP-02 | System assigns confidence score (0.0–1.0) to each classified sentence | Transformer pipeline returns `scores` list aligned to `labels`; temperature scaling via `sklearn.calibration.CalibratedClassifierCV` (method='temperature') available in sklearn 1.8 |
| NLP-03 | System flags ambiguous content (quotes, satire, breaking news without context) as "unclear" with low confidence | spaCy token count gate (`len(sent) < 30`) and PhraseMatcher for satire/breaking-news markers; these short-circuit the transformer |
| NLP-04 | System detects attributed speech patterns ("The CEO said X") and routes them through an attribution pre-filter before transformer classification | spaCy DependencyMatcher patterns for nsubj→verb(said/told/claimed/stated) + ccomp/dobj; PhraseMatcher for "according to", "the X said"; routes to `mixed` label |
| NLP-05 | System stores classification results as structured data (sentences child table, not JSON blob) for per-sentence querying | `Sentence` model confirmed in `factfeed/db/models.py`; SQLAlchemy 2.0 async `insert()` bulk pattern documented |
</phase_requirements>

---

## Standard Stack

### Core NLP Libraries

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| spaCy | 3.8.11 | Sentence segmentation, dependency parsing, token-level matching | Fastest production-ready NLP library for rule-based pre-filtering; `en_core_web_sm` provides sentence boundaries, POS, dep parse, NER |
| transformers | 5.2.0 | Zero-shot classification pipeline | Current HuggingFace release (Feb 2026); `pipeline("zero-shot-classification")` is the standard access layer for NLI models |
| torch (CPU) | 2.10.0 | Inference backend | CPU-only install (`--index-url .../cpu`) keeps image size manageable; DeBERTa-v3-base needs ~420 MB RAM at inference; GPU not required at 100 articles/day |
| scikit-learn | 1.8+ | Temperature scaling calibration | sklearn 1.8 added `method='temperature'` to `CalibratedClassifierCV`; one-parameter post-hoc calibration with no accuracy penalty |

### Model

| Model | Source | Parameters | RAM | License |
|-------|--------|-----------|-----|---------|
| MoritzLaurer/deberta-v3-base-zeroshot-v2.0 | HuggingFace Hub | 200M | ~420 MB | MIT |

F1-macro 0.619 across 28 classification tasks vs facebook/bart-large-mnli 0.497 — ~25% improvement confirmed in official model card benchmarks.

### Supporting Libraries (Already Installed)

| Library | Version | Status |
|---------|---------|--------|
| SQLAlchemy | 2.0.46 | Already in `pyproject.toml` — async `insert()` used for persistence |
| asyncpg | 0.31.0 | Already in `pyproject.toml` |
| pytest | 9.0.2 | Already in `pyproject.toml` dev group |
| pytest-asyncio | 1.3.0 | Already in `pyproject.toml` dev group |

### New Dependencies to Add

```bash
# Install NLP stack (add to pyproject.toml dependencies)
pip install spacy==3.8.11
pip install torch --index-url https://download.pytorch.org/whl/cpu  # CPU-only
pip install transformers==5.2.0
pip install scikit-learn>=1.8.0

# Download spaCy English model (en_core_web_sm for speed; en_core_web_md for better NER)
python -m spacy download en_core_web_sm

# Model auto-downloads from HuggingFace Hub on first pipeline() call:
# pipeline("zero-shot-classification", model="MoritzLaurer/deberta-v3-base-zeroshot-v2.0")
# Cached to ~/.cache/huggingface — no explicit download command needed
```

**pyproject.toml additions:**
```toml
"spacy>=3.8.11",
"torch>=2.10.0",          # CPU-only via separate pip install
"transformers>=5.2.0",
"scikit-learn>=1.8.0",
```

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| DeBERTa-v3-base-zeroshot-v2.0 | DeBERTa-v3-large-zeroshot-v2.0 | Large scores 0.676 vs 0.619 f1_macro but requires ~800 MB RAM and ~2x inference time; not justified at 100 articles/day |
| DeBERTa-v3-base-zeroshot-v2.0 | facebook/bart-large-mnli | BART scores 0.497 vs 0.619 — ~25% lower accuracy; avoid |
| sklearn temperature scaling | Custom sigmoid calibration | sklearn 1.8 `method='temperature'` is a proper one-parameter post-hoc calibrator; no need for custom implementation |
| spaCy DependencyMatcher | Regex-only attribution detection | Regex misses pronominal references and ellipsis; dependency parse is more robust for "he said", "she stated", "the ministry claims" |

---

## Architecture Patterns

### Recommended Project Structure

```
factfeed/
├── nlp/
│   ├── __init__.py              # (exists — empty stub)
│   ├── segmenter.py             # spaCy doc creation + sentence boundary detection
│   ├── pre_filter.py            # Attribution detection + unclear gate (rules-only, no transformer)
│   ├── classifier.py            # DeBERTa zero-shot pipeline wrapper
│   ├── calibrator.py            # Temperature scaling wrapper
│   └── pipeline.py              # Orchestrator: calls segmenter → pre_filter → classifier → calibrator
│
tests/
├── nlp/
│   ├── __init__.py
│   ├── test_segmenter.py        # Sentence boundary tests
│   ├── test_pre_filter.py       # Attribution + unclear gate unit tests (no model needed)
│   ├── test_classifier.py       # Transformer classifier tests (mocked pipeline in unit tests)
│   ├── test_pipeline.py         # Integration: full pipeline on evaluation dataset
│   └── eval_dataset.py          # 120+ labeled sentences for accuracy measurement
│
factfeed/
├── nlp/
│   └── persist.py               # async DB write: delete old sentences + bulk insert new
```

### Pattern 1: Two-Layer Hybrid Classification

**What:** Pre-filter deterministic cases before the transformer runs; avoid paying inference cost for sentences whose classification is certain.

**When to use:** Always. The pre-filter adds spaCy overhead (~5-20ms/sentence) but saves ~200ms/sentence transformer inference for attributed speech and short sentences.

```python
# Source: architecture from STACK.md + HuggingFace pipeline docs
from dataclasses import dataclass
from typing import Literal

Label = Literal["fact", "opinion", "mixed", "unclear"]

@dataclass
class SentenceResult:
    text: str
    position: int
    label: Label
    confidence: float  # 0.0–1.0, calibrated

def classify_article(body: str) -> list[SentenceResult]:
    doc = segmenter.parse(body)
    results = []
    for position, sent in enumerate(doc.sents):
        pre_result = pre_filter.classify(sent)
        if pre_result is not None:
            results.append(SentenceResult(sent.text, position, pre_result.label, pre_result.confidence))
        else:
            raw = classifier.classify(sent.text)
            calibrated = calibrator.calibrate(raw)
            results.append(SentenceResult(sent.text, position, calibrated.label, calibrated.confidence))
    return results
```

### Pattern 2: spaCy Attribution Pre-Filter

**What:** Use spaCy's DependencyMatcher plus PhraseMatcher to detect sentences where the main clause is attributed speech ("Minister said X", "According to the WHO").

**When to use:** Before transformer inference. Attribution sentences are inherently mixed (reported speech can be fact or opinion but is not classifiable without deep knowledge), so route to `mixed` directly.

```python
# Source: spaCy DependencyMatcher docs (spacy.io/api/dependencymatcher)
import spacy
from spacy.matcher import DependencyMatcher, PhraseMatcher

nlp = spacy.load("en_core_web_sm")

# DependencyMatcher: verb(said/told/claimed) with nsubj
dep_matcher = DependencyMatcher(nlp.vocab)
attribution_verbs = ["say", "tell", "claim", "state", "announce", "report",
                     "allege", "argue", "warn", "explain", "note", "add",
                     "confirm", "deny", "insist", "suggest", "indicate"]

pattern = [
    {"RIGHT_ID": "anchor_verb", "RIGHT_ATTRS": {"LEMMA": {"IN": attribution_verbs}, "POS": "VERB"}},
    {"LEFT_ID": "anchor_verb", "REL_OP": ">", "RIGHT_ID": "subject", "RIGHT_ATTRS": {"DEP": "nsubj"}},
]
dep_matcher.add("ATTRIBUTION", [pattern])

# PhraseMatcher: "according to", "sources say", "told reporters"
phrase_matcher = PhraseMatcher(nlp.vocab, attr="LOWER")
phrase_matcher.add("ATTR_PHRASE", [
    nlp.make_doc("according to"),
    nlp.make_doc("told reporters"),
    nlp.make_doc("sources said"),
    nlp.make_doc("officials said"),
])

def is_attribution(sent_span) -> bool:
    """Returns True if sentence is attributed speech."""
    doc = sent_span.as_doc()
    dep_matches = dep_matcher(doc)
    phrase_matches = phrase_matcher(doc)
    return bool(dep_matches or phrase_matches)
```

### Pattern 3: Unclear Gate (Token Count + Satire Markers)

**What:** Short sentences, satire markers, and "BREAKING:" news stubs lack sufficient context for reliable classification. Gate them to `unclear` with confidence 0.1.

**When to use:** After attribution check, before transformer inference.

```python
# Source: phase success criteria + FEATURES.md ambiguous content flagging
SATIRE_MARKERS = {
    "the onion", "babylon bee", "reductress", "the daily mash",
    "the beaverton", "world news daily report", "satire", "[satire]",
}
BREAKING_PATTERNS = ["breaking:", "breaking news:", "developing story"]

def is_unclear(sent_span, article_source_name: str = "") -> bool:
    token_count = len(sent_span)
    if token_count < 30:
        return True
    text_lower = sent_span.text.lower()
    if any(marker in text_lower for marker in SATIRE_MARKERS):
        return True
    if any(p in text_lower for p in BREAKING_PATTERNS):
        return True
    if article_source_name.lower() in SATIRE_MARKERS:
        return True
    return False
```

### Pattern 4: DeBERTa Zero-Shot Hypothesis Templates

**What:** The NLI pipeline requires candidate labels formatted as hypothesis templates. Template wording significantly affects classification accuracy — the model matches semantic similarity of the hypothesis to the sentence.

**When to use:** After pre-filter passes a sentence through (not attribution, not unclear).

```python
# Source: HuggingFace model card for MoritzLaurer/deberta-v3-base-zeroshot-v2.0
from transformers import pipeline

_classifier = pipeline(
    "zero-shot-classification",
    model="MoritzLaurer/deberta-v3-base-zeroshot-v2.0",
    device=-1,   # CPU; use device=0 for first CUDA GPU if available
)

CANDIDATE_LABELS = ["factual statement", "opinion or commentary"]
HYPOTHESIS_TEMPLATE = "This sentence is a {}."

def classify_sentence(text: str) -> dict:
    result = _classifier(
        text,
        CANDIDATE_LABELS,
        hypothesis_template=HYPOTHESIS_TEMPLATE,
        multi_label=False,
    )
    # result: {"labels": ["factual statement", "opinion or commentary"],
    #          "scores": [0.82, 0.18], "sequence": text}
    label_map = {
        "factual statement": "fact",
        "opinion or commentary": "opinion",
    }
    top_label = result["labels"][0]
    top_score = result["scores"][0]
    return {"label": label_map[top_label], "raw_confidence": top_score}
```

**Template selection rationale:** "factual statement" and "opinion or commentary" are more semantically precise than bare "fact"/"opinion". The model uses NLI entailment — "This sentence is a factual statement" entails much more specifically than "This sentence is a fact."

### Pattern 5: Async Inference (Thread Pool Executor)

**What:** The transformer pipeline is CPU-bound and synchronous. Run it in a thread pool to avoid blocking the FastAPI async event loop.

**When to use:** Whenever calling the classifier from within an async context (APScheduler job, FastAPI route).

```python
# Source: FastAPI async + run_in_executor pattern (Python asyncio docs)
import asyncio
from concurrent.futures import ThreadPoolExecutor

_executor = ThreadPoolExecutor(max_workers=1)  # Single worker: one inference at a time

async def classify_sentence_async(text: str) -> dict:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(_executor, classify_sentence, text)
```

**Important:** Use `max_workers=1`. DeBERTa-v3-base uses ~420 MB RAM per instance. Parallel workers multiply RAM usage. At 100 articles/day, throughput is not a constraint.

Alternatively, Python 3.9+ `asyncio.to_thread()` is cleaner:
```python
result = await asyncio.to_thread(classify_sentence, text)
```

### Pattern 6: Temperature Scaling Calibration

**What:** The transformer's softmax outputs are overconfident on in-distribution data and often poorly calibrated on new domains. Temperature scaling divides logits by a learned scalar T (T > 1 reduces confidence; T < 1 increases it).

**When to use:** After building the labeled evaluation set (100+ sentences). Fit the temperature on a held-out calibration split of the evaluation set, then apply it to all production scores.

```python
# Source: sklearn 1.8 docs (scikit-learn.org/stable/modules/calibration.html)
# Note: sklearn 1.8 is required — earlier versions do not have method='temperature'
from sklearn.calibration import CalibratedClassifierCV

# For NLI-produced probabilities, temperature scaling is applied directly to raw scores:
# Simplified manual approach (no sklearn wrapper needed for post-hoc)
import numpy as np

class TemperatureScaler:
    """Simple post-hoc temperature scaling for binary classification scores."""

    def __init__(self, temperature: float = 1.0):
        self.temperature = temperature

    def calibrate(self, raw_score: float) -> float:
        """Apply temperature scaling to a single probability."""
        # For binary: apply softmax([logit/T, (1-logit)/T])
        # Approximation for already-softmaxed scores:
        logit = np.log(raw_score / (1 - raw_score + 1e-8))
        scaled_logit = logit / self.temperature
        return float(1 / (1 + np.exp(-scaled_logit)))

    def fit_temperature(self, raw_scores: list[float], true_labels: list[int]) -> float:
        """Find temperature T that minimizes NLL on calibration set."""
        from scipy.optimize import minimize_scalar
        from sklearn.metrics import log_loss

        def nll(T):
            calibrated = [self.calibrate_with_T(s, T) for s in raw_scores]
            probs = [[1 - p, p] for p in calibrated]
            return log_loss(true_labels, probs)

        result = minimize_scalar(nll, bounds=(0.1, 10.0), method='bounded')
        self.temperature = result.x
        return self.temperature
```

**Blocker flagged in STATE.md:** Temperature scaling requires a labeled calibration set that does not yet exist. Build the 120+ sentence evaluation set in Wave 0 before fitting the temperature.

**If calibration set is not ready at Phase 3 time:** Default `temperature=1.0` (no scaling) is acceptable for launch. Calibration can be added in Phase 5 polish.

### Pattern 7: Async Bulk Persistence to Sentences Table

**What:** After classifying all sentences in an article, delete any existing sentence rows for that article, then bulk-insert the new classification results.

**When to use:** After the pipeline returns `list[SentenceResult]` for an article.

```python
# Source: SQLAlchemy 2.0 async docs (docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html)
from sqlalchemy import delete, insert
from factfeed.db.models import Sentence

async def persist_sentences(
    article_id: int,
    results: list[SentenceResult],
    session: AsyncSession,
) -> None:
    # Delete existing classifications (idempotent re-classification support)
    await session.execute(
        delete(Sentence).where(Sentence.article_id == article_id)
    )
    if not results:
        return
    # Bulk insert using SQLAlchemy 2.0 insert() — legacy bulk_save_objects
    # is NOT available on AsyncSession
    await session.execute(
        insert(Sentence),
        [
            {
                "article_id": article_id,
                "position": r.position,
                "text": r.text,
                "label": r.label,
                "confidence": r.confidence,
            }
            for r in results
        ],
    )
    await session.commit()
```

**Note:** CASCADE DELETE is already configured on the FK (`ondelete="CASCADE"` in `factfeed/db/models.py`), so deleting the parent Article cascades. The explicit `delete()` above handles the re-classification case where the article stays and only its sentences are refreshed.

### Anti-Patterns to Avoid

- **Running transformer inference inside `async def` without a thread pool:** Blocks the event loop for ~200ms/sentence. Always use `run_in_executor` or `asyncio.to_thread()`.
- **Using multi_label=True for fact/opinion classification:** This treats the labels as independent. `multi_label=False` forces the model to pick one label, which matches the 4-class schema (fact, opinion, mixed, unclear).
- **Using bare "fact" and "opinion" as candidate labels:** Too short and ambiguous for the NLI model. Use "factual statement" and "opinion or commentary" for better semantic matching.
- **Using `session.bulk_save_objects()` in async code:** Not available on `AsyncSession`. Use `session.execute(insert(Model), list_of_dicts)` instead.
- **Loading the transformer model inside a per-sentence function:** Model loading takes 3-10 seconds. Load once at module level or at app startup; reuse the pipeline object.
- **Using VADER for classification:** VADER is a sentiment classifier (positive/negative). Sentiment ≠ opinion. This is documented explicitly in STACK.md "What NOT to Use".
- **Calling `pre_filter` on the raw article body string:** spaCy's `doc.sents` requires a processed `Doc` object. Parse the body once and iterate over the resulting spans — do not re-parse per sentence.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Sentence boundary detection | Custom regex sentence splitter | spaCy `doc.sents` with `en_core_web_sm` | Regex fails on abbreviations ("U.S.", "Dr.", "No.", "Jan."), URLs, ellipsis, quotation boundaries |
| Zero-shot NLI classification | Custom fine-tuned classifier or keyword list | DeBERTa-v3-base-zeroshot-v2.0 via `pipeline("zero-shot-classification")` | Building and training a custom classifier requires thousands of labeled examples and weeks of iteration |
| Confidence calibration | Ad-hoc score normalization | Temperature scaling via scipy `minimize_scalar` or sklearn 1.8 `CalibratedClassifierCV(method='temperature')` | Calibration theory is subtle; temperature scaling is the established method with known properties |
| Attribution detection | Hand-written regex for "X said Y" | spaCy DependencyMatcher with `nsubj` + attribution verb lemmas | Regex cannot handle pronoun references, passive voice ("it was announced by"), or complex clauses |
| Async inference | `asyncio.run_coroutine_threadsafe` or custom queue | `asyncio.to_thread()` or `loop.run_in_executor()` | Standard library solution; correct thread-safety guarantees; no custom infrastructure |
| Bulk sentence insert | `session.add()` in a loop | `session.execute(insert(Sentence), list_of_dicts)` | Per-row `add()` in a loop issues N round trips to the DB; bulk insert issues one |

**Key insight:** The NLP domain has deep "deceptively simple" traps (sentence boundaries, attribution, calibration). Every component in this list has been hard-won by the open-source community and is available as a well-tested library function.

---

## Common Pitfalls

### Pitfall 1: Model Loading in Tests Causes Slow Tests and CI Failures
**What goes wrong:** Tests that import `classifier.py` trigger the DeBERTa model download and load (3-10 seconds, 420 MB). CI environments without internet access will fail. Test suites become slow.
**Why it happens:** `pipeline("zero-shot-classification", model=...)` downloads on first call if not cached. If imported at module level, it runs on test collection.
**How to avoid:** Inject the pipeline as a dependency (pass it as an argument to the classifier function). In tests, mock it:
```python
# conftest.py
@pytest.fixture
def mock_classifier():
    def fake_pipeline(text, labels, **kwargs):
        return {"labels": labels, "scores": [0.8, 0.2], "sequence": text}
    return fake_pipeline
```
**Warning signs:** Tests take >30 seconds; CI fails with network errors or disk space errors.

### Pitfall 2: Token Count Threshold of 30 Is on spaCy Tokens, Not Words
**What goes wrong:** Using `len(sent.text.split())` counts whitespace-delimited words, not spaCy tokens. spaCy tokenizes punctuation separately, so "He said so." is 4 tokens (He, said, so, .). A 25-word sentence is ~28-32 spaCy tokens.
**Why it happens:** Confusion between word count and token count is common.
**How to avoid:** Always use `len(sent)` where `sent` is a spaCy `Span` object. This counts spaCy tokens, which is what the success criterion specifies.
**Warning signs:** Short sentences that should be `unclear` are being passed to the transformer.

### Pitfall 3: Transformer Pipeline Object Is Not Thread-Safe by Default
**What goes wrong:** Using a single shared pipeline object from multiple async coroutines that all call `run_in_executor` simultaneously can cause race conditions if `batch_size > 1`.
**Why it happens:** torch tensors are not GIL-free; concurrent access to the same model forward pass is unsafe.
**How to avoid:** Use `ThreadPoolExecutor(max_workers=1)` to serialize inference calls. At 100 articles/day, the throughput is sufficient. The pipeline object is safe when accessed from a single thread at a time.
**Warning signs:** Intermittent SIGSEGV or incorrect classifications when testing concurrent article classification.

### Pitfall 4: Zero-Shot Confidence Scores Are Poorly Calibrated Out of the Box
**What goes wrong:** The DeBERTa model reports 0.92 confidence on a sentence that human labelers rate as genuinely ambiguous. Users see "92% confident: fact" and trust it incorrectly.
**Why it happens:** NLI models are trained to maximize classification accuracy, not calibration. Softmax outputs are systematically overconfident.
**How to avoid:** Build a labeled calibration set alongside (or before) the evaluation set. Fit temperature scaling. Even without a calibration set, clamp displayed confidence to a sensible range (0.1-0.9) as a temporary measure.
**Warning signs:** All sentences have confidence > 0.85; the score distribution is bimodal (most sentences are either very high or very low confidence).

### Pitfall 5: Re-Classifying Articles Doubles Sentence Rows
**What goes wrong:** Running the classifier on an article that already has rows in the `sentences` table inserts duplicate rows, since `Sentence` has no unique constraint on `(article_id, position)`.
**Why it happens:** The current `Sentence` model has no upsert constraint (confirmed in `factfeed/db/models.py`).
**How to avoid:** Always `DELETE FROM sentences WHERE article_id = ?` before bulk inserting. The `delete()` + `insert()` pattern in the persistence function handles this explicitly.
**Warning signs:** Article viewer shows duplicate highlighted sentences; `sentences` table row count grows on every scheduler run.

### Pitfall 6: spaCy Model Not Downloaded in Docker Container
**What goes wrong:** `spacy.load("en_core_web_sm")` raises `OSError: [E050] Can't find model 'en_core_web_sm'` in Docker.
**Why it happens:** spaCy language models are not installed via `pip install spacy`. They must be downloaded separately with `python -m spacy download en_core_web_sm`.
**How to avoid:** Add to the Dockerfile:
```dockerfile
RUN python -m spacy download en_core_web_sm
```
**Warning signs:** App starts successfully locally (where you ran the download) but crashes in Docker.

### Pitfall 7: Hypothesis Template Phrasing Significantly Affects Accuracy
**What goes wrong:** Using bare labels `["fact", "opinion"]` with default template `"This example is {}"` produces lower accuracy than semantically richer labels.
**Why it happens:** The NLI model entailment check is sensitive to the exact wording of the hypothesis. "This example is fact" is grammatically odd and semantically weak.
**How to avoid:** Use `["factual statement", "opinion or commentary"]` with `hypothesis_template="This sentence is a {}."`. Validate on the evaluation set before committing to a template.
**Warning signs:** Accuracy on the evaluation set is below 70% — check template wording first before assuming the model is insufficient.

---

## Code Examples

Verified patterns from official sources:

### Zero-Shot Pipeline Initialization (Load Once)
```python
# Source: HuggingFace model card - MoritzLaurer/deberta-v3-base-zeroshot-v2.0
# https://huggingface.co/MoritzLaurer/deberta-v3-base-zeroshot-v2.0
from transformers import pipeline

# Load at module level (once per process, ~3-10 seconds startup)
_zs_pipeline = pipeline(
    "zero-shot-classification",
    model="MoritzLaurer/deberta-v3-base-zeroshot-v2.0",
    device=-1,  # -1 = CPU
)

CANDIDATE_LABELS = ["factual statement", "opinion or commentary"]
HYPOTHESIS_TEMPLATE = "This sentence is a {}."

def classify(text: str) -> dict:
    return _zs_pipeline(
        text,
        CANDIDATE_LABELS,
        hypothesis_template=HYPOTHESIS_TEMPLATE,
        multi_label=False,
    )
# Returns: {"labels": ["factual statement", ...], "scores": [0.82, ...], "sequence": text}
```

### spaCy Sentence Segmentation
```python
# Source: spaCy usage docs - https://spacy.io/usage/linguistic-features
import spacy

nlp = spacy.load("en_core_web_sm")

def segment_article(body: str) -> list:
    """Returns list of spaCy Span objects (one per sentence)."""
    doc = nlp(body)
    return list(doc.sents)

# Token count on a Span:
for sent in doc.sents:
    token_count = len(sent)  # NOT len(sent.text.split())
```

### SQLAlchemy 2.0 Async Bulk Insert
```python
# Source: SQLAlchemy 2.0 async docs
# https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html
from sqlalchemy import delete, insert
from sqlalchemy.ext.asyncio import AsyncSession
from factfeed.db.models import Sentence

async def save_sentences(
    article_id: int,
    results: list[dict],
    session: AsyncSession,
) -> None:
    await session.execute(
        delete(Sentence).where(Sentence.article_id == article_id)
    )
    if results:
        await session.execute(
            insert(Sentence),
            [{"article_id": article_id, **r} for r in results],
        )
    await session.commit()
```

### Async Inference Pattern
```python
# Source: Python asyncio docs + FastAPI async patterns
import asyncio

async def classify_async(text: str) -> dict:
    """Run synchronous transformer inference without blocking event loop."""
    return await asyncio.to_thread(classify, text)
    # Python 3.9+; equivalent to loop.run_in_executor(None, classify, text)
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| BART-large-mnli as default zero-shot model | DeBERTa-v3-base-zeroshot-v2.0 | 2023 (Laurer et al.) | ~25% F1 improvement; MIT license vs CC-BY-NC |
| `transformers` v4.x | `transformers` v5.2.0 | Feb 2026 | Unified tokenizer backends; current release to install |
| sklearn isotonic/sigmoid calibration | Temperature scaling (`method='temperature'`) | sklearn 1.8 (2025) | One-parameter calibration; better for multi-class; proper softmax scaling |
| `session.bulk_save_objects()` | `session.execute(insert(Model), list_of_dicts)` | SQLAlchemy 2.0 | `bulk_save_objects` not available on `AsyncSession` |
| spaCy 2.x `Matcher` only | spaCy 3.x `DependencyMatcher` | 2021+ | Structural/dependency-aware matching for attribution detection |
| `asyncio.get_event_loop().run_in_executor()` | `asyncio.to_thread()` | Python 3.9 | Cleaner API; no need to get the event loop explicitly |

**Deprecated/outdated:**
- `transformers` v4.x: Do not install; current stable is v5.2.0 (Feb 2026)
- `APScheduler` 4.x alpha: Not applicable to this phase, but confirmed in STACK.md
- `sklearn.calibration.CalibratedClassifierCV(method='temperature')` requires sklearn ≥ 1.8; earlier sklearn does not have the temperature method

---

## Open Questions

1. **What hypothesis template produces the highest accuracy on news domain sentences?**
   - What we know: Template wording significantly affects NLI-based zero-shot accuracy; "factual statement" vs "fact" is known to differ; no domain-specific benchmark exists for news fact/opinion
   - What's unclear: Whether a 4-label formulation ("factual statement", "subjective opinion", "reported speech", "ambiguous") outperforms 2-label with a pre-filter; needs evaluation set to answer
   - Recommendation: Start with 2-label ("factual statement", "opinion or commentary") with pre-filter handling `mixed` and `unclear`. Measure accuracy. If below 80%, try alternative template phrasings before attempting fine-tuning.

2. **Will zero-shot alone reach 80% accuracy on hard cases?**
   - What we know: DeBERTa-v3-base achieves 0.619 f1_macro across 28 general tasks; news fact/opinion is not among the 28 tasks in the benchmark; accuracy on easy news sentences likely higher, hard cases likely lower
   - What's unclear: Without the evaluation set, the gap is unknown
   - Recommendation: Build a 120+ sentence evaluation set in Wave 0, including 30+ hard cases (hedging, implied opinion, irony, statistics with embedded judgment). Measure accuracy before Phase 5 hardening. If below 80%, the fix is likely label-smoothed fine-tuning with 500-1000 labeled news sentences, not a model replacement.

3. **Should the classification pipeline run inline with ingestion or as a separate post-ingestion step?**
   - What we know: Phase 2 ingestion is complete; it runs on APScheduler; articles are persisted with `body` text
   - What's unclear: Whether adding ~200ms/sentence classification inline will cause timeout issues in the ingestion scheduler; DeBERTa-v3-base at 200ms/sentence × 20 sentences/article × 100 articles = ~400 seconds per run
   - Recommendation: Run classification as a separate post-ingestion pass (query articles where `sentences` count = 0, classify in batches). This decouples ingestion failure from classification failure and allows the classification backlog to be processed independently.

4. **Does the Sentence model need a unique constraint on (article_id, position)?**
   - What we know: Current model has no such constraint; pitfall 5 documents the double-insert risk
   - What's unclear: Whether Phase 4 (web interface) requires guaranteed uniqueness at DB level
   - Recommendation: Add `UniqueConstraint("article_id", "position")` in a Phase 3 migration. This is cheap now and prevents data integrity bugs that are expensive to debug later. Requires a new Alembic migration (0003_sentence_position_unique.py).

---

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.0.2 + pytest-asyncio 1.3.0 |
| Config file | `pyproject.toml` — `asyncio_mode = "auto"` already set |
| Quick run command | `pytest tests/nlp/ -x -q` |
| Full suite command | `pytest tests/ -x -q` |
| Estimated runtime | ~10-30s for unit tests (mocked pipeline); ~60-120s if integration tests load the real model |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| NLP-01 | Pipeline on article body produces list of SentenceResults with label in {fact,opinion,mixed,unclear} | unit | `pytest tests/nlp/test_pipeline.py -x` | No — Wave 0 gap |
| NLP-01 | Attribution sentences get label=mixed from pre-filter (not transformer) | unit | `pytest tests/nlp/test_pre_filter.py::test_attribution_classified_as_mixed -x` | No — Wave 0 gap |
| NLP-01 | Transformer classifier maps "factual statement" hypothesis match to "fact" label | unit | `pytest tests/nlp/test_classifier.py -x` | No — Wave 0 gap |
| NLP-02 | Confidence score is float between 0.0 and 1.0 on every result | unit | `pytest tests/nlp/test_pipeline.py::test_confidence_bounds -x` | No — Wave 0 gap |
| NLP-03 | Sentences under 30 tokens receive label=unclear | unit | `pytest tests/nlp/test_pre_filter.py::test_short_sentence_unclear -x` | No — Wave 0 gap |
| NLP-03 | Satire-marker sentences receive label=unclear | unit | `pytest tests/nlp/test_pre_filter.py::test_satire_marker_unclear -x` | No — Wave 0 gap |
| NLP-04 | "The CEO said X" routed to mixed before transformer | unit | `pytest tests/nlp/test_pre_filter.py::test_attribution_verb_detection -x` | No — Wave 0 gap |
| NLP-04 | "According to the minister" routed to mixed via PhraseMatcher | unit | `pytest tests/nlp/test_pre_filter.py::test_according_to_detection -x` | No — Wave 0 gap |
| NLP-05 | `persist_sentences()` writes rows to sentences table with correct columns | integration | `pytest tests/nlp/test_pipeline.py::test_persist_sentences -x` | No — Wave 0 gap |
| NLP-05 | Re-running classifier on same article replaces sentences (no duplicates) | integration | `pytest tests/nlp/test_pipeline.py::test_idempotent_classification -x` | No — Wave 0 gap |
| INFRA-05 | Accuracy on evaluation set >= 80% (100+ labeled sentences, hard cases included) | integration | `pytest tests/nlp/test_pipeline.py::test_evaluation_set_accuracy -x` | No — Wave 0 gap |

### Nyquist Sampling Rate
- **Minimum sample interval:** After every committed task → run: `pytest tests/nlp/ -x -q`
- **Full suite trigger:** Before merging final task of any plan wave
- **Phase-complete gate:** Full suite green before `/gsd:verify-work` runs
- **Estimated feedback latency per task:** ~10-30 seconds (unit tests with mocked pipeline)

### Wave 0 Gaps (must be created before implementation)
- [ ] `tests/nlp/__init__.py` — package init for NLP tests
- [ ] `tests/nlp/test_segmenter.py` — covers sentence boundary detection (NLP-01)
- [ ] `tests/nlp/test_pre_filter.py` — covers attribution detection + unclear gate (NLP-03, NLP-04)
- [ ] `tests/nlp/test_classifier.py` — covers zero-shot classification with mocked pipeline (NLP-01, NLP-02)
- [ ] `tests/nlp/test_pipeline.py` — covers full pipeline integration + DB persistence + accuracy gate (NLP-01 through NLP-05, INFRA-05)
- [ ] `tests/nlp/eval_dataset.py` — 120+ labeled sentences (factual/opinion/mixed/unclear) covering hard cases; used by accuracy gate test
- [ ] `alembic/versions/0003_sentence_position_unique.py` — adds `UniqueConstraint("article_id", "position")` to sentences table

---

## Sources

### Primary (HIGH confidence)
- HuggingFace model card: https://huggingface.co/MoritzLaurer/deberta-v3-base-zeroshot-v2.0 — model description, hypothesis template API, f1_macro 0.619 benchmark, 200M params, MIT license
- HuggingFace transformers pipeline docs: https://huggingface.co/docs/transformers/main_classes/pipelines — device parameter, batch_size, ChunkPipeline architecture for zero-shot classification
- spaCy linguistic features docs: https://spacy.io/usage/linguistic-features — `doc.sents`, `len(sent)` token count, dependency parse usage
- spaCy DependencyMatcher API: https://spacy.io/api/dependencymatcher — pattern syntax, `RIGHT_ID`/`LEFT_ID`/`REL_OP`/`RIGHT_ATTRS` structure
- SQLAlchemy 2.0 async docs: https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html — `AsyncSession`, `insert()`, bulk insert patterns
- scikit-learn calibration docs: https://scikit-learn.org/stable/modules/calibration.html — temperature scaling, `CalibratedClassifierCV(method='temperature')`, sklearn 1.8 requirement
- `factfeed/db/models.py` — confirms `Sentence` model with `article_id`, `position`, `text`, `label`, `confidence` columns; CASCADE FK
- `pyproject.toml` — confirms transformers, spaCy, torch NOT yet in dependencies; scikit-learn not listed

### Secondary (MEDIUM confidence)
- HuggingFace transformers v5.2.0 current release: confirmed in STACK.md (sourced from PyPI Feb 2026)
- spaCy 3.8.11 current release: confirmed in STACK.md (sourced from PyPI Nov 2025)
- torch 2.10.0 current release: confirmed in STACK.md (sourced from PyPI Jan 2026)
- WebSearch: async transformers inference with `run_in_executor` / `asyncio.to_thread()` pattern — multiple production examples confirmed; markaicode.com/transformers-async-processing-non-blocking-inference/
- WebSearch: temperature scaling in sklearn 1.8 — confirmed via scikit-learn GitHub issue #28574 and official docs

### Tertiary (LOW confidence)
- 80% accuracy target on news fact/opinion for zero-shot DeBERTa: no domain-specific benchmark exists; target is from project requirements (INFRA-05); actual zero-shot accuracy on news sentences is unknown until evaluation set is built
- Hypothesis template wording effect on accuracy ("factual statement" vs "fact"): common knowledge in NLI community; no controlled experiment found for this specific domain
- Satire marker detection via keyword list: practical heuristic; no authoritative dataset of satire source names for news articles

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all library versions verified via PyPI and STACK.md (Feb 2026); DeBERTa model card benchmarks confirmed
- Architecture: HIGH — two-layer pattern (pre-filter + transformer) is the industry-standard approach for constrained-label NLP; all API patterns verified against official docs
- Pitfalls: HIGH — thread safety, Docker model download, bulk insert, token count confusion all verified from official sources; hypothesis template wording is MEDIUM (community consensus, not formally benchmarked)
- Accuracy target: LOW — 80% accuracy target is a project requirement; whether zero-shot alone reaches it on real news sentences is unknown until the evaluation set is built

**Research date:** 2026-02-23
**Valid until:** 2026-03-23 (stable libraries; transformers releases frequently but v5.x API is stable)
