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

      {/* ════ Main form card ════ */}
      <div className="bg-surface-100 rounded-2xl border border-themed p-8 space-y-6">

        {/* Experiment name */}
        <div className="rounded-xl border border-visible p-4">
          <label className="block text-sm font-medium text-t-hover mb-1">Experiment Name</label>
          <p className="text-xs text-muted mb-2">A short label to identify this experiment in the results dashboard.</p>
          <input
            type="text"
            value={experimentName}
            onChange={(e) => setExperimentName(e.target.value)}
            placeholder="e.g., Support agent — tone tuning"
            className="w-full px-3 py-2 bg-surface-50 border border-themed rounded-lg text-primary placeholder-muted text-sm focus:outline-none focus:border-accent/50"
          />
        </div>

        {/* Agent variants & models */}
        <div className="rounded-xl border border-visible p-4 space-y-4">
          <div>
            <h4 className="text-xs font-semibold text-primary uppercase tracking-wider mb-1">Agent under test</h4>
            <p className="text-xs text-muted">Which prompt variants and LLM backends to pit against each other.</p>
          </div>

          {/* Prompt Variants */}
          <div>
            <label className="block text-sm font-medium text-t-hover mb-1">Prompt Variants</label>
            <p className="text-xs text-muted mb-2">Variants generated in the Define Agent step — pick one or more to compare.</p>
            {promptVariants.length === 0 ? (
              <p className="text-sm text-muted italic">No variants available. Generate them in the Define Agent step.</p>
            ) : (
              <div className="flex flex-wrap gap-2">
                {promptVariants.map((v) => (
                  <button
                    key={v.id}
                    onClick={() => toggleVariant(v.id)}
                    className={`px-3 py-1.5 rounded-lg text-sm border transition-colors ${
                      selectedVariants.includes(v.id)
                        ? "bg-accent/20 border-accent text-accent"
                        : "bg-surface-50 border-visible text-t-hover hover:text-primary hover:border-accent/50"
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
          <div>
            <label className="block text-sm font-medium text-t-hover mb-1">LLM Models</label>
            <p className="text-xs text-muted mb-2">Each model is combined with every selected variant and parameter.</p>
            {availableModels.length === 0 ? (
              <p className="text-sm text-muted italic">No models available. Configure providers in Settings first.</p>
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
                          : "bg-surface-50 border-visible text-t-hover hover:text-primary hover:border-accent/50"
                      }`}
                    >
                      {selectedModels.includes(modelKey) && <Check className="w-3 h-3 inline mr-1" />}
                      {m.model}
                      <span className="text-xs text-muted ml-1">({m.provider_name})</span>
                    </button>
                  );
                })}
              </div>
            )}
          </div>
        </div>

        {/* LLM parameters */}
        <div className="rounded-xl border border-visible p-4 space-y-4">
          <div>
            <h4 className="text-xs font-semibold text-primary uppercase tracking-wider mb-1">LLM parameters</h4>
            <p className="text-xs text-muted">Generation settings swept across the grid.</p>
          </div>

          {/* Temperature */}
          <div>
            <label className="block text-sm font-medium text-t-hover mb-1">Temperature</label>
            <p className="text-xs text-muted mb-2">Lower values are more deterministic; higher values produce more variation.</p>
            <div className="flex flex-wrap gap-2">
              {TEMPERATURE_OPTIONS.map((t) => (
                <button
                  key={t}
                  onClick={() => toggleTemp(t)}
                  className={`px-4 py-2 rounded-lg text-sm font-mono border transition-colors ${
                    selectedTemps.includes(t)
                      ? "bg-accent/20 border-accent text-accent"
                      : "bg-surface-50 border-visible text-t-hover hover:text-primary hover:border-accent/50"
                  }`}
                >
                  {t.toFixed(1)}
                </button>
              ))}
            </div>
          </div>

          {/* Max Turns */}
          <div>
            <label className="block text-sm font-medium text-t-hover mb-1">Max Turns</label>
            <p className="text-xs text-muted mb-2">Upper bound on agent ↔ persona exchanges per simulation.</p>
            <div className="flex flex-wrap gap-2">
              {MAX_TURNS_OPTIONS.map((t) => (
                <button
                  key={t}
                  onClick={() => toggleMaxTurns(t)}
                  className={`px-4 py-2 rounded-lg text-sm border transition-colors ${
                    selectedMaxTurns.includes(t)
                      ? "bg-accent/20 border-accent text-accent"
                      : "bg-surface-50 border-visible text-t-hover hover:text-primary hover:border-accent/50"
                  }`}
                >
                  {t}
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* Simulation filters */}
        <div className="rounded-xl border border-visible p-4 space-y-4">
          <div>
            <h4 className="text-xs font-semibold text-primary uppercase tracking-wider mb-1">Simulation filters</h4>
            <p className="text-xs text-muted">Narrow down which scenarios and personas actually run.</p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-t-hover mb-1">Persona Group (optional)</label>
              <p className="text-xs text-muted mb-2">Restrict to a single group name — leave blank for all.</p>
              <input
                type="text"
                value={personaGroup}
                onChange={(e) => setPersonaGroup(e.target.value)}
                placeholder="Filter by group"
                className="w-full px-3 py-2 bg-surface-50 border border-themed rounded-lg text-primary placeholder-muted text-sm focus:outline-none focus:border-accent/50"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-t-hover mb-1">Interaction Count Override</label>
              <p className="text-xs text-muted mb-2">Replace each persona&apos;s interaction count with this value (1–50).</p>
              <input
                type="number"
                value={interactionCount}
                onChange={(e) => setInteractionCount(e.target.value ? parseInt(e.target.value) : "")}
                placeholder="Default"
                min={1}
                max={50}
                className="w-full px-3 py-2 bg-surface-50 border border-themed rounded-lg text-primary placeholder-muted text-sm focus:outline-none focus:border-accent/50"
              />
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium text-t-hover mb-1">Scenario Types</label>
            <p className="text-xs text-muted mb-2">Leave empty to run every scenario; pick one or more to focus the evaluation.</p>
            <div className="flex flex-wrap gap-2">
              {SCENARIO_TYPE_OPTIONS.map((st) => (
                <button
                  key={st.id}
                  onClick={() => toggleScenarioType(st.id)}
                  className={`px-3 py-1.5 rounded-lg text-sm border transition-colors ${
                    scenarioTypes.includes(st.id)
                      ? "bg-accent/20 border-accent text-accent"
                      : "bg-surface-50 border-visible text-t-hover hover:text-primary hover:border-accent/50"
                  }`}
                >
                  {scenarioTypes.includes(st.id) && <Check className="w-3 h-3 inline mr-1" />}
                  {st.label}
                </button>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* Summary + Submit footer */}
      {(() => {
        const filteredScenarios = scenarioTypes.length > 0
          ? scenarioTypes.reduce((sum, t) => sum + (scenarioCounts[t] || 0), 0)
          : scenarioCount;
        const hasOverride = interactionCount !== "" && Number(interactionCount) > 0;
        const overrideVal = hasOverride ? Number(interactionCount) : 0;

        const totalInteractionsPerCombo = hasOverride
          ? filteredScenarios * personaCount * overrideVal
          : personaInteractions.reduce((sum, p) => sum + filteredScenarios * p.count, 0);

        const totalSimulations = totalInteractionsPerCombo * combinationCount;
        const avgTurns = selectedMaxTurns.length > 0
          ? selectedMaxTurns.reduce((a, b) => a + b, 0) / selectedMaxTurns.length
          : 1;
        const tokensPerSimulation = Math.round((avgTurns * 2 + 1) * 800);
        const totalTokens = totalSimulations * tokensPerSimulation;
        // Blended ballpark rate (~$0.50/M tokens, in line with mid-tier LLMs)
        const estimatedCost = (totalTokens / 1_000_000) * 0.5;

        const hasData = filteredScenarios > 0 && personaCount > 0;
        const tokensLabel = totalTokens >= 1_000_000
          ? `${(totalTokens / 1_000_000).toFixed(1)}M`
          : totalTokens >= 1_000
            ? `${(totalTokens / 1_000).toFixed(0)}K`
            : totalTokens.toString();

        return (
          <div className="bg-surface-100 rounded-2xl border border-visible p-6">
            <div className="grid grid-cols-4 gap-4 mb-5">
              <div className="text-center rounded-lg bg-surface-50 py-3">
                <p className="text-xs text-t-secondary mb-1">Combinations</p>
                <p className="text-2xl font-bold text-primary">{combinationCount}</p>
              </div>
              <div className="text-center rounded-lg bg-surface-50 py-3">
                <p className="text-xs text-t-secondary mb-1">Est. Tokens</p>
                <p className="text-2xl font-bold text-primary">{hasData ? tokensLabel : "—"}</p>
              </div>
              <div className="text-center rounded-lg bg-surface-50 py-3">
                <p className="text-xs text-t-secondary mb-1">Simulations</p>
                <p className="text-2xl font-bold text-primary">{hasData ? totalSimulations.toLocaleString() : "—"}</p>
              </div>
              <div className="text-center rounded-lg bg-surface-50 py-3">
                <p className="text-xs text-t-secondary mb-1">Est. Cost</p>
                <p className="text-2xl font-bold text-warning">{hasData ? `$${estimatedCost.toFixed(4)}` : "—"}</p>
              </div>
            </div>

            <p className="text-xs text-muted mb-4 text-center">
              {hasData
                ? `Approximate values. Actual cost depends on provider and model. ${filteredScenarios} scenarios × ${personaCount} personas${hasOverride ? ` × ${overrideVal}` : " (per-persona ×)"} × ${combinationCount} combos.`
                : "Create scenarios and personas in the previous steps to see estimates."}
            </p>

            {totalSimulations > 100 && hasData && (
              <p className="text-[10px] text-warning text-center mb-3">
                ⚠ Large run — {totalSimulations.toLocaleString()} simulations may take significant time with CLI-based providers.
              </p>
            )}

            {error && (
              <div className="flex items-center gap-2 p-3 mb-3 bg-danger/10 border border-danger/30 rounded-lg text-danger text-sm">
                <AlertCircle className="w-4 h-4 flex-shrink-0" />
                {error}
              </div>
            )}

            <button
              onClick={handleCreate}
              disabled={creating || !hasData || selectedVariants.length === 0 || selectedModels.length === 0}
              className="w-full py-3 px-6 bg-accent shadow-resting text-accent-foreground font-medium rounded-xl hover:opacity-90 transition-opacity disabled:opacity-50 flex items-center justify-center gap-2"
            >
              {creating ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  Creating Experiment...
                </>
              ) : (
                <>
                  <Grid3X3 className="w-4 h-4" />
                  Confirm &amp; Continue
                </>
              )}
            </button>
          </div>
        );
      })()}
    </div>
  );
}
