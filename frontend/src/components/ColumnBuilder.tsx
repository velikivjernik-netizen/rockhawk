import { FormEvent, useMemo, useState } from "react";
import { api, Column, ColumnDraft } from "../api/client";

const VALUE_TYPES = ["text", "boolean", "date", "number", "money", "enum"];
const CITATION_POLICIES = ["always", "when_quoting", "optional", "never"];
const MODEL_ROLES = ["extraction", "qc", "synthesis", "orchestrator", "triage", "embeddings"];
const OVERWRITE = ["skip_verified", "overwrite_unverified", "overwrite_all"];

type Mode = "create" | "suggest" | "import" | "edit";

type Props = {
  tableId: string;
  columns: Column[];
  initial?: Column | null;
  onClose: () => void;
  onChanged: () => Promise<void> | void;
};

function emptyDraft(): ColumnDraft {
  return {
    name: "",
    value_type: "text",
    instruction: "",
    enum_options: null,
    condition_column_id: null,
    condition_equals: "",
    citation_policy: "when_quoting",
    model_role: "extraction",
    prompt_key: "column.extract",
    prompt_version: "",
    overwrite_policy: "skip_verified",
    required: false,
  };
}

export function ColumnBuilder({ tableId, columns, initial, onClose, onChanged }: Props) {
  const [mode, setMode] = useState<Mode>(initial ? "edit" : "create");
  const [draft, setDraft] = useState<ColumnDraft>(initial ? { ...initial } : emptyDraft());
  const [description, setDescription] = useState("");
  const [proposals, setProposals] = useState<ColumnDraft[]>([]);
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const title = useMemo(() => {
    if (mode === "suggest") return "Suggest columns";
    if (mode === "import") return "Import checklist";
    if (mode === "edit") return "Edit column";
    return "Add column";
  }, [mode]);

  function update<K extends keyof ColumnDraft>(key: K, value: ColumnDraft[K]) {
    setDraft((current) => ({ ...current, [key]: value }));
  }

  async function saveColumn(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      const body = serialize(draft);
      if (initial?.id) {
        await api(`/api/columns/${initial.id}`, { method: "PATCH", body: JSON.stringify(body) });
      } else {
        await api(`/api/tables/${tableId}/columns`, { method: "POST", body: JSON.stringify(body) });
      }
      await onChanged();
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not save column");
    } finally {
      setBusy(false);
    }
  }

  async function suggest(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      const result = await api<{ proposed: ColumnDraft[] }>(`/api/tables/${tableId}/columns/suggest`, {
        method: "POST",
        body: JSON.stringify({ description }),
      });
      setProposals(result.proposed);
      setSelected(new Set(result.proposed.map((_, index) => index)));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Suggest failed");
    } finally {
      setBusy(false);
    }
  }

  async function importFile(file: File) {
    setBusy(true);
    setError("");
    try {
      const data = new FormData();
      data.append("file", file);
      const result = await api<{ proposed: ColumnDraft[] }>(`/api/tables/${tableId}/columns/import`, {
        method: "POST",
        body: data,
      });
      setProposals(result.proposed);
      setSelected(new Set(result.proposed.map((_, index) => index)));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Import failed");
    } finally {
      setBusy(false);
    }
  }

  async function approveSelected() {
    const columnsToAdd = proposals.filter((_, index) => selected.has(index));
    if (!columnsToAdd.length) {
      setError("Select at least one proposed column to add. Nothing is created until you approve.");
      return;
    }
    setBusy(true);
    setError("");
    try {
      await api(`/api/tables/${tableId}/columns/bulk`, {
        method: "POST",
        body: JSON.stringify({ columns: columnsToAdd.map(serialize) }),
      });
      await onChanged();
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not add columns");
    } finally {
      setBusy(false);
    }
  }

  return (
    <aside className="drawer drawer-wide" aria-label={title}>
      <div className="toolbar">
        <button className="btn ghost" type="button" onClick={onClose}>
          Close
        </button>
        {!initial && (
          <div className="toolbar" role="tablist" aria-label="Column builder mode">
            <button className={`btn ${mode === "create" ? "" : "ghost"}`} type="button" onClick={() => setMode("create")}>
              New column
            </button>
            <button className={`btn ${mode === "suggest" ? "" : "ghost"}`} type="button" onClick={() => setMode("suggest")}>
              Suggest
            </button>
            <button className={`btn ${mode === "import" ? "" : "ghost"}`} type="button" onClick={() => setMode("import")}>
              Import
            </button>
          </div>
        )}
      </div>
      <h2>{title}</h2>
      <p className="lede">
        Questions become typed columns. Suggestions and imports are proposals only — they do not run until you
        approve them.
      </p>
      {error && (
        <p role="alert" className="banner warn">
          {error}
        </p>
      )}

      {(mode === "create" || mode === "edit") && (
        <form onSubmit={saveColumn} className="grid">
          <label className="field">
            Label
            <input value={draft.name} onChange={(e) => update("name", e.target.value)} required />
          </label>
          <label className="field">
            Instruction
            <textarea rows={4} value={draft.instruction} onChange={(e) => update("instruction", e.target.value)} required />
          </label>
          <label className="field">
            Output type
            <select value={draft.value_type} onChange={(e) => update("value_type", e.target.value)}>
              {VALUE_TYPES.map((item) => (
                <option key={item} value={item}>
                  {item}
                </option>
              ))}
            </select>
          </label>
          {draft.value_type === "enum" && (
            <label className="field">
              Enum options (comma-separated)
              <input
                value={(draft.enum_options || []).join(", ")}
                onChange={(e) =>
                  update(
                    "enum_options",
                    e.target.value.split(",").map((part) => part.trim()).filter(Boolean),
                  )
                }
              />
            </label>
          )}
          <label className="field">
            Depends on column
            <select
              value={draft.condition_column_id || ""}
              onChange={(e) => update("condition_column_id", e.target.value || null)}
            >
              <option value="">None</option>
              {columns
                .filter((col) => col.id !== initial?.id)
                .map((col) => (
                  <option key={col.id} value={col.id}>
                    {col.name}
                  </option>
                ))}
            </select>
          </label>
          <label className="field">
            Dependency equals
            <input
              value={draft.condition_equals || ""}
              onChange={(e) => update("condition_equals", e.target.value)}
              placeholder="true"
            />
          </label>
          <label className="field">
            Citation policy
            <select value={draft.citation_policy} onChange={(e) => update("citation_policy", e.target.value)}>
              {CITATION_POLICIES.map((item) => (
                <option key={item} value={item}>
                  {item}
                </option>
              ))}
            </select>
          </label>
          <label className="field">
            Model role
            <select value={draft.model_role} onChange={(e) => update("model_role", e.target.value)}>
              {MODEL_ROLES.map((item) => (
                <option key={item} value={item}>
                  {item}
                </option>
              ))}
            </select>
          </label>
          <label className="field">
            Prompt key
            <input value={draft.prompt_key || ""} onChange={(e) => update("prompt_key", e.target.value)} />
          </label>
          <label className="field">
            Prompt version
            <input value={draft.prompt_version || ""} onChange={(e) => update("prompt_version", e.target.value)} />
          </label>
          <label className="field">
            Rerun / overwrite policy
            <select value={draft.overwrite_policy} onChange={(e) => update("overwrite_policy", e.target.value)}>
              {OVERWRITE.map((item) => (
                <option key={item} value={item}>
                  {item}
                </option>
              ))}
            </select>
          </label>
          <label className="field checkbox">
            <input
              type="checkbox"
              checked={Boolean(draft.required)}
              onChange={(e) => update("required", e.target.checked)}
            />
            Required when the document supports this question
          </label>
          <button className="btn" type="submit" disabled={busy}>
            {busy ? "Saving…" : initial ? "Save column" : "Add column"}
          </button>
        </form>
      )}

      {mode === "suggest" && (
        <form onSubmit={suggest} className="grid">
          <label className="field">
            Describe the review questions
            <textarea
              rows={5}
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Extract governing law, venue, liability cap, and whether there is a jury waiver."
              required
            />
          </label>
          <button className="btn" type="submit" disabled={busy}>
            {busy ? "Proposing…" : "Propose columns"}
          </button>
        </form>
      )}

      {mode === "import" && (
        <label className="field">
          Checklist CSV or XLSX
          <input
            type="file"
            accept=".csv,.xlsx,.xls,.txt"
            onChange={(e) => {
              const file = e.target.files?.[0];
              if (file) importFile(file);
            }}
          />
        </label>
      )}

      {proposals.length > 0 && (mode === "suggest" || mode === "import") && (
        <section>
          <h3>Proposed columns — approve to add</h3>
          <ul className="proposal-list">
            {proposals.map((item, index) => (
              <li key={`${item.name}-${index}`}>
                <label className="checkbox">
                  <input
                    type="checkbox"
                    checked={selected.has(index)}
                    onChange={(e) => {
                      const next = new Set(selected);
                      if (e.target.checked) next.add(index);
                      else next.delete(index);
                      setSelected(next);
                    }}
                  />
                  <span>
                    <strong>{item.name}</strong> · {item.value_type}
                    <div className="lede">{item.instruction}</div>
                  </span>
                </label>
              </li>
            ))}
          </ul>
          <button className="btn" type="button" disabled={busy} onClick={approveSelected}>
            Add selected columns
          </button>
        </section>
      )}
    </aside>
  );
}

function serialize(draft: ColumnDraft) {
  return {
    name: draft.name,
    value_type: draft.value_type,
    instruction: draft.instruction,
    enum_options: draft.value_type === "enum" ? draft.enum_options : null,
    condition_column_id: draft.condition_column_id || null,
    condition_equals: draft.condition_equals || null,
    citation_policy: draft.citation_policy || "when_quoting",
    model_role: draft.model_role || "extraction",
    prompt_key: draft.prompt_key || "column.extract",
    prompt_version: draft.prompt_version || null,
    overwrite_policy: draft.overwrite_policy || "skip_verified",
    required: Boolean(draft.required),
  };
}
