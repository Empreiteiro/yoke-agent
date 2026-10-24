"use client";

import { useState, useEffect, useCallback } from "react";
import { FlaskConical, Plus, Trash2, Loader2, AlertCircle, Sparkles, Edit3, X, Check, ChevronDown, ChevronRight } from "lucide-react";
import { api } from "@/lib/api";

interface StepAgentScenariosProps {
  agentConfigId: number | null;
  onComplete?: () => void;
}

const SCENARIO_TYPES = [
  { id: "tool_use", label: "Tool Use", description: "Does the agent call the right tool with correct arguments?" },
  { id: "decision_path", label: "Decision Path", description: "Does the agent follow the correct multi-step logic?" },
  { id: "response_quality", label: "Response Quality", description: "Is the response accurate, relevant, and well-written?" },
  { id: "guardrail", label: "Guardrails", description: "Does the agent respect constraints and refuse correctly?" },
];

const EXPECTED_HINTS: Record<string, string> = {
  tool_use: '{"tool_name": "get_weather", "arguments": {"city": "Paris"}}',
  decision_path: '{"steps": ["search flights", "present options", "confirm booking"]}',
  response_quality: '{"reference_answer": "Our refund policy allows...", "rubric": {"tone": "professional"}}',
  guardrail: '{"expected_behavior": "refuse", "must_contain": ["I cannot"], "must_not_contain": ["password"]}',
};

// Column labels per scenario type
const TYPE_COLUMNS: Record<string, { expected_label: string; expected_keys: string[] }> = {
  tool_use: { expected_label: "Tool Call", expected_keys: ["tool_name", "arguments"] },
  decision_path: { expected_label: "Expected Steps", expected_keys: ["steps"] },
  response_quality: { expected_label: "Reference / Rubric", expected_keys: ["reference_answer", "rubric"] },
  guardrail: { expected_label: "Expected Behavior", expected_keys: ["expected_behavior", "must_contain", "must_not_contain"] },
};

function formatExpectedCell(expected: any, type: string): string {
  if (!expected) return "—";
  const keys = TYPE_COLUMNS[type]?.expected_keys || [];
  if (keys.length === 0) return typeof expected === "string" ? expected : JSON.stringify(expected, null, 2);

  const parts: string[] = [];
  for (const k of keys) {
    if (expected[k] !== undefined) {
      const val = typeof expected[k] === "string" ? expected[k] : JSON.stringify(expected[k]);
      parts.push(`${k}: ${val}`);
    }
  }
  return parts.length > 0 ? parts.join("\n") : JSON.stringify(expected, null, 2);
}

export default function StepAgentScenarios({ agentConfigId, onComplete }: StepAgentScenariosProps) {
  const [activeTab, setActiveTab] = useState("tool_use");
  const [scenarios, setScenarios] = useState<Record<string, any[]>>({
    tool_use: [], decision_path: [], response_quality: [], guardrail: [],
  });
  const [loading, setLoading] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [showAdd, setShowAdd] = useState(false);
  const [expandedId, setExpandedId] = useState<number | null>(null);

  // Form state
  const [formName, setFormName] = useState("");
  const [formObjective, setFormObjective] = useState("");
  const [formInputHint, setFormInputHint] = useState("");
  const [formExpected, setFormExpected] = useState("{}");
  const [formDescription, setFormDescription] = useState("");

  const totalCount = Object.values(scenarios).reduce((sum, arr) => sum + arr.length, 0);

  const loadScenarios = useCallback(async () => {
    if (!agentConfigId) return;
    setLoading(true);
    try {
      const all: Record<string, any[]> = { tool_use: [], decision_path: [], response_quality: [], guardrail: [] };
      for (const t of SCENARIO_TYPES) {
        all[t.id] = await api.listScenarios(agentConfigId, t.id);
      }
      setScenarios(all);
    } catch (err: any) {
      setError(err.message || "Failed to load scenarios");
    } finally {
      setLoading(false);
    }
  }, [agentConfigId]);

  useEffect(() => { loadScenarios(); }, [loadScenarios]);

  const handleGenerate = async () => {
    if (!agentConfigId) return;
    setGenerating(true);
    setError(null);
    try {
      const gen = await api.generateScenarios(agentConfigId, { scenario_type: activeTab, count: 5 });
      setScenarios((prev) => ({ ...prev, [activeTab]: [...prev[activeTab], ...gen] }));
    } catch (err: any) {
      setError(err.message || "Failed to generate scenarios");
    } finally {
      setGenerating(false);
    }
  };

  const handleAdd = async () => {
    if (!agentConfigId || !formName.trim()) return;
    setError(null);
    try {
      let parsed;
      try { parsed = JSON.parse(formExpected); } catch { parsed = { text: formExpected }; }
      const s = await api.createScenario(agentConfigId, {
        name: formName.trim(),
        description: formDescription.trim(),
        scenario_type: activeTab,
        objective: formObjective.trim(),
        input_hint: formInputHint.trim() || undefined,
        expected_output: parsed,
        is_manual: true,
      });
      setScenarios((prev) => ({ ...prev, [activeTab]: [...prev[activeTab], s] }));
      resetForm();
    } catch (err: any) {
      setError(err.message || "Failed to create scenario");
    }
  };

  const handleUpdate = async (id: number) => {
    if (!agentConfigId) return;
    setError(null);
    try {
      let parsed;
      try { parsed = JSON.parse(formExpected); } catch { parsed = { text: formExpected }; }
      const updated = await api.updateScenario(agentConfigId, id, {
        name: formName.trim(),
        description: formDescription.trim(),
        objective: formObjective.trim(),
        input_hint: formInputHint.trim() || undefined,
        expected_output: parsed,
      });
      setScenarios((prev) => ({ ...prev, [activeTab]: prev[activeTab].map((s) => (s.id === id ? updated : s)) }));
      resetForm();
    } catch (err: any) {
      setError(err.message || "Failed to update scenario");
    }
  };

  const handleDelete = async (id: number) => {
    if (!agentConfigId) return;
    try {
      await api.deleteScenario(agentConfigId, id);
      setScenarios((prev) => ({ ...prev, [activeTab]: prev[activeTab].filter((s) => s.id !== id) }));
    } catch (err: any) {
      setError(err.message || "Failed to delete scenario");
    }
  };

  const startEdit = (s: any) => {
    setEditingId(s.id);
    setFormName(s.name || "");
    setFormDescription(s.description || "");
    setFormObjective(s.objective || "");
    setFormInputHint(s.input_hint || "");
    setFormExpected(typeof s.expected_output === "string" ? s.expected_output : JSON.stringify(s.expected_output || {}, null, 2));
    setShowAdd(false);
  };

  const resetForm = () => {
    setEditingId(null);
    setShowAdd(false);
    setFormName("");
    setFormDescription("");
    setFormObjective("");
    setFormInputHint("");
    setFormExpected("{}");
  };

  if (!agentConfigId) {
    return (
      <div className="flex flex-col items-center justify-center py-20 text-center">
        <div className="w-14 h-14 rounded-2xl bg-accent/10 flex items-center justify-center mb-4">
          <FlaskConical className="w-7 h-7 text-accent" />
        </div>
        <h2 className="text-xl font-semibold text-primary mb-2">Create Scenarios</h2>
        <p className="text-sm text-t-secondary max-w-md">
          Please define an agent configuration first before creating scenarios.
        </p>
      </div>
    );
  }

  const currentScenarios = scenarios[activeTab] || [];
  const typeInfo = TYPE_COLUMNS[activeTab] || { expected_label: "Expected Output", expected_keys: [] };

  return (
    <div className="space-y-6">
      {/* Tabs with counts */}
      <div className="flex gap-2 flex-wrap">
        {SCENARIO_TYPES.map((t) => {
          const count = scenarios[t.id]?.length || 0;
          return (
            <button
              key={t.id}
              onClick={() => { setActiveTab(t.id); resetForm(); }}
              className={`px-4 py-2 rounded-lg text-sm font-medium border transition-colors flex items-center gap-2 ${
                activeTab === t.id
                  ? "bg-accent/20 border-accent text-accent"
                  : "bg-surface-100 border-themed text-t-secondary hover:text-primary hover:border-themed"
              }`}
            >
              {t.label}
              {count > 0 && (
                <span className={`px-1.5 py-0.5 rounded-full text-xs font-medium ${
                  activeTab === t.id ? "bg-accent/30 text-accent" : "bg-surface-200/50 text-t-secondary"
                }`}>
                  {count}
                </span>
              )}
            </button>
          );
        })}
        <div className="ml-auto flex items-center text-xs text-t-secondary">
          Total: <span className="ml-1 font-semibold text-primary">{totalCount}</span>
        </div>
      </div>

      {/* Tab description + actions */}
      <div className="flex items-center justify-between">
        <p className="text-xs text-t-secondary">{SCENARIO_TYPES.find((t) => t.id === activeTab)?.description}</p>
        <div className="flex items-center gap-2">
          <button
            onClick={() => { setShowAdd(true); setEditingId(null); }}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs bg-accent/20 text-accent rounded-lg hover:bg-accent/30 transition-colors"
          >
            <Plus className="w-3.5 h-3.5" /> Add
          </button>
          <button
            onClick={handleGenerate}
            disabled={generating}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs border border-accent/30 text-accent rounded-lg hover:bg-accent/10 transition-colors disabled:opacity-50"
          >
            {generating ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Sparkles className="w-3.5 h-3.5" />}
            Generate 5
          </button>
        </div>
      </div>

      {/* Error */}
      {error && (
        <div className="flex items-center gap-2 p-3 bg-danger/10 border border-danger/30 rounded-lg text-danger text-sm">
          <AlertCircle className="w-4 h-4 flex-shrink-0" />
          {error}
        </div>
      )}

      {/* Add / Edit form */}
      {(showAdd || editingId !== null) && (
        <div className="bg-surface-100 rounded-xl border border-accent/30 p-5 space-y-3">
          <h4 className="text-sm font-semibold text-primary">{editingId ? "Edit Scenario" : "New Scenario"}</h4>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <input
              type="text" value={formName} onChange={(e) => setFormName(e.target.value)}
              placeholder="Scenario name"
              className="px-3 py-2 bg-surface-100 border border-themed rounded-lg text-primary text-sm placeholder:text-t-secondary/50 focus:outline-none focus:border-accent"
            />
            <input
              type="text" value={formDescription} onChange={(e) => setFormDescription(e.target.value)}
              placeholder="Brief description (optional)"
              className="px-3 py-2 bg-surface-100 border border-themed rounded-lg text-primary text-sm placeholder:text-t-secondary/50 focus:outline-none focus:border-accent"
            />
          </div>
          <textarea
            value={formObjective} onChange={(e) => setFormObjective(e.target.value)}
            placeholder="What the user wants to accomplish (e.g., 'Get the current weather in Paris')"
            rows={2}
            className="w-full px-3 py-2 bg-surface-100 border border-themed rounded-lg text-primary text-sm placeholder:text-t-secondary/50 focus:outline-none focus:border-accent resize-y"
          />
          <input
            type="text" value={formInputHint} onChange={(e) => setFormInputHint(e.target.value)}
            placeholder="Example phrasing (optional, e.g., 'What's the weather like in Paris?')"
            className="w-full px-3 py-2 bg-surface-100 border border-themed rounded-lg text-primary text-sm placeholder:text-t-secondary/50 focus:outline-none focus:border-accent"
          />
          <div>
            <label className="block text-xs text-t-secondary mb-1">{typeInfo.expected_label} (JSON)</label>
            <textarea
              value={formExpected} onChange={(e) => setFormExpected(e.target.value)}
              placeholder={EXPECTED_HINTS[activeTab] || "{}"}
              rows={3}
              className="w-full px-3 py-2 bg-surface-100 border border-themed rounded-lg text-primary text-sm focus:outline-none focus:border-accent resize-y font-mono"
            />
          </div>
          <div className="flex gap-2">
            <button
              onClick={() => editingId ? handleUpdate(editingId) : handleAdd()}
              disabled={!formName.trim()}
              className="flex items-center gap-1.5 px-4 py-2 text-sm bg-accent text-accent-foreground rounded-lg hover:bg-accent/90 transition-colors disabled:opacity-50"
            >
              <Check className="w-3.5 h-3.5" /> {editingId ? "Update" : "Add"}
            </button>
            <button
              onClick={resetForm}
              className="flex items-center gap-1.5 px-4 py-2 text-sm bg-surface-200/50 text-t-secondary rounded-lg hover:text-primary transition-colors"
            >
              <X className="w-3.5 h-3.5" /> Cancel
            </button>
          </div>
        </div>
      )}

      {/* Scenarios table */}
      {loading ? (
        <div className="flex items-center justify-center py-12 text-t-secondary">
          <Loader2 className="w-5 h-5 animate-spin mr-2" /> Loading scenarios...
        </div>
      ) : currentScenarios.length === 0 ? (
        <div className="text-center py-12 text-t-secondary text-sm">
          No scenarios yet for this type. Add manually or generate with AI.
        </div>
      ) : (
        <div className="bg-surface-100 rounded-xl border border-themed overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-themed text-left">
                  <th className="px-4 py-3 text-xs font-semibold text-t-secondary uppercase tracking-wider w-8">#</th>
                  <th className="px-4 py-3 text-xs font-semibold text-t-secondary uppercase tracking-wider">Name</th>
                  <th className="px-4 py-3 text-xs font-semibold text-t-secondary uppercase tracking-wider">Objective</th>
                  <th className="px-4 py-3 text-xs font-semibold text-t-secondary uppercase tracking-wider">{typeInfo.expected_label}</th>
                  <th className="px-4 py-3 text-xs font-semibold text-t-secondary uppercase tracking-wider w-20">Actions</th>
                </tr>
              </thead>
              <tbody>
                {currentScenarios.map((s, idx) => {
                  const isExpanded = expandedId === s.id;
                  return (
                    <tr
                      key={s.id}
                      className={`border-b border-themed-subtle transition-colors ${
                        isExpanded ? "bg-surface-200/10" : "hover:bg-surface-200/5"
                      }`}
                    >
                      <td className="px-4 py-3 text-xs text-muted font-mono">{idx + 1}</td>
                      <td className="px-4 py-3">
                        <div className="flex items-center gap-2">
                          <button
                            onClick={() => setExpandedId(isExpanded ? null : s.id)}
                            className="text-t-secondary hover:text-primary"
                          >
                            {isExpanded ? <ChevronDown className="w-3.5 h-3.5" /> : <ChevronRight className="w-3.5 h-3.5" />}
                          </button>
                          <div>
                            <span className="text-primary font-medium">{s.name}</span>
                            {s.is_manual && (
                              <span className="ml-2 text-[10px] px-1.5 py-0.5 bg-accent/10 text-accent rounded-full">manual</span>
                            )}
                            {isExpanded && s.description && (
                              <p className="text-xs text-t-secondary mt-1">{s.description}</p>
                            )}
                          </div>
                        </div>
                      </td>
                      <td className="px-4 py-3">
                        <p className={`text-t-secondary ${isExpanded ? "" : "line-clamp-2"}`}>
                          {s.objective}
                        </p>
                        {isExpanded && s.input_hint && (
                          <p className="text-xs text-t-secondary/60 mt-1 italic">
                            Hint: &ldquo;{s.input_hint}&rdquo;
                          </p>
                        )}
                      </td>
                      <td className="px-4 py-3">
                        <pre className={`text-xs text-t-secondary/80 font-mono whitespace-pre-wrap ${isExpanded ? "" : "line-clamp-2"}`}>
                          {formatExpectedCell(s.expected_output, activeTab)}
                        </pre>
                      </td>
                      <td className="px-4 py-3">
                        <div className="flex items-center gap-1">
                          <button
                            onClick={() => startEdit(s)}
                            className="p-1.5 hover:bg-surface-200 rounded-lg transition-colors"
                            title="Edit"
                          >
                            <Edit3 className="w-3.5 h-3.5 text-t-secondary" />
                          </button>
                          <button
                            onClick={() => handleDelete(s.id)}
                            className="p-1.5 hover:bg-danger/10 rounded-lg transition-colors"
                            title="Delete"
                          >
                            <Trash2 className="w-3.5 h-3.5 text-t-secondary hover:text-danger" />
                          </button>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* CTA — Continue to next step */}
      {totalCount > 0 && (
        <button
          onClick={() => onComplete?.()}
          className="w-full py-3 px-6 bg-accent shadow-resting text-accent-foreground font-medium rounded-xl hover:opacity-90 transition-opacity disabled:opacity-50 flex items-center justify-center gap-2"
        >
          Continue to Create Personas ({totalCount} scenarios ready)
        </button>
      )}
    </div>
  );
}
