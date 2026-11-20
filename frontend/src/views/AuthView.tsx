import React, { useState } from "react";
import { api } from "../api/client";
import type { UserProfile } from "../api/types";

interface Props {
  theme: "dark" | "light";
  onToggleTheme: () => void;
  onAuthenticated: (user: UserProfile) => void;
}

export const AuthView: React.FC<Props> = ({ theme, onToggleTheme, onAuthenticated }) => {
  const [mode, setMode] = useState<"login" | "register">("register");
  const [email, setEmail] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      if (mode === "register") {
        const res = await api.register({ email, display_name: displayName, password });
        onAuthenticated(res.user);
      } else {
        const res = await api.login({ email, password });
        onAuthenticated(res.user);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Authentication failed.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <main className="auth-shell">
      <section className="auth-card" aria-labelledby="auth-heading">
        <div className="auth-brand">
          <div className="brand-mark">
            <span className="brand-dot" aria-hidden="true" />
            <span>Production Studio</span>
          </div>
          <button type="button" className="btn btn-sm" onClick={onToggleTheme}>
            {theme === "dark" ? "Light Mode" : "Dark Mode"}
          </button>
        </div>

        <h1 id="auth-heading" style={{ marginBottom: 6 }}>
          {mode === "register" ? "Create Studio Account" : "Sign In to Production Studio"}
        </h1>
        <p className="muted" style={{ marginTop: 0, marginBottom: 20 }}>
          Focused image and video production workbench powered by the 170-Protocol Production Intelligence Engine.
        </p>

        <div className="callout callout-info" style={{ marginBottom: 18, fontSize: 12 }}>
          <strong>Default Spend Safety ($0.00):</strong> New accounts start with a hard{" "}
          <span className="mono">$0.00</span> daily spend cap. Server-side API keys are encrypted at rest and never
          exposed to the browser.
        </div>

        <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: 14 }}>
          {mode === "register" && (
            <div className="field">
              <label htmlFor="auth-name">Display Name</label>
              <input
                id="auth-name"
                className="input"
                type="text"
                required
                value={displayName}
                onChange={(e) => setDisplayName(e.target.value)}
                placeholder="e.g. Creative Director"
              />
            </div>
          )}

          <div className="field">
            <label htmlFor="auth-email">Email Address</label>
            <input
              id="auth-email"
              className="input"
              type="email"
              required
              autoComplete="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="director@studio.local"
            />
          </div>

          <div className="field">
            <label htmlFor="auth-password">Password (min 8 characters)</label>
            <input
              id="auth-password"
              className="input"
              type="password"
              required
              minLength={8}
              autoComplete={mode === "register" ? "new-password" : "current-password"}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••••"
            />
          </div>

          {error && (
            <div className="callout callout-danger" role="alert">
              {error}
            </div>
          )}

          <button id="auth-submit-btn" type="submit" className="btn btn-primary" disabled={busy}>
            {busy ? "Please wait..." : mode === "register" ? "Create Account & Enter Workspace" : "Sign In"}
          </button>
        </form>

        <div style={{ marginTop: 18, paddingTop: 14, borderTop: "1px solid var(--border-subtle)", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <span className="muted" style={{ fontSize: 12 }}>
            {mode === "register" ? "Already have an account?" : "Need a local studio account?"}
          </span>
          <button
            type="button"
            className="btn btn-sm"
            onClick={() => {
              setMode(mode === "register" ? "login" : "register");
              setError(null);
            }}
          >
            {mode === "register" ? "Switch to Sign In" : "Create Account"}
          </button>
        </div>
      </section>
    </main>
  );
};
