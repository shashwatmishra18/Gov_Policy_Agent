# Multilingual Government Policy Assistant

GOV-CS-028 is a B.Tech student project for exploring document-grounded government policy question answering in English, Hindi and Hinglish. The current application provides authentication, document ingestion, multilingual passage retrieval and local English/Hindi answers from reviewed historical sources.

## Implemented features

- Registration, login, rotating sessions, language preference and server-enforced user/admin roles.
- Admin PDF/UTF-8 TXT upload, immutable document versions, checksum-based deduplication and source metadata.
- Separate durable ingestion worker with bounded retries, lease recovery and atomic result publication.
- Physical PDF pages, extracted text spans, provisional chunks, protected original download/page preview and archive controls.
- PostgreSQL migrations, health endpoints and tests using an isolated PostgreSQL database.
- Audited source eligibility reviews, token-aware exact-span chunks, persistent Chroma generations and recoverable indexing jobs.
- Versioned English/Hindi OCR for flagged PDF pages, protected original comparison and append-only admin decisions.
- Protected English/Hindi/Hinglish Search with filters, source-page text inspection, historical-status notices and measured retrieval timings.

- Protected Ask with bounded local Ollama generation, validated claim/excerpt references, clarification/abstention, cancellation and private query history.
- Stable per-claim citations with original version/page/span inspection, separate provenance/support states and current-access checks.
- English/Hindi evidence-quality panels with factual citation coverage and versioned source/check audit details.
- Responsive Ask/Search/History/Saved/Account navigation, protected answer details and persistent private answer bookmarks.
- Private helpful/not-helpful feedback with optional fixed reasons and plain-text comments; update/removal on accessible factual answers.
- Admin-only aggregate analytics with explicit UTC windows, outcome/language counts, recorded latency, feedback participation and processing counts.
- Frozen local evaluation with separate development controls, exact provenance checks and private raw outputs; bounded API/index requests and a dated security review.
- Separate local Compose packaging, production frontend routing, private volumes, explicit provisioning and offline backup/empty-target restore; native ownership scripts preserve manual Windows operation.

## Stack

React, TypeScript, Vite and Tailwind CSS; FastAPI, SQLAlchemy, psycopg and Alembic; PostgreSQL; PyMuPDF; Sentence-Transformers with multilingual E5-small, CPU PyTorch and Chroma; Tesseract English/Hindi OCR; local Ollama Qwen3 4B Q4_K_M; Argon2id and JWT authentication. Dependencies are pinned in the backend lock and frontend package-lock.

## Setup and usage

See [local setup](docs/SETUP.md) for dependencies, private database configuration, migrations, startup and checks. Python 3.12, Node 22.12+ and PostgreSQL 18 are the native baseline.

Native Windows operation uses the existing terminals or `scripts/native.ps1 preflight/start/status/stop`; open `http://127.0.0.1:5173/`. The separate Docker installation serves built React through Nginx at `http://127.0.0.1:8080/`, with private PostgreSQL, ingestion, index and RAG services. It has independent accounts/storage and requires explicit model/corpus preparation. Only the frontend loopback port is published. See [setup](docs/SETUP.md) for exact commands, model reuse, shutdown and backup/restore, and [verification](docs/VERIFICATION.md) for tested modes and remaining gaps.

Sign in, then use Search for exact passages or Ask for dated historical-source questions. History/Saved are private and expire after 30 days; saving cannot bypass source revocation. Answer details contain citations, evidence-quality information and optional private feedback. Admin Analytics shows retained aggregates rather than private question/comment listings. Account selects English/Hindi UI (Hinglish maps to Hindi). Admin uploads, reviews extraction/rights and explicitly queues indexing. System status is in the footer; native API documentation is at `http://127.0.0.1:8000/docs`, packaged documentation at `http://127.0.0.1:8080/docs`.

An optional [free native HTTPS demo](docs/SETUP.md#optional-free-native-https-demo) uses a separately built same-origin entry and Cloudflare Quick Tunnel. Preparation leaves the tunnel stopped; explicit startup is required. Only protected ordinary-user application routes are exposed, with registration/admin/diagnostics blocked. The laptop must stay awake and connected; the temporary URL changes on restart. Native English factual output and partial Hindi output were rechecked with exact citations; external HTTPS/Secure-cookie routing also passed the separately authorized public smoke checks.

## Hardware and measured evaluation

Measured on Windows 11, i5-13500HX, about 15.7 GiB usable RAM and RTX 4050 with 6 GiB VRAM. E5 runs on CPU with two threads; Qwen uses one bounded runtime. Docker adds VM/image overhead; available memory, other workloads and CPU/GPU mode affect latency. Inspect owners/resources before starting models and keep sufficient disk for pinned runtime images plus private model stores. [Evaluation timings](docs/EVALUATION.md) separate cold/warm/no-generation samples; they are not throughput guarantees.

Docker packaging is operationally verified for ingestion, retrieval, private account features and backup/restore. Accepted factual Qwen answers in Docker remain unverified: the CPU sample timed out; two GPU samples failed the unchanged evidence-reference guard. GPU loading alone is not answer verification. Native Windows remains the supported answer baseline. Linux Hindi OCR produced a pending-review transcript rather than an exact match. See the dated verification record for measurements and test scope.

Part 11's agent-authored/source-reviewed freeze remains unchanged: gold-span hit@5 **9/9**, factual retention **1/9 (partial)**, behavioral matches **16/24**, final citation validity **1/1**, and **nine separate controls rejected**. These one-source results are not broad accuracy or precision@5. Independent review and calibration remain unavailable; same-model support and [unresolved Python advisories](docs/SECURITY_REVIEW.md) remain limitations.

## Current limitations

Claim support uses deterministic scope/value guards and a bounded heuristic judge using the same Qwen model as generation. This is not independent fact verification or complete semantic/legal interpretation. Pre-Part-6 answers remain not_evaluated; current source revocation withholds historical answer/excerpt content without rewriting private snapshots. Overall and partial scores remain unavailable. Citation coverage is measured; other dimensions expose evidence and explicit unavailable reasons. Old evidence-quality snapshots are not fabricated or reassessed. Flagged PDF pages support bounded English/Hindi OCR with mandatory review and versioned extraction. Hindi output can contain language errors or hit the bounded output limit; failures publish no policy answer. Retrieval similarity is relevance, not correctness or current entitlement advice. A 0.78 cosine-similarity cutoff is a development heuristic, not calibrated abstention. Unreadable/unreviewed OCR remains excluded; source rights still require separate approval. Uploads have size/time/page/text limits but no malware scanner, OS parser sandbox or hard memory quota. Native operation defaults to local development HTTP. An optional restricted HTTPS demo entry is prepared; external HTTPS/cookie smoke checks passed after explicit activation; this is not production hosting.

The local corpus contains four PDFs across three schemes: one reviewed historical PIB factsheet is indexed into nine token-aware passages; three original local-reference PDFs remain excluded. Permitted scope covers attributed PIB narrative text, excluding third-party graphics and linked-source content. Original PDFs, extracted corpus text, models, vectors, secrets and runtime data are excluded from Git. The small source-checked development set is not a held-out benchmark; see [recorded measurements](docs/VERIFICATION.md).

## Project records

- [Architecture](docs/ARCHITECTURE.md) and [API conventions](docs/API.md)
- [Maintainer state and roadmap](docs/MAINTAINER.md)
- [Evidence-quality contract](docs/TRUST_SCORING.md)
- [Recorded verification](docs/VERIFICATION.md)
- [Frozen evaluation and its limitations](docs/EVALUATION.md) and [practical security review](docs/SECURITY_REVIEW.md)
- [Sources and licensing disclosures](docs/SOURCES.md) and [corpus manifest](docs/corpus_manifest.json)
- [Proposal requirement mapping](REQUIREMENTS_MATRIX.md)
