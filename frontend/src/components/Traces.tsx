"use client";

import React, { useState, useEffect } from "react";
import { Activity, Clock, Loader2, AlertCircle, CheckCircle, ChevronRight, Trash2, Filter } from "lucide-react";
import { api } from "@/lib/api";
import TraceDetail from "@/components/TraceDetail";

const SOURCE_COLORS: Record<string, string> = {
  rag_pipeline: "bg-accent/15 text-accent",
  agent_simulation: "bg-purple-500/15 text-purple-400",
  collection_query: "bg-emerald-500/15 text-emerald-400",
  http_request: "bg-amber-500/15 text-amber-400",
};

const STATUS_CONFIG: Record<string, { icon: any; color: string }> = {
  ok: { icon: CheckCircle, color: "text-emerald-400" },
  error: { icon: AlertCircle, color: "text-red-400" },
  unset: { icon: Clock, color: "text-t-secondary" },
};

function formatDuration(ms: number | null): string {
  if (ms == null) return "—";
  if (ms < 1000) return `${Math.round(ms)}ms`;
  if (ms < 60000) return `${(ms / 1000).toFixed(2)}s`;
  return `${(ms / 60000).toFixed(1)}m`;
}

function formatTime(ts: string): string {
  return new Date(ts).toLocaleString("en-US", {
    month: "short", day: "numeric", hour: "2-digit", minute: "2-digit", second: "2-digit",
  });
}

export default function Traces() {
  const [traces, setTraces] = useState<any[]>([]);
  const [summary, setSummary] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [selectedTraceId, setSelectedTraceId] = useState<string | null>(null);
  const [sourceFilter, setSourceFilter] = useState<string>("");
  const [days, setDays] = useState(7);

  useEffect(() => {
    loadTraces();
    loadSummary();
  }, [sourceFilter, days]);

  const loadTraces = async () => {
    try {
      const params: any = { days, limit: 200 };
      if (sourceFilter) params.source = sourceFilter;
      const data = await api.listTraces(params);
      setTraces(data);
    } catch (err) {
      console.error("Failed to load traces:", err);
    } finally {
      setLoading(false);
    }
  };

  const loadSummary = async () => {
    try {
      const data = await api.getTraceSummary(days);
      setSummary(data);
    } catch {}
  };

  if (selectedTraceId) {
    return (
      <TraceDetail
        traceId={selectedTraceId}
        onBack={() => setSelectedTraceId(null)}
      />
    );
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20 text-t-secondary">
        <Loader2 className="w-5 h-5 animate-spin mr-2" />
        Loading traces...
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-accent/15 flex items-center justify-center">
            <Activity className="w-5 h-5 text-accent" />
          </div>
          <div>
            <h2 className="text-2xl font-bold text-primary">Traces</h2>
            <p className="text-sm text-t-secondary">
              {summary ? `${summary.total_traces} trace${summary.total_traces === 1 ? "" : "s"} in the last ${days} days` : "Production observability"}
              {summary?.avg_duration_ms != null && (
                <> · avg {formatDuration(summary.avg_duration_ms)}</>
              )}
            </p>
          </div>
        </div>

        {/* Filters */}
        <div className="flex items-center gap-2">
          <select
            value={sourceFilter}
            onChange={(e) => setSourceFilter(e.target.value)}
            className="px-3 py-1.5 bg-surface-100 border border-visible rounded-lg text-xs text-primary focus:outline-none"
          >
            <option value="">All sources</option>
            <option value="rag_pipeline">RAG Pipeline</option>
            <option value="agent_simulation">Agent Simulation</option>
            <option value="collection_query">Collection Query</option>
            <option value="http_request">HTTP Request</option>
          </select>
          <select
            value={days}
            onChange={(e) => setDays(Number(e.target.value))}
            className="px-3 py-1.5 bg-surface-100 border border-visible rounded-lg text-xs text-primary focus:outline-none"
          >
            <option value={1}>Last 24h</option>
            <option value={7}>Last 7 days</option>
            <option value={30}>Last 30 days</option>
          </select>
        </div>
      </div>

      {/* Summary cards */}
      {summary && summary.total_traces > 0 && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          {Object.entries(summary.by_source as Record<string, number>).map(([source, count]) => (
            <button
              key={source}
              onClick={() => setSourceFilter(source === sourceFilter ? "" : source)}
              className={`p-3 rounded-xl border transition-colors text-left ${
                source === sourceFilter ? "border-accent bg-accent/5" : "border-visible bg-surface-100 hover:bg-surface-50"
              }`}
            >
              <p className="text-xs text-t-secondary capitalize">{source.replace(/_/g, " ")}</p>
              <p className="text-lg font-bold text-primary">{count}</p>
            </button>
          ))}
        </div>
      )}

      {/* Trace list */}
      {traces.length === 0 ? (
        <div className="text-center py-20">
          <Activity className="w-12 h-12 text-muted mx-auto mb-4" />
          <p className="text-t-secondary">No traces recorded yet.</p>
          <p className="text-xs text-muted mt-1">
            Set <code className="bg-surface-200 px-1.5 py-0.5 rounded text-xs">TRACING_ENABLED=true</code> in your environment to start capturing traces.
          </p>
        </div>
      ) : (
        <div className="bg-surface-100 rounded-2xl border border-visible overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-visible">
                {["Name", "Source", "Status", "Duration", "Spans", "Time"].map((h) => (
                  <th key={h} className="px-4 py-3 text-left text-xs font-medium text-t-secondary uppercase tracking-wider">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-surface-200/30">
              {traces.map((t) => {
                const status = STATUS_CONFIG[t.status] || STATUS_CONFIG.unset;
                const StatusIcon = status.icon;
                const sourceColor = SOURCE_COLORS[t.source] || "bg-surface-200/30 text-t-secondary";
                return (
                  <tr
                    key={t.id}
                    onClick={() => setSelectedTraceId(t.id)}
                    className="hover:bg-surface-50 cursor-pointer transition-colors"
                  >
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-2">
                        <ChevronRight className="w-3 h-3 text-muted" />
                        <span className="text-primary font-medium truncate max-w-xs">{t.name}</span>
                      </div>
                    </td>
                    <td className="px-4 py-3">
                      <span className={`px-2 py-0.5 rounded-full text-[10px] font-medium capitalize ${sourceColor}`}>
                        {(t.source || "unknown").replace(/_/g, " ")}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <StatusIcon className={`w-3.5 h-3.5 ${status.color}`} />
                    </td>
                    <td className="px-4 py-3 text-t-secondary text-xs font-mono">
                      {formatDuration(t.duration_ms)}
                    </td>
                    <td className="px-4 py-3 text-t-secondary text-xs">
                      {t.total_spans}
                    </td>
                    <td className="px-4 py-3 text-t-secondary text-xs">
                      {formatTime(t.start_time)}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
