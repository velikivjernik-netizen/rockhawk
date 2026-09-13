import { DragEvent, KeyboardEvent, useRef, useState } from "react";
import { api, DocumentOut } from "../api/client";

export type QueueStatus = "pending" | "uploading" | "processing" | "done" | "error" | "duplicate";

export type QueueItem = {
  id: string;
  file: File;
  name: string;
  status: QueueStatus;
  detail: string;
};

export const SUPPORTED_EXTENSIONS = [
  ".pdf",
  ".docx",
  ".txt",
  ".md",
  ".csv",
  ".xlsx",
  ".xls",
  ".htm",
  ".html",
  ".xml",
  ".pptx",
  ".ppt",
  ".jpg",
  ".jpeg",
  ".png",
  ".vcf",
  ".vcard",
  ".rtf",
  ".eml",
  ".msg",
];
const ACCEPT = SUPPORTED_EXTENSIONS.join(",") + ",application/pdf,text/plain,text/csv,text/html,image/jpeg,image/png";
const CONCURRENCY = 4;
const SKIP_NAMES = new Set([".ds_store", "thumbs.db", "desktop.ini"]);
const UNSUPPORTED_MESSAGE =
  "Unsupported file type. Use PDF, DOCX, TXT, CSV, XLSX, XLS, HTM/HTML, XML, PPTX, PPT, JPG/JPEG, PNG, VCF, RTF, EML, or MSG.";

export function displayName(file: File): string {
  const relative = (file as File & { webkitRelativePath?: string }).webkitRelativePath;
  return relative && relative.length > 0 ? relative : file.name;
}

export function isSupportedUpload(file: File): boolean {
  const name = file.name.toLowerCase();
  if (SKIP_NAMES.has(name)) return false;
  return SUPPORTED_EXTENSIONS.some((ext) => name.endsWith(ext));
}

export function queueSummary(items: QueueItem[]): string {
  const done = items.filter((item) => item.status === "done" || item.status === "duplicate").length;
  const errors = items.filter((item) => item.status === "error").length;
  const active = items.filter((item) => item.status === "uploading" || item.status === "processing").length;
  return `${done} of ${items.length} complete` + (active ? `, ${active} in progress` : "") + (errors ? `, ${errors} failed` : "");
}

export function DocumentUploader({
  matterId,
  onUploaded,
}: {
  matterId: string;
  onUploaded: () => void;
}) {
  const fileInput = useRef<HTMLInputElement>(null);
  const folderInput = useRef<HTMLInputElement>(null);
  const [items, setItems] = useState<QueueItem[]>([]);
  const [dragging, setDragging] = useState(false);
  const [busy, setBusy] = useState(false);

  function patch(id: string, update: Partial<QueueItem>) {
    setItems((current) => current.map((item) => (item.id === id ? { ...item, ...update } : item)));
  }

  async function enqueue(files: File[]) {
    if (!files.length) return;
    const next: QueueItem[] = files.map((file, index) => {
      const name = displayName(file);
      const supported = isSupportedUpload(file);
      return {
        id: `${Date.now()}-${index}-${name}`,
        file,
        name,
        status: supported ? "pending" : "error",
        detail: supported ? "" : UNSUPPORTED_MESSAGE,
      };
    });
    setItems((current) => [...next, ...current]);
    const work = next.filter((item) => item.status === "pending");
    if (!work.length) return;
    setBusy(true);
    try {
      await runPool(work, CONCURRENCY, async (item) => {
        patch(item.id, { status: "uploading" });
        const body = new FormData();
        body.append("file", item.file, item.name);
        try {
          patch(item.id, { status: "processing" });
          const created = await api<DocumentOut>(`/api/matters/${matterId}/documents`, { method: "POST", body });
          patch(item.id, { status: "done", detail: `${created.page_count} page${created.page_count === 1 ? "" : "s"}` });
        } catch (err) {
          const message = err instanceof Error ? err.message : "Upload failed";
          const duplicate = /duplicate/i.test(message);
          patch(item.id, { status: duplicate ? "duplicate" : "error", detail: message });
        }
      });
      onUploaded();
    } finally {
      setBusy(false);
    }
  }

  async function onDrop(event: DragEvent) {
    event.preventDefault();
    setDragging(false);
    const files = await filesFromDataTransfer(event.dataTransfer);
    await enqueue(files);
  }

  return (
    <div>
      <div className="toolbar">
        <button className="btn" type="button" onClick={() => fileInput.current?.click()} disabled={busy}>
          Upload files
        </button>
        <button className="btn secondary" type="button" onClick={() => folderInput.current?.click()} disabled={busy}>
          Upload folder
        </button>
      </div>
      <input
        ref={fileInput}
        className="sr-only"
        type="file"
        multiple
        tabIndex={-1}
        aria-hidden="true"
        accept={ACCEPT}
        onChange={(event) => {
          const list = event.target.files ? Array.from(event.target.files) : [];
          event.target.value = "";
          void enqueue(list);
        }}
      />
      <input
        ref={folderInput}
        className="sr-only"
        type="file"
        tabIndex={-1}
        aria-hidden="true"
        // @ts-expect-error webkitdirectory is not in the React typings
        webkitdirectory=""
        directory=""
        multiple
        onChange={(event) => {
          const list = event.target.files ? Array.from(event.target.files) : [];
          event.target.value = "";
          void enqueue(list);
        }}
      />
      <div
        className={`dropzone${dragging ? " active" : ""}`}
        role="button"
        tabIndex={0}
        aria-label="Drop supported files or a folder here to upload"
        onDragEnter={(event) => {
          event.preventDefault();
          setDragging(true);
        }}
        onDragOver={(event) => {
          event.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={(event) => void onDrop(event)}
        onKeyDown={(event: KeyboardEvent) => {
          if (event.key === "Enter" || event.key === " ") {
            event.preventDefault();
            fileInput.current?.click();
          }
        }}
      >
        Drop multiple files or a folder here. Same as <strong>Upload files</strong> (Shift/Ctrl-click for several) or{" "}
        <strong>Upload folder</strong>. Accepts PDF, DOCX, TXT, CSV, XLSX, XLS, HTML, XML, PPTX, PPT, JPG, PNG, VCF,
        RTF, EML, and MSG.
      </div>
      <p className="lede" aria-live="polite">
        {items.length ? queueSummary(items) : "No upload in progress."}
      </p>
      {items.length > 0 && (
        <ul className="upload-queue" aria-label="Upload queue">
          {items.map((item) => (
            <li key={item.id} className={`upload-item ${item.status}`}>
              <span className="upload-name">{item.name}</span>
              <span className={`status ${item.status}`}>{item.status}</span>
              {item.detail && <span className="lede"> — {item.detail}</span>}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

async function runPool<T>(items: T[], limit: number, worker: (item: T) => Promise<void>): Promise<void> {
  const queue = [...items];
  const n = Math.max(1, Math.min(limit, queue.length));
  await Promise.all(
    Array.from({ length: n }, async () => {
      while (queue.length) {
        const item = queue.shift();
        if (item) await worker(item);
      }
    }),
  );
}

async function filesFromDataTransfer(transfer: DataTransfer): Promise<File[]> {
  const items = Array.from(transfer.items || []);
  const collected: File[] = [];
  const entries = items
    .map((item) => (typeof item.webkitGetAsEntry === "function" ? item.webkitGetAsEntry() : null))
    .filter((entry): entry is FileSystemEntry => entry != null);
  if (entries.length) {
    for (const entry of entries) {
      await walkEntry(entry, collected);
    }
    if (collected.length) return collected;
  }
  return Array.from(transfer.files || []);
}

async function walkEntry(entry: FileSystemEntry, out: File[]): Promise<void> {
  if (entry.isFile) {
    const file = await new Promise<File | null>((resolve) => {
      (entry as FileSystemFileEntry).file(resolve, () => resolve(null));
    });
    if (file) out.push(file);
    return;
  }
  if (entry.isDirectory) {
    const reader = (entry as FileSystemDirectoryEntry).createReader();
    const read = () =>
      new Promise<FileSystemEntry[]>((resolve) => {
        reader.readEntries(resolve, () => resolve([]));
      });
    let batch = await read();
    while (batch.length) {
      for (const child of batch) {
        await walkEntry(child, out);
      }
      if (batch.length < 100) break;
      batch = await read();
    }
  }
}
