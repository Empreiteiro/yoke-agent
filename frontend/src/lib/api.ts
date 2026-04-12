const API_BASE = "/api";
const API_KEY_STORAGE_KEY = "rag-api-key";
const JWT_STORAGE_KEY = "rag-jwt";

export function getStoredApiKey(): string {
  if (typeof window === "undefined") return "";
  return localStorage.getItem(API_KEY_STORAGE_KEY) || "";
}

export function setStoredApiKey(key: string) {
  if (typeof window === "undefined") return;
  if (key) {
    localStorage.setItem(API_KEY_STORAGE_KEY, key);
  } else {
    localStorage.removeItem(API_KEY_STORAGE_KEY);
  }
}

export function getStoredJwt(): string {
  if (typeof window === "undefined") return "";
  return localStorage.getItem(JWT_STORAGE_KEY) || "";
}

export function setStoredJwt(token: string) {
  if (typeof window === "undefined") return;
  if (token) {
    localStorage.setItem(JWT_STORAGE_KEY, token);
  } else {
    localStorage.removeItem(JWT_STORAGE_KEY);
  }
}

function authHeaders(): Record<string, string> {
  // JWT takes priority over the long-lived API key when both are present.
  const jwt = getStoredJwt();
  if (jwt) return { Authorization: `Bearer ${jwt}` };
  const key = getStoredApiKey();
  return key ? { "X-API-Key": key } : {};
}

async function request<T>(
  path: string,
  options?: RequestInit
): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: {
      "Content-Type": "application/json",
      ...authHeaders(),
      ...options?.headers,
    },
    ...options,
  });

  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(error.detail || "Request failed");
  }

  // 204 No Content — nothing to parse
  if (res.status === 204) return undefined as T;

  return res.json();
}

export const api = {
  // Documents
  uploadDocuments: async (files: File[]) => {
    const formData = new FormData();
    files.forEach((f) => formData.append("files", f));
    const res = await fetch(`${API_BASE}/documents/upload`, {
      method: "POST",
      headers: authHeaders(),
      body: formData,
    });
    if (!res.ok) throw new Error("Upload failed");
    return res.json();
  },
  listDocuments: () => request<any>("/documents/"),
  deleteDocument: (id: number) =>
    request(`/documents/${id}`, { method: "DELETE" }),

  // Datasets
  createDataset: (data: { name: string; description?: string; document_ids: number[] }) =>
    request<any>("/datasets/", { method: "POST", body: JSON.stringify(data) }),
  listDatasets: () => request<any[]>("/datasets/"),
  getDataset: (id: number) => request<any>(`/datasets/${id}`),
  deleteDataset: (id: number) => request<any>(`/datasets/${id}`, { method: "DELETE" }),
  bulkDeleteDatasets: (ids: number[]) =>
    request<any>("/datasets/bulk-delete", { method: "POST", body: JSON.stringify({ ids }) }),
  duplicateDataset: (id: number) => request<any>(`/datasets/${id}/duplicate`, { method: "POST" }),
  generateDataset: (id: number, options?: { reading_mode?: string; max_pages?: number; num_questions?: number }) =>
    request<any>(`/datasets/${id}/generate`, {
      method: "POST",
      body: options ? JSON.stringify(options) : undefined,
    }),
  addDatasetItem: (id: number, item: { question: string; ground_truth: string; context?: string }) =>
    request<any>(`/datasets/${id}/items`, { method: "POST", body: JSON.stringify(item) }),
  updateDatasetItem: (datasetId: number, itemId: number, item: any) =>
    request<any>(`/datasets/${datasetId}/items/${itemId}`, {
      method: "PUT",
      body: JSON.stringify(item),
    }),
  deleteDatasetItem: (datasetId: number, itemId: number) =>
    request<any>(`/datasets/${datasetId}/items/${itemId}`, { method: "DELETE" }),
  importDatasetItems: async (datasetId: number, file: File) => {
    const formData = new FormData();
    formData.append("file", file);
    const res = await fetch(`${API_BASE}/datasets/${datasetId}/import`, {
      method: "POST",
      headers: authHeaders(),
      body: formData,
    });
    if (!res.ok) throw new Error("Import failed");
    return res.json();
  },
  approveDataset: (id: number) =>
    request<any>(`/datasets/${id}/approve`, { method: "POST" }),
  seedBenchmarks: () =>
    request<any>("/datasets/seed-benchmarks", { method: "POST" }),

  // Experiments
  createExperiment: (data: { name: string; description?: string; dataset_id: number; vectorstore_type?: string }) =>
    request<any>("/experiments/", { method: "POST", body: JSON.stringify(data) }),
  listExperiments: () => request<any[]>("/experiments/"),
  getExperiment: (id: number) => request<any>(`/experiments/${id}`),
  deleteExperiment: (id: number) => request<any>(`/experiments/${id}`, { method: "DELETE" }),
  bulkDeleteExperiments: (ids: number[]) =>
    request<any>("/experiments/bulk-delete", { method: "POST", body: JSON.stringify({ ids }) }),
  proposeGridSearch: (id: number) =>
    request<any>(`/experiments/${id}/propose-grid`, { method: "POST" }),
  configureGrid: (id: number, config: any) =>
    request<any>(`/experiments/${id}/configure-grid`, {
      method: "POST",
      body: JSON.stringify(config),
    }),
  runExperiment: (id: number) =>
    request<any>(`/experiments/${id}/run`, { method: "POST" }),
  stopExperiment: (id: number) =>
    request<any>(`/experiments/${id}/stop`, { method: "POST" }),
  resumeExperiment: (id: number, retryFailed: boolean = false) =>
    request<any>(`/experiments/${id}/resume?retry_failed=${retryFailed}`, { method: "POST" }),
  getExperimentReport: (id: number) =>
    request<any>(`/experiments/${id}/report`),
  estimateCost: (id: number, config: any) =>
    request<any>(`/experiments/${id}/estimate-cost`, { method: "POST", body: JSON.stringify(config) }),
  exportExperimentCSV: (id: number) =>
    `${API_BASE}/experiments/${id}/export?format=csv`,
  exportRatedQuestionsCSV: (id: number) =>
    `${API_BASE}/experiments/${id}/export-rated`,
  exportExperimentFailuresCSV: (id: number) =>
    `${API_BASE}/experiments/${id}/failures/export`,

  // Human ratings (issue #118)
  listCombinationRatings: (combinationId: number) =>
    request<any[]>(`/experiments/combinations/${combinationId}/ratings`),
  upsertCombinationRating: (
    combinationId: number,
    payload: {
      question_index: number;
      rating: "correct" | "incorrect" | "partial";
      notes?: string;
      question_text?: string;
    }
  ) =>
    request<any>(`/experiments/combinations/${combinationId}/ratings`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  deleteCombinationRating: (combinationId: number, ratingId: number) =>
    request<any>(
      `/experiments/combinations/${combinationId}/ratings/${ratingId}`,
      { method: "DELETE" }
    ),
  getExperimentCorrelation: (id: number) =>
    request<any>(`/experiments/${id}/correlation`),

  // Vector stores
  getVectorStoreCatalog: () => request<any>("/vectorstores/catalog"),
  listVectorStoreConfigs: () => request<any[]>("/vectorstores/configs"),
  createVectorStoreConfig: (data: any) =>
    request<any>("/vectorstores/configs", { method: "POST", body: JSON.stringify(data) }),
  updateVectorStoreConfig: (id: number, data: any) =>
    request<any>(`/vectorstores/configs/${id}`, { method: "PUT", body: JSON.stringify(data) }),
  deleteVectorStoreConfig: (id: number) =>
    request<any>(`/vectorstores/configs/${id}`, { method: "DELETE" }),
  testVectorStoreConfig: (id: number) =>
    request<any>(`/vectorstores/configs/${id}/test`, { method: "POST" }),
  getAvailableVectorStores: () => request<any[]>("/vectorstores/available"),

  // Providers
  getProviderCatalog: () => request<any>("/providers/catalog"),
  listProviders: () => request<any[]>("/providers/"),
  createProvider: (data: any) =>
    request<any>("/providers/", { method: "POST", body: JSON.stringify(data) }),
  updateProvider: (id: number, data: any) =>
    request<any>(`/providers/${id}`, { method: "PUT", body: JSON.stringify(data) }),
  deleteProvider: (id: number) =>
    request<any>(`/providers/${id}`, { method: "DELETE" }),
  testProvider: (id: number) =>
    request<any>(`/providers/${id}/test`, { method: "POST" }),
  discoverOllamaModels: (baseUrl: string) =>
    request<any>(`/providers/ollama/discover?base_url=${encodeURIComponent(baseUrl)}`),
  getAvailableModels: () => request<any>("/providers/models/available"),
  getEmbeddingDimensions: () => request<any>("/providers/models/embedding-dimensions"),
  getClaudeCodeStatus: () => request<any>("/providers/claude-code/status"),
  saveClaudeCodeToken: (token: string) =>
    request<any>("/providers/claude-code/auth", { method: "POST", body: JSON.stringify({ token }) }),

  // Collections
  listCollections: () => request<any[]>("/collections/"),
  saveCollectionFromExperiment: (experimentId: number) =>
    request<any>(`/collections/save-from-experiment/${experimentId}`, { method: "POST" }),
  deleteCollection: (id: number) => request<any>(`/collections/${id}`, { method: "DELETE" }),
  queryCollection: (id: number, data: { question: string; top_k?: number }) =>
    request<any>(`/collections/${id}/query`, { method: "POST", body: JSON.stringify(data) }),

  // Token Usage
  listTokenUsage: (params?: {
    days?: number;
    operation?: string;
    model_type?: string;
    model_name?: string;
    experiment_id?: number;
    limit?: number;
    offset?: number;
  }) => {
    const searchParams = new URLSearchParams();
    if (params?.days) searchParams.set("days", params.days.toString());
    if (params?.operation) searchParams.set("operation", params.operation);
    if (params?.model_type) searchParams.set("model_type", params.model_type);
    if (params?.model_name) searchParams.set("model_name", params.model_name);
    if (params?.experiment_id) searchParams.set("experiment_id", params.experiment_id.toString());
    if (params?.limit) searchParams.set("limit", params.limit.toString());
    if (params?.offset) searchParams.set("offset", params.offset.toString());
    const qs = searchParams.toString();
    return request<any[]>(`/token-usage/${qs ? `?${qs}` : ""}`);
  },
  getTokenUsageSummary: (params?: { days?: number; experiment_id?: number }) => {
    const searchParams = new URLSearchParams();
    if (params?.days) searchParams.set("days", params.days.toString());
    if (params?.experiment_id) searchParams.set("experiment_id", params.experiment_id.toString());
    const qs = searchParams.toString();
    return request<any>(`/token-usage/summary${qs ? `?${qs}` : ""}`);
  },

  // Auth
  getAuthStatus: () => request<any>("/auth/status"),
  listApiKeys: () => request<any[]>("/auth/keys"),
  createApiKey: (name: string) =>
    request<any>("/auth/keys", { method: "POST", body: JSON.stringify({ name }) }),
  deleteApiKey: (id: number) =>
    request<any>(`/auth/keys/${id}`, { method: "DELETE" }),

  // Users / sessions (issue #123)
  register: (email: string, password: string) =>
    request<any>("/users/register", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    }),
  login: (email: string, password: string) =>
    request<any>("/users/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    }),
  getMe: () => request<any>("/users/me"),
  listUsers: () => request<any[]>("/users/"),
  updateUserRole: (userId: number, role: "admin" | "user" | "viewer") =>
    request<any>(`/users/${userId}/role`, {
      method: "PATCH",
      body: JSON.stringify({ role }),
    }),
  listAuditLogs: (limit = 200) =>
    request<any[]>(`/users/audit-logs?limit=${limit}`),

  // MCP
  listMcpTools: () => request<any>("/mcp/tools"),
  updateMcpTools: (disabledTools: string[]) =>
    request<any>("/mcp/tools", {
      method: "PUT",
      body: JSON.stringify({ disabled_tools: disabledTools }),
    }),
  getMcpConnectionInfo: () => request<any>("/mcp/connection-info"),

  // ── Agent Evaluation Pipeline ────────────────────────────────────

  // Agent Configs
  listAgentConfigs: () => request<any[]>("/agent/configs/"),
  createAgentConfig: (data: any) =>
    request<any>("/agent/configs/", { method: "POST", body: JSON.stringify(data) }),
  getAgentConfig: (id: number) => request<any>(`/agent/configs/${id}`),
  updateAgentConfig: (id: number, data: any) =>
    request<any>(`/agent/configs/${id}`, { method: "PUT", body: JSON.stringify(data) }),
  deleteAgentConfig: (id: number) =>
    request<any>(`/agent/configs/${id}`, { method: "DELETE" }),

  // External HTTP agents (issue #169)
  testHttpAgentEndpoint: (data: {
    http_endpoint: string;
    http_auth_header?: string;
    http_timeout_seconds?: number;
    sample_message?: string;
    http_body_template?: string;
    http_response_path?: string;
    http_tool_calls_path?: string;
  }) =>
    request<{
      ok: boolean;
      status_code?: number;
      response_preview?: string;
      detected_format?: string;
      tool_calls_detected: number;
      latency_ms?: number;
      error?: string;
      rendered_body?: string;
    }>("/agent/configs/test-http", { method: "POST", body: JSON.stringify(data) }),
  testSavedHttpAgent: (configId: number) =>
    request<{
      ok: boolean;
      status_code?: number;
      response_preview?: string;
      detected_format?: string;
      tool_calls_detected: number;
      latency_ms?: number;
      error?: string;
      rendered_body?: string;
    }>(`/agent/configs/${configId}/test-http`, { method: "POST" }),

  // AI Enhance
  enhancePrompt: (data: { text: string; context?: string }) =>
    request<{ result: string }>("/agent/configs/enhance/prompt", { method: "POST", body: JSON.stringify(data) }),
  enhanceDescription: (data: { text: string; context?: string }) =>
    request<{ result: string }>("/agent/configs/enhance/description", { method: "POST", body: JSON.stringify(data) }),
  suggestTools: (data: { agent_name: string; description: string; system_prompt: string; existing_tools?: any[] }) =>
    request<{ tools: any[] }>("/agent/configs/enhance/suggest-tools", { method: "POST", body: JSON.stringify(data) }),

  // Prompt Variants
  listPromptVariants: (configId: number) =>
    request<any[]>(`/agent/configs/${configId}/variants`),
  createPromptVariant: (configId: number, data: any) =>
    request<any>(`/agent/configs/${configId}/variants`, { method: "POST", body: JSON.stringify(data) }),
  deletePromptVariant: (configId: number, variantId: number) =>
    request<any>(`/agent/configs/${configId}/variants/${variantId}`, { method: "DELETE" }),
  generatePromptVariants: (configId: number, data: { count?: number; focus?: string }) =>
    request<any[]>(`/agent/configs/${configId}/variants/generate`, { method: "POST", body: JSON.stringify(data) }),

  // Scenarios
  listScenarios: (configId: number, scenarioType?: string) =>
    request<any[]>(`/agent/configs/${configId}/scenarios${scenarioType ? `?scenario_type=${scenarioType}` : ""}`),
  createScenario: (configId: number, data: any) =>
    request<any>(`/agent/configs/${configId}/scenarios`, { method: "POST", body: JSON.stringify(data) }),
  createScenariosBulk: (configId: number, data: any[]) =>
    request<any[]>(`/agent/configs/${configId}/scenarios/bulk`, { method: "POST", body: JSON.stringify(data) }),
  updateScenario: (configId: number, scenarioId: number, data: any) =>
    request<any>(`/agent/configs/${configId}/scenarios/${scenarioId}`, { method: "PUT", body: JSON.stringify(data) }),
  deleteScenario: (configId: number, scenarioId: number) =>
    request<any>(`/agent/configs/${configId}/scenarios/${scenarioId}`, { method: "DELETE" }),
  generateScenarios: (configId: number, data: { scenario_type: string; count?: number }) =>
    request<any[]>(`/agent/configs/${configId}/scenarios/generate`, { method: "POST", body: JSON.stringify(data) }),

  // Personas
  listPersonas: (configId: number, groupName?: string) =>
    request<any[]>(`/agent/configs/${configId}/personas${groupName ? `?group_name=${groupName}` : ""}`),
  createPersona: (configId: number, data: any) =>
    request<any>(`/agent/configs/${configId}/personas`, { method: "POST", body: JSON.stringify(data) }),
  createPersonasBulk: (configId: number, data: any[]) =>
    request<any[]>(`/agent/configs/${configId}/personas/bulk`, { method: "POST", body: JSON.stringify(data) }),
  updatePersona: (configId: number, personaId: number, data: any) =>
    request<any>(`/agent/configs/${configId}/personas/${personaId}`, { method: "PUT", body: JSON.stringify(data) }),
  deletePersona: (configId: number, personaId: number) =>
    request<any>(`/agent/configs/${configId}/personas/${personaId}`, { method: "DELETE" }),
  generatePersonas: (configId: number, data: { audience_description: string; count?: number; interaction_count?: number }) =>
    request<any[]>(`/agent/configs/${configId}/personas/generate`, { method: "POST", body: JSON.stringify(data) }),
  getPersonaTemplates: (configId: number) =>
    request<any[]>(`/agent/configs/${configId}/personas/templates`),

  // Interaction Datasets
  listInteractionDatasets: () => request<any[]>("/agent/datasets"),
  createInteractionDataset: (data: any) =>
    request<any>("/agent/datasets", { method: "POST", body: JSON.stringify(data) }),
  getInteractionDataset: (id: number) => request<any>(`/agent/datasets/${id}`),
  deleteInteractionDataset: (id: number) =>
    request<any>(`/agent/datasets/${id}`, { method: "DELETE" }),
  duplicateInteractionDataset: (id: number) =>
    request<any>(`/agent/datasets/${id}/duplicate`, { method: "POST" }),
  listInteractionDatasetItems: (id: number) =>
    request<any[]>(`/agent/datasets/${id}/items`),
  addInteractionDatasetItem: (id: number, data: any) =>
    request<any>(`/agent/datasets/${id}/items`, { method: "POST", body: JSON.stringify(data) }),
  deleteInteractionDatasetItem: (datasetId: number, itemId: number) =>
    request<any>(`/agent/datasets/${datasetId}/items/${itemId}`, { method: "DELETE" }),
  generateInteractionDataset: (data: any) =>
    request<any>("/agent/datasets/generate", { method: "POST", body: JSON.stringify(data) }),
  exportInteractionDataset: (id: number) => request<any>(`/agent/datasets/${id}/export`),
  importInteractionDatasetItems: (id: number, items: any[]) =>
    request<any>(`/agent/datasets/${id}/import`, { method: "POST", body: JSON.stringify(items) }),

  // Agent Experiments
  listAgentExperiments: () => request<any[]>("/agent/experiments"),
  createAgentExperiment: (data: any) =>
    request<any>("/agent/experiments", { method: "POST", body: JSON.stringify(data) }),
  getAgentExperiment: (id: number) => request<any>(`/agent/experiments/${id}`),
  deleteAgentExperiment: (id: number) =>
    request<any>(`/agent/experiments/${id}`, { method: "DELETE" }),
  bulkDeleteAgentExperiments: (ids: number[]) =>
    request<any>("/agent/experiments/bulk-delete", {
      method: "POST",
      body: JSON.stringify({ ids }),
    }),
  getAgentExperimentCombinations: (id: number) =>
    request<any[]>(`/agent/experiments/${id}/combinations`),
  runAgentExperiment: (id: number) =>
    request<any>(`/agent/experiments/${id}/run`, { method: "POST" }),
  stopAgentExperiment: (id: number) =>
    request<any>(`/agent/experiments/${id}/stop`, { method: "POST" }),
  resumeAgentExperiment: (id: number, retryFailed: boolean = false) =>
    request<any>(`/agent/experiments/${id}/resume?retry_failed=${retryFailed}`, { method: "POST" }),
  getAgentExperimentStatus: (id: number) =>
    request<any>(`/agent/experiments/${id}/status`),
  getAgentExperimentResults: (id: number) =>
    request<any>(`/agent/experiments/${id}/results`),
  evaluateAgentExperiment: (id: number) =>
    request<any>(`/agent/experiments/${id}/evaluate`, { method: "POST" }),
  generateAgentReport: (id: number) =>
    request<any>(`/agent/experiments/${id}/report/generate`, { method: "POST" }),
  getAgentReport: (id: number) =>
    request<any>(`/agent/experiments/${id}/report`),

  // Transcripts
  listTranscripts: (expId: number, combinationId?: number) =>
    request<any[]>(`/agent/experiments/${expId}/transcripts${combinationId ? `?combination_id=${combinationId}` : ""}`),
  getTranscript: (id: number) => request<any>(`/agent/transcripts/${id}`),
  getTranscriptMetrics: (id: number) => request<any>(`/agent/transcripts/${id}/metrics`),
};
