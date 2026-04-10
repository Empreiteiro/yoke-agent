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
  ChevronRight,
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
  agent_simulation: "Agent Simulation",
  agent_evaluation: "Agent Evaluation",
  agent_generation: "Agent Generation",
  agent_report: "Agent Report",
  chat: "AI Assistant",
};

const PHASE_LABELS: Record<string, string> = {
  dataset_generation: "Generate Dataset",
  rag_pipeline: "Run Experiments",
  ragas_evaluation: "Run Experiments",
  provider_test: "Providers",
  agent_simulation: "Agent Workbench",
  agent_evaluation: "Agent Workbench",
  agent_generation: "Agent Workbench",
  agent_report: "Agent Workbench",
  chat: "AI Assistant",
};

const OPERATION_COLORS: Record<string, string> = {
  dataset_generation: "#8b5cf6",
  rag_pipeline: "#06b6d4",
  ragas_evaluation: "#10b981",
  provider_test: "#f59e0b",
  agent_simulation: "#ec4899",
  agent_evaluation: "#ef4444",
  agent_generation: "#a855f7",
  agent_report: "#14b8a6",
  chat: "#3b82f6",
};

const PIE_COLORS = ["#8b5cf6", "#06b6d4", "#10b981", "#f59e0b", "#ef4444", "#ec4899"];

interface GroupedLogsProps {
  logs: any[];
  formatDate: (d: string) => string;
  formatNumber: (n: number) => string;
  formatCost: (c: number) => string;
  filterOperation: string;
  setFilterOperation: (v: string) => void;
  filterModelType: string;
  setFilterModelType: (v: string) => void;
}

function GroupedLogs({
  logs,
  formatDate,
  formatNumber,
  formatCost,
  filterOperation,
  setFilterOperation,
  filterModelType,
  setFilterModelType,
}: GroupedLogsProps) {
  const [expandedGroups, setExpandedGroups] = useState<Set<string>>(new Set());

  const toggleGroup = (key: string) => {
    setExpandedGroups((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  };

  // Group logs by experiment_id (null → "ungrouped")
  const groups = logs.reduce<Record<string, any[]>>((acc, log) => {
    const key = log.experiment_id ? `exp-${log.experiment_id}` : "ungrouped";
    if (!acc[key]) acc[key] = [];
    acc[key].push(log);
    return acc;
  }, {});

  // Sort: experiments first (by id desc), ungrouped last
  const sortedKeys = Object.keys(groups).sort((a, b) => {
    if (a === "ungrouped") return 1;
    if (b === "ungrouped") return -1;
    const idA = parseInt(a.replace("exp-", ""));
    const idB = parseInt(b.replace("exp-", ""));
    return idB - idA;
  });

  const groupSummary = (entries: any[]) => {
    const totalTokens = entries.reduce((s, l) => s + (l.total_tokens || 0), 0);
    const totalCost = entries.reduce((s, l) => s + (l.estimated_cost || 0), 0);
    const operations = new Set(entries.map((l) => l.operation));
    const models = new Set(entries.map((l) => l.model_name));
    const earliest = entries.reduce(
      (min, l) => (l.created_at < min ? l.created_at : min),
      entries[0].created_at
    );
    return { totalTokens, totalCost, operations, models, earliest, count: entries.length };
  };

  const isGhost = logs.length === 0;

  // Ghost placeholder rows rendered (blurred) when no real logs exist.
  const ghostEntries = [
    { id: "g-1", operation: "rag_pipeline", model_name: "gpt-4o-mini", model_type: "llm", prompt_tokens: 1280, completion_tokens: 320, total_tokens: 1600, estimated_cost: 0, created_at: new Date().toISOString(), experiment_id: 1 },
    { id: "g-2", operation: "ragas_evaluation", model_name: "gpt-4o-mini", model_type: "llm", prompt_tokens: 2100, completion_tokens: 480, total_tokens: 2580, estimated_cost: 0, created_at: new Date().toISOString(), experiment_id: 1 },
    { id: "g-3", operation: "dataset_generation", model_name: "gpt-4o-mini", model_type: "llm", prompt_tokens: 800, completion_tokens: 200, total_tokens: 1000, estimated_cost: 0, created_at: new Date().toISOString(), experiment_id: null },
  ];
  const displayLogs = isGhost ? ghostEntries : logs;
  const displayGroups = displayLogs.reduce<Record<string, any[]>>((acc, log) => {
    const key = log.experiment_id ? `exp-${log.experiment_id}` : "ungrouped";
    if (!acc[key]) acc[key] = [];
    acc[key].push(log);
    return acc;
  }, {});
  const displaySortedKeys = Object.keys(displayGroups).sort((a, b) => {
    if (a === "ungrouped") return 1;
    if (b === "ungrouped") return -1;
    return parseInt(b.replace("exp-", "")) - parseInt(a.replace("exp-", ""));
  });

  return (
    <div className="relative rounded-2xl border border-visible p-6">
      <h3 className="text-sm font-semibold text-primary mb-3">
        Detailed Logs ({logs.length} entries)
      </h3>

      {/* Filters — moved below the title, inside the detailed logs card */}
      <div className="flex items-center gap-3 mb-4">
        <Filter className="w-4 h-4 text-t-secondary" />
        <select
          value={filterOperation}
          onChange={(e) => setFilterOperation(e.target.value)}
          className="bg-surface-100 border border-visible rounded-lg px-3 py-1.5 text-sm text-primary focus:outline-none focus:border-accent/50"
        >
          <option value="">All Operations</option>
          <option value="dataset_generation">Dataset Generation</option>
          <option value="rag_pipeline">RAG Pipeline</option>
          <option value="ragas_evaluation">RAGAS Evaluation</option>
          <option value="provider_test">Provider Test</option>
          <option value="agent_simulation">Agent Simulation</option>
          <option value="agent_evaluation">Agent Evaluation</option>
          <option value="agent_generation">Agent Generation</option>
          <option value="agent_report">Agent Report</option>
          <option value="chat">AI Assistant</option>
        </select>
        <select
          value={filterModelType}
          onChange={(e) => setFilterModelType(e.target.value)}
          className="bg-surface-100 border border-visible rounded-lg px-3 py-1.5 text-sm text-primary focus:outline-none focus:border-accent/50"
        >
          <option value="">All Types</option>
          <option value="llm">LLM</option>
          <option value="embedding">Embedding</option>
        </select>
      </div>

      <div className={`space-y-2 ${isGhost ? "opacity-25 blur-[1px] pointer-events-none select-none" : ""}`}>
          {displaySortedKeys.map((key) => {
            const entries = displayGroups[key];
            const isExpanded = expandedGroups.has(key);
            const summary = groupSummary(entries);
            const label =
              key === "ungrouped"
                ? "No Experiment"
                : `Experiment #${key.replace("exp-", "")}`;

            return (
              <div
                key={key}
                className="border border-surface-200/50 rounded-xl overflow-hidden"
              >
                {/* Accordion header */}
                <button
                  onClick={() => toggleGroup(key)}
                  className="w-full flex items-center gap-3 px-4 py-3 bg-surface-50 hover:bg-surface-100 transition-colors text-left"
                >
                  <ChevronRight
                    className={`w-4 h-4 text-t-secondary shrink-0 transition-transform duration-200 ${
                      isExpanded ? "rotate-90" : ""
                    }`}
                  />
                  <span className="text-sm font-semibold text-primary min-w-[140px]">
                    {label}
                  </span>
                  <span className="text-xs text-t-secondary">
                    {formatDate(summary.earliest)}
                  </span>
                  <div className="flex items-center gap-4 ml-auto">
                    <span className="text-xs text-t-secondary">
                      {summary.count} {summary.count === 1 ? "call" : "calls"}
                    </span>
                    <span className="text-xs text-primary font-medium">
                      {formatNumber(summary.totalTokens)} tokens
                    </span>
                    <span className="text-xs text-amber-400 font-medium min-w-[60px] text-right">
                      {formatCost(summary.totalCost)}
                    </span>
                    <div className="flex gap-1">
                      {Array.from(summary.operations).map((op: any) => (
                        <span
                          key={op}
                          className="text-[10px] px-1.5 py-0.5 rounded"
                          style={{
                            backgroundColor: `${OPERATION_COLORS[op] || "#64748b"}20`,
                            color: OPERATION_COLORS[op] || "#94a3b8",
                          }}
                        >
                          {OPERATION_LABELS[op] || op}
                        </span>
                      ))}
                    </div>
                  </div>
                </button>

                {/* Expanded detail table */}
                {isExpanded && (
                  <div className="overflow-x-auto">
                    <table className="w-full text-xs">
                      <thead>
                        <tr className="border-b border-surface-200/50 bg-surface-100/50">
                          {["Time", "Phase", "Operation", "Model", "Type", "Prompt", "Completion", "Total", "Cost"].map(
                            (h) => (
                              <th
                                key={h}
                                className="px-3 py-2 text-left text-[10px] font-medium text-t-secondary uppercase"
                              >
                                {h}
                              </th>
                            )
                          )}
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-surface-200/30">
                        {entries.map((log: any) => (
                          <tr
                            key={log.id}
                            className="hover:bg-surface-50 transition-colors"
                          >
                            <td className="px-3 py-2 text-t-secondary whitespace-nowrap">
                              {formatDate(log.created_at)}
                            </td>
                            <td className="px-3 py-2 text-t-secondary whitespace-nowrap">
                              {PHASE_LABELS[log.operation] || log.operation}
                            </td>
                            <td className="px-3 py-2">
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
                            <td className="px-3 py-2 text-primary truncate max-w-[150px]">
                              {log.model_name}
                            </td>
                            <td className="px-3 py-2">
                              <span
                                className={`text-xs ${
                                  log.model_type === "llm"
                                    ? "text-purple-400"
                                    : "text-emerald-400"
                                }`}
                              >
                                {log.model_type.toUpperCase()}
                              </span>
                            </td>
                            <td className="px-3 py-2 text-primary">
                              {formatNumber(log.prompt_tokens)}
                            </td>
                            <td className="px-3 py-2 text-primary">
                              {formatNumber(log.completion_tokens)}
                            </td>
                            <td className="px-3 py-2 text-primary font-medium">
                              {formatNumber(log.total_tokens)}
                            </td>
                            <td className="px-3 py-2 text-amber-400">
                              {log.estimated_cost != null
                                ? formatCost(log.estimated_cost)
                                : "-"}
                            </td>
                          </tr>
                        ))}
                        {/* Group totals row */}
                        <tr className="bg-surface-100/80 font-medium border-t border-surface-200/50">
                          <td
                            colSpan={5}
                            className="px-3 py-2 text-xs text-t-secondary uppercase"
                          >
                            Total
                          </td>
                          <td className="px-3 py-2 text-primary">
                            {formatNumber(
                              entries.reduce((s: number, l: any) => s + (l.prompt_tokens || 0), 0)
                            )}
                          </td>
                          <td className="px-3 py-2 text-primary">
                            {formatNumber(
                              entries.reduce(
                                (s: number, l: any) => s + (l.completion_tokens || 0),
                                0
                              )
                            )}
                          </td>
                          <td className="px-3 py-2 text-primary">
                            {formatNumber(summary.totalTokens)}
                          </td>
                          <td className="px-3 py-2 text-amber-400">
                            {formatCost(summary.totalCost)}
                          </td>
                        </tr>
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            );
          })}
      </div>
      {isGhost && (
        <div className="absolute inset-0 flex items-center justify-center">
          <div className="text-center">
            <FileText className="w-10 h-10 text-muted mx-auto mb-3" />
            <p className="text-t-secondary text-sm font-medium">No token usage logs yet</p>
            <p className="text-[11px] text-muted mt-0.5">Run a pipeline to start tracking</p>
          </div>
        </div>
      )}
    </div>
  );
}

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
          limit: 10000,
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

  const realByDay = (summary?.by_day || []).map((d: any) => ({
    date: d.date,
    tokens: d.total_tokens,
    cost: d.estimated_cost,
    calls: d.call_count,
  }));

  const realByOperation = (summary?.by_operation || []).map((o: any) => ({
    name: OPERATION_LABELS[o.operation] || o.operation,
    value: o.total_tokens,
    cost: o.estimated_cost,
    calls: o.call_count,
  }));

  // Ghost/placeholder data rendered when no real activity is available,
  // so the layout stays populated and users get a preview of what the
  // charts and tables will look like once they run their first pipeline.
  const ghostByDayData = Array.from({ length: Math.min(days, 14) }, (_, i) => {
    const d = new Date();
    d.setDate(d.getDate() - (Math.min(days, 14) - 1 - i));
    // Smooth sine wave so the bar chart looks natural, not random
    const wave = 0.5 + 0.5 * Math.sin(i / 2);
    return {
      date: d.toISOString().slice(0, 10),
      tokens: Math.round(1500 + wave * 3500),
      cost: 0,
      calls: Math.round(5 + wave * 15),
    };
  });
  const ghostByOperationData = [
    { name: "RAG Pipeline", value: 42000, cost: 0, calls: 120 },
    { name: "RAGAS Evaluation", value: 28000, cost: 0, calls: 80 },
    { name: "Dataset Generation", value: 18000, cost: 0, calls: 40 },
    { name: "Agent Simulation", value: 12000, cost: 0, calls: 30 },
  ];
  const ghostByModelData = [
    { model_name: "gpt-4o-mini", model_type: "llm", total_tokens: 58000, call_count: 140, estimated_cost: 0 },
    { model_name: "text-embedding-3-small", model_type: "embedding", total_tokens: 22000, call_count: 80, estimated_cost: 0 },
    { model_name: "claude-sonnet-4", model_type: "llm", total_tokens: 20000, call_count: 30, estimated_cost: 0 },
  ];

  const byDayData = realByDay.length > 0 ? realByDay : ghostByDayData;
  const byOperationData = realByOperation.length > 0 ? realByOperation : ghostByOperationData;
  const modelBreakdown = summary?.by_model?.length ? summary.by_model : ghostByModelData;

  const isByDayGhost = realByDay.length === 0;
  const isByOperationGhost = realByOperation.length === 0;
  const isModelGhost = !summary?.by_model?.length;

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

      {/* Summary cards — grouped under a single border */}
      {(() => {
        const totals = {
          total_tokens: summary?.total_tokens ?? 0,
          total_llm_tokens: summary?.total_llm_tokens ?? 0,
          total_embedding_tokens: summary?.total_embedding_tokens ?? 0,
          total_estimated_cost: summary?.total_estimated_cost ?? 0,
        };
        const isSummaryGhost =
          totals.total_tokens === 0 &&
          totals.total_llm_tokens === 0 &&
          totals.total_embedding_tokens === 0 &&
          totals.total_estimated_cost === 0;
        const display = isSummaryGhost
          ? { total_tokens: 124500, total_llm_tokens: 98200, total_embedding_tokens: 26300, total_estimated_cost: 1.37 }
          : totals;
        const ghostCls = isSummaryGhost
          ? "opacity-30 blur-[1px] pointer-events-none select-none"
          : "";
        return (
          <div className="relative rounded-2xl border border-visible p-4">
            <div className={`grid grid-cols-4 gap-4 ${ghostCls}`}>
              <div className="bg-surface-100 rounded-2xl border border-surface-200/50 p-5">
                <div className="flex items-center gap-2 mb-3">
                  <div className="w-8 h-8 rounded-lg bg-purple-500/20 flex items-center justify-center">
                    <Hash className="w-4 h-4 text-purple-400" />
                  </div>
                  <span className="text-xs text-t-secondary">Total Tokens</span>
                </div>
                <p className="text-2xl font-bold text-primary">
                  {formatNumber(display.total_tokens)}
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
                  {formatNumber(display.total_llm_tokens)}
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
                  {formatNumber(display.total_embedding_tokens)}
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
                  {formatCost(display.total_estimated_cost)}
                </p>
              </div>
            </div>
            {isSummaryGhost && (
              <div className="absolute inset-0 flex items-center justify-center">
                <div className="text-center">
                  <p className="text-xs font-medium text-t-secondary">No data yet</p>
                  <p className="text-[10px] text-muted mt-0.5">Sample values shown — run a pipeline to see real usage</p>
                </div>
              </div>
            )}
          </div>
        );
      })()}

      {/* Charts + model breakdown — grouped under a single larger border */}
      <div className="rounded-2xl border border-visible p-4 space-y-4">
      {/* Charts row */}
      <div className="grid grid-cols-2 gap-4">
        {/* Usage by day */}
        <div className="relative bg-surface-100 rounded-2xl border border-surface-200/50 p-6">
          <h3 className="text-sm font-semibold text-primary mb-4">Tokens per Day</h3>
          <div className={`h-52 ${isByDayGhost ? "opacity-25 blur-[1px] pointer-events-none" : ""}`}>
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
                <Bar dataKey="tokens" fill={isByDayGhost ? "#64748b" : "#8b5cf6"} radius={[3, 3, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
          {isByDayGhost && (
            <div className="absolute inset-0 flex items-center justify-center">
              <div className="text-center">
                <p className="text-xs font-medium text-t-secondary">No data yet</p>
                <p className="text-[10px] text-muted mt-0.5">Run a pipeline to populate this chart</p>
              </div>
            </div>
          )}
        </div>

        {/* Usage by operation */}
        <div className="relative bg-surface-100 rounded-2xl border border-surface-200/50 p-6">
          <h3 className="text-sm font-semibold text-primary mb-4">Tokens by Operation</h3>
          <div className={`h-52 ${isByOperationGhost ? "opacity-25 blur-[1px] pointer-events-none" : ""}`}>
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
                    <Cell
                      key={i}
                      fill={isByOperationGhost ? "#475569" : PIE_COLORS[i % PIE_COLORS.length]}
                    />
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
          {isByOperationGhost && (
            <div className="absolute inset-0 flex items-center justify-center">
              <div className="text-center">
                <p className="text-xs font-medium text-t-secondary">No data yet</p>
                <p className="text-[10px] text-muted mt-0.5">Run a pipeline to populate this chart</p>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Models breakdown */}
      <div className="relative bg-surface-100 rounded-2xl border border-surface-200/50 p-6 mt-4">
        <h3 className="text-sm font-semibold text-primary mb-4">Usage by Model</h3>
        <div className={`overflow-x-auto ${isModelGhost ? "opacity-25 blur-[1px] pointer-events-none" : ""}`}>
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
              {modelBreakdown.map((m: any, i: number) => (
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
        {isModelGhost && (
          <div className="absolute inset-0 flex items-center justify-center">
            <div className="text-center">
              <p className="text-xs font-medium text-t-secondary">No data yet</p>
              <p className="text-[10px] text-muted mt-0.5">Run a pipeline to populate this table</p>
            </div>
          </div>
        )}
      </div>
      </div>

      {/* Detailed logs grouped by experiment */}
      <GroupedLogs
        logs={logs}
        formatDate={formatDate}
        formatNumber={formatNumber}
        formatCost={formatCost}
        filterOperation={filterOperation}
        setFilterOperation={setFilterOperation}
        filterModelType={filterModelType}
        setFilterModelType={setFilterModelType}
      />
    </div>
  );
}
