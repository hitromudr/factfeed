# Pitfalls Research

**Domain:** News aggregator + NLP fact/opinion classifier (FactFeed)
**Researched:** 2026-02-23
**Confidence:** MEDIUM — findings verified across multiple WebSearch sources; no Context7 for domain-level pitfalls; critical technical pitfalls verified against official docs where possible

---

## Critical Pitfalls

### Pitfall 1: Zero-Shot Model Overconfidence on Short/Ambiguous Text

**What goes wrong:**
NLI-based zero-shot classifiers (BART, DeBERTa) return high softmax confidence scores that are systematically miscalibrated — the raw probability output is NOT a reliable confidence signal. A sentence like "Officials say the situation is improving" can return 0.91 "fact" confidence even when it is unverifiable attribution. This is documented across multiple NLP production deployments: "DNNs suffer from overconfidence... an overconfident DNN gives high confidence in wrong predictions." Breaking news headlines — often just 10-15 words — provide insufficient context for NLI inference, leading to high-confidence wrong labels.

**Why it happens:**
Softmax scores reflect relative ordering among label hypotheses, not absolute probability of correctness. Zero-shot NLI was trained on MNLI/ANLI premise-hypothesis pairs, not short news sentences. The model sees a short text, picks the highest-scoring hypothesis label, and returns that score as "confidence" — but calibration was never validated for this use case.

**How to avoid:**
- Never display raw softmax scores as confidence without calibration
- Apply temperature scaling as a post-processing step (well-documented, effective: see Guo et al. 2017, "On Calibration of Modern Neural Networks")
- For texts under ~30 tokens, lower the displayed confidence cap to 0.6 regardless of model output
- Route very short texts (headlines only, < 20 words) to the "unclear" bucket rather than forcing a classification
- Test calibration using a reserved evaluation set before shipping the UI confidence display

**Warning signs:**
- Classifier returns 0.85+ confidence on single-sentence breaking news with no verifiable claim
- Sentences containing direct quotes classified as "fact" at high confidence
- Test accuracy on your 80% target achieved in training but not on held-out breaking news articles

**Phase to address:** NLP classifier implementation phase (before UI integration; confidence display depends on calibrated scores)

---

### Pitfall 2: Label Wording Sensitivity Breaks Zero-Shot Classification

**What goes wrong:**
Zero-shot NLI classifiers are extremely sensitive to the exact wording of label hypotheses. Changing "This is a factual statement" to "This text is objective" changes classification outcomes significantly — sometimes flipping labels. This is not a minor accuracy concern; it causes inconsistent results across similar sentences and makes the 80% accuracy target a moving target depending on hypothesis phrasing. Research confirms: "Sensitivity to label ambiguity" is a core limitation, "mitigated via multi-hypothesis generation and ensemble scoring."

**Why it happens:**
The NLI model computes entailment between the input text and each label hypothesis. It is fundamentally a semantic similarity task. Subtly different hypotheses explore different semantic neighborhoods in the model's latent space. There is no "right" phrasing — only phrasing that empirically works on your evaluation data.

**How to avoid:**
- Treat hypothesis wording as a tunable hyperparameter; test at least 5 phrasings per class before finalizing
- Use multi-hypothesis ensembling: run the same text through 2-3 differently-worded hypotheses per class and average scores
- Establish a fixed evaluation set of 100+ labeled sentences BEFORE choosing final hypotheses; pick the phrasing that maximizes F1 on that set
- Document the exact hypothesis strings in code as named constants, not magic strings

**Warning signs:**
- Accuracy varies by more than 5 points when hypothesis wording is changed
- Team members informally tweaking hypothesis strings without re-running the evaluation set
- Fact/opinion boundary shifts noticeably between articles from different sources

**Phase to address:** NLP classifier design phase — hypothesis wording must be locked before building the rule-based pre-filter or the UI layer

---

### Pitfall 3: Treating Quoted Speech as Factual (Attribution Failure)

**What goes wrong:**
Sentences like "The CEO said profits are up 40% this quarter" or "'This will end the crisis,' the president declared" are opinions or unverifiable claims embedded in a factual reporting structure. Rule-based heuristics that detect attribution words ("said," "claimed," "according to") often misfire: they may classify the entire sentence as "opinion" (wrong — the attribution is factual) or as "fact" (wrong — the quoted claim is unverifiable). Zero-shot models trained on MNLI also struggle because the NLI training data has different distribution from quoted speech in news.

**Why it happens:**
Attribution sentences have two semantic layers: the fact of attribution (objectively true) and the content of the attribution (unverifiable). Most classifiers operate at sentence level and cannot decompose these layers. The model sees surface-level factual framing ("The report says...") and infers "fact."

**How to avoid:**
- Build a dedicated attribution pattern detector as a pre-processing step: regex + spaCy dependency parsing to identify quotes and reported speech
- Any sentence containing a direct quote or reported speech clause should be pre-labeled "mixed" with low confidence before the transformer even runs
- Add "sentences containing direct quotes" as a specific test case category in the evaluation set
- Flag the "mixed" category visually in the UI with a special indicator (not just yellow — add a quote icon)

**Warning signs:**
- Evaluation set shows high accuracy overall but low accuracy on sentences from interview-heavy sources (e.g., Reuters, NPR)
- Color-coded UI shows green (fact) on sentences that begin with a person's name + reporting verb + quoted claim
- User UAT flagging "that's not a fact, the politician just said it"

**Phase to address:** NLP classifier design phase (rule-based pre-filter design) + UAT validation phase

---

### Pitfall 4: Duplicate Articles Silently Inflating the Database

**What goes wrong:**
The same news story appears across multiple RSS feeds from different sources (BBC, Reuters, AP frequently republish each other's wire copy). Without robust deduplication, the database fills with near-identical articles — each classified separately, potentially with inconsistent labels. 38% of active news feeds emit at least one duplicate per week; 29% of feeds in W3C corpus have duplicate GUIDs. At 100+ articles/day across 5+ sources, this becomes a significant problem within a week of operation.

**Why it happens:**
RSS GUIDs are not globally unique across publishers. The same underlying story published by BBC and Reuters will have different GUIDs, different URLs, slightly different headlines. Simple URL or GUID checks miss these. Naive deduplication only catches exact copies.

**How to avoid:**
- Implement two-stage deduplication: (1) exact match on normalized URL + title hash, (2) near-duplicate detection using MinHash or SimHash on article body content
- Add a `content_hash` column to the articles table at schema design time — much cheaper to add early than retrofit
- Index on `(source, published_at, title_hash)` as a unique constraint in PostgreSQL — database enforces uniqueness at insert time
- Set a configurable similarity threshold (0.85 is a reasonable starting point, same as Feedly uses) for near-duplicate suppression

**Warning signs:**
- Database article count growing faster than expected given source count and posting frequency
- Search results returning the same story multiple times from different sources
- Classification pipeline running significantly longer than expected because it's reprocessing known stories

**Phase to address:** Database schema design phase (before ingestion pipeline is built; retrofitting deduplication is painful)

---

### Pitfall 5: APScheduler Running Multiple Instances Silently Executes Jobs Multiple Times

**What goes wrong:**
APScheduler (the likely choice for background scheduling in FastAPI) runs one scheduler per process. If FastAPI is started with multiple workers (e.g., `uvicorn --workers 4`), each worker spawns its own APScheduler instance. Result: every RSS fetch and classification job runs 4 times simultaneously. Articles get inserted 4 times. Classification runs 4 times per article. This is officially documented: "Sharing a persistent job store among two or more processes will lead to incorrect scheduler behavior like duplicate execution." This failure is silent — no errors, just extra load and corrupt data.

**Why it happens:**
APScheduler is designed for single-process use. FastAPI's multi-worker mode is common in production. The combination is a trap developers fall into when they start with one worker (works fine) and then scale up (breaks silently).

**How to avoid:**
- In development: use `uvicorn --workers 1` and document this constraint explicitly
- In production: use a dedicated scheduler process separate from the web server, OR use a persistent job store (PostgreSQL-backed) with APScheduler's inter-process locking feature
- Alternative: move to Celery Beat for production scheduling — designed for multi-process environments
- Add a `scheduler_lock` table or use PostgreSQL advisory locks to prevent concurrent job execution
- Log every job execution with a UUID and check for duplicate UUIDs in the first week of operation

**Warning signs:**
- Article count in database growing at N× the expected rate (where N = worker count)
- Classification taking longer than expected during fetch windows
- Logs showing the same feed URL fetched multiple times within the same minute

**Phase to address:** Background job / ingestion pipeline phase — configure single-worker constraint before deployment; architect for multi-process safety before adding workers

---

## Moderate Pitfalls

### Pitfall 6: RSS Feed Encoding and Malformed XML Causes Silent Data Loss

**What goes wrong:**
RSS feeds from real publishers frequently contain malformed XML, non-UTF-8 encodings (Windows-1252, Latin-1), invalid characters in CDATA sections, and namespace violations. feedparser handles many of these via its "bozo" detection, but silently degrades — fields silently become empty strings or are truncated. An article with a Windows-1252 encoded description that contains an em dash (0x96) may parse with an empty body field. At 100+ articles/day, 5-10% data loss from encoding issues is invisible until users notice missing content.

**How to avoid:**
- Always check `feed.bozo` and `feed.bozo_exception` on every parsed feed; log warnings for all bozo feeds
- Normalize all text to UTF-8 immediately after parsing using `ftfy` library (designed specifically for encoding repair)
- Treat empty article body as a failure condition, not a valid state — log and skip rather than storing empty-body articles
- Test ingestion against all 5 target sources (BBC, Reuters, AP, NPR, Al Jazeera) before launch; each has known encoding quirks

**Warning signs:**
- Articles stored with empty `body` or `description` fields
- Classification pipeline returning "unclear" at unusually high rates (often symptom of empty/garbled input text)
- Special characters (em dashes, smart quotes) appearing as `?` or `â€™` in the UI

**Phase to address:** Ingestion pipeline phase (build encoding normalization into the fetch layer from day one)

---

### Pitfall 7: PostgreSQL FTS Without a GIN Index Degrades Catastrophically at Scale

**What goes wrong:**
PostgreSQL full-text search using `to_tsvector()` without a GIN index performs sequential table scans. At 100 articles/day, the database reaches 36,500 articles per year. Sequential scan on `to_tsvector(body)` at this scale takes 2-8 seconds per query instead of milliseconds. The critical mistake: developers test FTS during development with 50 articles and get fast results, then ship to production where the query time has grown 700x.

**How to avoid:**
- Add a `tsvector` generated column to the articles table at schema design time: `body_tsv tsvector GENERATED ALWAYS AS (to_tsvector('english', body)) STORED`
- Create the GIN index on that column immediately: `CREATE INDEX idx_articles_body_tsv ON articles USING GIN(body_tsv)`
- Test with at least 10,000 synthetic articles before launch to validate query performance at expected scale
- Set up `EXPLAIN ANALYZE` as part of your test harness to confirm GIN index is being used, not seqscan

**Warning signs:**
- Search queries taking >500ms during development (signals missing index)
- `EXPLAIN ANALYZE` showing "Seq Scan" on articles table for FTS queries
- Performance acceptable at launch but degrading week-over-week as article count grows

**Phase to address:** Database schema design phase (index must be created before data is inserted; adding it retroactively is expensive on large tables)

---

### Pitfall 8: Transformer Model Cold-Start Blocking Web Request Thread

**What goes wrong:**
DeBERTa-v3-base takes 5-15 seconds to load from disk on first use. If the transformer pipeline is initialized lazily (on first request) rather than at application startup, the first classification request after app restart causes a 15-second timeout. In FastAPI's synchronous route handlers, this blocks the event loop. In async handlers with `run_in_executor`, it still monopolizes a thread pool worker. Users see a timeout; the app appears broken.

**How to avoid:**
- Load the transformer pipeline at application startup in a `lifespan` context manager, not lazily
- Run classification in a separate thread pool (`asyncio.get_event_loop().run_in_executor`) to keep FastAPI non-blocking
- Add a health check endpoint that verifies the model is loaded; fail readiness until the model is warm
- Consider quantized model (`int8`) for faster load time on CPU — typically 2-4x faster load, 30-40% faster inference at minimal accuracy cost

**Warning signs:**
- First request after restart times out or takes 10+ seconds
- Memory usage spikes suddenly on first classification request rather than at startup
- Health check passes but first real request fails

**Phase to address:** Application setup / FastAPI integration phase (model loading strategy must be decided before wiring routes)

---

### Pitfall 9: Sentence Segmentation Failures on News Article Structure

**What goes wrong:**
Standard sentence tokenizers (NLTK punkt, spaCy) fail on patterns common in news writing: bylines ("LONDON, Feb 23 (Reuters) —"), datelines, abbreviations in source attribution ("U.S. Rep.", "Dr.", "Sen."), and multi-sentence direct quotes. A single article may generate 5-15% incorrectly segmented "sentences" — fragments that are not classifiable units. Running the transformer on these fragments wastes compute and produces garbage classifications.

**How to avoid:**
- Use spaCy's sentence segmenter (not NLTK punkt) — it handles news article patterns better due to dependency parsing
- Add a pre-processing step that strips bylines/datelines before sentence segmentation using regex patterns for common news formats
- Filter out "sentences" under 8 words before classification — they are almost always fragments, not classifiable statements
- Log segmented sentence count per article and alert if variance is high (signals segmentation failure)

**Warning signs:**
- Classification pipeline processing many single-word or 2-3 word "sentences"
- Unusually high "unclear" rate from the classifier on a specific news source
- Direct quotes appearing split across multiple "sentences" in the output

**Phase to address:** NLP pre-processing / classifier pipeline phase

---

### Pitfall 10: Accuracy Target (80%) Measured on Wrong Distribution

**What goes wrong:**
The 80% classifier accuracy target is meaningful only if the evaluation set matches production data. Teams commonly build evaluation sets from easily-labeled examples (clear opinions, clear facts) and report 80%+ accuracy — but the production data is dominated by mixed/ambiguous sentences (attributed claims, hedged statements, breaking news fragments) where accuracy is 60-65%. The metric looks good; the product feels broken.

**Why it happens:**
Annotation is hard. Human annotators reach for clear cases. Ambiguous sentences cause disagreement, so they get excluded or resolved arbitrarily. The resulting evaluation set is easier than reality.

**How to avoid:**
- Build the evaluation set BEFORE building the classifier — prevents unconscious tuning to the eval set
- Include a mandatory "hard cases" category (at minimum 30% of eval set): attributed quotes, hedged claims ("sources say"), satire-adjacent headlines, breaking news fragments
- Measure accuracy separately for each category (fact, opinion, mixed, unclear) — overall accuracy hides per-class failures
- Use inter-annotator agreement (Cohen's Kappa) to validate label quality; target κ > 0.7 for the eval set

**Warning signs:**
- Evaluation accuracy significantly higher than accuracy during manual UAT of 10 articles
- Low inter-annotator agreement when team members independently label the same 20 sentences
- Users in UAT consistently questioning "obvious" classifications on mixed/attributed sentences

**Phase to address:** NLP classifier design phase (evaluation set design) + testing phase (automated test suite)

---

## Technical Debt Patterns

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Skip GIN index for FTS | Simpler schema, faster initial setup | Catastrophic query degradation at 1k+ articles | Never — add at schema creation |
| Lazy model loading | Faster app startup | First-request timeout; unpredictable cold starts | Never — use lifespan startup |
| Raw softmax as confidence display | Simpler code | Misleads users; confidence scores are not calibrated | Never for user-facing display |
| Single-stage URL deduplication only | Fast to implement | Silent duplicate accumulation from cross-publisher stories | MVP only if near-dup detection is Phase 2 |
| APScheduler in multi-worker mode | Zero extra configuration | Duplicate job execution, data corruption | Never — use single-worker or job locking |
| NLTK punkt for sentence splitting | Familiar library | 5-15% segmentation failures on news article patterns | Never — use spaCy |
| Hard-coded hypothesis strings in zero-shot | Fast initial implementation | Cannot tune without code changes; no versioning | Never — store as named constants with version |

---

## Integration Gotchas

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| feedparser | Treating `feed.bozo = True` as a hard failure | Log as warning, extract what was parsed, continue — bozo means degraded, not broken |
| feedparser | Ignoring `entry.published_parsed` timezone naive datetime | Always convert to UTC using `calendar.timegm(entry.published_parsed)` immediately after parsing |
| NewsAPI.org free tier | Assuming 100 requests/day means 100 articles | 100 requests/day, with up to 20 articles per request — plan fetch schedule accordingly |
| RSS feeds (BBC, Reuters, AP) | Fetching more frequently than feed update cycle | Most news RSS feeds update every 15-30 min; fetching every minute wastes requests and risks IP block |
| DeBERTa / BART pipeline | Passing full article text to classifier | These models have 512-token input limit; chunk articles into sentences first, then classify per-sentence |
| PostgreSQL GIN index | Adding GIN index after table has millions of rows | `CREATE INDEX` on large table requires table lock; schedule during low-traffic window |
| APScheduler + FastAPI | Starting scheduler in `@app.on_event("startup")` | Use `lifespan` context manager (deprecated warning in FastAPI 0.93+); use `contextlib.asynccontextmanager` |

---

## Performance Traps

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| Classifying full article text instead of per-sentence | Model truncates at 512 tokens silently; tail of article never classified | Segment first, classify sentences individually | Every article >400 words (~512 tokens) |
| Running transformer synchronously in web request | Page loads take 2-10 seconds while model runs | Decouple: classify during ingestion, store results, serve pre-classified data | First article viewed after ingestion |
| Fetching all articles on startup instead of on schedule | 5+ RSS feeds fetched simultaneously on every restart, hitting rate limits | Queue initial fetch into scheduler, add jitter between sources | Multi-worker restart in production |
| FTS query using `to_tsvector()` inline (not stored column) | Every search recomputes vectors on full table | Use `GENERATED ALWAYS AS ... STORED` column with GIN index | ~500+ articles in database |
| Loading transformer model in every test | Test suite takes 5+ minutes | Mock classifier in unit tests; use integration tests sparingly | As soon as test count > 10 |

---

## Security Mistakes

| Mistake | Risk | Prevention |
|---------|------|------------|
| Fetching and rendering raw HTML from RSS article bodies | XSS via malicious RSS feed content injected into templates | Strip all HTML tags from ingested content using `bleach` or `markupsafe` before storage |
| Storing full article bodies from sources that embed tracking pixels | Privacy/GDPR exposure if serving fetched images | Strip `<img>` tags and external resource references; store text only |
| No rate limiting on search endpoint | Search endpoint becomes a denial-of-service vector | Add rate limiting to `/search` via `slowapi` or nginx upstream |
| Logging full article content at DEBUG level | Log files contain republished copyrighted content | Log article IDs and URLs only, not body text |
| Fetching feeds without timeouts | Single slow feed hangs the entire ingestion job | Set explicit `timeout=10` on all HTTP requests; fail fast per source |

---

## UX Pitfalls

| Pitfall | User Impact | Better Approach |
|---------|-------------|-----------------|
| Showing confidence scores as raw percentages (e.g., "91%") | Users treat 91% as near-certain; system is not that reliable | Show relative bands: "High / Medium / Low confidence" mapped to calibrated score ranges |
| Collapsing all opinions by default, never shown | Users distrust the tool — feels like censorship | Collapse opinions by default but make them trivially expandable; show opinion count prominently |
| Classifying at article level instead of sentence level | Results feel wrong — mixed articles are all-or-nothing | Always highlight inline at sentence level; article-level summary is secondary |
| Showing "unclear" classification without explanation | Users think the tool is broken | Show "unclear" with a brief tooltip: "This sentence contains a quote, attribution, or ambiguous claim" |
| No indication that satire sources are unclassifiable | Satire reads as opinion with high confidence | Flag known satire domains (The Onion, The Babylon Bee) before classification; display source warning |

---

## "Looks Done But Isn't" Checklist

- [ ] **RSS Ingestion:** Feed fetches working in dev does not mean all 5 sources are tested — verify BBC, Reuters, AP, NPR, Al Jazeera individually, especially their encoding and feed format quirks
- [ ] **Deduplication:** Articles not duplicating in dev (low volume) does not mean deduplication works — test with same story from two sources simultaneously
- [ ] **Classifier Accuracy:** Passing 80% on your hand-crafted eval set does not mean 80% on production — run against 50 real articles from each source and measure
- [ ] **Confidence Display:** UI showing confidence scores does not mean scores are calibrated — verify that sentences labeled "high confidence" are correct at the claimed rate
- [ ] **APScheduler:** Jobs running in dev (single worker) does not mean safe in production — test multi-worker behavior explicitly
- [ ] **FTS Performance:** Search returning results in dev (small dataset) does not mean acceptable performance at scale — load test with 10,000 articles
- [ ] **Transformer Memory:** Model loading without error in dev does not mean it fits in production memory limits — profile peak RSS during classification

---

## Recovery Strategies

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| Overconfident scores in production | MEDIUM | Add temperature scaling calibration layer; re-run classifications on stored sentences; update displayed scores |
| Missing GIN index on large table | HIGH | Schedule index creation during maintenance window; table locked during creation; users lose search |
| APScheduler duplicate jobs | HIGH | Purge duplicate articles; re-run deduplication; switch to single-worker or Celery Beat; database cleanup |
| Wrong evaluation set (accuracy overstated) | MEDIUM | Build proper eval set; re-measure; adjust hypothesis strings; may require re-classifying stored articles |
| Malformed encoding data loss | LOW | Re-fetch affected articles with ftfy normalization; run encoding audit on existing stored articles |
| Attribution sentences misclassified at scale | MEDIUM | Add attribution pre-filter; re-classify stored articles; update stored confidence scores |

---

## Pitfall-to-Phase Mapping

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| Zero-shot overconfidence | NLP classifier design + testing | Calibration test: confidence scores correlate with actual accuracy on held-out set |
| Label hypothesis sensitivity | NLP classifier design (pre-code) | 5+ hypothesis phrasings tested; final choice documented with F1 scores |
| Attributed speech misclassification | Rule-based pre-filter design | UAT evaluation set includes 20+ attribution sentences |
| Duplicate articles | Database schema design | Insert same story from two sources; verify only one stored |
| APScheduler multi-worker | Background jobs implementation | Explicitly test with 2 workers; job executes exactly once |
| RSS encoding loss | Ingestion pipeline implementation | Test all 5 target sources; verify no empty body fields |
| Missing GIN index | Database schema design | `EXPLAIN ANALYZE` confirms GIN index used on search queries |
| Transformer cold-start blocking | Application setup / FastAPI integration | Health check endpoint shows model loaded; first request responds < 2s |
| Sentence segmentation failures | NLP pre-processing implementation | Segmented sentence count per article within expected range; no 1-2 word fragments |
| Accuracy measured on wrong distribution | NLP classifier design (eval set creation) | Eval set includes 30%+ hard cases; per-class accuracy reported separately |
| Confidence display misleads users | UI implementation | User UAT: participants understand confidence levels correctly |
| FTS degradation at scale | Database schema design | Query time < 200ms with 10,000 synthetic articles |

---

## Sources

- Hugging Face Zero-Shot Classification Task: https://huggingface.co/tasks/zero-shot-classification
- Guo et al. "On Calibration of Modern Neural Networks" (2017): https://arxiv.org/pdf/1706.04599
- Giskard Overconfidence Documentation: https://legacy-docs.giskard.ai/en/stable/knowledge/key_vulnerabilities/overconfidence/index.html
- Joe Davison, "Zero Shot Learning in Modern NLP": https://joeddav.github.io/blog/2020/05/29/ZSL.html
- MoritzLaurer DeBERTa-v3-base-zeroshot-v2.0 (Hugging Face): https://huggingface.co/MoritzLaurer/deberta-v3-base-zeroshot-v2.0
- feedparser Character Encoding docs: https://pythonhosted.org/feedparser/character-encoding.html
- feedparser GitHub Issues (malformed XML): https://github.com/kurtmckee/feedparser/issues/101
- APScheduler FAQ (interprocess safety): https://apscheduler.readthedocs.io/en/3.x/faq.html
- APScheduler common mistakes (Medium): https://sepgh.medium.com/common-mistakes-with-using-apscheduler-in-your-python-and-django-applications-100b289b812c
- PostgreSQL FTS limitations (Meilisearch): https://www.meilisearch.com/blog/postgres-full-text-search-limitations
- PostgreSQL FTS Crunchy Data: https://www.crunchydata.com/blog/postgres-full-text-search-a-search-engine-in-a-database
- RSS Duplicate Detection: http://www.xn--8ws00zhy3a.com/blog/2006/08/rss-dup-detection
- Feedly Duplicate Articles: https://docs.feedly.com/article/202-duplicate-articles
- Zero-shot vs Similarity-based Text Classification (Towards Data Science): https://towardsdatascience.com/zero-shot-vs-similarity-based-text-classification-83115d9879f5/
- Transformers Pipeline optimization (KDnuggets): https://www.kdnuggets.com/5-tips-for-building-optimized-hugging-face-transformer-pipelines
- NLP Sentence Segmentation review: https://tm-town-nlp-resources.s3.amazonaws.com/ch2.pdf
- RSS Aggregation myths: https://www.wprssaggregator.com/rss-content-aggregation-myths-busted/
- Transformers Pipelines 2025 (Johal): https://johal.in/transformers-pipelines-zero-shot-classification-tasks-2025/
- Subjectivity/Sentiment Analysis (Bing Liu, UIC): https://www.cs.uic.edu/~liub/FBS/NLP-handbook-sentiment-analysis.pdf

---
*Pitfalls research for: News aggregator + NLP fact/opinion classifier (FactFeed)*
*Researched: 2026-02-23*
