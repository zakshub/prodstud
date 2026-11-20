import React from "react";
import type { VideoSequencePlan } from "../api/types";
import { StatusBadge } from "./StatusBadge";

interface Props {
  videoPlan: VideoSequencePlan;
}

export const ShotStoryboard: React.FC<Props> = ({ videoPlan }) => {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
      <div className="section-head">
        <div>
          <h2>Timed Shot Storyboard</h2>
          <span className="small-mono">
            {videoPlan.shots.length} shot(s) · {videoPlan.total_duration_s.toFixed(1)}s total · {videoPlan.aspect_ratio} ·{" "}
            {videoPlan.resolution} · {videoPlan.fps} FPS
          </span>
        </div>
        <StatusBadge
          status={videoPlan.feasibility_status}
          label={videoPlan.feasibility_status === "feasible" ? "FEASIBLE" : "ALTERNATIVE PROPOSED"}
        />
      </div>

      {videoPlan.alternative_proposals.length > 0 && (
        <div className="callout callout-warning">
          <strong>Provider Feasibility Tradeoff &amp; Proposed Alternatives:</strong>
          <ul style={{ margin: "6px 0 0 18px", padding: 0 }}>
            {videoPlan.alternative_proposals.map((alt, i) => (
              <li key={i}>{alt}</li>
            ))}
          </ul>
        </div>
      )}

      <div className="shot-list">
        {videoPlan.shots.map((shot) => (
          <article key={shot.shot_id} className="shot-card">
            <div className="shot-header">
              <div className="btn-row">
                <span className="badge badge-accent">{shot.shot_id}</span>
                <span className="small-mono">
                  {shot.start_s.toFixed(1)}s – {shot.end_s.toFixed(1)}s ({shot.duration_s.toFixed(1)}s)
                </span>
                <span className="badge badge-neutral">{shot.lens_focal_mm}mm</span>
              </div>
              <span className="muted" style={{ fontSize: 12 }}>
                {shot.visual_purpose}
              </span>
            </div>

            <div className="kv-grid">
              <span className="kv-key">Subject Action</span>
              <span>{shot.subject_action}</span>
              <span className="kv-key">Framing</span>
              <span>{shot.framing}</span>
              <span className="kv-key">Camera Movement</span>
              <span>{shot.camera_movement}</span>
              <span className="kv-key">Lighting Continuity</span>
              <span>{shot.lighting_continuity}</span>
              <span className="kv-key">Environment</span>
              <span>{shot.environment_continuity}</span>
              <span className="kv-key">Transition Out</span>
              <span>{shot.transition_out}</span>
            </div>

            {shot.feasibility_notes && (
              <div className="muted" style={{ fontSize: 12, borderTop: "1px solid var(--border-subtle)", paddingTop: 6 }}>
                <strong>Feasibility note:</strong> {shot.feasibility_notes}
              </div>
            )}
          </article>
        ))}
      </div>

      <div className="subpanel">
        <h3>Cross-Shot Continuity Invariants Ledger</h3>
        <ul style={{ margin: "4px 0 0 18px", padding: 0, fontSize: 13 }}>
          {videoPlan.continuity_invariants.map((inv, idx) => (
            <li key={idx}>{inv}</li>
          ))}
        </ul>
      </div>
    </div>
  );
};
