"use client";

import { useState, useEffect, useRef } from "react";
import { Grid3X3, Plus, X, Loader2, AlertCircle, DollarSign, Scissors, Cpu, Search } from "lucide-react";
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
      {/* ════ Main form card ════ */}
      <div className="bg-surface-100 rounded-2xl border border-surface-200/50 p-8 space-y-6">

        {/* Experiment setup */}
        <div className="grid grid-cols-3 gap-5">
          <div className="rounded-xl border border-visible p-4">
            <label className="block text-sm font-medium text-t-hover mb-1">Experiment Name</label>
            <p className="text-xs text-muted mb-2">A name to identify this experiment run.</p>
            <input
              type="text"
              value={experimentName}
              onChange={(e) => setExperimentName(e.target.value)}
              placeholder="e.g., Documentation RAG v1"
              className="w-full px-3 py-2 bg-surface-50 border border-surface-200/50 rounded-lg text-primary placeholder-muted text-sm focus:outline-none focus:border-accent/50"
            />
          </div>
          <div className="rounded-xl border border-visible p-4">
            <label className="block text-sm font-medium text-t-hover mb-1">Vector Store</label>
            <p className="text-xs text-muted mb-2">Backend for storing and searching embeddings.</p>
            <select
              value={vectorStoreType}
              onChange={(e) => setVectorStoreType(e.target.value)}
              className="w-full px-3 py-2 bg-surface-50 border border-surface-200/50 rounded-lg text-primary text-sm focus:outline-none focus:border-accent/50"
            >
              <option value="chromadb">ChromaDB (Default)</option>
              <option value="pinecone">Pinecone</option>
              <option value="weaviate">Weaviate</option>
              <option value="qdrant">Qdrant</option>
              <option value="pgvector">PGVector</option>
            </select>
          </div>
          <div className="rounded-xl border border-visible p-4">
            <label className="block text-sm font-medium text-t-hover mb-1">Answer Language</label>
            <p className="text-xs text-muted mb-2">Language for LLM-generated answers.</p>
            <select
              value={config.answer_language}
              onChange={(e) => setConfig((prev) => ({ ...prev, answer_language: e.target.value }))}
              className="w-full px-3 py-2 bg-surface-50 border border-surface-200/50 rounded-lg text-primary text-sm focus:outline-none focus:border-accent/50"
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

        {/* Pipeline type */}
        <div className="rounded-xl border border-visible p-4">
          <label className="block text-sm font-medium text-t-hover mb-1">Pipeline Type</label>
          <p className="text-xs text-muted mb-3">Select which pipeline architectures to compare.</p>
          <div className="flex items-center gap-4">
            <div className="flex gap-4">
              {[
                { id: "rag", label: "RAG" },
                { id: "graphrag", label: "GraphRAG" },
              ].map((pt) => (
                <label key={pt.id} className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={config.pipeline_types.includes(pt.id)}
                    onChange={() => {
                      setConfig((prev) => {
                        const includes = prev.pipeline_types.includes(pt.id);
                        if (includes && prev.pipeline_types.length === 1) return prev;
                        return { ...prev, pipeline_types: includes ? prev.pipeline_types.filter((t) => t !== pt.id) : [...prev.pipeline_types, pt.id] };
                      });
                    }}
                    className="rounded border-visible bg-surface-50 text-accent focus:ring-accent/25"
                  />
                  <span className="text-sm text-t-hover">{pt.label}</span>
                </label>
              ))}
            </div>
            {ragCombinations > 0 && graphragCombinations > 0 && (
              <p className="text-xs text-muted ml-auto">RAG: {ragCombinations} + GraphRAG: {graphragCombinations}</p>
            )}
          </div>
        </div>

        {/* Chunk Size */}
        <div className="rounded-xl border border-visible p-4">
          <label className="block text-sm font-medium text-t-hover mb-1">Chunk Size (tokens)</label>
          <p className="text-xs text-muted mb-3">Number of characters per text fragment. Smaller = more precise retrieval, larger = more surrounding context.</p>
          {renderChips("chunk_sizes", config.chunk_sizes)}
          <div className="flex gap-2 mt-2">
            <input type="number" value={newChunkSize} onChange={(e) => setNewChunkSize(e.target.value)} placeholder="Add size..." className="px-3 py-2 bg-surface-50 border border-surface-200/50 rounded-lg text-primary text-sm w-28 focus:outline-none focus:border-accent/50" />
            <button onClick={() => { if (newChunkSize) { addToArray("chunk_sizes", parseInt(newChunkSize)); setNewChunkSize(""); } }} className="p-2 bg-surface-200 rounded-lg hover:bg-surface-300 transition-colors"><Plus className="w-4 h-4 text-t-hover" /></button>
          </div>
        </div>

        {/* Chunk Overlap */}
        <div className="rounded-xl border border-visible p-4">
          <label className="block text-sm font-medium text-t-hover mb-1">Chunk Overlap (%)</label>
          <p className="text-xs text-muted mb-3">Percentage of overlap between consecutive chunks. Prevents important information from being cut at boundaries.</p>
          {renderChips("chunk_overlaps", config.chunk_overlaps)}
          <div className="flex flex-wrap gap-1.5 mt-2">
            {[5, 10, 15, 20, 25, 30].map((val) => (
              <button key={val} onClick={() => { if (!config.chunk_overlaps.includes(val)) addToArray("chunk_overlaps", val); }} disabled={config.chunk_overlaps.includes(val)} className="px-2.5 py-1 bg-surface-200 text-t-hover text-xs rounded-lg hover:bg-surface-300 disabled:opacity-30 transition-colors">{val}%</button>
            ))}
          </div>
        </div>

        {/* Chunking Strategy */}
        <div className="rounded-xl border border-visible p-4">
          <label className="block text-sm font-medium text-t-hover mb-1">Chunking Strategy</label>
          <p className="text-xs text-muted mb-3">Algorithm for splitting documents into chunks.</p>
          <div className="flex gap-3 flex-wrap">
            {CHUNKING_STRATEGIES.map((cs) => (
              <label key={cs.id} className="flex items-center gap-2 cursor-pointer" title={cs.description}>
                <input type="checkbox" checked={config.chunking_strategies.includes(cs.id)} onChange={() => { if (config.chunking_strategies.includes(cs.id)) { setConfig((prev) => ({ ...prev, chunking_strategies: prev.chunking_strategies.filter((s) => s !== cs.id) })); } else { setConfig((prev) => ({ ...prev, chunking_strategies: [...prev.chunking_strategies, cs.id] })); } }} className="rounded border-visible bg-surface-50 text-accent focus:ring-accent/25" />
                <span className="text-sm text-t-hover">{cs.label}</span>
                <span className="text-xs text-muted">({cs.description})</span>
              </label>
            ))}
          </div>
        </div>

        {/* Embedding models */}
        <div className="rounded-xl border border-visible p-4">
          <label className="block text-sm font-medium text-t-hover mb-1">Embedding Models</label>
          <p className="text-xs text-muted mb-3">Neural networks that convert text into vectors for similarity search.</p>
          {noProviders && (
            <div className="flex items-center gap-2 mb-3 px-3 py-2 bg-amber-500/10 border border-amber-500/20 rounded-lg text-amber-400 text-xs">
              <AlertCircle className="w-3.5 h-3.5 shrink-0" />
              No providers configured. Go to Settings &rarr; Providers to add one.
            </div>
          )}
          {renderChips("embedding_models", config.embedding_models, "secondary")}
          <div className="flex flex-wrap gap-2 mt-2">
            {availableEmbeddings.filter((em) => !config.embedding_models.includes(em.model)).map((em) => (
              <button key={`${em.provider_name}-${em.model}`} onClick={() => addToArray("embedding_models", em.model)} className="px-3 py-1.5 bg-surface-200 text-t-hover text-xs rounded-lg hover:bg-surface-300 transition-colors" title={`Provider: ${em.provider_name}`}>
                + {em.model}<span className="ml-1 text-muted">({em.provider_name})</span>
              </button>
            ))}
          </div>
        </div>

        {/* Retrieval (RAG only) */}
        {config.pipeline_types.includes("rag") && (<>

        {/* Top-K */}
        <div className="rounded-xl border border-visible p-4">
          <label className="block text-sm font-medium text-t-hover mb-1">Top-K (retrieved docs)</label>
          <p className="text-xs text-muted mb-3">Number of most similar chunks retrieved per query. Higher = more context but more noise.</p>
          {renderChips("top_k_values", config.top_k_values)}
          <div className="flex gap-2 mt-2">
            <input type="number" value={newTopK} onChange={(e) => setNewTopK(e.target.value)} placeholder="Add..." className="px-3 py-2 bg-surface-50 border border-surface-200/50 rounded-lg text-primary text-sm w-24 focus:outline-none focus:border-accent/50" />
            <button onClick={() => { if (newTopK) { addToArray("top_k_values", parseInt(newTopK)); setNewTopK(""); } }} className="p-2 bg-surface-200 rounded-lg hover:bg-surface-300 transition-colors"><Plus className="w-4 h-4 text-t-hover" /></button>
          </div>
        </div>

        {/* Distance Metric */}
        <div className="rounded-xl border border-visible p-4">
          <label className="block text-sm font-medium text-t-hover mb-1">Distance Metric</label>
          <p className="text-xs text-muted mb-3">Mathematical function to measure how similar two embedding vectors are.</p>
            <div className="flex flex-wrap gap-3">
              {DISTANCE_METRICS.map((dm) => (
                <label key={dm.id} className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={config.distance_metrics.includes(dm.id)}
                    onChange={() => {
                      if (config.distance_metrics.includes(dm.id)) {
                        setConfig((prev) => ({ ...prev, distance_metrics: prev.distance_metrics.filter((d) => d !== dm.id) }));
                      } else {
                        setConfig((prev) => ({ ...prev, distance_metrics: [...prev.distance_metrics, dm.id] }));
                      }
                    }}
                    className="rounded border-visible bg-surface-50 text-accent focus:ring-accent/25"
                  />
                  <span className="text-sm text-t-hover">{dm.label}</span>
                </label>
              ))}
            </div>
        </div>

        {/* Search Type */}
        <div className="rounded-xl border border-visible p-4">
          <label className="block text-sm font-medium text-t-hover mb-1">Search Type</label>
          <p className="text-xs text-muted mb-3">Algorithm for finding relevant chunks. Strategies with $$ use extra LLM calls.</p>
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
                    className="rounded border-visible bg-surface-50 text-accent focus:ring-accent/25"
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

            {/* Multi-Query sub-parameter */}
            {config.search_types.includes("multi_query") && (
              <div className="mt-3 ml-5 pl-3 border-l-2 border-amber-500">
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
                          ? "chip-amber border"
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
              <div className="mt-3 ml-5 pl-3 border-l-2 border-red-500">
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
                          ? "chip-red border"
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
              <div className="mt-3 ml-5 pl-3 border-l-2 border-amber-500 space-y-3">
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
                          ? "chip-amber border"
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
                          ? "chip-amber border"
                          : "bg-surface-50 text-muted border border-surface-200/50"
                      }`}>{v}</button>
                    ))}
                  </div>
                </div>
              </div>
            )}

            {/* Self-RAG sub-parameter */}
            {config.search_types.includes("self_rag") && (
              <div className="mt-3 ml-5 pl-3 border-l-2 border-amber-500">
                <label className="block text-xs font-medium text-t-secondary mb-2">Retrieval Threshold</label>
                <div className="flex gap-2">
                  {[0.3, 0.5, 0.7].map((v) => (
                    <button key={v} onClick={() => setConfig((prev) => ({
                      ...prev, self_rag_retrieval_thresholds: prev.self_rag_retrieval_thresholds.includes(v)
                        ? prev.self_rag_retrieval_thresholds.filter((x) => x !== v)
                        : [...prev.self_rag_retrieval_thresholds, v].sort(),
                    }))} className={`px-3 py-1.5 rounded-lg text-xs transition-all ${
                      config.self_rag_retrieval_thresholds.includes(v)
                        ? "chip-amber border"
                        : "bg-surface-50 text-muted border border-surface-200/50"
                    }`}>{v}</button>
                  ))}
                </div>
              </div>
            )}

            {/* RAPTOR sub-parameters */}
            {config.search_types.includes("raptor") && (
              <div className="mt-3 ml-5 pl-3 border-l-2 border-red-500 space-y-3">
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
                          ? "chip-red border"
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
                          ? "chip-red border"
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
                          ? "chip-red border"
                          : "bg-surface-50 text-muted border border-surface-200/50"
                      }`}>{v.replace("_", " ")}</button>
                    ))}
                  </div>
                </div>
              </div>
            )}
        </div>
        </>)}

        {/* GraphRAG Parameters */}
        {config.pipeline_types.includes("graphrag") && (<>

        {/* Divider */}
        <div className="border-t border-surface-200/30" />

        <div className="flex items-start gap-2 px-3 py-2 bg-amber-500/10 border border-amber-500/20 rounded-lg text-amber-400 text-xs">
          <AlertCircle className="w-3.5 h-3.5 shrink-0 mt-0.5" />
          <span>GraphRAG extracts entities via LLM for every chunk — significantly more expensive than standard RAG.</span>
        </div>

        {/* Entity Extraction Model */}
        <div className="rounded-xl border border-visible p-4">
          <label className="block text-sm font-medium text-t-hover mb-1">Entity Extraction Model</label>
          <p className="text-xs text-muted mb-3">LLM used to extract entities and relationships from each chunk.</p>
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
        <div className="rounded-xl border border-visible p-4">
          <label className="block text-sm font-medium text-t-hover mb-1">Max Gleanings</label>
          <p className="text-xs text-muted mb-3">Number of extraction passes per chunk. More passes catch missed entities but increase cost.</p>
          {renderChips("max_gleanings", config.max_gleanings)}
          <div className="flex gap-2 mt-2">
            {[1, 2, 3].map((val) => (
              <button key={val} onClick={() => { if (!config.max_gleanings.includes(val)) addToArray("max_gleanings", val); }} disabled={config.max_gleanings.includes(val)} className="px-3 py-1.5 bg-surface-200 text-t-hover text-xs rounded-lg hover:bg-surface-300 disabled:opacity-30 transition-colors">{val}</button>
            ))}
          </div>
        </div>

        {/* Community Levels */}
        <div className="rounded-xl border border-visible p-4">
          <label className="block text-sm font-medium text-t-hover mb-1">Community Levels</label>
          <p className="text-xs text-muted mb-3">Granularity of the Leiden community detection. Higher levels produce finer-grained communities.</p>
          {renderChips("community_levels", config.community_levels)}
          <div className="flex gap-2 mt-2">
            {[1, 2, 3].map((val) => (
              <button key={val} onClick={() => { if (!config.community_levels.includes(val)) addToArray("community_levels", val); }} disabled={config.community_levels.includes(val)} className="px-3 py-1.5 bg-surface-200 text-t-hover text-xs rounded-lg hover:bg-surface-300 disabled:opacity-30 transition-colors">{val}</button>
            ))}
          </div>
        </div>

        {/* Search Mode */}
        <div className="rounded-xl border border-visible p-4">
          <label className="block text-sm font-medium text-t-hover mb-1">Search Mode</label>
          <p className="text-xs text-muted mb-3">How the graph is queried. Local traverses entity neighborhoods, global searches community summaries, hybrid combines both.</p>
          <div className="flex gap-3">
            {["local", "global", "hybrid"].map((mode) => (
              <label key={mode} className="flex items-center gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  checked={config.search_modes.includes(mode)}
                  onChange={() => {
                    if (config.search_modes.includes(mode)) {
                      setConfig((prev) => ({ ...prev, search_modes: prev.search_modes.filter((m) => m !== mode) }));
                    } else {
                      addToArray("search_modes", mode);
                    }
                  }}
                  className="rounded border-visible bg-surface-50 text-accent focus:ring-accent/25"
                />
                <span className="text-sm text-t-hover capitalize">{mode}</span>
              </label>
            ))}
          </div>
        </div>
        </>)}

      {/* Close the main form card */}
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
                  ? "bg-accent/5 border-accent"
                  : "bg-surface-50 border-visible hover:border-accent/50"
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
          <div className="text-center py-6 border border-dashed border-visible rounded-xl">
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

      {/* Summary + Submit footer */}
      <div className="bg-surface-100 rounded-2xl border border-visible p-6">
        <div className="grid grid-cols-4 gap-4 mb-5">
          <div className="text-center rounded-lg bg-surface-50 py-3">
            <p className="text-xs text-t-secondary mb-1">Combinations</p>
            <p className="text-2xl font-bold text-primary">{totalCombinations}</p>
          </div>
          <div className="text-center rounded-lg bg-surface-50 py-3">
            <p className="text-xs text-t-secondary mb-1">Est. Tokens</p>
            <p className="text-2xl font-bold text-primary">
              {costEstimate
                ? costEstimate.estimated_total_tokens >= 1_000_000
                  ? `${(costEstimate.estimated_total_tokens / 1_000_000).toFixed(1)}M`
                  : `${(costEstimate.estimated_total_tokens / 1_000).toFixed(0)}K`
                : "—"}
            </p>
          </div>
          <div className="text-center rounded-lg bg-surface-50 py-3">
            <p className="text-xs text-t-secondary mb-1">Questions</p>
            <p className="text-2xl font-bold text-primary">{costEstimate?.num_questions ?? "—"}</p>
          </div>
          <div className="text-center rounded-lg bg-surface-50 py-3">
            <p className="text-xs text-t-secondary mb-1">Est. Cost</p>
            <p className="text-2xl font-bold text-amber-400">{costEstimate ? `$${costEstimate.estimated_cost_usd}` : "—"}</p>
          </div>
        </div>
        <p className="text-xs text-muted mb-4 text-center">
          {costEstimate
            ? "Approximate values. Actual cost depends on provider and model."
            : "Cost estimate will appear once a dataset is selected in a previous step."}
        </p>
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
          Confirm & Continue
        </button>
      </div>
    </div>
  );
}
