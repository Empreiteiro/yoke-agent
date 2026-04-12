"use client";

import React, { useState, useEffect } from "react";
import { ArrowLeft, Loader2, AlertCircle, CheckCircle, Clock, ChevronRight, ChevronDown } from "lucide-react";
import { api } from "@/lib/api";

interface TraceDetailProps {
  traceId: string;
  onBack: () => void;
}

const KIND_COLORS: Record<string, string> = {
  internal: "bg-blue-500",
  client: "bg-amber-500",
  server: "bg-emerald-500",
};

const STATUS_DOT: Record<string, string> = {
  ok: "bg-emerald-400",
  error: "bg-red-400",
  unset: "bg-surface-200",
};

function formatDuration(ms: number | null): string {
  if (ms == null) return "—";
  if (ms < 1) return "<1ms";
  if (ms < 1000) return `${Math.round(ms)}ms`;
  if (ms < 60000) return `${(ms / 1000).toFixed(2)}s`;
  return `${(ms / 60000).toFixed(1)}m`;
}

interface SpanNode {
  id: string;
  name: string;
  kind: string;
  status: string;
  start_time: string;
  end_time?: string;
  duration_ms?: number;
  attributes?: Record<string, any>;
  events?: any[];
  error_message?: string;
  children: SpanNode[];
}

function flattenSpans(nodes: SpanNode[], depth: number = 0): Array<{ span: SpanNode; depth: number }> {
  const result: Array<{ span: SpanNode; depth: number }> = [];
  for (const node of nodes) {
    result.push({ span: node, depth });
    if (node.children?.length) {
      result.push(...flattenSpans(node.children, depth + 1));
    }
  }
  return result;
}

export default function TraceDetail({ traceId, onBack }: TraceDetailProps) {
  const [trace, setTrace] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [selectedSpanId, setSelectedSpanId] = useState<string | null>(null);

  useEffect(() => {
    loadTrace();
  }, [traceId]);

  const loadTrace = async () => {
    try {
      const data = await api.getTrace(traceId);
      setTrace(data);
    } catch (err) {
      console.error("Failed to load trace:", err);
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20 text-t-secondary">
        <Loader2 className="w-5 h-5 animate-spin mr-2" />
        Loading trace...
      </div>
    );
  }

  if (!trace) {
    return (
      <div className="text-center py-20 text-t-secondary">
        <AlertCircle className="w-12 h-12 mx-auto mb-4 text-muted" />
        <p>Trace not found.</p>
        <button onClick={onBack} className="mt-4 text-accent hover:underline text-sm">Back to traces</button>
      </div>
    );
  }

  const spans = trace.spans || [];
  const flatSpans = flattenSpans(spans);
  const traceDuration = trace.duration_ms || 1;
  const traceStart = new Date(trace.start_time).getTime();
  const selectedSpan = flatSpans.find((f) => f.span.id === selectedSpanId)?.span || null;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-3">
        <button onClick={onBack} className="p-1.5 rounded-lg hover:bg-surface-100 text-t-secondary transition-colors">
          <ArrowLeft className="w-5 h-5" />
        </button>
        <div className="flex-1 min-w-0">
          <h2 className="text-xl font-bold text-primary truncate">{trace.name}</h2>
          <div className="flex items-center gap-3 text-xs text-t-secondary mt-0.5">
            <span className={`w-2 h-2 rounded-full inline-block ${STATUS_DOT[trace.status] || STATUS_DOT.unset}`} />
            <span className="capitalize">{trace.status}</span>
            <span>{formatDuration(trace.duration_ms)}</span>
            <span>{trace.total_spans} span{trace.total_spans === 1 ? "" : "s"}</span>
            {trace.source && <span className="capitalize">{trace.source.replace(/_/g, " ")}</span>}
            {trace.experiment_id && <span>Experiment #{trace.experiment_id}</span>}
          </div>
        </div>
      </div>

      {/* Error banner */}
      {trace.error_message && (
        <div className="flex items-start gap-2 px-4 py-3 bg-red-500/10 border border-red-500/30 rounded-xl text-red-300 text-sm">
          <AlertCircle className="w-4 h-4 mt-0.5 flex-shrink-0" />
          <span className="break-all">{trace.error_message}</span>
        </div>
      )}

      <div className="flex gap-6">
        {/* Waterfall */}
        <div className="flex-1 bg-surface-100 rounded-2xl border border-visible p-4 overflow-x-auto">
          <h3 className="text-xs font-semibold text-t-secondary uppercase mb-3">Span waterfall</h3>

          {flatSpans.length === 0 ? (
            <p className="text-sm text-muted text-center py-8">No spans recorded.</p>
          ) : (
            <div className="space-y-1">
              {flatSpans.map(({ span, depth }) => {
                const spanStart = new Date(span.start_time).getTime();
                const offset = Math.max(0, spanStart - traceStart);
                const leftPct = (offset / traceDuration) * 100;
                const widthPct = Math.max(0.5, ((span.duration_ms || 0) / traceDuration) * 100);
                const isError = span.status === "error";
                const isSelected = span.id === selectedSpanId;
                const barColor = isError ? "bg-red-500" : KIND_COLORS[span.kind] || KIND_COLORS.internal;

                return (
                  <button
                    key={span.id}
                    onClick={() => setSelectedSpanId(isSelected ? null : span.id)}
                    className={`w-full flex items-center gap-2 py-1.5 px-2 rounded-lg transition-colors text-left ${
                      isSelected ? "bg-accent/10 ring-1 ring-accent/30" : "hover:bg-surface-50"
                    }`}
                  >
                    {/* Name with indent */}
                    <div className="w-40 flex-shrink-0 truncate text-xs" style={{ paddingLeft: `${depth * 16}px` }}>
                      <span className={`w-2 h-2 rounded-full inline-block mr-1.5 ${STATUS_DOT[span.status] || STATUS_DOT.unset}`} />
                      <span className={isError ? "text-red-400" : "text-primary"}>{span.name}</span>
                    </div>

                    {/* Bar */}
                    <div className="flex-1 h-5 relative bg-surface-200/20 rounded overflow-hidden">
                      <div
                        className={`absolute top-0 h-full rounded ${barColor} opacity-80`}
                        style={{ left: `${leftPct}%`, width: `${Math.min(widthPct, 100 - leftPct)}%`, minWidth: "2px" }}
                      />
                    </div>

                    {/* Duration */}
                    <div className="w-16 flex-shrink-0 text-right text-[10px] font-mono text-t-secondary">
                      {formatDuration(span.duration_ms || null)}
                    </div>
                  </button>
                );
              })}
            </div>
          )}

          {/* Legend */}
          <div className="flex items-center gap-4 mt-4 pt-3 border-t border-visible text-[10px] text-t-secondary">
            <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-blue-500" /> Internal</span>
            <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-amber-500" /> Client (LLM/HTTP)</span>
            <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-emerald-500" /> Server</span>
            <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-red-500" /> Error</span>
          </div>
        </div>

        {/* Attributes panel */}
        {selectedSpan && (
          <div className="w-80 flex-shrink-0 bg-surface-100 rounded-2xl border border-visible p-4">
            <h3 className="text-xs font-semibold text-t-secondary uppercase mb-3">
              Span: {selectedSpan.name}
            </h3>
            <div className="space-y-3 text-xs">
              <div className="flex justify-between">
                <span className="text-t-secondary">Kind</span>
                <span className="text-primary capitalize">{selectedSpan.kind}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-t-secondary">Status</span>
                <span className={selectedSpan.status === "error" ? "text-red-400" : "text-emerald-400"}>{selectedSpan.status}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-t-secondary">Duration</span>
                <span className="text-primary font-mono">{formatDuration(selectedSpan.duration_ms || null)}</span>
              </div>

              {selectedSpan.error_message && (
                <div className="bg-red-500/10 border border-red-500/20 rounded-lg px-2 py-1.5 text-red-300 break-all">
                  {selectedSpan.error_message}
                </div>
              )}

              {selectedSpan.attributes && Object.keys(selectedSpan.attributes).length > 0 && (
                <div>
                  <p className="text-t-secondary font-semibold mb-1.5 uppercase text-[10px]">Attributes</p>
                  <div className="space-y-1 bg-surface-50 rounded-lg p-2">
                    {Object.entries(selectedSpan.attributes).map(([k, v]) => (
                      <div key={k} className="flex justify-between gap-2">
                        <span className="text-t-secondary truncate">{k}</span>
                        <span className="text-primary font-mono text-right truncate max-w-[140px]" title={String(v)}>
                          {typeof v === "number" ? (Number.isInteger(v) ? v : v.toFixed(2)) : String(v)}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {selectedSpan.events && selectedSpan.events.length > 0 && (
                <div>
                  <p className="text-t-secondary font-semibold mb-1.5 uppercase text-[10px]">Events</p>
                  <div className="space-y-1">
                    {selectedSpan.events.map((ev: any, i: number) => (
                      <div key={i} className="bg-surface-50 rounded-lg p-2">
                        <p className="text-primary font-medium">{ev.name}</p>
                        {ev.attributes && Object.entries(ev.attributes).map(([k, v]) => (
                          <p key={k} className="text-t-secondary">{k}: {String(v)}</p>
                        ))}
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
