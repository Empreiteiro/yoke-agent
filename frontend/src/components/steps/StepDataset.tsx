"use client";

import { useState, useEffect } from "react";
import { Database, Loader2, CheckCircle, AlertCircle, List, Plus, FileText, Trash2, BookOpen, Shuffle, Copy, FlaskConical } from "lucide-react";
import { api } from "@/lib/api";
import { useWalkthrough } from "@/contexts/WalkthroughContext";

interface StepDatasetProps {
  documentIds: number[];
  onComplete: (datasetId: number, reused?: boolean) => void;
}

export default function StepDataset({ documentIds, onComplete }: StepDatasetProps) {
  const { startIfNew } = useWalkthrough();
  useEffect(() => { startIfNew("dataset"); }, []); // eslint-disable-line react-hooks/exhaustive-deps
  const [mode, setMode] = useState<"new" | "existing">("new");
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [generating, setGenerating] = useState(false);
  const [progress, setProgress] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Generation options
  const [readingMode, setReadingMode] = useState<"full" | "partial">("full");
  const [maxPages, setMaxPages] = useState(20);
  const [numQuestions, setNumQuestions] = useState<number | "">("");
  const [language, setLanguage] = useState("auto");
  const [selectedProviderId, setSelectedProviderId] = useState<string>("");
  const [selectedModel, setSelectedModel] = useState<string>("");
  const [availableLLMs, setAvailableLLMs] = useState<Array<{provider_id: number; provider_name: string; model: string}>>([]);

  // Existing datasets state
  const [existingDatasets, setExistingDatasets] = useState<any[]>([]);
  const [loadingDatasets, setLoadingDatasets] = useState(false);
  const [selectedDatasetId, setSelectedDatasetId] = useState<number | null>(null);

  useEffect(() => {
    if (mode === "existing") {
      loadExistingDatasets();
    }
  }, [mode]);

  useEffect(() => {
    api.getAvailableModels().then((data) => {
      if (data.llm_models) {
        setAvailableLLMs(data.llm_models);
      }
    }).catch(() => {});
  }, []);

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
      const genOptions: any = { reading_mode: readingMode, language };
      if (readingMode === "partial") {
        genOptions.max_pages = maxPages;
      }
      if (numQuestions && Number(numQuestions) > 0) {
        genOptions.num_questions = Number(numQuestions);
      }
      if (selectedProviderId) {
        genOptions.provider_id = Number(selectedProviderId);
      }
      if (selectedModel) {
        genOptions.model = selectedModel;
      }
      await api.generateDataset(dataset.id, genOptions);

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

  const handleDeleteDataset = async (datasetId: number) => {
    try {
      await api.deleteDataset(datasetId);
      setExistingDatasets((prev) => prev.filter((d) => d.id !== datasetId));
      if (selectedDatasetId === datasetId) {
        setSelectedDatasetId(null);
      }
    } catch (err) {
      console.error("Failed to delete dataset:", err);
    }
  };

  const handleDuplicateDataset = async (datasetId: number) => {
    try {
      const newDataset = await api.duplicateDataset(datasetId);
      setExistingDatasets((prev) => [newDataset, ...prev]);
    } catch (err) {
      console.error("Failed to duplicate dataset:", err);
    }
  };

  const handleSelectExisting = () => {
    if (selectedDatasetId) {
      onComplete(selectedDatasetId, true);
    }
  };

  const handleUseBenchmark = async (datasetId: number) => {
    try {
      const copy = await api.duplicateDataset(datasetId);
      onComplete(copy.id, true);
    } catch (err) {
      console.error("Failed to clone benchmark:", err);
    }
  };

  const modeToggle = (
    <div className="flex gap-2 p-1 bg-surface-50 rounded-xl border border-themed w-fit" data-walkthrough="dataset-mode-toggle">
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
  );

  return (
    <div className="space-y-6">
      {mode === "new" ? (
        /* Create new dataset */
        <>
        <div className="bg-surface-100 rounded-2xl border border-themed p-8">
          <div className="space-y-4">
            {modeToggle}
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
                className="w-full px-4 py-3 bg-surface-50 border border-themed rounded-xl text-primary placeholder-muted focus:outline-none focus:border-accent/50 focus:ring-1 focus:ring-accent/25 disabled:opacity-50"
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
                className="w-full px-4 py-3 bg-surface-50 border border-themed rounded-xl text-primary placeholder-muted focus:outline-none focus:border-accent/50 focus:ring-1 focus:ring-accent/25 resize-none disabled:opacity-50"
              />
            </div>

            <div className="bg-surface-50 rounded-xl p-4 border border-themed">
              <p className="text-sm text-t-secondary">
                <span className="text-primary font-medium">{documentIds.length}</span> document(s) selected for analysis
              </p>
            </div>

            {/* Reading Mode */}
            <div className="bg-surface-50 rounded-xl p-5 border border-themed space-y-4" data-walkthrough="dataset-options">
              <div>
                <label className="block text-sm font-medium text-t-hover mb-3">
                  <BookOpen className="w-4 h-4 inline mr-1.5 -mt-0.5" />
                  Document Reading Mode
                </label>
                <div className="flex gap-3">
                  <label className="flex items-center gap-2 cursor-pointer">
                    <input
                      type="radio"
                      checked={readingMode === "full"}
                      onChange={() => setReadingMode("full")}
                      disabled={generating}
                      className="text-accent focus:ring-accent/25"
                    />
                    <span className="text-sm text-t-hover">Full reading</span>
                    <span className="text-xs text-muted">(all pages, more questions, higher cost)</span>
                  </label>
                  <label className="flex items-center gap-2 cursor-pointer">
                    <input
                      type="radio"
                      checked={readingMode === "partial"}
                      onChange={() => setReadingMode("partial")}
                      disabled={generating}
                      className="text-accent focus:ring-accent/25"
                    />
                    <span className="text-sm text-t-hover">Partial reading</span>
                    <span className="text-xs text-muted">
                      <Shuffle className="w-3 h-3 inline mr-0.5 -mt-0.5" />
                      random pages, lower cost
                    </span>
                  </label>
                </div>
              </div>

              {readingMode === "partial" && (
                <div>
                  <label className="block text-xs font-medium text-t-hover mb-1.5">
                    Max pages to read (random selection)
                  </label>
                  <input
                    type="number"
                    value={maxPages}
                    onChange={(e) => setMaxPages(Math.max(1, parseInt(e.target.value) || 1))}
                    min={1}
                    disabled={generating}
                    className="px-3 py-2 bg-surface border border-themed rounded-lg text-primary text-sm w-32 focus:outline-none focus:border-accent/50 disabled:opacity-50"
                  />
                </div>
              )}

              <div>
                <label className="block text-xs font-medium text-t-hover mb-1.5">
                  Number of questions <span className="text-muted font-normal">(empty = auto-calculate based on content size)</span>
                </label>
                <input
                  type="number"
                  value={numQuestions}
                  onChange={(e) => setNumQuestions(e.target.value === "" ? "" : Math.max(1, parseInt(e.target.value) || 1))}
                  placeholder="Auto"
                  min={1}
                  disabled={generating}
                  className="px-3 py-2 bg-surface border border-themed rounded-lg text-primary text-sm w-32 placeholder-muted focus:outline-none focus:border-accent/50 disabled:opacity-50"
                />
              </div>

              {/* LLM Provider & Model */}
              <div data-walkthrough="dataset-llm">
                <label className="block text-xs font-medium text-t-hover mb-1.5">
                  LLM for Generation
                  <span className="text-muted font-normal ml-1">(empty = first active provider)</span>
                </label>
                <div className="flex gap-2">
                  <select
                    value={selectedModel}
                    onChange={(e) => {
                      const val = e.target.value;
                      setSelectedModel(val);
                      const match = availableLLMs.find((m) => m.model === val);
                      if (match) setSelectedProviderId(String(match.provider_id));
                    }}
                    disabled={generating}
                    className="flex-1 px-3 py-2 bg-surface border border-themed rounded-lg text-primary text-sm focus:outline-none focus:border-accent/50 disabled:opacity-50"
                  >
                    <option value="">Auto (first active provider)</option>
                    {availableLLMs.map((lm) => (
                      <option key={`${lm.provider_id}-${lm.model}`} value={lm.model}>
                        {lm.model} ({lm.provider_name})
                      </option>
                    ))}
                  </select>
                </div>
              </div>

              <div>
                <label className="block text-xs font-medium text-t-hover mb-1.5">
                  Language
                </label>
                <select
                  value={language}
                  onChange={(e) => setLanguage(e.target.value)}
                  disabled={generating}
                  className="px-3 py-2 bg-surface border border-themed rounded-lg text-primary text-sm focus:outline-none focus:border-accent/50 disabled:opacity-50"
                >
                  <option value="auto">Auto (same as document)</option>
                  <option value="English">English</option>
                  <option value="Portuguese">Portuguese</option>
                  <option value="Spanish">Spanish</option>
                  <option value="French">French</option>
                  <option value="German">German</option>
                  <option value="Italian">Italian</option>
                  <option value="Chinese">Chinese</option>
                  <option value="Japanese">Japanese</option>
                </select>
              </div>
            </div>

            {progress && (
              <div className="flex items-center gap-3 p-4 bg-accent/5 border border-accent/20 rounded-xl">
                {generating ? (
                  <Loader2 className="w-5 h-5 text-accent animate-spin flex-shrink-0" />
                ) : (
                  <CheckCircle className="w-5 h-5 text-success flex-shrink-0" />
                )}
                <p className="text-sm text-t-hover">{progress}</p>
              </div>
            )}

            {error && (
              <div className="flex items-start gap-3 p-4 bg-danger/5 border border-danger/20 rounded-xl">
                <AlertCircle className="w-5 h-5 text-danger flex-shrink-0 mt-0.5" />
                <p className="text-sm text-danger">{error}</p>
              </div>
            )}

          </div>
        </div>
        <button
          onClick={handleCreate}
          disabled={generating}
          className="w-full py-3 px-6 bg-accent shadow-resting text-accent-foreground font-medium rounded-xl hover:opacity-90 transition-opacity disabled:opacity-50 flex items-center justify-center gap-2"
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
        </>
      ) : (
        /* Use existing dataset */
        <>
        <div className="bg-surface-100 rounded-2xl border border-themed p-8">
          <div className="space-y-4">
            {modeToggle}
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
                {/* Benchmark Datasets */}
                {existingDatasets.some((ds: any) => ds.is_benchmark === 1) && (
                  <div data-walkthrough="dataset-benchmarks">
                    <div className="flex items-center gap-2 mb-3">
                      <FlaskConical className="w-4 h-4 text-purple-400" />
                      <h3 className="text-sm font-semibold text-primary">Benchmark Datasets</h3>
                      <span className="text-[10px] text-muted">No documents needed</span>
                    </div>
                    <div className="space-y-2 mb-6">
                      {existingDatasets.filter((ds: any) => ds.is_benchmark === 1).map((ds: any) => (
                        <div
                          key={ds.id}
                          className="w-full text-left px-4 py-4 rounded-xl border bg-surface-50 border-themed hover:border-purple-400/40 transition-colors"
                        >
                          <div className="flex items-start justify-between">
                            <div className="min-w-0 flex-1">
                              <div className="flex items-center gap-2">
                                <FlaskConical className="w-4 h-4 text-purple-400 flex-shrink-0" />
                                <span className="text-sm font-medium text-primary truncate">{ds.name}</span>
                                <span className="text-[10px] px-2 py-0.5 rounded-full bg-purple-500/10 text-purple-400">Benchmark</span>
                              </div>
                              {ds.description && (
                                <p className="text-xs text-muted mt-1 ml-6 line-clamp-2">{ds.description}</p>
                              )}
                              <div className="flex items-center gap-3 mt-2 ml-6 text-xs text-t-secondary">
                                <span>{ds.items?.length ?? 0} Q&A pairs</span>
                              </div>
                            </div>
                            <button
                              onClick={() => handleUseBenchmark(ds.id)}
                              className="px-4 py-2 bg-purple-500/10 text-purple-400 text-xs font-medium rounded-lg hover:bg-purple-500/20 transition-colors flex-shrink-0"
                            >
                              Use Benchmark
                            </button>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* User Datasets */}
                {existingDatasets.some((ds: any) => ds.is_benchmark !== 1) && (
                  <>
                    <p className="text-sm text-t-secondary mb-2">
                      Select a previously generated dataset to reuse:
                    </p>
                    <div className="space-y-2">
                      {existingDatasets.filter((ds: any) => ds.is_benchmark !== 1).map((ds: any) => (
                        <div
                          key={ds.id}
                          onClick={() => setSelectedDatasetId(ds.id)}
                          className={`w-full text-left px-4 py-4 rounded-xl border transition-colors cursor-pointer ${
                            selectedDatasetId === ds.id
                              ? "bg-accent/10 border-accent ring-1 ring-accent/30"
                              : "bg-surface-50 border-themed hover:border-themed"
                          }`}
                        >
                          <div className="flex items-start justify-between">
                            <div className="min-w-0 flex-1">
                              <div className="flex items-center gap-2">
                                <FileText className="w-4 h-4 text-accent flex-shrink-0" />
                                <span className="text-sm font-medium text-primary truncate">{ds.name}</span>
                              </div>
                              {ds.description && (
                                <p className="text-xs text-muted mt-1 ml-6 line-clamp-1">{ds.description}</p>
                              )}
                              <div className="flex items-center gap-3 mt-2 ml-6 text-xs text-t-secondary">
                                <span>{ds.items?.length ?? 0} Q&A pairs</span>
                                <span>{ds.document_ids?.length ?? 0} document(s)</span>
                                <span>{new Date(ds.created_at).toLocaleDateString()}</span>
                              </div>
                            </div>
                            <div className="flex items-center gap-2 flex-shrink-0">
                              <span
                                className={`text-xs px-2 py-0.5 rounded-full ${
                                  ds.status === "approved"
                                    ? "bg-success/10 text-success"
                                    : "bg-accent/10 text-accent"
                                }`}
                              >
                                {ds.status}
                              </span>
                              <button
                                onClick={(e) => { e.stopPropagation(); handleDuplicateDataset(ds.id); }}
                                className="p-1.5 text-muted hover:text-accent hover:bg-accent/10 rounded-lg transition-colors"
                                title="Duplicate dataset"
                              >
                                <Copy className="w-4 h-4" />
                              </button>
                              <button
                                onClick={(e) => { e.stopPropagation(); handleDeleteDataset(ds.id); }}
                                className="p-1.5 text-muted hover:text-danger hover:bg-danger/10 rounded-lg transition-colors"
                                title="Delete dataset"
                              >
                                <Trash2 className="w-4 h-4" />
                              </button>
                            </div>
                          </div>
                        </div>
                      ))}
                    </div>
                  </>
                )}
              </>
            )}
          </div>
        </div>
        {selectedDatasetId && (
          <button
            onClick={handleSelectExisting}
            className="w-full py-3 px-6 bg-accent shadow-resting text-accent-foreground font-medium rounded-xl hover:opacity-90 transition-opacity disabled:opacity-50 flex items-center justify-center gap-2"
          >
            <CheckCircle className="w-4 h-4" />
            Use Selected Dataset
          </button>
        )}
        </>
      )}
    </div>
  );
}
