import type {
  ApprovalQuote,
  AuditEventRecord,
  CredentialSummary,
  GeneratedAssetRecord,
  GenerationJobRecord,
  MediaType,
  ProductionPlanRecord,
  ProductionTemplateRecord,
  ProjectRecord,
  ProjectWorkspaceData,
  ProviderModelCapability,
  QualityReviewRecord,
  ReferenceAssetRecord,
  RevisionRecord,
  UserProfile,
} from "./types";

async function apiFetch<T>(url: string, options: RequestInit = {}): Promise<T> {
  const headers: Record<string, string> = {
    ...(options.headers as Record<string, string> | undefined),
  };
  if (options.body && !(options.body instanceof FormData) && !headers["Content-Type"]) {
    headers["Content-Type"] = "application/json";
  }
  const resp = await fetch(url, {
    ...options,
    headers,
    credentials: "include",
  });
  if (!resp.ok) {
    let detail = `Request failed (HTTP ${resp.status})`;
    try {
      const data = await resp.json();
      if (typeof data.detail === "string") detail = data.detail;
      else if (data.detail?.message) detail = data.detail.message;
    } catch {
      /* ignore parse error */
    }
    throw new Error(detail);
  }
  return resp.json() as Promise<T>;
}

export const api = {
  // Auth & Settings
  session: () =>
    apiFetch<{
      authenticated: boolean;
      user: UserProfile | null;
      environment?: string;
      local_test_fixture_enabled?: boolean;
      storage_usage_bytes?: number;
    }>("/api/auth/session"),

  me: () =>
    apiFetch<{
      user: UserProfile;
      environment: string;
      local_test_fixture_enabled: boolean;
      storage_usage_bytes: number;
    }>("/api/auth/me"),

  register: (payload: { email: string; display_name: string; password: string }) =>
    apiFetch<{ user: UserProfile }>("/api/auth/register", { method: "POST", body: JSON.stringify(payload) }),

  login: (payload: { email: string; password: string }) =>
    apiFetch<{ user: UserProfile }>("/api/auth/login", { method: "POST", body: JSON.stringify(payload) }),

  logout: () => apiFetch<{ status: string }>("/api/auth/logout", { method: "POST" }),

  updateSettings: (payload: { display_name?: string; daily_spend_cap_usd?: number; preferred_theme?: "dark" | "light" }) =>
    apiFetch<UserProfile>("/api/settings", { method: "PATCH", body: JSON.stringify(payload) }),

  // Server-side Encrypted Credentials (keys NEVER stored in browser storage)
  listCredentials: () => apiFetch<CredentialSummary[]>("/api/settings/credentials"),

  saveCredential: (provider: string, api_key: string) =>
    apiFetch<CredentialSummary>("/api/settings/credentials", {
      method: "POST",
      body: JSON.stringify({ provider, api_key }),
    }),

  validateCredential: (provider: string) =>
    apiFetch<{ provider: string; valid: boolean; note: string; validated_at: string }>(
      `/api/settings/credentials/${encodeURIComponent(provider)}/validate`,
      { method: "POST" },
    ),

  revokeCredential: (provider: string) =>
    apiFetch<{ provider: string; status: string }>(`/api/settings/credentials/${encodeURIComponent(provider)}`, {
      method: "DELETE",
    }),

  // Projects & References
  listProjects: (includeArchived = false) =>
    apiFetch<ProjectRecord[]>(`/api/projects?include_archived=${includeArchived ? "true" : "false"}`),

  createProject: (name: string, description = "") =>
    apiFetch<ProjectRecord>("/api/projects", { method: "POST", body: JSON.stringify({ name, description }) }),

  updateProject: (projectId: string, payload: { name?: string; description?: string; archived?: boolean }) =>
    apiFetch<ProjectRecord>(`/api/projects/${projectId}`, { method: "PATCH", body: JSON.stringify(payload) }),

  getProjectWorkspace: (projectId: string) => apiFetch<ProjectWorkspaceData>(`/api/projects/${projectId}`),

  uploadReference: (projectId: string, file: File, role: string, rightsConfirmed: boolean, notes = "") => {
    const fd = new FormData();
    fd.append("file", file);
    fd.append("role", role);
    fd.append("rights_confirmed", rightsConfirmed ? "true" : "false");
    fd.append("notes", notes);
    return apiFetch<ReferenceAssetRecord>(`/api/projects/${projectId}/references`, { method: "POST", body: fd });
  },

  // Capabilities & 170 Protocols
  listCapabilities: (mediaType?: MediaType) =>
    apiFetch<ProviderModelCapability[]>(mediaType ? `/api/capabilities?media_type=${mediaType}` : "/api/capabilities"),

  getProtocols: (params?: { layer?: string; disposition?: string }) => {
    const qs = new URLSearchParams();
    if (params?.layer) qs.set("layer", params.layer);
    if (params?.disposition) qs.set("disposition", params.disposition);
    const tail = qs.toString() ? `?${qs.toString()}` : "";
    return apiFetch<{
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
    }>(`/api/protocols/summary${tail}`);
  },

  // Production Planning, Approval Quote, Generation Jobs, Review, Revision & Compare
  createPlan: (projectId: string, payload: Record<string, unknown>) =>
    apiFetch<ProductionPlanRecord>(`/api/projects/${projectId}/plans`, {
      method: "POST",
      body: JSON.stringify({ ...payload, project_id: projectId }),
    }),

  editPlan: (planId: string, payload: Record<string, unknown>) =>
    apiFetch<ProductionPlanRecord>(`/api/plans/${planId}`, { method: "PATCH", body: JSON.stringify(payload) }),

  requestQuote: (planId: string, provider_id: string, model_id: string) =>
    apiFetch<ApprovalQuote>(`/api/plans/${planId}/quote`, {
      method: "POST",
      body: JSON.stringify({ provider_id, model_id }),
    }),

  submitGeneration: (
    planId: string,
    payload: {
      quote_id: string;
      confirmation_token: string;
      explicit_user_confirmed: boolean;
      parent_asset_id?: string | null;
    },
  ) =>
    apiFetch<{
      job: GenerationJobRecord;
      asset: GeneratedAssetRecord | null;
      quality_review: QualityReviewRecord | null;
    }>(`/api/plans/${planId}/generate`, { method: "POST", body: JSON.stringify(payload) }),

  pollJob: (jobId: string) =>
    apiFetch<{
      job: GenerationJobRecord;
      asset: GeneratedAssetRecord | null;
      quality_review: QualityReviewRecord | null;
    }>(`/api/jobs/${jobId}/poll`, { method: "POST" }),

  cancelJob: (jobId: string) => apiFetch<{ job: GenerationJobRecord }>(`/api/jobs/${jobId}/cancel`, { method: "POST" }),

  getAssetReview: (assetId: string) => apiFetch<QualityReviewRecord>(`/api/assets/${assetId}/review`),

  submitReviewFeedback: (reviewId: string, status: "accepted" | "rejected" | "needs_rework", note: string) =>
    apiFetch<QualityReviewRecord>(`/api/reviews/${reviewId}/feedback`, {
      method: "POST",
      body: JSON.stringify({ status, note }),
    }),

  revisePlan: (planId: string, change_request: string, sourceAssetId?: string | null, targetShotOrder?: number | null) => {
    const qs = sourceAssetId ? `?source_asset_id=${encodeURIComponent(sourceAssetId)}` : "";
    return apiFetch<{ plan: ProductionPlanRecord; revision: RevisionRecord }>(`/api/plans/${planId}/revise${qs}`, {
      method: "POST",
      body: JSON.stringify({
        change_request,
        target_shot_order: targetShotOrder ?? null,
      }),
    });
  },

  searchAssets: (params: {
    project_id?: string;
    media_type?: string;
    tag?: string;
    collection_name?: string;
    favorite_only?: boolean;
    q?: string;
  }) => {
    const qs = new URLSearchParams();
    Object.entries(params).forEach(([k, v]) => {
      if (v !== undefined && v !== "" && v !== false) qs.set(k, String(v));
    });
    const tail = qs.toString() ? `?${qs.toString()}` : "";
    return apiFetch<GeneratedAssetRecord[]>(`/api/assets${tail}`);
  },

  organizeAsset: (
    assetId: string,
    payload: { tags?: string[]; collection_name?: string; is_favorite?: boolean; accepted?: boolean },
  ) => apiFetch<GeneratedAssetRecord>(`/api/assets/${assetId}`, { method: "PATCH", body: JSON.stringify(payload) }),

  compareAssets: (leftId: string, rightId: string) =>
    apiFetch<{
      left: { asset: GeneratedAssetRecord; plan: ProductionPlanRecord | null; review: QualityReviewRecord | null };
      right: { asset: GeneratedAssetRecord; plan: ProductionPlanRecord | null; review: QualityReviewRecord | null };
      decision_diffs: Array<{ field: string; left: unknown; right: unknown }>;
    }>(`/api/assets/compare?left_id=${encodeURIComponent(leftId)}&right_id=${encodeURIComponent(rightId)}`),

  listTemplates: () => apiFetch<ProductionTemplateRecord[]>("/api/templates"),

  createTemplate: (payload: { name: string; media_type: MediaType; description: string; default_brief: Record<string, unknown> }) =>
    apiFetch<ProductionTemplateRecord>("/api/templates", { method: "POST", body: JSON.stringify(payload) }),

  listAudit: (projectId?: string) =>
    apiFetch<AuditEventRecord[]>(projectId ? `/api/audit?project_id=${encodeURIComponent(projectId)}` : "/api/audit"),
};
