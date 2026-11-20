import React, { useEffect, useState } from "react";
import { api } from "../api/client";
import type { QualityReviewRecord, VisionQCQuote } from "../api/types";
import { StatusBadge } from "./StatusBadge";

interface Props {
  review: QualityReviewRecord;
  onFeedback: (reviewId: string, status: "accepted" | "rejected" | "needs_rework", note: string) => Promise<void>;
  onVisionQCComplete?: (newReview: QualityReviewRecord) => Promise<void>;
}

export const QualityPanel: React.FC<Props> = ({ review, onFeedback, onVisionQCComplete }) => {
  const [note, setNote] = useState(review.human_feedback_note ?? "");
  const [saving, setSaving] = useState(false);

  // Optional Multimodal Vision QC state (explicit quote + confirmation)
  const [visionQuote, setVisionQuote] = useState<VisionQCQuote | null>(null);
  const [visionConfirm, setVisionConfirm] = useState(false);
  const [visionBusy, setVisionBusy] = useState(false);
  const [visionError, setVisionError] = useState<string | null>(null);

  useEffect(() => {
    setNote(review.human_feedback_note ?? "");
    setVisionQuote(null);
    setVisionConfirm(false);
    setVisionError(null);
  }, [review.id, review.asset_id, review.human_feedback_note]);

  const handleSave = async (status: "accepted" | "rejected" | "needs_rework") => {
    setSaving(true);
    try {
      await onFeedback(review.id, status, note);
    } finally {
      setSaving(false);
    }
  };

  const handleRequestVisionQuote = async () => {
    setVisionBusy(true);
    setVisionError(null);
    setVisionConfirm(false);
    try {
      const q = await api.requestVisionQCQuote(review.asset_id);
      setVisionQuote(q);
    } catch (err) {
      setVisionError(err instanceof Error ? err.message : "Failed to compute Vision QC quote.");
    } finally {
      setVisionBusy(false);
    }
  };

  const handleRunVisionQC = async () => {
    if (!visionQuote) return;
    setVisionBusy(true);
    setVisionError(null);
    try {
      const upgraded = await api.runVisionQC(review.asset_id, {
        quote_id: visionQuote.quote_id,
        confirmation_token: visionQuote.confirmation_token,
        explicit_user_confirmed: true,
      });
      setVisionQuote(null);
      setVisionConfirm(false);
      if (onVisionQCComplete) {
        await onVisionQCComplete(upgraded);
      }
    } catch (err) {
      setVisionError(err instanceof Error ? err.message : "Multimodal Vision QC request failed.");
    } finally {
      setVisionBusy(false);
    }
  };

  const visionBlocked = visionQuote ? !visionQuote.spend_guard_allows || !visionQuote.credential_ready : true;

  return (
    <section className="panel" aria-label="Advisory Quality Review">
      <div className="section-head">
        <div>
          <h2>Advisory Quality Review</h2>
          <span className="small-mono">
            Composite: {review.weighted_score !== null ? `${review.weighted_score.toFixed(2)} / 5.00` : "N/A"} · Confidence:{" "}
            {Math.round(review.confidence * 100)}%
          </span>
        </div>
        <StatusBadge status={review.advisory_verdict} />
      </div>

      <div className="callout callout-info" style={{ fontSize: 12 }}>
        <strong>Inspection Coverage:</strong> <span className="mono">{review.inspection_coverage}</span>
        <ul style={{ margin: "6px 0 0 18px", padding: 0 }}>
          {review.limitations.map((lim, i) => (
            <li key={i}>{lim}</li>
          ))}
        </ul>
      </div>

      <div className="table-wrap">
        <table className="data-table">
          <thead>
            <tr>
              <th>Dimension</th>
              <th>Weight</th>
              <th>Score</th>
              <th>Observed Evidence &amp; Notes</th>
            </tr>
          </thead>
          <tbody>
            {review.dimensions.map((d) => (
              <tr key={d.name}>
                <td>
                  <strong>{d.label}</strong>
                  {d.critical && (
                    <div style={{ marginTop: 3 }}>
                      <StatusBadge status="warning" label="CRITICAL GATE" />
                    </div>
                  )}
                </td>
                <td className="mono">{Math.round(d.weight * 100)}%</td>
                <td className="mono">{d.score !== null ? d.score.toFixed(1) : "Manual"}</td>
                <td>
                  <div>{d.observed_evidence}</div>
                  {d.inferred_notes && <div className="muted" style={{ fontSize: 12 }}>{d.inferred_notes}</div>}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {review.findings.length > 0 && (
        <div className="subpanel">
          <h3>Findings ({review.findings.length})</h3>
          {review.findings.map((f, idx) => (
            <div key={idx} style={{ borderTop: idx > 0 ? "1px solid var(--border-subtle)" : "none", paddingTop: idx > 0 ? 8 : 0 }}>
              <div className="btn-row" style={{ marginBottom: 4 }}>
                <StatusBadge status={f.severity} />
                <span className="small-mono">{f.location_or_timestamp}</span>
                <span className="small-mono">Confidence {Math.round(f.confidence * 100)}%</span>
              </div>
              <div style={{ fontSize: 13 }}>
                <strong>Observed:</strong> {f.observed_evidence}
              </div>
              <div className="muted" style={{ fontSize: 12 }}>
                <strong>Inferred cause:</strong> {f.inferred_cause} — <strong>Suggested fix:</strong> {f.suggested_correction}
              </div>
            </div>
          ))}
        </div>
      )}

      {review.ai_tell_checklist.length > 0 && (
        <details className="subpanel">
          <summary style={{ cursor: "pointer", fontWeight: 600, fontSize: 13 }}>
            Visual Screening Checklist ({review.ai_tell_checklist.length} Photographic Realism Checks)
          </summary>
          <ul style={{ margin: "8px 0 0 18px", padding: 0, fontSize: 12 }}>
            {review.ai_tell_checklist.map((t) => (
              <li key={t.id} style={{ marginBottom: 4 }}>
                <span className="mono">{t.id}:</span> {t.label}{" "}
                <span className="badge badge-neutral">{t.check_status}</span>
                {t.evidence && <span className="muted"> — {t.evidence}</span>}
              </li>
            ))}
          </ul>
        </details>
      )}

      {/* Optional Multimodal Vision QC Gate (Phase 2 — Never Automatic, Explicit Approval Required) */}
      <div className="subpanel">
        <div className="section-head">
          <div>
            <h3>Optional Multimodal Vision QC</h3>
            <div className="muted" style={{ fontSize: 12 }}>
              Opt-in billable Gemini visual check (inspects image + references, or 3 sampled keyframes for video). Advisory only.
            </div>
          </div>
          {!visionQuote && (
            <button
              id="request-vision-qc-quote-btn"
              type="button"
              className="btn btn-sm"
              disabled={visionBusy}
              onClick={handleRequestVisionQuote}
            >
              {visionBusy ? "Quoting..." : "Request Vision QC Quote"}
            </button>
          )}
        </div>

        {visionError && (
          <div className="callout callout-danger" role="alert" style={{ fontSize: 12 }}>
            {visionError}
          </div>
        )}

        {visionQuote && (
          <div style={{ display: "flex", flexDirection: "column", gap: 8, marginTop: 4 }}>
            <div className="kv-grid" style={{ fontSize: 12 }}>
              <span className="kv-key">Vision Model</span>
              <span className="mono">{visionQuote.model_id}</span>
              <span className="kv-key">Inspection Scope</span>
              <span className="mono">
                {visionQuote.frames_to_inspect} frame(s) · Source Comparison: {visionQuote.includes_source_comparison ? "YES" : "NO"}
              </span>
              <span className="kv-key">Estimated Cost</span>
              <span className="mono">${visionQuote.estimated_cost_usd.toFixed(4)} USD</span>
              <span className="kv-key">Spend Guard</span>
              <span>
                <StatusBadge status={visionQuote.spend_guard_allows ? "supported" : "blocking"} label={visionQuote.spend_guard_allows ? "ALLOWED" : "BLOCKED"} />{" "}
                <span className="muted">{visionQuote.spend_guard_reason}</span>
              </span>
              <span className="kv-key">Server Credential</span>
              <span>
                <StatusBadge status={visionQuote.credential_ready ? "active" : "blocking"} label={visionQuote.credential_ready ? "READY" : "MISSING"} />{" "}
                <span className="muted">{visionQuote.credential_reason}</span>
              </span>
            </div>
            <div className="muted" style={{ fontSize: 12 }}>{visionQuote.pricing_disclosure}</div>
            <label style={{ display: "flex", alignItems: "flex-start", gap: 8, fontSize: 12, cursor: visionBlocked ? "not-allowed" : "pointer" }}>
              <input
                id="confirm-vision-qc-checkbox"
                type="checkbox"
                disabled={visionBlocked || visionBusy}
                checked={visionConfirm}
                onChange={(e) => setVisionConfirm(e.target.checked)}
                style={{ marginTop: 2 }}
              />
              <span>
                I approve running this optional billable Vision QC inspection and understand results remain strictly advisory.
              </span>
            </label>
            <div className="btn-row">
              <button
                id="run-vision-qc-btn"
                type="button"
                className="btn btn-primary btn-sm"
                disabled={visionBlocked || !visionConfirm || visionBusy}
                onClick={handleRunVisionQC}
              >
                {visionBusy ? "Running Vision QC..." : "Approve & Run Vision QC"}
              </button>
              <button type="button" className="btn btn-sm" disabled={visionBusy} onClick={() => setVisionQuote(null)}>
                Dismiss Quote
              </button>
            </div>
          </div>
        )}
      </div>

      {review.design_fit_notes.length > 0 && (
        <div className="muted" style={{ fontSize: 12 }}>
          <strong>Design &amp; Placement Fit:</strong> {review.design_fit_notes.join(" ")}
        </div>
      )}

      <div className="subpanel">
        <div className="section-head">
          <h3>Human Review Decision</h3>
          {review.human_feedback_status && <StatusBadge status={review.human_feedback_status} />}
        </div>
        <div className="field">
          <label htmlFor={`qc-note-${review.id}`}>Review Note (recorded in version audit)</label>
          <input
            id={`qc-note-${review.id}`}
            className="input"
            value={note}
            onChange={(e) => setNote(e.target.value)}
            placeholder="Optional inspection note (e.g., lighting matches brief, ready for export)..."
          />
        </div>
        <div className="btn-row">
          <button type="button" className="btn btn-primary btn-sm" disabled={saving} onClick={() => handleSave("accepted")}>
            Accept Asset
          </button>
          <button type="button" className="btn btn-sm" disabled={saving} onClick={() => handleSave("needs_rework")}>
            Mark Needs Rework
          </button>
          <button type="button" className="btn btn-danger btn-sm" disabled={saving} onClick={() => handleSave("rejected")}>
            Reject
          </button>
        </div>
      </div>
    </section>
  );
};
