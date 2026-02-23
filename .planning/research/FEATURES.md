# Feature Research

**Domain:** News aggregation + NLP fact/opinion classification web app
**Researched:** 2026-02-23
**Confidence:** MEDIUM (competitor analysis HIGH; NLP-specific UX patterns MEDIUM; inline sentence-level classification UX LOW — this is a novel intersection)

---

## Feature Landscape

### Table Stakes (Users Expect These)

Features users assume exist. Missing these = product feels incomplete.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Article list with headline, source, date | Any aggregator shows this; it's the minimum viable display | LOW | Reverse-chronological default; source attribution required |
| Keyword search | Every news product has search; users immediately try it | LOW | Full-text search over stored articles; PostgreSQL FTS handles this |
| Source filter | Users trust some outlets more than others; standard in all aggregators | LOW | Filter by outlet name (BBC, Reuters, AP, etc.) |
| Date/recency filter | News is time-sensitive; stale results feel broken | LOW | Last 24h, 7 days, 30 days minimum; range picker is v2 |
| Article viewer / read mode | Users click through to read the full article; link-only feels lazy | MEDIUM | Show inline content with highlights; link to original at top |
| Inline fact/opinion highlighting | This is the core differentiator of FactFeed, but users coming from the premise will expect it | HIGH | Color-coded (green=fact, red=opinion, yellow=mixed); must be present at launch or the product has no purpose |
| Confidence score display | Any NLP output without a score feels like a black box; users want to calibrate trust | MEDIUM | Show 0.0–1.0 on hover or alongside label; do not hide it |
| Source credibility signal | Ground News, MBFC, and AllSides have trained users to expect outlet-level trust signals | LOW | Use MBFC/AllSides ratings as static metadata; do not attempt live fact-checking at outlet level |
| Graceful handling of paywall content | Users encounter paywalled articles in aggregators; behavior must be defined | LOW | Display excerpt + link; label "paywall" clearly so users are not surprised |
| Responsive layout | Users read news on mobile; non-responsive = broken | MEDIUM | Mobile-first viewport optimization; Jinja2 templates with CSS |

### Differentiators (Competitive Advantage)

Features that set the product apart. Not required, but valued.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Sentence-level fact/opinion classification with per-sentence confidence scores | No major consumer product does sentence-level inline labeling at this granularity; Ground News rates outlets, not sentences | HIGH | This is the core FactFeed thesis; all competitors operate at article or outlet level |
| "Facts first" result ordering | Users who want objective content shouldn't have to dig; surfacing high-fact-density articles first is a concrete UX advantage | MEDIUM | Sort by ratio of fact-classified sentences; configurable |
| Collapsible opinion sections | Lets users choose to expose opinion content without hiding it — honest and useful | MEDIUM | Default collapsed; expand on click with label "Show opinion content" |
| Ambiguous/unclear content flagging | Quotes, satire, and breaking news without context are systematically mishandled by all competitors; explicit "unclear" labeling builds trust | MEDIUM | Low-confidence sentences labeled yellow with "unclear" badge |
| Topic/category browsing | Users navigate news by topic (politics, science, business); topic-based browsing is expected in v1.5 | MEDIUM | Requires topic classification pass (separate from fact/opinion); NLP add-on |
| Mixed-content label ("mixed") | Distinguishing "mostly fact with opinion embedded" from pure opinion is more nuanced than competitors offer | LOW | Fourth classification state; makes the classifier feel more honest |
| Source coverage breadth indicator | Showing how many sources covered a story signals importance; Ground News does this at scale, FactFeed can do it at 5-source scale | LOW | Count sources covering same story; requires deduplication or story clustering |
| No user tracking / privacy-by-default | Users concerned about surveillance increasingly value products that don't collect data; explicit "no login, no tracking" is a differentiator | LOW | State clearly in UI; no analytics cookies; optional local search history only |

### Anti-Features (Commonly Requested, Often Problematic)

Features that seem good but create problems.

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| Personalized feed / recommendation algorithm | Every major news app has it; users assume it | Creates filter bubble; opaque; requires user data collection; contradicts FactFeed's "no bias" mission; requires ML infrastructure beyond project scope | Let users control their own filters (keyword, source, date); make filters transparent and user-driven |
| Real-time article streaming / websocket updates | "I want breaking news instantly" | Increases infrastructure complexity dramatically; scheduled batch ingestion (100+ articles/day) is the stated goal; real-time is premature optimization | Show last-updated timestamp; allow manual refresh; clearly communicate batch cadence |
| User accounts and authentication | "Save my preferences" | Requires auth infrastructure, session management, password security, GDPR considerations; PROJECT.md explicitly lists this as out of scope v1 | Store preferences in localStorage client-side; no login required |
| Automated claim verification against external databases | "Is this claim actually true?" | ClaimBuster-style verification requires external fact-check database integration, significant latency, and produces unreliable results at news-article scale; this is a different product | Classify fact vs. opinion (verifiability) not true vs. false (verification); make the distinction explicit in UI copy |
| Source bias ratings computed by FactFeed | "Tell me which outlets are biased" | MBFC, AllSides, and Ad Fontes Media have spent years developing these ratings with human review; building a competing system is expensive and error-prone; users will compare and distrust a novel system | Ingest and display MBFC/AllSides ratings as attributed third-party metadata |
| Social sharing and commenting | "Let users discuss articles" | Community features require moderation, user accounts, abuse handling; significantly expands scope; PROJECT.md explicitly out of scope | Link to original articles; let the source platforms handle discussion |
| Multi-language support | "I want non-English news" | NLP models for fact/opinion classification perform significantly worse in non-English; training data is English-heavy; managing source credibility across languages is a separate research project | English-only for v1; document clearly; v2 consideration |
| Email/push notifications | "Alert me when new articles match my query" | Requires notification infrastructure, user contact info storage, unsubscribe handling; PROJECT.md explicitly deferred | Manual refresh; clear batch schedule in UI ("Updated every X hours") |
| Visualization / bias charts | "Show me bias over time" | Charting infrastructure is medium complexity; requires historical data accumulation before it's meaningful; users want to read articles, not analyze dashboards first | Surface the data in article metadata first; charts are v2 after data accumulates |

---

## Feature Dependencies

```
[RSS/API ingestion pipeline]
    └──required by──> [Article storage (PostgreSQL)]
                          └──required by──> [Full-text search]
                          └──required by──> [NLP fact/opinion classification]
                                                └──required by──> [Inline highlighting in article viewer]
                                                └──required by──> [Confidence score display]
                                                └──required by──> [Facts-first ordering]
                                                └──required by──> [Collapsible opinion sections]
                                                └──required by──> [Ambiguous content flagging]

[Article storage]
    └──required by──> [Source filter]
    └──required by──> [Date filter]
    └──required by──> [Keyword search]

[Keyword search]
    └──enhances──> [Source filter]  (combined query)
    └──enhances──> [Date filter]    (combined query)

[Source credibility metadata (static)]
    └──enhances──> [Article viewer]  (outlet badge)
    └──enhances──> [Search results]  (credibility indicator in list)

[Inline highlighting]
    └──enhances──> [Article viewer]  (transforms plain text into annotated view)

[Facts-first ordering]
    └──conflicts with──> [Chronological ordering]  (pick one as default; other as toggle)
```

### Dependency Notes

- **Ingestion pipeline required by everything:** No articles = no product. This is Phase 1, blocks all other phases.
- **NLP classification required by all highlight/score features:** The classifier must work before any display layer can be built. Classification accuracy gates UX quality.
- **Full-text search requires stored articles:** Cannot search what hasn't been ingested and indexed. PostgreSQL FTS indexing must be set during schema design, not retrofitted.
- **Facts-first ordering conflicts with chronological ordering:** Must decide on a default sort and provide a toggle. Do not try to merge them into one view.
- **Static source credibility metadata enhances but does not block:** MBFC ratings can be loaded as a static JSON file; this does not require a live API call and is a low-risk enhancement to the article view.

---

## MVP Definition

### Launch With (v1)

Minimum viable product — what's needed to validate the concept.

- [ ] Ingestion from 5 RSS sources (BBC, Reuters, AP, NPR, Al Jazeera) on a scheduled background job — without this, the product has no content
- [ ] NLP classification pipeline: hybrid rule-based + zero-shot transformer, outputting fact/opinion/mixed/unclear per sentence with 0.0–1.0 confidence scores — this is the entire thesis
- [ ] Article storage in PostgreSQL with FTS index — needed for search and retrieval
- [ ] Article list view (headlines, source, date, brief excerpt) with keyword search, source filter, and date filter — minimum navigation surface
- [ ] Article viewer with inline color-coded highlighting (green/red/yellow) and confidence scores on hover — the core UX that proves the concept
- [ ] "Facts first" as default sort order, with toggle to recency — demonstrates the product's point of view
- [ ] Collapsible opinion sections (default collapsed) — enforces the "facts prioritized" value proposition without hiding information
- [ ] Graceful error handling: paywalled content labeled, API failures silent, low-confidence sentences flagged — without this, classifier errors break trust

### Add After Validation (v1.x)

Features to add once core is working and classifier accuracy is confirmed.

- [ ] Topic/category browsing — add when user feedback shows topic navigation is a real need; requires topic classification NLP pass
- [ ] Source coverage breadth indicator (how many sources covered this story) — add when article deduplication/clustering is implemented
- [ ] Static MBFC/AllSides source credibility badge in article viewer — low-complexity enhancement; add when article viewer is stable
- [ ] NewsAPI.org supplemental feed integration — add after core 5 RSS sources are stable and rate limits are characterized

### Future Consideration (v2+)

Features to defer until product-market fit is established.

- [ ] User feedback loop for misclassification corrections — requires user accounts or session tracking; defer
- [ ] Multi-language support — NLP model quality in non-English is significantly lower; defer until English pipeline is mature
- [ ] Email/push notifications — requires notification infrastructure and user contact info; defer
- [ ] Bias visualization/charts — requires accumulated historical data to be meaningful; defer
- [ ] Mobile app (iOS/Android) — web-first responsive is sufficient; defer until web product is validated

---

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| RSS ingestion pipeline | HIGH | MEDIUM | P1 |
| NLP fact/opinion classifier | HIGH | HIGH | P1 |
| Article storage + FTS | HIGH | MEDIUM | P1 |
| Inline sentence highlighting | HIGH | MEDIUM | P1 |
| Confidence score display | HIGH | LOW | P1 |
| Keyword search | HIGH | LOW | P1 |
| Source + date filters | MEDIUM | LOW | P1 |
| Facts-first sort order | HIGH | LOW | P1 |
| Collapsible opinion sections | MEDIUM | LOW | P1 |
| Ambiguous content flagging | MEDIUM | LOW | P1 |
| Graceful error handling | HIGH | LOW | P1 |
| Static source credibility metadata | LOW | LOW | P2 |
| Topic/category browsing | MEDIUM | MEDIUM | P2 |
| Story clustering / coverage breadth | LOW | HIGH | P2 |
| User feedback for misclassification | MEDIUM | HIGH | P3 |
| Personalized feed | LOW | HIGH | P3 (anti-feature) |
| Visualization/charts | LOW | MEDIUM | P3 |

**Priority key:**
- P1: Must have for launch
- P2: Should have, add when possible
- P3: Nice to have, future consideration

---

## Competitor Feature Analysis

| Feature | Google News | Ground News | AllSides | MBFC | Full Fact / ClaimBuster | FactFeed Approach |
|---------|-------------|-------------|----------|------|-------------------------|-------------------|
| Article aggregation | Yes (20K+ sources) | Yes (50K+ sources, 60K articles/day) | Yes (left/center/right framing) | No (source ratings only) | No (claim monitoring only) | Yes (5 curated sources; quality over quantity) |
| Outlet-level bias rating | No | Yes (from AllSides + MBFC + Ad Fontes) | Yes | Yes | No | Ingest MBFC/AllSides as static metadata |
| Article-level bias analysis | Limited (AI summaries) | No | Limited (bias checker for articles) | No | No | Not FactFeed's focus; focus is fact vs. opinion |
| Sentence-level fact/opinion classification | No | No | No | No | Yes (claim detection, not opinion labeling) | YES — the FactFeed thesis |
| Confidence scores per sentence | No | No | No | No | Yes (claim check-worthiness score) | Yes (0.0–1.0 displayed on hover) |
| Inline text highlighting | No | No | No | No | No | Yes — green/red/yellow color coding |
| Full-text search | Yes | Limited | Limited | No | No | Yes (PostgreSQL FTS) |
| Filter by source | Yes | Yes | Yes | Yes | N/A | Yes |
| Filter by date | Yes | Yes | Limited | No | N/A | Yes |
| Personalized feed | Yes (algorithmic) | Limited | No | No | No | Explicitly avoided |
| User accounts required | No (but Google account optional) | No (but premium paywall) | No | No | No | No — privacy by default |
| Privacy / no tracking | No | No | No | No | N/A | Yes — explicit design goal |
| Free to use | Yes | Free tier (paywalled features) | Yes | Yes | Yes | Yes — no paid APIs |

---

## Sources

- [Ground News About / Features](https://ground.news/about) — Competitor analysis, feature set, scale (HIGH confidence — official site)
- [Ground News Rating System](https://ground.news/rating-system) — Outlet-level bias and factuality ratings (HIGH confidence — official site)
- [AllSides Balanced News](https://www.allsides.com/unbiased-balanced-news) — Side-by-side perspective model, bias ratings (HIGH confidence — official site)
- [Full Fact AI Automated Tools](https://fullfact.org/automated) — Claim detection pipeline, BERT-based claim identification (MEDIUM confidence — official site, tool scope differs from FactFeed)
- [ClaimBuster IDIR Lab](https://idir.uta.edu/claimbuster/) — Check-worthy claim scoring, NLP approach (MEDIUM confidence — academic tool)
- [MBFC Methodology](https://mediabiasfactcheck.com/methodology/) — Source-level ratings methodology (HIGH confidence — official site)
- [WebSearch: news aggregator table stakes features 2025](https://www.wprssaggregator.com/a-list-of-best-news-aggregators/) — Feed management, search, source filtering norms (MEDIUM confidence — WebSearch, multiple sources agree)
- [WebSearch: NLP fact-opinion classification confidence scores 2025](https://arxiv.org/html/2301.11850v4) — Sentence-level factuality annotation research (MEDIUM confidence — academic)
- [WebSearch: algorithmic personalization pitfalls 2025](https://www.sciencedaily.com/releases/2025/11/251125081912.htm) — Filter bubble and personalization harms research (MEDIUM confidence — WebSearch)
- [CHI 2025: Fact-Checkers' Requirements for Explainable Automated Fact-Checking](https://dl.acm.org/doi/full/10.1145/3706598.3713277) — Professional fact-checker needs for confidence scores and explainability (MEDIUM confidence — peer-reviewed)
- [Media Bias Detector CHI 2025](https://dl.acm.org/doi/10.1145/3706598.3713716) — Real-time bias analysis tool design (MEDIUM confidence — peer-reviewed)

---

*Feature research for: News aggregation + NLP fact/opinion classification (FactFeed)*
*Researched: 2026-02-23*
