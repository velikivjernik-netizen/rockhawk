const TOKEN_KEY = "rockhawk.token";

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string | null) {
  if (token) localStorage.setItem(TOKEN_KEY, token);
  else localStorage.removeItem(TOKEN_KEY);
}

export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  if (!(init.body instanceof FormData) && !headers.has("Content-Type") && init.body) {
    headers.set("Content-Type", "application/json");
  }
  const token = getToken();
  if (token) headers.set("Authorization", `Bearer ${token}`);
  const response = await fetch(path, { ...init, headers });
  if (response.status === 401) {
    setToken(null);
    if (!path.includes("/auth/login")) window.location.assign("/login");
  }
  if (!response.ok) {
    let detail = response.statusText;
    try {
      const body = await response.json();
      detail = body.detail || JSON.stringify(body);
    } catch {
      detail = await response.text();
    }
    throw new Error(detail);
  }
  if (response.status === 204) return undefined as T;
  const contentType = response.headers.get("content-type") || "";
  if (contentType.includes("application/json")) return response.json() as Promise<T>;
  return response as T;
}

export type User = {
  id: string;
  email: string;
  name: string;
  role: string;
  must_change_password: boolean;
  admin_scopes?: string[] | null;
};

export type DocumentOut = {
  id: string;
  matter_id: string;
  filename: string;
  content_type: string;
  page_count: number;
  status: string;
  content_hash?: string;
  byte_size?: number;
};

export type Matter = {
  id: string;
  name: string;
  description: string;
  client_name: string;
  opposing_party: string;
  status: string;
};

export type Column = {
  id: string;
  name: string;
  value_type: string;
  instruction: string;
  enum_options?: string[] | null;
  condition_column_id: string | null;
  condition_equals: string | null;
  sort_order?: number;
  citation_policy?: string;
  model_role?: string;
  prompt_key?: string;
  prompt_version?: string | null;
  overwrite_policy?: string;
  required?: boolean;
  validation_json?: Record<string, unknown> | null;
};

export type ColumnDraft = Omit<Column, "id"> & { id?: string };

export type Citation = {
  document_id: string;
  document_name: string;
  page: number;
  quote: string;
};

export type Comment = {
  id: string;
  body: string;
  created_at: string;
  user?: User;
};

export type Cell = {
  id: string;
  row_id: string;
  column_id: string;
  value: string;
  status: string;
  verified: boolean;
  flagged: boolean;
  assigned_to_id: string | null;
  citations: Citation[];
  evidence_quote: string;
  comments: Comment[];
};

export type Row = {
  id: string;
  document_id: string;
  is_hot: boolean;
  document?: { id: string; filename: string; page_count: number };
  cells: Cell[];
};

export type TableDetail = {
  id: string;
  matter_id: string;
  name: string;
  description: string;
  hot_include_flagged?: boolean;
  hot_include_manual?: boolean;
  hot_min_flagged?: number;
  columns: Column[];
  rows: Row[];
};

export type EffectiveSetting = {
  key: string;
  value: unknown;
  source: string;
  overridden: boolean;
  restart_required: boolean;
  secret: boolean;
  editability: string;
  risk: string;
};

export type RegistrySetting = {
  key: string;
  category: string;
  category_label: string;
  label: string;
  description: string;
  value_type: string;
  default: unknown;
  risk: string;
  editability: string;
  restart_required: boolean;
  secret: boolean;
  enum_options: string[] | null;
  todo?: boolean;
};

export type HotItem = {
  row_id: string;
  document_id: string;
  filename: string;
  flagged_cells: number;
  is_hot: boolean;
  table_id: string;
  table_name: string;
};

export type AuditEvent = {
  id: string;
  action: string;
  entity_type: string;
  entity_id: string;
  created_at: string;
  payload: Record<string, unknown>;
};
