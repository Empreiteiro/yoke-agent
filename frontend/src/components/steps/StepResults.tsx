"use client";

import React, { useState, useEffect } from "react";
import { BarChart3, Trophy, Download, ArrowUpDown, ChevronDown, ChevronRight, Eye } from "lucide-react";
import { api } from "@/lib/api";
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
  const [report, setReport] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [sortBy, setSortBy] = useState<string>("overall_score");
  const [sortDir, setSortDir] = useState<"asc" | "desc">("desc");
  const [expandedComboId, setExpandedComboId] = useState<number | null>(null);
  const [expandedQuestionIdx, setExpandedQuestionIdx] = useState<number | null>(null);

  useEffect(() => {
    if (experimentId) loadReport();
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

  return (
    <div className="space-y-6">
      {/* Best combination */}
      {best && (
        <div className="bg-gradient-to-br from-accent/10 to-secondary/10 rounded-2xl border border-accent/20 p-8">
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
                className="p-3 bg-surface-100/50 rounded-xl border border-surface-200/30"
              >
                <p className="text-xs text-t-secondary mb-1">{item.label}</p>
                <p className="text-sm font-semibold text-primary">{item.value}</p>
              </div>
            ))}
          </div>

          {/* Radar chart */}
          <div className="h-64">
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
        <div className="bg-surface-100 rounded-2xl border border-surface-200/50 p-8">
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

      {/* Detailed table */}
      <div className="bg-surface-100 rounded-2xl border border-surface-200/50 p-8">
        <div className="flex items-center justify-between mb-6">
          <h3 className="text-lg font-semibold text-primary">All Results</h3>
          <div className="flex items-center gap-3">
            <span className="text-sm text-t-secondary">{report.summary.completed} of {report.summary.total_combinations} completed</span>
            {experimentId && (
              <a
                href={api.exportExperimentCSV(experimentId)}
                download
                className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-accent bg-accent/10 border border-accent/20 rounded-lg hover:bg-accent/20 transition-colors"
              >
                <Download className="w-3 h-3" />
                CSV
              </a>
            )}
          </div>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-surface-200/50">
                {["Rank", "Type", "Chunk", "Overlap", "Chunking", "Embedding", "Dims", "K", "Search", "Dist.", "Faith.", "Relev.", "Prec.", "Recall", "Overall", "Tokens", "Cost"].map(
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
                        setExpandedComboId(isExpanded ? null : combo.id);
                        setExpandedQuestionIdx(null);
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
                    </tr>
                    {/* Per-question detail */}
                    {isExpanded && details.length > 0 && (
                      <tr>
                        <td colSpan={17} className="p-0">
                          <div className="bg-surface-50 border-y border-surface-200/30 px-6 py-4">
                            <h4 className="text-xs font-semibold text-t-secondary uppercase mb-3">
                              Per-Question Results ({details.length} questions)
                            </h4>
                            <div className="space-y-2">
                              {details.map((q: any, qi: number) => {
                                const qExpanded = expandedQuestionIdx === qi;
                                const faith = q.faithfulness;
                                const relev = q.answer_relevancy;
                                const prec = q.context_precision;
                                const recall = q.context_recall;
                                return (
                                  <div key={qi} className="bg-surface-100 rounded-lg border border-surface-200/30 overflow-hidden">
                                    <button
                                      onClick={(e) => { e.stopPropagation(); setExpandedQuestionIdx(qExpanded ? null : qi); }}
                                      className="w-full flex items-start gap-3 px-4 py-3 text-left hover:bg-surface-50 transition-colors"
                                    >
                                      <span className="text-xs font-mono text-muted mt-0.5">Q{qi + 1}</span>
                                      <div className="flex-1 min-w-0">
                                        <p className="text-sm text-primary line-clamp-1">{q.user_input || q.question || "—"}</p>
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
                                      <div className="px-4 pb-4 space-y-3 border-t border-surface-200/30 pt-3">
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
                                                <div key={ci} className="text-xs text-t-secondary bg-surface-50 rounded-lg px-3 py-2 border-l-2 border-accent/20">
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
                    )}
                    {isExpanded && details.length === 0 && (
                      <tr>
                        <td colSpan={17} className="px-6 py-4 text-center text-sm text-muted bg-surface-50">
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
