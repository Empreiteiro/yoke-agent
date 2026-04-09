"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import { Play, Loader2, CheckCircle, XCircle, Clock, AlertCircle, Square, RotateCcw } from "lucide-react";
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
        if (s.status === "completed" || s.status === "completed_with_errors") {
          onComplete?.();
        }
      }
    } catch (err: any) {
      setError(err.message || "Failed to load status");
    }
  }, [selectedExpId, onComplete]);

  useEffect(() => {
    if (selectedExpId) loadStatus();
  }, [selectedExpId, loadStatus]);

  // Cleanup poll on unmount
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

  const completedCount = combinations.filter((c) => c.status === "completed").length;
  const failedCount = combinations.filter((c) => c.status === "failed" || c.status === "error").length;
  const runningCount = combinations.filter((c) => c.status === "running").length;
  const totalCount = combinations.length;
  const progress = totalCount > 0 ? ((completedCount + failedCount) / totalCount) * 100 : 0;

  const statusIcon = (s: string) => {
    switch (s) {
      case "completed":
        return <CheckCircle className="w-4 h-4 text-green-400" />;
      case "running":
        return <Loader2 className="w-4 h-4 text-accent animate-spin" />;
      case "failed":
      case "error":
        return <XCircle className="w-4 h-4 text-red-400" />;
      default:
        return <Clock className="w-4 h-4 text-t-secondary" />;
    }
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
      {/* Header */}
      <div className="flex items-center gap-3">
        <div className="w-10 h-10 rounded-xl bg-accent/20 flex items-center justify-center">
          <Play className="w-5 h-5 text-accent" />
        </div>
        <div>
          <h2 className="text-lg font-semibold text-primary">Experiment Execution</h2>
          <p className="text-sm text-t-secondary">Run simulated conversations across all combinations</p>
        </div>
      </div>

      {/* Experiment selector */}
      {!experimentId && experiments.length > 0 && (
        <div className="bg-surface-100 rounded-xl border border-surface-200/50 p-4">
          <label className="block text-sm font-medium text-t-secondary mb-2">Select Experiment</label>
          <select
            value={selectedExpId ?? ""}
            onChange={(e) => setSelectedExpId(e.target.value ? Number(e.target.value) : null)}
            className="w-full px-3 py-2 bg-surface-100 border border-surface-200/50 rounded-lg text-primary text-sm focus:outline-none focus:ring-2 focus:ring-accent/40"
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
          {/* Status summary */}
          {status && (
            <div className="bg-surface-100 rounded-xl border border-surface-200/50 p-5 space-y-4">
              <div className="flex items-center justify-between">
                <div>
                  <span className="text-sm text-t-secondary">Status</span>
                  <p className="text-lg font-semibold text-primary capitalize">{status.status || "pending"}</p>
                </div>
                <div className="text-right text-sm text-t-secondary">
                  <p>{completedCount} / {totalCount} completed</p>
                  {failedCount > 0 && <p className="text-red-400">{failedCount} failed</p>}
                  {runningCount > 0 && <p className="text-accent">{runningCount} running</p>}
                </div>
              </div>

              {/* Progress bar */}
              <div className="w-full h-3 bg-surface-200/50 rounded-full overflow-hidden">
                <div
                  className="h-full bg-gradient-to-r from-accent to-secondary rounded-full transition-all duration-500"
                  style={{ width: `${progress}%` }}
                />
              </div>
              <p className="text-xs text-t-secondary text-right">{progress.toFixed(0)}%</p>
            </div>
          )}

          {/* Controls */}
          <div className="flex items-center gap-3">
            {(!running && status?.status !== "completed") && (
              <button
                onClick={handleRun}
                className="flex items-center gap-2 px-6 py-2.5 bg-accent text-primary font-medium rounded-xl hover:bg-accent/90 transition-colors"
              >
                <Play className="w-4 h-4" />
                {status?.status === "stopped" || status?.status === "failed" ? "Resume" : "Start"}
              </button>
            )}
            {running && !stopping && (
              <button
                onClick={handleStop}
                className="flex items-center gap-2 px-6 py-2.5 bg-red-500/20 text-red-400 font-medium rounded-xl hover:bg-red-500/30 transition-colors"
              >
                <Square className="w-4 h-4" />
                Stop
              </button>
            )}
            {stopping && (
              <div className="flex items-center gap-2 px-6 py-2.5 text-t-secondary text-sm">
                <Loader2 className="w-4 h-4 animate-spin" />
                Stopping...
              </div>
            )}
            <button
              onClick={loadStatus}
              className="flex items-center gap-2 px-4 py-2.5 bg-surface-200/50 text-t-secondary rounded-xl hover:text-primary transition-colors text-sm"
            >
              <RotateCcw className="w-4 h-4" />
              Refresh
            </button>
          </div>

          {/* Error */}
          {error && (
            <div className="flex items-center gap-2 p-3 bg-red-500/10 border border-red-500/30 rounded-lg text-red-400 text-sm">
              <AlertCircle className="w-4 h-4 flex-shrink-0" />
              {error}
            </div>
          )}

          {/* Combination status grid */}
          {combinations.length > 0 && (
            <div className="bg-surface-100 rounded-xl border border-surface-200/50 p-5 space-y-3">
              <h3 className="text-sm font-semibold text-primary uppercase tracking-wider">
                Combinations ({combinations.length})
              </h3>
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
                {combinations.map((c) => (
                  <div
                    key={c.id}
                    className={`flex items-center gap-3 p-3 rounded-lg border transition-colors ${
                      c.status === "completed"
                        ? "border-green-500/30 bg-green-500/5"
                        : c.status === "failed" || c.status === "error"
                        ? "border-red-500/30 bg-red-500/5"
                        : c.status === "running"
                        ? "border-accent/30 bg-accent/5"
                        : "border-surface-200/50 bg-surface-100"
                    }`}
                  >
                    {statusIcon(c.status)}
                    <div className="flex-1 min-w-0">
                      <p className="text-xs font-medium text-primary truncate">
                        {c.model || c.label || `Combo #${c.id}`}
                      </p>
                      <p className="text-xs text-t-secondary truncate">
                        T={c.temperature ?? "?"} | Turns={c.max_turns ?? "?"}
                      </p>
                    </div>
                    <span className="text-xs text-t-secondary capitalize">{c.status || "pending"}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}
