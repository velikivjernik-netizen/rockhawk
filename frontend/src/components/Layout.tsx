import { useEffect, useState } from "react";
import { NavLink, Outlet, useParams } from "react-router-dom";
import { api, getToken, setToken, User } from "../api/client";
import { Logo } from "./Logo";

export function Layout() {
  const { matterId } = useParams();
  const authed = Boolean(getToken());
  const [me, setMe] = useState<User | null>(null);

  useEffect(() => {
    if (!authed) return;
    api<User>("/api/auth/me")
      .then(setMe)
      .catch(() => setMe(null));
  }, [authed]);

  return (
    <div className="app-shell">
      <a className="skip-link" href="#main">
        Skip to content
      </a>
      <aside className="sidebar" aria-label="Primary">
        <NavLink to={authed ? "/matters" : "/login"} className="brand">
          <Logo />
          <span>
            <div className="brand-name">RockHawk</div>
            <div className="brand-tag">Review Tables</div>
          </span>
        </NavLink>
        <nav>
          <NavLink className="nav-link" to="/matters">
            Matters
          </NavLink>
          {me?.role === "admin" && (
            <NavLink className="nav-link" to="/admin">
              Administration
            </NavLink>
          )}
          {matterId && (
            <>
              <NavLink className="nav-link" to={`/matters/${matterId}`}>
                Matter home
              </NavLink>
              <NavLink className="nav-link" to={`/matters/${matterId}/hot`}>
                Hot Review
              </NavLink>
              <NavLink className="nav-link" to={`/matters/${matterId}/audit`}>
                Audit trail
              </NavLink>
            </>
          )}
        </nav>
        <p className="sidebar-foot">
          Attorney assistance only. RockHawk does not make legal determinations. Verify every cell before reliance.
          {me && (
            <button
              className="btn ghost"
              type="button"
              style={{ marginTop: 12, width: "100%" }}
              onClick={() => {
                setToken(null);
                window.location.assign("/login");
              }}
            >
              Sign out {me.name}
            </button>
          )}
        </p>
      </aside>
      <main id="main" className="main">
        <Outlet />
      </main>
    </div>
  );
}
