import React, { useState } from "react";
import { api } from "../api/client";
import type { ProductionTemplateRecord, ProjectRecord } from "../api/types";
import { StatusBadge } from "../components/StatusBadge";

interface Props {
  projects: ProjectRecord[];
  templates: ProductionTemplateRecord[];
  includeArchived: boolean;
  onToggleArchived: (v: boolean) => void;
  onOpenProject: (projectId: string) => void;
  onProjectsChanged: () => Promise<void>;
}

export const ProjectsView: React.FC<Props> = ({
  projects,
  templates,
  includeArchived,
  onToggleArchived,
  onOpenProject,
  onProjectsChanged,
}) => {
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [creating, setCreating] = useState(false);
  const [renamingId, setRenamingId] = useState<string | null>(null);
  const [renameValue, setRenameValue] = useState("");
  const [error, setError] = useState<string | null>(null);

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) return;
    setCreating(true);
    setError(null);
    try {
      const created = await api.createProject(name.trim(), description.trim());
      setName("");
      setDescription("");
      await onProjectsChanged();
      onOpenProject(created.id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create project.");
    } finally {
      setCreating(false);
    }
  };

  const handleRename = async (projectId: string) => {
    if (!renameValue.trim()) return;
    setError(null);
    try {
      await api.updateProject(projectId, { name: renameValue.trim() });
      setRenamingId(null);
      await onProjectsChanged();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to rename project.");
    }
  };

  const handleArchiveToggle = async (project: ProjectRecord) => {
    if (!project.archived && !window.confirm(`Archive project "${project.name}"? You can reopen it anytime from archived view.`)) {
      return;
    }
    setError(null);
    try {
      await api.updateProject(project.id, { archived: !project.archived });
      await onProjectsChanged();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to update project status.");
    }
  };

  return (
    <main className="page-container">
      <div className="section-head">
        <div>
          <h1>Production Projects</h1>
          <p className="muted" style={{ margin: "4px 0 0" }}>
            Select a project workspace to plan, generate, inspect, revise, and export image and video assets.
          </p>
        </div>
        <label style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 13 }}>
          <input
            type="checkbox"
            checked={includeArchived}
            onChange={(e) => onToggleArchived(e.target.checked)}
          />
          Show archived projects
        </label>
      </div>

      <section className="panel" aria-label="Create New Project">
        <h2>New Project</h2>
        <form onSubmit={handleCreate} className="form-grid-3" style={{ alignItems: "end" }}>
          <div className="field">
            <label htmlFor="new-project-name">Project Name</label>
            <input
              id="new-project-name"
              className="input"
              required
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. Autumn Ceramic Launch"
            />
          </div>
          <div className="field">
            <label htmlFor="new-project-desc">Production Objective (Optional)</label>
            <input
              id="new-project-desc"
              className="input"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Hero tabletop stills + 8s launch reel"
            />
          </div>
          <div>
            <button id="create-project-btn" type="submit" className="btn btn-primary" disabled={creating} style={{ width: "100%" }}>
              {creating ? "Creating..." : "Create & Open Project"}
            </button>
          </div>
        </form>
        {error && <div className="callout callout-danger">{error}</div>}
      </section>

      {projects.length === 0 ? (
        <section className="panel" style={{ padding: 32, textAlign: "center" }}>
          <h2>No active projects yet</h2>
          <p className="muted">Create your first project above to open the asset-first Image &amp; Video Production Workspace.</p>
        </section>
      ) : (
        <section className="project-grid" aria-label="Project List">
          {projects.map((p) => (
            <article key={p.id} className="panel">
              <div className="section-head">
                {renamingId === p.id ? (
                  <div className="btn-row" style={{ flex: 1 }}>
                    <input
                      className="input"
                      aria-label="New project name"
                      value={renameValue}
                      onChange={(e) => setRenameValue(e.target.value)}
                    />
                    <button type="button" className="btn btn-primary btn-sm" onClick={() => handleRename(p.id)}>
                      Save
                    </button>
                    <button type="button" className="btn btn-sm" onClick={() => setRenamingId(null)}>
                      Cancel
                    </button>
                  </div>
                ) : (
                  <h2>{p.name}</h2>
                )}
                {p.archived && <StatusBadge status="cancelled" label="ARCHIVED" />}
              </div>

              <p className="muted" style={{ margin: 0, minHeight: 20 }}>
                {p.description || "No project description recorded."}
              </p>

              <div className="small-mono">
                {p.asset_count} asset(s) · Updated {new Date(p.updated_at).toLocaleString()}
              </div>

              <div className="btn-row" style={{ marginTop: "auto", paddingTop: 8 }}>
                <button type="button" className="btn btn-primary btn-sm" onClick={() => onOpenProject(p.id)}>
                  Open Workspace
                </button>
                <button
                  type="button"
                  className="btn btn-sm"
                  onClick={() => {
                    setRenamingId(p.id);
                    setRenameValue(p.name);
                  }}
                >
                  Rename
                </button>
                <button type="button" className="btn btn-sm" onClick={() => handleArchiveToggle(p)}>
                  {p.archived ? "Reopen" : "Archive"}
                </button>
              </div>
            </article>
          ))}
        </section>
      )}

      {templates.length > 0 && (
        <section className="panel" aria-label="Saved Reusable Templates">
          <h2>Saved Production Templates ({templates.length})</h2>
          <div className="project-grid">
            {templates.map((t) => (
              <div key={t.id} className="subpanel">
                <div className="section-head">
                  <strong>{t.name}</strong>
                  <StatusBadge status={t.media_type === "image" ? "core" : "adapted"} label={t.media_type.toUpperCase()} />
                </div>
                <div className="muted" style={{ fontSize: 12 }}>
                  {t.description || "Reusable production brief preset."}
                </div>
              </div>
            ))}
          </div>
        </section>
      )}
    </main>
  );
};
