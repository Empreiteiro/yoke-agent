const API_BASE = "/api";
const API_KEY_STORAGE_KEY = "rag-api-key";

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

function authHeaders(): Record<string, string> {
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

  // MCP
  listMcpTools: () => request<any>("/mcp/tools"),
  updateMcpTools: (disabledTools: string[]) =>
    request<any>("/mcp/tools", {
      method: "PUT",
      body: JSON.stringify({ disabled_tools: disabledTools }),
    }),
  getMcpConnectionInfo: () => request<any>("/mcp/connection-info"),
};
