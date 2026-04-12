"use client";

import React, { useState, useEffect } from "react";
import { BarChart3, Trophy, Download, ArrowUpDown, ChevronDown, ChevronRight, Eye, Check, X, Minus, MessageSquare } from "lucide-react";
import { api } from "@/lib/api";
import { useWalkthrough } from "@/contexts/WalkthroughContext";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  RadarChart,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
  Radar,
} from "recharts";

interface StepResultsProps {
  experimentId: number | null;
}

export default function StepResults({ experimentId }: StepResultsProps) {
  const { startIfNew } = useWalkthrough();
  useEffect(() => { startIfNew("results"); }, []); // eslint-disable-line react-hooks/exhaustive-deps
  const [report, setReport] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [sortBy, setSortBy] = useState<string>("overall_score");
  const [sortDir, setSortDir] = useState<"asc" | "desc">("desc");
  const [expandedComboId, setExpandedComboId] = useState<number | null>(null);
  const [expandedQuestionIdx, setExpandedQuestionIdx] = useState<number | null>(null);
  // Failure filter (issue #117): when set, only show Q&A pairs matching this category
  const [failureFilter, setFailureFilter] = useState<string | null>(null);
  // Human ratings (issue #118): Map<combinationId, Map<questionIndex, rating>>
  const [ratingsByCombo, setRatingsByCombo] = useState<Record<number, Record<number, any>>>({});
  const [correlation, setCorrelation] = useState<any>(null);
  const [savingRating, setSavingRating] = useState<string | null>(null);

  useEffect(() => {
    if (experimentId) {
      loadReport();
      loadCorrelation();
    }
  }, [experimentId]);

  const loadReport = async () => {
    if (!experimentId) return;
    try {
      const data = await api.getExperimentReport(experimentId);
      setReport(data);
    } catch (err) {
      console.error("Failed to load report:", err);
    } finally {
      setLoading(false);
    }
  };

  const loadCorrelation = async () => {
    if (!experimentId) return;
    try {
      const c = await api.getExperimentCorrelation(experimentId);
      setCorrelation(c);
    } catch (err) {
      console.error("Failed to load correlation:", err);
    }
  };

  const loadRatingsForCombo = async (combinationId: number) => {
    try {
      const list = await api.listCombinationRatings(combinationId);
      const map: Record<number, any> = {};
      for (const r of list) map[r.question_index] = r;
      setRatingsByCombo((prev) => ({ ...prev, [combinationId]: map }));
    } catch (err) {
      console.error("Failed to load ratings:", err);
    }
  };

  const handleRate = async (
    combinationId: number,
    questionIndex: number,
    rating: "correct" | "incorrect" | "partial",
    questionText?: string
  ) => {
    const key = `${combinationId}:${questionIndex}`;
    setSavingRating(key);
    try {
      const saved = await api.upsertCombinationRating(combinationId, {
        question_index: questionIndex,
        rating,
        question_text: questionText,
      });
      setRatingsByCombo((prev) => ({
        ...prev,
        [combinationId]: { ...(prev[combinationId] || {}), [questionIndex]: saved },
      }));
      // Refresh correlation after each rating
      loadCorrelation();
    } catch (err) {
      console.error("Failed to save rating:", err);
    } finally {
      setSavingRating(null);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20 text-t-secondary">
        Loading report...
      </div>
    );
  }

  if (!report) {
    return (
      <div className="text-center py-20 text-t-secondary">
        No report available. Run experiments first.
      </div>
    );
  }

  const combinations = report.experiment?.combinations || [];
  const completed = combinations.filter((c: any) => c.status === "completed");

  const sorted = [...completed].sort((a: any, b: any) => {
    const aVal = a[sortBy] ?? 0;
    const bVal = b[sortBy] ?? 0;
    return sortDir === "desc" ? bVal - aVal : aVal - bVal;
  });

  const best = report.best_combination;

  const radarData = best
    ? [
        { metric: "Faithfulness", value: (best.faithfulness ?? 0) * 100 },
        { metric: "Answer Relevancy", value: (best.answer_relevancy ?? 0) * 100 },
        { metric: "Context Precision", value: (best.context_precision ?? 0) * 100 },
        { metric: "Context Recall", value: (best.context_recall ?? 0) * 100 },
      ]
    : [];

  const barData = sorted.slice(0, 10).map((c: any, i: number) => ({
    name: `#${i + 1}`,
    score: ((c.overall_score ?? 0) * 100).toFixed(1),
    faithfulness: ((c.faithfulness ?? 0) * 100).toFixed(1),
    relevancy: ((c.answer_relevancy ?? 0) * 100).toFixed(1),
  }));

  // Failure summary aggregated across all completed combinations (issue #117)
  const FAILURE_LABELS: Record<string, { label: string; color: string }> = {
    hallucination: { label: "Hallucination", color: "text-red-400 bg-red-500/10" },
    missing_context: { label: "Missing context", color: "text-amber-400 bg-amber-500/10" },
    irrelevant_retrieval: { label: "Irrelevant retrieval", color: "text-orange-400 bg-orange-500/10" },
    incomplete_answer: { label: "Incomplete answer", color: "text-yellow-400 bg-yellow-500/10" },
    ok: { label: "OK", color: "text-emerald-400 bg-emerald-500/10" },
    unknown: { label: "Unknown", color: "text-t-secondary bg-surface-200/30" },
  };
  const aggregateFailures: Record<string, number> = {};
  for (const c of completed) {
    const fs = (c as any).failure_summary || {};
    for (const [k, v] of Object.entries(fs)) {
      aggregateFailures[k] = (aggregateFailures[k] || 0) + (v as number);
    }
  }
  const totalFailureCount = Object.values(aggregateFailures).reduce((a, b) => a + (b || 0), 0);

  return (
    <div className="space-y-6">
      {/* Best combination */}
      {best && (
        <div className="bg-gradient-to-br from-accent/10 to-secondary/10 rounded-2xl border border-visible p-8" data-walkthrough="results-best">
          <div className="flex items-center gap-3 mb-6">
            <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-amber-400 to-amber-600 flex items-center justify-center">
              <Trophy className="w-6 h-6 text-primary" />
            </div>
            <div>
              <h3 className="text-xl font-bold text-primary">Best Configuration</h3>
              <p className="text-sm text-t-secondary">
                Overall Score:{" "}
                <span className="text-accent font-bold text-lg">
                  {((best.overall_score ?? 0) * 100).toFixed(1)}%
                </span>
              </p>
            </div>
          </div>

          <div className="grid grid-cols-4 lg:grid-cols-7 gap-4 mb-6">
            {[
              { label: "Pipeline", value: best.params.pipeline_type === "graphrag" ? "GraphRAG" : "RAG" },
              { label: "Chunk Size", value: `${best.params.chunk_size} tokens` },
              { label: "Overlap", value: `${best.params.chunk_overlap}%` },
              { label: "Chunking", value: best.params.chunking_strategy || "recursive" },
              { label: "Embedding", value: best.params.embedding_model },
              { label: "Dims", value: best.params.embedding_dimensions || "default" },
              ...(best.params.pipeline_type === "graphrag"
                ? [
                    { label: "Entity Model", value: best.params.entity_extraction_model || "-" },
                    { label: "Gleanings", value: best.params.max_gleanings ?? "-" },
                    { label: "Community Lvl", value: best.params.community_level ?? "-" },
                    { label: "Search Mode", value: best.params.search_mode || "-" },
                  ]
                : [
                    { label: "Top-K", value: best.params.top_k },
                    { label: "Search", value: best.params.search_type },
                    { label: "Distance", value: best.params.distance_metric || "cosine" },
                  ]),
            ].map((item) => (
              <div
                key={item.label}
                className="p-3 bg-surface-100/50 rounded-xl border border-visible text-center"
              >
                <p className="text-[10px] text-t-secondary uppercase tracking-wider mb-1">{item.label}</p>
                <p className="text-sm font-semibold text-primary truncate" title={String(item.value)}>{item.value}</p>
              </div>
            ))}
          </div>

          {/* Radar chart */}
          <div className="h-64" data-walkthrough="results-radar">
            <ResponsiveContainer width="100%" height="100%">
              <RadarChart data={radarData}>
                <PolarGrid stroke="var(--surface-200)" />
                <PolarAngleAxis dataKey="metric" tick={{ fill: "var(--text-secondary)", fontSize: 12 }} />
                <PolarRadiusAxis angle={30} domain={[0, 100]} tick={{ fill: "var(--text-muted)", fontSize: 10 }} />
                <Radar
                  name="Score"
                  dataKey="value"
                  stroke="var(--accent)"
                  fill="var(--accent)"
                  fillOpacity={0.2}
                />
              </RadarChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}

      {/* Bar chart comparison */}
      {barData.length > 0 && (
        <div className="bg-surface-100 rounded-2xl border border-visible p-8">
          <h3 className="text-lg font-semibold text-primary mb-6">Top 10 Configurations</h3>
          <div className="h-72">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={barData}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--surface-200)" />
                <XAxis dataKey="name" tick={{ fill: "var(--text-secondary)", fontSize: 12 }} />
                <YAxis tick={{ fill: "var(--text-secondary)", fontSize: 12 }} domain={[0, 100]} />
                <Tooltip
                  contentStyle={{
                    backgroundColor: "var(--surface-100)",
                    border: "1px solid var(--surface-200)",
                    borderRadius: "12px",
                    color: "var(--text-primary)",
                  }}
                />
                <Legend />
                <Bar dataKey="score" name="Overall" fill="var(--accent)" radius={[4, 4, 0, 0]} />
                <Bar dataKey="faithfulness" name="Faithfulness" fill="var(--secondary)" radius={[4, 4, 0, 0]} />
                <Bar dataKey="relevancy" name="Relevancy" fill="#10b981" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}

      {/* Human feedback correlation (issue #118) */}
      {correlation && correlation.total_ratings > 0 && (
        <div className="bg-surface-100 rounded-2xl border border-visible p-8">
          <div className="flex items-center gap-3 mb-5">
            <div className="w-10 h-10 rounded-xl bg-secondary/15 flex items-center justify-center">
              <MessageSquare className="w-5 h-5 text-secondary" />
            </div>
            <div>
              <h3 className="text-lg font-semibold text-primary">Human ↔ RAGAS correlation</h3>
              <p className="text-xs text-t-secondary">
                {correlation.total_ratings} rating{correlation.total_ratings === 1 ? "" : "s"}
                {Object.entries(correlation.rating_counts || {}).length > 0 && (
                  <>
                    {" — "}
                    {Object.entries(correlation.rating_counts).map(([k, v]) => (
                      <span key={k} className="mr-2">
                        {k}: <span className="text-primary font-medium">{v as number}</span>
                      </span>
                    ))}
                  </>
                )}
              </p>
            </div>
          </div>
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
            {(correlation.metrics || []).map((m: any) => {
              const p = m.pearson;
              const colour =
                p == null
                  ? "text-t-secondary"
                  : p >= 0.6
                  ? "text-emerald-400"
                  : p >= 0.3
                  ? "text-amber-400"
                  : p >= 0
                  ? "text-t-secondary"
                  : "text-red-400";
              return (
                <div
                  key={m.metric}
                  className="p-3 bg-surface-50 rounded-xl border border-visible text-center"
                  title={`Spearman: ${m.spearman != null ? m.spearman.toFixed(3) : "n/a"} (n=${m.n})`}
                >
                  <p className="text-[10px] text-t-secondary uppercase tracking-wider mb-1">
                    {m.metric.replace(/_/g, " ")}
                  </p>
                  <p className={`text-base font-semibold ${colour}`}>
                    {p != null ? p.toFixed(2) : "—"}
                  </p>
                  <p className="text-[10px] text-muted">n={m.n}</p>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Failure distribution (issue #117) */}
      {totalFailureCount > 0 && (
        <div className="bg-surface-100 rounded-2xl border border-visible p-8">
          <div className="flex items-center justify-between mb-5">
            <div>
              <h3 className="text-lg font-semibold text-primary">Failure analysis</h3>
              <p className="text-xs text-t-secondary">
                Distribution across {completed.length} completed combination{completed.length === 1 ? "" : "s"}. Click a category to filter the expanded Q&amp;A view.
              </p>
            </div>
            {experimentId && (
              <a
                href={api.exportExperimentFailuresCSV(experimentId)}
                download
                className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-red-300 bg-red-500/10 border border-red-500/30 rounded-lg hover:bg-red-500/20 transition-colors"
              >
                <Download className="w-3 h-3" />
                Failures CSV
              </a>
            )}
          </div>
          <div className="flex flex-wrap gap-2">
            {Object.entries(aggregateFailures)
              .filter(([, count]) => (count as number) > 0)
              .sort(([a], [b]) => (a === "ok" ? 1 : b === "ok" ? -1 : 0))
              .map(([cat, count]) => {
                const meta = FAILURE_LABELS[cat] || { label: cat, color: "text-t-secondary bg-surface-200/30" };
                const isActive = failureFilter === cat;
                return (
                  <button
                    key={cat}
                    onClick={() => setFailureFilter(isActive ? null : cat)}
                    className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-medium border transition-colors ${meta.color} ${
                      isActive ? "border-accent ring-1 ring-accent/40" : "border-visible"
                    }`}
                    title={`Click to ${isActive ? "clear filter" : "show only this category"}`}
                  >
                    <span>{meta.label}</span>
                    <span className="font-semibold">{count as number}</span>
                  </button>
                );
              })}
            {failureFilter && (
              <button
                onClick={() => setFailureFilter(null)}
                className="px-3 py-1.5 rounded-lg text-xs font-medium border border-visible text-t-secondary hover:text-primary"
              >
                Clear filter
              </button>
            )}
          </div>
        </div>
      )}

      {/* Detailed table */}
      <div className="bg-surface-100 rounded-2xl border border-visible p-8" data-walkthrough="results-table">
        <div className="flex items-center justify-between mb-6">
          <h3 className="text-lg font-semibold text-primary">All Results</h3>
          <div className="flex items-center gap-3">
            <span className="text-sm text-t-secondary">{report.summary.completed} of {report.summary.total_combinations} completed</span>
            {experimentId && (
              <>
                <a
                  href={api.exportExperimentCSV(experimentId)}
                  download
                  className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-accent bg-accent/10 border border-visible rounded-lg hover:bg-accent/20 transition-colors"
                >
                  <Download className="w-3 h-3" />
                  CSV
                </a>
                {correlation && correlation.total_ratings > 0 && (
                  <a
                    href={api.exportRatedQuestionsCSV(experimentId)}
                    download
                    className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-secondary bg-secondary/10 border border-visible rounded-lg hover:bg-secondary/20 transition-colors"
                    title="Export rated Q&A pairs (one row per rating)"
                  >
                    <Download className="w-3 h-3" />
                    Rated CSV
                  </a>
                )}
              </>
            )}
          </div>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-visible">
                {["Rank", "Type", "Chunk", "Overlap", "Chunking", "Embedding", "Dims", "K", "Search", "Dist.", "Faith.", "Relev.", "Prec.", "Recall", "Overall", "Tokens", "Cost", "Avg Lat.", "p95 Lat."].map(
                  (header) => (
                    <th
                      key={header}
                      className="px-3 py-3 text-left text-xs font-medium text-t-secondary uppercase tracking-wider"
                    >
                      {header}
                    </th>
                  )
                )}
              </tr>
            </thead>
            <tbody className="divide-y divide-surface-200/30">
              {sorted.map((combo: any, index: number) => {
                const isExpanded = expandedComboId === combo.id;
                const details: any[] = Array.isArray(combo.detailed_results) ? combo.detailed_results : [];
                return (
                  <React.Fragment key={combo.id}>
                    <tr
                      onClick={() => {
                        const next = isExpanded ? null : combo.id;
                        setExpandedComboId(next);
                        setExpandedQuestionIdx(null);
                        if (next !== null && !ratingsByCombo[next]) {
                          loadRatingsForCombo(next);
                        }
                      }}
                      className={`hover:bg-surface-50 transition-colors cursor-pointer ${
                        index === 0 ? "bg-accent/5" : ""
                      } ${isExpanded ? "bg-surface-50" : ""}`}
                    >
                      <td className="px-3 py-3 text-t-hover">
                        <div className="flex items-center gap-1">
                          {isExpanded ? <ChevronDown className="w-3 h-3 text-t-secondary" /> : <ChevronRight className="w-3 h-3 text-t-secondary" />}
                          {index === 0 ? (
                            <Trophy className="w-4 h-4 text-amber-400" />
                          ) : (
                            `#${index + 1}`
                          )}
                        </div>
                      </td>
                      <td className="px-3 py-3">
                        {combo.params.pipeline_type === "graphrag" ? (
                          <span className="px-1.5 py-0.5 bg-purple-500/10 text-purple-400 rounded text-xs font-medium">GraphRAG</span>
                        ) : (
                          <span className="px-1.5 py-0.5 bg-accent/10 text-accent rounded text-xs font-medium">RAG</span>
                        )}
                      </td>
                      <td className="px-3 py-3 text-primary">{combo.params.chunk_size}</td>
                      <td className="px-3 py-3 text-primary">{combo.params.chunk_overlap}%</td>
                      <td className="px-3 py-3 text-t-secondary text-xs capitalize">{combo.params.chunking_strategy || "recursive"}</td>
                      <td className="px-3 py-3 text-primary text-xs">{combo.params.embedding_model}</td>
                      <td className="px-3 py-3 text-t-secondary text-xs">{combo.params.embedding_dimensions || "default"}</td>
                      <td className="px-3 py-3 text-primary">{combo.params.pipeline_type === "graphrag" ? (combo.params.community_level ?? combo.params.top_k) : combo.params.top_k}</td>
                      <td className="px-3 py-3 text-primary capitalize">{combo.params.pipeline_type === "graphrag" ? (combo.params.search_mode ?? combo.params.search_type) : combo.params.search_type}</td>
                      <td className="px-3 py-3 text-t-secondary text-xs">{combo.params.pipeline_type === "graphrag" ? "-" : (combo.params.distance_metric || "cosine")}</td>
                      <td className="px-3 py-3 text-primary">
                        {combo.faithfulness != null ? `${(combo.faithfulness * 100).toFixed(1)}%` : "-"}
                      </td>
                      <td className="px-3 py-3 text-primary">
                        {combo.answer_relevancy != null ? `${(combo.answer_relevancy * 100).toFixed(1)}%` : "-"}
                      </td>
                      <td className="px-3 py-3 text-primary">
                        {combo.context_precision != null ? `${(combo.context_precision * 100).toFixed(1)}%` : "-"}
                      </td>
                      <td className="px-3 py-3 text-primary">
                        {combo.context_recall != null ? `${(combo.context_recall * 100).toFixed(1)}%` : "-"}
                      </td>
                      <td className="px-3 py-3">
                        <span
                          className={`font-semibold ${
                            (combo.overall_score ?? 0) >= 0.8
                              ? "text-emerald-400"
                              : (combo.overall_score ?? 0) >= 0.6
                              ? "text-amber-400"
                              : "text-red-400"
                          }`}
                        >
                          {combo.overall_score != null ? `${(combo.overall_score * 100).toFixed(1)}%` : "-"}
                        </span>
                      </td>
                      <td className="px-3 py-3 text-t-secondary text-xs">
                        {combo.total_tokens ? (combo.total_tokens >= 1000 ? `${(combo.total_tokens / 1000).toFixed(1)}K` : combo.total_tokens) : "-"}
                      </td>
                      <td className="px-3 py-3 text-amber-400 text-xs">
                        {combo.total_cost ? `$${combo.total_cost < 0.01 ? combo.total_cost.toFixed(4) : combo.total_cost.toFixed(2)}` : "-"}
                      </td>
                      <td className="px-3 py-3 text-t-secondary text-xs">
                        {combo.avg_latency_ms != null ? (combo.avg_latency_ms >= 1000 ? `${(combo.avg_latency_ms / 1000).toFixed(2)}s` : `${Math.round(combo.avg_latency_ms)}ms`) : "-"}
                      </td>
                      <td className="px-3 py-3 text-t-secondary text-xs">
                        {combo.p95_latency_ms != null ? (combo.p95_latency_ms >= 1000 ? `${(combo.p95_latency_ms / 1000).toFixed(2)}s` : `${Math.round(combo.p95_latency_ms)}ms`) : "-"}
                      </td>
                    </tr>
                    {/* Per-question detail */}
                    {isExpanded && details.length > 0 && (() => {
                      const visibleIndexes = details
                        .map((_q: any, qi: number) => qi)
                        .filter((qi: number) => {
                          if (!failureFilter) return true;
                          const cat = (details[qi] as any)?.failure_category || "unknown";
                          return cat === failureFilter;
                        });
                      return (
                      <tr>
                        <td colSpan={19} className="p-0">
                          <div className="bg-surface-50 border-y border-visible px-6 py-4">
                            <h4 className="text-xs font-semibold text-t-secondary uppercase mb-3">
                              Per-Question Results ({visibleIndexes.length} {failureFilter ? `of ${details.length} (filtered)` : "questions"})
                            </h4>
                            {visibleIndexes.length === 0 && (
                              <p className="text-sm text-t-secondary text-center py-4">
                                No questions match the selected failure filter.
                              </p>
                            )}
                            <div className="space-y-2">
                              {visibleIndexes.map((qi: number) => {
                                const q: any = details[qi];
                                const qExpanded = expandedQuestionIdx === qi;
                                const faith = q.faithfulness;
                                const relev = q.answer_relevancy;
                                const prec = q.context_precision;
                                const recall = q.context_recall;
                                const questionText = q.user_input || q.question || "";
                                const currentRating = ratingsByCombo[combo.id]?.[qi]?.rating as
                                  | "correct"
                                  | "incorrect"
                                  | "partial"
                                  | undefined;
                                const ratingKey = `${combo.id}:${qi}`;
                                const ratingSaving = savingRating === ratingKey;
                                const ratingDot =
                                  currentRating === "correct"
                                    ? "bg-emerald-400"
                                    : currentRating === "partial"
                                    ? "bg-amber-400"
                                    : currentRating === "incorrect"
                                    ? "bg-red-400"
                                    : "bg-surface-200";
                                return (
                                  <div key={qi} className="bg-surface-100 rounded-lg border border-visible overflow-hidden">
                                    <button
                                      onClick={(e) => { e.stopPropagation(); setExpandedQuestionIdx(qExpanded ? null : qi); }}
                                      className="w-full flex items-start gap-3 px-4 py-3 text-left hover:bg-surface-50 transition-colors"
                                    >
                                      <span className="text-xs font-mono text-muted mt-0.5">Q{qi + 1}</span>
                                      <span
                                        className={`w-2 h-2 rounded-full mt-1.5 flex-shrink-0 ${ratingDot}`}
                                        title={
                                          currentRating
                                            ? `Human rated: ${currentRating}`
                                            : "Not rated"
                                        }
                                      />
                                      <div className="flex-1 min-w-0">
                                        <p className="text-sm text-primary line-clamp-1">{questionText || "—"}</p>
                                        {(q.failure_category && q.failure_category !== "ok") && (
                                          <span
                                            className={`inline-block mt-1 text-[10px] font-medium px-1.5 py-0.5 rounded ${
                                              FAILURE_LABELS[q.failure_category]?.color || "bg-surface-200/30 text-t-secondary"
                                            }`}
                                          >
                                            {FAILURE_LABELS[q.failure_category]?.label || q.failure_category}
                                          </span>
                                        )}
                                      </div>
                                      <div className="flex items-center gap-3 flex-shrink-0 text-xs">
                                        <span className={faith >= 0.8 ? "text-emerald-400" : faith >= 0.5 ? "text-amber-400" : "text-red-400"}>
                                          F:{(faith * 100).toFixed(0)}%
                                        </span>
                                        <span className={relev >= 0.8 ? "text-emerald-400" : relev >= 0.5 ? "text-amber-400" : "text-red-400"}>
                                          R:{(relev * 100).toFixed(0)}%
                                        </span>
                                        <span className={prec >= 0.8 ? "text-emerald-400" : prec >= 0.5 ? "text-amber-400" : "text-red-400"}>
                                          P:{((prec ?? 0) * 100).toFixed(0)}%
                                        </span>
                                        <span className={recall >= 0.8 ? "text-emerald-400" : recall >= 0.5 ? "text-amber-400" : "text-red-400"}>
                                          C:{((recall ?? 0) * 100).toFixed(0)}%
                                        </span>
                                        {qExpanded ? <ChevronDown className="w-3 h-3 text-muted" /> : <ChevronRight className="w-3 h-3 text-muted" />}
                                      </div>
                                    </button>
                                    {qExpanded && (
                                      <div className="px-4 pb-4 space-y-3 border-t border-visible pt-3">
                                        {/* Human rating buttons (issue #118) */}
                                        <div className="flex items-center gap-2">
                                          <span className="text-xs font-medium text-t-secondary">Your rating:</span>
                                          {(
                                            [
                                              { key: "correct", Icon: Check, label: "Correct", on: "bg-emerald-500/20 text-emerald-300 border-emerald-500/40", off: "text-t-secondary hover:bg-surface-50" },
                                              { key: "partial", Icon: Minus, label: "Partial", on: "bg-amber-500/20 text-amber-300 border-amber-500/40", off: "text-t-secondary hover:bg-surface-50" },
                                              { key: "incorrect", Icon: X, label: "Incorrect", on: "bg-red-500/20 text-red-300 border-red-500/40", off: "text-t-secondary hover:bg-surface-50" },
                                            ] as const
                                          ).map(({ key, Icon, label, on, off }) => {
                                            const active = currentRating === key;
                                            return (
                                              <button
                                                key={key}
                                                disabled={ratingSaving}
                                                onClick={(e) => {
                                                  e.stopPropagation();
                                                  handleRate(combo.id, qi, key, questionText);
                                                }}
                                                className={`flex items-center gap-1 px-2.5 py-1 text-xs font-medium rounded-md border transition-colors ${
                                                  active ? on : `border-visible ${off}`
                                                } ${ratingSaving ? "opacity-50 cursor-wait" : ""}`}
                                                title={`Mark as ${label}`}
                                              >
                                                <Icon className="w-3 h-3" />
                                                {label}
                                              </button>
                                            );
                                          })}
                                        </div>
                                        <div>
                                          <p className="text-xs font-medium text-t-secondary mb-1">Generated Answer</p>
                                          <p className="text-sm text-primary bg-surface-50 rounded-lg px-3 py-2">{q.response || q.answer || "—"}</p>
                                        </div>
                                        <div>
                                          <p className="text-xs font-medium text-t-secondary mb-1">Ground Truth</p>
                                          <p className="text-sm text-primary bg-surface-50 rounded-lg px-3 py-2">{q.reference || q.ground_truth || "—"}</p>
                                        </div>
                                        {(q.retrieved_contexts || q.contexts) && (
                                          <div>
                                            <p className="text-xs font-medium text-t-secondary mb-1">
                                              Retrieved Contexts ({(q.retrieved_contexts || q.contexts || []).length})
                                            </p>
                                            <div className="space-y-1.5">
                                              {(q.retrieved_contexts || q.contexts || []).map((ctx: string, ci: number) => (
                                                <div key={ci} className="text-xs text-t-secondary bg-surface-50 rounded-lg px-3 py-2 border-l-2 border-visible">
                                                  {ctx.length > 500 ? ctx.slice(0, 500) + "..." : ctx}
                                                </div>
                                              ))}
                                            </div>
                                          </div>
                                        )}
                                      </div>
                                    )}
                                  </div>
                                );
                              })}
                            </div>
                          </div>
                        </td>
                      </tr>
                      );
                    })()}
                    {isExpanded && details.length === 0 && (
                      <tr>
                        <td colSpan={19} className="px-6 py-4 text-center text-sm text-muted bg-surface-50">
                          No per-question details available for this combination.
                        </td>
                      </tr>
                    )}
                  </React.Fragment>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
