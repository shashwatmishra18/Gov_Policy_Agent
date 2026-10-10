# Practical security review — Part 11

Reviewed 2026-10-06 for the existing local Windows application. This is an implementation review with regression checks, not a penetration-test certificate or production approval. Private configuration, source eligibility, assessment snapshots and model pins are preserved.

Part 12 adds an internal container network, a loopback-only frontend port, fixed service addresses, non-root/read-only application containers, memory/PID limits and private file-based secrets. Existing Host/origin/cookie rules and request/worker bounds remain. Backup is offline; restore accepts only an empty isolated installation. These changes do not resolve the Python findings below. Image OS packages have not received an independent vulnerability assessment. Local HTTP is a trusted-laptop demonstration profile without production HTTPS or hostile-parser isolation. See [packaging verification](VERIFICATION.md) for checks actually executed.

## Evidenced fixes

Before the changes, regression requests with an unrelated Host and a 65,537-byte body both returned 200. [Request middleware](../backend/app/request_limits.py) now rejects unrelated/malformed/duplicate Host values and limits actual non-upload body streams to 65,536 bytes before JSON parsing. Missing or understated Content-Length cannot bypass the cap. The API allows loopback hosts and explicitly configured origin hosts; the private index allows loopback hosts only. The exact raw upload route retains its existing authenticated 50 MiB streaming limit. API responses add nosniff; protected originals already used it.

[Boundary tests](../tests/test_request_boundaries.py) cover malformed host-after-port paths, allowed hosts, declared/actual/chunked size boundaries, CORS errors and private-index authentication. [PostgreSQL upload tests](../tests/test_security_review_postgres.py) confirm the upload exemption, unsafe filename isolation, generated storage/download names, text/plain plus nosniff and traversal rejection. These address bounded request parsing; slow clients and hard process memory quotas remain deployment concerns.

## Boundaries inspected and checked

| Boundary | Existing implementation and evidence |
| --- | --- |
| Authentication and CSRF | Argon2id, signed HS256 access tokens, server roles/revocation, refresh rotation/replay rejection, logout, exact origins/CSRF and durable throttles; real PostgreSQL auth regressions |
| Private records | Composite owner FKs and server ownership checks for History/Saved/feedback; foreign IDs denied; retention cascades; browser two-user denial |
| Source changes | SQL rights/archive/extraction/provenance gates on search, publication, history, saved details, feedback and inspection; tests revoke sources and verify redaction without snapshot mutation |
| Uploads | Generated private keys, checksums, byte/time/page/text bounds and contained parser children; raw stream never trusts filename paths; protected preview/original tests |
| Rendering | React text interpolation for question, claim, filename/title and comment; no injected HTML renderer. Literal markup comment/browser check and protected download nosniff; this is not exhaustive XSS fuzzing |
| Untrusted instructions | Documents serialize as data; strict output schema, server-built excerpt handles and scope/provenance/support guards. Existing grounding tests reject control tokens; frozen instruction cases are recorded separately |
| URL/filesystem/tools | Source URL metadata is validated, not fetched by the backend. Model output cannot invoke tools, URLs or arbitrary paths. Local pinned models use offline loading; no user-selected model/config path |
| Leases and cancellation | Fenced ingestion/index work, retries, stale ownership tests and contained worker/model process cancellation; controlled service restarts keep one project owner |
| Exposure and logging | API/frontend/index/project Ollama bind loopback; index requires a private key; personal Ollama untouched. API access logging disabled, controlled errors omit prompts/secrets; raw local evaluation remains ignored/private |
| Snapshots and retention | Stored assessment immutable; no rescoring/backfill. Actual cleanup/cascade tests; before/after live snapshot digests and corpus counts unchanged |

The complete 143-test suite includes existing regressions for these boundaries; see [verification](VERIFICATION.md). Loopback restricts network access, but another process in the same Windows profile is trusted. Project Ollama itself has no application-user authentication. Local HTTP is not a public deployment design. OCR critical values, source rights and policy currency still require review. Malware scanning, OS parser sandboxing, hard RAM/VRAM quotas, public HTTPS/proxy timeouts, broad assistive-technology testing and independent security assessment remain unresolved.

## Dependency audit

[Sanitized dated audit record](dependency_audit_part11.json) preserves IDs, aliases, reported duplicates, fix versions and skipped-package limitations. Commands are in [SETUP](SETUP.md#frozen-evaluation-and-dependency-audit). Audits report known advisories, not proof that code is vulnerability-free; [pip-audit limitations](https://github.com/pypa/pip-audit) apply.

Compatible updates: PyJWT 2.12.1 → 2.15.0, pydantic-settings 2.13.1 → 2.14.2, pytest 9.0.2 → 9.0.3, installer pip 25.0.1 → 26.2; Vite 7.3.1 → 7.3.7 and its allowed esbuild dependency 0.27.7 → 0.28.2. Locks preserve other application pins. The [PyJWT advisory](https://github.com/jpadilla/pyjwt/security/advisories/GHSA-42vr-xj54-vc7v), [settings advisory](https://github.com/pydantic/pydantic-settings/security/advisories/GHSA-4xgf-cpjx-pc3j) and [Vite advisory](https://github.com/vitejs/vite/security/advisories/GHSA-p9ff-h696-f583) informed focused updates. Dependency check and full regression/build passed. npm audit changed from two affected packages to zero reported vulnerabilities.

Python audit changed from 58 reported entries/eight packages to **25 entries/four packages (16 unique package/advisory IDs)**. Duplicate aliases are not additional distinct defects. Remaining findings:

| Installed package | Unique IDs | Exposure assessment and unresolved work |
| --- | --- | --- |
| Chroma 1.5.9 | 4 | No public Chroma HTTP/RBAC or arbitrary embedding-model configuration endpoint is exposed. Local library/index only. No fixes reported by the tool; upstream/package review remains necessary |
| sentence-transformers 5.1.2 | 1 | Model class/config loading advisory; only trusted pinned offline encoder is accepted. Fix 5.6.0 requires separate compatibility/model evaluation, not silently replacing this baseline |
| Starlette 0.52.1 | 5 | Strict Host validation mitigates the reviewed [Host parsing issue](https://github.com/Kludex/starlette/security/advisories/GHSA-86qp-5c8j-p5mr). No StaticFiles, HTTPEndpoint or form parsing paths used. Other URL parsing risk remains; available 1.x fixes conflict with current FastAPI dependency bounds |
| Transformers 4.57.6 | 6 | No Trainer, untrusted checkpoint converter, user config, remote custom generation or chat-template save path. Pinned offline inference only. Some fixes require 5.x; other entries have no fix reported. Migration remains unverified |

The installed torch 2.10.0+cpu wheel was skipped by the PyPI matcher. A separate advisory-only query for normalized torch==2.10.0 reports two findings, [JIT script](https://github.com/advisories/GHSA-rrmf-rvhw-rf47) and [pt2 deserialization](https://osv.dev/vulnerability/PYSEC-2026-139). The app does not accept untrusted JIT/pt2 models and uses pinned safetensors, but these remain unresolved package findings. The normalized query is not certification of the exact CPU wheel. Affected paths being unused reduces exposure; it does not repair dependencies. Preserve trusted local model stores and follow the [PyTorch security policy](https://github.com/pytorch/pytorch/security/policy).

Configured database/test/JWT secret bytes and excluded runtime/model/corpus files are scanned against the public file set before release. Documentation links and referenced commands are checked. This scan cannot establish that every historical log or unknown secret is absent; private raw evaluation/log folders remain outside Git.
