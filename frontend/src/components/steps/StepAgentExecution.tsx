"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import { Play, Loader2, CheckCircle, XCircle, Clock, AlertCircle, Square, StopCircle, RotateCcw, ChevronDown, ChevronUp } from "lucide-react";
import { api } from "@/lib/api";

interface StepAgentExecutionProps {
  experimentId: number | null;
  onComplete?: () => void;
}

export default function StepAgentExecution({ experimentId, onComplete }: StepAgentExecutionProps) {
  const [experiments, setExperiments] = useState<any[]>([]);
  const [selectedExpId, setSelectedExpId] = useState<number | null>(experimentId);
  const [status, setStatus] = useState<any>(null);
  const [combinations, setCombinations] = useState<any[]>([]);
  const [running, setRunning] = useState(false);
  const [stopping, setStopping] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [expandedError, setExpandedError] = useState<number | null>(null);
  const pollRef = useRef<NodeJS.Timeout | null>(null);

  useEffect(() => {
    setSelectedExpId(experimentId);
  }, [experimentId]);

  const loadExperiments = useCallback(async () => {
    try {
      const data = await api.listAgentExperiments();
      setExperiments(data);
    } catch {
      // ignore
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadExperiments();
  }, [loadExperiments]);

  const loadStatus = useCallback(async () => {
    if (!selectedExpId) return;
    try {
      const [s, c] = await Promise.all([
        api.getAgentExperimentStatus(selectedExpId),
        api.getAgentExperimentCombinations(selectedExpId),
      ]);
      setStatus(s);
      setCombinations(c);

      if (s.status === "completed" || s.status === "completed_with_errors" || s.status === "failed" || s.status === "stopped") {
        if (pollRef.current) {
          clearInterval(pollRef.current);
          pollRef.current = null;
        }
        setRunning(false);
        setStopping(false);
      }
    } catch (err: any) {
      setError(err.message || "Failed to load status");
    }
  }, [selectedExpId]);

  useEffect(() => {
    if (selectedExpId) loadStatus();
  }, [selectedExpId, loadStatus]);

  useEffect(() => {
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, []);

  const startPolling = () => {
    if (pollRef.current) clearInterval(pollRef.current);
    pollRef.current = setInterval(() => {
      loadStatus();
    }, 3000);
  };

  const handleRun = async () => {
    if (!selectedExpId) return;
    setRunning(true);
    setError(null);
    try {
      await api.runAgentExperiment(selectedExpId);
      startPolling();
    } catch (err: any) {
      setError(err.message || "Failed to run experiment");
      setRunning(false);
    }
  };

  const handleStop = async () => {
    if (!selectedExpId) return;
    setStopping(true);
    try {
      await api.stopAgentExperiment(selectedExpId);
    } catch (err: any) {
      setError(err.message || "Failed to stop experiment");
      setStopping(false);
    }
  };

  const handleResume = async (retryFailed: boolean = false) => {
    if (!selectedExpId) return;
    setRunning(true);
    setError(null);
    try {
      await api.resumeAgentExperiment(selectedExpId, retryFailed);
      startPolling();
    } catch (err: any) {
      setError(err.message || "Failed to resume experiment");
      setRunning(false);
    }
  };

  const completed = combinations.filter((c) => c.status === "completed").length;
  const failed = combinations.filter((c) => c.status === "failed" || c.status === "error").length;
  const pending = combinations.filter((c) => c.status === "pending" || !c.status).length;
  const stopped = combinations.filter((c) => c.status === "stopped").length;
  const total = combinations.length;
  const progress = total > 0 ? ((completed + failed) / total) * 100 : 0;

  const isDone = (status?.status === "completed" || status?.status === "completed_with_errors") && failed === 0;
  const isStopped = status?.status === "stopped";
  const isFailed = status?.status === "failed" || status?.status === "completed_with_errors";
  const canResume = (isStopped || isFailed || (failed + stopped) > 0) && status?.status !== "running" && !running;

  const firstError = combinations.find((c: any) => c.status === "failed" || c.status === "error");
  const errorMessage = firstError?.error_message || firstError?.detailed_results?.error;

  const getErrorText = (combo: any) => {
    return combo.error_message || combo.detailed_results?.error || "Unknown error";
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20 text-t-secondary">
        <Loader2 className="w-5 h-5 animate-spin mr-2" />
        Loading...
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Experiment selector — only when no prop provided */}
      {!experimentId && experiments.length > 0 && (
        <div className="bg-surface-100 rounded-xl border border-themed p-4">
          <label className="block text-sm font-medium text-t-secondary mb-2">Select Experiment</label>
          <select
            value={selectedExpId ?? ""}
            onChange={(e) => setSelectedExpId(e.target.value ? Number(e.target.value) : null)}
            className="w-full px-3 py-2 bg-surface-100 border border-themed rounded-lg text-primary text-sm focus:outline-none focus:border-accent"
          >
            <option value="">Choose an experiment...</option>
            {experiments.map((exp) => (
              <option key={exp.id} value={exp.id}>
                {exp.name} ({exp.status})
              </option>
            ))}
          </select>
        </div>
      )}

      {!selectedExpId ? (
        <div className="text-center py-12 text-t-secondary text-sm">
          No experiment selected. Create one in the Grid Search step or select from the list above.
        </div>
      ) : (
        <>
          <div className="bg-surface-100 rounded-2xl border border-themed p-8">
            {/* Top controls */}
            <div className="flex items-center justify-end gap-3 mb-6">
              {running ? (
                <button
                  onClick={handleStop}
                  disabled={stopping}
                  className="px-6 py-3 bg-danger/10 border border-danger/30 text-danger font-medium rounded-xl hover:bg-danger/20 disabled:opacity-50 flex items-center gap-2"
                >
                  {stopping ? (
                    <Loader2 className="w-4 h-4 animate-spin" />
                  ) : (
                    <Square className="w-4 h-4" />
                  )}
                  {stopping ? "Stopping..." : "Stop Execution"}
                </button>
              ) : canResume ? (
                <>
                  {failed > 0 && (
                    <button
                      onClick={() => handleResume(true)}
                      className="px-5 py-3 bg-orange-500/10 border border-orange-500/30 text-orange-400 font-medium rounded-xl hover:bg-orange-500/20 flex items-center gap-2 text-sm"
                    >
                      <RotateCcw className="w-4 h-4" />
                      Resume &amp; Retry Failed ({failed + stopped})
                    </button>
                  )}
                  <button
                    onClick={() => handleResume(false)}
                    className="px-5 py-3 bg-accent/10 border border-accent/30 text-accent font-medium rounded-xl hover:bg-accent/20 flex items-center gap-2 text-sm"
                  >
                    <Play className="w-4 h-4" />
                    {stopped > 0 ? `Resume (${stopped} remaining)` : `Retry Failed (${failed})`}
                  </button>
                </>
              ) : null}
            </div>

            {/* Progress */}
            <div className="mb-6">
              <div className="flex items-center justify-between text-sm mb-2">
                <span className="text-t-secondary">Progress</span>
                <span className="text-primary">
                  {completed + failed}/{total}
                </span>
              </div>
              <div className="w-full h-2 bg-surface-200 rounded-full overflow-hidden">
                <div
                  className="h-full bg-gradient-to-r from-accent to-secondary rounded-full transition-all duration-500"
                  style={{ width: `${progress}%` }}
                />
              </div>
              <div className="flex items-center gap-4 mt-3 text-xs">
                <span className="flex items-center gap-1 text-success">
                  <CheckCircle className="w-3 h-3" /> {completed} completed
                </span>
                <span className="flex items-center gap-1 text-danger">
                  <XCircle className="w-3 h-3" /> {failed} failed
                </span>
                <span className="flex items-center gap-1 text-t-secondary">
                  <Clock className="w-3 h-3" /> {pending} pending
                </span>
                {stopped > 0 && (
                  <span className="flex items-center gap-1 text-orange-400">
                    <StopCircle className="w-3 h-3" /> {stopped} stopped
                  </span>
                )}
              </div>
            </div>

            {/* Error summary when all failed */}
            {failed > 0 && completed === 0 && !running && errorMessage && (
              <div className="mb-6 flex items-start gap-3 p-4 bg-danger/5 border border-danger/20 rounded-xl">
                <AlertCircle className="w-5 h-5 text-danger flex-shrink-0 mt-0.5" />
                <div className="min-w-0">
                  <p className="text-sm text-danger font-medium">All {failed} combinations failed</p>
                  <p className="text-sm text-danger/80 mt-1 break-words">{errorMessage}</p>
                </div>
              </div>
            )}

            {/* Combination list */}
            <div className="space-y-2">
              {combinations.map((combo: any, index: number) => {
                const isError = combo.status === "failed" || combo.status === "error";
                return (
                  <div key={combo.id}>
                    <div
                      className={`flex items-center justify-between px-4 py-3 bg-surface-50 border border-themed ${
                        isError ? "cursor-pointer hover:bg-surface-100" : ""
                      } ${expandedError === combo.id ? "rounded-t-xl" : "rounded-xl"}`}
                      onClick={() => {
                        if (isError) {
                          setExpandedError(expandedError === combo.id ? null : combo.id);
                        }
                      }}
                    >
                      <div className="flex items-center gap-3">
                        <span className="text-xs font-mono text-muted">#{index + 1}</span>
                        <div className="flex items-center gap-2 text-xs">
                          {combo.params?.model && (
                            <span className="px-2 py-0.5 bg-accent/10 text-accent rounded">
                              {combo.params.model}
                            </span>
                          )}
                          {combo.params?.temperature != null && (
                            <span className="px-2 py-0.5 bg-secondary/10 text-secondary rounded">
                              T={combo.params.temperature}
                            </span>
                          )}
                          {combo.params?.max_turns != null && (
                            <span className="px-2 py-0.5 bg-surface-200 text-t-hover rounded">
                              turns={combo.params.max_turns}
                            </span>
                          )}
                          {combo.params?.variant_label && (
                            <span className="px-2 py-0.5 bg-surface-200 text-t-hover rounded">
                              {combo.params.variant_label}
                            </span>
                          )}
                        </div>
                      </div>
                      <div className="flex items-center gap-2">
                        {combo.total_simulations > 0 && combo.status !== "pending" && (
                          <span className="text-xs text-t-secondary">
                            {combo.completed_simulations ?? 0}/{combo.total_simulations}
                          </span>
                        )}
                        {combo.overall_score != null && (
                          <span className="text-sm font-medium text-primary">
                            {(combo.overall_score * 100).toFixed(1)}%
                          </span>
                        )}
                        {combo.status === "completed" ? (
                          <CheckCircle className="w-4 h-4 text-success" />
                        ) : isError ? (
                          <div className="flex items-center gap-1">
                            <XCircle className="w-4 h-4 text-danger" />
                            {expandedError === combo.id ? (
                              <ChevronUp className="w-3 h-3 text-danger" />
                            ) : (
                              <ChevronDown className="w-3 h-3 text-danger" />
                            )}
                          </div>
                        ) : combo.status === "running" ? (
                          <Loader2 className="w-4 h-4 text-accent animate-spin" />
                        ) : combo.status === "stopped" ? (
                          <StopCircle className="w-4 h-4 text-orange-400" />
                        ) : (
                          <Clock className="w-4 h-4 text-muted" />
                        )}
                      </div>
                    </div>
                    {expandedError === combo.id && isError && (
                      <div className="px-4 py-3 bg-danger/5 border border-danger/20 border-t-0 rounded-b-xl">
                        <p className="text-xs text-danger font-mono break-words whitespace-pre-wrap">
                          {getErrorText(combo)}
                        </p>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </div>

          {/* Error */}
          {error && (
            <div className="flex items-center gap-2 p-3 bg-danger/10 border border-danger/30 rounded-lg text-danger text-sm">
              <AlertCircle className="w-4 h-4 flex-shrink-0" />
              {error}
            </div>
          )}

          {canResume && (
            <div className="flex items-start gap-3 p-4 bg-orange-500/5 border border-orange-500/20 rounded-xl">
              <StopCircle className="w-5 h-5 text-orange-400 flex-shrink-0 mt-0.5" />
              <div className="text-sm text-orange-400">
                <p>
                  {isStopped ? "Experiment stopped." : "Experiment finished with errors."}{" "}
                  {completed > 0 && `${completed} completed`}
                  {failed > 0 && `${completed > 0 ? ", " : ""}${failed} failed`}
                  {stopped > 0 && `${completed > 0 || failed > 0 ? ", " : ""}${stopped} stopped`}.
                </p>
                <p className="mt-1 text-orange-400/70">Use the buttons above to resume or retry.</p>
              </div>
            </div>
          )}

          {/* Start Execution CTA */}
          {!isDone && !running && !canResume && (!status?.status || status?.status === "configured" || status?.status === "pending") && (
            <button
              onClick={handleRun}
              className="w-full py-3 px-6 bg-accent shadow-resting text-accent-foreground font-medium rounded-xl hover:opacity-90 transition-opacity disabled:opacity-50 flex items-center justify-center gap-2"
            >
              <Play className="w-4 h-4" />
              Start Execution
            </button>
          )}

          {/* View Results CTA */}
          {(isDone || (isStopped && completed > 0)) && (
            <button
              onClick={() => onComplete?.()}
              className="w-full py-3 px-6 bg-accent shadow-resting text-accent-foreground font-medium rounded-xl hover:opacity-90 transition-opacity disabled:opacity-50 flex items-center justify-center gap-2"
            >
              View Results Report
            </button>
          )}
        </>
      )}
    </div>
  );
}
