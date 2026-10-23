"use client";

import { useState, useEffect } from "react";
import { Play, Loader2, CheckCircle, XCircle, Clock, AlertCircle, ChevronDown, ChevronUp, Square, StopCircle, RotateCcw } from "lucide-react";
import { api } from "@/lib/api";
import { useWalkthrough } from "@/contexts/WalkthroughContext";

interface StepExecutionProps {
  experimentId: number | null;
  onComplete: () => void;
}

export default function StepExecution({ experimentId, onComplete }: StepExecutionProps) {
  const { startIfNew } = useWalkthrough();
  useEffect(() => { startIfNew("execution"); }, []); // eslint-disable-line react-hooks/exhaustive-deps
  const [experiment, setExperiment] = useState<any>(null);
  const [running, setRunning] = useState(false);
  const [loading, setLoading] = useState(true);
  const [expandedError, setExpandedError] = useState<number | null>(null);
  const [stopping, setStopping] = useState(false);
  const [pollInterval, setPollInterval] = useState<NodeJS.Timeout | null>(null);

  useEffect(() => {
    if (experimentId) loadExperiment();
  }, [experimentId]);

  const loadExperiment = async () => {
    if (!experimentId) return;
    try {
      const data = await api.getExperiment(experimentId);
      setExperiment(data);
    } catch (err) {
      console.error("Failed to load experiment:", err);
    } finally {
      setLoading(false);
    }
  };

  const handleRun = async () => {
    if (!experimentId) return;
    setRunning(true);
    setStopping(false);
    try {
      await api.runExperiment(experimentId);
      const interval = setInterval(async () => {
        const data = await api.getExperiment(experimentId);
        setExperiment(data);
        if (data.status === "completed" || data.status === "completed_with_errors" || data.status === "failed" || data.status === "stopped") {
          clearInterval(interval);
          setPollInterval(null);
          setRunning(false);
          setStopping(false);
        }
      }, 3000);
      setPollInterval(interval);
    } catch (err) {
      console.error("Failed to run experiment:", err);
      setRunning(false);
    }
  };

  const handleStop = async () => {
    if (!experimentId) return;
    setStopping(true);
    try {
      await api.stopExperiment(experimentId);
    } catch (err) {
      console.error("Failed to stop experiment:", err);
      setStopping(false);
    }
  };

  const handleResume = async (retryFailed: boolean = false) => {
    if (!experimentId) return;
    setRunning(true);
    setStopping(false);
    try {
      await api.resumeExperiment(experimentId, retryFailed);
      const interval = setInterval(async () => {
        const data = await api.getExperiment(experimentId);
        setExperiment(data);
        if (data.status === "completed" || data.status === "completed_with_errors" || data.status === "failed" || data.status === "stopped") {
          clearInterval(interval);
          setPollInterval(null);
          setRunning(false);
          setStopping(false);
        }
      }, 3000);
      setPollInterval(interval);
    } catch (err) {
      console.error("Failed to resume experiment:", err);
      setRunning(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20 text-t-secondary">
        Loading experiment...
      </div>
    );
  }

  const combinations = experiment?.combinations || [];
  const completed = combinations.filter((c: any) => c.status === "completed").length;
  const failed = combinations.filter((c: any) => c.status === "failed").length;
  const pending = combinations.filter((c: any) => c.status === "pending").length;
  const total = combinations.length;
  const progress = total > 0 ? ((completed + failed) / total) * 100 : 0;
  const stuck = combinations.filter((c: any) => c.status === "running").length;
  const stopped = combinations.filter((c: any) => c.status === "stopped").length;
  const incomplete = failed + stopped + stuck;
  const isDone = (experiment?.status === "completed" || experiment?.status === "completed_with_errors") && incomplete === 0;
  const isStopped = experiment?.status === "stopped";
  const isFailed = experiment?.status === "failed" || experiment?.status === "completed_with_errors";
  const canResume = (isStopped || isFailed || incomplete > 0) && experiment?.status !== "running";

  // Get first error message for summary
  const firstError = combinations.find((c: any) => c.status === "failed");
  const errorMessage = firstError?.error_message || firstError?.detailed_results?.error;

  const getErrorText = (combo: any) => {
    return combo.error_message || combo.detailed_results?.error || "Unknown error";
  };

  return (
    <div className="space-y-6">
      <div className="bg-surface-100 rounded-2xl border border-themed p-8">
        <div className="flex items-center justify-end gap-3 mb-6" data-walkthrough="execution-controls">
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
          ) : canResume && !running ? (
            <>
              {failed > 0 && (
                <button
                  onClick={() => handleResume(true)}
                  className="px-5 py-3 bg-orange-500/10 border border-orange-500/30 text-orange-400 font-medium rounded-xl hover:bg-orange-500/20 flex items-center gap-2 text-sm"
                >
                  <RotateCcw className="w-4 h-4" />
                  Resume & Retry Failed ({failed + stopped + stuck})
                </button>
              )}
              <button
                onClick={() => handleResume(false)}
                className="px-5 py-3 bg-accent/10 border border-accent/30 text-accent font-medium rounded-xl hover:bg-accent/20 flex items-center gap-2 text-sm"
              >
                <Play className="w-4 h-4" />
                {stopped + stuck > 0 ? `Resume (${stopped + stuck} remaining)` : `Retry Failed (${failed})`}
              </button>
            </>
          ) : null}
        </div>

        {/* Progress */}
        <div className="mb-6" data-walkthrough="execution-progress">
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
          {combinations.map((combo: any, index: number) => (
            <div key={combo.id}>
              <div
                className={`flex items-center justify-between px-4 py-3 bg-surface-50 border border-themed ${
                  combo.status === "failed" ? "cursor-pointer hover:bg-surface-100" : ""
                } ${expandedError === combo.id ? "rounded-t-xl" : "rounded-xl"}`}
                onClick={() => {
                  if (combo.status === "failed") {
                    setExpandedError(expandedError === combo.id ? null : combo.id);
                  }
                }}
              >
                <div className="flex items-center gap-3">
                  <span className="text-xs font-mono text-muted">#{index + 1}</span>
                  <div className="flex items-center gap-2 text-xs flex-wrap">
                    {combo.params.pipeline_type === "graphrag" && (
                      <span className="px-2 py-0.5 bg-purple-500/10 text-purple-400 rounded text-xs">GraphRAG</span>
                    )}
                    <span className="px-2 py-0.5 bg-accent/10 text-accent rounded">
                      {combo.params.chunk_size}t
                    </span>
                    <span className="px-2 py-0.5 bg-surface-200 text-t-hover rounded">
                      {combo.params.chunking_strategy || "recursive"}
                    </span>
                    <span className="px-2 py-0.5 bg-secondary/10 text-secondary rounded">
                      {combo.params.chunk_overlap}%
                    </span>
                    <span className="px-2 py-0.5 bg-surface-200 text-t-hover rounded">
                      {combo.params.pipeline_type === "graphrag" ? `lvl=${combo.params.community_level ?? "?"}` : `k=${combo.params.top_k}`}
                    </span>
                    <span className="px-2 py-0.5 bg-surface-200 text-t-hover rounded">
                      {combo.params.pipeline_type === "graphrag" ? (combo.params.search_mode || "local") : combo.params.search_type}
                    </span>
                    {combo.params.pipeline_type !== "graphrag" && (
                      <span className="px-2 py-0.5 bg-surface-200 text-t-hover rounded">
                        {combo.params.distance_metric || "cosine"}
                      </span>
                    )}
                    {combo.params.reranker && combo.params.reranker !== "none" && (
                      <span className="px-2 py-0.5 bg-surface-200 text-t-hover rounded">
                        {combo.params.reranker}
                      </span>
                    )}
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  {combo.overall_score != null && (
                    <span className="text-sm font-medium text-primary">
                      {(combo.overall_score * 100).toFixed(1)}%
                    </span>
                  )}
                  {combo.status === "completed" ? (
                    <CheckCircle className="w-4 h-4 text-success" />
                  ) : combo.status === "failed" ? (
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
              {/* Expanded error detail */}
              {expandedError === combo.id && combo.status === "failed" && (
                <div className="px-4 py-3 bg-danger/5 border border-danger/20 border-t-0 rounded-b-xl">
                  <p className="text-xs text-danger font-mono break-words whitespace-pre-wrap">
                    {getErrorText(combo)}
                  </p>
                </div>
              )}
            </div>
          ))}
        </div>
      </div>

      {canResume && !running && (
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
      {!isDone && !running && !canResume && (
        <button
          onClick={handleRun}
          data-walkthrough="execution-start"
          className="w-full py-3 px-6 bg-accent shadow-resting text-accent-foreground font-medium rounded-xl hover:opacity-90 transition-opacity disabled:opacity-50 flex items-center justify-center gap-2"
        >
          <Play className="w-4 h-4" />
          Start Execution
        </button>
      )}

      {/* View Results CTA */}
      {(isDone || (isStopped && completed > 0)) && (
        <button
          onClick={onComplete}
          className="w-full py-3 px-6 bg-accent shadow-resting text-accent-foreground font-medium rounded-xl hover:opacity-90 transition-opacity disabled:opacity-50 flex items-center justify-center gap-2"
        >
          View Results Report
        </button>
      )}
    </div>
  );
}
