import { FormEvent, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, setToken } from "../api/client";
import { Logo } from "../components/Logo";

type LoginToken = { access_token: string; must_change_password: boolean };

export function LoginPage() {
  const navigate = useNavigate();
  const [email, setEmail] = useState("admin@rockhawk.local");
  const [password, setPassword] = useState("ChangeMeNow!");
  const [error, setError] = useState("");

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setError("");
    try {
      const token = await api<LoginToken>("/api/auth/login", {
        method: "POST",
        body: JSON.stringify({ email, password }),
      });
      setToken(token.access_token);
      navigate("/matters");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Login failed");
    }
  }

  return (
    <div className="login-wrap">
      <div className="card login-card">
        <Logo />
        <h1>RockHawk Review Tables</h1>
        <p className="lede">Local attorney-assistance workspace. Grounded answers only. Not a substitute for legal judgment.</p>
        <div className="banner warn" role="alert">
          Development credentials are published for first run. Change the admin password before any shared or networked use.
        </div>
        <form onSubmit={onSubmit} aria-describedby={error ? "login-error" : undefined}>
          <div className="grid" style={{ gap: 12, margin: "16px 0" }}>
            <label className="field">
              Email
              <input name="email" type="email" autoComplete="username" value={email} onChange={(e) => setEmail(e.target.value)} required />
            </label>
            <label className="field">
              Password
              <input
                name="password"
                type="password"
                autoComplete="current-password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
              />
            </label>
          </div>
          {error && (
            <p id="login-error" role="alert">
              {error}
            </p>
          )}
          <button className="btn" type="submit">
            Sign in
          </button>
        </form>
      </div>
    </div>
  );
}
