"use client";

import { useState, useEffect, useRef } from "react";
import { Grid3X3, Plus, X, Loader2, AlertCircle, DollarSign } from "lucide-react";
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
  embedding_dimensions: [] as number[],
  distance_metrics: ["cosine"],
  chunking_strategies: ["recursive"],
  answer_language: "auto",
  optional_metrics: [] as string[],
  pipeline_types: ["rag"] as string[],
  entity_extraction_models: [] as string[],
  max_gleanings: [1] as number[],
  community_levels: [1] as number[],
  search_modes: ["local"] as string[],
  multi_query_counts: [3] as number[],
  agent_max_steps: [5] as number[],
  crag_relevance_thresholds: [0.7] as number[],
  crag_max_retries: [2] as number[],
  self_rag_retrieval_thresholds: [0.5] as number[],
  raptor_max_levels: [3] as number[],
  raptor_clustering: ["kmeans"] as string[],
  raptor_retrieval_modes: ["collapsed"] as string[],
  prompt_templates: [] as string[],
};

const SEARCH_TYPES = [
  { id: "vector", label: "Vector", description: "Semantic similarity search" },
  { id: "hybrid", label: "Hybrid", description: "Vector + keyword (BM25)" },
  { id: "mmr", label: "MMR", description: "Diverse results via Max Marginal Relevance" },
  { id: "hyde", label: "HyDE", description: "Embeds a hypothetical answer for better retrieval", cost: "amber" },
  { id: "multi_query", label: "Multi-Query", description: "LLM generates alternative queries, fuses via RRF", cost: "amber" },
  { id: "crag", label: "CRAG", description: "Corrective RAG — grades relevance, reformulates if needed", cost: "amber" },
  { id: "self_rag", label: "Self-RAG", description: "Decides if retrieval is needed, validates grounding", cost: "amber" },
  { id: "raptor", label: "RAPTOR", description: "Hierarchical summary tree for multi-level retrieval", cost: "red" },
  { id: "agentic", label: "Agentic", description: "LLM agent decides retrieval strategy dynamically", cost: "red" },
  { id: "cag", label: "CAG", description: "Full document in context — no retrieval (baseline)", cost: "red" },
];

const CHUNKING_STRATEGIES = [
  { id: "recursive", label: "Recursive Character", description: "Splits by paragraphs, lines, sentences" },
  { id: "token", label: "Token-based", description: "Exact token count per chunk" },
  { id: "semantic", label: "Semantic", description: "Groups by semantic similarity" },
];

const DISTANCE_METRICS = [
  { id: "cosine", label: "Cosine" },
  { id: "l2", label: "L2 (Euclidean)" },
  { id: "ip", label: "IP (Inner Product)" },
];

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
  const [availableLLMs, setAvailableLLMs] = useState<Array<{provider_name: string; model: string}>>([]);
  const [noProviders, setNoProviders] = useState(false);
  const [dimensionsMap, setDimensionsMap] = useState<Record<string, {default: number; supports_custom: boolean; supported: number[]}>>({});
  const [costEstimate, setCostEstimate] = useState<any>(null);
  const [tempExperimentId, setTempExperimentId] = useState<number | null>(null);

  useEffect(() => {
    api.getAvailableModels().then((data) => {
      if (data.embedding_models && data.embedding_models.length > 0) {
        setAvailableEmbeddings(data.embedding_models);
        setNoProviders(false);
      } else {
        setAvailableEmbeddings([]);
        setNoProviders(true);
      }
      if (data.llm_models && data.llm_models.length > 0) {
        setAvailableLLMs(data.llm_models);
      }
    }).catch(() => {
      setNoProviders(true);
    });
    api.getEmbeddingDimensions().then(setDimensionsMap).catch(() => {});
  }, []);

  // Calculate combinations accounting for per-model dimension expansion
  const dimensionMultiplier = (() => {
    if (config.embedding_dimensions.length === 0) return 1;
    // For each model, count how many selected dimensions are valid
    let totalModelDimCombos = 0;
    for (const model of config.embedding_models) {
      const info = dimensionsMap[model];
      if (!info) { totalModelDimCombos += 1; continue; }
      const validDims = config.embedding_dimensions.filter((d) => info.supported.includes(d));
      totalModelDimCombos += validDims.length || 1;
    }
    // Average per model (will be multiplied by other params which already include model count)
    return config.embedding_models.length > 0 ? totalModelDimCombos / config.embedding_models.length : 1;
  })();

  // Effective search type count: simple types + expanded advanced types
  const advancedTypes = ["multi_query", "agentic", "crag", "self_rag", "raptor"];
  const simpleSearchCount = config.search_types.filter((t) => !advancedTypes.includes(t)).length;
  const mqExpansion = config.search_types.includes("multi_query") ? config.multi_query_counts.length : 0;
  const agExpansion = config.search_types.includes("agentic") ? config.agent_max_steps.length : 0;
  const cragExpansion = config.search_types.includes("crag") ? config.crag_relevance_thresholds.length * config.crag_max_retries.length : 0;
  const selfRagExpansion = config.search_types.includes("self_rag") ? config.self_rag_retrieval_thresholds.length : 0;
  const raptorExpansion = config.search_types.includes("raptor") ? config.raptor_max_levels.length * config.raptor_clustering.length * config.raptor_retrieval_modes.length : 0;
  const effectiveSearchCount = simpleSearchCount + mqExpansion + agExpansion + cragExpansion + selfRagExpansion + raptorExpansion;

  const ragCombinations = config.pipeline_types.includes("rag")
    ? Math.round(
        config.chunk_sizes.length *
        config.chunk_overlaps.length *
        config.embedding_models.length *
        config.top_k_values.length *
        Math.max(effectiveSearchCount, 1) *
        config.distance_metrics.length *
        config.chunking_strategies.length *
        dimensionMultiplier
      )
    : 0;

  const graphragCombinations = config.pipeline_types.includes("graphrag")
    ? Math.round(
        config.chunk_sizes.length *
        config.chunk_overlaps.length *
        config.embedding_models.length *
        config.chunking_strategies.length *
        (config.entity_extraction_models.length || 1) *
        config.max_gleanings.length *
        config.community_levels.length *
        config.search_modes.length *
        dimensionMultiplier
      )
    : 0;

  const promptMultiplier = Math.max(config.prompt_templates.length, 1);
  const totalCombinations = (ragCombinations + graphragCombinations) * promptMultiplier;

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

  // Auto-update cost estimate when config changes (debounced)
  const debounceRef = useRef<NodeJS.Timeout | null>(null);
  useEffect(() => {
    if (!datasetId || totalCombinations === 0) {
      setCostEstimate(null);
      return;
    }
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(async () => {
      try {
        let expId = tempExperimentId;
        if (!expId) {
          const exp = await api.createExperiment({
            name: `estimate-${Date.now()}`,
            dataset_id: datasetId,
            vectorstore_type: vectorStoreType,
          });
          expId = exp.id;
          setTempExperimentId(expId);
        }
        const estimate = await api.estimateCost(expId, config);
        setCostEstimate(estimate);
      } catch {
        // silent
      }
    }, 800);
    return () => { if (debounceRef.current) clearTimeout(debounceRef.current); };
  }, [config, datasetId, totalCombinations]);

  const handleSubmit = async () => {
    if (!datasetId) return;
    setLoading(true);

    try {
      let expId = tempExperimentId;
      if (!expId) {
        const exp = await api.createExperiment({
          name: experimentName.trim() || undefined,
          dataset_id: datasetId,
          vectorstore_type: vectorStoreType,
        });
        expId = exp.id;
      }
      await api.configureGrid(expId, config);
      onComplete(expId);
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
          <div>
            <label className="block text-sm font-medium text-t-hover mb-2">Answer Language</label>
            <select
              value={config.answer_language}
              onChange={(e) => setConfig((prev) => ({ ...prev, answer_language: e.target.value }))}
              className="w-full px-4 py-3 bg-surface-50 border border-surface-200/50 rounded-xl text-primary focus:outline-none focus:border-accent/50"
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
          {/* Pipeline Type */}
          <div>
            <label className="block text-sm font-medium text-t-hover mb-3">Pipeline Type</label>
            <div className="flex gap-3">
              {[
                { id: "rag", label: "RAG" },
                { id: "graphrag", label: "GraphRAG" },
              ].map((pt) => (
                <label
                  key={pt.id}
                  className="flex items-center gap-2 cursor-pointer"
                >
                  <input
                    type="checkbox"
                    checked={config.pipeline_types.includes(pt.id)}
                    onChange={() => {
                      setConfig((prev) => {
                        const includes = prev.pipeline_types.includes(pt.id);
                        // Don't allow removing the last pipeline type
                        if (includes && prev.pipeline_types.length === 1) return prev;
                        return {
                          ...prev,
                          pipeline_types: includes
                            ? prev.pipeline_types.filter((t) => t !== pt.id)
                            : [...prev.pipeline_types, pt.id],
                        };
                      });
                    }}
                    className="rounded border-surface-300 bg-surface-50 text-accent focus:ring-accent/25"
                  />
                  <span className="text-sm text-t-hover">{pt.label}</span>
                </label>
              ))}
            </div>
            {ragCombinations > 0 && graphragCombinations > 0 && (
              <p className="text-xs text-muted mt-2">
                RAG: {ragCombinations} combos + GraphRAG: {graphragCombinations} combos = {totalCombinations} total
              </p>
            )}
          </div>

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

          {/* Chunking Strategy */}
          <div>
            <label className="block text-sm font-medium text-t-hover mb-3">Chunking Strategy</label>
            <div className="flex gap-3 flex-wrap">
              {CHUNKING_STRATEGIES.map((cs) => (
                <label
                  key={cs.id}
                  className="flex items-center gap-2 cursor-pointer"
                  title={cs.description}
                >
                  <input
                    type="checkbox"
                    checked={config.chunking_strategies.includes(cs.id)}
                    onChange={() => {
                      if (config.chunking_strategies.includes(cs.id)) {
                        setConfig((prev) => ({
                          ...prev,
                          chunking_strategies: prev.chunking_strategies.filter((s) => s !== cs.id),
                        }));
                      } else {
                        setConfig((prev) => ({
                          ...prev,
                          chunking_strategies: [...prev.chunking_strategies, cs.id],
                        }));
                      }
                    }}
                    className="rounded border-surface-300 bg-surface-50 text-accent focus:ring-accent/25"
                  />
                  <span className="text-sm text-t-hover">{cs.label}</span>
                  <span className="text-xs text-muted">({cs.description})</span>
                </label>
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

          {/* Top-K (RAG only) */}
          {config.pipeline_types.includes("rag") && (
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
          )}

          {/* Search type (RAG only) */}
          {config.pipeline_types.includes("rag") && (
          <div>
            <label className="block text-sm font-medium text-t-hover mb-3">Search Type</label>
            <div className="flex flex-wrap gap-x-4 gap-y-2">
              {SEARCH_TYPES.map((st) => (
                <label
                  key={st.id}
                  className="flex items-center gap-2 cursor-pointer"
                  title={st.description}
                >
                  <input
                    type="checkbox"
                    checked={config.search_types.includes(st.id)}
                    onChange={() => {
                      if (config.search_types.includes(st.id)) {
                        setConfig((prev) => ({
                          ...prev,
                          search_types: prev.search_types.filter((t) => t !== st.id),
                        }));
                      } else {
                        addToArray("search_types", st.id);
                      }
                    }}
                    className="rounded border-surface-300 bg-surface-50 text-accent focus:ring-accent/25"
                  />
                  <span className="text-sm text-t-hover">{st.label}</span>
                  {st.cost && (
                    <span className={`text-[10px] px-1.5 py-0.5 rounded-full font-medium ${
                      st.cost === "red"
                        ? "bg-red-500/15 text-red-400"
                        : "bg-amber-500/15 text-amber-400"
                    }`}>
                      {st.cost === "red" ? "$$$$" : "$$"}
                    </span>
                  )}
                </label>
              ))}
            </div>
            <p className="text-xs text-muted mt-2">
              Multi-Query and Agentic use extra LLM calls during retrieval, increasing cost.
            </p>

            {/* Multi-Query sub-parameter */}
            {config.search_types.includes("multi_query") && (
              <div className="mt-3 ml-5 pl-3 border-l-2 border-amber-500/30">
                <label className="block text-xs font-medium text-t-secondary mb-2">
                  Alternative Queries (multi_query_count)
                </label>
                <div className="flex gap-2">
                  {[3, 4, 5].map((n) => (
                    <button
                      key={n}
                      onClick={() => {
                        setConfig((prev) => ({
                          ...prev,
                          multi_query_counts: prev.multi_query_counts.includes(n)
                            ? prev.multi_query_counts.filter((v) => v !== n)
                            : [...prev.multi_query_counts, n].sort(),
                        }));
                      }}
                      className={`px-3 py-1.5 rounded-lg text-xs transition-all ${
                        config.multi_query_counts.includes(n)
                          ? "bg-amber-500/20 text-amber-300 border border-amber-500/30"
                          : "bg-surface-50 text-muted border border-surface-200/50"
                      }`}
                    >
                      {n}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {/* Agentic sub-parameter */}
            {config.search_types.includes("agentic") && (
              <div className="mt-3 ml-5 pl-3 border-l-2 border-red-500/30">
                <label className="block text-xs font-medium text-t-secondary mb-2">
                  Max Agent Steps (agent_max_steps)
                </label>
                <div className="flex gap-2">
                  {[3, 5, 7, 10].map((n) => (
                    <button
                      key={n}
                      onClick={() => {
                        setConfig((prev) => ({
                          ...prev,
                          agent_max_steps: prev.agent_max_steps.includes(n)
                            ? prev.agent_max_steps.filter((v) => v !== n)
                            : [...prev.agent_max_steps, n].sort(),
                        }));
                      }}
                      className={`px-3 py-1.5 rounded-lg text-xs transition-all ${
                        config.agent_max_steps.includes(n)
                          ? "bg-red-500/20 text-red-300 border border-red-500/30"
                          : "bg-surface-50 text-muted border border-surface-200/50"
                      }`}
                    >
                      {n}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {/* CRAG sub-parameters */}
            {config.search_types.includes("crag") && (
              <div className="mt-3 ml-5 pl-3 border-l-2 border-amber-500/30 space-y-3">
                <div>
                  <label className="block text-xs font-medium text-t-secondary mb-2">Relevance Threshold</label>
                  <div className="flex gap-2">
                    {[0.5, 0.7, 0.9].map((v) => (
                      <button key={v} onClick={() => setConfig((prev) => ({
                        ...prev, crag_relevance_thresholds: prev.crag_relevance_thresholds.includes(v)
                          ? prev.crag_relevance_thresholds.filter((x) => x !== v)
                          : [...prev.crag_relevance_thresholds, v].sort(),
                      }))} className={`px-3 py-1.5 rounded-lg text-xs transition-all ${
                        config.crag_relevance_thresholds.includes(v)
                          ? "bg-amber-500/20 text-amber-300 border border-amber-500/30"
                          : "bg-surface-50 text-muted border border-surface-200/50"
                      }`}>{v}</button>
                    ))}
                  </div>
                </div>
                <div>
                  <label className="block text-xs font-medium text-t-secondary mb-2">Max Retries</label>
                  <div className="flex gap-2">
                    {[1, 2, 3].map((v) => (
                      <button key={v} onClick={() => setConfig((prev) => ({
                        ...prev, crag_max_retries: prev.crag_max_retries.includes(v)
                          ? prev.crag_max_retries.filter((x) => x !== v)
                          : [...prev.crag_max_retries, v].sort(),
                      }))} className={`px-3 py-1.5 rounded-lg text-xs transition-all ${
                        config.crag_max_retries.includes(v)
                          ? "bg-amber-500/20 text-amber-300 border border-amber-500/30"
                          : "bg-surface-50 text-muted border border-surface-200/50"
                      }`}>{v}</button>
                    ))}
                  </div>
                </div>
              </div>
            )}

            {/* Self-RAG sub-parameter */}
            {config.search_types.includes("self_rag") && (
              <div className="mt-3 ml-5 pl-3 border-l-2 border-amber-500/30">
                <label className="block text-xs font-medium text-t-secondary mb-2">Retrieval Threshold</label>
                <div className="flex gap-2">
                  {[0.3, 0.5, 0.7].map((v) => (
                    <button key={v} onClick={() => setConfig((prev) => ({
                      ...prev, self_rag_retrieval_thresholds: prev.self_rag_retrieval_thresholds.includes(v)
                        ? prev.self_rag_retrieval_thresholds.filter((x) => x !== v)
                        : [...prev.self_rag_retrieval_thresholds, v].sort(),
                    }))} className={`px-3 py-1.5 rounded-lg text-xs transition-all ${
                      config.self_rag_retrieval_thresholds.includes(v)
                        ? "bg-amber-500/20 text-amber-300 border border-amber-500/30"
                        : "bg-surface-50 text-muted border border-surface-200/50"
                    }`}>{v}</button>
                  ))}
                </div>
              </div>
            )}

            {/* RAPTOR sub-parameters */}
            {config.search_types.includes("raptor") && (
              <div className="mt-3 ml-5 pl-3 border-l-2 border-red-500/30 space-y-3">
                <div>
                  <label className="block text-xs font-medium text-t-secondary mb-2">Max Levels</label>
                  <div className="flex gap-2">
                    {[2, 3, 4].map((v) => (
                      <button key={v} onClick={() => setConfig((prev) => ({
                        ...prev, raptor_max_levels: prev.raptor_max_levels.includes(v)
                          ? prev.raptor_max_levels.filter((x) => x !== v)
                          : [...prev.raptor_max_levels, v].sort(),
                      }))} className={`px-3 py-1.5 rounded-lg text-xs transition-all ${
                        config.raptor_max_levels.includes(v)
                          ? "bg-red-500/20 text-red-300 border border-red-500/30"
                          : "bg-surface-50 text-muted border border-surface-200/50"
                      }`}>{v}</button>
                    ))}
                  </div>
                </div>
                <div>
                  <label className="block text-xs font-medium text-t-secondary mb-2">Clustering</label>
                  <div className="flex gap-2">
                    {["kmeans", "gmm"].map((v) => (
                      <button key={v} onClick={() => setConfig((prev) => ({
                        ...prev, raptor_clustering: prev.raptor_clustering.includes(v)
                          ? prev.raptor_clustering.filter((x) => x !== v)
                          : [...prev.raptor_clustering, v],
                      }))} className={`px-3 py-1.5 rounded-lg text-xs transition-all ${
                        config.raptor_clustering.includes(v)
                          ? "bg-red-500/20 text-red-300 border border-red-500/30"
                          : "bg-surface-50 text-muted border border-surface-200/50"
                      }`}>{v}</button>
                    ))}
                  </div>
                </div>
                <div>
                  <label className="block text-xs font-medium text-t-secondary mb-2">Retrieval Mode</label>
                  <div className="flex gap-2">
                    {["collapsed", "tree_traversal", "level_specific"].map((v) => (
                      <button key={v} onClick={() => setConfig((prev) => ({
                        ...prev, raptor_retrieval_modes: prev.raptor_retrieval_modes.includes(v)
                          ? prev.raptor_retrieval_modes.filter((x) => x !== v)
                          : [...prev.raptor_retrieval_modes, v],
                      }))} className={`px-3 py-1.5 rounded-lg text-xs transition-all ${
                        config.raptor_retrieval_modes.includes(v)
                          ? "bg-red-500/20 text-red-300 border border-red-500/30"
                          : "bg-surface-50 text-muted border border-surface-200/50"
                      }`}>{v.replace("_", " ")}</button>
                    ))}
                  </div>
                </div>
              </div>
            )}
          </div>
          )}

          {/* Distance Metric (RAG only) */}
          {config.pipeline_types.includes("rag") && (
          <div>
            <label className="block text-sm font-medium text-t-hover mb-3">Distance Metric</label>
            <div className="flex gap-3">
              {DISTANCE_METRICS.map((dm) => (
                <label
                  key={dm.id}
                  className="flex items-center gap-2 cursor-pointer"
                >
                  <input
                    type="checkbox"
                    checked={config.distance_metrics.includes(dm.id)}
                    onChange={() => {
                      if (config.distance_metrics.includes(dm.id)) {
                        setConfig((prev) => ({
                          ...prev,
                          distance_metrics: prev.distance_metrics.filter((d) => d !== dm.id),
                        }));
                      } else {
                        setConfig((prev) => ({
                          ...prev,
                          distance_metrics: [...prev.distance_metrics, dm.id],
                        }));
                      }
                    }}
                    className="rounded border-surface-300 bg-surface-50 text-accent focus:ring-accent/25"
                  />
                  <span className="text-sm text-t-hover">{dm.label}</span>
                </label>
              ))}
            </div>
          </div>
          )}

          {/* Embedding Dimensions */}
          <div>
            <label className="block text-sm font-medium text-t-hover mb-1">Embedding Dimensions</label>
            <p className="text-xs text-muted mb-3">
              Leave empty to use each model&apos;s default. Only models that support custom dimensions will be tested with non-default values.
            </p>
            {(() => {
              // Collect all valid dimensions from selected models
              const allDims = new Set<number>();
              const modelDefaults: Record<string, number> = {};
              for (const model of config.embedding_models) {
                const info = dimensionsMap[model];
                if (info) {
                  modelDefaults[model] = info.default;
                  if (info.supports_custom) {
                    info.supported.forEach((d: number) => allDims.add(d));
                  }
                }
              }
              const sortedDims = Array.from(allDims).sort((a, b) => a - b);

              if (sortedDims.length === 0) {
                return (
                  <div className="text-xs text-t-secondary px-3 py-2 bg-surface-50 rounded-lg border border-surface-200/50">
                    Selected models do not support custom dimensions — defaults will be used
                    {Object.entries(modelDefaults).map(([model, dim]) => (
                      <span key={model} className="ml-2 text-muted">({model}: {dim}d)</span>
                    ))}
                  </div>
                );
              }

              return (
                <div className="flex flex-wrap gap-2">
                  {sortedDims.map((dim) => {
                    const selected = config.embedding_dimensions.includes(dim);
                    // Which selected models support this dim?
                    const supportedBy = config.embedding_models.filter((m) => {
                      const info = dimensionsMap[m];
                      return info?.supported.includes(dim);
                    });
                    return (
                      <button
                        key={dim}
                        onClick={() => {
                          setConfig((prev) => ({
                            ...prev,
                            embedding_dimensions: selected
                              ? prev.embedding_dimensions.filter((d) => d !== dim)
                              : [...prev.embedding_dimensions, dim],
                          }));
                        }}
                        className={`px-3 py-1.5 text-xs rounded-lg border transition-colors ${
                          selected
                            ? "bg-accent/10 text-accent border-accent/30"
                            : "bg-surface-200 text-t-hover border-surface-200/50 hover:bg-surface-300"
                        }`}
                        title={`Supported by: ${supportedBy.join(", ")}`}
                      >
                        {dim}d
                      </button>
                    );
                  })}
                </div>
              );
            })()}
          </div>

          {/* GraphRAG Parameters */}
          {config.pipeline_types.includes("graphrag") && (
            <>
              <div className="border-t border-surface-200/30 pt-6">
                <h4 className="text-sm font-semibold text-primary mb-4">GraphRAG Parameters</h4>

                {/* Warning banner */}
                <div className="flex items-start gap-2 mb-4 px-3 py-2 bg-amber-500/10 border border-amber-500/20 rounded-lg text-amber-400 text-xs">
                  <AlertCircle className="w-3.5 h-3.5 shrink-0 mt-0.5" />
                  <span>GraphRAG extracts entities via LLM for every chunk — significantly more expensive than standard RAG.</span>
                </div>

                {/* Entity Extraction Model */}
                <div className="mb-4">
                  <label className="block text-sm font-medium text-t-hover mb-3">Entity Extraction Model</label>
                  {renderChips("entity_extraction_models", config.entity_extraction_models, "secondary")}
                  <div className="flex flex-wrap gap-2 mt-2">
                    {availableLLMs
                      .filter((lm) => !config.entity_extraction_models.includes(lm.model))
                      .map((lm) => (
                        <button
                          key={`${lm.provider_name}-${lm.model}`}
                          onClick={() => addToArray("entity_extraction_models", lm.model)}
                          className="px-3 py-1.5 bg-surface-200 text-t-hover text-xs rounded-lg hover:bg-surface-300 transition-colors"
                          title={`Provider: ${lm.provider_name}`}
                        >
                          + {lm.model}
                          <span className="ml-1 text-muted">({lm.provider_name})</span>
                        </button>
                      ))}
                    {availableLLMs.length === 0 && (
                      <span className="text-xs text-muted">No LLM models available. Configure providers in Settings.</span>
                    )}
                  </div>
                </div>

                {/* Max Gleanings */}
                <div className="mb-4">
                  <label className="block text-sm font-medium text-t-hover mb-3">Max Gleanings</label>
                  {renderChips("max_gleanings", config.max_gleanings)}
                  <div className="flex gap-2 mt-2">
                    {[1, 2, 3].map((val) => (
                      <button
                        key={val}
                        onClick={() => {
                          if (!config.max_gleanings.includes(val)) addToArray("max_gleanings", val);
                        }}
                        disabled={config.max_gleanings.includes(val)}
                        className="px-3 py-1.5 bg-surface-200 text-t-hover text-xs rounded-lg hover:bg-surface-300 disabled:opacity-30 transition-colors"
                      >
                        {val}
                      </button>
                    ))}
                  </div>
                </div>

                {/* Community Levels */}
                <div className="mb-4">
                  <label className="block text-sm font-medium text-t-hover mb-3">Community Levels</label>
                  {renderChips("community_levels", config.community_levels)}
                  <div className="flex gap-2 mt-2">
                    {[1, 2, 3].map((val) => (
                      <button
                        key={val}
                        onClick={() => {
                          if (!config.community_levels.includes(val)) addToArray("community_levels", val);
                        }}
                        disabled={config.community_levels.includes(val)}
                        className="px-3 py-1.5 bg-surface-200 text-t-hover text-xs rounded-lg hover:bg-surface-300 disabled:opacity-30 transition-colors"
                      >
                        {val}
                      </button>
                    ))}
                  </div>
                </div>

                {/* Search Mode */}
                <div>
                  <label className="block text-sm font-medium text-t-hover mb-3">Search Mode</label>
                  <div className="flex gap-3">
                    {["local", "global", "hybrid"].map((mode) => (
                      <label
                        key={mode}
                        className="flex items-center gap-2 cursor-pointer"
                      >
                        <input
                          type="checkbox"
                          checked={config.search_modes.includes(mode)}
                          onChange={() => {
                            if (config.search_modes.includes(mode)) {
                              setConfig((prev) => ({
                                ...prev,
                                search_modes: prev.search_modes.filter((m) => m !== mode),
                              }));
                            } else {
                              addToArray("search_modes", mode);
                            }
                          }}
                          className="rounded border-surface-300 bg-surface-50 text-accent focus:ring-accent/25"
                        />
                        <span className="text-sm text-t-hover capitalize">{mode}</span>
                      </label>
                    ))}
                  </div>
                </div>
              </div>
            </>
          )}
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

      {/* Prompt Templates */}
      <div className="bg-surface-100 rounded-2xl border border-surface-200/50 p-6">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h4 className="text-sm font-semibold text-primary">Prompt Templates</h4>
            <p className="text-xs text-muted mt-0.5">
              Customize the answer generation prompt. Use <code className="text-accent">{"{context}"}</code> and <code className="text-accent">{"{question}"}</code> as placeholders.
              {config.prompt_templates.length > 1 && (
                <span className="text-amber-400 ml-1">
                  {config.prompt_templates.length} templates = {config.prompt_templates.length}x more combinations
                </span>
              )}
            </p>
          </div>
          <button
            onClick={() => {
              setConfig((prev) => ({
                ...prev,
                prompt_templates: [
                  ...prev.prompt_templates,
                  `Based on the following context, answer the question.\nIf the answer cannot be found in the context, say "I cannot find the answer in the provided context."{lang_instruction}\n\nContext:\n{context}\n\nQuestion: {question}\n\nAnswer:`,
                ],
              }));
            }}
            className="flex items-center gap-1.5 px-3 py-1.5 bg-accent/10 text-accent text-xs font-medium rounded-lg hover:bg-accent/20 transition-colors"
          >
            <Plus className="w-3.5 h-3.5" />
            Add Template
          </button>
        </div>

        {config.prompt_templates.length === 0 ? (
          <div className="text-center py-6 border border-dashed border-surface-300 rounded-xl">
            <p className="text-sm text-muted">Using default prompt template.</p>
            <p className="text-xs text-t-secondary mt-1">Click &quot;Add Template&quot; to customize or test multiple prompts.</p>
          </div>
        ) : (
          <div className="space-y-3">
            {config.prompt_templates.map((tpl, idx) => (
              <div key={idx} className="relative group">
                <div className="flex items-center gap-2 mb-1.5">
                  <span className="text-xs font-medium text-t-secondary">Template {idx + 1}</span>
                  <button
                    onClick={() => {
                      setConfig((prev) => ({
                        ...prev,
                        prompt_templates: prev.prompt_templates.filter((_, i) => i !== idx),
                      }));
                    }}
                    className="p-0.5 text-muted hover:text-red-400 transition-colors"
                  >
                    <X className="w-3.5 h-3.5" />
                  </button>
                </div>
                <textarea
                  value={tpl}
                  onChange={(e) => {
                    setConfig((prev) => ({
                      ...prev,
                      prompt_templates: prev.prompt_templates.map((t, i) =>
                        i === idx ? e.target.value : t
                      ),
                    }));
                  }}
                  rows={6}
                  className="w-full px-4 py-3 bg-surface-50 border border-surface-200/50 rounded-xl text-primary text-xs font-mono leading-relaxed focus:outline-none focus:border-accent/50 resize-y"
                  placeholder="Write your prompt template here. Use {context} and {question} placeholders."
                />
                {!tpl.includes("{context}") && (
                  <p className="text-[10px] text-red-400 mt-1">Missing {"{context}"} placeholder</p>
                )}
                {!tpl.includes("{question}") && (
                  <p className="text-[10px] text-red-400 mt-1">Missing {"{question}"} placeholder</p>
                )}
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Cost estimate */}
      {costEstimate && (
        <div className="bg-surface-100 rounded-2xl border border-surface-200/50 p-6">
          <div className="grid grid-cols-4 gap-4">
            <div className="text-center">
              <p className="text-xs text-t-secondary">Combinations</p>
              <p className="text-lg font-bold text-primary">{costEstimate.total_combinations}</p>
            </div>
            <div className="text-center">
              <p className="text-xs text-t-secondary">Est. Tokens</p>
              <p className="text-lg font-bold text-primary">
                {costEstimate.estimated_total_tokens >= 1_000_000
                  ? `${(costEstimate.estimated_total_tokens / 1_000_000).toFixed(1)}M`
                  : `${(costEstimate.estimated_total_tokens / 1_000).toFixed(0)}K`}
              </p>
            </div>
            <div className="text-center">
              <p className="text-xs text-t-secondary">Questions</p>
              <p className="text-lg font-bold text-primary">{costEstimate.num_questions}</p>
            </div>
            <div className="text-center">
              <p className="text-xs text-t-secondary">Est. Cost</p>
              <p className="text-lg font-bold text-amber-400">${costEstimate.estimated_cost_usd}</p>
            </div>
          </div>
          <p className="text-xs text-muted mt-3 text-center">
            Approximate values. Actual cost depends on provider and model.
          </p>
        </div>
      )}

      {/* Submit */}
      <button
        onClick={handleSubmit}
        disabled={loading || totalCombinations === 0}
        className="w-full py-3 px-6 bg-gradient-to-r from-accent to-accent-dark text-primary font-medium rounded-xl hover:opacity-90 transition-opacity disabled:opacity-50 flex items-center justify-center gap-2"
      >
        {loading ? (
          <Loader2 className="w-4 h-4 animate-spin" />
        ) : (
          <Grid3X3 className="w-4 h-4" />
        )}
        Confirm Grid Search Configuration & Continue
      </button>
    </div>
  );
}
