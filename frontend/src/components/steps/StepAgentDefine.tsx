"use client";

import { useState, useEffect, useCallback } from "react";
import { Bot, Plus, X, Loader2, AlertCircle, Save, Sparkles, Trash2, Wrench, ShieldCheck, Wand2, ChevronDown, ChevronRight } from "lucide-react";
import { api } from "@/lib/api";

interface StepAgentDefineProps {
  onComplete?: (configId: number) => void;
}

interface ToolDef {
  name: string;
  description: string;
  parameters: string;
}

const EXAMPLE_TOOLS: ToolDef[] = [
  {
    name: "web_search",
    description: "Search the web for current information on a topic",
    parameters: '{"type":"object","properties":{"query":{"type":"string","description":"The search query"},"num_results":{"type":"integer","description":"Number of results to return","default":5}},"required":["query"]}',
  },
  {
    name: "get_weather",
    description: "Get current weather conditions for a given location",
    parameters: '{"type":"object","properties":{"city":{"type":"string","description":"City name"},"units":{"type":"string","enum":["celsius","fahrenheit"],"default":"celsius"}},"required":["city"]}',
  },
  {
    name: "send_email",
    description: "Send an email to a specified recipient",
    parameters: '{"type":"object","properties":{"to":{"type":"string","description":"Recipient email address"},"subject":{"type":"string"},"body":{"type":"string"}},"required":["to","subject","body"]}',
  },
  {
    name: "query_database",
    description: "Execute a read-only SQL query against the application database",
    parameters: '{"type":"object","properties":{"query":{"type":"string","description":"SQL SELECT query"},"limit":{"type":"integer","default":100}},"required":["query"]}',
  },
  {
    name: "create_ticket",
    description: "Create a support ticket in the helpdesk system",
    parameters: '{"type":"object","properties":{"title":{"type":"string"},"description":{"type":"string"},"priority":{"type":"string","enum":["low","medium","high","critical"]},"assignee":{"type":"string"}},"required":["title","description","priority"]}',
  },
  {
    name: "get_user_info",
    description: "Retrieve profile and account information for a user by ID or email",
    parameters: '{"type":"object","properties":{"user_id":{"type":"string","description":"User ID or email address"}},"required":["user_id"]}',
  },
  {
    name: "calculate",
    description: "Evaluate a mathematical expression and return the result",
    parameters: '{"type":"object","properties":{"expression":{"type":"string","description":"Math expression to evaluate, e.g. 2+2*3"}},"required":["expression"]}',
  },
  {
    name: "schedule_meeting",
    description: "Schedule a calendar meeting with one or more participants",
    parameters: '{"type":"object","properties":{"title":{"type":"string"},"datetime":{"type":"string","description":"ISO 8601 datetime"},"duration_minutes":{"type":"integer","default":30},"participants":{"type":"array","items":{"type":"string"}}},"required":["title","datetime","participants"]}',
  },
];

export default function StepAgentDefine({ onComplete }: StepAgentDefineProps) {
  const [configs, setConfigs] = useState<any[]>([]);
  const [selectedConfigId, setSelectedConfigId] = useState<number | null>(null);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [systemPrompt, setSystemPrompt] = useState("");
  const [tools, setTools] = useState<ToolDef[]>([]);
  const [constraints, setConstraints] = useState<string[]>([]);
  const [newConstraint, setNewConstraint] = useState("");
  const [saving, setSaving] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [variants, setVariants] = useState<any[]>([]);
  const [generatingVariants, setGeneratingVariants] = useState(false);
  const [enhancingPrompt, setEnhancingPrompt] = useState(false);
  const [enhancingDescription, setEnhancingDescription] = useState(false);
  const [suggestingTools, setSuggestingTools] = useState(false);
  const [showToolPicker, setShowToolPicker] = useState(false);

  const loadConfigs = useCallback(async () => {
    try {
      const data = await api.listAgentConfigs();
      setConfigs(data);
    } catch {
      // ignore
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadConfigs();
  }, [loadConfigs]);

  const loadConfig = useCallback(async (id: number) => {
    try {
      const data = await api.getAgentConfig(id);
      setName(data.name || "");
      setDescription(data.description || "");
      setSystemPrompt(data.system_prompt || "");
      setTools(
        (data.tools || []).map((t: any) => ({
          name: t.name || "",
          description: t.description || "",
          parameters: typeof t.parameters === "string" ? t.parameters : JSON.stringify(t.parameters || {}, null, 2),
        }))
      );
      setConstraints(data.constraints || []);
      setSelectedConfigId(id);
      const v = await api.listPromptVariants(id);
      setVariants(v);
    } catch (err: any) {
      setError(err.message || "Failed to load config");
    }
  }, []);

  const resetForm = () => {
    setSelectedConfigId(null);
    setName("");
    setDescription("");
    setSystemPrompt("");
    setTools([]);
    setConstraints([]);
    setNewConstraint("");
    setVariants([]);
    setError(null);
  };

  const handleSave = async () => {
    if (!name.trim()) {
      setError("Name is required");
      return;
    }
    setSaving(true);
    setError(null);
    try {
      const payload = {
        name: name.trim(),
        description: description.trim(),
        system_prompt: systemPrompt,
        tools: tools.map((t) => ({
          name: t.name,
          description: t.description,
          parameters: (() => { try { return JSON.parse(t.parameters); } catch { return {}; } })(),
        })),
        constraints,
      };
      let config;
      if (selectedConfigId) {
        config = await api.updateAgentConfig(selectedConfigId, payload);
      } else {
        config = await api.createAgentConfig(payload);
      }
      setSelectedConfigId(config.id);
      await loadConfigs();
      onComplete?.(config.id);
    } catch (err: any) {
      setError(err.message || "Failed to save agent config");
    } finally {
      setSaving(false);
    }
  };

  const handleGenerateVariants = async () => {
    if (!selectedConfigId) return;
    setGeneratingVariants(true);
    setError(null);
    try {
      const newVariants = await api.generatePromptVariants(selectedConfigId, { count: 3 });
      setVariants((prev) => [...prev, ...newVariants]);
    } catch (err: any) {
      setError(err.message || "Failed to generate variants");
    } finally {
      setGeneratingVariants(false);
    }
  };

  const handleDeleteVariant = async (variantId: number) => {
    if (!selectedConfigId) return;
    try {
      await api.deletePromptVariant(selectedConfigId, variantId);
      setVariants((prev) => prev.filter((v) => v.id !== variantId));
    } catch (err: any) {
      setError(err.message || "Failed to delete variant");
    }
  };

  // ── AI Enhance handlers ──────────────────────────────────────

  const handleEnhancePrompt = async () => {
    if (!systemPrompt.trim()) return;
    setEnhancingPrompt(true);
    setError(null);
    try {
      const { result } = await api.enhancePrompt({
        text: systemPrompt,
        context: description || undefined,
      });
      setSystemPrompt(result);
    } catch (err: any) {
      setError(err.message || "Failed to enhance prompt");
    } finally {
      setEnhancingPrompt(false);
    }
  };

  const handleEnhanceDescription = async () => {
    if (!description.trim() && !name.trim()) return;
    setEnhancingDescription(true);
    setError(null);
    try {
      const { result } = await api.enhanceDescription({
        text: description || name,
        context: systemPrompt || undefined,
      });
      setDescription(result);
    } catch (err: any) {
      setError(err.message || "Failed to enhance description");
    } finally {
      setEnhancingDescription(false);
    }
  };

  const handleSuggestTools = async () => {
    if (!name.trim() && !systemPrompt.trim()) return;
    setSuggestingTools(true);
    setError(null);
    try {
      const { tools: suggested } = await api.suggestTools({
        agent_name: name,
        description,
        system_prompt: systemPrompt,
        existing_tools: tools.map((t) => ({ name: t.name, description: t.description })),
      });
      const newTools: ToolDef[] = suggested.map((t: any) => ({
        name: t.name || "",
        description: t.description || "",
        parameters: typeof t.parameters === "string" ? t.parameters : JSON.stringify(t.parameters || {}, null, 2),
      }));
      setTools((prev) => [...prev, ...newTools]);
    } catch (err: any) {
      setError(err.message || "Failed to suggest tools");
    } finally {
      setSuggestingTools(false);
    }
  };

  // ── Tool helpers ─────────────────────────────────────────────

  const addTool = () => {
    setTools([...tools, { name: "", description: "", parameters: "{}" }]);
  };

  const addExampleTool = (example: ToolDef) => {
    if (tools.some((t) => t.name === example.name)) return;
    setTools([...tools, { ...example }]);
  };

  const updateTool = (index: number, field: keyof ToolDef, value: string) => {
    const updated = [...tools];
    updated[index] = { ...updated[index], [field]: value };
    setTools(updated);
  };

  const removeTool = (index: number) => {
    setTools(tools.filter((_, i) => i !== index));
  };

  const addConstraint = () => {
    if (!newConstraint.trim()) return;
    setConstraints([...constraints, newConstraint.trim()]);
    setNewConstraint("");
  };

  const removeConstraint = (index: number) => {
    setConstraints(constraints.filter((_, i) => i !== index));
  };

  return (
    <div className="space-y-6">
      {/* Top action bar */}
      <div className="flex items-center justify-end">
        <button
          onClick={resetForm}
          className="flex items-center gap-1.5 px-3 py-1.5 text-sm text-t-secondary hover:text-primary border border-visible rounded-lg transition-colors"
        >
          <Plus className="w-3.5 h-3.5" /> New Agent
        </button>
      </div>

      {/* Existing configs selector */}
      {configs.length > 0 && (
        <div className="bg-surface-100 rounded-2xl border border-surface-200/50 p-6">
          <label className="block text-sm font-medium text-t-hover mb-1">Load Existing Config</label>
          <p className="text-xs text-muted mb-3">Pick a saved agent to edit, or start fresh with &quot;New Agent&quot;.</p>
          <div className="flex flex-wrap gap-2">
            {configs.map((c) => (
              <button
                key={c.id}
                onClick={() => loadConfig(c.id)}
                className={`px-3 py-1.5 rounded-lg text-sm border transition-colors ${
                  selectedConfigId === c.id
                    ? "bg-accent/20 border-accent text-accent"
                    : "bg-surface-50 border-visible text-t-hover hover:text-primary hover:border-accent/50"
                }`}
              >
                {c.name}
              </button>
            ))}
          </div>
        </div>
      )}

      {loading ? (
        <div className="flex items-center justify-center py-20 text-t-secondary">
          <Loader2 className="w-5 h-5 animate-spin mr-2" />
          Loading...
        </div>
      ) : (
        <>
          {/* ════ Main form card ════ */}
          <div className="bg-surface-100 rounded-2xl border border-surface-200/50 p-8 space-y-6">

            {/* Name */}
            <div className="rounded-xl border border-visible p-4">
              <label className="block text-sm font-medium text-t-hover mb-1">Name</label>
              <p className="text-xs text-muted mb-2">A short label to identify this agent.</p>
              <input
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="e.g., Support Triage Agent"
                className="w-full px-3 py-2 bg-surface-50 border border-surface-200/50 rounded-lg text-primary placeholder-muted text-sm focus:outline-none focus:border-accent/50"
              />
            </div>

            {/* Description */}
            <div className="rounded-xl border border-visible p-4">
              <div className="flex items-center justify-between mb-1">
                <label className="block text-sm font-medium text-t-hover">Description</label>
                <button
                  onClick={handleEnhanceDescription}
                  disabled={enhancingDescription || (!description.trim() && !name.trim())}
                  className="flex items-center gap-1 px-2 py-1 text-[11px] text-accent hover:bg-accent/10 rounded-md transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
                  title="Improve description with AI"
                >
                  {enhancingDescription ? <Loader2 className="w-3 h-3 animate-spin" /> : <Wand2 className="w-3 h-3" />}
                  Enhance
                </button>
              </div>
              <p className="text-xs text-muted mb-2">One-liner describing what this agent does.</p>
              <input
                type="text"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="What does this agent do?"
                className="w-full px-3 py-2 bg-surface-50 border border-surface-200/50 rounded-lg text-primary placeholder-muted text-sm focus:outline-none focus:border-accent/50"
              />
            </div>

            {/* System Prompt */}
            <div className="rounded-xl border border-visible p-4">
              <div className="flex items-center justify-between mb-1">
                <label className="block text-sm font-medium text-t-hover">System Prompt</label>
                <button
                  onClick={handleEnhancePrompt}
                  disabled={enhancingPrompt || !systemPrompt.trim()}
                  className="flex items-center gap-1 px-2 py-1 text-[11px] text-accent hover:bg-accent/10 rounded-md transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
                  title="Improve prompt with AI"
                >
                  {enhancingPrompt ? <Loader2 className="w-3 h-3 animate-spin" /> : <Wand2 className="w-3 h-3" />}
                  Enhance
                </button>
              </div>
              <p className="text-xs text-muted mb-3">The instructions that shape the agent&apos;s persona, objectives, and behavior.</p>
              <textarea
                value={systemPrompt}
                onChange={(e) => setSystemPrompt(e.target.value)}
                placeholder="You are a helpful assistant that..."
                rows={8}
                className="w-full px-3 py-2 bg-surface-50 border border-surface-200/50 rounded-lg text-primary placeholder-muted text-sm focus:outline-none focus:border-accent/50 resize-y font-mono"
              />
            </div>

            {/* Tools */}
            <div className="rounded-xl border border-visible p-4">
              <div className="flex items-start justify-between mb-1 gap-4">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <Wrench className="w-3.5 h-3.5 text-t-secondary" />
                    <label className="block text-sm font-medium text-t-hover">Tools</label>
                    {tools.length > 0 && (
                      <span className="px-1.5 py-0.5 text-[10px] bg-accent/20 text-accent rounded-full font-medium">{tools.length}</span>
                    )}
                  </div>
                  <p className="text-xs text-muted mt-1">Functions the agent can call to fetch data or take actions.</p>
                </div>
                <div className="flex items-center gap-2 flex-shrink-0">
                  <button
                    onClick={handleSuggestTools}
                    disabled={suggestingTools || (!name.trim() && !systemPrompt.trim())}
                    className="flex items-center gap-1 px-2.5 py-1.5 text-xs text-accent hover:bg-accent/10 border border-accent/30 rounded-lg transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
                    title="Suggest tools with AI based on your agent definition"
                  >
                    {suggestingTools ? <Loader2 className="w-3 h-3 animate-spin" /> : <Wand2 className="w-3 h-3" />}
                    Suggest with AI
                  </button>
                  <button
                    onClick={() => setShowToolPicker(!showToolPicker)}
                    className="flex items-center gap-1 px-2.5 py-1.5 text-xs text-t-secondary hover:text-primary border border-visible rounded-lg transition-colors"
                  >
                    {showToolPicker ? <ChevronDown className="w-3 h-3" /> : <ChevronRight className="w-3 h-3" />}
                    Examples
                  </button>
                  <button
                    onClick={addTool}
                    className="flex items-center gap-1 px-2.5 py-1.5 text-xs bg-accent/20 text-accent rounded-lg hover:bg-accent/30 transition-colors"
                  >
                    <Plus className="w-3 h-3" /> Add Blank
                  </button>
                </div>
              </div>

              {/* Example tool picker */}
              {showToolPicker && (
                <div className="border border-visible rounded-lg p-3 bg-surface-50 mt-3">
                  <p className="text-xs text-muted mb-2">Click to add an example tool:</p>
                  <div className="flex flex-wrap gap-1.5">
                    {EXAMPLE_TOOLS.map((ex) => {
                      const alreadyAdded = tools.some((t) => t.name === ex.name);
                      return (
                        <button
                          key={ex.name}
                          onClick={() => addExampleTool(ex)}
                          disabled={alreadyAdded}
                          className={`px-2.5 py-1.5 rounded-lg text-xs border transition-colors ${
                            alreadyAdded
                              ? "opacity-40 cursor-not-allowed bg-surface-100 border-visible text-muted"
                              : "bg-surface-100 border-visible text-t-hover hover:text-primary hover:border-accent/30"
                          }`}
                        >
                          <span className="font-mono">{ex.name}</span>
                          {alreadyAdded && <span className="ml-1 text-[10px]">added</span>}
                        </button>
                      );
                    })}
                  </div>
                </div>
              )}

              {tools.length === 0 && !showToolPicker && (
                <p className="text-sm text-muted mt-3">No tools defined. Add from examples, suggest with AI, or create a blank one.</p>
              )}

              {tools.length > 0 && (
                <div className="space-y-3 mt-3">
                  {tools.map((tool, idx) => (
                    <div key={idx} className="border border-visible rounded-lg p-4 bg-surface-50 space-y-3">
                      <div className="flex items-center justify-between">
                        <span className="text-xs font-medium text-muted">Tool #{idx + 1}</span>
                        <button onClick={() => removeTool(idx)} className="text-red-400 hover:text-red-300">
                          <X className="w-4 h-4" />
                        </button>
                      </div>
                      <input
                        type="text"
                        value={tool.name}
                        onChange={(e) => updateTool(idx, "name", e.target.value)}
                        placeholder="Tool name (snake_case)"
                        className="w-full px-3 py-2 bg-surface-100 border border-surface-200/50 rounded-lg text-primary text-sm placeholder-muted focus:outline-none focus:border-accent/50 font-mono"
                      />
                      <input
                        type="text"
                        value={tool.description}
                        onChange={(e) => updateTool(idx, "description", e.target.value)}
                        placeholder="What does this tool do?"
                        className="w-full px-3 py-2 bg-surface-100 border border-surface-200/50 rounded-lg text-primary text-sm placeholder-muted focus:outline-none focus:border-accent/50"
                      />
                      <textarea
                        value={tool.parameters}
                        onChange={(e) => updateTool(idx, "parameters", e.target.value)}
                        placeholder='{"type": "object", "properties": {}}'
                        rows={3}
                        className="w-full px-3 py-2 bg-surface-100 border border-surface-200/50 rounded-lg text-primary text-sm placeholder-muted focus:outline-none focus:border-accent/50 resize-y font-mono"
                      />
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Constraints */}
            <div className="rounded-xl border border-visible p-4">
              <div className="flex items-center gap-2 mb-1">
                <ShieldCheck className="w-3.5 h-3.5 text-t-secondary" />
                <label className="block text-sm font-medium text-t-hover">Constraints</label>
                {constraints.length > 0 && (
                  <span className="px-1.5 py-0.5 text-[10px] bg-accent/20 text-accent rounded-full font-medium">{constraints.length}</span>
                )}
              </div>
              <p className="text-xs text-muted mb-3">Guardrails and rules the agent must always respect.</p>
              <div className="flex gap-2">
                <input
                  type="text"
                  value={newConstraint}
                  onChange={(e) => setNewConstraint(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && addConstraint()}
                  placeholder="e.g., Never share internal customer data"
                  className="flex-1 px-3 py-2 bg-surface-50 border border-surface-200/50 rounded-lg text-primary text-sm placeholder-muted focus:outline-none focus:border-accent/50"
                />
                <button
                  onClick={addConstraint}
                  disabled={!newConstraint.trim()}
                  className="px-3 py-2 bg-accent/20 text-accent rounded-lg hover:bg-accent/30 transition-colors text-sm disabled:opacity-40"
                >
                  <Plus className="w-4 h-4" />
                </button>
              </div>
              {constraints.length > 0 && (
                <div className="space-y-2 mt-3">
                  {constraints.map((c, idx) => (
                    <div key={idx} className="flex items-center justify-between gap-2 px-3 py-2 bg-surface-50 border border-visible rounded-lg">
                      <span className="text-sm text-t-hover">{c}</span>
                      <button onClick={() => removeConstraint(idx)} className="text-red-400 hover:text-red-300 flex-shrink-0">
                        <X className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  ))}
                </div>
              )}
            </div>

          {/* Close main form card */}
          </div>

          {/* Error */}
          {error && (
            <div className="flex items-center gap-2 p-3 bg-red-500/10 border border-red-500/30 rounded-lg text-red-400 text-sm">
              <AlertCircle className="w-4 h-4 flex-shrink-0" />
              {error}
            </div>
          )}

          {/* Prompt Variants */}
          {variants.length > 0 && (
            <div className="bg-surface-100 rounded-2xl border border-surface-200/50 p-6 space-y-4">
              <div className="flex items-center justify-between">
                <h3 className="text-sm font-semibold text-primary uppercase tracking-wider">
                  Prompt Variants ({variants.length})
                </h3>
                <button
                  onClick={handleGenerateVariants}
                  disabled={generatingVariants || !selectedConfigId}
                  className="flex items-center gap-1.5 px-3 py-1.5 text-xs text-accent hover:bg-accent/10 border border-accent/30 rounded-lg transition-colors disabled:opacity-40"
                >
                  {generatingVariants ? <Loader2 className="w-3 h-3 animate-spin" /> : <Sparkles className="w-3 h-3" />}
                  Generate more
                </button>
              </div>
              {variants.map((v) => (
                <div key={v.id} className="border border-visible rounded-lg p-4 space-y-2 bg-surface-50">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-medium text-primary">{v.variant_name || v.label || v.name || `Variant #${v.id}`}</span>
                      {v.is_original && (
                        <span className="px-1.5 py-0.5 text-[10px] bg-green-500/20 text-green-400 rounded-full">Original</span>
                      )}
                    </div>
                    {!v.is_original && (
                      <button onClick={() => handleDeleteVariant(v.id)} className="text-red-400 hover:text-red-300">
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    )}
                  </div>
                  {v.description && (
                    <p className="text-xs text-muted">{v.description}</p>
                  )}
                  <pre className="text-xs text-t-secondary font-mono whitespace-pre-wrap bg-surface-100 rounded-lg p-3 border border-visible max-h-32 overflow-y-auto">
                    {v.system_prompt || v.prompt || "---"}
                  </pre>
                </div>
              ))}
            </div>
          )}

          {/* ════ Summary + Save footer ════ */}
          <div className="bg-surface-100 rounded-2xl border border-surface-200/50 p-6">
            <div className="grid grid-cols-3 gap-4 mb-5">
              <div className="text-center rounded-lg bg-surface-50 py-3">
                <p className="text-xs text-t-secondary mb-1">Tools</p>
                <p className="text-2xl font-bold text-primary">{tools.length}</p>
              </div>
              <div className="text-center rounded-lg bg-surface-50 py-3">
                <p className="text-xs text-t-secondary mb-1">Constraints</p>
                <p className="text-2xl font-bold text-primary">{constraints.length}</p>
              </div>
              <div className="text-center rounded-lg bg-surface-50 py-3">
                <p className="text-xs text-t-secondary mb-1">Prompt Variants</p>
                <p className="text-2xl font-bold text-primary">{variants.length || "—"}</p>
              </div>
            </div>

            <button
              onClick={handleSave}
              disabled={saving || !name.trim()}
              className="w-full flex items-center justify-center gap-2 px-5 py-2.5 bg-surface-50 border border-visible text-t-hover font-medium rounded-xl hover:border-accent/50 hover:text-primary transition-colors disabled:opacity-50"
            >
              {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
              {selectedConfigId ? "Update Agent" : "Save Agent"}
            </button>
          </div>

          {/* Continue CTA — outside the summary card */}
          <button
            onClick={() => selectedConfigId && onComplete?.(selectedConfigId)}
            disabled={!selectedConfigId}
            className="w-full py-3 px-6 bg-gradient-to-r from-accent to-accent-dark text-primary font-medium rounded-xl hover:opacity-90 transition-opacity disabled:opacity-50 flex items-center justify-center gap-2"
          >
            <Bot className="w-4 h-4" />
            {selectedConfigId ? "Continue to Create Scenarios" : "Save agent to continue"}
          </button>
        </>
      )}
    </div>
  );
}
