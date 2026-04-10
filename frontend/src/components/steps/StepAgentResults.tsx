"use client";

import React, { useState, useEffect, useCallback, useRef, useMemo } from "react";
import { BarChart3, Loader2, AlertCircle, ArrowUpDown, ChevronDown, ChevronRight, ChevronUp, FileText, MessageSquare, Sparkles, Trophy, X } from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { api } from "@/lib/api";

interface StepAgentResultsProps {
  experimentId: number | null;
}

export default function StepAgentResults({ experimentId }: StepAgentResultsProps) {
  const [results, setResults] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [sortBy, setSortBy] = useState("overall_score");
  const [sortDir, setSortDir] = useState<"asc" | "desc">("desc");
  const [generatingReport, setGeneratingReport] = useState(false);
  const [report, setReport] = useState<string | null>(null);
  const [reportCollapsed, setReportCollapsed] = useState(false);
  const reportRef = useRef<HTMLDivElement | null>(null);

  // Transcript modal — opens when clicking a configuration row.
  // Holds the full combo object so we can render its config/stats/metrics
  // in the modal header without re-querying the table.
  const [modalCombo, setModalCombo] = useState<any | null>(null);
  const [transcripts, setTranscripts] = useState<any[]>([]);
  const [transcriptsForCombo, setTranscriptsForCombo] = useState<number | null>(null);
  const [loadingTranscripts, setLoadingTranscripts] = useState(false);
  const [expandedTranscript, setExpandedTranscript] = useState<number | null>(null);
  const [transcriptDetail, setTranscriptDetail] = useState<any>(null);
  const [loadingTranscriptDetail, setLoadingTranscriptDetail] = useState(false);

  const loadResults = useCallback(async () => {
    if (!experimentId) return;
    setLoading(true);
    try {
      const data = await api.getAgentExperimentResults(experimentId);
      setResults(data);
    } catch (err: any) {
      setError(err.message || "Failed to load results");
    } finally {
      setLoading(false);
    }
  }, [experimentId]);

  const loadExistingReport = useCallback(async () => {
    if (!experimentId) return;
    try {
      const data = await api.getAgentReport(experimentId);
      if (data?.report) {
        setReport(data.report);
      }
    } catch {
      // Silent: report may not exist yet
    }
  }, [experimentId]);

  useEffect(() => {
    loadResults();
    loadExistingReport();
  }, [loadResults, loadExistingReport]);

  // When the user arrives via "View Report" from History, URL carries
  // ?focus=report — scroll the report section into view after it loads.
  useEffect(() => {
    if (typeof window === "undefined") return;
    const params = new URLSearchParams(window.location.search);
    if (params.get("focus") !== "report") return;
    if (!report) return;
    // Wait a tick for the report block to paint.
    const t = setTimeout(() => {
      reportRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
    }, 80);
    return () => clearTimeout(t);
  }, [report]);

  const handleGenerateReport = async () => {
    if (!experimentId) return;
    setGeneratingReport(true);
    setError(null);
    try {
      const data = await api.generateAgentReport(experimentId);
      const reportText = data.report || data.content || data.markdown || JSON.stringify(data, null, 2);
      setReport(reportText);
      // Scroll the newly generated report into view.
      setTimeout(() => {
        reportRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
      }, 80);
    } catch (err: any) {
      setError(err.message || "Report generation failed");
    } finally {
      setGeneratingReport(false);
    }
  };

  const loadTranscripts = async (combinationId?: number) => {
    if (!experimentId) return;
    setLoadingTranscripts(true);
    try {
      const data = await api.listTranscripts(experimentId, combinationId);
      setTranscripts(data);
      setTranscriptsForCombo(combinationId ?? null);
    } catch (err: any) {
      setError(err.message || "Failed to load transcripts");
    } finally {
      setLoadingTranscripts(false);
    }
  };

  // Auto-load transcripts whenever the modal opens for a new combo.
  useEffect(() => {
    if (modalCombo == null) return;
    if (transcriptsForCombo === modalCombo.id) return;
    loadTranscripts(modalCombo.id);
    setExpandedTranscript(null);
    setTranscriptDetail(null);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [modalCombo]);

  // Close modal on Escape key.
  useEffect(() => {
    if (!modalCombo) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setModalCombo(null);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [modalCombo]);

  const loadTranscriptDetail = async (transcriptId: number) => {
    if (expandedTranscript === transcriptId) {
      setExpandedTranscript(null);
      setTranscriptDetail(null);
      return;
    }
    setLoadingTranscriptDetail(true);
    setExpandedTranscript(transcriptId);
    try {
      const data = await api.getTranscript(transcriptId);
      setTranscriptDetail(data);
    } catch (err: any) {
      setError(err.message || "Failed to load transcript");
    } finally {
      setLoadingTranscriptDetail(false);
    }
  };

  const toggleSort = (field: string) => {
    if (sortBy === field) {
      setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortBy(field);
      setSortDir("desc");
    }
  };

  if (!experimentId) {
    return (
      <div className="flex flex-col items-center justify-center py-20 text-center">
        <div className="w-14 h-14 rounded-2xl bg-accent/10 flex items-center justify-center mb-4">
          <BarChart3 className="w-7 h-7 text-accent" />
        </div>
        <h2 className="text-xl font-semibold text-primary mb-2">Results &amp; Report</h2>
        <p className="text-sm text-t-secondary max-w-md">
          No experiment selected. Run an experiment first.
        </p>
      </div>
    );
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20 text-t-secondary">
        <Loader2 className="w-5 h-5 animate-spin mr-2" />
        Loading results...
      </div>
    );
  }

  const combinations = results?.combinations || results?.rankings || [];
  const sorted = [...combinations].sort((a: any, b: any) => {
    const aVal = a[sortBy] ?? a.metrics?.[sortBy] ?? 0;
    const bVal = b[sortBy] ?? b.metrics?.[sortBy] ?? 0;
    return sortDir === "desc" ? bVal - aVal : aVal - bVal;
  });

  const best = sorted.length > 0 ? sorted[0] : null;

  // Metric scores are 0-1 ratios, shown as percentages
  const renderMetricValue = (val: any) => {
    if (val === null || val === undefined) return "---";
    if (typeof val === "number") return (val * 100).toFixed(1) + "%";
    return String(val);
  };

  // Raw numeric values (counts, tokens, durations) — shown as-is
  const renderRawValue = (val: any, kind?: "int" | "float" | "currency" | "tokens" | "duration") => {
    if (val === null || val === undefined) return "---";
    if (typeof val !== "number") return String(val);
    if (kind === "currency") return val === 0 ? "---" : `$${val.toFixed(4)}`;
    if (kind === "tokens") return val.toLocaleString();
    if (kind === "duration") return `${val.toFixed(1)}s`;
    if (kind === "int") return Math.round(val).toLocaleString();
    return val.toLocaleString();
  };

  // Only these keys inside a combo represent metrics that should be rendered as %
  const METRIC_KEYS = new Set([
    "overall_score", "faithfulness", "answer_relevancy", "context_precision", "context_recall",
    "answer_similarity", "answer_correctness", "accuracy", "precision", "recall", "f1_score",
    "tool_accuracy", "goal_completion", "instruction_following", "coherence", "relevance",
  ]);

  // Collect the union of metric keys across all combos so the All Results
  // table has a dynamic set of per-scenario metric columns (overall_score
  // is rendered separately as the last highlighted column).
  const metricColumns = useMemo(() => {
    const keys = new Set<string>();
    for (const c of sorted) {
      const metrics = c.aggregated_metrics || c.metrics || {};
      for (const [k, v] of Object.entries(metrics)) {
        if (k === "overall_score") continue;
        if (typeof v !== "number") continue;
        if (METRIC_KEYS.has(k) || k.includes("score") || k.includes("accuracy")) {
          keys.add(k);
        }
      }
    }
    return Array.from(keys);
  }, [sorted]);

  const shortLabel = (key: string) => {
    const words = key.replace(/_/g, " ").split(" ");
    return words.map((w) => w.charAt(0).toUpperCase() + w.slice(1, 6)).join(" ");
  };

  const scoreColor = (val: number | null | undefined) => {
    if (val == null) return "text-t-secondary";
    if (val >= 0.8) return "text-emerald-400";
    if (val >= 0.6) return "text-amber-400";
    return "text-red-400";
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-3">
        <div className="w-10 h-10 rounded-xl bg-accent/20 flex items-center justify-center">
          <BarChart3 className="w-5 h-5 text-accent" />
        </div>
        <div>
          <h2 className="text-lg font-semibold text-primary">Results &amp; Report</h2>
          <p className="text-sm text-t-secondary">View metrics, compare configurations, and generate reports</p>
        </div>
      </div>

      {/* Actions — evaluation runs automatically after the experiment finishes,
          and transcripts are now shown inline inside each expanded combo. The
          optional "Generate Improvement Report" CTA sits at the bottom. */}
      {report && (
        <div className="flex items-center gap-3 flex-wrap">
          <button
            onClick={() => reportRef.current?.scrollIntoView({ behavior: "smooth", block: "start" })}
            className="flex items-center gap-2 px-5 py-2.5 bg-secondary/10 text-secondary font-medium rounded-xl hover:bg-secondary/20 transition-colors"
          >
            <FileText className="w-4 h-4" />
            Jump to Report
          </button>
        </div>
      )}

      {/* Error */}
      {error && (
        <div className="flex items-center gap-2 p-3 bg-red-500/10 border border-red-500/30 rounded-lg text-red-400 text-sm">
          <AlertCircle className="w-4 h-4 flex-shrink-0" />
          {error}
        </div>
      )}

      {/* Best combination */}
      {best && (
        <div className="bg-gradient-to-br from-accent/10 to-secondary/10 rounded-2xl border border-surface-200/50 p-6">
          <div className="flex items-center gap-3 mb-4">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-amber-400 to-amber-600 flex items-center justify-center">
              <Trophy className="w-5 h-5 text-primary" />
            </div>
            <div>
              <h3 className="text-lg font-bold text-primary">Best Configuration</h3>
              <p className="text-sm text-t-secondary">
                Overall Score:{" "}
                <span className="text-accent font-bold">
                  {renderMetricValue(best.overall_score ?? best.metrics?.overall_score)}
                </span>
              </p>
            </div>
          </div>
          <div className="grid grid-cols-3 gap-4 text-sm">
            {best.params?.model && (
              <div>
                <span className="text-t-secondary">Model</span>
                <p className="text-primary font-medium">{best.params.model}</p>
              </div>
            )}
            {best.params?.temperature !== undefined && (
              <div>
                <span className="text-t-secondary">Temperature</span>
                <p className="text-primary font-medium">{best.params.temperature}</p>
              </div>
            )}
            {best.params?.max_turns !== undefined && (
              <div>
                <span className="text-t-secondary">Max Turns</span>
                <p className="text-primary font-medium">{best.params.max_turns}</p>
              </div>
            )}
          </div>
        </div>
      )}

      {/* ── Block 1: All Results ─────────────────────────────────────────── */}
      {sorted.length > 0 && (
        <div className="bg-surface-100 rounded-2xl border border-visible p-6">
          <div className="flex items-center justify-between mb-5">
            <h3 className="text-lg font-semibold text-primary">All Results</h3>
            <span className="text-xs text-t-secondary">
              {sorted.length} configuration{sorted.length !== 1 ? "s" : ""} · click a row to open transcripts
            </span>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-visible">
                  <th className="px-3 py-3 text-left text-xs font-medium text-t-secondary uppercase tracking-wider">Rank</th>
                  <th className="px-3 py-3 text-left text-xs font-medium text-t-secondary uppercase tracking-wider">Model</th>
                  <th className="px-3 py-3 text-left text-xs font-medium text-t-secondary uppercase tracking-wider">Temp</th>
                  <th className="px-3 py-3 text-left text-xs font-medium text-t-secondary uppercase tracking-wider">Turns</th>
                  {metricColumns.map((key) => (
                    <th
                      key={key}
                      className="px-3 py-3 text-left text-xs font-medium text-t-secondary uppercase tracking-wider"
                      title={key.replace(/_/g, " ")}
                    >
                      {shortLabel(key)}
                    </th>
                  ))}
                  <th
                    className="px-3 py-3 text-left text-xs font-medium text-t-secondary uppercase tracking-wider cursor-pointer hover:text-accent"
                    onClick={() => toggleSort("overall_score")}
                  >
                    <span className="flex items-center gap-1">
                      Overall <ArrowUpDown className="w-3 h-3" />
                    </span>
                  </th>
                  <th className="px-3 py-3 text-left text-xs font-medium text-t-secondary uppercase tracking-wider">Sims</th>
                  <th className="px-3 py-3 text-left text-xs font-medium text-t-secondary uppercase tracking-wider">Tokens</th>
                  <th className="px-3 py-3 text-left text-xs font-medium text-t-secondary uppercase tracking-wider">Cost</th>
                  <th className="px-3 py-3 text-left text-xs font-medium text-t-secondary uppercase tracking-wider">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-surface-200/30">
                {sorted.map((c: any, idx: number) => {
                  const p = c.params || {};
                  const metrics = c.aggregated_metrics || c.metrics || {};
                  const overall = c.overall_score ?? metrics.overall_score;
                  const sims = `${c.completed_simulations ?? "—"}/${c.total_simulations ?? "—"}`;
                  return (
                    <tr
                      key={c.id}
                      onClick={() => setModalCombo(c)}
                      className={`hover:bg-surface-50 transition-colors cursor-pointer ${
                        idx === 0 ? "bg-accent/5" : ""
                      }`}
                      title="Click to open transcripts for this configuration"
                    >
                      <td className="px-3 py-3 text-t-hover">
                        <div className="flex items-center gap-1">
                          {idx === 0 ? (
                            <Trophy className="w-4 h-4 text-amber-400" />
                          ) : (
                            `#${idx + 1}`
                          )}
                        </div>
                      </td>
                      <td className="px-3 py-3 text-primary text-xs font-medium">{p.model || `Combo #${c.id}`}</td>
                      <td className="px-3 py-3 text-primary">{p.temperature ?? "—"}</td>
                      <td className="px-3 py-3 text-primary">{p.max_turns ?? "—"}</td>
                      {metricColumns.map((key) => {
                        const val = metrics[key];
                        return (
                          <td key={key} className={`px-3 py-3 font-mono ${scoreColor(typeof val === "number" ? val : null)}`}>
                            {renderMetricValue(val)}
                          </td>
                        );
                      })}
                      <td className="px-3 py-3">
                        <span className={`font-semibold font-mono ${scoreColor(typeof overall === "number" ? overall : null)}`}>
                          {renderMetricValue(overall)}
                        </span>
                      </td>
                      <td className="px-3 py-3 text-t-secondary text-xs font-mono">{sims}</td>
                      <td className="px-3 py-3 text-t-secondary text-xs font-mono">{renderRawValue(c.total_tokens, "tokens")}</td>
                      <td className="px-3 py-3 text-amber-400 text-xs font-mono">{renderRawValue(c.total_cost, "currency")}</td>
                      <td className="px-3 py-3 capitalize text-t-secondary text-xs">{c.status || "—"}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {sorted.length === 0 && !loading && (
        <div className="text-center py-12 text-t-secondary text-sm">
          No results available yet. Run the experiment first — evaluation will start automatically.
        </div>
      )}

      {/* ── Block 2: Improvement Report (bordered, collapsible) ─────────── */}
      {sorted.length > 0 && (
        <div ref={reportRef}>
          {!report ? (
            <div className="bg-surface-100 rounded-2xl border border-visible p-6 space-y-4">
              <div className="flex items-center gap-2">
                <FileText className="w-4 h-4 text-secondary" />
                <h3 className="text-lg font-semibold text-primary">Improvement Report</h3>
              </div>
              <p className="text-xs text-t-secondary">
                Generate an LLM-authored report with prompt improvement suggestions based on this experiment&apos;s metrics and transcripts.
              </p>
              <button
                onClick={handleGenerateReport}
                disabled={generatingReport}
                className="w-full flex items-center justify-center gap-2 px-6 py-2.5 bg-accent text-white font-medium rounded-xl hover:bg-accent/90 transition-colors disabled:opacity-50"
              >
                {generatingReport ? <Loader2 className="w-4 h-4 animate-spin" /> : <FileText className="w-4 h-4" />}
                {generatingReport ? "Generating..." : "Generate Improvement Report"}
              </button>
            </div>
          ) : (
            <div className="bg-surface-100 rounded-2xl border border-visible overflow-hidden">
              {/* Title row — title on the left, regenerate (with AI icon) on the right */}
              <div className="flex items-center justify-between gap-3 px-6 pt-6">
                <h3 className="text-lg font-semibold text-primary flex items-center gap-2">
                  <FileText className="w-4 h-4 text-secondary" />
                  Improvement Report
                </h3>
                <button
                  type="button"
                  onClick={handleGenerateReport}
                  disabled={generatingReport}
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-accent/10 text-accent hover:bg-accent/20 transition-colors text-xs font-medium disabled:opacity-50"
                  title="Regenerate the report with latest metrics"
                >
                  {generatingReport ? (
                    <Loader2 className="w-3.5 h-3.5 animate-spin" />
                  ) : (
                    <Sparkles className="w-3.5 h-3.5" />
                  )}
                  {generatingReport ? "Regenerating…" : "Regenerate"}
                </button>
              </div>

              {/* Expand/collapse toggle row — chevron sits below the title */}
              <button
                type="button"
                onClick={() => setReportCollapsed((v) => !v)}
                className="w-full flex items-center justify-center gap-1.5 py-2 mt-2 text-t-secondary hover:text-accent hover:bg-surface-200/30 transition-colors text-xs"
                aria-expanded={!reportCollapsed}
                title={reportCollapsed ? "Expand report" : "Collapse report"}
              >
                {reportCollapsed ? (
                  <>
                    <ChevronDown className="w-4 h-4" />
                    <span>Show report</span>
                  </>
                ) : (
                  <>
                    <ChevronUp className="w-4 h-4" />
                    <span>Hide report</span>
                  </>
                )}
              </button>

              {!reportCollapsed && (
                <div className="px-6 pb-6">
                  <div className="markdown-report text-sm text-t-secondary leading-relaxed">
                    <ReactMarkdown
                      remarkPlugins={[remarkGfm]}
                      components={{
                        h1: ({ node, ...props }) => (
                          <h1 className="text-primary font-bold text-xl mt-6 mb-3" {...props} />
                        ),
                        h2: ({ node, ...props }) => (
                          <h2 className="text-primary font-bold text-lg mt-6 mb-3" {...props} />
                        ),
                        h3: ({ node, ...props }) => (
                          <h3 className="text-primary font-semibold text-base mt-4 mb-2" {...props} />
                        ),
                        h4: ({ node, ...props }) => (
                          <h4 className="text-primary font-semibold text-sm mt-3 mb-2" {...props} />
                        ),
                        p: ({ node, ...props }) => <p className="my-3" {...props} />,
                        strong: ({ node, ...props }) => (
                          <strong className="text-primary font-semibold" {...props} />
                        ),
                        em: ({ node, ...props }) => <em className="italic" {...props} />,
                        a: ({ node, ...props }) => (
                          <a
                            className="text-accent hover:underline"
                            target="_blank"
                            rel="noopener noreferrer"
                            {...props}
                          />
                        ),
                        ul: ({ node, ...props }) => (
                          <ul className="list-disc pl-6 my-3 space-y-1" {...props} />
                        ),
                        ol: ({ node, ...props }) => (
                          <ol className="list-decimal pl-6 my-3 space-y-1" {...props} />
                        ),
                        li: ({ node, ...props }) => <li className="leading-relaxed" {...props} />,
                        blockquote: ({ node, ...props }) => (
                          <blockquote
                            className="border-l-2 border-accent/50 pl-4 my-3 italic text-t-secondary"
                            {...props}
                          />
                        ),
                        hr: () => <hr className="border-surface-200/50 my-6" />,
                        code: ({ node, inline, className, children, ...props }: any) =>
                          inline ? (
                            <code
                              className="px-1.5 py-0.5 rounded bg-surface-200/60 text-primary font-mono text-xs"
                              {...props}
                            >
                              {children}
                            </code>
                          ) : (
                            <code
                              className="block p-3 rounded-lg bg-surface-200/40 text-primary font-mono text-xs overflow-x-auto whitespace-pre"
                              {...props}
                            >
                              {children}
                            </code>
                          ),
                        pre: ({ node, ...props }) => (
                          <pre className="my-3 overflow-x-auto" {...props} />
                        ),
                        table: ({ node, ...props }) => (
                          <div className="my-4 overflow-x-auto">
                            <table
                              className="w-full text-xs border-collapse border border-surface-200/50"
                              {...props}
                            />
                          </div>
                        ),
                        thead: ({ node, ...props }) => (
                          <thead className="bg-surface-200/40" {...props} />
                        ),
                        th: ({ node, ...props }) => (
                          <th
                            className="border border-surface-200/50 px-3 py-2 text-left text-primary font-semibold"
                            {...props}
                          />
                        ),
                        td: ({ node, ...props }) => (
                          <td className="border border-surface-200/50 px-3 py-2 align-top" {...props} />
                        ),
                      }}
                    >
                      {report}
                    </ReactMarkdown>
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* ── Block 3: Transcripts Modal ──────────────────────────────────── */}
      {modalCombo && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm"
          onClick={() => setModalCombo(null)}
        >
          <div
            className="relative w-full max-w-5xl max-h-[90vh] flex flex-col bg-surface-100 rounded-2xl border border-visible shadow-2xl overflow-hidden"
            onClick={(e) => e.stopPropagation()}
          >
            {/* Modal header */}
            <div className="flex items-start justify-between gap-4 px-6 py-4 border-b border-visible">
              <div className="flex items-center gap-3 min-w-0">
                <div className="w-10 h-10 rounded-xl bg-accent/20 flex items-center justify-center flex-shrink-0">
                  <MessageSquare className="w-5 h-5 text-accent" />
                </div>
                <div className="min-w-0">
                  <h3 className="text-lg font-semibold text-primary truncate">
                    {modalCombo.params?.model || `Combo #${modalCombo.id}`}
                  </h3>
                  <p className="text-xs text-t-secondary">
                    T={modalCombo.params?.temperature ?? "?"} · Turns={modalCombo.params?.max_turns ?? "?"} · Overall{" "}
                    <span className={`font-mono ${scoreColor(modalCombo.overall_score ?? modalCombo.metrics?.overall_score)}`}>
                      {renderMetricValue(modalCombo.overall_score ?? modalCombo.metrics?.overall_score)}
                    </span>
                  </p>
                </div>
              </div>
              <button
                type="button"
                onClick={() => setModalCombo(null)}
                className="flex-shrink-0 w-8 h-8 rounded-lg flex items-center justify-center text-t-secondary hover:text-primary hover:bg-surface-200/40 transition-colors"
                aria-label="Close"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Modal body — execution stats, quality metrics, then transcripts */}
            <div className="flex-1 overflow-y-auto px-6 py-5 space-y-5">
              {/* Execution stats */}
              <div>
                <h4 className="text-[10px] font-semibold text-t-secondary uppercase tracking-wider mb-2">Execution Stats</h4>
                <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
                  <div className="text-sm">
                    <span className="text-t-secondary">Total Simulations</span>
                    <p className="text-primary font-medium font-mono">{renderRawValue(modalCombo.total_simulations, "int")}</p>
                  </div>
                  <div className="text-sm">
                    <span className="text-t-secondary">Completed</span>
                    <p className="text-primary font-medium font-mono">{renderRawValue(modalCombo.completed_simulations, "int")}</p>
                  </div>
                  <div className="text-sm">
                    <span className="text-t-secondary">Failed</span>
                    <p className={`font-medium font-mono ${(modalCombo.failed_simulations ?? 0) > 0 ? "text-red-400" : "text-primary"}`}>
                      {renderRawValue(modalCombo.failed_simulations, "int")}
                    </p>
                  </div>
                  <div className="text-sm">
                    <span className="text-t-secondary">Duration</span>
                    <p className="text-primary font-medium font-mono">{renderRawValue(modalCombo.duration_seconds, "duration")}</p>
                  </div>
                  <div className="text-sm">
                    <span className="text-t-secondary">Tokens Used</span>
                    <p className="text-primary font-medium font-mono">{renderRawValue(modalCombo.total_tokens, "tokens")}</p>
                  </div>
                  <div className="text-sm">
                    <span className="text-t-secondary">Estimated Cost</span>
                    <p className="text-primary font-medium font-mono">{renderRawValue(modalCombo.total_cost, "currency")}</p>
                  </div>
                </div>
              </div>

              {/* Quality metrics */}
              {(() => {
                const metrics = modalCombo.aggregated_metrics || modalCombo.metrics || {};
                const metricEntries = Object.entries(metrics).filter(([k, v]) =>
                  typeof v === "number" && (METRIC_KEYS.has(k) || k.includes("score") || k.includes("accuracy"))
                );
                if (metricEntries.length === 0) return null;
                return (
                  <div>
                    <h4 className="text-[10px] font-semibold text-t-secondary uppercase tracking-wider mb-2">Quality Metrics</h4>
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                      {metricEntries.map(([key, val]) => (
                        <div key={key} className="text-sm">
                          <span className="text-t-secondary capitalize">{key.replace(/_/g, " ")}</span>
                          <p className={`font-medium font-mono ${scoreColor(val as number)}`}>{renderMetricValue(val)}</p>
                        </div>
                      ))}
                    </div>
                  </div>
                );
              })()}

              {/* Transcripts */}
              <div>
                <h4 className="text-[10px] font-semibold text-t-secondary uppercase tracking-wider mb-2 flex items-center gap-2">
                  <MessageSquare className="w-3.5 h-3.5" />
                  Transcripts
                  {!loadingTranscripts && transcripts.length > 0 && (
                    <span className="text-t-secondary/80 normal-case">({transcripts.length})</span>
                  )}
                </h4>
                {loadingTranscripts ? (
                  <div className="flex items-center justify-center py-8 text-t-secondary text-xs">
                    <Loader2 className="w-4 h-4 animate-spin mr-2" />
                    Loading transcripts...
                  </div>
                ) : transcripts.length === 0 ? (
                  <p className="text-xs text-t-secondary py-4">No transcripts for this configuration.</p>
                ) : (
                  <div className="space-y-2">
                    {transcripts.map((t) => (
                      <div key={t.id} className="border border-surface-200/50 rounded-lg overflow-hidden">
                        <button
                          onClick={() => loadTranscriptDetail(t.id)}
                          className="w-full flex items-center justify-between px-4 py-3 hover:bg-surface-200/20 transition-colors text-left"
                        >
                          <div>
                            <span className="text-sm font-medium text-primary">
                              {t.persona_name || t.scenario_name || `Transcript #${t.id}`}
                            </span>
                            {t.scenario_name && (
                              <span className="ml-2 text-xs text-t-secondary">{t.scenario_name}</span>
                            )}
                          </div>
                          {expandedTranscript === t.id ? (
                            <ChevronDown className="w-4 h-4 text-t-secondary" />
                          ) : (
                            <ChevronRight className="w-4 h-4 text-t-secondary" />
                          )}
                        </button>
                        {expandedTranscript === t.id && (
                          <div className="px-4 pb-4 border-t border-surface-200/50">
                            {loadingTranscriptDetail ? (
                              <div className="flex items-center justify-center py-6 text-t-secondary text-sm">
                                <Loader2 className="w-4 h-4 animate-spin mr-2" />
                                Loading transcript...
                              </div>
                            ) : transcriptDetail ? (
                              <div className="space-y-2 mt-3">
                                {(transcriptDetail.messages || transcriptDetail.turns || []).map((msg: any, idx: number) => (
                                  <div
                                    key={idx}
                                    className={`p-3 rounded-lg text-sm ${
                                      msg.role === "user" || msg.role === "persona"
                                        ? "bg-surface-200/30 text-t-secondary"
                                        : "bg-accent/10 text-primary"
                                    }`}
                                  >
                                    <span className="text-xs font-semibold uppercase text-t-secondary/70 block mb-1">
                                      {msg.role || "unknown"}
                                    </span>
                                    <p className="whitespace-pre-wrap">{msg.content || msg.text || "---"}</p>
                                    {msg.tool_calls && msg.tool_calls.length > 0 && (
                                      <div className="mt-2 space-y-1">
                                        {msg.tool_calls.map((tc: any, i: number) => (
                                          <div key={i} className="text-xs font-mono bg-surface-200/30 rounded p-2 text-t-secondary">
                                            Tool: {tc.name || tc.function?.name || "unknown"}
                                          </div>
                                        ))}
                                      </div>
                                    )}
                                  </div>
                                ))}
                              </div>
                            ) : (
                              <p className="text-sm text-t-secondary py-4">No detail available.</p>
                            )}
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
