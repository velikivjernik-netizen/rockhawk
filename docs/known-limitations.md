# Known limitations

- **Not legal advice.** Outputs are drafts for a licensed attorney. Privilege, liability, and strategy calls stay with the human.
- **Image OCR** uses Tesseract in the Compose image (`tesseract-ocr`). If Tesseract is missing (SQLite laptop without the package), JPG/PNG still upload; searchable text is filename/EXIF only and the page is marked low-confidence.
- **Image-only PDFs** still extract empty pages unless they already contain a text layer. That is separate from JPG/PNG OCR.
- **Legacy .ppt** is best-effort: the original is stored; recovered strings may be incomplete. Prefer PPTX.
- **.msg** uses `extract-msg`. Corrupt Outlook files are stored with a parse-failure note rather than rejected.
- **HTML/XML/EML** extraction is visible text only (scripts/styles stripped). Markup is never treated as model instructions.
- **Page mapping:** PDF and PPTX use file pages/slides; spreadsheets use one section per sheet; DOCX/TXT/HTML/XML/EML are chunked.
- **Mock AI** is a conservative lexical extractor. It will miss some clauses a large model would catch, by design.
- **openai_compatible** sends page text off-box. That is a data-governance decision, not a default.
- **Embeddings** shipped here are toy hashes so SQLite demos work. They are not a production retrieval model.
- **OIDC** returns 501 until issuer and client id are configured and a token exchange is implemented against your IdP.
- **No MinIO daemon** is started; object bytes live on a Compose volume. Swap `STORAGE_DIR` for an S3-compatible client if you need it.
- **Playwright** expects a running UI; it is not executed inside `docker compose up`.
- **Scale.** The worker is a single pop-loop. Large productions should shard queues and add OCR, true pgvector indexes, and WORM audit.

The Origin reference commit was not available to this publisher. Behavior matches the stated acceptance criteria; pixel-level identity with that private tree is not claimed.
