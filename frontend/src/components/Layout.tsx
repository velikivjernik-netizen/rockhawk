import { NavLink, Outlet, useParams } from "react-router-dom";
import { Logo } from "./Logo";
import { getToken } from "../api/client";

export function Layout() {
  const { matterId } = useParams();
  const authed = Boolean(getToken());
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
        </p>
      </aside>
      <main id="main" className="main">
        <Outlet />
      </main>
    </div>
  );
}
