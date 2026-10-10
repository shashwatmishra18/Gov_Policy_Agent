# Local setup

All root commands run from the repository directory in PowerShell. Prerequisites: Python 3.12, Node 22.12+ with npm, Git and PostgreSQL 18 with Server/Command Line Tools. Tested versions are in [verification](VERIFICATION.md). Use [official PostgreSQL Windows installation](https://www.postgresql.org/download/windows/); Stack Builder packages are unnecessary. Keep PostgreSQL on loopback port 5432.

## Dependencies

For a fresh clone only, create the environment; preserve an existing `.venv` and private `.env`:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend/requirements.lock
npm.cmd --prefix frontend ci
```

The existing development environment uses bundled Python 3.12.14; an independent installation is needed on another machine. Activation is unnecessary. `npm.cmd` avoids PowerShell npm.ps1 execution-policy issues.

## Database and administrator

Fresh installations only:

```powershell
.\.venv\Scripts\python.exe backend\manage.py configure
```

Enter the PostgreSQL administrator password at the hidden prompt. This creates private `.env` credentials for `gov_app/gov_policy` and disposable `gov_test/gov_policy_test`, verifies ownership and uses non-superuser roles. If it requests a service restart after setting loopback listening, run `Restart-Service postgresql-x64-18` in administrator PowerShell, then rerun configure. Do not provision again on an already configured installation or overwrite `.env` with example values.

Apply migrations for both fresh and existing application installations:

```powershell
.\.venv\Scripts\python.exe -m alembic -c backend/alembic.ini upgrade head
.\.venv\Scripts\python.exe -m alembic -c backend/alembic.ini current
```

Expected head: `0009_answer_feedback`. Upgrade is additive and repeatable; startup does not create tables. Downgrades remove data and are not a setup step.

Create the first administrator only when none exists:

```powershell
.\.venv\Scripts\python.exe backend\manage.py bootstrap-admin
```

The command prompts for identity and hidden password confirmation. Existing installations retain their administrator. Secrets stay in ignored `.env`; never include them in logs, screenshots or public files.

## Prepare the embedding model

Run explicitly once (network download from the pinned official Hugging Face revision):

```powershell
.\.venv\Scripts\python.exe backend\prepare_model.py
```

Expected output includes `intfloat/multilingual-e5-small`, revision `614241f622f53c4eeff9890bdc4f31cfecc418b3`, 384 dimensions and CPU configuration. The lock uses the official PyTorch CPU wheel index. No CUDA stack is required. Model files default to `%LOCALAPPDATA%\GovPolicyAgent\models`; subsequent API/model startup is offline and rejects an absent/mismatched preparation manifest. Downloading another revision requires a deliberate code/spec change and index rebuild.

## Prepare local generation

Install [official Ollama for Windows](https://docs.ollama.com/windows) if absent. Tested installation is the per-user `%LOCALAPPDATA%\Programs\Ollama\ollama.exe`, version 0.17.1. The worker requires that location and rejects another runtime version. Existing personal models/service on 11434 are preserved. From the root, explicitly prepare once:

```powershell
.\.venv\Scripts\python.exe backend\prepare_llm.py
```

This starts a temporary project-owned loopback server on 11435, downloads only `qwen3:4b-instruct-2507-q4_K_M` (about 2.5 GB) and the pinned Qwen tokenizer, then stops its process tree. Model/tag/digest/runtime/settings must match [llm_model.json](llm_model.json); unexpected changes fail rather than updating the record. Runtime startup is offline and does not pull weights. Files live in `%LOCALAPPDATA%\GovPolicyAgent\ollama`, separate from the personal Ollama cache. Stop the answer worker before preparation or evaluation; both use its exclusive owner lock. No cloud generation, CUDA Python installation or Stack Builder package is needed.

## Start

Terminal 1, root:

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000 --no-proxy-headers --no-access-log
```

Terminal 2, root:

```powershell
npm.cmd --prefix frontend run dev
```

Terminal 3, root:

```powershell
.\.venv\Scripts\python.exe backend\worker.py
```

Terminal 4, root:

```powershell
.\.venv\Scripts\python.exe backend\index.py serve
```

This loads one CPU model and owns Chroma under a Windows file lock, then starts a private loopback service on port 8011. Wait for Uvicorn startup (measured runtime load about 16 seconds). Do not start additional index owners or use reload/multiple workers. API startup does not load the model. The internal query endpoint requires a private derived key; use the authenticated API/UI instead.

Terminal 5, root:

```powershell
.\.venv\Scripts\python.exe backend\rag.py
```

Expected: `Local RAG worker ready; one pending job; project Ollama 127.0.0.1:11435`. It owns one private server/runner tree and processes durable PostgreSQL requests. Do not launch a second RAG worker or a manual server on 11435. Cancellation/timeouts replace this contained tree; Ctrl+C closes it. Default context/output are 4096/768 tokens, temperature 0, concurrency one. Trust is unavailable.

Use `http://127.0.0.1:5173/` consistently; `localhost` is a different origin. Admin uploads are at `/#admin`; protected retrieval is at `/#search`; local answers/history are at `/#ask`. Try “According to the 2025 PM-KISAN factsheet, what annual assistance and instalments are described?” or “2025 के पीएम किसान दस्तावेज़ के अनुसार: पीएम किसान में हर साल कितनी आर्थिक सहायता मिलती है और कितनी किस्तों में?” Select English/Hindi explicitly. Current entitlement questions abstain; ambiguous questions clarify. Sign in, enter a Hindi/English question and select Search passages. Filters match exact stored scheme/issuer/type; date bounds concern publication dates, with an explicit unknown-date choice. Inspect extracted source text from a result. Only admins can review/upload/rebuild or fetch original PDF/PNG. API docs: `http://127.0.0.1:8000/docs`; readiness: `/health/ready`. Ready checks DB/schema/auth, not index-service availability. Stop terminals with Ctrl+C.

## Storage and corpus operations

Durable originals default to `%LOCALAPPDATA%\GovPolicyAgent\data`, outside OneDrive. `GOV_DATA_DIR` can override this in private `.env`; model/vector directories are siblings of that data directory. Back up the database and originals together; Chroma is derived and rebuildable. To relocate, stop all services, copy storage, update the setting and verify original checksums. Paths must remain private and outside frontend assets.

Optional root commands:

```powershell
.\.venv\Scripts\python.exe backend\worker.py --once
.\.venv\Scripts\python.exe backend\worker.py --reconcile
.\.venv\Scripts\python.exe backend\corpus.py --download
.\.venv\Scripts\python.exe backend\corpus.py --import
.\.venv\Scripts\python.exe backend\index.py rebuild
.\.venv\Scripts\python.exe backend\index.py status
```

Worker reconcile removes only generated unreferenced originals older than 24 hours and temporary files older than one hour. Corpus download verifies [manifest](corpus_manifest.json) hashes; changed sources require review. Import requires an existing active first admin, reuses versions on repeat and records the manifest's explicit audited review for the PIB factsheet only. Inspect extraction before rebuild. The existing three sources remain restricted. Source terms/scope are in [SOURCES.md](SOURCES.md).

Rebuild prints a queued generation UUID; the running index service processes it. Repeated pending requests reuse the job. Status prints source exclusion reasons and durable progress; `ready` means a completed SQL generation, not a live-service probe. Failed jobs below three attempts can retry through the admin API; exhausted jobs require a new rebuild.

Stop Terminal 4 before these maintenance commands (each requires exclusive vector ownership):

```powershell
.\.venv\Scripts\python.exe backend\index.py once
.\.venv\Scripts\python.exe backend\index.py reconcile
.\.venv\Scripts\python.exe backend\evaluate_retrieval.py
```

`once` claims one queued/expired job. Index reconcile removes orphan vector IDs; missing SQL-referenced vectors clear the active pointer and mark failure, requiring retry/rebuild. Old generation SQL provenance is retained; automatic old-collection garbage collection is deferred. Evaluation checks the eligible real source and writes ignored `runtime/retrieval-results.json`; it never substitutes fixtures. Restart `index.py serve` afterwards.

For read-only real answer evaluation, keep the index service running and stop only Terminal 5:

```powershell
.\.venv\Scripts\python.exe backend\evaluate_answers.py
```

This uses the existing real-source development questions, isolated injection text and actual local cancellation/timeout/offline recovery. It writes ignored `runtime/answer-results.json` with quoted corpus text. Inspect every claim manually; schema validity is not factual accuracy. Restart `backend\rag.py` afterwards. Source/model weights, private histories and raw prompts stay outside Git. Terminal answer records expire after 30 days during worker startup/hourly cleanup; database backups retain their own copies.

## Checks

Root commands; prepare the model first. Tests reset only the dedicated test database and use temporary vector/storage collections:

```powershell
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider
npm.cmd --prefix frontend run typecheck
npm.cmd --prefix frontend run build
```

If old Windows pytest temporary directories are inaccessible, supply `--basetemp=runtime/pytest-check-NEW` with a new unused directory name. Database tests fail when private test prerequisites are missing; they do not substitute SQLite.

| Symptom | Check |
| --- | --- |
| Ready returns 503 | PostgreSQL service, private settings and `upgrade head` |
| Queued job | Worker running, schema current, document not archived |
| Partial/needs_ocr | Queue a separate OCR revision below; inspect quality and review every OCR page |
| Upload 409 | Same bytes with conflicting metadata; inspect the existing version |
| Upload 413/422 | Actual stream size or parser/file validation limits |
| Inspection 401/403 | Session, admin role and approved 127.0.0.1 origin |
| Missing/changed original | Restore matching storage/database backup |
| Search 503/busy | Start the prepared single-owner service; retry after a batch finishes |
| Model missing/mismatched | Run explicit preparation; preserve the pinned spec |
| Index owner lock | Stop the other index service before offline maintenance |
| No results | Check eligibility, exact filters, dates and heuristic cutoff; no answer is asserted |
| Review changed after indexing | Rebuild; new review must be included in the active snapshot |
| Query 422 | Shorten to 2–2000 characters and at most 512 actual prefixed tokens |

Answer errors: worker 503 → start Terminal 5; busy → wait/cancel the existing request; `llm_not_prepared` → stop worker and run preparation; digest/runtime mismatch → inspect the pinned record, do not accept a changed model silently. `generation_truncated`/`grounding_validation_failed` publish no answer: shorten the question and inspect source coverage. Source change errors require a fresh reviewed/indexed snapshot and a new question. Longer context/output/model settings require fresh measurements.

## Claim citations and support checks

The same `upgrade head` command applies additive `0005_citations`; no account provisioning, data reset or second model is required. Existing answers stay `not_evaluated`. New Ask results expose numbered source evidence buttons and a citation panel. Open cited source text to inspect the actual referenced physical page/span; publication/effective dates and historical applicability remain distinct from support.

For read-only claim-support evaluation, keep Terminal 4 running and stop Terminal 5 first. From project root:

```powershell
.\.venv\Scripts\python.exe backend\evaluate_support.py
```

This uses [support_devset.json](support_devset.json), writes ignored `runtime/support-results.json`, and never imports synthetic mutations. It measures false accepts/rejects, exact provenance, candidate retention and latency with the existing pinned Qwen. Restart `backend\rag.py` afterwards. Labels are implementing-agent development review, not independent human or held-out validation.

`verification_unavailable`/`verification_timeout` publish no answer; check the worker and pinned project Ollama, then submit a new request. `verification_invalid_output` is an explicit error with no fallback. `unsupported`/`conflicting` candidates are omitted with a reason; zero retained claims abstain. Large complete context yields `insufficient_context` without truncation. Revoked history shows metadata and a withheld notice; restore eligibility through an evidence-backed review and rebuild for new retrieval. Do not change original snapshots or weaken guards. Historical citations retain the old review: a changed review remains withheld even when a new positive review is added.


## English/Hindi OCR and multilingual queries

Use the tested trusted Windows package; an admin/UAC action may be required on a fresh machine:

```powershell
winget install --id UB-Mannheim.TesseractOCR --exact --version 5.4.0.20240606 --source winget --accept-source-agreements --accept-package-agreements
.\.venv\Scripts\python.exe backend\prepare_ocr.py
```

Preparation detects PATH, standard per-user/Program Files folders and Tesseract registry paths. It verifies the tested engine version, downloads pinned official `tessdata_fast` English/Hindi data and checks both SHA256 hashes. Expected: `tesseract v5.4.0.20240606`, language list `eng`, `hin`. Private `%LOCALAPPDATA%\GovPolicyAgent\ocr\prepared.json` records the actual executable path/hash and pack pins. No Poppler or Python OCR wrapper is needed. Preparation is explicit; worker startup never installs or downloads. Stop the ingestion worker before preparation.

After `upgrade head`, the existing Terminal 3 worker processes initial extraction and OCR jobs under one owner lock. Admin → select a PDF → **OCR extraction and review** → Queue OCR revision. Inspect each physical page, use Compare original page, and record acceptance/rejection with a reason and critical-value check. Readable OCR always requires review. Low-quality/failed pages cannot be accepted. Retry is capped at three attempts; digital/legible published pages are reused. Cancellation fences the child. Raw text editing is deferred; do not guess corrections.

Optional local-owner commands, root PowerShell; replace the value with the selected Admin version reference:

```powershell
$versionId = 'replace-with-version-uuid-from-admin'
.\.venv\Scripts\python.exe backend\ocr_manage.py queue $versionId
.\.venv\Scripts\python.exe backend\ocr_manage.py status $versionId
.\.venv\Scripts\python.exe backend\worker.py --once
```

Stop the running worker before `--once`; do not create a duplicate owner. Use Admin for review/retry/cancel. After every required page is accepted, perform the separate evidence-backed rights/applicability review if needed, then explicitly rebuild via Admin Search or `backend\index.py rebuild` from root. A rebuild cannot clear rights restrictions. Old index/citations keep their recorded extraction; neither OCR failure nor pending review switches the active index.

OCR defaults: 300 DPI, maximum 12 million rendered pixels, 30 seconds/page, grayscale and PDF-declared rotation only, one child/Tesseract tree, one OpenMP thread. Optional private settings `GOV_OCR_DPI` (150–300), `GOV_OCR_MAX_PIXELS` (1–12 million), `GOV_OCR_PAGE_SECONDS` (1–60) apply to **newly queued revisions**. Existing revisions retain their recorded settings. Oversized pages report `ocr_pixel_limit`; low quality remains excluded. The tested one-hour orphan cleanup is `worker.py --reconcile`; current page temporary files are removed immediately on success/error/timeout/cancel. No hard RAM quota or automatic deskew is claimed.

Search/Ask accept English, Hindi, Hinglish and mixed input. Original question is preserved; recorded retrieval normalization handles NFC, whitespace, Devanagari digits and bounded common phrases/aliases. Original-query ranking stays primary; changed-query hits are compared and used only when original retrieval is empty. No general retrieval improvement is claimed. Short scheme names yield uncertain detection. Ask defaults to the profile preference (Hinglish preference maps to Hindi); explicit English/Hindi selection wins. Current-policy questions still abstain. Examples: `2025 PM Kisan factsheet ke anusaar saalana kitna paisa aur kitni kiste?` and `aaj PM Kisan me paatra hun?`.

Read-only development measurements (stop Terminal 4 and Terminal 5; keep personal Ollama untouched):

```powershell
.\.venv\Scripts\python.exe backend\evaluate_language.py
.\.venv\Scripts\python.exe backend\evaluate_ocr.py
```

The language runner owns the existing E5/vector store and project Ollama exclusively; it does not write answers or import sources. Baseline uses the recorded Part 6 prompt/retrieval with shared current guards; the changed branch uses normalization and complete-excerpt selection. OCR runner generates four isolated self-authored scans with installed Windows Nirmala.ttc; no fixtures enter the application corpus. Results containing quoted/transcribed text remain ignored under `runtime`. Restart Terminals 4/5 afterward. Measurement scope and limitations are in [VERIFICATION.md](VERIFICATION.md).

## Evidence-quality panel

The existing root `upgrade head` command adds the nullable assessment column without backfilling old answers. Restart only the existing API/answer worker after an upgrade; keep one owner per service. No model preparation, new downloads or database provisioning is required. New Ask results and opened history records show the same English/Hindi panel. Expand Methods, counts and source scope to inspect the saved evidence audit. Legacy answers show not evaluated; revoked sources hide saved values. Formula and availability rules: [TRUST_SCORING](TRUST_SCORING.md).

## Existing installation upgrade

Part 9 adds only the bookmark migration; keep the existing private configuration, accounts, corpus and model stores. Apply the migration using the existing command above, then restart the existing API owner. Frontend startup remains `npm.cmd --prefix frontend run dev`; no new service, model, package or provisioning step is required. Inspect listening ports/process owners before restarting a missing service; use one owner per API/frontend/worker/index/RAG service. A stopped frontend produces `ERR_CONNECTION_REFUSED`; run the existing dev command and confirm Vite reports `http://127.0.0.1:5173/`.

## Feedback and analytics

Existing startup commands are unchanged. After the additive migration, restart only the API if it is already running. Feedback is available on accessible answered/partial details in Ask, History and Saved; it requires no model service. Admin Analytics is at `/#analytics`, with 1/7/30-day UTC windows. Feedback comments are private plain text, maximum 500 Unicode characters (the browser may conservatively count supplementary characters as two). No analytics package or synthetic live feedback seed is required.

## Frozen evaluation and dependency audit

Part 11 has no migration or model preparation. Install the updated backend lock/frontend lock using the existing commands, then restart only the existing API/index/frontend owners. Non-upload API/index bodies have a 65,536-byte actual-stream cap; raw admin uploads retain the 50 MiB limit. Hosts must be loopback or, for the API, explicitly configured origin hostnames. Keep private configuration unchanged.

For evaluation, keep Terminal 4 (index) running. Wait for zero queued/processing answers, stop only Terminal 5 (project RAG) with Ctrl+C, and keep personal Ollama untouched. From project-root PowerShell:

```powershell
.\.venv\Scripts\python.exe backend\evaluate_frozen.py --check
.\.venv\Scripts\python.exe backend\evaluate_frozen.py --run-id local-review-v1
.\.venv\Scripts\python.exe backend\evaluate_frozen.py --check --set evaluation_installment_controls_v1
.\.venv\Scripts\python.exe backend\evaluate_frozen.py --set evaluation_installment_controls_v1 --run-id local-installment-v1
.\.venv\Scripts\python.exe backend\rag.py
```

Expected checks: `part11-agent-v1 30` and `part11-installment-controls-v1 3`, followed by recorded SHA256 values. Runs refuse an existing output directory; choose a new ID for each repetition. Success writes private outputs and an allowlisted summary under ignored `runtime/evaluation/<run-id>` and verifies application records unchanged. Source/gold/development hash mismatch is a failure, not permission to alter the freeze. An owner-lock error means another project RAG/evaluation process is running; inspect it instead of starting a duplicate. Results vary with hardware and model execution; do not overwrite the committed original baseline. See [EVALUATION](EVALUATION.md) for denominators and independent review.

Optional reproducible audit tool setup, project root (separate environment; no application/model upgrades):

```powershell
.\.venv\Scripts\python.exe -m venv runtime\audit-env
.\runtime\audit-env\Scripts\python.exe -m pip install pip-audit==2.10.1
.\runtime\audit-env\Scripts\python.exe -m pip_audit --path .venv\Lib\site-packages --format json --output runtime\pip-audit.json
npm.cmd --prefix frontend audit --json
.\.venv\Scripts\python.exe -m pip check
```

Audits may return a nonzero exit code when advisories exist. Network/advisory-service failure is not a clean audit. The CPU torch wheel may be skipped; the recorded supplemental normalized query and unresolved package findings are in [SECURITY_REVIEW](SECURITY_REVIEW.md). Tested installer pip version was 26.2. Keep raw audit logs private; publish only reviewed aggregate records.

## Native service controller (Windows)

Existing manual terminals remain supported. From project root, after dependencies, migrations and explicit model/OCR preparation:

```powershell
.\scripts\native.ps1 preflight
.\scripts\native.ps1 status
.\scripts\native.ps1 start
.\scripts\native.ps1 status
.\scripts\native.ps1 stop
```

Preflight checks configuration, schema, dependencies and pinned preparation manifests without loading models. Start creates ignored supervisors/logs under `runtime/native-services`; repeated starts skip owners. Status distinguishes managed processes from occupied ports/file locks owned elsewhere; it is process status, not HTTP readiness. Check System status too. Stop verifies supervisor PID, creation time and command before closing its contained tree. Unmanaged terminal processes, native PostgreSQL and personal Ollama are untouched. Stop manual owners with Ctrl+C in their own terminal. Inspect logs privately.

For a smaller session: `.\scripts\native.ps1 start -Services api,frontend,worker`. Start `index,rag` only with sufficient memory and no packaged model owner. Never run native and container model owners concurrently, especially with reused stores. Cancel/wait for Ask/uploads before shutdown/sleep. Jobs cannot run during sleep; after wake inspect status, start only missing owners and allow durable leases to recover. No database reset is a recovery step.

## Separate Docker installation

Docker Desktop Linux/WSL2 containers are optional. This is an independent local installation; native PostgreSQL/accounts/documents are preserved. Use sufficient free RAM/disk for images and one model owner; measured limits are in VERIFICATION. Base versions and application dependencies are pinned; Debian repositories are not snapshot-pinned and the backend lock has no wheel hashes. Setup does not promise byte-identical images.

Project-root PowerShell, fresh package setup (existing private secrets are preserved):

```powershell
.\.venv\Scripts\python.exe backend\package_setup.py
.\.venv\Scripts\python.exe backend\package_context.py
docker compose config --quiet
docker compose build api
docker compose build frontend
docker compose --profile tools build backup
docker compose up -d postgres init
docker compose run --rm migrate
docker compose up -d api worker frontend
docker compose run --rm api admin
```

The last command needs an interactive terminal; it uses existing hidden-input first-admin provisioning with no default accounts. Random credentials live in ignored `runtime/docker-secrets`, separate from native `.env`. Protect them with Windows permissions; preserve them with existing volumes. Regenerating a secret file does not change an existing PostgreSQL role. [Settings example](../docker/settings.example) lists nonsecret overrides; an ignored environment file can be passed with `--env-file` on every Compose command. Native `.env` is excluded from images and its values are not automatically injected.

Open `http://127.0.0.1:8080/`. Only the loopback production frontend is published; database/index/Ollama have no host ports. Nginx forwards root API routes on the same origin, preserving `/auth` cookie paths and origin/Host checks. Use 127.0.0.1 for login. API health is required for UI; Search/Ask also need models and reviewed indexed evidence. Images contain no models, policy PDFs, databases or private configuration. Regenerate the allowlisted context after source edits, then rebuild.

### Explicit models and corpus

Initialize volumes first. A new machine explicitly prepares the same pins (network required here):

```powershell
docker compose --profile prepare run --rm prepare prepare-embedding
docker compose --profile prepare run --rm prepare prepare-llm
docker compose --profile prepare run --rm prepare prepare-ocr
docker compose --profile models up -d index rag
```

CPU is the packaged default. Existing bounds/deadlines remain; slow inference can fail safely. Optional GPU needs compatible NVIDIA drivers/WSL2 support. Stop the owned RAG service before probing/recreating it:

Measured CPU Ask timed out at 62.17 seconds. Two real GPU samples ran but were blocked by invalid judge evidence references; accepted factual Docker answers remain unverified. Use the existing native Windows setup for the measured answer baseline. Do not increase deadlines or relax verification solely to make a demonstration succeed. Linux Hindi OCR requires transcript review even when the engine and language-pack checks pass.

```powershell
docker compose --profile models stop rag
docker run --rm --gpus all --entrypoint nvidia-smi gov-policy-backend:part12
docker compose -f compose.yaml -f docker/compose.gpu.yaml --profile models up -d index rag
```

A successful GPU probe alone does not establish inference success. See VERIFICATION for actual results. No paid hosting is configured.

To reuse prepared E5/Qwen, stop native model owners, set `$env:GOV_EXISTING_ROOT` to the private `GovPolicyAgent` parent of `data` containing `models` and `ollama`, and add `-f docker/compose.reuse.yaml` after `-f compose.yaml` on model commands. Stores mount read-only with separate package locks. This does not import native originals, vectors, configuration or accounts. Windows OCR executable manifests cannot run on Linux; prepare its Linux manifest. Matching existing `eng/hin` pack files are reused. GPU plus reuse uses all three override files. Never silently copy the native corpus or repull changed pins.

Existing pinned language packs can also be reused explicitly, without copying the Windows executable manifest:

```powershell
docker compose --profile prepare run --rm -v "${env:GOV_EXISTING_ROOT}/ocr:/reuse-ocr:ro" prepare prepare-ocr --packs-source /reuse-ocr
```

Both pack checksums must match. The new Linux executable/version/hash is recorded separately in the package OCR volume.

Use [source links/disclosures](SOURCES.md) to obtain documents privately. Admin uploads, inspects exact extraction/page quality, verifies origin, records a separate rights/applicability review, reviews OCR critical values, then explicitly queues rebuilding. A fresh package contains no policy corpus. Self-authored test fixtures are not government evidence or accuracy measurements.

### Operation and backup/restore

```powershell
docker compose --profile models ps
docker compose logs --tail 50 api worker index rag
docker compose --profile models restart api worker index rag
docker compose --profile models down
```

Logs are private local diagnosis. Ordinary `down` preserves volumes. **Adding `--volumes` permanently removes this package's private data; it is not routine shutdown or sleep recovery.** After wake inspect Docker/owners, then start missing services with the same project/environment/overrides. File locks and durable leases remain authoritative; expired interrupted jobs recover or reach the existing bounded attempt limit.

Back up only an offline package; stop all its application services while PostgreSQL remains running:

```powershell
docker compose --profile models stop frontend api worker index rag
$env:GOV_BACKUP_DIR = "$PWD/runtime/package-backups/backup-01"
docker compose --profile tools run --rm backup backup
```

The private bundle contains a PostgreSQL 18 custom dump, immutable originals, schema/model pins and SHA256 checksums. Accounts/history/feedback/OCR text/reviews are private. Keep installation secrets separately protected; role/JWT secrets are not in the dump. Models/language packs are preparation assets, vectors are rebuildable, and both are excluded. The tool refuses another application DB connection or an existing bundle. A failed bundle without a manifest is incomplete.

Restore only into a **new empty isolated project** with the same protected secret files and selected backup directory. Never overwrite native or existing package data:

```powershell
docker compose -p gov-restored up -d postgres init
docker compose -p gov-restored --profile tools run --rm backup restore
docker compose -p gov-restored run --rm migrate
docker compose -p gov-restored up -d api worker frontend
```

Stop the original frontend first or set a separate `GOV_WEB_PORT`. Restore checks schema emptiness, empty originals, checksums, pins and archive paths before writing. A mid-restore failure needs diagnosis in that isolated target, not another restore over nonempty records. Prepare/reuse models for that project, start its single index/RAG owner, and queue a new index rebuild. SQL provenance/answer snapshots remain; verify original downloads and private history. Retention still applies. Unset `GOV_BACKUP_DIR` afterward. Isolated rehearsal results are in VERIFICATION.


## Optional free native HTTPS demo

### Private local account recovery

If you forget the native account email or password, use a real interactive PowerShell terminal in the project root:

```powershell
.\.venv\Scripts\python.exe backend\manage.py recover-account
```

This trusted laptop-owner command displays account identities **only locally**. Select your account by number; the unique bootstrap administrator is labelled as a candidate, not automatically selected. Confirm with `RESET`, then enter a new 12–128 character password twice at hidden prompts. Echo fallback is refused. Do not paste the local account list or credentials into chat. Successful output: `Password recovered; all existing sessions revoked. Account identity and role preserved.` All access/refresh sessions for that account are revoked in the same transaction as the password replacement. Other accounts, roles, documents and configuration are unchanged; inactive accounts are refused. Login is serialized with recovery so a concurrent old-password login cannot leave a surviving session.

If no listed account is yours, select `N` to privately provision a new **ordinary** account with your own email, username and hidden password. Duplicate identities fail without replacing an account. Enter cancels. No recovery password is accepted through arguments, stored in a script or supplied by default. Public registration and password recovery remain unavailable. Sign in at the current printed HTTPS URL using the selected registered email and new password; old tabs may use an obsolete tunnel hostname. Authentication throttling remains enabled.

Prepared on 2026-10-11 with the tunnel stopped. Subsequent explicitly authorized public HTTPS/auth/Ask checks passed; see the [activation record](VERIFICATION.md#explicit-public-https-activation-2026-10-11). This uses the existing native database/models/source restrictions. It is a small invited demonstration, not a production hosting release. No paid plan, card trial, purchased domain or Cloudflare account is required for [Quick Tunnel](https://developers.cloudflare.com/tunnel/get-started/quick-tunnels/).

Use project-root PowerShell. Existing owners/configuration/data are preserved:

```powershell
.\scripts\native.ps1 preflight
.\scripts\native.ps1 start
.\scripts\demo.ps1 prepare
.\scripts\demo.ps1 check
```

`prepare` builds a separate frontend in ignored `runtime/demo-frontend`, with relative same-origin API URLs and demo-only navigation. It reuses/downloads the official Windows x64 cloudflared **2026.10.0**, verifying SHA256 `86aee4017b26625cee8484c113558f48effa4cd47f7aa05fcf425604e5d2b23c` against the [official release](https://github.com/cloudflare/cloudflared/releases/tag/2026.10.0). It never starts a tunnel. Native `.env`, Vite build/configuration and model stores are untouched. `check` requires existing healthy ingestion/index/answer owners and pinned project Ollama. If a personal `.cloudflared/config.yml` or `config.yaml` exists, it refuses rather than modifying that configuration.

Optional local-only browser check:

```powershell
.\scripts\demo.ps1 local-check
# Open http://127.0.0.1:8765/ in a browser; this is HTTP with local-only cookies.
# In a second project-root terminal:
.\scripts\demo.ps1 stop
.\scripts\demo.ps1 status
```

Sign in with the registered **email** of an existing active native account. A username or an account from the separate Docker/QA installation cannot substitute for that native account. Administrator login is allowed, but administration routes stay private. Existing signed-in sessions redirect Login to Ask. Pre-provision an **ordinary** demonstration account using the native Register page privately. Public registration, administration, analytics and diagnostics are blocked. No default account/password is provided. Avoid administrator credentials and personal information in the public demonstration; authentication still protects private History/Saved/feedback. Search requires login too.

**Next command when intentionally opening the public demo:**

```powershell
.\scripts\demo.ps1 start
```

Keep that foreground terminal open. It creates an accountless Quick Tunnel to **only `http://127.0.0.1:8765`**, waits up to 60 seconds for a valid generated HTTPS hostname, then starts the built frontend/restricted API with exact Host/origin and Secure/HttpOnly/SameSite=Strict refresh cookies. It never exposes native 8000/5173, PostgreSQL, project/personal Ollama, index IPC, private files, metrics or development diagnostics. Connector metrics are loopback-only on 20249. The application entry closes on a failed start. Child processes are owned/contained; stop closes the connector first and leaves native services/data intact.

Open the printed HTTPS URL, sign in again, then verify Search, a historical English/Hindi Ask, exact citation inspection, assessment, Saved and feedback from that external URL before sharing it. Browser-to-Cloudflare HTTPS and the real proxy/Host/cookie exchange have **not** been demonstrated in this readiness task. A local simulated-HTTPS test is not external TLS proof. Outbound network restrictions can still prevent connection; inspect ignored `runtime/demo-control` logs privately. Do not paste logs/tokens into public issues.

Shutdown with **Ctrl+C** in its terminal, or from another project-root terminal:

```powershell
.\scripts\demo.ps1 stop
.\scripts\demo.ps1 status
```

Wait for the owning terminal to finish and status to show stopped. The laptop must stay awake, connected and running the native services. Sleep/network loss closes availability. URL is temporary/random and changes after restart, so redistribute it and sign in at the new hostname. No uptime SLA; 200 concurrent in-flight requests produce 429 when exceeded; SSE is unsupported (this app polls). These are provider limits, not model concurrency: the app still permits one pending answer job, with conservative shared-proxy authentication throttling. Use only a few invited visitors. Cloudflare terminates TLS and processes application traffic; this is not end-to-end encryption bypassing the provider. No router port forwarding, firewall relaxation or private service publication is needed. Known security/dependency and language limits remain in [security review](SECURITY_REVIEW.md) and [verification](VERIFICATION.md).
