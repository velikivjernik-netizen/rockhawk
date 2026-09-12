import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { api, AuditEvent } from "../api/client";

export function AuditPage() {
  const { matterId } = useParams();
  const [events, setEvents] = useState<AuditEvent[]>([]);
  const [error, setError] = useState("");

  useEffect(() => {
    api<AuditEvent[]>(`/api/audit?matter_id=${matterId}`)
      .then(setEvents)
      .catch((err) => setError(err.message));
  }, [matterId]);

  return (
    <div>
      <h1 className="page-title">Immutable audit trail</h1>
      <p className="lede">Append-only events. Application code never updates or deletes these rows.</p>
      {error && <p role="alert">{error}</p>}
      <div className="table-wrap">
        <table className="review">
          <thead>
            <tr>
              <th>When</th>
              <th>Action</th>
              <th>Entity</th>
            </tr>
          </thead>
          <tbody>
            {events.map((event) => (
              <tr key={event.id}>
                <td>{new Date(event.created_at).toLocaleString()}</td>
                <td>{event.action}</td>
                <td>
                  {event.entity_type} {event.entity_id.slice(0, 8)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
