"use client";

import { useState, useEffect } from "react";
import {
  Clock,
  ChevronDown,
  ChevronRight,
  Trophy,
  CheckCircle,
  XCircle,
  Loader2,
  AlertCircle,
  ArrowLeft,
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

interface HistoryProps {
  onBack: () => void;
}

const statusConfig: Record<string, { icon: any; color: string; label: string }> = {
  completed: { icon: CheckCircle, color: "text-emerald-400", label: "Completed" },
  running: { icon: Loader2, color: "text-blue-400", label: "Running" },
  failed: { icon: XCircle, color: "text-red-400", label: "Failed" },
  pending: { icon: Clock, color: "text-slate-400", label: "Pending" },
  configured: { icon: AlertCircle, color: "text-amber-400", label: "Configured" },
  proposing: { icon: Loader2, color: "text-purple-400", label: "Proposing" },
};

export default function History({ onBack }: HistoryProps) {
  const [experiments, setExperiments] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [expandedId, setExpandedId] = useState<number | null>(null);
  const [expandedReport, setExpandedReport] = useState<any>(null);
  const [loadingReport, setLoadingReport] = useState(false);

  useEffect(() => {
    loadExperiments();
  }, []);

  const loadExperiments = async () => {
    try {
      const data = await api.listExperiments();
      setExperiments(data);
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
      <div className="flex items-center justify-center py-20 text-slate-400">
        <Loader2 className="w-5 h-5 animate-spin mr-2" />
        Loading history...
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-4">
        <button
          onClick={onBack}
          className="p-2 rounded-lg hover:bg-surface-100 text-slate-400 hover:text-white transition-colors"
        >
          <ArrowLeft className="w-5 h-5" />
        </button>
        <div>
          <h2 className="text-2xl font-bold text-white">Pipeline History</h2>
          <p className="text-sm text-slate-400 mt-1">
            {experiments.length} experiment{experiments.length !== 1 ? "s" : ""} recorded
          </p>
        </div>
      </div>

      {experiments.length === 0 ? (
        <div className="text-center py-20">
          <Clock className="w-12 h-12 text-slate-600 mx-auto mb-4" />
          <p className="text-slate-400">No experiments yet. Run your first pipeline to see history here.</p>
        </div>
      ) : (
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
                className="bg-surface-100 rounded-2xl border border-surface-200/50 overflow-hidden"
              >
                {/* Summary row */}
                <button
                  onClick={() => toggleExpand(exp.id)}
                  className="w-full flex items-center gap-4 p-5 hover:bg-surface-50 transition-colors text-left"
                >
                  <div className="flex-shrink-0">
                    {isExpanded ? (
                      <ChevronDown className="w-5 h-5 text-slate-400" />
                    ) : (
                      <ChevronRight className="w-5 h-5 text-slate-400" />
                    )}
                  </div>

                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-3 mb-1">
                      <h3 className="text-white font-semibold truncate">
                        {exp.name}
                      </h3>
                      <span
                        className={`flex items-center gap-1 text-xs px-2 py-0.5 rounded-full ${status.color} bg-surface-200/50`}
                      >
                        <StatusIcon className={`w-3 h-3 ${exp.status === "running" ? "animate-spin" : ""}`} />
                        {status.label}
                      </span>
                    </div>
                    <div className="flex items-center gap-4 text-xs text-slate-400">
                      <span>{formatDate(exp.created_at)}</span>
                      {exp.dataset_name && (
                        <span>Dataset: {exp.dataset_name}</span>
                      )}
                      <span>
                        {completedCount}/{totalCount} combinations
                      </span>
                      <span className="capitalize">{exp.vectorstore_type}</span>
                    </div>
                  </div>

                  {bestScore != null && (
                    <div className="flex-shrink-0 text-right">
                      <p className="text-xs text-slate-400 mb-0.5">Best Score</p>
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
                </button>

                {/* Expanded details */}
                {isExpanded && (
                  <div className="border-t border-surface-200/50 p-6">
                    {loadingReport ? (
                      <div className="flex items-center justify-center py-8 text-slate-400">
                        <Loader2 className="w-5 h-5 animate-spin mr-2" />
                        Loading details...
                      </div>
                    ) : expandedReport ? (
                      <ExpandedReport report={expandedReport} />
                    ) : (
                      <p className="text-slate-400 text-center py-4">
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
    </div>
  );
}

function ExpandedReport({ report }: { report: any }) {
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
        <div className="p-3 bg-surface-50 rounded-xl border border-surface-200/30">
          <p className="text-xs text-slate-400 mb-1">Total</p>
          <p className="text-lg font-bold text-white">{report.summary.total_combinations}</p>
        </div>
        <div className="p-3 bg-surface-50 rounded-xl border border-surface-200/30">
          <p className="text-xs text-slate-400 mb-1">Completed</p>
          <p className="text-lg font-bold text-emerald-400">{report.summary.completed}</p>
        </div>
        <div className="p-3 bg-surface-50 rounded-xl border border-surface-200/30">
          <p className="text-xs text-slate-400 mb-1">Failed</p>
          <p className="text-lg font-bold text-red-400">{report.summary.failed}</p>
        </div>
        <div className="p-3 bg-surface-50 rounded-xl border border-surface-200/30">
          <p className="text-xs text-slate-400 mb-1">Pending</p>
          <p className="text-lg font-bold text-slate-400">{report.summary.pending}</p>
        </div>
      </div>

      {/* Best config */}
      {best && (
        <div className="bg-gradient-to-br from-accent/5 to-secondary/5 rounded-xl border border-accent/20 p-5">
          <div className="flex items-center gap-2 mb-4">
            <Trophy className="w-5 h-5 text-amber-400" />
            <h4 className="text-white font-semibold">Best Configuration</h4>
            <span className="text-accent font-bold ml-auto">
              {((best.overall_score ?? 0) * 100).toFixed(1)}%
            </span>
          </div>

          <div className="grid grid-cols-4 lg:grid-cols-7 gap-3 mb-4">
            {[
              { label: "Chunk Size", value: `${best.params.chunk_size}` },
              { label: "Overlap", value: `${best.params.chunk_overlap}%` },
              { label: "Embedding", value: best.params.embedding_model },
              { label: "Dims", value: best.params.embedding_dimensions || "default" },
              { label: "Top-K", value: best.params.top_k },
              { label: "Search", value: best.params.search_type },
              { label: "Distance", value: best.params.distance_metric || "cosine" },
            ].map((item) => (
              <div key={item.label} className="text-center">
                <p className="text-xs text-slate-400">{item.label}</p>
                <p className="text-sm font-medium text-white">{item.value}</p>
              </div>
            ))}
          </div>

          {/* Radar chart */}
          {radarData.length > 0 && (
            <div className="h-48">
              <ResponsiveContainer width="100%" height="100%">
                <RadarChart data={radarData}>
                  <PolarGrid stroke="#232338" />
                  <PolarAngleAxis
                    dataKey="metric"
                    tick={{ fill: "#94a3b8", fontSize: 11 }}
                  />
                  <PolarRadiusAxis
                    angle={30}
                    domain={[0, 100]}
                    tick={{ fill: "#64748b", fontSize: 9 }}
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
        <div>
          <h4 className="text-sm font-semibold text-white mb-3">Top Configurations</h4>
          <div className="h-48">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={barData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#232338" />
                <XAxis dataKey="name" tick={{ fill: "#94a3b8", fontSize: 11 }} />
                <YAxis tick={{ fill: "#94a3b8", fontSize: 11 }} domain={[0, 100]} />
                <Tooltip
                  contentStyle={{
                    backgroundColor: "#1a1a2e",
                    border: "1px solid #232338",
                    borderRadius: "8px",
                    color: "#e2e8f0",
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
        <div>
          <h4 className="text-sm font-semibold text-white mb-3">All Results</h4>
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b border-surface-200/50">
                  {["#", "Chunk", "Overlap", "Embedding", "Dims", "K", "Search", "Dist.", "Faith.", "Relev.", "Prec.", "Recall", "Score", "Time"].map(
                    (h) => (
                      <th key={h} className="px-2 py-2 text-left text-xs font-medium text-slate-400 uppercase">
                        {h}
                      </th>
                    )
                  )}
                </tr>
              </thead>
              <tbody className="divide-y divide-surface-200/30">
                {completed.map((c: any, i: number) => (
                  <tr
                    key={c.id}
                    className={`hover:bg-surface-50 transition-colors ${i === 0 ? "bg-accent/5" : ""}`}
                  >
                    <td className="px-2 py-2 text-slate-300">
                      {i === 0 ? <Trophy className="w-3.5 h-3.5 text-amber-400 inline" /> : i + 1}
                    </td>
                    <td className="px-2 py-2 text-white">{c.params.chunk_size}</td>
                    <td className="px-2 py-2 text-white">{c.params.chunk_overlap}%</td>
                    <td className="px-2 py-2 text-white truncate max-w-[120px]">{c.params.embedding_model}</td>
                    <td className="px-2 py-2 text-slate-400 text-xs">{c.params.embedding_dimensions || "def"}</td>
                    <td className="px-2 py-2 text-white">{c.params.top_k}</td>
                    <td className="px-2 py-2 text-white capitalize">{c.params.search_type}</td>
                    <td className="px-2 py-2 text-slate-400 text-xs">{c.params.distance_metric || "cos"}</td>
                    <td className="px-2 py-2 text-white">
                      {c.faithfulness != null ? `${(c.faithfulness * 100).toFixed(1)}%` : "-"}
                    </td>
                    <td className="px-2 py-2 text-white">
                      {c.answer_relevancy != null ? `${(c.answer_relevancy * 100).toFixed(1)}%` : "-"}
                    </td>
                    <td className="px-2 py-2 text-white">
                      {c.context_precision != null ? `${(c.context_precision * 100).toFixed(1)}%` : "-"}
                    </td>
                    <td className="px-2 py-2 text-white">
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
                    <td className="px-2 py-2 text-slate-400">
                      {c.duration_seconds != null ? `${c.duration_seconds.toFixed(1)}s` : "-"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
