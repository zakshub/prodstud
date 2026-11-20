import React, { useEffect, useState } from "react";
import type { ApprovalQuote } from "../api/types";
import { StatusBadge } from "./StatusBadge";

interface Props {
  quote: ApprovalQuote;
  submitting: boolean;
  onCancel: () => void;
  onConfirm: () => void;
}

export const ApprovalModal: React.FC<Props> = ({ quote, submitting, onCancel, onConfirm }) => {
  const [checked, setChecked] = useState(false);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape" && !submitting) onCancel();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onCancel, submitting]);

  const blocked = !quote.spend_guard_allows || !quote.credential_ready;

  return (
    <div className="modal-backdrop" role="dialog" aria-modal="true" aria-labelledby="approval-modal-title">
      <div className="modal-dialog">
        <div className="section-head">
          <h2 id="approval-modal-title">Explicit Generation Approval Gate</h2>
          {quote.is_local_test_fixture ? (
            <StatusBadge status="warning" label="LOCAL TEST FIXTURE · $0.00" />
          ) : (
            <StatusBadge status="awaiting_approval" label="BILLABLE REQUEST" />
          )}
        </div>

        <p className="muted" style={{ margin: 0 }}>
          Verify provider, model, output parameters, and billing impact before authorizing execution. No request is
          submitted until you explicitly confirm below.
        </p>

        {quote.is_local_test_fixture && (
          <div className="callout callout-info">
            <strong>Non-Billable Local Test Render:</strong> This fixture produces deterministic PNG/MP4 workflow
            verification assets locally at <strong>$0.00</strong>. It does not invoke Google live generation APIs.
          </div>
        )}

        <div className="subpanel">
          <div className="kv-grid">
            <span className="kv-key">Provider</span>
            <span className="mono">{quote.provider_id}</span>
            <span className="kv-key">Model</span>
            <span className="mono">{quote.model_id}</span>
            <span className="kv-key">Media Type</span>
            <span className="mono">{quote.media_type.toUpperCase()}</span>
            <span className="kv-key">Estimated Cost</span>
            <span className="mono">
              {quote.estimated_cost_usd === null
                ? "Dynamic token billing (see pricing note)"
                : `$${quote.estimated_cost_usd.toFixed(4)} USD`}
            </span>
            <span className="kv-key">Spend Guard</span>
            <span>
              <StatusBadge status={quote.spend_guard_allows ? "supported" : "blocking"} label={quote.spend_guard_allows ? "ALLOWED" : "BLOCKED"} />{" "}
              <span className="muted">{quote.spend_guard_reason}</span>
            </span>
            <span className="kv-key">Server Credential</span>
            <span>
              <StatusBadge status={quote.credential_ready ? "active" : "blocking"} label={quote.credential_ready ? "READY" : "MISSING"} />{" "}
              <span className="muted">{quote.credential_reason}</span>
            </span>
          </div>
        </div>

        <div className="subpanel">
          <h3>Approved Generation Settings</h3>
          <div className="kv-grid">
            {Object.entries(quote.settings_summary).map(([k, v]) => (
              <React.Fragment key={k}>
                <span className="kv-key">{k.replace(/_/g, " ")}</span>
                <span className="mono">{String(v)}</span>
              </React.Fragment>
            ))}
          </div>
          <p className="muted" style={{ margin: "6px 0 0", fontSize: 12 }}>
            <strong>Pricing Disclosure:</strong> {quote.pricing_disclosure}
          </p>
        </div>

        {quote.feasibility_warnings.length > 0 && (
          <div className="callout callout-warning">
            <strong>Feasibility &amp; Capability Warnings:</strong>
            <ul style={{ margin: "6px 0 0 18px", padding: 0 }}>
              {quote.feasibility_warnings.map((w, idx) => (
                <li key={idx}>{w}</li>
              ))}
            </ul>
          </div>
        )}

        {blocked && (
          <div className="callout callout-danger">
            <strong>Submission Blocked by Policy Gate:</strong> Resolve the credential or daily spend cap requirement in{" "}
            <strong>Settings</strong> (or select the non-billable local test fixture for offline testing).
          </div>
        )}

        <label style={{ display: "flex", alignItems: "flex-start", gap: 10, cursor: blocked ? "not-allowed" : "pointer" }}>
          <input
            id="confirm-generation-checkbox"
            type="checkbox"
            disabled={blocked || submitting}
            checked={checked}
            onChange={(e) => setChecked(e.target.checked)}
            style={{ marginTop: 3 }}
          />
          <span>
            I explicitly approve submitting this generation request with the disclosed provider, model, settings, and cost
            policy. I understand automatic paid retries are disabled on uncertain timeouts.
          </span>
        </label>

        <div className="btn-row" style={{ justifyContent: "flex-end" }}>
          <button type="button" className="btn" onClick={onCancel} disabled={submitting}>
            Cancel
          </button>
          <button
            id="confirm-submit-generation-btn"
            type="button"
            className="btn btn-primary"
            disabled={blocked || !checked || submitting}
            onClick={onConfirm}
          >
            {submitting ? "Submitting Job..." : "Approve & Generate"}
          </button>
        </div>
      </div>
    </div>
  );
};
