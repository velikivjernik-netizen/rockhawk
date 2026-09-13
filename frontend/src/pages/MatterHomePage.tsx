import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api, DocumentOut, Matter, TableDetail } from "../api/client";
import { DocumentUploader } from "../components/DocumentUploader";

type TableSummary = { id: string; name: string; description: string };

export function MatterHomePage() {
  const { matterId } = useParams();
  const [matter, setMatter] = useState<Matter | null>(null);
  const [documents, setDocuments] = useState<DocumentOut[]>([]);
  const [tables, setTables] = useState<TableSummary[]>([]);
  const [error, setError] = useState("");

  async function refreshDocuments() {
    if (!matterId) return;
    setDocuments(await api<DocumentOut[]>(`/api/matters/${matterId}/documents`));
  }

  useEffect(() => {
    if (!matterId) return;
    Promise.all([
      api<Matter>(`/api/matters/${matterId}`),
      api<DocumentOut[]>(`/api/matters/${matterId}/documents`),
      api<TableSummary[]>(`/api/matters/${matterId}/tables`),
    ])
      .then(([m, d, t]) => {
        setMatter(m);
        setDocuments(d);
        setTables(t);
      })
      .catch((err) => setError(err.message));
  }, [matterId]);

  async function createTable() {
    const created = await api<TableDetail>(`/api/matters/${matterId}/tables`, {
      method: "POST",
      body: JSON.stringify({ name: "Review table", include_all_documents: true }),
    });
    setTables(await api<TableSummary[]>(`/api/matters/${matterId}/tables`));
    window.location.assign(`/matters/${matterId}/tables/${created.id}`);
  }

  if (!matter || !matterId) return <p>{error || "Loading matter…"}</p>;

  return (
    <div>
      <h1 className="page-title">{matter.name}</h1>
      <p className="lede">{matter.description}</p>
      <div className="banner">Fictional demonstration data unless you uploaded your own files. Review every extraction.</div>
      {error && <p role="alert">{error}</p>}
      <section className="card" style={{ marginBottom: 16 }}>
        <h2>Documents</h2>
        <DocumentUploader
          matterId={matterId}
          onUploaded={() => {
            refreshDocuments().catch((err) => setError(err.message));
          }}
        />
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
