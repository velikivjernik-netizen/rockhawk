import { FormEvent, useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api, Cell, TableDetail, User } from "../api/client";

export function TablePage() {
  const { matterId, tableId } = useParams();
  const [table, setTable] = useState<TableDetail | null>(null);
  const [selected, setSelected] = useState<Cell | null>(null);
  const [users, setUsers] = useState<User[]>([]);
  const [question, setQuestion] = useState("Which documents are governed by Delaware law?");
  const [askAnswer, setAskAnswer] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function refresh() {
    if (!tableId) return;
    const next = await api<TableDetail>(`/api/tables/${tableId}`);
    setTable(next);
    if (selected) {
      const match = next.rows.flatMap((r) => r.cells).find((c) => c.id === selected.id);
      if (match) setSelected(match);
    }
  }

  useEffect(() => {
    refresh().catch((err) => setError(err.message));
    if (matterId) {
      api<{ user?: User }[]>(`/api/matters/${matterId}/members`)
        .then((members) => setUsers(members.map((m) => m.user).filter((u): u is User => Boolean(u))))
        .catch(() => setUsers([]));
    }
  }, [tableId, matterId]);

  const columns = table?.columns ?? [];

  async function run(includeVerified = false) {
    setBusy(true);
    try {
      await api(`/api/tables/${tableId}/run`, { method: "POST", body: JSON.stringify({ include_verified: includeVerified }) });
      await api(`/api/tables/${tableId}/run-sync`, { method: "POST", body: JSON.stringify({ include_verified: includeVerified }) });
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Run failed");
    } finally {
      setBusy(false);
    }
  }

  async function patchCell(cell: Cell, body: Record<string, unknown>) {
    await api(`/api/cells/${cell.id}`, { method: "PATCH", body: JSON.stringify(body) });
    await refresh();
  }

  async function comment(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selected) return;
    const data = new FormData(event.currentTarget);
    await api(`/api/cells/${selected.id}/comments`, { method: "POST", body: JSON.stringify({ body: data.get("body") }) });
    event.currentTarget.reset();
    await refresh();
  }

  async function downloadExport(format: "csv" | "xlsx") {
    const token = localStorage.getItem("rockhawk.token");
    const response = await fetch(`/api/tables/${tableId}/export.${format}`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    });
    if (!response.ok) throw new Error("Export failed");
    const blob = await response.blob();
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `${table?.name || "review"}.${format}`;
    link.click();
    URL.revokeObjectURL(url);
  }

  async function ask(event: FormEvent) {
    event.preventDefault();
    const result = await api<{ messages: { role: string; body: string }[] }>(`/api/tables/${tableId}/ask`, {
      method: "POST",
      body: JSON.stringify({ question }),
    });
    const assistant = [...result.messages].reverse().find((m) => m.role === "assistant");
    setAskAnswer(assistant?.body || "");
  }

  const selectedColumn = useMemo(
    () => columns.find((c) => c.id === selected?.column_id),
    [columns, selected],
  );

  if (!table) return <p>{error || "Loading table…"}</p>;

  return (
    <div>
      <p>
        <Link to={`/matters/${matterId}`}>← Matter</Link>
      </p>
      <h1 className="page-title">{table.name}</h1>
      <p className="lede">{table.description} Cells are drafts for attorney review. Verified cells survive bulk reruns.</p>
      {error && <p role="alert">{error}</p>}
      <div className="toolbar">
        <button className="btn" type="button" disabled={busy} onClick={() => run(false)}>
          {busy ? "Running…" : "Run AI columns"}
        </button>
        <button className="btn ghost" type="button" onClick={() => run(true)}>
          Rerun including verified
        </button>
        <button className="btn secondary" type="button" onClick={() => downloadExport("csv")}>
          Export CSV
        </button>
        <button className="btn secondary" type="button" onClick={() => downloadExport("xlsx")}>
          Export XLSX
        </button>
      </div>
      <div className="table-wrap" role="region" aria-label="Review table">
        <table className="review">
          <thead>
            <tr>
              <th scope="col">Document</th>
              {columns.map((col) => (
                <th key={col.id} scope="col">
                  {col.name}
                  <div className="status">{col.value_type}{col.condition_column_id ? " · conditional" : ""}</div>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {table.rows.map((row) => (
              <tr key={row.id}>
                <th scope="row">
                  {row.is_hot && <span className="hot-dot" aria-label="Hot document" />}
                  {row.document?.filename}
                  <div>
                    <button className="btn ghost" type="button" onClick={() => api(`/api/rows/${row.id}/hot`, { method: "POST" }).then(refresh)}>
                      {row.is_hot ? "Remove from Hot Review" : "Mark hot"}
                    </button>
                  </div>
                </th>
                {columns.map((col) => {
                  const cell = row.cells.find((c) => c.column_id === col.id);
                  if (!cell) return <td key={col.id} />;
                  return (
                    <td key={col.id} className={`cell ${cell.verified ? "verified" : ""} ${cell.flagged ? "flagged" : ""}`}>
                      <button type="button" className="cell-value" style={{ background: "none", border: 0, color: "inherit", textAlign: "left", cursor: "pointer" }} onClick={() => setSelected(cell)}>
                        {cell.value || "—"}
                      </button>
                      <div className={`status ${cell.status}`}>{cell.status}</div>
                      {cell.citations?.[0] && (
                        <div className="cite">
                          p.{cell.citations[0].page} · {cell.citations[0].quote.slice(0, 90)}
                        </div>
                      )}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <section className="card" style={{ marginTop: 20 }}>
        <h2>Ask RockHawk</h2>
        <p className="lede">Answers are grounded in this table’s outputs and cited pages. If unsupported: Not found.</p>
        <form onSubmit={ask} className="toolbar">
          <label className="field" style={{ flex: 1 }}>
            Question
            <input value={question} onChange={(e) => setQuestion(e.target.value)} />
          </label>
          <button className="btn" type="submit">
            Ask
          </button>
        </form>
        {askAnswer && <pre className="cell-value">{askAnswer}</pre>}
      </section>

      {selected && selectedColumn && (
        <aside className="drawer" aria-label="Cell detail">
          <button className="btn ghost" type="button" onClick={() => setSelected(null)}>
            Close
          </button>
          <h2>{selectedColumn.name}</h2>
          <p className="lede">{selectedColumn.instruction}</p>
          <label className="field">
            Value
            <textarea
              rows={4}
              defaultValue={selected.value}
              key={selected.id + selected.value}
              onBlur={(e) => patchCell(selected, { value: e.target.value })}
            />
          </label>
          <div className="toolbar">
            <button className="btn secondary" type="button" onClick={() => patchCell(selected, { verified: !selected.verified })}>
              {selected.verified ? "Unverify" : "Verify"}
            </button>
            <button className="btn danger" type="button" onClick={() => patchCell(selected, { flagged: !selected.flagged })}>
              {selected.flagged ? "Clear flag" : "Flag"}
            </button>
          </div>
          <label className="field">
            Assign
            <select
              value={selected.assigned_to_id || ""}
              onChange={(e) => patchCell(selected, { assigned_to_id: e.target.value || null })}
            >
              <option value="">Unassigned</option>
              {users.map((user) => (
                <option key={user.id} value={user.id}>
                  {user.name}
                </option>
              ))}
            </select>
          </label>
          <h3>Pinpoint citations</h3>
          {selected.citations?.length ? (
            selected.citations.map((cite, index) => (
              <p key={index} className="cite">
                {cite.document_name} p.{cite.page}: “{cite.quote}”
              </p>
            ))
          ) : (
            <p>No page citation — typically a Not found result.</p>
          )}
          <h3>Comments</h3>
          <ul>
            {selected.comments?.map((item) => (
              <li key={item.id}>{item.body}</li>
            ))}
          </ul>
          <form onSubmit={comment}>
            <label className="field">
              Add comment
              <input name="body" required />
            </label>
            <button className="btn secondary" type="submit">
              Comment
            </button>
          </form>
        </aside>
      )}
    </div>
  );
}
