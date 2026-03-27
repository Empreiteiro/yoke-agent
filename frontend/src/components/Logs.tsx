"use client";

import { useState, useEffect } from "react";
import {
  FileText,
  Loader2,
  Cpu,
  Hash,
  DollarSign,
  Layers,
  Filter,
} from "lucide-react";
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
  PieChart,
  Pie,
  Cell,
} from "recharts";



const OPERATION_LABELS: Record<string, string> = {
  dataset_generation: "Dataset Generation",
  rag_pipeline: "RAG Pipeline",
  ragas_evaluation: "RAGAS Evaluation",
  provider_test: "Provider Test",
};

const PHASE_LABELS: Record<string, string> = {
  dataset_generation: "Generate Dataset",
  rag_pipeline: "Run Experiments",
  ragas_evaluation: "Run Experiments",
  provider_test: "Providers",
};

const OPERATION_COLORS: Record<string, string> = {
  dataset_generation: "#8b5cf6",
  rag_pipeline: "#06b6d4",
  ragas_evaluation: "#10b981",
  provider_test: "#f59e0b",
};

const PIE_COLORS = ["#8b5cf6", "#06b6d4", "#10b981", "#f59e0b", "#ef4444", "#ec4899"];

export default function Logs() {
  const [summary, setSummary] = useState<any>(null);
  const [logs, setLogs] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [days, setDays] = useState(30);
  const [filterOperation, setFilterOperation] = useState<string>("");
  const [filterModelType, setFilterModelType] = useState<string>("");

  useEffect(() => {
    loadData();
  }, [days, filterOperation, filterModelType]);

  const loadData = async () => {
    setLoading(true);
    try {
      const [summaryData, logsData] = await Promise.all([
        api.getTokenUsageSummary({ days }),
        api.listTokenUsage({
          days,
          operation: filterOperation || undefined,
          model_type: filterModelType || undefined,
          limit: 200,
        }),
      ]);
      setSummary(summaryData);
      setLogs(logsData);
    } catch (err) {
      console.error("Failed to load token usage:", err);
    } finally {
      setLoading(false);
    }
  };

  const formatNumber = (n: number) => {
    if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
    if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`;
    return n.toString();
  };

  const formatCost = (cost: number) => {
    if (cost < 0.01) return `$${cost.toFixed(4)}`;
    return `$${cost.toFixed(2)}`;
  };

  const formatDate = (dateStr: string) => {
    return new Date(dateStr).toLocaleDateString("en-US", {
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  };

  if (loading && !summary) {
    return (
      <div className="flex items-center justify-center py-20 text-t-secondary">
        <Loader2 className="w-5 h-5 animate-spin mr-2" />
        Loading logs...
      </div>
    );
  }

  const byDayData = (summary?.by_day || []).map((d: any) => ({
    date: d.date,
    tokens: d.total_tokens,
    cost: d.estimated_cost,
    calls: d.call_count,
  }));

  const byOperationData = (summary?.by_operation || []).map((o: any) => ({
    name: OPERATION_LABELS[o.operation] || o.operation,
    value: o.total_tokens,
    cost: o.estimated_cost,
    calls: o.call_count,
  }));

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-primary">Token Usage Logs</h2>
          <p className="text-sm text-t-secondary mt-1">
            Monitor LLM and embedding token consumption
          </p>
        </div>

        {/* Period selector */}
        <div className="flex items-center gap-2">
          {[7, 30, 90].map((d) => (
            <button
              key={d}
              onClick={() => setDays(d)}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
                days === d
                  ? "bg-accent/20 text-accent border border-accent/30"
                  : "bg-surface-100 text-t-secondary hover:text-primary border border-surface-200/50"
              }`}
            >
              {d}d
            </button>
          ))}
        </div>
      </div>

      {/* Summary cards */}
      {summary && (
        <div className="grid grid-cols-4 gap-4">
          <div className="bg-surface-100 rounded-2xl border border-surface-200/50 p-5">
            <div className="flex items-center gap-2 mb-3">
              <div className="w-8 h-8 rounded-lg bg-purple-500/20 flex items-center justify-center">
                <Hash className="w-4 h-4 text-purple-400" />
              </div>
              <span className="text-xs text-t-secondary">Total Tokens</span>
            </div>
            <p className="text-2xl font-bold text-primary">
              {formatNumber(summary.total_tokens)}
            </p>
          </div>

          <div className="bg-surface-100 rounded-2xl border border-surface-200/50 p-5">
            <div className="flex items-center gap-2 mb-3">
              <div className="w-8 h-8 rounded-lg bg-cyan-500/20 flex items-center justify-center">
                <Cpu className="w-4 h-4 text-cyan-400" />
              </div>
              <span className="text-xs text-t-secondary">LLM Tokens</span>
            </div>
            <p className="text-2xl font-bold text-primary">
              {formatNumber(summary.total_llm_tokens)}
            </p>
          </div>

          <div className="bg-surface-100 rounded-2xl border border-surface-200/50 p-5">
            <div className="flex items-center gap-2 mb-3">
              <div className="w-8 h-8 rounded-lg bg-emerald-500/20 flex items-center justify-center">
                <Layers className="w-4 h-4 text-emerald-400" />
              </div>
              <span className="text-xs text-t-secondary">Embedding Tokens</span>
            </div>
            <p className="text-2xl font-bold text-primary">
              {formatNumber(summary.total_embedding_tokens)}
            </p>
          </div>

          <div className="bg-surface-100 rounded-2xl border border-surface-200/50 p-5">
            <div className="flex items-center gap-2 mb-3">
              <div className="w-8 h-8 rounded-lg bg-amber-500/20 flex items-center justify-center">
                <DollarSign className="w-4 h-4 text-amber-400" />
              </div>
              <span className="text-xs text-t-secondary">Est. Cost</span>
            </div>
            <p className="text-2xl font-bold text-primary">
              {formatCost(summary.total_estimated_cost)}
            </p>
          </div>
        </div>
      )}

      {/* Charts row */}
      <div className="grid grid-cols-2 gap-4">
        {/* Usage by day */}
        {byDayData.length > 0 && (
          <div className="bg-surface-100 rounded-2xl border border-surface-200/50 p-6">
            <h3 className="text-sm font-semibold text-primary mb-4">Tokens per Day</h3>
            <div className="h-52">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={byDayData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
                  <XAxis
                    dataKey="date"
                    tick={{ fill: "var(--text-secondary)", fontSize: 10 }}
                    tickFormatter={(d) => {
                      const date = new Date(d);
                      return `${date.getMonth() + 1}/${date.getDate()}`;
                    }}
                  />
                  <YAxis
                    tick={{ fill: "var(--text-secondary)", fontSize: 10 }}
                    tickFormatter={formatNumber}
                  />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: "var(--surface-100)",
                      border: "1px solid var(--surface-200)",
                      borderRadius: "8px",
                      color: "var(--text-primary)",
                      fontSize: 12,
                    }}
                    formatter={(value: any) => [formatNumber(value), "Tokens"]}
                  />
                  <Bar dataKey="tokens" fill="#8b5cf6" radius={[3, 3, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>
        )}

        {/* Usage by operation */}
        {byOperationData.length > 0 && (
          <div className="bg-surface-100 rounded-2xl border border-surface-200/50 p-6">
            <h3 className="text-sm font-semibold text-primary mb-4">Tokens by Operation</h3>
            <div className="h-52">
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie
                    data={byOperationData}
                    cx="50%"
                    cy="50%"
                    outerRadius={80}
                    dataKey="value"
                    label={({ name, percent }) =>
                      `${name} ${(percent * 100).toFixed(0)}%`
                    }
                    labelLine={false}
                  >
                    {byOperationData.map((_: any, i: number) => (
                      <Cell key={i} fill={PIE_COLORS[i % PIE_COLORS.length]} />
                    ))}
                  </Pie>
                  <Tooltip
                    contentStyle={{
                      backgroundColor: "var(--surface-100)",
                      border: "1px solid var(--surface-200)",
                      borderRadius: "8px",
                      color: "var(--text-primary)",
                      fontSize: 12,
                    }}
                    formatter={(value: any) => [formatNumber(value as number), "Tokens"]}
                  />
                </PieChart>
              </ResponsiveContainer>
            </div>
          </div>
        )}
      </div>

      {/* Models breakdown */}
      {summary?.by_model?.length > 0 && (
        <div className="bg-surface-100 rounded-2xl border border-surface-200/50 p-6">
          <h3 className="text-sm font-semibold text-primary mb-4">Usage by Model</h3>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-surface-200/50">
                  {["Model", "Type", "Total Tokens", "Calls", "Est. Cost"].map((h) => (
                    <th key={h} className="px-3 py-2 text-left text-xs font-medium text-t-secondary uppercase">
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-surface-200/30">
                {summary.by_model.map((m: any, i: number) => (
                  <tr key={i} className="hover:bg-surface-50 transition-colors">
                    <td className="px-3 py-2.5 text-primary font-medium">{m.model_name}</td>
                    <td className="px-3 py-2.5">
                      <span
                        className={`text-xs px-2 py-0.5 rounded-full ${
                          m.model_type === "llm"
                            ? "bg-purple-500/20 text-purple-400"
                            : "bg-emerald-500/20 text-emerald-400"
                        }`}
                      >
                        {m.model_type.toUpperCase()}
                      </span>
                    </td>
                    <td className="px-3 py-2.5 text-primary">{formatNumber(m.total_tokens)}</td>
                    <td className="px-3 py-2.5 text-t-secondary">{m.call_count}</td>
                    <td className="px-3 py-2.5 text-amber-400">{formatCost(m.estimated_cost)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Filters */}
      <div className="flex items-center gap-3">
        <Filter className="w-4 h-4 text-t-secondary" />
        <select
          value={filterOperation}
          onChange={(e) => setFilterOperation(e.target.value)}
          className="bg-surface-100 border border-surface-200/50 rounded-lg px-3 py-1.5 text-sm text-primary focus:outline-none focus:border-accent/50"
        >
          <option value="">All Operations</option>
          <option value="dataset_generation">Dataset Generation</option>
          <option value="rag_pipeline">RAG Pipeline</option>
          <option value="ragas_evaluation">RAGAS Evaluation</option>
          <option value="provider_test">Provider Test</option>
        </select>
        <select
          value={filterModelType}
          onChange={(e) => setFilterModelType(e.target.value)}
          className="bg-surface-100 border border-surface-200/50 rounded-lg px-3 py-1.5 text-sm text-primary focus:outline-none focus:border-accent/50"
        >
          <option value="">All Types</option>
          <option value="llm">LLM</option>
          <option value="embedding">Embedding</option>
        </select>
      </div>

      {/* Detailed log table */}
      <div className="bg-surface-100 rounded-2xl border border-surface-200/50 p-6">
        <h3 className="text-sm font-semibold text-primary mb-4">
          Detailed Logs ({logs.length} entries)
        </h3>
        {logs.length === 0 ? (
          <div className="text-center py-8">
            <FileText className="w-10 h-10 text-muted mx-auto mb-3" />
            <p className="text-t-secondary text-sm">
              No token usage logs yet. Run a pipeline to start tracking.
            </p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b border-surface-200/50">
                  {["Time", "Phase", "Operation", "Model", "Type", "Prompt", "Completion", "Total", "Cost", "Experiment"].map(
                    (h) => (
                      <th key={h} className="px-2 py-2 text-left text-xs font-medium text-t-secondary uppercase">
                        {h}
                      </th>
                    )
                  )}
                </tr>
              </thead>
              <tbody className="divide-y divide-surface-200/30">
                {logs.map((log: any) => (
                  <tr key={log.id} className="hover:bg-surface-50 transition-colors">
                    <td className="px-2 py-2 text-t-secondary whitespace-nowrap">
                      {formatDate(log.created_at)}
                    </td>
                    <td className="px-2 py-2 text-t-secondary whitespace-nowrap">
                      {PHASE_LABELS[log.operation] || log.operation}
                    </td>
                    <td className="px-2 py-2">
                      <span
                        className="text-xs px-1.5 py-0.5 rounded"
                        style={{
                          backgroundColor: `${OPERATION_COLORS[log.operation] || "#64748b"}20`,
                          color: OPERATION_COLORS[log.operation] || "#94a3b8",
                        }}
                      >
                        {OPERATION_LABELS[log.operation] || log.operation}
                      </span>
                    </td>
                    <td className="px-2 py-2 text-primary truncate max-w-[150px]">
                      {log.model_name}
                    </td>
                    <td className="px-2 py-2">
                      <span
                        className={`text-xs ${
                          log.model_type === "llm" ? "text-purple-400" : "text-emerald-400"
                        }`}
                      >
                        {log.model_type.toUpperCase()}
                      </span>
                    </td>
                    <td className="px-2 py-2 text-primary">{formatNumber(log.prompt_tokens)}</td>
                    <td className="px-2 py-2 text-primary">{formatNumber(log.completion_tokens)}</td>
                    <td className="px-2 py-2 text-primary font-medium">{formatNumber(log.total_tokens)}</td>
                    <td className="px-2 py-2 text-amber-400">
                      {log.estimated_cost != null ? formatCost(log.estimated_cost) : "-"}
                    </td>
                    <td className="px-2 py-2 text-t-secondary">
                      {log.experiment_id ? `#${log.experiment_id}` : "-"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
