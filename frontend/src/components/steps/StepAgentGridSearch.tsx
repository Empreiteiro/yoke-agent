"use client";

import { useState, useEffect, useCallback } from "react";
import { Grid3X3, Loader2, AlertCircle, Plus, Check } from "lucide-react";
import { api } from "@/lib/api";

interface StepAgentGridSearchProps {
  agentConfigId: number | null;
  onComplete?: (experimentId: number) => void;
}

const TEMPERATURE_OPTIONS = [0.0, 0.3, 0.5, 0.7, 1.0];
const MAX_TURNS_OPTIONS = [1, 3, 5, 10];
const SCENARIO_TYPE_OPTIONS = [
  { id: "tool_use", label: "Tool Use" },
  { id: "decision_path", label: "Decision Path" },
  { id: "response_quality", label: "Response Quality" },
  { id: "guardrails", label: "Guardrails" },
];

export default function StepAgentGridSearch({ agentConfigId, onComplete }: StepAgentGridSearchProps) {
  const [promptVariants, setPromptVariants] = useState<any[]>([]);
  const [availableModels, setAvailableModels] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Selections
  const [selectedVariants, setSelectedVariants] = useState<number[]>([]);
  const [selectedModels, setSelectedModels] = useState<string[]>([]);
  const [selectedTemps, setSelectedTemps] = useState<number[]>([0.3, 0.7]);
  const [selectedMaxTurns, setSelectedMaxTurns] = useState<number[]>([5]);
  const [personaGroup, setPersonaGroup] = useState("");
  const [scenarioTypes, setScenarioTypes] = useState<string[]>([]);
  const [interactionCount, setInteractionCount] = useState<number | "">("");
  const [experimentName, setExperimentName] = useState("");

  const loadData = useCallback(async () => {
    if (!agentConfigId) return;
    setLoading(true);
    try {
      const [variants, models] = await Promise.all([
        api.listPromptVariants(agentConfigId),
        api.getAvailableModels(),
      ]);
      setPromptVariants(variants);
      const llmModels = models.llm_models || [];
      setAvailableModels(llmModels);
      // Pre-select first variant and first model
      if (variants.length > 0 && selectedVariants.length === 0) {
        setSelectedVariants([variants[0].id]);
      }
      if (llmModels.length > 0 && selectedModels.length === 0) {
        setSelectedModels([llmModels[0].model || `${llmModels[0].provider_name}/${llmModels[0].model}`]);
      }
    } catch (err: any) {
      setError(err.message || "Failed to load data");
    } finally {
      setLoading(false);
    }
  }, [agentConfigId]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    loadData();
  }, [loadData]);

  const toggleVariant = (id: number) => {
    setSelectedVariants((prev) =>
      prev.includes(id) ? prev.filter((v) => v !== id) : [...prev, id]
    );
  };

  const toggleModel = (model: string) => {
    setSelectedModels((prev) =>
      prev.includes(model) ? prev.filter((m) => m !== model) : [...prev, model]
    );
  };

  const toggleTemp = (temp: number) => {
    setSelectedTemps((prev) =>
      prev.includes(temp) ? prev.filter((t) => t !== temp) : [...prev, temp]
    );
  };

  const toggleMaxTurns = (turns: number) => {
    setSelectedMaxTurns((prev) =>
      prev.includes(turns) ? prev.filter((t) => t !== turns) : [...prev, turns]
    );
  };

  const toggleScenarioType = (type: string) => {
    setScenarioTypes((prev) =>
      prev.includes(type) ? prev.filter((t) => t !== type) : [...prev, type]
    );
  };

  const combinationCount =
    Math.max(1, selectedVariants.length) *
    Math.max(1, selectedModels.length) *
    Math.max(1, selectedTemps.length) *
    Math.max(1, selectedMaxTurns.length);

  const handleCreate = async () => {
    if (!agentConfigId) return;
    if (selectedVariants.length === 0) {
      setError("Select at least one prompt variant");
      return;
    }
    if (selectedModels.length === 0) {
      setError("Select at least one model");
      return;
    }
    if (selectedTemps.length === 0) {
      setError("Select at least one temperature");
      return;
    }
    setCreating(true);
    setError(null);
    try {
      const payload: any = {
        name: experimentName.trim() || `Agent Experiment ${new Date().toISOString().slice(0, 10)}`,
        agent_config_id: agentConfigId,
        prompt_variant_ids: selectedVariants,
        models: selectedModels,
        temperatures: selectedTemps,
        max_turns: selectedMaxTurns,
      };
      if (personaGroup) payload.persona_group = personaGroup;
      if (scenarioTypes.length > 0) payload.scenario_types = scenarioTypes;
      if (interactionCount && Number(interactionCount) > 0) payload.interaction_count = Number(interactionCount);

      const experiment = await api.createAgentExperiment(payload);
      onComplete?.(experiment.id);
    } catch (err: any) {
      setError(err.message || "Failed to create experiment");
    } finally {
      setCreating(false);
    }
  };

  if (!agentConfigId) {
    return (
      <div className="flex flex-col items-center justify-center py-20 text-center">
        <div className="w-14 h-14 rounded-2xl bg-accent/10 flex items-center justify-center mb-4">
          <Grid3X3 className="w-7 h-7 text-accent" />
        </div>
        <h2 className="text-xl font-semibold text-primary mb-2">Grid Search Config</h2>
        <p className="text-sm text-t-secondary max-w-md">
          Please define an agent configuration first.
        </p>
      </div>
    );
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20 text-t-secondary">
        <Loader2 className="w-5 h-5 animate-spin mr-2" />
        Loading configuration options...
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-3">
        <div className="w-10 h-10 rounded-xl bg-accent/20 flex items-center justify-center">
          <Grid3X3 className="w-5 h-5 text-accent" />
        </div>
        <div>
          <h2 className="text-lg font-semibold text-primary">Grid Search Configuration</h2>
          <p className="text-sm text-t-secondary">Select combinations of prompts, models, and parameters</p>
        </div>
      </div>

      {/* Experiment name */}
      <div className="bg-surface-100 rounded-xl border border-surface-200/50 p-5">
        <label className="block text-sm font-medium text-t-secondary mb-2">Experiment Name</label>
        <input
          type="text"
          value={experimentName}
          onChange={(e) => setExperimentName(e.target.value)}
          placeholder="My Agent Experiment"
          className="w-full px-3 py-2 bg-surface-100 border border-surface-200/50 rounded-lg text-primary placeholder:text-t-secondary/50 focus:outline-none focus:ring-2 focus:ring-accent/40"
        />
      </div>

      {/* Prompt Variants */}
      <div className="bg-surface-100 rounded-xl border border-surface-200/50 p-5 space-y-3">
        <h3 className="text-sm font-semibold text-primary uppercase tracking-wider">Prompt Variants</h3>
        {promptVariants.length === 0 ? (
          <p className="text-sm text-t-secondary">No variants available. Generate them in the Define Agent step.</p>
        ) : (
          <div className="flex flex-wrap gap-2">
            {promptVariants.map((v) => (
              <button
                key={v.id}
                onClick={() => toggleVariant(v.id)}
                className={`px-3 py-1.5 rounded-lg text-sm border transition-colors ${
                  selectedVariants.includes(v.id)
                    ? "bg-accent/20 border-accent text-accent"
                    : "bg-surface-100 border-surface-200/50 text-t-secondary hover:text-primary"
                }`}
              >
                {selectedVariants.includes(v.id) && <Check className="w-3 h-3 inline mr-1" />}
                {v.label || v.name || `Variant #${v.id}`}
              </button>
            ))}
          </div>
        )}
      </div>

      {/* Models */}
      <div className="bg-surface-100 rounded-xl border border-surface-200/50 p-5 space-y-3">
        <h3 className="text-sm font-semibold text-primary uppercase tracking-wider">LLM Models</h3>
        {availableModels.length === 0 ? (
          <p className="text-sm text-t-secondary">No models available. Configure providers first.</p>
        ) : (
          <div className="flex flex-wrap gap-2">
            {availableModels.map((m, idx) => {
              const modelKey = m.model || `${m.provider_name}/${m.model}`;
              return (
                <button
                  key={idx}
                  onClick={() => toggleModel(modelKey)}
                  className={`px-3 py-1.5 rounded-lg text-sm border transition-colors ${
                    selectedModels.includes(modelKey)
                      ? "bg-accent/20 border-accent text-accent"
                      : "bg-surface-100 border-surface-200/50 text-t-secondary hover:text-primary"
                  }`}
                >
                  {selectedModels.includes(modelKey) && <Check className="w-3 h-3 inline mr-1" />}
                  {m.model}
                  <span className="text-xs text-t-secondary/60 ml-1">({m.provider_name})</span>
                </button>
              );
            })}
          </div>
        )}
      </div>

      {/* Temperature */}
      <div className="bg-surface-100 rounded-xl border border-surface-200/50 p-5 space-y-3">
        <h3 className="text-sm font-semibold text-primary uppercase tracking-wider">Temperature</h3>
        <div className="flex gap-2">
          {TEMPERATURE_OPTIONS.map((t) => (
            <button
              key={t}
              onClick={() => toggleTemp(t)}
              className={`px-4 py-2 rounded-lg text-sm font-mono border transition-colors ${
                selectedTemps.includes(t)
                  ? "bg-accent/20 border-accent text-accent"
                  : "bg-surface-100 border-surface-200/50 text-t-secondary hover:text-primary"
              }`}
            >
              {t.toFixed(1)}
            </button>
          ))}
        </div>
      </div>

      {/* Max Turns */}
      <div className="bg-surface-100 rounded-xl border border-surface-200/50 p-5 space-y-3">
        <h3 className="text-sm font-semibold text-primary uppercase tracking-wider">Max Turns</h3>
        <div className="flex gap-2">
          {MAX_TURNS_OPTIONS.map((t) => (
            <button
              key={t}
              onClick={() => toggleMaxTurns(t)}
              className={`px-4 py-2 rounded-lg text-sm border transition-colors ${
                selectedMaxTurns.includes(t)
                  ? "bg-accent/20 border-accent text-accent"
                  : "bg-surface-100 border-surface-200/50 text-t-secondary hover:text-primary"
              }`}
            >
              {t}
            </button>
          ))}
        </div>
      </div>

      {/* Filters */}
      <div className="bg-surface-100 rounded-xl border border-surface-200/50 p-5 space-y-4">
        <h3 className="text-sm font-semibold text-primary uppercase tracking-wider">Filters</h3>
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-xs text-t-secondary mb-1">Persona Group (optional)</label>
            <input
              type="text"
              value={personaGroup}
              onChange={(e) => setPersonaGroup(e.target.value)}
              placeholder="Filter by group"
              className="w-full px-3 py-2 bg-surface-100 border border-surface-200/50 rounded-lg text-primary text-sm placeholder:text-t-secondary/50 focus:outline-none focus:ring-2 focus:ring-accent/40"
            />
          </div>
          <div>
            <label className="block text-xs text-t-secondary mb-1">Interaction Count Override</label>
            <input
              type="number"
              value={interactionCount}
              onChange={(e) => setInteractionCount(e.target.value ? parseInt(e.target.value) : "")}
              placeholder="Default"
              min={1}
              max={50}
              className="w-full px-3 py-2 bg-surface-100 border border-surface-200/50 rounded-lg text-primary text-sm placeholder:text-t-secondary/50 focus:outline-none focus:ring-2 focus:ring-accent/40"
            />
          </div>
        </div>
        <div>
          <label className="block text-xs text-t-secondary mb-2">Scenario Types</label>
          <div className="flex flex-wrap gap-2">
            {SCENARIO_TYPE_OPTIONS.map((st) => (
              <button
                key={st.id}
                onClick={() => toggleScenarioType(st.id)}
                className={`px-3 py-1.5 rounded-lg text-sm border transition-colors ${
                  scenarioTypes.includes(st.id)
                    ? "bg-accent/20 border-accent text-accent"
                    : "bg-surface-100 border-surface-200/50 text-t-secondary hover:text-primary"
                }`}
              >
                {st.label}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Combination preview */}
      <div className="bg-gradient-to-br from-accent/10 to-secondary/10 rounded-xl border border-surface-200/50 p-5">
        <div className="flex items-center justify-between">
          <div>
            <span className="text-sm text-t-secondary">Total Combinations</span>
            <p className="text-3xl font-bold text-accent">{combinationCount}</p>
          </div>
          <div className="text-right text-xs text-t-secondary space-y-1">
            <p>{selectedVariants.length} variant(s)</p>
            <p>{selectedModels.length} model(s)</p>
            <p>{selectedTemps.length} temperature(s)</p>
            <p>{selectedMaxTurns.length} max turn(s)</p>
          </div>
        </div>
      </div>

      {/* Error */}
      {error && (
        <div className="flex items-center gap-2 p-3 bg-red-500/10 border border-red-500/30 rounded-lg text-red-400 text-sm">
          <AlertCircle className="w-4 h-4 flex-shrink-0" />
          {error}
        </div>
      )}

      {/* Create button */}
      <button
        onClick={handleCreate}
        disabled={creating}
        className="flex items-center gap-2 px-6 py-2.5 bg-accent text-primary font-medium rounded-xl hover:bg-accent/90 transition-colors disabled:opacity-50"
      >
        {creating ? <Loader2 className="w-4 h-4 animate-spin" /> : <Plus className="w-4 h-4" />}
        Create Experiment
      </button>
    </div>
  );
}
