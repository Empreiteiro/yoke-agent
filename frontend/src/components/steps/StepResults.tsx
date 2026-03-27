"use client";

import { useState, useEffect } from "react";
import { BarChart3, Trophy, Download, ArrowUpDown } from "lucide-react";
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
      <div className="flex items-center justify-center py-20 text-slate-400">
        Loading report...
      </div>
    );
  }

  if (!report) {
    return (
      <div className="text-center py-20 text-slate-400">
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
              <Trophy className="w-6 h-6 text-white" />
            </div>
            <div>
              <h3 className="text-xl font-bold text-white">Best Configuration</h3>
              <p className="text-sm text-slate-400">
                Overall Score:{" "}
                <span className="text-accent font-bold text-lg">
                  {((best.overall_score ?? 0) * 100).toFixed(1)}%
                </span>
              </p>
            </div>
          </div>

          <div className="grid grid-cols-5 gap-4 mb-6">
            {[
              { label: "Chunk Size", value: `${best.params.chunk_size} tokens` },
              { label: "Overlap", value: `${best.params.chunk_overlap}%` },
              { label: "Embedding", value: best.params.embedding_model },
              { label: "Top-K", value: best.params.top_k },
              { label: "Search", value: best.params.search_type },
            ].map((item) => (
              <div
                key={item.label}
                className="p-3 bg-surface-100/50 rounded-xl border border-surface-200/30"
              >
                <p className="text-xs text-slate-400 mb-1">{item.label}</p>
                <p className="text-sm font-semibold text-white">{item.value}</p>
              </div>
            ))}
          </div>

          {/* Radar chart */}
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <RadarChart data={radarData}>
                <PolarGrid stroke="#232338" />
                <PolarAngleAxis dataKey="metric" tick={{ fill: "#94a3b8", fontSize: 12 }} />
                <PolarRadiusAxis angle={30} domain={[0, 100]} tick={{ fill: "#64748b", fontSize: 10 }} />
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
        </div>
      )}

      {/* Bar chart comparison */}
      {barData.length > 0 && (
        <div className="bg-surface-100 rounded-2xl border border-surface-200/50 p-8">
          <h3 className="text-lg font-semibold text-white mb-6">Top 10 Configurations</h3>
          <div className="h-72">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={barData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#232338" />
                <XAxis dataKey="name" tick={{ fill: "#94a3b8", fontSize: 12 }} />
                <YAxis tick={{ fill: "#94a3b8", fontSize: 12 }} domain={[0, 100]} />
                <Tooltip
                  contentStyle={{
                    backgroundColor: "#1a1a2e",
                    border: "1px solid #232338",
                    borderRadius: "12px",
                    color: "#e2e8f0",
                  }}
                />
                <Legend />
                <Bar dataKey="score" name="Overall" fill="#8b5cf6" radius={[4, 4, 0, 0]} />
                <Bar dataKey="faithfulness" name="Faithfulness" fill="#06b6d4" radius={[4, 4, 0, 0]} />
                <Bar dataKey="relevancy" name="Relevancy" fill="#10b981" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}

      {/* Detailed table */}
      <div className="bg-surface-100 rounded-2xl border border-surface-200/50 p-8">
        <div className="flex items-center justify-between mb-6">
          <h3 className="text-lg font-semibold text-white">All Results</h3>
          <div className="flex items-center gap-2 text-sm text-slate-400">
            <span>{report.summary.completed} of {report.summary.total_combinations} completed</span>
          </div>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-surface-200/50">
                {["Rank", "Chunk Size", "Overlap", "Embedding", "Top-K", "Search", "Faithfulness", "Relevancy", "Precision", "Recall", "Overall"].map(
                  (header) => (
                    <th
                      key={header}
                      className="px-3 py-3 text-left text-xs font-medium text-slate-400 uppercase tracking-wider"
                    >
                      {header}
                    </th>
                  )
                )}
              </tr>
            </thead>
            <tbody className="divide-y divide-surface-200/30">
              {sorted.map((combo: any, index: number) => (
                <tr
                  key={combo.id}
                  className={`hover:bg-surface-50 transition-colors ${
                    index === 0 ? "bg-accent/5" : ""
                  }`}
                >
                  <td className="px-3 py-3 text-slate-300">
                    {index === 0 ? (
                      <Trophy className="w-4 h-4 text-amber-400 inline" />
                    ) : (
                      `#${index + 1}`
                    )}
                  </td>
                  <td className="px-3 py-3 text-white">{combo.params.chunk_size}</td>
                  <td className="px-3 py-3 text-white">{combo.params.chunk_overlap}%</td>
                  <td className="px-3 py-3 text-white text-xs">{combo.params.embedding_model}</td>
                  <td className="px-3 py-3 text-white">{combo.params.top_k}</td>
                  <td className="px-3 py-3 text-white capitalize">{combo.params.search_type}</td>
                  <td className="px-3 py-3 text-white">
                    {combo.faithfulness != null ? `${(combo.faithfulness * 100).toFixed(1)}%` : "-"}
                  </td>
                  <td className="px-3 py-3 text-white">
                    {combo.answer_relevancy != null ? `${(combo.answer_relevancy * 100).toFixed(1)}%` : "-"}
                  </td>
                  <td className="px-3 py-3 text-white">
                    {combo.context_precision != null ? `${(combo.context_precision * 100).toFixed(1)}%` : "-"}
                  </td>
                  <td className="px-3 py-3 text-white">
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
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
