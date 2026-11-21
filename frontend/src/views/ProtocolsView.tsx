import React, { useEffect, useState } from "react";
import { api } from "../api/client";
import { StatusBadge } from "../components/StatusBadge";

export const ProtocolsView: React.FC = () => {
  const [layer, setLayer] = useState("");
  const [disposition, setDisposition] = useState("");
  const [search, setSearch] = useState("");
  const [data, setData] = useState<{
    registry_version: string;
    total_protocols: number;
    dispositions: Record<string, number>;
    layers: Record<string, number>;
    protocols: Array<{
      protocol_id: number;
      protocol_code: string;
      canonical_title: string;
      source_layer: string;
      disposition: string;
      decision_fields: string[];
      original_description: string;
    }>;
  } | null>(null);

  useEffect(() => {
    api.getProtocols({ layer: layer || undefined, disposition: disposition || undefined }).then(setData);
  }, [layer, disposition]);

  const filtered =
    data?.protocols.filter((p) => {
      if (!search.trim()) return true;
      const q = search.toLowerCase();
      return (
        p.protocol_code.toLowerCase().includes(q) ||
        p.canonical_title.toLowerCase().includes(q) ||
        p.original_description.toLowerCase().includes(q)
      );
    }) ?? [];

  return (
    <main className="page-container">
      <div className="section-head">
        <div>
          <h1>170-Protocol Production Intelligence Registry</h1>
          <p className="muted" style={{ margin: "4px 0 0" }}>
            Version {data?.registry_version ?? "1.0.0"} · {data?.total_protocols ?? 170} canonical protocols across 16
            production layers. Activated contextually per brief rather than shown as 170 questions.
          </p>
        </div>
        {data && (
          <div className="btn-row">
            {Object.entries(data.dispositions).map(([k, v]) => (
              <StatusBadge key={k} status={k} label={`${k.toUpperCase()}: ${v}`} />
            ))}
          </div>
        )}
      </div>

      <section className="panel">
        <div className="form-grid-3">
          <div className="field">
            <label htmlFor="proto-search">Search Protocol Code, Title, or Description</label>
            <input
              id="proto-search"
              className="input"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="e.g. P081, lighting, focal, continuity..."
            />
          </div>
          <div className="field">
            <label htmlFor="proto-layer">Layer (A–P)</label>
            <select id="proto-layer" className="select" value={layer} onChange={(e) => setLayer(e.target.value)}>
              <option value="">All 16 Layers</option>
              {data &&
                Object.keys(data.layers).map((l) => (
                  <option key={l} value={l.split(".")[0]}>
                    {l}
                  </option>
                ))}
            </select>
          </div>
          <div className="field">
            <label htmlFor="proto-disp">Disposition</label>
            <select id="proto-disp" className="select" value={disposition} onChange={(e) => setDisposition(e.target.value)}>
              <option value="">All Dispositions</option>
              <option value="core">Core</option>
              <option value="conditional">Conditional</option>
              <option value="adapted">Adapted</option>
              <option value="deferred">Deferred</option>
            </select>
          </div>
        </div>

        <div className="table-wrap">
          <table className="data-table">
            <thead>
              <tr>
                <th>Code</th>
                <th>Layer</th>
                <th>Canonical Title</th>
                <th>Disposition</th>
                <th>Production Role</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((p) => (
                <tr key={p.protocol_id}>
                  <td className="mono">{p.protocol_code}</td>
                  <td className="muted" style={{ whiteSpace: "nowrap" }}>{p.source_layer}</td>
                  <td><strong>{p.canonical_title}</strong></td>
                  <td><StatusBadge status={p.disposition} /></td>
                  <td className="muted">{p.original_description}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </main>
  );
};
