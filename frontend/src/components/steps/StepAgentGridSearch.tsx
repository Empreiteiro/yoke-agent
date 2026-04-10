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
  const [scenarioCount, setScenarioCount] = useState(0);
  const [personaCount, setPersonaCount] = useState(0);
  const [personaInteractions, setPersonaInteractions] = useState<{ name: string; count: number }[]>([]);
  const [scenarioCounts, setScenarioCounts] = useState<Record<string, number>>({});

  const loadData = useCallback(async () => {
    if (!agentConfigId) return;
    setLoading(true);
    try {
      const [variants, models, scenarios, personas] = await Promise.all([
        api.listPromptVariants(agentConfigId),
        api.getAvailableModels(),
        api.listScenarios(agentConfigId),
        api.listPersonas(agentConfigId),
      ]);
      setScenarioCount(scenarios.length);
      setPersonaCount(personas.length);
      setPersonaInteractions(
        personas.map((p: any) => ({ name: p.name, count: p.interaction_count || 1 }))
      );
      // Count by type
      const byType: Record<string, number> = {};
      for (const s of scenarios) {
        byType[s.scenario_type] = (byType[s.scenario_type] || 0) + 1;
      }
      setScenarioCounts(byType);
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
      const payload = {
        name: experimentName.trim() || `Agent Experiment ${new Date().toISOString().slice(0, 10)}`,
        agent_config_id: agentConfigId,
        grid_config: {
          prompt_variant_ids: selectedVariants,
          llm_models: selectedModels,
          temperatures: selectedTemps,
          max_turns: selectedMaxTurns,
          persona_group_names: personaGroup ? [personaGroup] : [],
          scenario_types: scenarioTypes,
          interaction_count_override: interactionCount ? Number(interactionCount) : null,
        },
      };

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

      {/* Simulation preview */}
      {(() => {
        const filteredScenarios = scenarioTypes.length > 0
          ? scenarioTypes.reduce((sum, t) => sum + (scenarioCounts[t] || 0), 0)
          : scenarioCount;
        const hasOverride = interactionCount !== "" && Number(interactionCount) > 0;
        const overrideVal = hasOverride ? Number(interactionCount) : 0;

        // Per-persona: each persona has its own multiplier
        // Total interactions = sum over personas of (scenarios × persona.interaction_count)
        const totalInteractionsPerCombo = hasOverride
          ? filteredScenarios * personaCount * overrideVal
          : personaInteractions.reduce((sum, p) => sum + filteredScenarios * p.count, 0);

        const totalSimulations = totalInteractionsPerCombo * combinationCount;
        const avgTurns = selectedMaxTurns.length > 0
          ? selectedMaxTurns.reduce((a, b) => a + b, 0) / selectedMaxTurns.length
          : 1;
        const tokensPerSimulation = Math.round((avgTurns * 2 + 1) * 800);
        const totalTokens = totalSimulations * tokensPerSimulation;

        return (
          <div className="bg-gradient-to-br from-accent/10 to-secondary/10 rounded-xl border border-surface-200/50 p-5 space-y-4">
            <div className="flex items-center justify-between">
              <div>
                <span className="text-sm text-t-secondary">Total Simulations</span>
                <p className="text-3xl font-bold text-accent">{totalSimulations.toLocaleString()}</p>
              </div>
              <div>
                <span className="text-sm text-t-secondary">Combinations</span>
                <p className="text-3xl font-bold text-primary">{combinationCount}</p>
              </div>
            </div>

            {/* Breakdown table */}
            <div className="border-t border-surface-200/30 pt-3">
              <table className="w-full text-xs">
                <tbody className="divide-y divide-surface-200/20">
                  <tr>
                    <td className="py-1.5 text-t-secondary">Scenarios</td>
                    <td className="py-1.5 text-right text-primary font-medium">{filteredScenarios}</td>
                    <td className="py-1.5 text-right text-t-secondary/60 pl-2 w-32">
                      {scenarioTypes.length > 0 ? `(filtered from ${scenarioCount})` : ""}
                    </td>
                  </tr>
                  <tr>
                    <td className="py-1.5 text-t-secondary">Personas</td>
                    <td className="py-1.5 text-right text-primary font-medium">{personaCount}</td>
                    <td className="py-1.5 text-right text-t-secondary/60 pl-2"></td>
                  </tr>
                  {/* Per-persona multipliers */}
                  {personaInteractions.length > 0 && !hasOverride && (
                    <tr>
                      <td className="py-1.5 text-t-secondary" colSpan={3}>
                        <div className="flex flex-wrap gap-x-3 gap-y-1 mt-1">
                          {personaInteractions.map((p, i) => (
                            <span key={i} className="text-[10px]">
                              <span className="text-primary">{p.name}</span>
                              <span className="text-accent font-bold ml-0.5">×{p.count}</span>
                            </span>
                          ))}
                        </div>
                      </td>
                    </tr>
                  )}
                  {hasOverride && (
                    <tr>
                      <td className="py-1.5 text-t-secondary">Override multiplier</td>
                      <td className="py-1.5 text-right text-accent font-bold">×{overrideVal}</td>
                      <td className="py-1.5 text-right text-t-secondary/60 pl-2">replaces per-persona</td>
                    </tr>
                  )}
                  <tr className="border-t border-surface-200/40">
                    <td className="py-1.5 text-t-secondary">Simulations per combo</td>
                    <td className="py-1.5 text-right text-primary font-bold">{totalInteractionsPerCombo.toLocaleString()}</td>
                    <td className="py-1.5 text-right text-t-secondary/60 pl-2">
                      {filteredScenarios} scenarios × {personaCount} personas {hasOverride ? `× ${overrideVal}` : "(per-persona ×)"}
                    </td>
                  </tr>
                  <tr>
                    <td className="py-1.5 text-t-secondary">Grid combinations</td>
                    <td className="py-1.5 text-right text-primary font-medium">{combinationCount}</td>
                    <td className="py-1.5 text-right text-t-secondary/60 pl-2">
                      {selectedVariants.length}v × {selectedModels.length}m × {selectedTemps.length}t × {selectedMaxTurns.length}turns
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>

            {/* Token estimation */}
            <div className="border-t border-surface-200/30 pt-3 space-y-1">
              <h4 className="text-xs font-semibold text-t-secondary uppercase tracking-wider">Estimated Token Usage</h4>
              <div className="flex items-center justify-between">
                <span className="text-xs text-t-secondary">~{tokensPerSimulation.toLocaleString()} tokens/simulation (avg {avgTurns.toFixed(1)} turns)</span>
                <span className="text-sm font-bold text-primary">{totalTokens >= 1_000_000 ? `~${(totalTokens / 1_000_000).toFixed(1)}M` : `~${(totalTokens / 1_000).toFixed(0)}K`} tokens total</span>
              </div>
              {totalSimulations > 100 && (
                <p className="text-[10px] text-amber-400">
                  ⚠ Large run — {totalSimulations.toLocaleString()} simulations may take significant time with CLI-based providers.
                  Consider reducing scenarios, personas, or multipliers for a faster test.
                </p>
              )}
              {(filteredScenarios === 0 || personaCount === 0) && (
                <p className="text-[10px] text-red-400">
                  ⚠ {filteredScenarios === 0 ? "No scenarios found" : "No personas found"} — create them in the previous steps before running.
                </p>
              )}
            </div>
          </div>
        );
      })()}

      {/* Error */}
      {error && (
        <div className="flex items-center gap-2 p-3 bg-red-500/10 border border-red-500/30 rounded-lg text-red-400 text-sm">
          <AlertCircle className="w-4 h-4 flex-shrink-0" />
          {error}
        </div>
      )}

      {/* CTA — Create experiment and continue */}
      <button
        onClick={handleCreate}
        disabled={creating || selectedVariants.length === 0 || selectedModels.length === 0}
        className="w-full py-3 px-6 bg-gradient-to-r from-accent to-accent-dark text-primary font-medium rounded-xl hover:opacity-90 transition-opacity disabled:opacity-50 flex items-center justify-center gap-2"
      >
        {creating ? (
          <>
            <Loader2 className="w-4 h-4 animate-spin" />
            Creating Experiment...
          </>
        ) : (
          <>Create Experiment &amp; Continue ({combinationCount} combinations)</>
        )}
      </button>
    </div>
  );
}
