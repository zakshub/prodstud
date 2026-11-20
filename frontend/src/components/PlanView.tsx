import React, { useEffect, useState } from "react";
import type { ImagePlanDetails, ProductionPlanRecord, VideoSequencePlan } from "../api/types";
import { ShotStoryboard } from "./ShotStoryboard";
import { StatusBadge } from "./StatusBadge";

interface Props {
  plan: ProductionPlanRecord;
  onSaveEdits: (planId: string, imagePlan: ImagePlanDetails) => Promise<void>;
  onSaveVideoEdits?: (planId: string, videoPlan: VideoSequencePlan) => Promise<void>;
  onApplyDefaultField: (field: string, value: string) => void;
}

export const PlanView: React.FC<Props> = ({ plan, onSaveEdits, onSaveVideoEdits, onApplyDefaultField }) => {
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [showProtocols, setShowProtocols] = useState(false);
  const [editingImage, setEditingImage] = useState<ImagePlanDetails | null>(null);
  const [editingVideo, setEditingVideo] = useState<VideoSequencePlan | null>(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    setEditingImage(null);
    setEditingVideo(null);
  }, [plan.id]);

  const img = editingImage ?? plan.image_plan;

  const startEdit = () => {
    if (plan.media_type === "image" && plan.image_plan) {
      setEditingImage({ ...plan.image_plan });
      setShowAdvanced(true);
    } else if (plan.media_type === "video" && plan.video_plan && onSaveVideoEdits) {
      setEditingVideo({
        ...plan.video_plan,
        shots: plan.video_plan.shots.map((s) => ({ ...s })),
      });
    }
  };

  const commitImageEdit = async () => {
    if (!editingImage) return;
    setSaving(true);
    try {
      await onSaveEdits(plan.id, editingImage);
      setEditingImage(null);
    } finally {
      setSaving(false);
    }
  };

  const commitVideoEdit = async () => {
    if (!editingVideo || !onSaveVideoEdits) return;
    setSaving(true);
    try {
      await onSaveVideoEdits(plan.id, editingVideo);
      setEditingVideo(null);
    } finally {
      setSaving(false);
    }
  };

  return (
    <section className="panel" aria-label="Production Plan">
      <div className="section-head">
        <div>
          <div className="btn-row">
            <h2>Production Plan v{plan.version}</h2>
            <StatusBadge status={plan.media_type === "image" ? "core" : "adapted"} label={plan.media_type.toUpperCase()} />
            {plan.video_plan?.extended_from_asset_id && (
              <StatusBadge
                status="supported"
                label={`EXTENSION +${plan.video_plan.extension_duration_s ?? 0}s`}
              />
            )}
            <StatusBadge status={plan.feasibility_ok ? "feasible" : "requires_alternative"} label={plan.feasibility_ok ? "FEASIBLE" : "NEEDS ATTENTION"} />
          </div>
          <span className="small-mono">
            Mode: {plan.task_mode} · Complexity: {plan.complexity_tier.toUpperCase()} · {plan.activated_protocols.length} protocols activated
          </span>
        </div>

        <div className="btn-row">
          <button type="button" className="btn btn-sm" onClick={() => setShowProtocols((s) => !s)}>
            {showProtocols ? "Hide Protocol Trace" : `Protocol Trace (${plan.activated_protocols.length})`}
          </button>
          {((plan.media_type === "image" && plan.image_plan && !editingImage) ||
            (plan.media_type === "video" && plan.video_plan && onSaveVideoEdits && !editingVideo)) && (
            <button id="edit-plan-controls-btn" type="button" className="btn btn-sm" onClick={startEdit}>
              Edit Plan Controls
            </button>
          )}
        </div>
      </div>

      <p style={{ margin: 0 }}>{plan.summary}</p>

      {plan.feasibility_warnings.length > 0 && (
        <div className="callout callout-warning">
          <strong>Provider Feasibility Alerts:</strong>
          <ul style={{ margin: "4px 0 0 18px", padding: 0 }}>
            {plan.feasibility_warnings.map((w, i) => (
              <li key={i}>{w}</li>
            ))}
          </ul>
        </div>
      )}

      {plan.contradictions.length > 0 && (
        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
          {plan.contradictions.map((c, idx) => (
            <div key={idx} className={`callout ${c.severity === "blocking" ? "callout-danger" : "callout-warning"}`}>
              <div className="btn-row" style={{ marginBottom: 4 }}>
                <StatusBadge status={c.severity} />
                <span className="small-mono">{c.code}</span>
              </div>
              <div>{c.message}</div>
              <div className="muted" style={{ fontSize: 12, marginTop: 4 }}>
                <strong>Suggested resolution:</strong> {c.suggested_resolution}
              </div>
            </div>
          ))}
        </div>
      )}

      {plan.missing_info.length > 0 && (
        <div className="subpanel">
          <h3>Material Unknowns ({plan.missing_info.length} — Safe Defaults Applied)</h3>
          {plan.missing_info.map((q) => (
            <div key={q.field} style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
              <div>
                <strong>{q.question}</strong>
                <div className="muted" style={{ fontSize: 12 }}>
                  {q.why_it_matters} Default: <span className="mono">{q.suggested_default}</span>
                </div>
              </div>
              <button type="button" className="btn btn-sm" onClick={() => onApplyDefaultField(q.field, q.suggested_default)}>
                Fill in Brief
              </button>
            </div>
          ))}
        </div>
      )}

      {/* Key Explainable Decisions (Concise Summary First) */}
      <div className="subpanel">
        <h3>Key Production Decisions</h3>
        <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
          {plan.decisions.map((d) => (
            <div key={d.field} style={{ borderBottom: "1px solid var(--border-subtle)", paddingBottom: 8 }}>
              <div className="section-head">
                <strong>{d.label}</strong>
                <div className="btn-row">
                  <StatusBadge status={d.origin} label={d.origin === "user_specified" ? "USER SPECIFIED" : "INFERRED"} />
                  {d.protocol_codes.slice(0, 3).map((code) => (
                    <span key={code} className="badge badge-neutral">
                      {code}
                    </span>
                  ))}
                </div>
              </div>
              <div className="mono" style={{ fontSize: 13, marginTop: 2 }}>
                {Array.isArray(d.value) ? d.value.join(", ") : String(d.value)}
              </div>
              <div className="muted" style={{ fontSize: 12, marginTop: 2 }}>
                {d.plain_explanation}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Dedicated Image Progressive-Disclosure Technical Deck */}
      {plan.media_type === "image" && img && (
        <div className="subpanel">
          <div className="section-head">
            <h3>Camera, Optics, Lighting &amp; Preservation Specification</h3>
            <button type="button" className="btn btn-sm" onClick={() => setShowAdvanced((s) => !s)}>
              {showAdvanced ? "Collapse Technical Spec" : "Inspect Technical Spec"}
            </button>
          </div>

          {showAdvanced && !editingImage && (
            <div className="kv-grid" style={{ marginTop: 6 }}>
              <span className="kv-key">Subject &amp; Physics</span>
              <span>{img.subject_details}</span>
              <span className="kv-key">Environment</span>
              <span>{img.environment}</span>
              <span className="kv-key">Camera Position</span>
              <span>{img.camera_position} ({img.camera_height})</span>
              <span className="kv-key">Lens &amp; Focus</span>
              <span className="mono">{img.focal_length_mm}mm · {img.aperture} · {img.focus_plane}</span>
              <span className="kv-key">Key Light</span>
              <span>{img.lighting_key}</span>
              <span className="kv-key">Fill &amp; Contrast</span>
              <span>{img.lighting_fill} · {img.lighting_contrast_ratio} (~{img.color_temperature_k}K)</span>
              <span className="kv-key">Composition</span>
              <span>{img.composition_rule} · {img.shot_framing}</span>
              <span className="kv-key">Materials &amp; Color</span>
              <span>{img.material_and_texture}</span>
              <span className="kv-key">Hard Locks</span>
              <span>{img.hard_locks.length > 0 ? img.hard_locks.join(" · ") : "None declared"}</span>
              <span className="kv-key">Anti-AI Guardrails</span>
              <span>{img.negative_constraints.slice(0, 4).join(" · ")}</span>
            </div>
          )}

          {editingImage && (
            <div style={{ display: "flex", flexDirection: "column", gap: 10, marginTop: 8 }}>
              <div className="form-grid-3">
                <div className="field">
                  <label htmlFor="edit-focal">Focal Length (mm)</label>
                  <input
                    id="edit-focal"
                    type="number"
                    className="input mono"
                    value={editingImage.focal_length_mm}
                    onChange={(e) => setEditingImage({ ...editingImage, focal_length_mm: Number(e.target.value) || 50 })}
                  />
                </div>
                <div className="field">
                  <label htmlFor="edit-kelvin">Color Temp (K)</label>
                  <input
                    id="edit-kelvin"
                    type="number"
                    className="input mono"
                    value={editingImage.color_temperature_k}
                    onChange={(e) => setEditingImage({ ...editingImage, color_temperature_k: Number(e.target.value) || 5600 })}
                  />
                </div>
                <div className="field">
                  <label htmlFor="edit-ar">Aspect Ratio</label>
                  <input
                    id="edit-ar"
                    className="input mono"
                    value={editingImage.aspect_ratio}
                    onChange={(e) => setEditingImage({ ...editingImage, aspect_ratio: e.target.value })}
                  />
                </div>
              </div>
              <div className="field">
                <label htmlFor="edit-env">Environment</label>
                <input
                  id="edit-env"
                  className="input"
                  value={editingImage.environment}
                  onChange={(e) => setEditingImage({ ...editingImage, environment: e.target.value })}
                />
              </div>
              <div className="field">
                <label htmlFor="edit-keylight">Key Light Motivation</label>
                <input
                  id="edit-keylight"
                  className="input"
                  value={editingImage.lighting_key}
                  onChange={(e) => setEditingImage({ ...editingImage, lighting_key: e.target.value })}
                />
              </div>
              <div className="btn-row">
                <button type="button" className="btn btn-primary btn-sm" disabled={saving} onClick={commitImageEdit}>
                  {saving ? "Saving..." : "Save Plan Edits"}
                </button>
                <button type="button" className="btn btn-sm" onClick={() => setEditingImage(null)}>
                  Cancel
                </button>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Dedicated Timed Video Shot Storyboard + Inline Video Editor */}
      {plan.media_type === "video" && plan.video_plan && (
        <>
          {editingVideo ? (
            <div className="subpanel" style={{ display: "flex", flexDirection: "column", gap: 10 }}>
              <h3>Edit Timed Video Plan Controls</h3>
              <div className="form-grid-3">
                <div className="field">
                  <label htmlFor="edit-vid-dur">Total Duration (s)</label>
                  <input
                    id="edit-vid-dur"
                    type="number"
                    min={3}
                    max={30}
                    step={0.5}
                    className="input mono"
                    value={editingVideo.total_duration_s}
                    onChange={(e) =>
                      setEditingVideo({ ...editingVideo, total_duration_s: Number(e.target.value) || 8 })
                    }
                  />
                </div>
                <div className="field">
                  <label htmlFor="edit-vid-ar">Aspect Ratio</label>
                  <select
                    id="edit-vid-ar"
                    className="select mono"
                    value={editingVideo.aspect_ratio}
                    onChange={(e) => setEditingVideo({ ...editingVideo, aspect_ratio: e.target.value })}
                  >
                    <option value="16:9">16:9</option>
                    <option value="9:16">9:16</option>
                    <option value="1:1">1:1</option>
                  </select>
                </div>
                <div className="field">
                  <label htmlFor="edit-vid-res">Resolution</label>
                  <select
                    id="edit-vid-res"
                    className="select mono"
                    value={editingVideo.resolution}
                    onChange={(e) => setEditingVideo({ ...editingVideo, resolution: e.target.value })}
                  >
                    <option value="360p">360p</option>
                    <option value="720p">720p</option>
                    <option value="1080p">1080p</option>
                    <option value="4K">4K</option>
                  </select>
                </div>
              </div>
              {editingVideo.shots.map((shot, idx) => (
                <div key={shot.shot_id} className="subpanel" style={{ gap: 8 }}>
                  <strong className="mono">{shot.shot_id} ({shot.start_s.toFixed(1)}s–{shot.end_s.toFixed(1)}s)</strong>
                  <div className="field">
                    <label htmlFor={`edit-shot-action-${shot.order}`}>Subject Action ({shot.shot_id})</label>
                    <input
                      id={`edit-shot-action-${shot.order}`}
                      className="input"
                      value={shot.subject_action}
                      onChange={(e) => {
                        const next = editingVideo.shots.map((s, j) =>
                          j === idx ? { ...s, subject_action: e.target.value } : s,
                        );
                        setEditingVideo({ ...editingVideo, shots: next });
                      }}
                    />
                  </div>
                  <div className="field">
                    <label htmlFor={`edit-shot-cam-${shot.order}`}>Camera Movement ({shot.shot_id})</label>
                    <input
                      id={`edit-shot-cam-${shot.order}`}
                      className="input"
                      value={shot.camera_movement}
                      onChange={(e) => {
                        const next = editingVideo.shots.map((s, j) =>
                          j === idx ? { ...s, camera_movement: e.target.value } : s,
                        );
                        setEditingVideo({ ...editingVideo, shots: next });
                      }}
                    />
                  </div>
                </div>
              ))}
              <div className="btn-row">
                <button type="button" className="btn btn-primary btn-sm" disabled={saving} onClick={commitVideoEdit}>
                  {saving ? "Saving & Re-validating..." : "Save Video Plan Edits"}
                </button>
                <button type="button" className="btn btn-sm" onClick={() => setEditingVideo(null)}>
                  Cancel
                </button>
              </div>
            </div>
          ) : (
            <ShotStoryboard videoPlan={plan.video_plan} />
          )}
        </>
      )}

      {/* Contextual Protocol Activation Trace (Progressive Disclosure) */}
      {showProtocols && (
        <div className="subpanel">
          <h3>Activated Protocols ({plan.activated_protocols.length} of 170)</h3>
          <div className="table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Code</th>
                  <th>Protocol</th>
                  <th>Layer</th>
                  <th>Disposition</th>
                  <th>Activation Rationale</th>
                </tr>
              </thead>
              <tbody>
                {plan.activated_protocols.map((p) => (
                  <tr key={p.protocol_id}>
                    <td className="mono">{p.protocol_code}</td>
                    <td><strong>{p.canonical_title}</strong></td>
                    <td className="muted">{p.source_layer}</td>
                    <td><StatusBadge status={p.disposition} /></td>
                    <td className="muted">{p.reason}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </section>
  );
};
