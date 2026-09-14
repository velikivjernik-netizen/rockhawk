import { EffectiveSetting } from "../api/client";
import { api } from "../api/client";

export const ROLE_ORDER = [
  { role: "orchestrator", key: "ai.role.orchestrator", label: "Orchestrator" },
  { role: "triage", key: "ai.role.triage", label: "Triage" },
  { role: "extraction", key: "ai.role.extraction", label: "Coding / extraction" },
  { role: "qc", key: "ai.role.qc", label: "QC" },
  { role: "synthesis", key: "ai.role.synthesis", label: "Synthesis" },
  { role: "embeddings", key: "ai.role.embeddings", label: "Embeddings" },
];

export const AI_PANEL_KEYS = new Set([
  "ai.provider",
  "ai.openai_compatible.base_url",
  "ai.openai_compatible.api_key",
  "ai.openai_compatible.model",
  ...ROLE_ORDER.map((item) => item.key),
]);

type Props = {
  values: EffectiveSetting[];
  pending: Record<string, string>;
  setPending: (next: Record<string, string> | ((cur: Record<string, string>) => Record<string, string>)) => void;
  models: string[];
  setModels: (models: string[]) => void;
  aiResult: string;
  setAiResult: (text: string) => void;
  onError: (message: string) => void;
};

export function secretStatus(item: EffectiveSetting | undefined): string {
  if (!item?.secret) return "";
  const value = item.value as { configured?: boolean; hint?: string } | null;
  if (value && value.configured) return `Configured (${value.hint || "••••"})`;
  return "Not configured";
}

export function OpenWebUIPanel({
  values,
  pending,
  setPending,
  models,
  setModels,
  aiResult,
  setAiResult,
  onError,
}: Props) {
  const byKey = Object.fromEntries(values.map((item) => [item.key, item]));
  const provider = byKey["ai.provider"];
  const base = byKey["ai.openai_compatible.base_url"];
  const key = byKey["ai.openai_compatible.api_key"];
  const model = byKey["ai.openai_compatible.model"];
  const providerLocked = provider?.editability === "bootstrap";

  function draftValue(settingKey: string, fallback = "") {
    if (settingKey in pending) return pending[settingKey];
    const item = byKey[settingKey];
    if (!item || item.secret) return fallback;
    return item.value == null ? fallback : String(item.value);
  }

  function setDraft(settingKey: string, value: string) {
    setPending((cur) => ({ ...cur, [settingKey]: value }));
  }

  async function probe(kind: "test" | "discover") {
    const body: Record<string, string> = {
      target: "openai_compatible",
      base_url: draftValue("ai.openai_compatible.base_url"),
    };
    if (pending["ai.openai_compatible.api_key"]) {
      body.api_key = pending["ai.openai_compatible.api_key"];
    }
    const path = kind === "test" ? "/api/admin/ai/test-connection" : "/api/admin/ai/models";
    const result = await api<{ ok?: boolean; detail?: string; models?: string[]; provider: string; key_configured?: boolean }>(
      path,
      { method: "POST", body: JSON.stringify(body) },
    );
    setAiResult(
      `${result.provider}: ${result.detail || ""}`.trim() +
        (result.key_configured ? " · API key: configured" : " · API key: not configured"),
    );
    if (result.models) setModels(result.models);
    if (kind === "discover" && result.ok === false) onError(result.detail || "Discovery failed");
  }

  const options = unique([
    ...models,
    draftValue("ai.openai_compatible.model"),
    ...ROLE_ORDER.map((item) => draftValue(item.key)).filter(Boolean),
  ]);

  return (
    <section className="card" style={{ marginTop: 8 }} aria-labelledby="open-webui-heading">
      <h2 id="open-webui-heading">Open WebUI / OpenAI-compatible</h2>
      <p className="lede">
        Store the API key as a secret reference, test the <code>/v1</code> endpoint (no matter documents are sent),
        discover models, then assign each role. Changes still go through <strong>Validate &amp; preview draft</strong>{" "}
        → confirm → apply.
      </p>
      <aside className="banner" aria-label="Linux Docker help">
        From RockHawk Compose on Linux, Open WebUI on the host is not <code>localhost</code> inside the api/worker
        containers. Use <code>http://host.docker.internal:&lt;port&gt;/v1</code> (Compose sets{" "}
        <code>extra_hosts: host.docker.internal:host-gateway</code>) or the docker0 address{" "}
        <code>http://172.17.0.1:&lt;port&gt;/v1</code>. Match the port Open WebUI publishes on the host (often 8080,
        which is also RockHawk’s UI port — use Open WebUI’s actual published port).
      </aside>
      {providerLocked ? (
        <p className="banner warn" role="status">
          AI provider is pinned by <code>ROCKHAWK_PIN_AI_SETTINGS</code>. You can still store the Open WebUI URL and
          key here for later. Unset that pin to switch the active provider from this page.
        </p>
      ) : (
        <label className="field">
          Active provider
          <select value={draftValue("ai.provider", "mock")} onChange={(e) => setDraft("ai.provider", e.target.value)}>
            <option value="mock">mock (on-box, no network)</option>
            <option value="openai_compatible">openai_compatible (Open WebUI /v1)</option>
          </select>
        </label>
      )}
      <label className="field">
        Base URL
        <input
          value={draftValue("ai.openai_compatible.base_url")}
          onChange={(e) => setDraft("ai.openai_compatible.base_url", e.target.value)}
          placeholder="http://host.docker.internal:8080/v1"
        />
      </label>
      <label className="field">
        API key
        <input
          type="password"
          autoComplete="new-password"
          value={pending["ai.openai_compatible.api_key"] || ""}
          placeholder={secretStatus(key)}
          onChange={(e) => setDraft("ai.openai_compatible.api_key", e.target.value)}
        />
      </label>
      <p className="lede">{secretStatus(key)}. Leave the field blank to keep the stored reference.</p>
      <div className="toolbar">
        <button className="btn secondary" type="button" onClick={() => probe("test").catch((err) => onError(err.message))}>
          Test Connection
        </button>
        <button className="btn ghost" type="button" onClick={() => probe("discover").catch((err) => onError(err.message))}>
          Discover models
        </button>
      </div>
      {aiResult && <p role="status">{aiResult}</p>}
      <label className="field">
        Default chat model
        <ModelPicker
          value={draftValue("ai.openai_compatible.model")}
          options={options}
          allowEmpty={false}
          onChange={(value) => setDraft("ai.openai_compatible.model", value)}
        />
      </label>
      <h3>Role assignments</h3>
      <p className="lede">Each role can use a discovered model or a typed id. Empty inherits the default chat model.</p>
      <div className="grid">
        {ROLE_ORDER.map((item) => (
          <label key={item.key} className="field">
            {item.label}
            <ModelPicker
              value={draftValue(item.key)}
              options={options}
              allowEmpty
              onChange={(value) => setDraft(item.key, value)}
            />
          </label>
        ))}
      </div>
      {base?.source && (
        <p className="status">
          Effective URL source: {base.source}
          {model?.source ? ` · default model source: ${model.source}` : ""}
        </p>
      )}
    </section>
  );
}

function ModelPicker({
  value,
  options,
  allowEmpty,
  onChange,
}: {
  value: string;
  options: string[];
  allowEmpty: boolean;
  onChange: (value: string) => void;
}) {
  const listed = options.includes(value);
  return (
    <span className="model-picker">
      <select
        value={listed || !value ? value : "__manual__"}
        onChange={(e) => {
          if (e.target.value === "__manual__") return;
          onChange(e.target.value);
        }}
      >
        {allowEmpty && <option value="">Use default chat model</option>}
        {options.filter(Boolean).map((item) => (
          <option key={item} value={item}>
            {item}
          </option>
        ))}
        <option value="__manual__">Other… (type below)</option>
      </select>
      <input
        aria-label="Manual model id"
        value={value}
        placeholder="Optional manual model id"
        onChange={(e) => onChange(e.target.value)}
      />
    </span>
  );
}

function unique(items: string[]) {
  return [...new Set(items.filter(Boolean))];
}
