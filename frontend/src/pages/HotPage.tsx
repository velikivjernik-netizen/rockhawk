import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api, HotItem } from "../api/client";

export function HotPage() {
  const { matterId } = useParams();
  const [items, setItems] = useState<HotItem[]>([]);
  const [error, setError] = useState("");

  useEffect(() => {
    api<HotItem[]>(`/api/matters/${matterId}/hot`)
      .then(setItems)
      .catch((err) => setError(err.message));
  }, [matterId]);

  return (
    <div>
      <h1 className="page-title">Hot Review</h1>
      <p className="lede">Documents marked hot or cells flagged for attorney attention.</p>
      {error && <p role="alert">{error}</p>}
      <ul>
        {items.map((item) => (
          <li key={item.row_id} className="card" style={{ marginBottom: 12 }}>
            <span className="hot-dot" aria-hidden />
            <strong>{item.filename}</strong> · {item.table_name} · {item.flagged_cells} flagged cell
            {item.flagged_cells === 1 ? "" : "s"}
            <div>
              <Link to={`/matters/${matterId}/tables/${item.table_id}`}>Open table</Link>
            </div>
          </li>
        ))}
        {items.length === 0 && <p>Nothing in the hot queue.</p>}
      </ul>
    </div>
  );
}
