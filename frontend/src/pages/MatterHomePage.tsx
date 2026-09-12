import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api, Matter, TableDetail } from "../api/client";

type Document = { id: string; filename: string; page_count: number; content_type: string };
type TableSummary = { id: string; name: string; description: string };

export function MatterHomePage() {
  const { matterId } = useParams();
  const [matter, setMatter] = useState<Matter | null>(null);
  const [documents, setDocuments] = useState<Document[]>([]);
  const [tables, setTables] = useState<TableSummary[]>([]);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!matterId) return;
    Promise.all([
      api<Matter>(`/api/matters/${matterId}`),
      api<Document[]>(`/api/matters/${matterId}/documents`),
      api<TableSummary[]>(`/api/matters/${matterId}/tables`),
    ])
      .then(([m, d, t]) => {
        setMatter(m);
        setDocuments(d);
        setTables(t);
      })
      .catch((err) => setError(err.message));
  }, [matterId]);

  async function upload(file: File) {
    const body = new FormData();
    body.append("file", file);
    await api(`/api/matters/${matterId}/documents`, { method: "POST", body });
    setDocuments(await api<Document[]>(`/api/matters/${matterId}/documents`));
  }

  async function createTable() {
    const created = await api<TableDetail>(`/api/matters/${matterId}/tables`, {
      method: "POST",
      body: JSON.stringify({ name: "Review table", include_all_documents: true }),
    });
    setTables(await api<TableSummary[]>(`/api/matters/${matterId}/tables`));
    window.location.assign(`/matters/${matterId}/tables/${created.id}`);
  }

  if (!matter) return <p>{error || "Loading matter…"}</p>;

  return (
    <div>
      <h1 className="page-title">{matter.name}</h1>
      <p className="lede">{matter.description}</p>
      <div className="banner">Fictional demonstration data unless you uploaded your own files. Review every extraction.</div>
      <section className="card" style={{ marginBottom: 16 }}>
        <h2>Documents</h2>
        <label className="field">
          Upload PDF, DOCX, or TXT
          <input
            type="file"
            accept=".pdf,.docx,.txt,application/pdf,text/plain"
            onChange={(e) => {
              const file = e.target.files?.[0];
              if (file) upload(file).catch((err) => setError(err.message));
            }}
          />
        </label>
        <ul>
          {documents.map((doc) => (
            <li key={doc.id}>
              {doc.filename} · {doc.page_count} page{doc.page_count === 1 ? "" : "s"}
            </li>
          ))}
        </ul>
      </section>
      <section className="card">
        <h2>Review tables</h2>
        <button className="btn" type="button" onClick={() => createTable().catch((err) => setError(err.message))}>
          Create review table
        </button>
        <ul>
          {tables.map((table) => (
            <li key={table.id}>
              <Link to={`/matters/${matterId}/tables/${table.id}`}>{table.name}</Link>
              <div className="lede">{table.description}</div>
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}
