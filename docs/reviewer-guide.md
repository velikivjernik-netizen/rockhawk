# Reviewer guide

RockHawk organizes a matter’s documents into a **review table**. Each row is a document. Each column is a typed question the model tries to answer from that document’s pages.

## Adding documents

On the matter home page, natives can be added in one action. Supported types: **PDF, DOCX, TXT, CSV, XLSX, XLS, HTM/HTML, XML, PPTX, PPT, JPG/JPEG, PNG, VCF, RTF, EML, MSG**.

- **Upload files** — the file picker allows multiple files (Shift/Ctrl-click, or select a range). A single file still works.
- **Upload folder** — choose a directory; RockHawk queues every supported file inside it (including subfolders).
- **Drag and drop** — drop several files, or drop a folder, onto the dashed target.

A queue under the drop zone shows each file as pending, uploading, processing, done, duplicate, or error. Uploads run a few at a time so the page stays usable. Duplicates (same bytes already on the matter) are skipped and labeled. Unsupported types never block the rest of the batch.

## Working a table

On the matter home page, name the table and choose whether to include the starter diligence columns or start blank.

On the table, **Add column** opens the column builder (label, instruction, type, enums, dependency, citation policy, model role, prompt version, overwrite policy). **Suggest** turns a typed description into proposed columns; **Import** reads a CSV/XLSX checklist. Nothing is created until you approve. Click a column header to edit it.

1. Open a matter, then a review table
2. Click **Run AI columns**
3. Read the cell, then the pinpoint citation (document + page + quote)
4. Edit if the extraction is incomplete
5. **Verify** when you accept the cell
6. **Flag** and **comment** when another attorney should look
7. **Assign** the cell if your team uses ownership

Verified cells are not overwritten by a later bulk run. Use **Rerun including verified** only when you intend to replace human work.

## Conditional columns

The demo **Termination notice period** column runs only when **Termination for convenience** is `true`. If the prerequisite is not met, the cell is **Not found** (the condition failed — not a fabricated period).

## Hot Review

Mark a document hot, or flag any cell. Those rows appear on the matter’s **Hot Review** page.

## Ask RockHawk

Ask questions such as “Which documents name a Delaware governing-law clause?” Answers are assembled from **current table values and cited pages**. If the table and pages do not support an answer, RockHawk says so. This is still not legal advice.

## Exports

CSV and XLSX download the current grid, including human edits.

## What RockHawk will not do

- Invent a date, cap, party, or statute that is not on a page
- Decide privilege, liability, or strategy
- Replace a conflict check or a supervising attorney
