"use client";

import { useState, useEffect } from "react";
import { Play, Loader2, CheckCircle, XCircle, Clock } from "lucide-react";
import { api } from "@/lib/api";

interface StepExecutionProps {
  experimentId: number | null;
  onComplete: () => void;
}

export default function StepExecution({ experimentId, onComplete }: StepExecutionProps) {
  const [experiment, setExperiment] = useState<any>(null);
  const [running, setRunning] = useState(false);
  const [loading, setLoading] = useState(true);

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
    try {
      await api.runExperiment(experimentId);
      // Poll for updates
      const interval = setInterval(async () => {
        const data = await api.getExperiment(experimentId);
        setExperiment(data);
        if (data.status === "completed" || data.status === "failed") {
          clearInterval(interval);
          setRunning(false);
        }
      }, 3000);
    } catch (err) {
      console.error("Failed to run experiment:", err);
      setRunning(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20 text-slate-400">
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

  return (
    <div className="space-y-6">
      <div className="bg-surface-100 rounded-2xl border border-surface-200/50 p-8">
        <div className="flex items-center justify-between mb-6">
          <div>
            <h3 className="text-lg font-semibold text-white">Run Experiments</h3>
            <p className="text-sm text-slate-400">
              Execute all {total} combinations and evaluate with RAGAS.
            </p>
          </div>
          {experiment?.status !== "completed" && (
            <button
              onClick={handleRun}
              disabled={running}
              className="px-6 py-3 bg-gradient-to-r from-accent to-accent-dark text-white font-medium rounded-xl hover:opacity-90 disabled:opacity-50 flex items-center gap-2"
            >
              {running ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <Play className="w-4 h-4" />
              )}
              {running ? "Running..." : "Start Execution"}
            </button>
          )}
        </div>

        {/* Progress */}
        <div className="mb-6">
          <div className="flex items-center justify-between text-sm mb-2">
            <span className="text-slate-400">Progress</span>
            <span className="text-white">
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
            <span className="flex items-center gap-1 text-emerald-400">
              <CheckCircle className="w-3 h-3" /> {completed} completed
            </span>
            <span className="flex items-center gap-1 text-red-400">
              <XCircle className="w-3 h-3" /> {failed} failed
            </span>
            <span className="flex items-center gap-1 text-slate-400">
              <Clock className="w-3 h-3" /> {pending} pending
            </span>
          </div>
        </div>

        {/* Combination list */}
        <div className="space-y-2 max-h-96 overflow-y-auto">
          {combinations.map((combo: any, index: number) => (
            <div
              key={combo.id}
              className="flex items-center justify-between px-4 py-3 bg-surface-50 rounded-xl border border-surface-200/50"
            >
              <div className="flex items-center gap-3">
                <span className="text-xs font-mono text-slate-500">#{index + 1}</span>
                <div className="flex items-center gap-2 text-xs">
                  <span className="px-2 py-0.5 bg-accent/10 text-accent rounded">
                    {combo.params.chunk_size}t
                  </span>
                  <span className="px-2 py-0.5 bg-secondary/10 text-secondary rounded">
                    {combo.params.chunk_overlap}%
                  </span>
                  <span className="px-2 py-0.5 bg-surface-200 text-slate-300 rounded">
                    k={combo.params.top_k}
                  </span>
                  <span className="px-2 py-0.5 bg-surface-200 text-slate-300 rounded">
                    {combo.params.search_type}
                  </span>
                </div>
              </div>
              <div className="flex items-center gap-2">
                {combo.overall_score != null && (
                  <span className="text-sm font-medium text-white">
                    {(combo.overall_score * 100).toFixed(1)}%
                  </span>
                )}
                {combo.status === "completed" ? (
                  <CheckCircle className="w-4 h-4 text-emerald-400" />
                ) : combo.status === "failed" ? (
                  <XCircle className="w-4 h-4 text-red-400" />
                ) : combo.status === "running" ? (
                  <Loader2 className="w-4 h-4 text-accent animate-spin" />
                ) : (
                  <Clock className="w-4 h-4 text-slate-500" />
                )}
              </div>
            </div>
          ))}
        </div>
      </div>

      {experiment?.status === "completed" && (
        <button
          onClick={onComplete}
          className="w-full py-3 px-6 bg-gradient-to-r from-emerald-500 to-emerald-600 text-white font-medium rounded-xl hover:opacity-90 transition-opacity"
        >
          View Results Report
        </button>
      )}
    </div>
  );
}
