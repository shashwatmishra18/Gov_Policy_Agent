# Requirement mapping

Source: full local GOV-CS-028 proposal, 34 physical pages, read 2026-10-05. The PDF is ignored and not reproduced in this public repository. This matrix covers functional modules, objectives, quality controls, design choices and stated future scope; front matter and bibliography are reference material, not application features. **Planned** means no functionality delivered yet.

| Requirement / proposal location | Planned part | Current status and adaptation |
| --- | --- | --- |
| O1 grounded policy Q&A; pp.5,10,14 | 4–5 | Parts 4–6 eligible-source retrieval, bounded local answers, exact citations and limited same-model support checks delivered; complete semantic/legal verification not established |
| O2 clause/claim-level citations; pp.14,21 | 6 | Part 6 stable ordered claim/citation records, original version/page/span, controlled support reasons and authorized citation panel delivered; section heuristic, absent clauses null |
| O3 six-dimensional trust; pp.14,22,26 | 8 | Part 8 versioned post-validation audit delivered: factual citation coverage, six explicit component availabilities/evidence, null aggregates, English/Hindi panel; no calibrated correctness or independent agreement |
| O4 Hindi/English; pp.14,18,29 | 4,7,9 | Part 4 real multilingual retrieval and paired source-checked Hindi/English dev queries; Part 5 real English/Hindi generation samples with documented Hindi limitations; Part 7 bounded recorded Hinglish/mixed normalization and real paired development comparison; Part 9 profile-based English/Hindi navigation/bookmark states; independent evaluation pending |
| O5 hallucination <5%; p.14 | 11 | Aspirational; not measured or guaranteed |
| O6 Docker/cloud production; pp.14,30 | 12 | Part 12 separate local Compose, production frontend routing, private database/storage, explicit provisioning/model setup and native ownership tools implemented; isolated ingestion/search/private features/persistence/restore verified; factual Docker Qwen answer acceptance unverified (CPU timeout/GPU guard failures), native baseline retained; cloud/public deployment deferred, not production-ready |
| S1 500 documents/10 ministries; p.14 | 3–4,11 | Adapted toward 10–20 verified files/3–5 schemes; actual four PDFs/three schemes/171 pages, one eligible historical PIB text source and three excluded |
| S2 retrieval P@5 ≥0.80; pp.14,30 | 11 | Aspirational; Part 11 agent-authored frozen gold-span hit@5 9/9 on one source; not precision@5 or independent accuracy |
| S3 PDF, scanned PDF, HTML, text; pp.14–15,19 | 3,7 | Part 3 digital PDF/UTF-8 TXT implemented; scanned/mixed quality flags delivered, Part 7 bounded English/Hindi OCR with versioned artifacts and manual review; HTML/DOCX deferred |
| S4 feedback improvement; pp.14,22 | 10 | Part 10 private current votes/reasons/comments delivered; no automatic training or numerical trust component |
| S5 admin corpus/system dashboard; pp.14,22 | 3,9–10 | Part 3 upload/list/status/page inspection/preview/retry/archive delivered; Part 10 bounded admin aggregates delivered; no private question/comment browsing |
| S6 MLflow/model monitoring; pp.14,30 | 10–11 | Part 11 frozen hashes, code/model pins, private outputs and safe metric records delivered; MLflow not needed for this local workflow |
| S7 research publication; pp.14,31 | 12 | Optional future research; no acceptance promise |
| User management/profile/guest-user-admin; p.19 | 2,9 | Part 2 verified with real PostgreSQL and browser: user/admin, protected language profile; guest access limited to health/public registration/login |
| OAuth2/JWT/login/logout/refresh/brute-force limits; p.19 | 2,11 | Part 2 verified: Argon2id, JWT bearer (no third-party OAuth login), rotating/revocable cookie sessions, persistent throttling |
| Admin drag/drop upload, formats/size/virus scan; p.19 | 3,9,11 | Part 3 native file selector, actual stream 50 MiB cap, content validation and private storage; virus scanning unavailable |
| Scanned PDF detection/Tesseract eng+hin/300 DPI; pp.19–20 | 7 | Part 3 conservative low-text detection and needs_ocr/partial states; Part 7 real eng+hin Tesseract, page bounds, durable retries and mandatory review delivered; unreadable/oversized pages excluded |
| PDF text/headings/tables/metadata PyMuPDF; p.20 | 3 | Part 3 PyMuPDF exact physical-page text/spans; unknown dates null; heuristic headings, table layout not guaranteed |
| Clause-aware chunking, 512 tokens/50 overlap; p.20 | 3–4 | Part 4 actual tokenizer: 448-token passages/48 overlap including prefix/special-token safety, exact spans/heuristic sections/continuation; old chunks retained |
| SBERT+MuRIL, 768 dimensions; p.20 | 4 | Adapted to one pinned Sentence-Transformers multilingual E5-small, 384 normalized dimensions, documented official-card selection |
| Vector CRUD/HNSW/filtering; pp.20–21 | 4 | Persistent cosine Chroma, explicit embeddings, durable coherent generations, reconcile/rebuild, SQL eligibility/filter gates implemented |
| Top20 → rerank top5; HyDE; p.21 | 4,11 | Bounded-corpus candidate retrieval/top1–10 delivered; uncalibrated heuristic cutoff, reranker/HyDE deferred |
| Ollama Mistral/Llama, temp0.1/context4096/streaming; p.21 | 5,9 | Part 5 pinned Qwen3 4B Q4/Ollama, full LLM-token budgets, structured final-only answers, deadlines/cancellation and real GPU measurements; no unchecked streaming |
| Claim extraction/cosine source mapping; p.21 | 6 | Part 6 exact SQL provenance + lexical scope/value guards + bounded same-Qwen heuristic; similarity cannot prove support; old answers not_evaluated |
| Personal dashboard/history/saved answers/trust timeline; p.22 | 2,9 | Part 9 responsive protected History/Saved pagination and owner-only persistent bookmarks delivered; no copied answer snapshots or extended retention; decorative dashboard/trust timeline deferred, unavailable scores absent |
| Admin analytics/topics/P@5/feedback/error rates; p.22 | 10–11 | Part 10 retained run/latency/feedback/processing aggregates delivered; Part 11 separate frozen local evaluation delivered; topics/P@5 and independent labels remain unavailable; feedback ≠ accuracy |
| Feedback ratings/comments/review flags; p.22 | 10 | Part 10 owned current-access feedback with fixed reasons, 500-character plain comments, update/removal and cascade retention; no moderation/private-comment browser |
| PostgreSQL users/documents/chunks/queries/citations/trust/feedback; pp.23–27 | 2–10 | Auth/ingestion plus Part 4 audited reviews, generations, active pointer and exact passages verified on PostgreSQL 18.6; Part 5 owned queries/answers and exact grounding snapshots delivered; Part 6 additive claim/citation tables delivered; Part 8 nullable versioned evidence-quality snapshot and Part 9 additive owned bookmark references delivered; Part 10 private feedback delivered |
| Source versioning/amendments/supersession; pp.10,12 | 3–6 | Part 3 immutable versions and explicitly verified relationship APIs; legal dates separate from ingestion/verification, no automatic supersession |
| Swagger/OpenAPI; p.15 | 1 | Implemented at /docs and /openapi.json |
| React/Tailwind/FastAPI layered architecture; pp.3,16–18 | 1 | Implemented starter, modular monolith; TypeScript/Vite added |
| Restricted CORS/config/errors/request IDs/health (user additions) | 1–2 | Foundation retained; Part 2 credentialed CORS, DB/schema readiness and sanitized 503 added; AI-free liveness |
| Real browser connectivity/loading/error/retry (user additions) | 1 | Implemented; readiness endpoint checked, no fake answers/stats |
| Pinned dependencies/lockfiles/local setup (user additions) | 1 | requirements.lock and package-lock.json, PowerShell instructions |
| Source legitimacy/rights/provenance; pp.15,32 | 3–4,11 | Original three rights restrictions preserved; one PIB first-party narrative-text source reviewed under official terms, historical scope/attribution shown; append-only corrections |
| Security/JWT/TLS/rate limiting; pp.4,19,30 | 2,11–12 | Local loopback HTTP, JWT/cookie auth and durable throttling verified in Part 2; Part 11 practical regression/audit review and request bounds delivered; public TLS/deployment security remain later |
| Resource profiling/performance/OWASP review; p.30 | 4,11 | Part 4 sequential CPU latency and process memory measured; Part 5 GPU generation measured; Part 11 grouped cold/warm pipeline timings and security review recorded; throughput/production security deferred |
| Reproducible test set/BLEU/ROUGE/BERTScore; pp.30–31 | 4,11 | Part 11 new frozen 24-case pipeline set plus nine separately labeled controls across two freezes; agent-authored/source-reviewed, baseline retained 1/9 factual outputs; independent labels/calibration pending; no invented BLEU/ROUGE scores |
| Full report/demo/video/viva and public code; pp.30–31 | 12 | Technical README/setup/architecture/source/evaluation/security/release records maintained; formal college report/video/submission remain outside this implementation. Beginner/viva guides withdrawn; no public deployment claim |
| Eight-month multi-person roadmap; pp.28–30 | 1–12 | Adapted to user-directed numbered parts, solo pace, no deadline |
| GPU/translation/OCR/vector-scale/copyright/team risks; pp.31–32 | 3–12 | Local CPU fallback, quality flags, measured expansion, documented handover |
| Additional Indian languages, mobile, voice; pp.15,32 | Beyond 12 | Deferred; no implementation in baseline |
| Live feeds, legal advisory, multimodal, federated hosting, fine-tuning; p.32 | Beyond 12 | Deferred; no training or legal advice in baseline |

## Cross-cutting acceptance rules

User input and retrieved instructions are untrusted data. Future answering must preserve original passages, label translations, clarify ambiguous scheme/jurisdiction/date questions and abstain without support. Immutable source versions, explicit verified relationships and SQL-gated retrieval are implemented; Part 5 bounded structured output, initial numeric/exact-span checks, conservative clarification/abstention and source rechecks delivered; Part 6 limited final-language support checks and current-access history redaction delivered; exhaustive semantic/legal verification remains unavailable. Retrieval candidates and similarity cannot establish claim support. Publication dates, counts, evaluation results and trust values must remain evidence-based. See [maintainer state](docs/MAINTAINER.md) for continuation decisions.
