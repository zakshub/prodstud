import React, { useEffect, useMemo, useState } from "react";
import { api } from "../api/client";
import type {
  ApprovalQuote,
  GeneratedAssetRecord,
  GenerationJobRecord,
  ImagePlanDetails,
  MediaType,
  ProductionPlanRecord,
  ProductionTemplateRecord,
  ProjectRecord,
  ProjectWorkspaceData,
  ProviderModelCapability,
  QualityReviewRecord,
  RevisionRecord,
} from "../api/types";
import { ApprovalModal } from "../components/ApprovalModal";
import { PlanView } from "../components/PlanView";
import { QualityPanel } from "../components/QualityPanel";
import { StatusBadge } from "../components/StatusBadge";

interface Props {
  projects: ProjectRecord[];
  activeProjectId: string;
  capabilities: ProviderModelCapability[];
  templates: ProductionTemplateRecord[];
  onSelectProject: (projectId: string) => void;
  onRefreshGlobal: () => Promise<void>;
  onOpenCompare: (leftId: string, rightId: string) => void;
}

export const WorkspaceView: React.FC<Props> = ({
  projects,
  activeProjectId,
  capabilities,
  templates,
  onSelectProject,
  onRefreshGlobal,
  onOpenCompare,
}) => {
  const [workspace, setWorkspace] = useState<ProjectWorkspaceData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Brief state
  const [mediaType, setMediaType] = useState<MediaType>("image");
  const [promptText, setPromptText] = useState("");
  const [environment, setEnvironment] = useState("");
  const [aspectRatio, setAspectRatio] = useState("3:2");
  const [resolution, setResolution] = useState("2K");
  const [durationS, setDurationS] = useState(8);
  const [preservationMode, setPreservationMode] = useState("new_generation");
  const [selectedRefIds, setSelectedRefIds] = useState<string[]>([]);
  const [selectedModelKey, setSelectedModelKey] = useState("");

  // Reference upload state
  const [refRole, setRefRole] = useState("product");
  const [refRightsConfirmed, setRefRightsConfirmed] = useState(true);
  const [uploadingRef, setUploadingRef] = useState(false);

  // Active objects
  const [activePlan, setActivePlan] = useState<ProductionPlanRecord | null>(null);
  const [activeAsset, setActiveAsset] = useState<GeneratedAssetRecord | null>(null);
  const [activeReview, setActiveReview] = useState<QualityReviewRecord | null>(null);
  const [activeJob, setActiveJob] = useState<GenerationJobRecord | null>(null);
  const [latestRevision, setLatestRevision] = useState<RevisionRecord | null>(null);

  // Quote & generation modal
  const [pendingQuote, setPendingQuote] = useState<ApprovalQuote | null>(null);
  const [busyAction, setBusyAction] = useState<string | null>(null);

  // Revision & asset organization inputs
  const [revisionInput, setRevisionInput] = useState("");
  const [revisionShotOrder, setRevisionShotOrder] = useState<string>("");
  const [tagsInput, setTagsInput] = useState("");
  const [collectionInput, setCollectionInput] = useState("");

  const mediaCapabilities = useMemo(
    () => capabilities.filter((c) => c.media_type === mediaType),
    [capabilities, mediaType],
  );

  // Select sensible default model only when mediaType changes or current selection is not valid for mediaType
  useEffect(() => {
    const stillValid = mediaCapabilities.some((c) => `${c.provider_id}::${c.model_id}` === selectedModelKey);
    if (stillValid) return;
    const supported = mediaCapabilities.filter((c) => c.support_status === "supported");
    const fixture = supported.find((c) => c.is_local_test_fixture);
    const chosen = supported[0] ?? fixture ?? mediaCapabilities[0];
    if (chosen) {
      setSelectedModelKey(`${chosen.provider_id}::${chosen.model_id}`);
      if (mediaType === "video") {
        setAspectRatio("16:9");
        setResolution("720p");
      } else {
        setAspectRatio("3:2");
        setResolution("2K");
      }
    }
  }, [mediaType, mediaCapabilities, selectedModelKey]);

  const loadWorkspace = async (projectId: string, preserveActive = false) => {
    setLoading(true);
    setError(null);
    try {
      const data = await api.getProjectWorkspace(projectId);
      setWorkspace(data);
      if (!preserveActive) {
        setActivePlan(data.plans[0] ?? null);
        setActiveJob(data.jobs[0] ?? null);
        const latestAsset = data.assets[0] ?? null;
        setActiveAsset(latestAsset);
        if (latestAsset) {
          setTagsInput(latestAsset.tags.join(", "));
          setCollectionInput(latestAsset.collection_name ?? "");
          try {
            setActiveReview(await api.getAssetReview(latestAsset.id));
          } catch {
            setActiveReview(null);
          }
        } else {
          setActiveReview(null);
        }
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load project workspace.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (activeProjectId) {
      loadWorkspace(activeProjectId, false);
    }
  }, [activeProjectId]);

  const selectAsset = async (asset: GeneratedAssetRecord) => {
    setActiveAsset(asset);
    setTagsInput(asset.tags.join(", "));
    setCollectionInput(asset.collection_name ?? "");
    const matchingPlan = workspace?.plans.find((p) => p.id === asset.plan_id);
    if (matchingPlan) setActivePlan(matchingPlan);
    try {
      setActiveReview(await api.getAssetReview(asset.id));
    } catch {
      setActiveReview(null);
    }
  };

  const handleReferenceUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploadingRef(true);
    setError(null);
    try {
      const ref = await api.uploadReference(activeProjectId, file, refRole, refRightsConfirmed);
      setSelectedRefIds((prev) => [...prev, ref.id]);
      await loadWorkspace(activeProjectId, true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Reference upload failed.");
    } finally {
      setUploadingRef(false);
      e.target.value = "";
    }
  };

  const selectedProviderAndModel = (): [string, string] => {
    if (selectedModelKey.includes("::")) {
      const [p, m] = selectedModelKey.split("::", 2);
      return [p, m];
    }
    const fallback = mediaCapabilities.find((c) => c.support_status === "supported") ?? mediaCapabilities[0];
    return fallback ? [fallback.provider_id, fallback.model_id] : ["google_gemini_image", "gemini-nano-banana-2.1"];
  };

  const handleCreatePlan = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!promptText.trim()) return;
    setBusyAction("planning");
    setError(null);
    setLatestRevision(null);
    try {
      const [provider_id, model_id] = selectedProviderAndModel();
      const plan = await api.createPlan(activeProjectId, {
        media_type: mediaType,
        prompt_text: promptText.trim(),
        environment: environment.trim() || null,
        aspect_ratio: aspectRatio || null,
        resolution: resolution || null,
        duration_s: mediaType === "video" ? durationS : null,
        reference_ids: selectedRefIds,
        preservation_mode: preservationMode,
        provider_id,
        model_id,
      });
      setActivePlan(plan);
      await loadWorkspace(activeProjectId, true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Plan generation failed.");
    } finally {
      setBusyAction(null);
    }
  };

  const handleSavePlanEdits = async (planId: string, imagePlan: ImagePlanDetails) => {
    const updated = await api.editPlan(planId, { image_plan: imagePlan });
    setActivePlan(updated);
    await loadWorkspace(activeProjectId, true);
  };

  const handleRequestQuote = async () => {
    if (!activePlan) return;
    setBusyAction("quoting");
    setError(null);
    try {
      const [provider_id, model_id] = selectedProviderAndModel();
      // If active plan's media type differs from brief switcher, respect active plan's media type
      const validCap = capabilities.find(
        (c) => c.media_type === activePlan.media_type && c.provider_id === provider_id && c.model_id === model_id,
      );
      const targetProvider = validCap ? provider_id : activePlan.recommended_provider;
      const targetModel = validCap ? model_id : activePlan.recommended_model;
      const quote = await api.requestQuote(activePlan.id, targetProvider, targetModel);
      setPendingQuote(quote);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to compute approval quote.");
    } finally {
      setBusyAction(null);
    }
  };

  const handleConfirmGenerate = async () => {
    if (!activePlan || !pendingQuote) return;
    setBusyAction("generating");
    setError(null);
    try {
      const res = await api.submitGeneration(activePlan.id, {
        quote_id: pendingQuote.quote_id,
        confirmation_token: pendingQuote.confirmation_token,
        explicit_user_confirmed: true,
        parent_asset_id: activePlan.parent_plan_id ? activeAsset?.id ?? null : null,
      });
      setPendingQuote(null);
      setActiveJob(res.job);
      if (res.asset) {
        setActiveAsset(res.asset);
        setTagsInput(res.asset.tags.join(", "));
        setCollectionInput(res.asset.collection_name ?? "");
      }
      if (res.quality_review) {
        setActiveReview(res.quality_review);
      }
      await loadWorkspace(activeProjectId, true);
      await onRefreshGlobal();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Generation request failed.");
      setPendingQuote(null);
    } finally {
      setBusyAction(null);
    }
  };

  const handlePollJob = async (jobId: string) => {
    setBusyAction("polling");
    try {
      const res = await api.pollJob(jobId);
      setActiveJob(res.job);
      if (res.asset) setActiveAsset(res.asset);
      if (res.quality_review) setActiveReview(res.quality_review);
      await loadWorkspace(activeProjectId, true);
    } finally {
      setBusyAction(null);
    }
  };

  const handleCancelJob = async (jobId: string) => {
    const res = await api.cancelJob(jobId);
    setActiveJob(res.job);
    await loadWorkspace(activeProjectId, true);
  };

  const handleRevise = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!activePlan || !revisionInput.trim()) return;
    setBusyAction("revising");
    setError(null);
    try {
      const shotNum = revisionShotOrder ? Number(revisionShotOrder) : null;
      const res = await api.revisePlan(activePlan.id, revisionInput.trim(), activeAsset?.id ?? null, shotNum);
      setActivePlan(res.plan);
      setLatestRevision(res.revision);
      setRevisionInput("");
      await loadWorkspace(activeProjectId, true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Revision failed.");
    } finally {
      setBusyAction(null);
    }
  };

  const handleFeedback = async (reviewId: string, status: "accepted" | "rejected" | "needs_rework", note: string) => {
    const updated = await api.submitReviewFeedback(reviewId, status, note);
    setActiveReview(updated);
    await loadWorkspace(activeProjectId, true);
  };

  const handleOrganizeSave = async () => {
    if (!activeAsset) return;
    const tags = tagsInput
      .split(",")
      .map((s) => s.trim())
      .filter(Boolean);
    const updated = await api.organizeAsset(activeAsset.id, {
      tags,
      collection_name: collectionInput.trim(),
    });
    setActiveAsset(updated);
    await loadWorkspace(activeProjectId, true);
  };

  const handleSaveTemplate = async () => {
    if (!promptText.trim()) return;
    const tName = window.prompt("Template name (e.g. Studio Watch Still):");
    if (!tName || !tName.trim()) return;
    await api.createTemplate({
      name: tName.trim(),
      media_type: mediaType,
      description: `Saved from ${workspace?.project.name ?? "project"}`,
      default_brief: {
        prompt_text: promptText.trim(),
        environment: environment.trim(),
        aspect_ratio: aspectRatio,
        resolution,
        duration_s: mediaType === "video" ? durationS : undefined,
      },
    });
    await onRefreshGlobal();
  };

  const applyTemplate = (tpl: ProductionTemplateRecord) => {
    setMediaType(tpl.media_type);
    if (typeof tpl.default_brief.prompt_text === "string") setPromptText(tpl.default_brief.prompt_text);
    if (typeof tpl.default_brief.environment === "string") setEnvironment(tpl.default_brief.environment);
    if (typeof tpl.default_brief.aspect_ratio === "string") setAspectRatio(tpl.default_brief.aspect_ratio);
    if (typeof tpl.default_brief.resolution === "string") setResolution(tpl.default_brief.resolution);
    if (typeof tpl.default_brief.duration_s === "number") setDurationS(tpl.default_brief.duration_s);
  };

  if (loading && !workspace) {
    return (
      <main className="page-container">
        <div className="panel">Loading production workspace...</div>
      </main>
    );
  }

  return (
    <div className="workbench-layout">
      {/* Zone 1: Left Project & History Rail */}
      <aside className="rail-left" aria-label="Project Switcher and History">
        <div>
          <h3 style={{ marginBottom: 8 }}>Projects</h3>
          <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
            {projects.map((p) => (
              <button
                key={p.id}
                type="button"
                className={`list-item ${p.id === activeProjectId ? "active" : ""}`}
                onClick={() => onSelectProject(p.id)}
              >
                <strong style={{ fontSize: 13 }}>{p.name}</strong>
                <span className="small-mono">{p.asset_count} asset(s)</span>
              </button>
            ))}
          </div>
        </div>

        <div style={{ borderTop: "1px solid var(--border-subtle)", paddingTop: 12 }}>
          <h3 style={{ marginBottom: 8 }}>Version History ({workspace?.assets.length ?? 0})</h3>
          {workspace && workspace.assets.length === 0 ? (
            <p className="muted" style={{ fontSize: 12, margin: 0 }}>
              No generated assets yet. Build a plan and approve generation to populate version history.
            </p>
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
              {workspace?.assets.map((a) => (
                <button
                  key={a.id}
                  type="button"
                  className={`list-item ${activeAsset?.id === a.id ? "active" : ""}`}
                  onClick={() => selectAsset(a)}
                >
                  <div className="section-head">
                    <span className="mono" style={{ fontSize: 12, fontWeight: 600 }}>
                      v{String(a.version_number).padStart(2, "0")} · {a.media_type.toUpperCase()}
                    </span>
                    {a.accepted && <StatusBadge status="accepted" label="OK" />}
                  </div>
                  <span className="muted" style={{ fontSize: 11, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                    {a.filename}
                  </span>
                </button>
              ))}
            </div>
          )}
        </div>

        {workspace && workspace.assets.length >= 2 && (
          <button
            type="button"
            className="btn btn-sm"
            onClick={() => {
              const images = workspace.assets.filter((a) => a.media_type === "image");
              const videos = workspace.assets.filter((a) => a.media_type === "video");
              if (images.length >= 2) {
                onOpenCompare(images[1].id, images[0].id);
              } else if (videos.length >= 2) {
                onOpenCompare(videos[1].id, videos[0].id);
              } else {
                onOpenCompare(workspace.assets[1].id, workspace.assets[0].id);
              }
            }}
          >
            Compare Latest Two Versions
          </button>
        )}

        {templates.length > 0 && (
          <div style={{ borderTop: "1px solid var(--border-subtle)", paddingTop: 12 }}>
            <h3 style={{ marginBottom: 8 }}>Templates</h3>
            <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
              {templates.map((t) => (
                <button key={t.id} type="button" className="list-item" onClick={() => applyTemplate(t)}>
                  <strong style={{ fontSize: 12 }}>{t.name}</strong>
                  <span className="small-mono">{t.media_type}</span>
                </button>
              ))}
            </div>
          </div>
        )}
      </aside>

      {/* Zone 2: Dominant Asset-First Stage & Production Plan */}
      <main className="stage-center">
        <div className="section-head">
          <div>
            <h1>{workspace?.project.name ?? "Project Workspace"}</h1>
            <p className="muted" style={{ margin: "2px 0 0" }}>
              {workspace?.project.description || "Asset-first image and video production stage"}
            </p>
          </div>
          {activeJob && (
            <div className="btn-row" aria-live="polite">
              <StatusBadge status={activeJob.status} label={`JOB: ${activeJob.status.toUpperCase()}`} />
              {(activeJob.status === "processing" || activeJob.status === "queued" || activeJob.status === "unknown") && (
                <button
                  type="button"
                  className="btn btn-sm"
                  disabled={busyAction === "polling"}
                  onClick={() => handlePollJob(activeJob.id)}
                >
                  Check Status
                </button>
              )}
              {(activeJob.status === "processing" || activeJob.status === "queued") && (
                <button type="button" className="btn btn-danger btn-sm" onClick={() => handleCancelJob(activeJob.id)}>
                  Cancel Job
                </button>
              )}
            </div>
          )}
        </div>

        {error && (
          <div className="callout callout-danger" role="alert">
            {error}
          </div>
        )}

        {activeJob && activeJob.status === "unknown" && (
          <div className="callout callout-warning" role="alert">
            <strong>Uncertain Provider Acceptance (UNKNOWN State):</strong> {activeJob.error_message} Use{" "}
            <strong>Check Status</strong> to inspect provider progress rather than blindly resubmitting.
          </div>
        )}

        {activeJob && activeJob.status === "failed" && (
          <div className="callout callout-danger" role="alert">
            <strong>Generation Failed ({activeJob.error_category}):</strong> {activeJob.error_message} Your brief and
            plan are preserved safely below.
          </div>
        )}

        {/* Dominant Asset Preview Stage */}
        {activeAsset ? (
          <section className="panel" aria-label="Generated Asset Stage">
            <div className="section-head">
              <div>
                <div className="btn-row">
                  <h2>
                    Asset v{String(activeAsset.version_number).padStart(2, "0")} — {activeAsset.filename}
                  </h2>
                  {activeAsset.is_local_test_fixture && (
                    <StatusBadge status="warning" label="LOCAL TEST RENDER · NOT GOOGLE LIVE" />
                  )}
                </div>
                <span className="small-mono">
                  {activeAsset.provider_id} / {activeAsset.model_id} ·{" "}
                  {activeAsset.width && activeAsset.height ? `${activeAsset.width}×${activeAsset.height}px` : "media"}
                  {activeAsset.duration_s ? ` · ${activeAsset.duration_s.toFixed(1)}s @ ${activeAsset.fps ?? 24} FPS` : ""} ·
                  SHA-256 {activeAsset.sha256.slice(0, 12)}
                </span>
              </div>
              <div className="btn-row">
                <button
                  type="button"
                  className="btn btn-sm"
                  onClick={async () => {
                    const updated = await api.organizeAsset(activeAsset.id, { is_favorite: !activeAsset.is_favorite });
                    setActiveAsset(updated);
                    await loadWorkspace(activeProjectId, true);
                  }}
                >
                  {activeAsset.is_favorite ? "★ Favorited" : "☆ Favorite"}
                </button>
                <a className="btn btn-sm" href={`/api/assets/${activeAsset.id}/file?download=true`} download>
                  Download File
                </a>
                <a className="btn btn-primary btn-sm" href={`/api/assets/${activeAsset.id}/export`} download>
                  Export ZIP + Provenance
                </a>
              </div>
            </div>

            <div className="asset-stage-frame">
              {activeAsset.media_type === "image" ? (
                <img
                  src={`/api/assets/${activeAsset.id}/file`}
                  alt={`Generated visual asset ${activeAsset.filename}`}
                />
              ) : (
                <video
                  key={activeAsset.id}
                  controls
                  playsInline
                  preload="metadata"
                  src={`/api/assets/${activeAsset.id}/file`}
                />
              )}
            </div>

            {/* Asset Metadata & Organization Bar */}
            <div className="form-grid-3" style={{ alignItems: "end" }}>
              <div className="field">
                <label htmlFor="asset-tags-input">Tags (comma-separated)</label>
                <input
                  id="asset-tags-input"
                  className="input"
                  value={tagsInput}
                  onChange={(e) => setTagsInput(e.target.value)}
                  placeholder="hero, studio, approved"
                />
              </div>
              <div className="field">
                <label htmlFor="asset-collection-input">Collection</label>
                <input
                  id="asset-collection-input"
                  className="input"
                  value={collectionInput}
                  onChange={(e) => setCollectionInput(e.target.value)}
                  placeholder="Autumn Launch"
                />
              </div>
              <div>
                <button type="button" className="btn btn-sm" style={{ width: "100%" }} onClick={handleOrganizeSave}>
                  Save Tags &amp; Collection
                </button>
              </div>
            </div>
          </section>
        ) : (
          <section className="asset-stage-frame" aria-label="Empty Stage">
            <h2>Production Stage Ready</h2>
            <p className="muted" style={{ maxWidth: 460, textAlign: "center", margin: 0 }}>
              Describe your Image or Video brief in the right inspector to generate a structured 170-protocol production
              plan. Assets appear here immediately after explicit generation approval.
            </p>
          </section>
        )}

        {/* Latest Revision Delta Disclosure */}
        {latestRevision && (
          <section className="callout callout-info" aria-label="Revision Summary">
            <strong>Controlled Revision Applied:</strong> Updated{" "}
            <span className="mono">{latestRevision.changed_fields.join(", ")}</span> while preserving{" "}
            <span className="mono">{latestRevision.preserved_fields.length}</span> unaffected approved decision(s).
            <div className="muted" style={{ fontSize: 12, marginTop: 4 }}>
              {latestRevision.provider_regeneration_note}
            </div>
          </section>
        )}

        {/* Active Production Plan */}
        {activePlan && (
          <PlanView
            plan={activePlan}
            onSaveEdits={handleSavePlanEdits}
            onApplyDefaultField={(field, val) => {
              if (field === "environment") setEnvironment(val);
              if (field === "aspect_ratio") setAspectRatio(val);
            }}
          />
        )}

        {/* Advisory Quality Review */}
        {activeReview && <QualityPanel review={activeReview} onFeedback={handleFeedback} />}
      </main>

      {/* Zone 3: Right Production Brief, Reference Upload, Execution Approval & Targeted Revision Inspector */}
      <aside className="rail-right" aria-label="Brief Composer and Execution Controls">
        <div className="section-head">
          <h2>Production Brief</h2>
          <div className="segmented" role="group" aria-label="Deliverable Media Type">
            <button
              id="mode-image-btn"
              type="button"
              aria-pressed={mediaType === "image"}
              onClick={() => setMediaType("image")}
            >
              Image
            </button>
            <button
              id="mode-video-btn"
              type="button"
              aria-pressed={mediaType === "video"}
              onClick={() => setMediaType("video")}
            >
              Video
            </button>
          </div>
        </div>

        <form onSubmit={handleCreatePlan} style={{ display: "flex", flexDirection: "column", gap: 12 }}>
          <div className="field">
            <label htmlFor="brief-prompt">Creative Intent (Plain Language)</label>
            <textarea
              id="brief-prompt"
              className="textarea"
              required
              value={promptText}
              onChange={(e) => setPromptText(e.target.value)}
              placeholder={
                mediaType === "image"
                  ? "Describe subject, lighting feel, materials, and visual purpose (e.g. Brushed titanium mechanical watch on dark travertine stone, diffused studio softbox)..."
                  : "Describe sequence intent, subject action, camera motion, and pacing (e.g. Two-shot reveal of ceramic pour-over coffee in warm sunlit atelier, moving from wide glide to macro pour)..."
              }
            />
          </div>

          <div className="field">
            <label htmlFor="brief-env">Environment / Setting (Optional)</label>
            <input
              id="brief-env"
              className="input"
              value={environment}
              onChange={(e) => setEnvironment(e.target.value)}
              placeholder="e.g. North-facing concrete studio"
            />
          </div>

          <div className="form-grid-2">
            <div className="field">
              <label htmlFor="brief-ar">Aspect Ratio</label>
              <select id="brief-ar" className="select mono" value={aspectRatio} onChange={(e) => setAspectRatio(e.target.value)}>
                {mediaType === "image" ? (
                  <>
                    <option value="3:2">3:2 · Photo</option>
                    <option value="4:5">4:5 · Portrait</option>
                    <option value="1:1">1:1 · Square</option>
                    <option value="16:9">16:9 · Wide</option>
                    <option value="9:16">9:16 · Vertical</option>
                    <option value="21:9">21:9 · Cinema</option>
                  </>
                ) : (
                  <>
                    <option value="16:9">16:9 · Wide</option>
                    <option value="9:16">9:16 · Vertical</option>
                    <option value="1:1">1:1 · Square</option>
                  </>
                )}
              </select>
            </div>

            <div className="field">
              <label htmlFor="brief-res">Resolution</label>
              <select id="brief-res" className="select mono" value={resolution} onChange={(e) => setResolution(e.target.value)}>
                {mediaType === "image" ? (
                  <>
                    <option value="1K">1K</option>
                    <option value="2K">2K</option>
                    <option value="4K">4K</option>
                  </>
                ) : (
                  <>
                    <option value="720p">720p</option>
                    <option value="1080p">1080p</option>
                    <option value="4K">4K</option>
                  </>
                )}
              </select>
            </div>
          </div>

          {mediaType === "video" ? (
            <div className="field">
              <label htmlFor="brief-duration">Target Duration (Seconds — 3–15s on Omni 1.2 Flash)</label>
              <input
                id="brief-duration"
                type="number"
                min={3}
                max={30}
                step={1}
                className="input mono"
                value={durationS}
                onChange={(e) => setDurationS(Number(e.target.value) || 8)}
              />
            </div>
          ) : (
            <div className="field">
              <label htmlFor="brief-pres">Preservation Mode</label>
              <select
                id="brief-pres"
                className="select"
                value={preservationMode}
                onChange={(e) => setPreservationMode(e.target.value)}
              >
                <option value="new_generation">New Generation</option>
                <option value="selective_edit">Selective Edit (Preserve Locked Areas)</option>
                <option value="strict_preservation">Strict Preservation (Enhance Only)</option>
              </select>
            </div>
          )}

          <div className="field">
            <label htmlFor="brief-model">Target Provider &amp; Model (Verified Capabilities)</label>
            <select
              id="brief-model"
              className="select"
              value={selectedModelKey}
              onChange={(e) => setSelectedModelKey(e.target.value)}
            >
              {mediaCapabilities.map((c) => {
                const disabled = c.support_status === "unsupported" || c.support_status === "provider_conditional";
                return (
                  <option key={`${c.provider_id}::${c.model_id}`} value={`${c.provider_id}::${c.model_id}`} disabled={disabled}>
                    {c.display_name} [{c.support_status.toUpperCase()}]
                  </option>
                );
              })}
            </select>
          </div>

          <div className="btn-row">
            <button id="build-plan-btn" type="submit" className="btn btn-primary" style={{ flex: 1 }} disabled={busyAction === "planning"}>
              {busyAction === "planning" ? "Interpreting Brief..." : `Build ${mediaType === "image" ? "Image" : "Video Shot"} Plan`}
            </button>
            <button type="button" className="btn btn-sm" onClick={handleSaveTemplate} title="Save current brief as reusable template">
              Save Preset
            </button>
          </div>
        </form>

        {/* Reference Upload Panel */}
        <div className="subpanel">
          <h3>Reference Assets ({workspace?.references.length ?? 0})</h3>
          <div className="field">
            <label htmlFor="ref-role">Reference Role</label>
            <select id="ref-role" className="select" value={refRole} onChange={(e) => setRefRole(e.target.value)}>
              <option value="product">Product Fidelity</option>
              <option value="identity">Subject Identity</option>
              <option value="style">Style / Mood</option>
              <option value="composition">Composition</option>
              <option value="environment">Environment</option>
              <option value="start_frame">Video Start Frame</option>
              <option value="end_frame">Video End Frame</option>
            </select>
          </div>
          <div className="field">
            <label htmlFor="ref-file-input">Upload Reference Image (PNG / JPG / WebP, max 15 MB)</label>
            <input
              id="ref-file-input"
              type="file"
              accept="image/png,image/jpeg,image/webp"
              disabled={uploadingRef}
              onChange={handleReferenceUpload}
              style={{ fontSize: 12, width: "100%" }}
            />
          </div>
          <label style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 12 }}>
            <input
              type="checkbox"
              checked={refRightsConfirmed}
              onChange={(e) => setRefRightsConfirmed(e.target.checked)}
            />
            I confirm usage rights for uploaded references
          </label>
          {workspace && workspace.references.length > 0 && (
            <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
              {workspace.references.map((r) => {
                const active = selectedRefIds.includes(r.id);
                return (
                  <label key={r.id} style={{ display: "flex", alignItems: "center", justifyContent: "space-between", fontSize: 12, gap: 6 }}>
                    <span style={{ display: "flex", alignItems: "center", gap: 6, overflow: "hidden" }}>
                      <input
                        type="checkbox"
                        checked={active}
                        onChange={(e) =>
                          setSelectedRefIds((prev) =>
                            e.target.checked ? [...prev, r.id] : prev.filter((id) => id !== r.id),
                          )
                        }
                      />
                      <span style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{r.filename}</span>
                    </span>
                    <span className="badge badge-neutral">{r.role}</span>
                  </label>
                );
              })}
            </div>
          )}
        </div>

        {/* Execution Approval Action */}
        <div className="subpanel" style={{ borderColor: "var(--accent-border)" }}>
          <h3>Generation Execution Gate</h3>
          <p className="muted" style={{ margin: 0, fontSize: 12 }}>
            Review exact provider, model, output parameters, and spend guard status before submitting.
          </p>
          <button
            id="review-approval-btn"
            type="button"
            className="btn btn-primary"
            disabled={!activePlan || busyAction !== null}
            onClick={handleRequestQuote}
          >
            {busyAction === "quoting" ? "Preparing Quote..." : "Review Quote & Approve Generation"}
          </button>
        </div>

        {/* Controlled Targeted Revision Panel */}
        {activePlan && (
          <form className="subpanel" onSubmit={handleRevise}>
            <h3>Controlled Revision</h3>
            <p className="muted" style={{ margin: 0, fontSize: 12 }}>
              Describe a targeted adjustment (e.g., warmer lighting, 85mm close-up, slower dolly). Unaffected approved
              decisions stay locked.
            </p>
            {activePlan.media_type === "video" && activePlan.video_plan && (
              <div className="field">
                <label htmlFor="rev-shot">Target Shot (Optional)</label>
                <select
                  id="rev-shot"
                  className="select"
                  value={revisionShotOrder}
                  onChange={(e) => setRevisionShotOrder(e.target.value)}
                >
                  <option value="">Sequence-wide / Auto-detect</option>
                  {activePlan.video_plan.shots.map((s) => (
                    <option key={s.shot_id} value={String(s.order)}>
                      {s.shot_id} ({s.start_s}s–{s.end_s}s)
                    </option>
                  ))}
                </select>
              </div>
            )}
            <div className="field">
              <label htmlFor="rev-input">Targeted Change Request</label>
              <input
                id="rev-input"
                className="input"
                value={revisionInput}
                onChange={(e) => setRevisionInput(e.target.value)}
                placeholder="e.g. Shift lighting warmer and 85mm close-up"
              />
            </div>
            <button id="apply-revision-btn" type="submit" className="btn btn-sm" disabled={!revisionInput.trim() || busyAction === "revising"}>
              {busyAction === "revising" ? "Mapping Revision..." : "Create Revised Plan (Preserve Locks)"}
            </button>
          </form>
        )}
      </aside>

      {pendingQuote && (
        <ApprovalModal
          quote={pendingQuote}
          submitting={busyAction === "generating"}
          onCancel={() => setPendingQuote(null)}
          onConfirm={handleConfirmGenerate}
        />
      )}
    </div>
  );
};
