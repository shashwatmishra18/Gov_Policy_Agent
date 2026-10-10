# Architecture

The packaged Nginx upstream resolves the private API service through Docker DNS with a shared upstream zone and a five-second cache. This avoids a stale container address after API replacement; the browser uses same-origin relative API URLs and the original Host/Origin are preserved. Login throttles persist in PostgreSQL across restart/restore; repeated verification logins can legitimately return 429. Wait for the existing window rather than clearing records or weakening the limit.

## Local packaging and process ownership

[Compose](../compose.yaml) defines an independent installation with private PostgreSQL 18 volumes and one API, ingestion worker, index and RAG owner. A production React/Nginx frontend alone publishes `127.0.0.1:8080`. It proxies root API paths on the same origin, retaining the existing `/auth` cookie path, CSRF/exact-origin and strict Host checks. Inside an internal network, the API/RAG use `http://index:8011` and SQL uses `postgres`; Ollama remains loopback inside its owning RAG container. Native defaults remain Windows loopback; container addresses require explicit `container_local` settings and fixed service names.

Initialization owns volume permissions, migration is a controlled one-shot dependency, API health checks schema/auth configuration, worker health checks a recent polling heartbeat, and index health requires a loaded offline encoder plus current SQL schema. RAG health checks worker heartbeat and pinned local Ollama version. Healthy API does not mean a corpus/index exists or that a model answer will finish. Index/RAG and preparation use separate profiles; setup never downloads models implicitly.

[Owned processes](../backend/app/processes.py) retain Windows kill-on-close Job Objects. Linux creates a private session supervised by [parent-death containment](../backend/process_guard.py); timeout/cancellation closes that process group, including parser/Ollama descendants. Container init reaps children; named-volume file locks serialize model/index/ingestion owners across container recreation. Existing deadlines, leases, attempt limits and fenced SQL publication remain unchanged. These are lifecycle/resource bounds, not a hostile-code sandbox; process groups alone cannot stop a malicious program deliberately escaping its session. Docker adds bounded memory/PIDs, while native child memory remains unbounded.

[Native operations](../backend/operate.py) use Windows PID, creation timestamp and exact supervisor-command verification. Status never adopts an unmanaged service, repeated starts skip ports/locks, and stop closes only a matching [project supervisor](../backend/service_owner.py). PostgreSQL and personal Ollama remain outside its ownership. Native and container locks are separate; an operator must prevent concurrent owners when reusing read-only model stores. Sleep suspends work; expired durable jobs recover after restart rather than continuing during sleep.

Build inputs are copied by an explicit [source allowlist](../backend/package_context.py) into ignored runtime context, then filtered by [.dockerignore](../.dockerignore). Private native configuration, original uploads, model weights, caches, database and frozen raw outputs never enter an image. Backend application dependencies/base versions and Tesseract source checksum are pinned; apt repositories and wheels lack full content locks. OCR manifests record platform-specific executable hash/version and the same pinned official English/Hindi language packs. [Ollama's pinned official image](https://github.com/ollama/ollama/blob/v0.17.1/Dockerfile) supplies its runtime libraries; GPU exposure is an optional override, separate from CPU verification.

[Offline backup](../docker/backup.py) uses PostgreSQL 18 tools and rejects active application connections. A private checksummed bundle stores SQL records and immutable originals together after all writers stop. It excludes preparation assets/rebuildable vectors and records schema/model pins. Restore accepts only an empty separate package database and empty original directory, checks paths/hashes/pins, then restores records and storage. Installation secrets are separately protected. Existing SQL extraction/citation/assessment provenance remains; a fresh vector generation is explicitly rebuilt after restore. A failed restoration must be diagnosed in that isolated target; this is not an in-place database replacement tool.

Part 11 adds [strict Host and actual-stream request bounds](../backend/app/request_limits.py) to API/private index before JSON parsing (64 KiB; exact raw upload path retains its existing stream limit). The API permits loopback/configured origin hostnames; native index permits loopback only, packaged index additionally permits its fixed private service name. Packaging adds no schema. [Frozen evaluation](EVALUATION.md) runs the existing pipeline with a SELECT-only database engine, source locks rolled back, private raw outputs and explicit safe aggregate fields; it verifies live table digests unchanged and never publishes history/feedback/bookmarks. Existing pins and guards remain unchanged; [security record](SECURITY_REVIEW.md) separates mitigations from unresolved upstream findings.

One React frontend calls a modular FastAPI application. PostgreSQL stores authentication, source metadata, exact passages and durable jobs. Separate ingestion, single-owner indexing and answer-worker processes handle parsing, embeddings and generation. Originals are private local files; no public static mount exists.

```mermaid
flowchart LR
  UI[React frontend] --> API[FastAPI]
  API --> DB[(PostgreSQL)]
  API --> FILES[Private originals]
  DB --> WORKER[Ingestion worker]
  FILES --> PARSER[Parser child]
  WORKER --> PARSER
  WORKER --> DB
  API --> INDEX[Private loopback index service]
  DB --> INDEX
  INDEX --> MODEL[Offline pinned E5-small CPU]
  INDEX --> VECTOR[(Persistent Chroma)]
  DB --> RAG[Single-owner answer worker]
  RAG --> INDEX
  RAG --> LLM[Contained loopback Ollama / Qwen3 4B]
  RAG --> DB
```

## Authentication

Argon2id password hashes; HS256 access JWTs with required claims and a ten-minute default lifetime. Protected requests also check live user/session records, so role/status/revocation are database-authoritative. Refresh tokens are opaque values stored as SHA256 digests; rotation row-locks sessions and replay revokes them. Default absolute expiry is seven days, with at most 256 consumed digests per session.

Frontend access tokens stay in memory. Refresh cookies are host-only, HttpOnly, Strict and `/auth` scoped; production requires Secure/HTTPS. Credentialed CORS uses exact origins and mutations check Origin plus CSRF header. Web Locks serialize cross-tab refresh; unsupported browsers may require login after a race. Persistent account/IP throttling counts all attempts. Uvicorn proxy headers remain disabled in local setup.

## Data model

UUID keys, foreign keys, constraints and timezone-aware timestamps are defined in [auth models](../backend/app/models.py) and [document models](../backend/app/document_models.py).

| Tables | Responsibility |
| --- | --- |
| users, auth_sessions, auth_throttles | Accounts, revocation/rotation and durable login limits |
| schemes, documents | Logical source grouping, identity and archive state |
| document_versions | Immutable original identifiers/metadata, unique corpus checksum, version number and verification |
| version_relationships | Explicitly verified amendments/supersession with evidence and scope |
| extracted_pages, chunks | Physical-page text, exact offsets, flags and replaceable chunk profile |
| ingestion_jobs | One persisted job per version, state, attempt count, progress and lease ownership |
| eligibility_reviews | Append-only evidence/reason/scope/reviewer decisions, separate from immutable originals |
| index_generations, index_state | Pinned model/chunk spec, reviewed source snapshot, durable lease/progress and atomic active pointer |
| index_passages | Generation-scoped exact page/text spans; old provisional chunks remain intact |
| answer_runs | Owned questions, terminal results, immutable grounding/model snapshots and sanitized errors |
| answer_worker | Singleton heartbeat for request availability |
| answer_claims, claim_citations | Ordered candidate/retention assessments, stable citation IDs, exact quote/version/page offsets and model/review snapshots |

Alembic revisions `0001_auth`, `0002_documents`, `0003_retrieval` and additive `0004_answers`/`0005_citations` are explicit. Startup does not create tables. PostgreSQL triggers protect original-version fields and forbid eligibility-review update/delete. Corrections append a new reviewed decision.

## Ingestion

Admin authorization precedes streaming. Upload enforces actual byte limits and validates content in a child parser, then publishes a generated no-overwrite original and commits version/job metadata. Same bytes/same metadata reuse the version; conflicting metadata returns 409. Grace-period orphan reconciliation handles interrupted file/database publication.

Workers claim with `FOR UPDATE SKIP LOCKED`, owner UUID and expiring lease. Heartbeats extend ownership; stale-worker fencing prevents late result publication. Pages/chunks and terminal state commit atomically. Expired processing jobs can recover up to three attempts; controlled retry is limited to failed jobs below the cap.

PDF text preserves physical page numbers and exact `get_text('text', sort=False)` output. UTF-8 TXT uses character spans without invented PDF pages. Chunk profile `unicode-char-v1:1200:120` is provisional; detected labels are heuristic and long paragraphs carry continuation flags. Low-text pages are OCR-pending; mixed PDFs are partial. Original PNG preview and download require admin authorization and integrity checks.

Limits: 50 MiB stream, 60-second upload read deadline, 30-second default parser deadline, 500 pages and 2,000,000 extracted characters. Parser children are not an OS sandbox and have no hard memory quota. No malware scan is available; table layout and encoding need review. API liveness is independent of DB/worker/AI; readiness requires current DB/schema and authentication.

## Retrieval

The [encoder](../backend/app/embedding.py) explicitly prepares a pinned safetensors model outside Git, loads offline without remote code, and supplies all embeddings to Chroma. Hindi/English queries share the same normalized 384-dimensional space. Query/passage prefixes and special tokens count toward the 512-token maximum. New chunks target 448 tokens with 48-token overlap and heuristic newline/section boundaries; exact half-open offsets, continuation flags and original physical pages survive. No reparse of immutable originals is needed.

[Eligibility](../backend/app/eligibility.py) requires a latest audited verified review, recorded reuse scope, completed extraction, active document and no explicit superseding relationship. Historical/unknown applicability remains visible. Partial/OCR-pending sources are excluded. A changed review blocks the old index snapshot immediately, even if still positive; rebuild to include it. Archive/rejection is rechecked from SQL after vector work. Regular users inspect eligible indexed text only; original/PNG routes remain admin-only because permitted narrative scope excludes graphics.

[Index runtime](../backend/app/vector_index.py) creates one collection per generation with an exact model revision/dimension/normalization/metric/chunk spec. It checks actual cosine configuration and disables Chroma's embedding function. Stable passage UUIDs derive from generation/page/span; batches of eight use idempotent upserts. SQL leases last 180 seconds with heartbeats and stale-owner fencing, capped at three attempts. Only exact vector-ID coverage plus current source-review checks can atomically publish the active pointer. Failure preserves the previous ready generation. Reconciliation removes orphan IDs and invalidates missing-vector generations; historical SQL/collections are retained pending explicit garbage-collection design.

[Single-owner service](../backend/index.py) holds a Windows file lock before model/Chroma loading. Worker and query operations share one nonblocking runtime lock; busy queries return 503 rather than overlap. It binds 127.0.0.1:8011 with a private HMAC-derived internal key, no public schema or CORS. The ordinary [search API](../backend/app/search_api.py) checks live auth/CSRF, applies persistent IP throttling (50 requests per 15 minutes by default) and uses a 20-second IPC timeout. Model loading never occurs during API startup. CPU uses two Torch threads; GPU inference is not configured.

Search accepts 2–2000 characters, rejects actual prefixed input over 512 tokens, returns at most ten passages, and supports exact scheme/issuer/type and publication-date filters. Unknown dates are explicitly included/excluded when date filtering. SQL eligibility precedes Chroma filtering, and candidate retrieval covers the bounded corpus (100 versions/20,000 passages) so excluded hits cannot consume the requested count. This small-corpus strategy is not a scalable search benchmark. Every returned text is checked against the stored source-page span. Similarity >=0.78 is a labeled uncalibrated relevance heuristic; it cannot establish claim support or entitlement.

Limited claim-support checks are described below; complete semantic/legal interpretation, OCR correction and saved-answer/feedback workflows remain deferred; the evidence-quality audit is described below. See [maintainer state](MAINTAINER.md).

## Local answers

[Ask API](../backend/app/ask_api.py) accepts owned, CSRF-protected requests. PostgreSQL advisory locking plus a partial unique index allow one queued/processing request globally, without an unbounded inference queue. A 15-second worker heartbeat gates submissions. History is owner-filtered; another user's UUID returns 404. Records retain question/language/filters, validated claims, exact source/version/page/span/review snapshots, index generation, model digest/settings, prompt/schema revisions, timings and sanitized errors. Terminal records older than 30 days are removed at worker startup and hourly while active; backups have separate retention. Raw generation prompts/output and thinking are neither logged nor stored. Structured candidate claim text and assessments are retained privately for audit, including rejected candidates; their factual text is not returned in API explanations. Disable API access logs to avoid identity-bearing URLs.

[Worker](../backend/app/answer_worker.py) uses replaceable [retrieval/generation interfaces](../backend/app/rag_engine.py). Retrieval calls the existing keyed service, never a second E5 model. Conservative keyword scope checks distinguish historical questions, ambiguous requests and unsupported current-policy advice; these are not comprehensive intent classification. The model also evaluates answerability. Empty/insufficient evidence makes no generation call; service failures remain errors.

The complete raw Qwen control template, system/schema, escaped untrusted question/excerpts and output reserve use the pinned **LLM** tokenizer. Whole lower-ranked passages are removed until prompt + 768 output + 64 safety tokens fit 4096. No excerpt is silently clipped; omissions are disclosed. Ollama truncation/context shifting are disabled. Actual prompt counts must equal preflight counts; unexpected thinking, truncation or oversized responses fail. Structured output permits at most one concise claim; only final validated results appear in the UI. Repair is bounded to one additional generation and never uses model memory as fallback.

[Grounding](../backend/app/grounding.py) supplies exact excerpt handles. The model selects IDs/handles; the server reconstructs original quote text and page offsets, preventing altered PDF whitespace. Extra fields, invented IDs/excerpts, non-exact spans, basic unsupported numbers/currencies/months and one explicit negation case are rejected. These checks do **not** prove semantic entailment, numeric association, exhaustive conditions, translation quality or complete date interpretation. Broad page excerpts can contain unrelated values. High-signal instruction paragraphs are omitted and Qwen control tokens escaped, but this is not a comprehensive prompt-injection defense. The separate Part 6 method adds conservative support checks; it does not establish complete semantic entailment. Trust stays null.

Sources are rechecked after inference and row-locked through publication against live SQL eligibility, latest review, ready generation and original page spans. Changed sources produce an error, never a new answer from stale evidence. Later history views apply current access/provenance checks under source locks. A revoked/changed source withholds the entire answer and all excerpt text, while preserving its private SQL snapshot. Referenced old-generation SQL remains inspectable after index rebuild when the original review remains eligible.

[Contained Ollama](../backend/app/ollama_local.py) uses an exclusive project lock and Windows kill-on-close job containing server/runner descendants at 127.0.0.1:11435, a separate private model store, cloud disabled, one loaded model/parallel request/queue slot. The worker has a 120-second processing deadline and 120-second queued TTL; generation HTTP read/load limits are 60 seconds. Cancellation/timeouts cancel the HTTP task and replace the complete owned process tree. A fresh worker marks interrupted processing jobs as errors rather than regenerating silently. These are execution/token bounds, not hard RAM/VRAM quotas. The personal Ollama service/cache is untouched.

## Claim support and citation access

[Provenance](../backend/app/citations.py) matches each quote and passage to authoritative extracted-page text, original version and half-open offsets. Surrounding complete paragraphs clarify conditions; over-budget contexts are rejected rather than clipped. Missing dates/clauses stay null; detected section labels remain heuristic. UUID5 claim IDs use run/order/text; citation IDs use claim/order/passage. [Additive tables](../backend/app/citation_models.py) store exact candidate text, retention, controlled reason, method/revision and original/model/review snapshots. Existing answer JSON is never migrated/reassessed; old views derive presentation IDs and show `not_evaluated` without writes. No reassessment API exists.

[Support](../backend/app/support.py) checks final displayed English/Hindi text. Lexical guards associate currency/value/frequency, Indian/Devanagari numbers, land-holding/SMF categories, explicit negation, historical scope and selected same-scheme annual conflicts. Remaining questions go to the existing Qwen model with exact quote/context, bounded strict JSON and controlled reason codes. This is a same-generator heuristic, not independent evidence, legal verification or complete named-entity/condition reasoning. Similarity never sets support. Outcomes: `supported_by_check`, `unsupported`, `conflicting`, `insufficient_context`, `not_evaluated`.

Judge prompt + 256 output + 64 safety tokens must fit the same 4096 context. One judge call/candidate, 30-second deadline; no judge repair/fallback. Production output remains one claim; internal evaluation permits up to five candidates. Missing/invalid/timed-out verification fails closed. Source gates run before/after support and under row locks through final publication; explicit relationship creation takes the same version locks. The answer is rebuilt only from retained checked claims; none retained means abstention, mixed retention means partial. No unchecked streaming.

Owned citation text routes validate current eligibility/review and the original page span independently of the active index pointer. Normal users can inspect approved narrative text; originals/PNG remain admin-only. History redaction is deliberately conservative if any recorded source becomes unavailable/revoked. Already delivered client text cannot be withdrawn; fresh reads and failed inspection refresh current access. Thirty-day answer deletion cascades its claim/citation records. These snapshots have no edit API, not DB-wide immutability guarantees against privileged manual SQL.


## Versioned extraction and multilingual context

[OCR models](../backend/app/ocr_models.py) are additive: `extraction_revisions` are durable leased jobs/specs, `extraction_pages` are immutable per-physical-page attempt artifacts, `extraction_reviews` are append-only decisions, and `extraction_state` selects a completed reviewed revision. Existing `extracted_pages`, originals, initial ingestion records and provisional chunks are preserved. Successful digital pages are copied exactly into a revision; only initial `needs_ocr` pages are rendered. Retrying appends failed/low-quality attempts and reuses successful artifacts. Initial parsing refuses to replace already published pages.

The single-owner [worker](../backend/worker.py) uses row-locked 90-second OCR leases, fresh owner UUIDs and fenced page publication. A page commits independently so expired jobs resume. Three attempts maximum, explicit failure retry, archive/cancel checks during heartbeat. [Contained renderer](../backend/ocr_child.py) waits for Windows Job assignment before spawning Tesseract. One grayscale/PDF-rotated page, bounded DPI/pixels, one OpenMP thread and a whole-child deadline. Kill-on-close contains renderer/Tesseract descendants even if the parent dies; normal finally cleanup removes its generated directory, and explicit one-hour reconciliation handles crash orphans. This is containment and output limits, not an OS security sandbox or hard memory quota.

Quality policy `manual-all-ocr-v1`: at least 30 characters/five words, mean word signal >=70, <=25% word signals below 50; every remaining OCR page still needs manual original comparison/acceptance. Empty/unreadable pages stay excluded. Signals/boxes measure engine behavior, never factual confidence or measured error. Raw OCR is never silently corrected; deskew, manual text corrections and correction revisions are deferred.

[Artifact resolver](../backend/app/extraction_artifacts.py) selects exact generation/citation revision, including legacy null IDs. E5's token-aware chunks are stored in `index_passages.extraction_page_id` with generation revision snapshots; original physical-page FKs remain stable. A failed/new unreviewed revision does not alter the prior ready pointer/index. Review completion alone does not rebuild or clear source rights. Rejection blocks the affected revision immediately, with normal rights/archive/supersession checks still applied. Historical answer JSON is not rewritten or reassessed.

[Language normalization](../backend/app/language.py) retains the exact question and transparent bounded transformations. E5 retrieves both original and changed queries when needed; original ranking remains primary and an empty original result falls back to normalized retrieval. The paired development measurement found original gold coverage already complete, so no normalization-based reranking is claimed. There is no paid translator or additional model. Response language comes from explicit choice/profile, never uncertain input detection. Complete annual-benefit excerpts are selected only for narrow Hindi annual questions; cumulative/national disbursement chunks are omitted with a context notice. English and other Hindi questions retain the original whole-passage context ordering. For the narrow digital annual-benefit pattern, final Hindi wording is constructed from the exact positive source phrase and its recipient, annual amount and instalment count; no family category is invented. A family-specific question receives partial scope. OCR excerpts skip this construction. A second exact digital paragraph pattern constructs only chatbot development-support answers, retaining EKstep foundation and Bhashini verbatim. Both complete final Hindi lines still go through unchanged support checks; no general translation quality is claimed. Selection is not support: final Hindi/English candidates still need exact provenance, unchanged restrictive guards and the same bounded judge. A single constrained scope/condition regeneration shares the existing two-generation cap; rejected candidates are retained privately and never displayed as policy explanations.

## Evidence-quality snapshots

The answer worker calculates [evidence-quality-v1](../backend/app/evidence_quality.py) after source locking/revalidation and claim persistence in the same publication transaction. Nullable `answer_runs.evidence_quality` JSONB carries schema/method IDs, time, exact references and counts; additive `0007_evidence_quality` does not backfill. No inference/resource/guard changes. Coverage is the sole numerical measurement; the remaining dimensions, full aggregate and partial index stay null for the documented reasons. Conflicts and currency limitations are separate from coverage. [Contract](TRUST_SCORING.md) specifies formulas and bounds.

Owned detail reads copy the saved assessment only after current source/citation gates. Revoked/withheld views contain no assessment values, references, counts or historical dates. History summaries omit assessments; opening a record evaluates current availability without rejudging. Historical null snapshots stay not evaluated. Thirty-day deletion removes the assessment with its answer. No edit/reassessment API or privileged-SQL immutability guarantee is added. The shared frontend panel localizes English/Hindi and expands methods/evidence separately.

## Private saved answers

[Answer models](../backend/app/answer_models.py) add `saved_answers(user_id, run_id, created_at)` and a composite FK to the unique answer owner/id pair. The key prevents duplicates and mismatched owners; `ON DELETE CASCADE` follows existing answer retention. [Migration](../backend/migrations/versions/0008_saved_answers.py) adds constraints/table without copying or modifying historical answer snapshots.

[Ask API](../backend/app/ask_api.py) authenticates every list/detail/write and filters by owner. CSRF/exact-origin checks cover PUT/DELETE; CORS permits these verbs only for configured origins. Save and remove lock the parent row before membership changes; duplicate insert is a no-op. Eligibility reuses the protected `view` flow with current source/citation checks. Saved summaries contain question/state/date/availability only, with no answer, excerpt or assessment copies. A revoked source leaves an unavailable bookmark until unsaved/expired; opened details redact as History does. No inference occurs while bookmarking or opening records.

[Application shell](../frontend/src/AuthApp.tsx) separates Ask, Search, History, Saved and Account, with admin routing still authorized by the server. [Library](../frontend/src/AnswerLibrary.tsx) and [record page](../frontend/src/RecordPage.tsx) use owner-protected APIs and retain page navigation. [Shared detail](../frontend/src/AnswerDetail.tsx) renders the same answer/evidence in Ask and saved/history records; the existing assessment component retains explicit unavailable dimensions. Profile-driven UI translation does not translate stored policy statements or source names.

## Private feedback and aggregate analytics

[Feedback routes](../backend/app/feedback_api.py) reuse owned answers and current citation/source access gates. [AnswerFeedback](../backend/app/answer_models.py) stores only a current vote, optional fixed reason/plain comment and timestamps. The composite owner/run key prevents duplicate or foreign membership; parent row locks serialize PUT/DELETE. Additive [migration 0009](../backend/migrations/versions/0009_answer_feedback.py) adds no historical ratings or assessment changes. Answer deletion cascades feedback; voting never renews retention. Source revocation suppresses feedback in protected details and denies every feedback endpoint. Comments are never model input, raw HTML, history summaries or analytics output.

[Analytics](../backend/app/analytics_api.py) enforces the existing live admin dependency and performs a fixed number of grouped SQL queries in a separate read-only repeatable-read transaction, with existing pool/statement bounds. It exposes aggregate counts only, not individual questions, answers or comments. Windows and denominators are explicit; null means unavailable. No new inference, telemetry service, tracking table or analytics infrastructure is involved. UI feedback and analytics are shared English/Hindi components; assessment copy distinguishes descriptive votes from unavailable numerical evidence quality.
