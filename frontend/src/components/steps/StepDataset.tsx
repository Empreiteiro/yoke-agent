"use client";

import { useState } from "react";
import { Database, Loader2, Sparkles, CheckCircle, AlertCircle } from "lucide-react";
import { api } from "@/lib/api";

interface StepDatasetProps {
  documentIds: number[];
  onComplete: (datasetId: number) => void;
}

export default function StepDataset({ documentIds, onComplete }: StepDatasetProps) {
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [generating, setGenerating] = useState(false);
  const [progress, setProgress] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const pollForCompletion = async (datasetId: number): Promise<{ success: boolean; errorMessage?: string }> => {
    const maxAttempts = 120;
    for (let i = 0; i < maxAttempts; i++) {
      await new Promise((r) => setTimeout(r, 2000));
      try {
        const dataset = await api.getDataset(datasetId);
        if (dataset.status === "generated") {
          const itemCount = dataset.items?.length ?? 0;
          setProgress(`Generated ${itemCount} Q&A pairs successfully!`);
          return { success: true };
        }
        if (dataset.status === "error") {
          return {
            success: false,
            errorMessage: dataset.error_message || "Generation failed. Check your LLM provider configuration.",
          };
        }
        if (dataset.status === "draft") {
          return { success: false, errorMessage: "Generation failed unexpectedly." };
        }
        setProgress(`Generating Q&A pairs from your documents...`);
      } catch {
        // Network error, keep polling
      }
    }
    return { success: false, errorMessage: "Generation timed out. Please try again." };
  };

  const handleCreate = async () => {
    if (!name.trim()) return;
    setError(null);
    setGenerating(true);
    setProgress("Creating dataset...");

    try {
      const dataset = await api.createDataset({
        name: name.trim(),
        description: description.trim() || undefined,
        document_ids: documentIds,
      });

      setProgress("Starting Q&A generation with LLM...");
      await api.generateDataset(dataset.id);

      setProgress("Generating Q&A pairs from your documents...");
      const result = await pollForCompletion(dataset.id);

      if (result.success) {
        setTimeout(() => onComplete(dataset.id), 1000);
      } else {
        setError(result.errorMessage || "Dataset generation failed.");
        setGenerating(false);
        setProgress(null);
        onComplete(dataset.id);
      }
    } catch (err: any) {
      setError(err.message);
      setGenerating(false);
      setProgress(null);
    }
  };

  return (
    <div className="space-y-6">
      <div className="bg-surface-100 rounded-2xl border border-surface-200/50 p-8">
        <div className="flex items-center gap-3 mb-6">
          <div className="w-10 h-10 rounded-xl bg-accent/10 flex items-center justify-center">
            <Sparkles className="w-5 h-5 text-accent" />
          </div>
          <div>
            <h3 className="text-lg font-semibold text-primary">Generate Evaluation Dataset</h3>
            <p className="text-sm text-t-secondary">
              An LLM will analyze your documents and generate question-answer pairs for evaluation.
            </p>
          </div>
        </div>

        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-t-hover mb-2">
              Dataset Name
            </label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g., Product Documentation QA"
              disabled={generating}
              className="w-full px-4 py-3 bg-surface-50 border border-surface-200/50 rounded-xl text-primary placeholder-muted focus:outline-none focus:border-accent/50 focus:ring-1 focus:ring-accent/25 disabled:opacity-50"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-t-hover mb-2">
              Description (optional)
            </label>
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Describe the purpose of this evaluation dataset..."
              rows={3}
              disabled={generating}
              className="w-full px-4 py-3 bg-surface-50 border border-surface-200/50 rounded-xl text-primary placeholder-muted focus:outline-none focus:border-accent/50 focus:ring-1 focus:ring-accent/25 resize-none disabled:opacity-50"
            />
          </div>

          <div className="bg-surface-50 rounded-xl p-4 border border-surface-200/50">
            <p className="text-sm text-t-secondary">
              <span className="text-primary font-medium">{documentIds.length}</span> document(s) selected for analysis
            </p>
          </div>

          {progress && (
            <div className="flex items-center gap-3 p-4 bg-accent/5 border border-accent/20 rounded-xl">
              {generating ? (
                <Loader2 className="w-5 h-5 text-accent animate-spin flex-shrink-0" />
              ) : (
                <CheckCircle className="w-5 h-5 text-emerald-400 flex-shrink-0" />
              )}
              <p className="text-sm text-t-hover">{progress}</p>
            </div>
          )}

          {error && (
            <div className="flex items-start gap-3 p-4 bg-red-500/5 border border-red-500/20 rounded-xl">
              <AlertCircle className="w-5 h-5 text-red-400 flex-shrink-0 mt-0.5" />
              <p className="text-sm text-red-400">{error}</p>
            </div>
          )}

          <button
            onClick={handleCreate}
            disabled={generating || !name.trim()}
            className="w-full py-3 px-6 bg-gradient-to-r from-accent to-accent-dark text-primary font-medium rounded-xl hover:opacity-90 transition-opacity disabled:opacity-50 flex items-center justify-center gap-2"
          >
            {generating ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin" />
                Generating Dataset...
              </>
            ) : (
              <>
                <Database className="w-4 h-4" />
                Generate Evaluation Dataset
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  );
}
