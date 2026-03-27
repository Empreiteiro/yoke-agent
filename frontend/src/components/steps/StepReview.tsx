"use client";

import { useState, useEffect, useRef } from "react";
import { CheckCircle, Plus, Upload, Trash2, Edit3, Save, X, Loader2, AlertCircle } from "lucide-react";
import { api } from "@/lib/api";

interface StepReviewProps {
  datasetId: number | null;
  onComplete: () => void;
}

export default function StepReview({ datasetId, onComplete }: StepReviewProps) {
  const [dataset, setDataset] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [editData, setEditData] = useState({ question: "", ground_truth: "" });
  const [newItem, setNewItem] = useState({ question: "", ground_truth: "", context: "" });
  const [showAddForm, setShowAddForm] = useState(false);
  const [isGenerating, setIsGenerating] = useState(false);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    if (datasetId) loadDataset();
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, [datasetId]);

  const loadDataset = async () => {
    if (!datasetId) return;
    try {
      const data = await api.getDataset(datasetId);
      setDataset(data);

      // If still generating, poll for completion
      if (data.status === "generating") {
        setIsGenerating(true);
        pollRef.current = setInterval(async () => {
          try {
            const updated = await api.getDataset(datasetId);
            setDataset(updated);
            if (updated.status !== "generating") {
              setIsGenerating(false);
              if (pollRef.current) clearInterval(pollRef.current);
            }
          } catch {}
        }, 2000);
      }
    } catch (err) {
      console.error("Failed to load dataset:", err);
    } finally {
      setLoading(false);
    }
  };

  const handleAddItem = async () => {
    if (!datasetId || !newItem.question.trim() || !newItem.ground_truth.trim()) return;
    try {
      await api.addDatasetItem(datasetId, newItem);
      setNewItem({ question: "", ground_truth: "", context: "" });
      setShowAddForm(false);
      await loadDataset();
    } catch (err) {
      console.error("Failed to add item:", err);
    }
  };

  const handleDeleteItem = async (itemId: number) => {
    if (!datasetId) return;
    try {
      await api.deleteDatasetItem(datasetId, itemId);
      await loadDataset();
    } catch (err) {
      console.error("Failed to delete item:", err);
    }
  };

  const startEdit = (item: any) => {
    setEditingId(item.id);
    setEditData({ question: item.question, ground_truth: item.ground_truth });
  };

  const saveEdit = async (itemId: number) => {
    if (!datasetId) return;
    try {
      await api.updateDatasetItem(datasetId, itemId, editData);
      setEditingId(null);
      await loadDataset();
    } catch (err) {
      console.error("Failed to update item:", err);
    }
  };

  const handleImport = async (e: React.ChangeEvent<HTMLInputElement>) => {
    if (!datasetId || !e.target.files?.[0]) return;
    try {
      await api.importDatasetItems(datasetId, e.target.files[0]);
      await loadDataset();
    } catch (err) {
      console.error("Failed to import:", err);
    }
  };

  const handleApprove = async () => {
    if (!datasetId) return;
    try {
      await api.approveDataset(datasetId);
      onComplete();
    } catch (err) {
      console.error("Failed to approve:", err);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20 text-t-secondary">
        Loading dataset...
      </div>
    );
  }

  const itemCount = dataset?.items?.length ?? 0;
  const hasError = dataset?.status === "error";

  return (
    <div className="space-y-6">
      <div className="bg-surface-100 rounded-2xl border border-surface-200/50 p-8">
        <div className="flex items-center justify-end mb-6">
          <div className="flex items-center gap-2">
            <label className="px-4 py-2 bg-surface-200 text-t-hover text-sm font-medium rounded-xl hover:bg-surface-300 transition-colors cursor-pointer flex items-center gap-2">
              <Upload className="w-4 h-4" />
              Import JSON
              <input type="file" accept=".json" onChange={handleImport} className="hidden" />
            </label>
            <button
              onClick={() => setShowAddForm(true)}
              className="px-4 py-2 bg-accent/10 text-accent text-sm font-medium rounded-xl hover:bg-accent/20 transition-colors flex items-center gap-2"
            >
              <Plus className="w-4 h-4" />
              Add Item
            </button>
          </div>
        </div>

        {/* Error message from generation */}
        {hasError && dataset?.error_message && (
          <div className="mb-4 flex items-start gap-3 p-4 bg-red-500/5 border border-red-500/20 rounded-xl">
            <AlertCircle className="w-5 h-5 text-red-400 flex-shrink-0 mt-0.5" />
            <div>
              <p className="text-sm text-red-400 font-medium">Dataset generation failed</p>
              <p className="text-sm text-red-400/80 mt-1">{dataset.error_message}</p>
              <p className="text-sm text-slate-400 mt-2">
                You can add items manually or import a JSON file to continue.
              </p>
            </div>
          </div>
        )}

        {/* Add form */}
        {showAddForm && (
          <div className="mb-6 p-4 bg-surface-50 rounded-xl border border-accent/20">
            <h4 className="text-sm font-medium text-primary mb-3">Add New Q&A Pair</h4>
            <div className="space-y-3">
              <input
                type="text"
                value={newItem.question}
                onChange={(e) => setNewItem((prev) => ({ ...prev, question: e.target.value }))}
                placeholder="Question"
                className="w-full px-3 py-2 bg-surface-100 border border-surface-200/50 rounded-lg text-primary text-sm placeholder-muted focus:outline-none focus:border-accent/50"
              />
              <textarea
                value={newItem.ground_truth}
                onChange={(e) => setNewItem((prev) => ({ ...prev, ground_truth: e.target.value }))}
                placeholder="Expected answer (ground truth)"
                rows={2}
                className="w-full px-3 py-2 bg-surface-100 border border-surface-200/50 rounded-lg text-primary text-sm placeholder-muted focus:outline-none focus:border-accent/50 resize-none"
              />
              <div className="flex gap-2">
                <button
                  onClick={handleAddItem}
                  className="px-4 py-2 bg-accent text-primary text-sm rounded-lg hover:bg-accent-dark"
                >
                  Add
                </button>
                <button
                  onClick={() => setShowAddForm(false)}
                  className="px-4 py-2 bg-surface-200 text-t-hover text-sm rounded-lg hover:bg-surface-300"
                >
                  Cancel
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Generation in progress indicator */}
        {isGenerating && (
          <div className="mb-4 flex items-center gap-3 p-4 bg-accent/5 border border-accent/20 rounded-xl">
            <Loader2 className="w-5 h-5 text-accent animate-spin flex-shrink-0" />
            <p className="text-sm text-t-hover">
              Generating Q&A pairs from your documents... This may take a moment.
            </p>
          </div>
        )}

        {/* Items table */}
        <div className="space-y-2">
          {dataset?.items?.map((item: any, index: number) => (
            <div
              key={item.id}
              className="p-4 bg-surface-50 rounded-xl border border-surface-200/50"
            >
              {editingId === item.id ? (
                <div className="space-y-2">
                  <input
                    type="text"
                    value={editData.question}
                    onChange={(e) => setEditData((prev) => ({ ...prev, question: e.target.value }))}
                    className="w-full px-3 py-2 bg-surface-100 border border-surface-200/50 rounded-lg text-primary text-sm focus:outline-none focus:border-accent/50"
                  />
                  <textarea
                    value={editData.ground_truth}
                    onChange={(e) => setEditData((prev) => ({ ...prev, ground_truth: e.target.value }))}
                    rows={2}
                    className="w-full px-3 py-2 bg-surface-100 border border-surface-200/50 rounded-lg text-primary text-sm focus:outline-none focus:border-accent/50 resize-none"
                  />
                  <div className="flex gap-2">
                    <button
                      onClick={() => saveEdit(item.id)}
                      className="p-1.5 bg-emerald-500/20 text-emerald-400 rounded-lg hover:bg-emerald-500/30"
                    >
                      <Save className="w-3.5 h-3.5" />
                    </button>
                    <button
                      onClick={() => setEditingId(null)}
                      className="p-1.5 bg-surface-200 text-t-secondary rounded-lg hover:bg-surface-300"
                    >
                      <X className="w-3.5 h-3.5" />
                    </button>
                  </div>
                </div>
              ) : (
                <div>
                  <div className="flex items-start justify-between">
                    <div className="flex-1">
                      <div className="flex items-center gap-2 mb-1">
                        <span className="text-xs font-mono text-muted">Q{index + 1}</span>
                        {item.is_manual === 1 && (
                          <span className="text-xs px-2 py-0.5 bg-accent/10 text-accent rounded-full">
                            manual
                          </span>
                        )}
                      </div>
                      <p className="text-sm text-primary mb-2">{item.question}</p>
                      <p className="text-sm text-t-secondary">{item.ground_truth}</p>
                    </div>
                    <div className="flex items-center gap-1 ml-4">
                      <button
                        onClick={() => startEdit(item)}
                        className="p-1.5 hover:bg-surface-200 rounded-lg transition-colors"
                      >
                        <Edit3 className="w-3.5 h-3.5 text-t-secondary" />
                      </button>
                      <button
                        onClick={() => handleDeleteItem(item.id)}
                        className="p-1.5 hover:bg-red-500/10 rounded-lg transition-colors"
                      >
                        <Trash2 className="w-3.5 h-3.5 text-t-secondary hover:text-red-400" />
                      </button>
                    </div>
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>

        {(!dataset?.items || dataset.items.length === 0) && !isGenerating && !hasError && (
          <div className="text-center py-12 text-muted">
            No items in dataset yet. Add items manually or import a JSON file.
          </div>
        )}
      </div>

      {/* Always show the approve button when not generating */}
      {!isGenerating && (
        <button
          onClick={handleApprove}
          disabled={itemCount === 0}
          className="w-full py-3 px-6 bg-gradient-to-r from-emerald-500 to-emerald-600 text-primary font-medium rounded-xl hover:opacity-90 transition-opacity disabled:opacity-40 disabled:cursor-not-allowed flex items-center justify-center gap-2"
        >
          <CheckCircle className="w-4 h-4" />
          {itemCount > 0
            ? `Approve Dataset (${itemCount} items) & Continue`
            : "Add items to continue"}
        </button>
      )}
    </div>
  );
}
