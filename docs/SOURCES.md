# Sources and licensing disclosures

The local GOV-CS-028 proposal (34 physical pages) supplied project requirements. It is excluded from Git and is not chatbot evidence. [Requirement mapping](../REQUIREMENTS_MATRIX.md) preserves proposal references; accuracy, novelty, publication and production-scale aspirations are not established results. No authorship history or blanket project license is inferred here.

## Local document corpus

[corpus_manifest.json](corpus_manifest.json) retains original URLs, issuers, titles, SHA256 hashes, byte/page counts, retrieval date, verification notes and per-source rights scope.

| Source | Pages | Recorded status |
| --- | --- | --- |
| PM-KISAN operational guidelines | 12 | Digital extraction completed |
| PMJDY mission document | 40 | Partial; one low-text page |
| PMAY-U 2.0 guidelines | 112 | Partial; five low-text pages |
| PIB Research Unit: 20th Instalment of PM-KISAN (2025-08-01) | 7 | Completed; audited historical narrative-text scope; nine indexed passages |

Retrieved/inspected 2026-10-05. Official origins and covers/title/issuer were checked; exact publication/effective dates remain unknown where not established. Historical snapshots are not current entitlement advice. SHA256 verifies bytes, not authenticity or legal status.

The original three remain local-reference-only; reproduction permissions are not obtained. [PM-KISAN copyright policy](https://www.pmkisan.gov.in/CopyrightPolicy.aspx) and [PMAY copyright policy](https://pmay-urban.gov.in/copyright) require reproduction permission. PMJDY's [official accessibility page](https://www.pmjdy.gov.in/accessibility) lists a copyright policy whose text was unavailable during review. Public availability is not a blanket reuse license. Originals and extracted corpus text are not redistributed in Git.

The new [PIB factsheet](https://static.pib.gov.in/WriteReadData/specificdocs/documents/2025/aug/doc202581597201.pdf) was inspected across all seven physical pages. Its cover establishes the publication date; effective/current applicability is not inferred. SHA256: `cb739585b7794b79dc61a164fcd744de4fc5bc1de75b1402db387b03eac40df8`. [PIB copyright terms](https://www.pib.gov.in/content/3604_2_CopyrightPolicy.aspx?lang=1&reg=3), reviewed 2026-10-05, permit first-party featured material reproduction without prior permission subject to accuracy, non-misleading use and prominent source acknowledgment; third-party material is excluded. Intended-use review permits exact attributed PIB-authored narrative excerpts only, with title/issuer/source URL shown on every result. It does not clear photographs/graphics or reproduce content from linked third-party sources. Normal-user inspection is extracted text only. This is one eligible historical source, not blanket clearance for the earlier PM-KISAN guidelines or current entitlement advice.

## Embedding baseline

Official model-card comparison informed selection; only E5 was downloaded and measured. [Multilingual MiniLM-L12-v2](https://huggingface.co/sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2) is Apache-2.0, supports 50 languages, produces 384 dimensions and has a 128-token Sentence-Transformers limit. [Multilingual E5-small](https://huggingface.co/intfloat/multilingual-e5-small/tree/614241f622f53c4eeff9890bdc4f31cfecc418b3) is MIT, supports 100 languages including Hindi/English, produces 384 dimensions and uses a 512-token limit with mandatory `query: ` / `passage: ` prefixes for retrieval. E5's retrieval training and larger source context fit this task. This is a documented suitability comparison, not a head-to-head quality or resource benchmark.

Pinned E5 revision: `614241f622f53c4eeff9890bdc4f31cfecc418b3`. Selected licenses/cards remain in the downloaded cache; models and weights are excluded from Git. Installed Sentence-Transformers 5.1.2, Transformers 4.57.6, CPU Torch 2.10.0+cpu and Chroma 1.5.9 were tested together. See [Sentence-Transformers loading/encoding](https://sbert.net/docs/package_reference/sentence_transformer/model.html), [Chroma clients](https://docs.trychroma.com/docs/run-chroma/client-server) and the [official CPU wheel index](https://download.pytorch.org/whl/cpu).

## Dependency references

PyMuPDF is AGPL/commercial dual licensed; use and redistribution must respect the applicable license. Proprietary redistribution needs separate review. See [licensing](https://pymupdf.io/licensing), [installation](https://pymupdf.readthedocs.io/en/latest/installation.html), [page extraction](https://pymupdf.readthedocs.io/en/latest/page.html) and [document API](https://pymupdf.readthedocs.io/en/latest/document.html).

Implementation references: [PostgreSQL SELECT/SKIP LOCKED](https://www.postgresql.org/docs/18/sql-select.html), [SQLAlchemy psycopg](https://docs.sqlalchemy.org/en/20/dialects/postgresql.html#psycopg), [psycopg installation](https://www.psycopg.org/psycopg3/docs/basic/install.html), [Alembic](https://alembic.sqlalchemy.org/en/latest/tutorial.html), [pwdlib](https://frankie567.github.io/pwdlib/reference/pwdlib/) and [PyJWT](https://pyjwt.readthedocs.io/en/latest/usage.html). Dependency license/notice files remain with installed distributions; this documentation does not replace them.

## Local generation model

Selected [official Ollama Qwen3 4B Instruct 2507 Q4_K_M tag](https://ollama.com/library/qwen3:4b-instruct-2507-q4_K_M), one 4.0B candidate, about 2.5 GB. The [official Qwen model card](https://huggingface.co/Qwen/Qwen3-4B-Instruct-2507) identifies Apache-2.0 licensing and non-thinking instruction generation; [Qwen language documentation](https://qwenlm.github.io/blog/qwen3/) includes Hindi/English. [Structured outputs](https://docs.ollama.com/capabilities/structured-outputs) constrain JSON, not factual correctness. No quality or hardware comparison with a second candidate is claimed.

Actual runtime/tag/digest/quantization/tokenizer revision/settings are in [llm_model.json](llm_model.json). Only the Qwen tokenizer/config are downloaded from Hugging Face; quantized weights come from the official Ollama tag. Weights/license artifacts remain in the private downloaded cache and are not redistributed in Git. The card's larger native context is not the tested configuration: this project uses 4096 tokens. GPU feasibility was verified locally rather than inferred from a model-card claim.

Implementation references: [official Windows distribution](https://docs.ollama.com/windows), [generation API](https://docs.ollama.com/api/generate), [resource controls and GPU inspection](https://docs.ollama.com/faq), and pinned Ollama 0.17.1 [environment options](https://github.com/ollama/ollama/blob/v0.17.1/envconfig/config.go) / [generation request handling](https://github.com/ollama/ollama/blob/v0.17.1/server/routes.go). No paid API or remote generation is used.

## Claim citation policy (Part 6)

No corpus, reuse permission, source provenance status or extraction flag changed in Part 6. Citations reuse the existing attributed narrative-text scope. Original PDF/PNG access remains admin-only. Stable historical references preserve recorded title/issuer/URL/date/version/page/span/review; unknown legal dates and clauses are not invented. Current archive, rejection, supersession, changed review or missing provenance blocks fresh history excerpt access, while the private audit snapshot remains stored under normal retention. Index rebuild by itself preserves citation access. Automated support labels do not establish legal effect or independently verify government claims.


## OCR dependencies and test material

Tested Windows engine: trusted upstream-referenced [UB-Mannheim build](https://github.com/UB-Mannheim/tesseract/wiki), Tesseract `5.4.0.20240606`, Leptonica `1.84.1`. This is a compatibility pin, not a claim to be the newest release. [Official installation guidance](https://tesseract-ocr.github.io/tessdoc/Installation.html) identifies the builder and Apache-2.0 licensing. Installer SHA256: `c885fff6998e0608ba4bb8ab51436e1c6775c2bafc2559a19b423e18678b60c9`; actual tesseract.exe SHA256: `babb405f4366b480d02cd8ff2bac8d497170f6c1711ce6f3d5d8bf0fb7fa6ed9`. Executable path/version are recorded privately by preparation.

Official [tessdata_fast](https://github.com/tesseract-ocr/tessdata_fast/tree/87416418657359cb625c412a48b6e1d6d41c29bd) revision `87416418657359cb625c412a48b6e1d6d41c29bd`, [Apache-2.0 license](https://github.com/tesseract-ocr/tessdata_fast/blob/87416418657359cb625c412a48b6e1d6d41c29bd/LICENSE). English SHA256: `7d4322bd2a7749724879683fc3912cb542f19906c83bcc1a52132556427170b2`; Hindi: `4c73ffc59d497c186b19d1e90f5d721d678ea6b2e277b719bee4e2af12271825`. [Official data guidance](https://tesseract-ocr.github.io/tessdoc/Data-Files.html) requires LSTM OEM 1 for fast packs. Engine/pack artifacts stay outside Git. Original Tesseract TXT and word-box TSV outputs are enabled explicitly; no wrapper import is treated as OCR verification.

[Self-authored scan transcripts/generator](../tests/ocr_fixtures.py) are synthetic test-only material, never government evidence or application-corpus imports. Runtime generation uses installed Windows Nirmala.ttc and PyMuPDF; no font/PDF/image/model binaries are redistributed. CER/WER against these transcripts do not measure real-government-corpus accuracy. Private local OCR of the earlier restricted files does not clear reproduction permissions; all three restricted source reviews remain unchanged. Successful OCR requires separate transcription review and existing source rights/applicability approval before retrieval.

## Local packaging references

[Dockerfiles and tools](../docker/) use official versioned Python, Node, Nginx, PostgreSQL and Ollama images. Upstream notices/licenses remain in those distributions; no authorship history is inferred from using them. Linux Tesseract is built from [official 5.4.0 source](https://github.com/tesseract-ocr/tesseract/releases/tag/5.4.0) with a measured archive checksum and the same pinned Apache-2.0 `tessdata_fast` packs. Images/Git contain no policy corpus, model weights or private original uploads. Isolated packaging tests use self-authored fictional TXT/scans; successful routing/inference on those fixtures is operational verification, excluded from the frozen policy evaluation.

The copied runtime has its upstream [Tesseract Apache-2.0 license](../docker/licenses/tesseract-LICENSE) and [Ollama MIT license](../docker/licenses/ollama-LICENSE) in `/app/docker/licenses`. These are unmodified license texts from the pinned upstream tags, not a license or authorship statement for this project. GPU runtime libraries supplied by the official Ollama distribution may have separate NVIDIA/vendor terms; free local use does not mean every dependency is open source. No images, model assets or private corpus were publicly published in Part 12.
