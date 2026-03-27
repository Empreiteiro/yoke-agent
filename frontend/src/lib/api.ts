const API_BASE = "/api";

async function request<T>(
  path: string,
  options?: RequestInit
): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: {
      "Content-Type": "application/json",
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
  generateDataset: (id: number) =>
    request<any>(`/datasets/${id}/generate`, { method: "POST" }),
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
      body: formData,
    });
    if (!res.ok) throw new Error("Import failed");
    return res.json();
  },
  approveDataset: (id: number) =>
    request<any>(`/datasets/${id}/approve`, { method: "POST" }),

  // Experiments
  createExperiment: (data: { name: string; description?: string; dataset_id: number; vectorstore_type?: string }) =>
    request<any>("/experiments/", { method: "POST", body: JSON.stringify(data) }),
  listExperiments: () => request<any[]>("/experiments/"),
  getExperiment: (id: number) => request<any>(`/experiments/${id}`),
  proposeGridSearch: (id: number) =>
    request<any>(`/experiments/${id}/propose-grid`, { method: "POST" }),
  configureGrid: (id: number, config: any) =>
    request<any>(`/experiments/${id}/configure-grid`, {
      method: "POST",
      body: JSON.stringify(config),
    }),
  runExperiment: (id: number) =>
    request<any>(`/experiments/${id}/run`, { method: "POST" }),
  getExperimentReport: (id: number) =>
    request<any>(`/experiments/${id}/report`),

  // Vector stores
  listVectorStores: () => request<any>("/vectorstores/"),
  validateVectorStore: (data: { type: string; config?: Record<string, string> }) =>
    request<any>("/vectorstores/validate", { method: "POST", body: JSON.stringify(data) }),

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
  getAvailableModels: () => request<any>("/providers/models/available"),
};
