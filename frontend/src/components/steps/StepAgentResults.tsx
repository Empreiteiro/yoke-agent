"use client";

import React, { useState, useEffect, useCallback } from "react";
import { BarChart3, Loader2, AlertCircle, ArrowUpDown, ChevronDown, ChevronRight, FileText, MessageSquare, Sparkles, Trophy } from "lucide-react";
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
  const [expandedCombo, setExpandedCombo] = useState<number | null>(null);
  const [evaluating, setEvaluating] = useState(false);
  const [generatingReport, setGeneratingReport] = useState(false);
  const [report, setReport] = useState<string | null>(null);

  // Transcript browser
  const [transcripts, setTranscripts] = useState<any[]>([]);
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

  useEffect(() => {
    loadResults();
  }, [loadResults]);

  const handleEvaluate = async () => {
    if (!experimentId) return;
    setEvaluating(true);
    setError(null);
    try {
      await api.evaluateAgentExperiment(experimentId);
      await loadResults();
    } catch (err: any) {
      setError(err.message || "Evaluation failed");
    } finally {
      setEvaluating(false);
    }
  };

  const handleGenerateReport = async () => {
    if (!experimentId) return;
    setGeneratingReport(true);
    setError(null);
    try {
      const data = await api.generateAgentReport(experimentId);
      setReport(data.report || data.content || data.markdown || JSON.stringify(data, null, 2));
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
    } catch (err: any) {
      setError(err.message || "Failed to load transcripts");
    } finally {
      setLoadingTranscripts(false);
    }
  };

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

  const renderMetricValue = (val: any) => {
    if (val === null || val === undefined) return "---";
    if (typeof val === "number") return (val * 100).toFixed(1) + "%";
    return String(val);
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

      {/* Actions */}
      <div className="flex items-center gap-3 flex-wrap">
        <button
          onClick={handleEvaluate}
          disabled={evaluating}
          className="flex items-center gap-2 px-5 py-2.5 bg-accent text-primary font-medium rounded-xl hover:bg-accent/90 transition-colors disabled:opacity-50"
        >
          {evaluating ? <Loader2 className="w-4 h-4 animate-spin" /> : <Sparkles className="w-4 h-4" />}
          Evaluate
        </button>
        <button
          onClick={handleGenerateReport}
          disabled={generatingReport}
          className="flex items-center gap-2 px-5 py-2.5 bg-secondary/20 text-secondary font-medium rounded-xl hover:bg-secondary/30 transition-colors disabled:opacity-50"
        >
          {generatingReport ? <Loader2 className="w-4 h-4 animate-spin" /> : <FileText className="w-4 h-4" />}
          Generate Report
        </button>
        <button
          onClick={() => loadTranscripts()}
          disabled={loadingTranscripts}
          className="flex items-center gap-2 px-5 py-2.5 bg-surface-200/50 text-t-secondary font-medium rounded-xl hover:text-primary transition-colors disabled:opacity-50"
        >
          {loadingTranscripts ? <Loader2 className="w-4 h-4 animate-spin" /> : <MessageSquare className="w-4 h-4" />}
          Browse Transcripts
        </button>
      </div>

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
            {best.model && (
              <div>
                <span className="text-t-secondary">Model</span>
                <p className="text-primary font-medium">{best.model}</p>
              </div>
            )}
            {best.temperature !== undefined && (
              <div>
                <span className="text-t-secondary">Temperature</span>
                <p className="text-primary font-medium">{best.temperature}</p>
              </div>
            )}
            {best.max_turns !== undefined && (
              <div>
                <span className="text-t-secondary">Max Turns</span>
                <p className="text-primary font-medium">{best.max_turns}</p>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Ranking table */}
      {sorted.length > 0 && (
        <div className="bg-surface-100 rounded-xl border border-surface-200/50 overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-surface-200/50">
                  <th className="px-4 py-3 text-left text-xs font-semibold text-t-secondary uppercase tracking-wider">#</th>
                  <th className="px-4 py-3 text-left text-xs font-semibold text-t-secondary uppercase tracking-wider">Config</th>
                  <th
                    className="px-4 py-3 text-left text-xs font-semibold text-t-secondary uppercase tracking-wider cursor-pointer hover:text-accent"
                    onClick={() => toggleSort("overall_score")}
                  >
                    <span className="flex items-center gap-1">
                      Overall Score <ArrowUpDown className="w-3 h-3" />
                    </span>
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-semibold text-t-secondary uppercase tracking-wider">Status</th>
                  <th className="px-4 py-3 text-left text-xs font-semibold text-t-secondary uppercase tracking-wider">Details</th>
                </tr>
              </thead>
              <tbody>
                {sorted.map((c: any, idx: number) => {
                  const score = c.overall_score ?? c.metrics?.overall_score;
                  const isExpanded = expandedCombo === c.id;
                  return (
                    <React.Fragment key={c.id}>
                      <tr className="border-b border-surface-200/50 hover:bg-surface-200/20 transition-colors">
                        <td className="px-4 py-3 text-t-secondary">{idx + 1}</td>
                        <td className="px-4 py-3 text-primary">
                          <div>
                            <p className="font-medium">{c.model || `Combo #${c.id}`}</p>
                            <p className="text-xs text-t-secondary">
                              T={c.temperature ?? "?"} | Turns={c.max_turns ?? "?"}
                            </p>
                          </div>
                        </td>
                        <td className="px-4 py-3">
                          <span className="font-mono font-medium text-accent">{renderMetricValue(score)}</span>
                        </td>
                        <td className="px-4 py-3 capitalize text-t-secondary">{c.status || "---"}</td>
                        <td className="px-4 py-3">
                          <button
                            onClick={() => setExpandedCombo(isExpanded ? null : c.id)}
                            className="text-t-secondary hover:text-accent transition-colors"
                          >
                            {isExpanded ? <ChevronDown className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
                          </button>
                        </td>
                      </tr>
                      {isExpanded && (
                        <tr className="border-b border-surface-200/50">
                          <td colSpan={5} className="px-6 py-4 bg-surface-200/10">
                            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                              {Object.entries(c.metrics || c).map(([key, val]) => {
                                if (["id", "status", "model", "temperature", "max_turns", "created_at", "updated_at", "experiment_id", "prompt_variant_id", "overall_score"].includes(key)) return null;
                                if (typeof val !== "number") return null;
                                return (
                                  <div key={key} className="text-sm">
                                    <span className="text-t-secondary capitalize">{key.replace(/_/g, " ")}</span>
                                    <p className="text-primary font-medium font-mono">{renderMetricValue(val)}</p>
                                  </div>
                                );
                              })}
                            </div>
                            <button
                              onClick={() => loadTranscripts(c.id)}
                              className="mt-3 text-xs text-accent hover:underline"
                            >
                              View transcripts for this combination
                            </button>
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

      {sorted.length === 0 && !loading && (
        <div className="text-center py-12 text-t-secondary text-sm">
          No results available yet. Run the experiment and evaluate first.
        </div>
      )}

      {/* Report display */}
      {report && (
        <div className="bg-surface-100 rounded-xl border border-surface-200/50 p-6 space-y-3">
          <h3 className="text-sm font-semibold text-primary uppercase tracking-wider">Report</h3>
          <div
            className="prose prose-invert prose-sm max-w-none text-t-secondary"
            dangerouslySetInnerHTML={{
              __html: report
                .replace(/^### (.*$)/gm, '<h3 class="text-primary font-semibold mt-4 mb-2">$1</h3>')
                .replace(/^## (.*$)/gm, '<h2 class="text-primary font-bold mt-6 mb-3 text-lg">$1</h2>')
                .replace(/^# (.*$)/gm, '<h1 class="text-primary font-bold mt-6 mb-3 text-xl">$1</h1>')
                .replace(/\*\*(.*?)\*\*/g, '<strong class="text-primary">$1</strong>')
                .replace(/\n/g, "<br />"),
            }}
          />
        </div>
      )}

      {/* Transcript browser */}
      {transcripts.length > 0 && (
        <div className="bg-surface-100 rounded-xl border border-surface-200/50 p-6 space-y-3">
          <h3 className="text-sm font-semibold text-primary uppercase tracking-wider">
            Transcripts ({transcripts.length})
          </h3>
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
        </div>
      )}
    </div>
  );
}
