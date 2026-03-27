"use client";

import { useState, useEffect } from "react";
import { Database, Loader2, CheckCircle, AlertCircle, List, Plus, FileText } from "lucide-react";
import { api } from "@/lib/api";

interface StepDatasetProps {
  documentIds: number[];
  onComplete: (datasetId: number, reused?: boolean) => void;
}

export default function StepDataset({ documentIds, onComplete }: StepDatasetProps) {
  const [mode, setMode] = useState<"new" | "existing">("new");
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [generating, setGenerating] = useState(false);
  const [progress, setProgress] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Existing datasets state
  const [existingDatasets, setExistingDatasets] = useState<any[]>([]);
  const [loadingDatasets, setLoadingDatasets] = useState(false);
  const [selectedDatasetId, setSelectedDatasetId] = useState<number | null>(null);

  useEffect(() => {
    if (mode === "existing") {
      loadExistingDatasets();
    }
  }, [mode]);

  const loadExistingDatasets = async () => {
    setLoadingDatasets(true);
    try {
      const datasets = await api.listDatasets();
      // Only show datasets that are ready to use
      const usable = datasets.filter(
        (d: any) => d.status === "generated" || d.status === "approved"
      );
      setExistingDatasets(usable);
    } catch (err) {
      console.error("Failed to load datasets:", err);
    } finally {
      setLoadingDatasets(false);
    }
  };

  const pollForCompletion = async (datasetId: number): Promise<{ success: boolean; errorMessage?: string }> => {
    const maxAttempts = 120;
    for (let i = 0; i < maxAttempts; i++) {
      await new Promise((r) => setTimeout(r, 2000));
      try {
        const dataset = await api.getDataset(datasetId);
        if (dataset.status === "generated") {
          const itemCount = dataset.items?.length ?? 0;
          setProgress(`Generated ${itemCount} Q&A pairs successfully!`);
          return { success: true };
        }
        if (dataset.status === "error") {
          return {
            success: false,
            errorMessage: dataset.error_message || "Generation failed. Check your LLM provider configuration.",
          };
        }
        if (dataset.status === "draft") {
          return { success: false, errorMessage: "Generation failed unexpectedly." };
        }
        setProgress(`Generating Q&A pairs from your documents...`);
      } catch {
        // Network error, keep polling
      }
    }
    return { success: false, errorMessage: "Generation timed out. Please try again." };
  };

  const handleCreate = async () => {
    setError(null);
    setGenerating(true);
    setProgress("Creating dataset...");

    try {
      const dataset = await api.createDataset({
        name: name.trim() || undefined,
        description: description.trim() || undefined,
        document_ids: documentIds,
      });

      setProgress("Starting Q&A generation with LLM...");
      await api.generateDataset(dataset.id);

      setProgress("Generating Q&A pairs from your documents...");
      const result = await pollForCompletion(dataset.id);

      if (result.success) {
        setTimeout(() => onComplete(dataset.id), 1000);
      } else {
        setError(result.errorMessage || "Dataset generation failed.");
        setGenerating(false);
        setProgress(null);
        onComplete(dataset.id);
      }
    } catch (err: any) {
      setError(err.message);
      setGenerating(false);
      setProgress(null);
    }
  };

  const handleSelectExisting = () => {
    if (selectedDatasetId) {
      onComplete(selectedDatasetId, true);
    }
  };

  return (
    <div className="space-y-6">
      {/* Mode toggle */}
      <div className="flex gap-2 p-1 bg-surface-50 rounded-xl border border-surface-200/50 w-fit">
        <button
          onClick={() => setMode("new")}
          className={`px-4 py-2 text-sm font-medium rounded-lg flex items-center gap-2 transition-colors ${
            mode === "new"
              ? "bg-accent/10 text-accent border border-accent/20"
              : "text-t-secondary hover:text-t-hover"
          }`}
        >
          <Plus className="w-4 h-4" />
          Create New
        </button>
        <button
          onClick={() => setMode("existing")}
          className={`px-4 py-2 text-sm font-medium rounded-lg flex items-center gap-2 transition-colors ${
            mode === "existing"
              ? "bg-accent/10 text-accent border border-accent/20"
              : "text-t-secondary hover:text-t-hover"
          }`}
        >
          <List className="w-4 h-4" />
          Use Existing
        </button>
      </div>

      {mode === "new" ? (
        /* Create new dataset */
        <div className="bg-surface-100 rounded-2xl border border-surface-200/50 p-8">
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-t-hover mb-2">
                Dataset Name <span className="text-muted font-normal">(optional)</span>
              </label>
              <input
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="e.g., Product Documentation QA"
                disabled={generating}
                className="w-full px-4 py-3 bg-surface-50 border border-surface-200/50 rounded-xl text-primary placeholder-muted focus:outline-none focus:border-accent/50 focus:ring-1 focus:ring-accent/25 disabled:opacity-50"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-t-hover mb-2">
                Description (optional)
              </label>
              <textarea
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="Describe the purpose of this evaluation dataset..."
                rows={3}
                disabled={generating}
                className="w-full px-4 py-3 bg-surface-50 border border-surface-200/50 rounded-xl text-primary placeholder-muted focus:outline-none focus:border-accent/50 focus:ring-1 focus:ring-accent/25 resize-none disabled:opacity-50"
              />
            </div>

            <div className="bg-surface-50 rounded-xl p-4 border border-surface-200/50">
              <p className="text-sm text-t-secondary">
                <span className="text-primary font-medium">{documentIds.length}</span> document(s) selected for analysis
              </p>
            </div>

            {progress && (
              <div className="flex items-center gap-3 p-4 bg-accent/5 border border-accent/20 rounded-xl">
                {generating ? (
                  <Loader2 className="w-5 h-5 text-accent animate-spin flex-shrink-0" />
                ) : (
                  <CheckCircle className="w-5 h-5 text-emerald-400 flex-shrink-0" />
                )}
                <p className="text-sm text-t-hover">{progress}</p>
              </div>
            )}

            {error && (
              <div className="flex items-start gap-3 p-4 bg-red-500/5 border border-red-500/20 rounded-xl">
                <AlertCircle className="w-5 h-5 text-red-400 flex-shrink-0 mt-0.5" />
                <p className="text-sm text-red-400">{error}</p>
              </div>
            )}

            <button
              onClick={handleCreate}
              disabled={generating}
              className="w-full py-3 px-6 bg-gradient-to-r from-accent to-accent-dark text-primary font-medium rounded-xl hover:opacity-90 transition-opacity disabled:opacity-50 flex items-center justify-center gap-2"
            >
              {generating ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  Generating Dataset...
                </>
              ) : (
                <>
                  <Database className="w-4 h-4" />
                  Generate Evaluation Dataset
                </>
              )}
            </button>
          </div>
        </div>
      ) : (
        /* Use existing dataset */
        <div className="bg-surface-100 rounded-2xl border border-surface-200/50 p-8">
          <div className="space-y-4">
            {loadingDatasets ? (
              <div className="flex items-center justify-center py-12 text-t-secondary">
                <Loader2 className="w-5 h-5 animate-spin mr-2" />
                Loading datasets...
              </div>
            ) : existingDatasets.length === 0 ? (
              <div className="text-center py-12">
                <Database className="w-10 h-10 text-muted mx-auto mb-3" />
                <p className="text-t-secondary text-sm">No existing datasets found.</p>
                <p className="text-muted text-xs mt-1">Create a new dataset first.</p>
              </div>
            ) : (
              <>
                <p className="text-sm text-t-secondary mb-2">
                  Select a previously generated dataset to reuse:
                </p>
                <div className="space-y-2 max-h-80 overflow-y-auto">
                  {existingDatasets.map((ds: any) => (
                    <button
                      key={ds.id}
                      onClick={() => setSelectedDatasetId(ds.id)}
                      className={`w-full text-left px-4 py-4 rounded-xl border transition-colors ${
                        selectedDatasetId === ds.id
                          ? "bg-accent/5 border-accent/30"
                          : "bg-surface-50 border-surface-200/50 hover:border-surface-200"
                      }`}
                    >
                      <div className="flex items-start justify-between">
                        <div className="min-w-0 flex-1">
                          <div className="flex items-center gap-2">
                            <FileText className="w-4 h-4 text-accent flex-shrink-0" />
                            <span className="text-sm font-medium text-primary truncate">
                              {ds.name}
                            </span>
                          </div>
                          {ds.description && (
                            <p className="text-xs text-muted mt-1 ml-6 line-clamp-1">
                              {ds.description}
                            </p>
                          )}
                          <div className="flex items-center gap-3 mt-2 ml-6 text-xs text-t-secondary">
                            <span>{ds.items?.length ?? 0} Q&A pairs</span>
                            <span>{ds.document_ids?.length ?? 0} document(s)</span>
                            <span>{new Date(ds.created_at).toLocaleDateString()}</span>
                          </div>
                        </div>
                        <span
                          className={`text-xs px-2 py-0.5 rounded-full flex-shrink-0 ${
                            ds.status === "approved"
                              ? "bg-emerald-500/10 text-emerald-400"
                              : "bg-accent/10 text-accent"
                          }`}
                        >
                          {ds.status}
                        </span>
                      </div>
                    </button>
                  ))}
                </div>

                <button
                  onClick={handleSelectExisting}
                  disabled={!selectedDatasetId}
                  className="w-full py-3 px-6 bg-gradient-to-r from-accent to-accent-dark text-primary font-medium rounded-xl hover:opacity-90 transition-opacity disabled:opacity-50 flex items-center justify-center gap-2"
                >
                  <CheckCircle className="w-4 h-4" />
                  Use Selected Dataset
                </button>
              </>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
