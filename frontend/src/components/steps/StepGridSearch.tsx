"use client";

import { useState, useEffect } from "react";
import { Grid3X3, Plus, X, Loader2, AlertCircle } from "lucide-react";
import { api } from "@/lib/api";

interface StepGridSearchProps {
  datasetId: number | null;
  onComplete: (experimentId: number) => void;
}

const DEFAULT_CONFIG = {
  chunk_sizes: [512, 1024],
  chunk_overlaps: [10, 20],
  embedding_models: ["text-embedding-3-small"],
  top_k_values: [3, 5],
  search_types: ["vector"],
  optional_metrics: [] as string[],
};

const AVAILABLE_METRICS = [
  { id: "answer_similarity", label: "Answer Similarity", description: "Semantic similarity between generated and ground truth answers" },
  { id: "answer_correctness", label: "Answer Correctness", description: "Factual correctness of the generated answer" },
];

export default function StepGridSearch({ datasetId, onComplete }: StepGridSearchProps) {
  const [config, setConfig] = useState(DEFAULT_CONFIG);
  const [experimentName, setExperimentName] = useState("");
  const [vectorStoreType, setVectorStoreType] = useState("chromadb");
  const [loading, setLoading] = useState(false);
  const [newChunkSize, setNewChunkSize] = useState("");
  const [newTopK, setNewTopK] = useState("");
  const [availableEmbeddings, setAvailableEmbeddings] = useState<Array<{provider_name: string; model: string}>>([]);
  const [noProviders, setNoProviders] = useState(false);

  useEffect(() => {
    api.getAvailableModels().then((data) => {
      if (data.embedding_models && data.embedding_models.length > 0) {
        setAvailableEmbeddings(data.embedding_models);
        setNoProviders(false);
      } else {
        setAvailableEmbeddings([]);
        setNoProviders(true);
      }
    }).catch(() => {
      setNoProviders(true);
    });
  }, []);

  const totalCombinations =
    config.chunk_sizes.length *
    config.chunk_overlaps.length *
    config.embedding_models.length *
    config.top_k_values.length *
    config.search_types.length;

  const addToArray = (
    field: keyof typeof config,
    value: string | number
  ) => {
    setConfig((prev) => ({
      ...prev,
      [field]: [...(prev[field] as any[]), value],
    }));
  };

  const removeFromArray = (
    field: keyof typeof config,
    index: number
  ) => {
    setConfig((prev) => ({
      ...prev,
      [field]: (prev[field] as any[]).filter((_: any, i: number) => i !== index),
    }));
  };

  const toggleMetric = (metricId: string) => {
    setConfig((prev) => ({
      ...prev,
      optional_metrics: prev.optional_metrics.includes(metricId)
        ? prev.optional_metrics.filter((m) => m !== metricId)
        : [...prev.optional_metrics, metricId],
    }));
  };

  const handleSubmit = async () => {
    if (!datasetId) return;
    setLoading(true);

    try {
      const exp = await api.createExperiment({
        name: experimentName.trim() || undefined,
        dataset_id: datasetId,
        vectorstore_type: vectorStoreType,
      });
      await api.configureGrid(exp.id, config);
      onComplete(exp.id);
    } catch (err) {
      console.error("Failed to configure grid search:", err);
    } finally {
      setLoading(false);
    }
  };

  const renderChips = (
    field: keyof typeof config,
    items: (string | number)[],
    color: string = "accent"
  ) => (
    <div className="flex flex-wrap gap-2">
      {items.map((item, index) => (
        <span
          key={index}
          className={`inline-flex items-center gap-1.5 px-3 py-1.5 bg-${color}/10 text-${color === "accent" ? "accent" : "secondary"} text-sm rounded-lg border border-${color}/20`}
        >
          {item}
          <button
            onClick={() => removeFromArray(field, index)}
            className="hover:text-red-400 transition-colors"
          >
            <X className="w-3 h-3" />
          </button>
        </span>
      ))}
    </div>
  );

  return (
    <div className="space-y-6">
      {/* Experiment name */}
      <div className="bg-surface-100 rounded-2xl border border-surface-200/50 p-8">
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium text-t-hover mb-2">Experiment Name <span className="text-muted font-normal">(optional)</span></label>
            <input
              type="text"
              value={experimentName}
              onChange={(e) => setExperimentName(e.target.value)}
              placeholder="e.g., Documentation RAG v1"
              className="w-full px-4 py-3 bg-surface-50 border border-surface-200/50 rounded-xl text-primary placeholder-muted focus:outline-none focus:border-accent/50"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-t-hover mb-2">Vector Store</label>
            <select
              value={vectorStoreType}
              onChange={(e) => setVectorStoreType(e.target.value)}
              className="w-full px-4 py-3 bg-surface-50 border border-surface-200/50 rounded-xl text-primary focus:outline-none focus:border-accent/50"
            >
              <option value="chromadb">ChromaDB (Default)</option>
              <option value="pinecone">Pinecone</option>
              <option value="weaviate">Weaviate</option>
              <option value="qdrant">Qdrant</option>
              <option value="pgvector">PGVector</option>
            </select>
          </div>
        </div>
      </div>

      {/* Hyperparameters */}
      <div className="bg-surface-100 rounded-2xl border border-surface-200/50 p-8">
        <div className="flex items-center gap-3 mb-6">
          <div className="w-10 h-10 rounded-xl bg-secondary/10 flex items-center justify-center">
            <Grid3X3 className="w-5 h-5 text-secondary" />
          </div>
          <div>
            <h3 className="text-lg font-semibold text-primary">RAG Hyperparameters</h3>
            <p className="text-sm text-t-secondary">
              Configure the grid search space. Total combinations:{" "}
              <span className="text-primary font-semibold">{totalCombinations}</span>
            </p>
          </div>
        </div>

        <div className="space-y-6">
          {/* Chunk sizes */}
          <div>
            <label className="block text-sm font-medium text-t-hover mb-3">Chunk Size (tokens)</label>
            {renderChips("chunk_sizes", config.chunk_sizes)}
            <div className="flex gap-2 mt-2">
              <input
                type="number"
                value={newChunkSize}
                onChange={(e) => setNewChunkSize(e.target.value)}
                placeholder="Add size..."
                className="px-3 py-2 bg-surface-50 border border-surface-200/50 rounded-lg text-primary text-sm w-32 focus:outline-none focus:border-accent/50"
              />
              <button
                onClick={() => {
                  if (newChunkSize) {
                    addToArray("chunk_sizes", parseInt(newChunkSize));
                    setNewChunkSize("");
                  }
                }}
                className="p-2 bg-surface-200 rounded-lg hover:bg-surface-300 transition-colors"
              >
                <Plus className="w-4 h-4 text-t-hover" />
              </button>
            </div>
          </div>

          {/* Chunk overlap */}
          <div>
            <label className="block text-sm font-medium text-t-hover mb-3">Chunk Overlap (%)</label>
            {renderChips("chunk_overlaps", config.chunk_overlaps)}
            <div className="flex gap-2 mt-2">
              {[5, 10, 15, 20, 25, 30].map((val) => (
                <button
                  key={val}
                  onClick={() => {
                    if (!config.chunk_overlaps.includes(val)) addToArray("chunk_overlaps", val);
                  }}
                  disabled={config.chunk_overlaps.includes(val)}
                  className="px-3 py-1.5 bg-surface-200 text-t-hover text-xs rounded-lg hover:bg-surface-300 disabled:opacity-30 transition-colors"
                >
                  {val}%
                </button>
              ))}
            </div>
          </div>

          {/* Embedding models */}
          <div>
            <label className="block text-sm font-medium text-t-hover mb-3">Embedding Models</label>
            {noProviders && (
              <div className="flex items-center gap-2 mb-3 px-3 py-2 bg-amber-500/10 border border-amber-500/20 rounded-lg text-amber-400 text-xs">
                <AlertCircle className="w-3.5 h-3.5 shrink-0" />
                No providers configured. Go to Settings → Providers to add one.
              </div>
            )}
            {renderChips("embedding_models", config.embedding_models, "secondary")}
            <div className="flex flex-wrap gap-2 mt-2">
              {availableEmbeddings
                .filter((em) => !config.embedding_models.includes(em.model))
                .map((em) => (
                  <button
                    key={`${em.provider_name}-${em.model}`}
                    onClick={() => addToArray("embedding_models", em.model)}
                    className="px-3 py-1.5 bg-surface-200 text-t-hover text-xs rounded-lg hover:bg-surface-300 transition-colors"
                    title={`Provider: ${em.provider_name}`}
                  >
                    + {em.model}
                    <span className="ml-1 text-muted">({em.provider_name})</span>
                  </button>
                ))}
            </div>
          </div>

          {/* Top-K */}
          <div>
            <label className="block text-sm font-medium text-t-hover mb-3">Top-K (retrieved docs)</label>
            {renderChips("top_k_values", config.top_k_values)}
            <div className="flex gap-2 mt-2">
              <input
                type="number"
                value={newTopK}
                onChange={(e) => setNewTopK(e.target.value)}
                placeholder="Add value..."
                className="px-3 py-2 bg-surface-50 border border-surface-200/50 rounded-lg text-primary text-sm w-32 focus:outline-none focus:border-accent/50"
              />
              <button
                onClick={() => {
                  if (newTopK) {
                    addToArray("top_k_values", parseInt(newTopK));
                    setNewTopK("");
                  }
                }}
                className="p-2 bg-surface-200 rounded-lg hover:bg-surface-300 transition-colors"
              >
                <Plus className="w-4 h-4 text-t-hover" />
              </button>
            </div>
          </div>

          {/* Search type */}
          <div>
            <label className="block text-sm font-medium text-t-hover mb-3">Search Type</label>
            <div className="flex gap-3">
              {["vector", "hybrid", "mmr"].map((type) => (
                <label
                  key={type}
                  className="flex items-center gap-2 cursor-pointer"
                >
                  <input
                    type="checkbox"
                    checked={config.search_types.includes(type)}
                    onChange={() => {
                      if (config.search_types.includes(type)) {
                        setConfig((prev) => ({
                          ...prev,
                          search_types: prev.search_types.filter((t) => t !== type),
                        }));
                      } else {
                        addToArray("search_types", type);
                      }
                    }}
                    className="rounded border-surface-300 bg-surface-50 text-accent focus:ring-accent/25"
                  />
                  <span className="text-sm text-t-hover capitalize">{type}</span>
                </label>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* RAGAS Metrics */}
      <div className="bg-surface-100 rounded-2xl border border-surface-200/50 p-8">
        <h3 className="text-lg font-semibold text-primary mb-2">Evaluation Metrics (RAGAS)</h3>
        <p className="text-sm text-t-secondary mb-6">
          Core metrics are always included. Select additional optional metrics.
        </p>

        <div className="grid grid-cols-2 gap-4 mb-4">
          {[
            { id: "faithfulness", label: "Faithfulness", desc: "Factual consistency with context", fixed: true },
            { id: "answer_relevancy", label: "Answer Relevancy", desc: "Relevance of answer to question", fixed: true },
            { id: "context_precision", label: "Context Precision", desc: "Signal-to-noise in retrieved context", fixed: true },
            { id: "context_recall", label: "Context Recall", desc: "Coverage of ground truth by context", fixed: true },
          ].map((metric) => (
            <div
              key={metric.id}
              className="p-4 bg-surface-50 rounded-xl border border-emerald-500/20"
            >
              <div className="flex items-center gap-2 mb-1">
                <div className="w-2 h-2 rounded-full bg-emerald-500" />
                <span className="text-sm font-medium text-primary">{metric.label}</span>
                <span className="text-xs text-emerald-400 ml-auto">Required</span>
              </div>
              <p className="text-xs text-t-secondary">{metric.desc}</p>
            </div>
          ))}
        </div>

        <div className="grid grid-cols-2 gap-4">
          {AVAILABLE_METRICS.map((metric) => (
            <button
              key={metric.id}
              onClick={() => toggleMetric(metric.id)}
              className={`p-4 rounded-xl border text-left transition-all ${
                config.optional_metrics.includes(metric.id)
                  ? "bg-accent/5 border-accent/30"
                  : "bg-surface-50 border-surface-200/50 hover:border-surface-300"
              }`}
            >
              <div className="flex items-center gap-2 mb-1">
                <div
                  className={`w-2 h-2 rounded-full ${
                    config.optional_metrics.includes(metric.id) ? "bg-accent" : "bg-surface-300"
                  }`}
                />
                <span className="text-sm font-medium text-primary">{metric.label}</span>
                <span className="text-xs text-muted ml-auto">Optional</span>
              </div>
              <p className="text-xs text-t-secondary">{metric.description}</p>
            </button>
          ))}
        </div>
      </div>

      {/* Submit */}
      <div className="bg-surface-100 rounded-2xl border border-accent/20 p-6">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-primary font-medium">
              Ready to configure {totalCombinations} experiment combinations
            </p>
            <p className="text-sm text-t-secondary">
              {4 + config.optional_metrics.length} metrics will be evaluated per combination
            </p>
          </div>
          <button
            onClick={handleSubmit}
            disabled={loading || totalCombinations === 0}
            className="px-8 py-3 bg-gradient-to-r from-accent to-accent-dark text-primary font-medium rounded-xl hover:opacity-90 transition-opacity disabled:opacity-50 flex items-center gap-2"
          >
            {loading ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <Grid3X3 className="w-4 h-4" />
            )}
            Configure Grid Search
          </button>
        </div>
      </div>
    </div>
  );
}
