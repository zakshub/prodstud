import React, { useEffect, useState } from "react";
import type { ApprovalQuote, BatchApprovalQuote } from "../api/types";
import { StatusBadge } from "./StatusBadge";

interface Props {
  quote?: ApprovalQuote | null;
  batchQuote?: BatchApprovalQuote | null;
  submitting: boolean;
  onCancel: () => void;
  onConfirm: () => void;
}

export const ApprovalModal: React.FC<Props> = ({ quote, batchQuote, submitting, onCancel, onConfirm }) => {
  const [checked, setChecked] = useState(false);

  useEffect(() => {
    setChecked(false);
  }, [quote?.quote_id, batchQuote?.batch_quote_id]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape" && !submitting) onCancel();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onCancel, submitting]);

  if (!quote && !batchQuote) return null;

  if (batchQuote) {
    const hasItemErrors = batchQuote.items.some((it) => it.validation_errors.length > 0);
    const blocked = !batchQuote.spend_guard_allows || !batchQuote.credential_ready || hasItemErrors;
    return (
      <div className="modal-backdrop" role="dialog" aria-modal="true" aria-labelledby="approval-modal-title">
        <div className="modal-dialog">
          <div className="section-head">
            <h2 id="approval-modal-title">Combined Batch Generation Approval Gate</h2>
            {!batchQuote.has_billable_items ? (
              <StatusBadge status="warning" label={`LOCAL TEST BATCH · ${batchQuote.total_requested_outputs} OUTPUTS · $0.00`} />
            ) : (
              <StatusBadge status="awaiting_approval" label={`BILLABLE BATCH · ${batchQuote.total_requested_outputs} OUTPUTS`} />
            )}
          </div>

          <p className="muted" style={{ margin: 0 }}>
            Review every queued plan, model, output count, and the combined spend impact before authorizing batch execution.
            Execution halts automatically without retry on uncertain timeouts or spend-guard limits.
          </p>

          <div className="subpanel">
            <div className="table-wrap">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Plan</th>
                    <th>Model</th>
                    <th>Outputs</th>
                    <th>Subtotal</th>
                  </tr>
                </thead>
                <tbody>
                  {batchQuote.items.map((it) => (
                    <tr key={it.plan_id}>
                      <td>
                        <div className="small-mono">{it.plan_id}</div>
                        <div className="muted" style={{ fontSize: 12 }}>{it.plan_summary.slice(0, 72)}</div>
                      </td>
                      <td className="mono">{it.model_id}</td>
                      <td className="mono">{it.variation_count}</td>
                      <td className="mono">
                        {it.subtotal_estimated_cost_usd === null
                          ? "Dynamic"
                          : `$${it.subtotal_estimated_cost_usd.toFixed(4)}`}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          <div className="subpanel">
            <div className="kv-grid">
              <span className="kv-key">Total Outputs</span>
              <span className="mono">{batchQuote.total_requested_outputs} asset(s)</span>
              <span className="kv-key">Combined Estimated Cost</span>
              <span className="mono">
                {batchQuote.total_estimated_cost_usd === null
                  ? "Includes dynamic token-billed items (verify pricing before approval)"
                  : `$${batchQuote.total_estimated_cost_usd.toFixed(4)} USD`}
              </span>
              <span className="kv-key">Spend Guard</span>
              <span>
                <StatusBadge status={batchQuote.spend_guard_allows ? "supported" : "blocking"} label={batchQuote.spend_guard_allows ? "ALLOWED" : "BLOCKED"} />{" "}
                <span className="muted">{batchQuote.spend_guard_reason}</span>
              </span>
              <span className="kv-key">Server Credentials</span>
              <span>
                <StatusBadge status={batchQuote.credential_ready ? "active" : "blocking"} label={batchQuote.credential_ready ? "READY" : "MISSING"} />{" "}
                <span className="muted">{batchQuote.credential_reason}</span>
              </span>
            </div>
          </div>

          {batchQuote.feasibility_warnings.length > 0 && (
            <div className="callout callout-warning">
              <strong>Batch Feasibility Warnings:</strong>
              <ul style={{ margin: "6px 0 0 18px", padding: 0 }}>
                {batchQuote.feasibility_warnings.map((w, idx) => (
                  <li key={idx}>{w}</li>
                ))}
              </ul>
            </div>
          )}

          {blocked && (
            <div className="callout callout-danger">
              <strong>Batch Blocked by Policy Gate:</strong> Resolve credential, daily spend cap, or plan validation issues before executing.
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
              I explicitly approve submitting all {batchQuote.total_requested_outputs} output(s) in this batch with the disclosed
              combined cost policy. Remaining outputs will halt automatically if any job enters UNKNOWN or spend-cap state.
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
              {submitting ? "Executing Batch..." : `Approve & Execute Batch (${batchQuote.total_requested_outputs})`}
            </button>
          </div>
        </div>
      </div>
    );
  }

  assertQuote(quote);
  const blocked = !quote.spend_guard_allows || !quote.credential_ready;
  const varCount = quote.variation_count ?? 1;

  return (
    <div className="modal-backdrop" role="dialog" aria-modal="true" aria-labelledby="approval-modal-title">
      <div className="modal-dialog">
        <div className="section-head">
          <h2 id="approval-modal-title">Explicit Generation Approval Gate</h2>
          {quote.is_local_test_fixture ? (
            <StatusBadge status="warning" label={`LOCAL TEST FIXTURE · ${varCount}× · $0.00`} />
          ) : (
            <StatusBadge status="awaiting_approval" label={varCount > 1 ? `BILLABLE · ${varCount} VARIATIONS` : "BILLABLE REQUEST"} />
          )}
        </div>

        <p className="muted" style={{ margin: 0 }}>
          Verify provider, model, output count, settings, and billing impact before authorizing execution. No request is
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
            <span className="kv-key">Media &amp; Output Count</span>
            <span className="mono">
              {quote.media_type.toUpperCase()} · {varCount} output{varCount > 1 ? "s (variation set)" : ""}
            </span>
            <span className="kv-key">Estimated Total Cost</span>
            <span className="mono">
              {quote.estimated_cost_usd === null
                ? "Dynamic token billing (see pricing note)"
                : varCount > 1 && quote.unit_estimated_cost_usd !== null
                  ? `$${quote.unit_estimated_cost_usd.toFixed(4)} × ${varCount} = $${quote.estimated_cost_usd.toFixed(4)} USD`
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
                <span className="mono">{v === null || v === undefined ? "—" : String(v)}</span>
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
            I explicitly approve submitting {varCount > 1 ? `these ${varCount} variation outputs` : "this generation request"} with the
            disclosed provider, model, settings, and cost policy. I understand automatic paid retries are disabled on uncertain timeouts.
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
            {submitting
              ? "Submitting Job..."
              : varCount > 1
                ? `Approve & Generate ${varCount} Variations`
                : "Approve & Generate"}
          </button>
        </div>
      </div>
    </div>
  );
};

function assertQuote(q: ApprovalQuote | null | undefined): asserts q is ApprovalQuote {
  if (!q) throw new Error("Missing approval quote");
}
