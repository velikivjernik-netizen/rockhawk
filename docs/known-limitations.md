# Known limitations

- **Not legal advice.** Outputs are drafts for a licensed attorney. Privilege, liability, and strategy calls stay with the human.
- **OCR is not included.** Image-only PDFs extract as empty pages and therefore **Not found**.
- **Page mapping for DOCX/TXT** is chunk-based (or form-feed). PDF pages follow the file’s page tree.
- **Mock AI** is a conservative lexical extractor. It will miss some clauses a large model would catch, by design.
- **openai_compatible** sends page text off-box. That is a data-governance decision, not a default.
- **Embeddings** shipped here are toy hashes so SQLite demos work. They are not a production retrieval model.
- **OIDC** returns 501 until issuer and client id are configured and a token exchange is implemented against your IdP.
- **No MinIO daemon** is started; object bytes live on a Compose volume. Swap `STORAGE_DIR` for an S3-compatible client if you need it.
- **Playwright** expects a running UI; it is not executed inside `docker compose up`.
- **Scale.** The worker is a single pop-loop. Large productions should shard queues and add OCR, true pgvector indexes, and WORM audit.

The Origin reference commit was not available to this publisher. Behavior matches the stated acceptance criteria; pixel-level identity with that private tree is not claimed.
