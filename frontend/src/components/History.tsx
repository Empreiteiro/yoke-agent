"use client";

import React, { useState, useEffect } from "react";
import {
  Clock,
  ChevronDown,
  ChevronRight,
  Trophy,
  CheckCircle,
  XCircle,
  Loader2,
  AlertCircle,
  StopCircle,
  Play,
  RotateCcw,
  Trash2,
  Square,
  Download,
  Database,
  Eye,
} from "lucide-react";
import { api } from "@/lib/api";
import {
  RadarChart,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
  Radar,
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
} from "recharts";



const statusConfig: Record<string, { icon: any; color: string; label: string }> = {
  completed: { icon: CheckCircle, color: "text-emerald-400", label: "Completed" },
  completed_with_errors: { icon: AlertCircle, color: "text-amber-400", label: "Partial" },
  running: { icon: Loader2, color: "text-blue-400", label: "Running" },
  failed: { icon: XCircle, color: "text-red-400", label: "Failed" },
  stopped: { icon: StopCircle, color: "text-orange-400", label: "Stopped" },
  pending: { icon: Clock, color: "text-t-secondary", label: "Pending" },
  configured: { icon: AlertCircle, color: "text-amber-400", label: "Configured" },
  proposing: { icon: Loader2, color: "text-purple-400", label: "Proposing" },
};

export default function History({ onViewResults }: { onViewResults?: (experimentId: number) => void } = {}) {
  const [activeTab, setActiveTab] = useState<"rag" | "agent">("rag");
  const [experiments, setExperiments] = useState<any[]>([]);
  const [agentExperiments, setAgentExperiments] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [expandedId, setExpandedId] = useState<number | null>(null);
  const [expandedReport, setExpandedReport] = useState<any>(null);
  const [loadingReport, setLoadingReport] = useState(false);
  const [resumingId, setResumingId] = useState<number | null>(null);
  const [pollingId, setPollingId] = useState<number | null>(null);
  const [confirmDeleteId, setConfirmDeleteId] = useState<number | null>(null);
  const [stoppingId, setStoppingId] = useState<number | null>(null);
  const [savingCollectionId, setSavingCollectionId] = useState<number | null>(null);

  useEffect(() => {
    loadExperiments();
  }, []);

  const loadExperiments = async () => {
    try {
      const [ragData, agentData] = await Promise.all([
        api.listExperiments(),
        api.listAgentExperiments().catch(() => []),
      ]);
      setExperiments(ragData);
      setAgentExperiments(agentData);
    } catch (err) {
      console.error("Failed to load experiments:", err);
    } finally {
      setLoading(false);
    }
  };

  const toggleExpand = async (id: number) => {
    if (expandedId === id) {
      setExpandedId(null);
      setExpandedReport(null);
      return;
    }
    setExpandedId(id);
    setLoadingReport(true);
    try {
      const report = await api.getExperimentReport(id);
      setExpandedReport(report);
    } catch (err) {
      console.error("Failed to load report:", err);
      setExpandedReport(null);
    } finally {
      setLoadingReport(false);
    }
  };

  const handleResume = async (expId: number, retryFailed: boolean) => {
    setResumingId(expId);
    try {
      await api.resumeExperiment(expId, retryFailed);
      setPollingId(expId);
      const interval = setInterval(async () => {
        try {
          const data = await api.getExperiment(expId);
          setExperiments((prev) =>
            prev.map((e) => (e.id === expId ? data : e))
          );
          if (["completed", "completed_with_errors", "failed", "stopped"].includes(data.status)) {
            clearInterval(interval);
            setPollingId(null);
            setResumingId(null);
          }
        } catch {
          // keep polling
        }
      }, 3000);
    } catch (err) {
      console.error("Failed to resume experiment:", err);
      setResumingId(null);
    }
  };

  const handleDelete = async (expId: number) => {
    try {
      await api.deleteExperiment(expId);
      setExperiments((prev) => prev.filter((e) => e.id !== expId));
      if (expandedId === expId) {
        setExpandedId(null);
        setExpandedReport(null);
      }
    } catch (err) {
      console.error("Failed to delete experiment:", err);
    } finally {
      setConfirmDeleteId(null);
    }
  };

  const handleDownloadReport = async (exp: any) => {
    try {
      const report = await api.getExperimentReport(exp.id);
      const blob = new Blob([JSON.stringify(report, null, 2)], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `${exp.name || "experiment"}-report.json`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      console.error("Failed to download report:", err);
    }
  };

  const handleSaveCollection = async (expId: number) => {
    setSavingCollectionId(expId);
    try {
      await api.saveCollectionFromExperiment(expId);
    } catch (err: any) {
      // 409 = already saved, that's fine
      if (!err.message?.includes("409")) {
        console.error("Failed to save collection:", err);
      }
    } finally {
      setTimeout(() => setSavingCollectionId(null), 2000);
    }
  };

  const handleStop = async (expId: number) => {
    setStoppingId(expId);
    try {
      await api.stopExperiment(expId);
      const data = await api.getExperiment(expId);
      setExperiments((prev) => prev.map((e) => (e.id === expId ? data : e)));
    } catch (err) {
      console.error("Failed to stop experiment:", err);
    } finally {
      setStoppingId(null);
    }
  };

  const getBestScore = (exp: any) => {
    const completed = (exp.combinations || []).filter(
      (c: any) => c.status === "completed" && c.overall_score != null
    );
    if (completed.length === 0) return null;
    return Math.max(...completed.map((c: any) => c.overall_score));
  };

  const formatDate = (dateStr: string) => {
    return new Date(dateStr).toLocaleDateString("en-US", {
      month: "short",
      day: "numeric",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20 text-t-secondary">
        <Loader2 className="w-5 h-5 animate-spin mr-2" />
        Loading history...
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h2 className="text-2xl font-bold text-primary">Experiment History</h2>
        <p className="text-sm text-t-secondary mt-1">
          {experiments.length + agentExperiments.length} experiment{(experiments.length + agentExperiments.length) !== 1 ? "s" : ""} recorded
        </p>
      </div>

      {/* Pipeline tabs */}
      <div className="flex gap-2">
        <button
          onClick={() => setActiveTab("rag")}
          className={`flex-1 px-4 py-2 rounded-lg text-sm font-medium border transition-colors flex items-center justify-center gap-2 ${
            activeTab === "rag"
              ? "bg-accent/20 border-accent text-accent"
              : "bg-surface-100 border-surface-200/50 text-t-secondary hover:text-primary"
          }`}
        >
          RAG Optimization
          {experiments.length > 0 && (
            <span className={`px-1.5 py-0.5 rounded-full text-xs ${activeTab === "rag" ? "bg-accent/30" : "bg-surface-200/50"}`}>
              {experiments.length}
            </span>
          )}
        </button>
        <button
          onClick={() => setActiveTab("agent")}
          className={`flex-1 px-4 py-2 rounded-lg text-sm font-medium border transition-colors flex items-center justify-center gap-2 ${
            activeTab === "agent"
              ? "bg-accent/20 border-accent text-accent"
              : "bg-surface-100 border-surface-200/50 text-t-secondary hover:text-primary"
          }`}
        >
          Agent Evaluation
          {agentExperiments.length > 0 && (
            <span className={`px-1.5 py-0.5 rounded-full text-xs ${activeTab === "agent" ? "bg-accent/30" : "bg-surface-200/50"}`}>
              {agentExperiments.length}
            </span>
          )}
        </button>
      </div>

      {/* Agent experiments tab */}
      {activeTab === "agent" && (
        agentExperiments.length === 0 ? (
          <div className="text-center py-20">
            <Clock className="w-12 h-12 text-muted mx-auto mb-4" />
            <p className="text-t-secondary">No agent experiments yet. Run your first agent evaluation to see history here.</p>
          </div>
        ) : (
          <div className="space-y-3">
            {agentExperiments.map((exp: any) => {
              const status = statusConfig[exp.status] || statusConfig.pending;
              const StatusIcon = status.icon;
              return (
                <div
                  key={exp.id}
                  className="bg-surface-100 rounded-xl border border-surface-200/50 p-4"
                >
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3">
                      <div className={`w-8 h-8 rounded-lg flex items-center justify-center ${
                        exp.status === "completed" ? "bg-emerald-500/20" : "bg-surface-200/50"
                      }`}>
                        <StatusIcon className={`w-4 h-4 ${status.color} ${exp.status === "running" ? "animate-spin" : ""}`} />
                      </div>
                      <div>
                        <h3 className="text-sm font-semibold text-primary">{exp.name}</h3>
                        <p className="text-xs text-t-secondary">
                          {formatDate(exp.created_at)} · {exp.combination_count || 0} combinations
                        </p>
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      <span className={`px-2 py-1 rounded-full text-xs font-medium ${status.color} bg-surface-200/30`}>
                        {status.label}
                      </span>
                    </div>
                  </div>
                  {exp.description && (
                    <p className="text-xs text-t-secondary mt-2 ml-11">{exp.description}</p>
                  )}
                </div>
              );
            })}
          </div>
        )
      )}

      {/* RAG experiments tab */}
      {activeTab === "rag" && experiments.length === 0 && (
        <div className="text-center py-20">
          <Clock className="w-12 h-12 text-muted mx-auto mb-4" />
          <p className="text-t-secondary">No experiments yet. Run your first pipeline to see history here.</p>
        </div>
      )}
      {activeTab === "rag" && experiments.length > 0 && (
        <div className="space-y-3">
          {experiments.map((exp) => {
            const status = statusConfig[exp.status] || statusConfig.pending;
            const StatusIcon = status.icon;
            const bestScore = getBestScore(exp);
            const completedCount = (exp.combinations || []).filter(
              (c: any) => c.status === "completed"
            ).length;
            const totalCount = (exp.combinations || []).length;
            const isExpanded = expandedId === exp.id;

            return (
              <div
                key={exp.id}
                className="bg-surface-100 rounded-2xl border border-visible overflow-hidden"
              >
                {/* Summary row */}
                <button
                  onClick={() => toggleExpand(exp.id)}
                  className="w-full flex items-center gap-4 p-5 hover:bg-surface-50 transition-colors text-left"
                >
                  <div className="flex-shrink-0">
                    {isExpanded ? (
                      <ChevronDown className="w-5 h-5 text-t-secondary" />
                    ) : (
                      <ChevronRight className="w-5 h-5 text-t-secondary" />
                    )}
                  </div>

                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-3 mb-1">
                      <h3 className="text-primary font-semibold truncate">
                        {exp.name}
                      </h3>
                      <span
                        className={`flex items-center gap-1 text-xs px-2 py-0.5 rounded-full ${status.color} bg-surface-200/50`}
                      >
                        <StatusIcon className={`w-3 h-3 ${exp.status === "running" ? "animate-spin" : ""}`} />
                        {status.label}
                      </span>
                    </div>
                    <div className="flex items-center gap-4 text-xs text-t-secondary">
                      <span>{formatDate(exp.created_at)}</span>
                      {exp.dataset_name && (
                        <span>
                          Dataset: {exp.dataset_name}
                          {exp.dataset_questions > 0 && ` (${exp.dataset_questions} questions)`}
                        </span>
                      )}
                      <span>
                        {completedCount}/{totalCount} combinations
                      </span>
                      <span className="capitalize">{exp.vectorstore_type}</span>
                    </div>
                  </div>

                  {bestScore != null && (
                    <div className="flex-shrink-0 text-right">
                      <p className="text-xs text-t-secondary mb-0.5">Best Score</p>
                      <p
                        className={`text-lg font-bold ${
                          bestScore >= 0.8
                            ? "text-emerald-400"
                            : bestScore >= 0.6
                            ? "text-amber-400"
                            : "text-red-400"
                        }`}
                      >
                        {(bestScore * 100).toFixed(1)}%
                      </p>
                    </div>
                  )}

                  {/* Action buttons */}
                  {(() => {
                    const combos = exp.combinations || [];
                    const stoppedCount = combos.filter((c: any) => c.status === "stopped").length;
                    const failedCount = combos.filter((c: any) => c.status === "failed").length;
                    const stuckCount = combos.filter((c: any) => c.status === "running").length;
                    const resumableCount = stoppedCount + stuckCount;
                    const incompleteCount = stoppedCount + failedCount + stuckCount;
                    const canResume = incompleteCount > 0 && exp.status !== "running";
                    const isRunning = exp.status === "running";
                    const isResuming = resumingId === exp.id || pollingId === exp.id;

                    return (
                      <div className="flex items-center gap-1 flex-shrink-0" onClick={(e) => e.stopPropagation()}>
                        {/* View Results */}
                        {onViewResults && completedCount > 0 && (
                          <button
                            onClick={() => onViewResults(exp.id)}
                            className="p-1.5 rounded-lg text-muted hover:text-accent hover:bg-accent/10 transition-colors"
                            title="View results"
                          >
                            <Eye className="w-3.5 h-3.5" />
                          </button>
                        )}

                        {/* Resume / Retry — always visible, disabled when nothing to resume */}
                        {isResuming ? (
                          <span className="p-1.5">
                            <Loader2 className="w-3.5 h-3.5 text-accent animate-spin" />
                          </span>
                        ) : (
                          <button
                            onClick={() => canResume ? handleResume(exp.id, false) : undefined}
                            disabled={!canResume || isRunning}
                            className={`p-1.5 rounded-lg transition-colors ${
                              canResume && !isRunning
                                ? "text-accent hover:bg-accent/10"
                                : "text-muted/30 cursor-not-allowed"
                            }`}
                            title={
                              isRunning ? "Experiment is running"
                                : canResume
                                  ? resumableCount > 0 ? `Resume (${resumableCount} pending)` : "Resume"
                                  : "No pending combinations"
                            }
                          >
                            <Play className="w-3.5 h-3.5" />
                          </button>
                        )}

                        {/* Retry failed */}
                        {failedCount > 0 && !isRunning && !isResuming && (
                          <button
                            onClick={() => handleResume(exp.id, true)}
                            className="p-1.5 rounded-lg text-orange-400 hover:bg-orange-500/10 transition-colors"
                            title={`Retry failed (${failedCount})`}
                          >
                            <RotateCcw className="w-3.5 h-3.5" />
                          </button>
                        )}

                        {/* Stop (only when running) */}
                        {isRunning && (
                          <button
                            onClick={() => handleStop(exp.id)}
                            disabled={stoppingId === exp.id}
                            className="p-1.5 rounded-lg text-red-400 hover:bg-red-500/10 transition-colors"
                            title="Stop experiment"
                          >
                            {stoppingId === exp.id ? (
                              <Loader2 className="w-3.5 h-3.5 animate-spin" />
                            ) : (
                              <Square className="w-3.5 h-3.5" />
                            )}
                          </button>
                        )}

                        {/* Save collection + Download report */}
                        {completedCount > 0 && (
                          <>
                            <button
                              onClick={() => handleSaveCollection(exp.id)}
                              disabled={savingCollectionId === exp.id}
                              className="p-1.5 rounded-lg text-muted hover:text-secondary hover:bg-secondary/10 transition-colors disabled:opacity-50"
                              title="Save winning collection"
                            >
                              {savingCollectionId === exp.id ? (
                                <Loader2 className="w-3.5 h-3.5 animate-spin text-secondary" />
                              ) : (
                                <Database className="w-3.5 h-3.5" />
                              )}
                            </button>
                            <button
                              onClick={() => handleDownloadReport(exp)}
                              className="p-1.5 rounded-lg text-muted hover:text-accent hover:bg-accent/10 transition-colors"
                              title="Download report"
                            >
                              <Download className="w-3.5 h-3.5" />
                            </button>
                          </>
                        )}

                        {/* Delete */}
                        <button
                          onClick={() => { if (!isRunning) setConfirmDeleteId(exp.id); }}
                          className={`p-1.5 rounded-lg transition-colors ${
                            isRunning
                              ? "text-muted/30 cursor-not-allowed"
                              : "text-muted hover:text-red-400 hover:bg-red-500/10"
                          }`}
                          title={isRunning ? "Stop first" : "Delete"}
                          disabled={isRunning}
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      </div>
                    );
                  })()}
                </button>

                {/* Expanded details */}
                {isExpanded && (
                  <div className="border-t border-visible p-6">
                    {loadingReport ? (
                      <div className="flex items-center justify-center py-8 text-t-secondary">
                        <Loader2 className="w-5 h-5 animate-spin mr-2" />
                        Loading details...
                      </div>
                    ) : expandedReport ? (
                      <ExpandedReport report={expandedReport} />
                    ) : (
                      <p className="text-t-secondary text-center py-4">
                        Failed to load report details.
                      </p>
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}

      {/* Delete confirmation modal */}
      {confirmDeleteId && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
          <div className="bg-surface-100 border border-visible rounded-2xl p-6 max-w-sm w-full mx-4 shadow-xl">
            <h3 className="text-primary font-semibold mb-2">Delete experiment?</h3>
            <p className="text-sm text-t-secondary mb-5">
              This will permanently remove the experiment and all its results. This action cannot be undone.
            </p>
            <div className="flex justify-end gap-3">
              <button
                onClick={() => setConfirmDeleteId(null)}
                className="px-4 py-2 text-sm text-t-secondary hover:text-primary bg-surface-200 rounded-lg transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={() => handleDelete(confirmDeleteId)}
                className="px-4 py-2 text-sm text-white bg-red-500 hover:bg-red-600 rounded-lg transition-colors"
              >
                Delete
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function ExpandedReport({ report }: { report: any }) {
  const [expandedComboId, setExpandedComboId] = useState<number | null>(null);
  const [expandedQuestionIdx, setExpandedQuestionIdx] = useState<number | null>(null);

  const best = report.best_combination;
  const combinations = report.experiment?.combinations || [];
  const completed = combinations
    .filter((c: any) => c.status === "completed" && c.overall_score != null)
    .sort((a: any, b: any) => (b.overall_score ?? 0) - (a.overall_score ?? 0));

  const radarData = best
    ? [
        { metric: "Faithfulness", value: (best.faithfulness ?? 0) * 100 },
        { metric: "Relevancy", value: (best.answer_relevancy ?? 0) * 100 },
        { metric: "Precision", value: (best.context_precision ?? 0) * 100 },
        { metric: "Recall", value: (best.context_recall ?? 0) * 100 },
      ]
    : [];

  const barData = completed.slice(0, 8).map((c: any, i: number) => ({
    name: `#${i + 1}`,
    score: ((c.overall_score ?? 0) * 100).toFixed(1),
    faithfulness: ((c.faithfulness ?? 0) * 100).toFixed(1),
    relevancy: ((c.answer_relevancy ?? 0) * 100).toFixed(1),
  }));

  return (
    <div className="space-y-6">
      {/* Summary stats */}
      <div className="grid grid-cols-4 gap-4">
        <div className="p-3 bg-surface-50 rounded-xl border border-visible">
          <p className="text-xs text-t-secondary mb-1">Total</p>
          <p className="text-lg font-bold text-primary">{report.summary.total_combinations}</p>
        </div>
        <div className="p-3 bg-surface-50 rounded-xl border border-visible">
          <p className="text-xs text-t-secondary mb-1">Completed</p>
          <p className="text-lg font-bold text-emerald-400">{report.summary.completed}</p>
        </div>
        <div className="p-3 bg-surface-50 rounded-xl border border-visible">
          <p className="text-xs text-t-secondary mb-1">Failed</p>
          <p className="text-lg font-bold text-red-400">{report.summary.failed}</p>
        </div>
        <div className="p-3 bg-surface-50 rounded-xl border border-visible">
          <p className="text-xs text-t-secondary mb-1">Pending</p>
          <p className="text-lg font-bold text-t-secondary">{report.summary.pending}</p>
        </div>
      </div>

      {/* Best config */}
      {best && (
        <div className="bg-gradient-to-br from-accent/5 to-secondary/5 rounded-xl border border-visible p-5">
          <div className="flex items-center gap-2 mb-4">
            <Trophy className="w-5 h-5 text-amber-400" />
            <h4 className="text-primary font-semibold">Best Configuration</h4>
          </div>

          <div className="grid grid-cols-4 lg:grid-cols-7 gap-3 mb-4">
            {[
              { label: "Pipeline", value: best.params.pipeline_type === "graphrag" ? "GraphRAG" : "RAG" },
              { label: "Chunk Size", value: `${best.params.chunk_size}` },
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
              <div key={item.label} className="text-center p-2.5 rounded-lg border border-visible">
                <p className="text-[10px] text-t-secondary uppercase tracking-wider mb-1">{item.label}</p>
                <p className="text-sm font-semibold text-primary truncate" title={String(item.value)}>{item.value}</p>
              </div>
            ))}
          </div>

          {/* Radar chart */}
          {radarData.length > 0 && (
            <div className="h-48">
              <ResponsiveContainer width="100%" height="100%">
                <RadarChart data={radarData}>
                  <PolarGrid stroke="var(--border)" />
                  <PolarAngleAxis
                    dataKey="metric"
                    tick={{ fill: "var(--text-secondary)", fontSize: 11 }}
                  />
                  <PolarRadiusAxis
                    angle={30}
                    domain={[0, 100]}
                    tick={{ fill: "var(--text-muted)", fontSize: 9 }}
                  />
                  <Radar
                    name="Score"
                    dataKey="value"
                    stroke="#8b5cf6"
                    fill="#8b5cf6"
                    fillOpacity={0.2}
                  />
                </RadarChart>
              </ResponsiveContainer>
            </div>
          )}
        </div>
      )}

      {/* Bar chart */}
      {barData.length > 1 && (
        <div className="rounded-xl border border-visible p-5">
          <h4 className="text-sm font-semibold text-primary mb-3">Top Configurations</h4>
          <div className="h-48">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={barData}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
                <XAxis dataKey="name" tick={{ fill: "var(--text-secondary)", fontSize: 11 }} />
                <YAxis tick={{ fill: "var(--text-secondary)", fontSize: 11 }} domain={[0, 100]} />
                <Tooltip
                  contentStyle={{
                    backgroundColor: "var(--surface-100)",
                    border: "1px solid var(--surface-200)",
                    borderRadius: "8px",
                    color: "var(--text-primary)",
                    fontSize: 12,
                  }}
                />
                <Legend wrapperStyle={{ fontSize: 11 }} />
                <Bar dataKey="score" name="Overall" fill="#8b5cf6" radius={[3, 3, 0, 0]} />
                <Bar dataKey="faithfulness" name="Faithfulness" fill="#06b6d4" radius={[3, 3, 0, 0]} />
                <Bar dataKey="relevancy" name="Relevancy" fill="#10b981" radius={[3, 3, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}

      {/* Results table */}
      {completed.length > 0 && (
        <div className="rounded-xl border border-visible p-5">
          <h4 className="text-sm font-semibold text-primary mb-3">All Results</h4>
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b border-visible">
                  {["#", "Type", "Chunk", "Overlap", "Chunking", "Embedding", "Dims", "K", "Search", "Dist.", "Faith.", "Relev.", "Prec.", "Recall", "Score", "Tokens", "Cost"].map(
                    (h) => (
                      <th key={h} className="px-2 py-2 text-left text-xs font-medium text-t-secondary uppercase">
                        {h}
                      </th>
                    )
                  )}
                </tr>
              </thead>
              <tbody className="divide-y divide-surface-200/30">
                {completed.map((c: any, i: number) => {
                  const isExpanded = expandedComboId === c.id;
                  const details: any[] = Array.isArray(c.detailed_results) ? c.detailed_results : [];
                  return (
                    <React.Fragment key={c.id}>
                      <tr
                        onClick={() => { setExpandedComboId(isExpanded ? null : c.id); setExpandedQuestionIdx(null); }}
                        className={`hover:bg-surface-50 transition-colors cursor-pointer ${i === 0 ? "bg-accent/5" : ""} ${isExpanded ? "bg-surface-50" : ""}`}
                      >
                        <td className="px-2 py-2 text-t-secondary">
                          <div className="flex items-center gap-1">
                            {isExpanded ? <ChevronDown className="w-3 h-3 text-t-secondary" /> : <ChevronRight className="w-3 h-3 text-t-secondary" />}
                            {i === 0 ? <Trophy className="w-3.5 h-3.5 text-amber-400" /> : i + 1}
                          </div>
                        </td>
                        <td className="px-2 py-2">
                          {c.params.pipeline_type === "graphrag" ? (
                            <span className="px-1.5 py-0.5 bg-purple-500/10 text-purple-400 rounded text-[10px] font-medium">GraphRAG</span>
                          ) : (
                            <span className="px-1.5 py-0.5 bg-accent/10 text-accent rounded text-[10px] font-medium">RAG</span>
                          )}
                        </td>
                        <td className="px-2 py-2 text-primary">{c.params.chunk_size}</td>
                        <td className="px-2 py-2 text-primary">{c.params.chunk_overlap}%</td>
                        <td className="px-2 py-2 text-t-secondary text-xs capitalize">{c.params.chunking_strategy || "recursive"}</td>
                        <td className="px-2 py-2 text-primary truncate max-w-[120px]">{c.params.embedding_model}</td>
                        <td className="px-2 py-2 text-t-secondary text-xs">{c.params.embedding_dimensions || "def"}</td>
                        <td className="px-2 py-2 text-primary">{c.params.pipeline_type === "graphrag" ? (c.params.community_level ?? c.params.top_k) : c.params.top_k}</td>
                        <td className="px-2 py-2 text-primary capitalize">{c.params.pipeline_type === "graphrag" ? (c.params.search_mode ?? c.params.search_type) : c.params.search_type}</td>
                        <td className="px-2 py-2 text-t-secondary text-xs">{c.params.pipeline_type === "graphrag" ? "-" : (c.params.distance_metric || "cos")}</td>
                        <td className="px-2 py-2 text-primary">
                          {c.faithfulness != null ? `${(c.faithfulness * 100).toFixed(1)}%` : "-"}
                        </td>
                        <td className="px-2 py-2 text-primary">
                          {c.answer_relevancy != null ? `${(c.answer_relevancy * 100).toFixed(1)}%` : "-"}
                        </td>
                        <td className="px-2 py-2 text-primary">
                          {c.context_precision != null ? `${(c.context_precision * 100).toFixed(1)}%` : "-"}
                        </td>
                        <td className="px-2 py-2 text-primary">
                          {c.context_recall != null ? `${(c.context_recall * 100).toFixed(1)}%` : "-"}
                        </td>
                        <td className="px-2 py-2">
                          <span
                            className={`font-semibold ${
                              (c.overall_score ?? 0) >= 0.8
                                ? "text-emerald-400"
                                : (c.overall_score ?? 0) >= 0.6
                                ? "text-amber-400"
                                : "text-red-400"
                            }`}
                          >
                            {c.overall_score != null ? `${(c.overall_score * 100).toFixed(1)}%` : "-"}
                          </span>
                        </td>
                        <td className="px-2 py-2 text-t-secondary text-xs">
                          {c.total_tokens ? (c.total_tokens >= 1000 ? `${(c.total_tokens / 1000).toFixed(1)}K` : c.total_tokens) : "-"}
                        </td>
                        <td className="px-2 py-2 text-amber-400 text-xs">
                          {c.total_cost ? `$${c.total_cost < 0.01 ? c.total_cost.toFixed(4) : c.total_cost.toFixed(2)}` : "-"}
                        </td>
                      </tr>
                      {isExpanded && details.length > 0 && (
                        <tr>
                          <td colSpan={17} className="p-0">
                            <div className="bg-surface-50 border-y border-visible px-4 py-3">
                              <h4 className="text-xs font-semibold text-t-secondary uppercase mb-2">
                                Per-Question Results ({details.length})
                              </h4>
                              <div className="space-y-1.5">
                                {details.map((q: any, qi: number) => {
                                  const qExpanded = expandedQuestionIdx === qi;
                                  const faith = q.faithfulness ?? 0;
                                  const relev = q.answer_relevancy ?? 0;
                                  const prec = q.context_precision ?? 0;
                                  const recall = q.context_recall ?? 0;
                                  return (
                                    <div key={qi} className="bg-surface-100 rounded-lg border border-visible overflow-hidden">
                                      <button
                                        onClick={(e) => { e.stopPropagation(); setExpandedQuestionIdx(qExpanded ? null : qi); }}
                                        className="w-full flex items-start gap-2 px-3 py-2 text-left hover:bg-surface-50 transition-colors"
                                      >
                                        <span className="text-xs font-mono text-muted mt-0.5">Q{qi + 1}</span>
                                        <p className="flex-1 text-xs text-primary line-clamp-1">{q.user_input || q.question || "—"}</p>
                                        <div className="flex items-center gap-2 flex-shrink-0 text-[10px]">
                                          <span className={faith >= 0.8 ? "text-emerald-400" : faith >= 0.5 ? "text-amber-400" : "text-red-400"}>F:{(faith * 100).toFixed(0)}%</span>
                                          <span className={relev >= 0.8 ? "text-emerald-400" : relev >= 0.5 ? "text-amber-400" : "text-red-400"}>R:{(relev * 100).toFixed(0)}%</span>
                                          <span className={prec >= 0.8 ? "text-emerald-400" : prec >= 0.5 ? "text-amber-400" : "text-red-400"}>P:{(prec * 100).toFixed(0)}%</span>
                                          <span className={recall >= 0.8 ? "text-emerald-400" : recall >= 0.5 ? "text-amber-400" : "text-red-400"}>C:{(recall * 100).toFixed(0)}%</span>
                                          {qExpanded ? <ChevronDown className="w-2.5 h-2.5 text-muted" /> : <ChevronRight className="w-2.5 h-2.5 text-muted" />}
                                        </div>
                                      </button>
                                      {qExpanded && (
                                        <div className="px-3 pb-3 space-y-2 border-t border-visible pt-2">
                                          <div>
                                            <p className="text-[10px] font-medium text-t-secondary mb-0.5">Generated Answer</p>
                                            <p className="text-xs text-primary bg-surface-50 rounded px-2 py-1.5">{q.response || q.answer || "—"}</p>
                                          </div>
                                          <div>
                                            <p className="text-[10px] font-medium text-t-secondary mb-0.5">Ground Truth</p>
                                            <p className="text-xs text-primary bg-surface-50 rounded px-2 py-1.5">{q.reference || q.ground_truth || "—"}</p>
                                          </div>
                                          {(q.retrieved_contexts || q.contexts) && (
                                            <div>
                                              <p className="text-[10px] font-medium text-t-secondary mb-0.5">Retrieved Contexts ({(q.retrieved_contexts || q.contexts || []).length})</p>
                                              <div className="space-y-1">
                                                {(q.retrieved_contexts || q.contexts || []).map((ctx: string, ci: number) => (
                                                  <div key={ci} className="text-[10px] text-t-secondary bg-surface-50 rounded px-2 py-1.5 border-l-2 border-visible">
                                                    {ctx.length > 400 ? ctx.slice(0, 400) + "..." : ctx}
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
                          <td colSpan={17} className="px-4 py-3 text-center text-xs text-muted bg-surface-50">
                            No per-question details available.
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
      )}
    </div>
  );
}
