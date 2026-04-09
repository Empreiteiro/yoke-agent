"use client";

import { useState, useEffect, useCallback } from "react";
import { FlaskConical, Plus, Trash2, Loader2, AlertCircle, Sparkles, Edit, X, Check } from "lucide-react";
import { api } from "@/lib/api";

interface StepAgentScenariosProps {
  agentConfigId: number | null;
  onComplete?: () => void;
}

const SCENARIO_TYPES = [
  { id: "tool_use", label: "Tool Use" },
  { id: "decision_path", label: "Decision Path" },
  { id: "response_quality", label: "Response Quality" },
  { id: "guardrails", label: "Guardrails" },
];

export default function StepAgentScenarios({ agentConfigId, onComplete }: StepAgentScenariosProps) {
  const [activeTab, setActiveTab] = useState("tool_use");
  const [scenarios, setScenarios] = useState<Record<string, any[]>>({
    tool_use: [],
    decision_path: [],
    response_quality: [],
    guardrails: [],
  });
  const [loading, setLoading] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [showAdd, setShowAdd] = useState(false);

  // Form state
  const [formName, setFormName] = useState("");
  const [formInput, setFormInput] = useState("");
  const [formExpected, setFormExpected] = useState("{}");

  const loadScenarios = useCallback(async () => {
    if (!agentConfigId) return;
    setLoading(true);
    try {
      const allScenarios: Record<string, any[]> = {
        tool_use: [],
        decision_path: [],
        response_quality: [],
        guardrails: [],
      };
      for (const t of SCENARIO_TYPES) {
        const data = await api.listScenarios(agentConfigId, t.id);
        allScenarios[t.id] = data;
      }
      setScenarios(allScenarios);
    } catch (err: any) {
      setError(err.message || "Failed to load scenarios");
    } finally {
      setLoading(false);
    }
  }, [agentConfigId]);

  useEffect(() => {
    loadScenarios();
  }, [loadScenarios]);

  const handleGenerate = async () => {
    if (!agentConfigId) return;
    setGenerating(true);
    setError(null);
    try {
      const newScenarios = await api.generateScenarios(agentConfigId, {
        scenario_type: activeTab,
        count: 5,
      });
      setScenarios((prev) => ({
        ...prev,
        [activeTab]: [...prev[activeTab], ...newScenarios],
      }));
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
      let expectedParsed;
      try {
        expectedParsed = JSON.parse(formExpected);
      } catch {
        expectedParsed = { text: formExpected };
      }
      const scenario = await api.createScenario(agentConfigId, {
        name: formName.trim(),
        scenario_type: activeTab,
        input_message: formInput.trim(),
        expected_output: expectedParsed,
      });
      setScenarios((prev) => ({
        ...prev,
        [activeTab]: [...prev[activeTab], scenario],
      }));
      setFormName("");
      setFormInput("");
      setFormExpected("{}");
      setShowAdd(false);
    } catch (err: any) {
      setError(err.message || "Failed to create scenario");
    }
  };

  const handleUpdate = async (scenarioId: number) => {
    if (!agentConfigId) return;
    setError(null);
    try {
      let expectedParsed;
      try {
        expectedParsed = JSON.parse(formExpected);
      } catch {
        expectedParsed = { text: formExpected };
      }
      const updated = await api.updateScenario(agentConfigId, scenarioId, {
        name: formName.trim(),
        input_message: formInput.trim(),
        expected_output: expectedParsed,
      });
      setScenarios((prev) => ({
        ...prev,
        [activeTab]: prev[activeTab].map((s) => (s.id === scenarioId ? updated : s)),
      }));
      setEditingId(null);
      setFormName("");
      setFormInput("");
      setFormExpected("{}");
    } catch (err: any) {
      setError(err.message || "Failed to update scenario");
    }
  };

  const handleDelete = async (scenarioId: number) => {
    if (!agentConfigId) return;
    try {
      await api.deleteScenario(agentConfigId, scenarioId);
      setScenarios((prev) => ({
        ...prev,
        [activeTab]: prev[activeTab].filter((s) => s.id !== scenarioId),
      }));
    } catch (err: any) {
      setError(err.message || "Failed to delete scenario");
    }
  };

  const startEdit = (scenario: any) => {
    setEditingId(scenario.id);
    setFormName(scenario.name || "");
    setFormInput(scenario.input_message || "");
    setFormExpected(
      typeof scenario.expected_output === "string"
        ? scenario.expected_output
        : JSON.stringify(scenario.expected_output || {}, null, 2)
    );
    setShowAdd(false);
  };

  const cancelEdit = () => {
    setEditingId(null);
    setFormName("");
    setFormInput("");
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

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-3">
        <div className="w-10 h-10 rounded-xl bg-accent/20 flex items-center justify-center">
          <FlaskConical className="w-5 h-5 text-accent" />
        </div>
        <div>
          <h2 className="text-lg font-semibold text-primary">Scenarios</h2>
          <p className="text-sm text-t-secondary">Build test cases for evaluating agent behavior</p>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex gap-2 flex-wrap">
        {SCENARIO_TYPES.map((t) => {
          const count = scenarios[t.id]?.length || 0;
          return (
            <button
              key={t.id}
              onClick={() => { setActiveTab(t.id); setShowAdd(false); cancelEdit(); }}
              className={`px-4 py-2 rounded-lg text-sm font-medium border transition-colors flex items-center gap-2 ${
                activeTab === t.id
                  ? "bg-accent/20 border-accent text-accent"
                  : "bg-surface-100 border-surface-200/50 text-t-secondary hover:text-primary hover:border-surface-200"
              }`}
            >
              {t.label}
              {count > 0 && (
                <span className={`px-1.5 py-0.5 rounded-full text-xs ${
                  activeTab === t.id ? "bg-accent/30 text-accent" : "bg-surface-200/50 text-t-secondary"
                }`}>
                  {count}
                </span>
              )}
            </button>
          );
        })}
      </div>

      {/* Actions */}
      <div className="flex items-center gap-3">
        <button
          onClick={() => { setShowAdd(true); cancelEdit(); }}
          className="flex items-center gap-2 px-4 py-2 text-sm bg-accent/20 text-accent rounded-lg hover:bg-accent/30 transition-colors"
        >
          <Plus className="w-4 h-4" /> Add Scenario
        </button>
        <button
          onClick={handleGenerate}
          disabled={generating}
          className="flex items-center gap-2 px-4 py-2 text-sm bg-secondary/20 text-secondary rounded-lg hover:bg-secondary/30 transition-colors disabled:opacity-50"
        >
          {generating ? <Loader2 className="w-4 h-4 animate-spin" /> : <Sparkles className="w-4 h-4" />}
          Generate 5 Scenarios
        </button>
      </div>

      {/* Error */}
      {error && (
        <div className="flex items-center gap-2 p-3 bg-red-500/10 border border-red-500/30 rounded-lg text-red-400 text-sm">
          <AlertCircle className="w-4 h-4 flex-shrink-0" />
          {error}
        </div>
      )}

      {/* Add / Edit form */}
      {(showAdd || editingId !== null) && (
        <div className="bg-surface-100 rounded-xl border border-accent/30 p-5 space-y-3">
          <h4 className="text-sm font-semibold text-primary">
            {editingId ? "Edit Scenario" : "New Scenario"}
          </h4>
          <input
            type="text"
            value={formName}
            onChange={(e) => setFormName(e.target.value)}
            placeholder="Scenario name"
            className="w-full px-3 py-2 bg-surface-100 border border-surface-200/50 rounded-lg text-primary text-sm placeholder:text-t-secondary/50 focus:outline-none focus:ring-2 focus:ring-accent/40"
          />
          <textarea
            value={formInput}
            onChange={(e) => setFormInput(e.target.value)}
            placeholder="Input message from user"
            rows={3}
            className="w-full px-3 py-2 bg-surface-100 border border-surface-200/50 rounded-lg text-primary text-sm placeholder:text-t-secondary/50 focus:outline-none focus:ring-2 focus:ring-accent/40 resize-y"
          />
          <div>
            <label className="block text-xs text-t-secondary mb-1">Expected Output (JSON)</label>
            <textarea
              value={formExpected}
              onChange={(e) => setFormExpected(e.target.value)}
              rows={4}
              className="w-full px-3 py-2 bg-surface-100 border border-surface-200/50 rounded-lg text-primary text-sm focus:outline-none focus:ring-2 focus:ring-accent/40 resize-y font-mono"
            />
          </div>
          <div className="flex gap-2">
            <button
              onClick={() => editingId ? handleUpdate(editingId) : handleAdd()}
              className="flex items-center gap-1.5 px-4 py-2 text-sm bg-accent text-primary rounded-lg hover:bg-accent/90 transition-colors"
            >
              <Check className="w-3.5 h-3.5" /> {editingId ? "Update" : "Add"}
            </button>
            <button
              onClick={() => { setShowAdd(false); cancelEdit(); }}
              className="flex items-center gap-1.5 px-4 py-2 text-sm bg-surface-200/50 text-t-secondary rounded-lg hover:text-primary transition-colors"
            >
              <X className="w-3.5 h-3.5" /> Cancel
            </button>
          </div>
        </div>
      )}

      {/* Scenario list */}
      {loading ? (
        <div className="flex items-center justify-center py-12 text-t-secondary">
          <Loader2 className="w-5 h-5 animate-spin mr-2" />
          Loading scenarios...
        </div>
      ) : currentScenarios.length === 0 ? (
        <div className="text-center py-12 text-t-secondary text-sm">
          No scenarios yet for this type. Add manually or generate with AI.
        </div>
      ) : (
        <div className="space-y-3">
          {currentScenarios.map((s) => (
            <div key={s.id} className="bg-surface-100 rounded-xl border border-surface-200/50 p-4 space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-sm font-medium text-primary">{s.name}</span>
                <div className="flex items-center gap-2">
                  <button onClick={() => startEdit(s)} className="text-t-secondary hover:text-accent transition-colors">
                    <Edit className="w-3.5 h-3.5" />
                  </button>
                  <button onClick={() => handleDelete(s.id)} className="text-t-secondary hover:text-red-400 transition-colors">
                    <Trash2 className="w-3.5 h-3.5" />
                  </button>
                </div>
              </div>
              <p className="text-xs text-t-secondary">{s.input_message}</p>
              {s.expected_output && (
                <pre className="text-xs text-t-secondary/70 font-mono bg-surface-100 rounded-lg p-2 border border-surface-200/50 max-h-24 overflow-y-auto">
                  {typeof s.expected_output === "string"
                    ? s.expected_output
                    : JSON.stringify(s.expected_output, null, 2)}
                </pre>
              )}
            </div>
          ))}
        </div>
      )}
      {/* CTA — Continue to next step */}
      {scenarios.length > 0 && (
        <button
          onClick={() => onComplete?.()}
          className="w-full py-3 px-6 bg-gradient-to-r from-accent to-accent-dark text-primary font-medium rounded-xl hover:opacity-90 transition-opacity disabled:opacity-50 flex items-center justify-center gap-2"
        >
          Continue to Create Personas ({scenarios.length} scenarios ready)
        </button>
      )}
    </div>
  );
}
