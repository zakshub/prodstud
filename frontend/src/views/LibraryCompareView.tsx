import React, { useEffect, useState } from "react";
import { api } from "../api/client";
import type { GeneratedAssetRecord, ProductionPlanRecord, QualityReviewRecord } from "../api/types";
import { StatusBadge } from "../components/StatusBadge";

interface Props {
  storageUsageBytes: number;
  initialComparePair: [string, string] | null;
  onOpenProjectAsset: (projectId: string) => void;
}

export const LibraryCompareView: React.FC<Props> = ({
  storageUsageBytes,
  initialComparePair,
  onOpenProjectAsset,
}) => {
  const [tab, setTab] = useState<"library" | "compare">(initialComparePair ? "compare" : "library");
  const [assets, setAssets] = useState<GeneratedAssetRecord[]>([]);
  const [query, setQuery] = useState("");
  const [mediaFilter, setMediaFilter] = useState("");
  const [favOnly, setFavOnly] = useState(false);
  const [selectedIds, setSelectedIds] = useState<string[]>([]);

  const [leftId, setLeftId] = useState(initialComparePair?.[0] ?? "");
  const [rightId, setRightId] = useState(initialComparePair?.[1] ?? "");
  const [comparison, setComparison] = useState<{
    left: { asset: GeneratedAssetRecord; plan: ProductionPlanRecord | null; review: QualityReviewRecord | null };
    right: { asset: GeneratedAssetRecord; plan: ProductionPlanRecord | null; review: QualityReviewRecord | null };
    decision_diffs: Array<{ field: string; left: unknown; right: unknown }>;
  } | null>(null);

  const loadAssets = async () => {
    const list = await api.searchAssets({
      q: query || undefined,
      media_type: mediaFilter || undefined,
      favorite_only: favOnly,
    });
    setAssets(list);
    if (!leftId && list.length >= 2) {
      setLeftId(list[1].id);
      setRightId(list[0].id);
    }
  };

  useEffect(() => {
    loadAssets();
  }, [mediaFilter, favOnly]);

  useEffect(() => {
    if (tab === "compare" && leftId && rightId && leftId !== rightId) {
      api.compareAssets(leftId, rightId).then(setComparison).catch(() => setComparison(null));
    }
  }, [tab, leftId, rightId]);

  const handleBulkExport = async () => {
    if (selectedIds.length === 0) return;
    const first = assets.find((a) => selectedIds.includes(a.id));
    if (!first) return;
    const sameProjectIds = assets.filter((a) => selectedIds.includes(a.id) && a.project_id === first.project_id).map((a) => a.id);
    const resp = await fetch(`/api/projects/${first.project_id}/export-bulk`, {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ asset_ids: sameProjectIds }),
    });
    if (!resp.ok) return;
    const blob = await resp.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `prodstud_bulk_export.zip`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const kb = (storageUsageBytes / 1024).toFixed(1);

  return (
    <main className="page-container">
      <div className="section-head">
        <div>
          <h1>{tab === "library" ? "Asset Library" : "Version Comparison"}</h1>
          <span className="small-mono">
            {assets.length} matching asset(s) · Private Storage Used: {kb} KB
          </span>
        </div>
        <div className="segmented" role="group" aria-label="Library or Comparison View">
          <button type="button" aria-pressed={tab === "library"} onClick={() => setTab("library")}>
            Asset Library
          </button>
          <button type="button" aria-pressed={tab === "compare"} onClick={() => setTab("compare")}>
            Side-by-Side Compare
          </button>
        </div>
      </div>

      {tab === "library" ? (
        <>
          <section className="panel" aria-label="Search and Filter Assets">
            <div className="form-grid-3" style={{ alignItems: "end" }}>
              <div className="field">
                <label htmlFor="lib-search">Search Filename, Tags, or Collection</label>
                <input
                  id="lib-search"
                  className="input"
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && loadAssets()}
                  placeholder="Filter by keyword..."
                />
              </div>
              <div className="field">
                <label htmlFor="lib-media">Media Type</label>
                <select id="lib-media" className="select" value={mediaFilter} onChange={(e) => setMediaFilter(e.target.value)}>
                  <option value="">All Media</option>
                  <option value="image">Images Only</option>
                  <option value="video">Videos Only</option>
                </select>
              </div>
              <div className="btn-row">
                <label style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 13 }}>
                  <input type="checkbox" checked={favOnly} onChange={(e) => setFavOnly(e.target.checked)} />
                  Favorites only
                </label>
                <button type="button" className="btn btn-primary btn-sm" onClick={loadAssets}>
                  Search
                </button>
                {selectedIds.length > 0 && (
                  <button type="button" className="btn btn-sm" onClick={handleBulkExport}>
                    Bulk Export ZIP ({selectedIds.length})
                  </button>
                )}
              </div>
            </div>
          </section>

          {assets.length === 0 ? (
            <section className="panel" style={{ padding: 28, textAlign: "center" }}>
              <h2>No assets match the current filter</h2>
              <p className="muted">Generate an image or video inside a project workspace to populate your library.</p>
            </section>
          ) : (
            <section className="asset-grid">
              {assets.map((a) => (
                <article key={a.id} className="asset-card">
                  <div className="asset-thumb">
                    {a.media_type === "image" ? (
                      <img src={`/api/assets/${a.id}/file`} alt={a.filename} loading="lazy" />
                    ) : (
                      <video src={`/api/assets/${a.id}/file`} muted preload="metadata" />
                    )}
                  </div>
                  <div style={{ padding: 12, display: "flex", flexDirection: "column", gap: 6 }}>
                    <div className="section-head">
                      <label style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 12, fontWeight: 600 }}>
                        <input
                          type="checkbox"
                          checked={selectedIds.includes(a.id)}
                          onChange={(e) =>
                            setSelectedIds((prev) =>
                              e.target.checked ? [...prev, a.id] : prev.filter((id) => id !== a.id),
                            )
                          }
                        />
                        <span className="mono">v{String(a.version_number).padStart(2, "0")}</span>
                      </label>
                      <div className="btn-row">
                        <StatusBadge status={a.media_type === "image" ? "core" : "adapted"} label={a.media_type.toUpperCase()} />
                        {a.is_favorite && <span aria-label="Favorited">★</span>}
                      </div>
                    </div>
                    <div style={{ fontSize: 12, fontWeight: 500, wordBreak: "break-all" }}>{a.filename}</div>
                    <div className="small-mono">
                      {a.width}×{a.height}
                      {a.duration_s ? ` · ${a.duration_s.toFixed(1)}s` : ""}
                      {a.collection_name ? ` · ${a.collection_name}` : ""}
                    </div>
                    {a.tags.length > 0 && (
                      <div className="btn-row">
                        {a.tags.map((t) => (
                          <span key={t} className="badge badge-neutral">
                            {t}
                          </span>
                        ))}
                      </div>
                    )}
                    <div className="btn-row" style={{ marginTop: 4 }}>
                      <button type="button" className="btn btn-sm" onClick={() => onOpenProjectAsset(a.project_id)}>
                        Open Project
                      </button>
                      <a className="btn btn-sm" href={`/api/assets/${a.id}/export`} download>
                        Export
                      </a>
                    </div>
                  </div>
                </article>
              ))}
            </section>
          )}
        </>
      ) : (
        <section className="panel" aria-label="Side-by-Side Version Comparator">
          <div className="form-grid-2">
            <div className="field">
              <label htmlFor="cmp-left">Baseline Asset (Left)</label>
              <select id="cmp-left" className="select mono" value={leftId} onChange={(e) => setLeftId(e.target.value)}>
                <option value="">Select asset...</option>
                {assets.map((a) => (
                  <option key={a.id} value={a.id}>
                    v{String(a.version_number).padStart(2, "0")} · {a.media_type} · {a.filename}
                  </option>
                ))}
              </select>
            </div>
            <div className="field">
              <label htmlFor="cmp-right">Revised Asset (Right)</label>
              <select id="cmp-right" className="select mono" value={rightId} onChange={(e) => setRightId(e.target.value)}>
                <option value="">Select asset...</option>
                {assets.map((a) => (
                  <option key={a.id} value={a.id}>
                    v{String(a.version_number).padStart(2, "0")} · {a.media_type} · {a.filename}
                  </option>
                ))}
              </select>
            </div>
          </div>

          {comparison ? (
            <>
              <div className="compare-grid">
                {[comparison.left, comparison.right].map((side, i) => (
                  <div key={side.asset.id} className="subpanel">
                    <div className="section-head">
                      <strong>
                        {i === 0 ? "Left" : "Right"} · v{String(side.asset.version_number).padStart(2, "0")}
                      </strong>
                      <span className="small-mono">
                        QC: {side.review?.weighted_score?.toFixed(2) ?? "N/A"} / 5.0
                      </span>
                    </div>
                    <div className="asset-stage-frame" style={{ minHeight: 240 }}>
                      {side.asset.media_type === "image" ? (
                        <img src={`/api/assets/${side.asset.id}/file`} alt={side.asset.filename} />
                      ) : (
                        <video controls src={`/api/assets/${side.asset.id}/file`} />
                      )}
                    </div>
                    <div className="small-mono">{side.asset.filename}</div>
                  </div>
                ))}
              </div>

              <div className="subpanel">
                <h3>Production Decision Differences ({comparison.decision_diffs.length})</h3>
                {comparison.decision_diffs.length === 0 ? (
                  <p className="muted" style={{ margin: 0 }}>
                    No structural plan field differences detected between selected versions.
                  </p>
                ) : (
                  <div className="table-wrap">
                    <table className="data-table">
                      <thead>
                        <tr>
                          <th>Field</th>
                          <th>Left Version</th>
                          <th>Right Version</th>
                        </tr>
                      </thead>
                      <tbody>
                        {comparison.decision_diffs.map((d) => (
                          <tr key={d.field}>
                            <td className="mono">{d.field}</td>
                            <td className="muted">{typeof d.left === "object" ? JSON.stringify(d.left) : String(d.left)}</td>
                            <td><strong>{typeof d.right === "object" ? JSON.stringify(d.right) : String(d.right)}</strong></td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            </>
          ) : (
            <p className="muted">Select two distinct assets above to compare visuals and changed production decisions.</p>
          )}
        </section>
      )}
    </main>
  );
};
