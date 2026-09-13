import { FormEvent, useEffect, useMemo, useState } from "react";
import {
  api,
  EffectiveSetting,
  RegistrySetting,
} from "../api/client";

type Category = { id: string; label: string };
type Draft = {
  id: string;
  status: string;
  proposed: Record<string, unknown>;
  validation?: { ok?: boolean; errors?: string[]; warnings?: string[] } | null;
  preview?: { diffs?: Diff[]; impact?: string[]; high_risk?: boolean } | null;
  expected_revision_id?: string | null;
};
type Diff = { key: string; before: unknown; after: unknown; risk?: string };
type Revision = {
  id: string;
  number: number;
  status: string;
  reason: string;
  note: string;
  created_at: string | null;
};
type PromptRow = {
  id: string;
  prompt_key: string;
  version: string;
  body: string;
  note: string;
  parent_version: string | null;
};
type FilterId = "all" | "changed" | "overridden" | "restart" | "high-risk";

export function AdminPage() {
  const [categories, setCategories] = useState<Category[]>([]);
  const [registry, setRegistry] = useState<RegistrySetting[]>([]);
  const [values, setValues] = useState<EffectiveSetting[]>([]);
  const [revisionId, setRevisionId] = useState<string | null>(null);
  const [revisionNumber, setRevisionNumber] = useState<number | null>(null);
  const [revisions, setRevisions] = useState<Revision[]>([]);
  const [prompts, setPrompts] = useState<PromptRow[]>([]);
  const [roles, setRoles] = useState<{ role: string; model: string; key: string }[]>([]);
  const [category, setCategory] = useState("application");
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState<FilterId>("all");
  const [pending, setPending] = useState<Record<string, string>>({});
  const [draft, setDraft] = useState<Draft | null>(null);
  const [reason, setReason] = useState("");
  const [status, setStatus] = useState("");
  const [error, setError] = useState("");
  const [aiResult, setAiResult] = useState("");
  const [models, setModels] = useState<string[]>([]);
  const [promptKey, setPromptKey] = useState("column.extract");
  const [promptBody, setPromptBody] = useState("");
  const [promptNote, setPromptNote] = useState("");
  const [compareA, setCompareA] = useState("");
  const [compareB, setCompareB] = useState("");
  const [exportText, setExportText] = useState("");

  const byKey = useMemo(() => Object.fromEntries(registry.map((item) => [item.key, item])), [registry]);

  async function load() {
    const [reg, eff, hist, promptRows, roleRows] = await Promise.all([
      api<{ categories: Category[]; settings: RegistrySetting[] }>("/api/admin/registry"),
      api<{ active_revision_id: string; active_revision_number: number; values: EffectiveSetting[] }>(
        "/api/admin/effective",
      ),
      api<Revision[]>("/api/admin/revisions"),
      api<PromptRow[]>("/api/admin/prompts"),
      api<{ roles: { role: string; model: string; key: string }[] }>("/api/admin/ai/roles"),
    ]);
    setCategories(reg.categories);
    setRegistry(reg.settings);
    setValues(eff.values);
    setRevisionId(eff.active_revision_id);
    setRevisionNumber(eff.active_revision_number);
    setRevisions(hist);
    setPrompts(promptRows);
    setRoles(roleRows.roles);
  }

  useEffect(() => {
    load().catch((err) => setError(err.message));
  }, []);

  const visible = values.filter((item) => {
    const def = byKey[item.key];
    if (category !== "history" && def && def.category !== category) return false;
    if (category === "history") return false;
    const hay = `${item.key} ${def?.label || ""} ${def?.description || ""}`.toLowerCase();
    if (query && !hay.includes(query.toLowerCase())) return false;
    if (filter === "changed" && !(item.key in pending)) return false;
    if (filter === "overridden" && !item.overridden && item.source === "default") return false;
    if (filter === "restart" && !item.restart_required) return false;
    if (filter === "high-risk" && !["high", "bootstrap"].includes(item.risk)) return false;
    return true;
  });

  function displayValue(item: EffectiveSetting) {
    if (item.secret) {
      const hint = item.value && typeof item.value === "object" ? (item.value as { hint?: string }).hint : "••••";
      return hint || "••••";
    }
    if (item.value === null || item.value === undefined || item.value === "") return "—";
    return String(item.value);
  }

  async function startApply(event: FormEvent) {
    event.preventDefault();
    setError("");
    setStatus("");
    const changes: Record<string, unknown> = {};
    for (const [key, raw] of Object.entries(pending)) {
      const def = byKey[key];
      if (!def) continue;
      changes[key] = coerce(def, raw);
    }
    if (!Object.keys(changes).length) {
      setError("Change at least one editable setting before opening a draft.");
      return;
    }
    try {
      const created = await api<Draft>("/api/admin/drafts", {
        method: "POST",
        body: JSON.stringify({ changes, expected_revision_id: revisionId }),
      });
      const validated = await api<{ draft: Draft }>(`/api/admin/drafts/${created.id}/validate`, { method: "POST" });
      if (validated.draft.validation && validated.draft.validation.ok === false) {
        setDraft(validated.draft);
        setError((validated.draft.validation.errors || []).join(" "));
        return;
      }
      const previewed = await api<{ draft: Draft }>(`/api/admin/drafts/${created.id}/preview`, { method: "POST" });
      setDraft(previewed.draft);
      setStatus("Draft validated. Review the impact, then confirm apply.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Draft failed");
    }
  }

  async function confirmApply() {
    if (!draft) return;
    setError("");
    try {
      await api(`/api/admin/drafts/${draft.id}/apply`, {
        method: "POST",
        body: JSON.stringify({ reason, confirm: true, expected_revision_id: revisionId }),
      });
      setPending({});
      setDraft(null);
      setReason("");
      setStatus("Revision applied. Consumers will read the new effective values.");
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Apply failed");
    }
  }

  async function rollback(id: string) {
    const why = reason || "Rollback to previous known-good revision";
    try {
      await api(`/api/admin/revisions/${id}/rollback`, {
        method: "POST",
        body: JSON.stringify({ reason: why }),
      });
      setStatus("Rollback created a new revision.");
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Rollback failed");
    }
  }

  async function testAi() {
    const result = await api<{ ok: boolean; detail: string; models?: string[]; provider: string }>(
      "/api/admin/ai/test-connection",
      { method: "POST" },
    );
    setAiResult(`${result.provider}: ${result.detail}`);
    if (result.models) setModels(result.models);
  }

  async function discover() {
    const result = await api<{ models: string[]; detail?: string }>("/api/admin/ai/models");
    setModels(result.models || []);
    setAiResult(result.detail || `Discovered ${result.models?.length || 0} models`);
  }

  async function savePrompt(event: FormEvent) {
    event.preventDefault();
    await api("/api/admin/prompts", {
      method: "POST",
      body: JSON.stringify({ prompt_key: promptKey, body: promptBody, note: promptNote }),
    });
    setPromptBody("");
    setPromptNote("");
    await load();
  }

  async function doExport() {
    const bundle = await api<Record<string, unknown>>("/api/admin/export");
    setExportText(JSON.stringify(bundle, null, 2));
  }

  async function dryImport(file: File) {
    const bundle = JSON.parse(await file.text());
    const result = await api<{ validation: { ok?: boolean; errors?: string[] }; count: number }>(
      "/api/admin/import",
      { method: "POST", body: JSON.stringify({ bundle, dry_run: true }) },
    );
    setStatus(`Import dry-run: ${result.count} keys. ${result.validation.ok ? "Valid." : (result.validation.errors || []).join(" ")}`);
  }

  const promptVersions = prompts.filter((row) => row.prompt_key === promptKey);
  const left = promptVersions.find((row) => row.id === compareA);
  const right = promptVersions.find((row) => row.id === compareB);

  return (
    <div className="admin-shell">
      <header>
        <h1 className="page-title">Administration Center</h1>
        <p className="lede">
          Draft, validate, preview, and apply configuration. Secrets stay as references. Active revision{" "}
          {revisionNumber ?? "—"}.
        </p>
      </header>
      {error && (
        <p role="alert" className="banner warn">
          {error}
        </p>
      )}
      {status && (
        <p role="status" className="banner">
          {status}
        </p>
      )}
      <div className="admin-layout">
        <nav className="admin-nav" aria-label="Settings categories">
          <label className="field">
            Search settings
            <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="support email, model role…" />
          </label>
          <ul>
            {categories.map((item) => (
              <li key={item.id}>
                <button
                  type="button"
                  className={`nav-link ${category === item.id ? "active" : ""}`}
                  onClick={() => setCategory(item.id)}
                >
                  {item.label}
                </button>
              </li>
            ))}
          </ul>
        </nav>
        <section>
          <div className="toolbar" role="group" aria-label="Filters">
            {(["all", "changed", "overridden", "restart", "high-risk"] as FilterId[]).map((item) => (
              <button key={item} className={`btn ${filter === item ? "" : "ghost"}`} type="button" onClick={() => setFilter(item)}>
                {item}
              </button>
            ))}
          </div>

          {category !== "history" && (
            <form onSubmit={startApply}>
              <div className="table-wrap" role="region" aria-label="Settings">
                <table className="review admin-table">
                  <thead>
                    <tr>
                      <th scope="col">Setting</th>
                      <th scope="col">Effective value</th>
                      <th scope="col">Source</th>
                      <th scope="col">Risk</th>
                      <th scope="col">Draft change</th>
                    </tr>
                  </thead>
                  <tbody>
                    {visible.map((item) => {
                      const def = byKey[item.key];
                      const locked = item.editability === "readonly" || item.editability === "bootstrap";
                      return (
                        <tr key={item.key}>
                          <th scope="row">
                            {def?.label || item.key}
                            <div className="status">{item.key}</div>
                            <div className="lede">{def?.description}</div>
                            {def?.todo && <div className="status">TODO — metadata only</div>}
                          </th>
                          <td>{displayValue(item)}</td>
                          <td>{item.source}</td>
                          <td>
                            {item.risk}
                            {item.restart_required ? " · restart" : ""}
                          </td>
                          <td>
                            {locked ? (
                              <span className="lede">{item.editability}</span>
                            ) : item.secret ? (
                              <label className="field">
                                New secret
                                <input
                                  type="password"
                                  autoComplete="new-password"
                                  value={pending[item.key] || ""}
                                  onChange={(e) => setPending((cur) => ({ ...cur, [item.key]: e.target.value }))}
                                />
                              </label>
                            ) : def?.enum_options ? (
                              <select
                                value={pending[item.key] ?? String(item.value ?? "")}
                                onChange={(e) => setPending((cur) => ({ ...cur, [item.key]: e.target.value }))}
                              >
                                {def.enum_options.map((option) => (
                                  <option key={option} value={option}>
                                    {option}
                                  </option>
                                ))}
                              </select>
                            ) : (
                              <label className="field">
                                <span className="sr-only">New value for {def?.label}</span>
                                <input
                                  value={pending[item.key] ?? ""}
                                  placeholder={displayValue(item)}
                                  onChange={(e) => setPending((cur) => ({ ...cur, [item.key]: e.target.value }))}
                                />
                              </label>
                            )}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
              <div className="toolbar">
                <button className="btn" type="submit">
                  Validate & preview draft
                </button>
              </div>
            </form>
          )}

          {category === "ai" && (
            <section className="card" style={{ marginTop: 16 }}>
              <h2>AI probes</h2>
              <p className="lede">Test Connection and discovery never send matter documents.</p>
              <div className="toolbar">
                <button className="btn secondary" type="button" onClick={() => testAi().catch((err) => setError(err.message))}>
                  Test Connection
                </button>
                <button className="btn ghost" type="button" onClick={() => discover().catch((err) => setError(err.message))}>
                  Discover models
                </button>
              </div>
              {aiResult && <p role="status">{aiResult}</p>}
              {models.length > 0 && <p className="lede">Models: {models.join(", ")}</p>}
              <h3>Role assignments</h3>
              <ul>
                {roles.map((item) => (
                  <li key={item.role}>
                    <strong>{item.role}</strong> → {item.model || "(default chat model)"} ({item.key})
                  </li>
                ))}
              </ul>
            </section>
          )}

          {category === "prompts" && (
            <section className="card" style={{ marginTop: 16 }}>
              <h2>Prompt versions</h2>
              <p className="lede">Saving creates a new immutable version. Prior versions stay for lineage.</p>
              <form onSubmit={savePrompt} className="grid">
                <label className="field">
                  Prompt key
                  <input value={promptKey} onChange={(e) => setPromptKey(e.target.value)} />
                </label>
                <label className="field">
                  Body
                  <textarea rows={6} value={promptBody} onChange={(e) => setPromptBody(e.target.value)} required />
                </label>
                <label className="field">
                  Note
                  <input value={promptNote} onChange={(e) => setPromptNote(e.target.value)} />
                </label>
                <button className="btn" type="submit">
                  Save new version
                </button>
              </form>
              <div className="toolbar">
                <label className="field">
                  Compare A
                  <select value={compareA} onChange={(e) => setCompareA(e.target.value)}>
                    <option value="">Select</option>
                    {promptVersions.map((row) => (
                      <option key={row.id} value={row.id}>
                        v{row.version}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="field">
                  Compare B
                  <select value={compareB} onChange={(e) => setCompareB(e.target.value)}>
                    <option value="">Select</option>
                    {promptVersions.map((row) => (
                      <option key={row.id} value={row.id}>
                        v{row.version}
                      </option>
                    ))}
                  </select>
                </label>
              </div>
              {left && right && (
                <div className="compare">
                  <pre>{left.body}</pre>
                  <pre>{right.body}</pre>
                </div>
              )}
              <ul>
                {promptVersions.map((row) => (
                  <li key={row.id}>
                    v{row.version}
                    {row.parent_version ? ` (from v${row.parent_version})` : ""} — {row.note || "no note"}
                  </li>
                ))}
              </ul>
            </section>
          )}

          {category === "history" && (
            <section className="card">
              <h2>Revisions, import, export</h2>
              <div className="toolbar">
                <button className="btn secondary" type="button" onClick={() => doExport().catch((err) => setError(err.message))}>
                  Export (no secrets)
                </button>
                <label className="field">
                  Dry-run import
                  <input
                    type="file"
                    accept="application/json"
                    onChange={(e) => {
                      const file = e.target.files?.[0];
                      if (file) dryImport(file).catch((err) => setError(err.message));
                    }}
                  />
                </label>
              </div>
              {exportText && <pre className="cell-value">{exportText}</pre>}
              <table className="review">
                <thead>
                  <tr>
                    <th scope="col">#</th>
                    <th scope="col">Status</th>
                    <th scope="col">Reason</th>
                    <th scope="col" />
                  </tr>
                </thead>
                <tbody>
                  {revisions.map((row) => (
                    <tr key={row.id}>
                      <td>{row.number}</td>
                      <td>{row.status}</td>
                      <td>{row.reason}</td>
                      <td>
                        {row.status !== "applied" && (
                          <button className="btn ghost" type="button" onClick={() => rollback(row.id)}>
                            Rollback to this revision
                          </button>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </section>
          )}
        </section>
      </div>

      {draft && (
        <aside className="drawer drawer-wide" aria-label="Configuration draft">
          <button className="btn ghost" type="button" onClick={() => setDraft(null)}>
            Close draft
          </button>
          <h2>Draft {draft.status}</h2>
          {draft.validation?.errors?.length ? (
            <ul>
              {draft.validation.errors.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
          ) : (
            <p className="lede">Validation passed.</p>
          )}
          <h3>Impact</h3>
          <ul>
            {(draft.preview?.impact || []).map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
          <h3>Diff</h3>
          <ul>
            {(draft.preview?.diffs || []).map((item) => (
              <li key={item.key}>
                <strong>{item.key}</strong>: {String(item.before)} → {String(item.after)}
              </li>
            ))}
          </ul>
          <label className="field">
            Reason for apply
            <input value={reason} onChange={(e) => setReason(e.target.value)} minLength={8} required />
          </label>
          <button className="btn" type="button" onClick={confirmApply} disabled={reason.trim().length < 8}>
            Confirm and apply
          </button>
        </aside>
      )}
    </div>
  );
}

function coerce(def: RegistrySetting, raw: string): unknown {
  if (def.value_type === "boolean") return raw === "true" || raw === "1" || raw === "on";
  if (def.value_type === "integer") return Number.parseInt(raw, 10);
  if (def.value_type === "number") return Number.parseFloat(raw);
  return raw;
}
