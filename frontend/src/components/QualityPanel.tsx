import React, { useState } from "react";
import type { QualityReviewRecord } from "../api/types";
import { StatusBadge } from "./StatusBadge";

interface Props {
  review: QualityReviewRecord;
  onFeedback: (reviewId: string, status: "accepted" | "rejected" | "needs_rework", note: string) => Promise<void>;
}

export const QualityPanel: React.FC<Props> = ({ review, onFeedback }) => {
  const [note, setNote] = useState(review.human_feedback_note ?? "");
  const [saving, setSaving] = useState(false);

  const handleSave = async (status: "accepted" | "rejected" | "needs_rework") => {
    setSaving(true);
    try {
      await onFeedback(review.id, status, note);
    } finally {
      setSaving(false);
    }
  };

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
            Human Visual Screening Checklist ({review.ai_tell_checklist.length} Photographic Realism Checks)
          </summary>
          <ul style={{ margin: "8px 0 0 18px", padding: 0, fontSize: 12 }}>
            {review.ai_tell_checklist.map((t) => (
              <li key={t.id}>
                <span className="mono">{t.id}:</span> {t.label}
              </li>
            ))}
          </ul>
        </details>
      )}

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
