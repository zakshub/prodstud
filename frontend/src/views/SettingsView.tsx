import React, { useEffect, useState } from "react";
import { api } from "../api/client";
import type {
  AuditEventRecord,
  CredentialSummary,
  ProviderModelCapability,
  UserProfile,
} from "../api/types";
import { StatusBadge } from "../components/StatusBadge";

interface Props {
  user: UserProfile;
  capabilities: ProviderModelCapability[];
  theme: "dark" | "light";
  onToggleTheme: () => void;
  onUserUpdated: (user: UserProfile) => void;
}

export const SettingsView: React.FC<Props> = ({
  user,
  capabilities,
  theme,
  onToggleTheme,
  onUserUpdated,
}) => {
  const [displayName, setDisplayName] = useState(user.display_name);
  const [spendCap, setSpendCap] = useState(String(user.daily_spend_cap_usd.toFixed(2)));
  const [apiKeyInput, setApiKeyInput] = useState("");
  const [credentials, setCredentials] = useState<CredentialSummary[]>([]);
  const [auditEvents, setAuditEvents] = useState<AuditEventRecord[]>([]);
  const [notice, setNotice] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const refresh = async () => {
    const [creds, events] = await Promise.all([api.listCredentials(), api.listAudit()]);
    setCredentials(creds);
    setAuditEvents(events);
  };

  useEffect(() => {
    refresh();
  }, []);

  const handleSaveSettings = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setNotice(null);
    setBusy(true);
    try {
      const updated = await api.updateSettings({
        display_name: displayName.trim(),
        daily_spend_cap_usd: Math.max(0, Number(spendCap) || 0),
        preferred_theme: theme,
      });
      onUserUpdated(updated);
      setNotice("Profile and Spend Guard settings updated.");
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save settings.");
    } finally {
      setBusy(false);
    }
  };

  const handleSaveGoogleKey = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!apiKeyInput.trim()) return;
    setError(null);
    setNotice(null);
    setBusy(true);
    try {
      const saved = await api.saveCredential("google", apiKeyInput.trim());
      setApiKeyInput(""); // Immediately clear secret from browser memory
      setNotice(`Google API key encrypted server-side (${saved.masked_key}). Plaintext is never returned to browser.`);
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save credential.");
    } finally {
      setBusy(false);
    }
  };

  const handleValidate = async (provider: string) => {
    setBusy(true);
    setError(null);
    try {
      const res = await api.validateCredential(provider);
      setNotice(`${provider} validation: ${res.valid ? "VALID" : "INVALID"} — ${res.note}`);
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Validation failed.");
    } finally {
      setBusy(false);
    }
  };

  const handleRevoke = async (provider: string) => {
    if (!window.confirm(`Revoke stored server-side credential for '${provider}'?`)) return;
    setBusy(true);
    try {
      await api.revokeCredential(provider);
      setNotice(`Credential for '${provider}' revoked and wiped from encrypted vault.`);
      await refresh();
    } finally {
      setBusy(false);
    }
  };

  return (
    <main className="page-container">
      <div className="section-head">
        <div>
          <h1>Settings, Credentials &amp; Spend Governance</h1>
          <p className="muted" style={{ margin: "4px 0 0" }}>
            API keys are encrypted server-side using Fernet (AES-128-CBC + HMAC-SHA256) and never stored in browser storage.
          </p>
        </div>
        <button type="button" className="btn btn-sm" onClick={onToggleTheme}>
          Appearance: {theme === "dark" ? "Calibrated Studio Dark" : "Archival Proofing Light"}
        </button>
      </div>

      {notice && <div className="callout callout-info">{notice}</div>}
      {error && <div className="callout callout-danger">{error}</div>}

      <div className="form-grid-2">
        {/* Profile & Hard Spend Guard */}
        <section className="panel" aria-label="Profile and Spend Guard">
          <h2>Profile &amp; Daily Spend Guard</h2>
          <form onSubmit={handleSaveSettings} style={{ display: "flex", flexDirection: "column", gap: 12 }}>
            <div className="field">
              <label htmlFor="set-name">Display Name</label>
              <input id="set-name" className="input" value={displayName} onChange={(e) => setDisplayName(e.target.value)} />
            </div>
            <div className="field">
              <label htmlFor="set-cap">Daily Spend Cap (USD — $0.00 hard-blocks paid calls)</label>
              <input
                id="set-cap"
                type="number"
                min={0}
                max={10000}
                step="0.25"
                className="input mono"
                value={spendCap}
                onChange={(e) => setSpendCap(e.target.value)}
              />
            </div>
            <div className="small-mono">
              Recorded spend today: ${user.spent_today_usd.toFixed(4)} / ${user.daily_spend_cap_usd.toFixed(2)} USD
            </div>
            <button type="submit" className="btn btn-primary btn-sm" disabled={busy}>
              Save Profile &amp; Spend Cap
            </button>
          </form>
        </section>

        {/* Server-Side Encrypted Provider Credential Vault */}
        <section className="panel" aria-label="Provider Credentials Vault">
          <h2>Server-Side Provider Credentials</h2>
          <form onSubmit={handleSaveGoogleKey} style={{ display: "flex", flexDirection: "column", gap: 12 }}>
            <div className="field">
              <label htmlFor="google-api-key">Google Gemini API Key (x-goog-api-key)</label>
              <input
                id="google-api-key"
                type="password"
                className="input mono"
                autoComplete="off"
                value={apiKeyInput}
                onChange={(e) => setApiKeyInput(e.target.value)}
                placeholder="AIza... (encrypted immediately on server)"
              />
            </div>
            <button type="submit" className="btn btn-primary btn-sm" disabled={busy || !apiKeyInput.trim()}>
              Save / Replace Encrypted Key
            </button>
          </form>

          {credentials.length > 0 && (
            <div className="subpanel">
              <h3>Stored Credentials</h3>
              {credentials.map((c) => (
                <div key={c.provider} style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
                  <div>
                    <div className="btn-row">
                      <strong className="mono">{c.provider}</strong>
                      <span className="small-mono">{c.masked_key}</span>
                      <StatusBadge status={c.status} />
                    </div>
                    {c.validation_note && <div className="muted" style={{ fontSize: 12 }}>{c.validation_note}</div>}
                  </div>
                  {c.status === "active" && (
                    <div className="btn-row">
                      <button type="button" className="btn btn-sm" disabled={busy} onClick={() => handleValidate(c.provider)}>
                        Validate
                      </button>
                      <button type="button" className="btn btn-danger btn-sm" disabled={busy} onClick={() => handleRevoke(c.provider)}>
                        Revoke
                      </button>
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </section>
      </div>

      {/* Verified Provider Capability Registry */}
      <section className="panel" aria-label="Verified Provider Capability Matrix">
        <h2>Verified Provider Capability Matrix (Official Docs Checked 2026-11-19)</h2>
        <div className="table-wrap">
          <table className="data-table">
            <thead>
              <tr>
                <th>Media</th>
                <th>Model ID</th>
                <th>Status</th>
                <th>Formats &amp; Limits</th>
                <th>Pricing &amp; Limitations</th>
              </tr>
            </thead>
            <tbody>
              {capabilities.map((c) => (
                <tr key={`${c.provider_id}::${c.model_id}`}>
                  <td className="mono">{c.media_type.toUpperCase()}</td>
                  <td>
                    <div className="mono"><strong>{c.model_id}</strong></div>
                    <div className="muted" style={{ fontSize: 12 }}>{c.display_name}</div>
                  </td>
                  <td><StatusBadge status={c.support_status} /></td>
                  <td className="small-mono">
                    {c.supported_resolutions.length > 0 ? c.supported_resolutions.join(", ") : "N/A"}
                    {c.max_duration_s ? ` · ${c.min_duration_s}–${c.max_duration_s}s` : ""}
                    {c.max_reference_images > 0 ? ` · max ${c.max_reference_images} refs` : ""}
                  </td>
                  <td>
                    <div style={{ fontSize: 12 }}>{c.pricing_note}</div>
                    <div className="muted" style={{ fontSize: 11 }}>{c.limitations.join(" ")}</div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      {/* Immutable Secret-Redacted Audit Log */}
      <section className="panel" aria-label="Audit Trail">
        <h2>Immutable Audit Trail (Recent {auditEvents.length} Events — Secret-Redacted)</h2>
        <div className="table-wrap">
          <table className="data-table">
            <thead>
              <tr>
                <th>Timestamp</th>
                <th>Event</th>
                <th>Entity</th>
                <th>Details</th>
              </tr>
            </thead>
            <tbody>
              {auditEvents.slice(0, 25).map((e) => (
                <tr key={e.id}>
                  <td className="small-mono" style={{ whiteSpace: "nowrap" }}>{e.created_at}</td>
                  <td className="mono">{e.event_type}</td>
                  <td className="small-mono">{e.entity_type}:{e.entity_id}</td>
                  <td className="small-mono">{JSON.stringify(e.payload)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </main>
  );
};
