import React from "react";

interface Props {
  status: string;
  label?: string;
}

const STYLE_MAP: Record<string, { cls: string; sym: string }> = {
  succeeded: { cls: "badge-success", sym: "✓" },
  pass_advisory: { cls: "badge-success", sym: "✓" },
  supported: { cls: "badge-success", sym: "●" },
  active: { cls: "badge-success", sym: "●" },
  accepted: { cls: "badge-success", sym: "✓" },
  feasible: { cls: "badge-success", sym: "✓" },

  processing: { cls: "badge-info", sym: "◌" },
  queued: { cls: "badge-info", sym: "◔" },
  submitted: { cls: "badge-info", sym: "↗" },
  inferred: { cls: "badge-info", sym: "◆" },
  core: { cls: "badge-info", sym: "■" },

  awaiting_approval: { cls: "badge-accent", sym: "◇" },
  user_specified: { cls: "badge-accent", sym: "★" },
  adapted: { cls: "badge-accent", sym: "◈" },

  unknown: { cls: "badge-warning", sym: "?" },
  review_recommended: { cls: "badge-warning", sym: "!" },
  requires_alternative: { cls: "badge-warning", sym: "!" },
  deprecated: { cls: "badge-warning", sym: "!" },
  provider_conditional: { cls: "badge-warning", sym: "◐" },
  warning: { cls: "badge-warning", sym: "▲" },
  conditional: { cls: "badge-neutral", sym: "◇" },

  failed: { cls: "badge-danger", sym: "✕" },
  rework_recommended: { cls: "badge-danger", sym: "✕" },
  unsupported: { cls: "badge-danger", sym: "⊘" },
  blocking: { cls: "badge-danger", sym: "⊘" },
  revoked: { cls: "badge-danger", sym: "⊘" },
  rejected: { cls: "badge-danger", sym: "✕" },
  critical: { cls: "badge-danger", sym: "✕" },

  cancelled: { cls: "badge-neutral", sym: "–" },
  draft: { cls: "badge-neutral", sym: "○" },
  deferred: { cls: "badge-neutral", sym: "…" },
};

export const StatusBadge: React.FC<Props> = ({ status, label }) => {
  const key = status.toLowerCase();
  const cfg = STYLE_MAP[key] ?? { cls: "badge-neutral", sym: "•" };
  const text = label ?? status.replace(/_/g, " ").toUpperCase();
  return (
    <span className={`badge ${cfg.cls}`}>
      <span aria-hidden="true">{cfg.sym}</span>
      <span>{text}</span>
    </span>
  );
};
