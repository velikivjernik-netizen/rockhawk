import { FormEvent, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, Matter, User } from "../api/client";

export function MattersPage() {
  const [matters, setMatters] = useState<Matter[]>([]);
  const [me, setMe] = useState<User | null>(null);
  const [error, setError] = useState("");
  const [name, setName] = useState("");

  async function refresh() {
    const [user, list] = await Promise.all([api<User>("/api/auth/me"), api<Matter[]>("/api/matters")]);
    setMe(user);
    setMatters(list);
  }

  useEffect(() => {
    refresh().catch((err) => setError(err.message));
  }, []);

  async function loadDemo() {
    await api("/api/matters/demo/load", { method: "POST" });
    await refresh();
  }

  async function createMatter(event: FormEvent) {
    event.preventDefault();
    await api("/api/matters", {
      method: "POST",
      body: JSON.stringify({ name, description: "New matter", client_name: "Fictional client" }),
    });
    setName("");
    await refresh();
  }

  return (
    <div>
      <h1 className="page-title">Matters</h1>
      <p className="lede">Matter-scoped workspaces. Ethical walls hide matters you must not see.</p>
      {me?.must_change_password && (
        <div className="banner warn" role="alert">
          You are using the published development admin password. Change it immediately on any shared host.
        </div>
      )}
      <div className="toolbar">
        {me?.role === "admin" && (
          <button className="btn" type="button" onClick={() => loadDemo().catch((e) => setError(e.message))}>
            Load demo matter
          </button>
        )}
        <form onSubmit={createMatter} className="toolbar" style={{ margin: 0 }}>
          <label className="field">
            New matter name
            <input value={name} onChange={(e) => setName(e.target.value)} required />
          </label>
          <button className="btn secondary" type="submit">
            Create
          </button>
        </form>
      </div>
      {error && <p role="alert">{error}</p>}
      <div className="grid matter-grid">
        {matters.map((matter) => (
          <Link key={matter.id} to={`/matters/${matter.id}`} className="card matter-card" style={{ textDecoration: "none", color: "inherit" }}>
            <h2>{matter.name}</h2>
            <p>{matter.description}</p>
            <small>
              {matter.client_name} · {matter.opposing_party}
            </small>
          </Link>
        ))}
        {matters.length === 0 && <p>No visible matters. Admins can load the fictional demo matter.</p>}
      </div>
    </div>
  );
}
