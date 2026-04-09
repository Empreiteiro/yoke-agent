"use client";

import { useState, useEffect, useCallback } from "react";
import { Users, Plus, Trash2, Loader2, AlertCircle, Sparkles, X, Check, Filter, UserPlus } from "lucide-react";
import { api } from "@/lib/api";

interface StepAgentPersonasProps {
  agentConfigId: number | null;
}

const EXPERTISE_COLORS: Record<string, string> = {
  beginner: "bg-green-500/20 text-green-400",
  intermediate: "bg-blue-500/20 text-blue-400",
  advanced: "bg-purple-500/20 text-purple-400",
  expert: "bg-amber-500/20 text-amber-400",
};

export default function StepAgentPersonas({ agentConfigId }: StepAgentPersonasProps) {
  const [personas, setPersonas] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showAddForm, setShowAddForm] = useState(false);
  const [groupFilter, setGroupFilter] = useState<string>("");
  const [templates, setTemplates] = useState<any[]>([]);
  const [loadingTemplates, setLoadingTemplates] = useState(false);

  // Generate form
  const [genAudience, setGenAudience] = useState("");
  const [genCount, setGenCount] = useState(5);
  const [genInteractionCount, setGenInteractionCount] = useState(3);
  const [showGenerateForm, setShowGenerateForm] = useState(false);

  // Add form
  const [formName, setFormName] = useState("");
  const [formRole, setFormRole] = useState("");
  const [formExpertise, setFormExpertise] = useState("intermediate");
  const [formStyle, setFormStyle] = useState("");
  const [formTraits, setFormTraits] = useState("");
  const [formGroup, setFormGroup] = useState("");

  const loadPersonas = useCallback(async () => {
    if (!agentConfigId) return;
    setLoading(true);
    try {
      const data = await api.listPersonas(agentConfigId, groupFilter || undefined);
      setPersonas(data);
    } catch (err: any) {
      setError(err.message || "Failed to load personas");
    } finally {
      setLoading(false);
    }
  }, [agentConfigId, groupFilter]);

  useEffect(() => {
    loadPersonas();
  }, [loadPersonas]);

  const loadTemplates = useCallback(async () => {
    if (!agentConfigId) return;
    setLoadingTemplates(true);
    try {
      const data = await api.getPersonaTemplates(agentConfigId);
      setTemplates(data);
    } catch {
      // ignore
    } finally {
      setLoadingTemplates(false);
    }
  }, [agentConfigId]);

  useEffect(() => {
    if (agentConfigId) loadTemplates();
  }, [agentConfigId, loadTemplates]);

  const handleGenerate = async () => {
    if (!agentConfigId || !genAudience.trim()) return;
    setGenerating(true);
    setError(null);
    try {
      const newPersonas = await api.generatePersonas(agentConfigId, {
        audience_description: genAudience.trim(),
        count: genCount,
        interaction_count: genInteractionCount,
      });
      setPersonas((prev) => [...prev, ...newPersonas]);
      setShowGenerateForm(false);
      setGenAudience("");
    } catch (err: any) {
      setError(err.message || "Failed to generate personas");
    } finally {
      setGenerating(false);
    }
  };

  const handleAdd = async () => {
    if (!agentConfigId || !formName.trim()) return;
    setError(null);
    try {
      const persona = await api.createPersona(agentConfigId, {
        name: formName.trim(),
        role: formRole.trim(),
        expertise_level: formExpertise,
        communication_style: formStyle.trim(),
        traits: formTraits.split(",").map((t) => t.trim()).filter(Boolean),
        group: formGroup.trim() || undefined,
      });
      setPersonas((prev) => [...prev, persona]);
      resetAddForm();
    } catch (err: any) {
      setError(err.message || "Failed to create persona");
    }
  };

  const handleAddTemplate = async (template: any) => {
    if (!agentConfigId) return;
    setError(null);
    try {
      const persona = await api.createPersona(agentConfigId, template);
      setPersonas((prev) => [...prev, persona]);
    } catch (err: any) {
      setError(err.message || "Failed to add template persona");
    }
  };

  const handleDelete = async (personaId: number) => {
    if (!agentConfigId) return;
    try {
      await api.deletePersona(agentConfigId, personaId);
      setPersonas((prev) => prev.filter((p) => p.id !== personaId));
    } catch (err: any) {
      setError(err.message || "Failed to delete persona");
    }
  };

  const resetAddForm = () => {
    setShowAddForm(false);
    setFormName("");
    setFormRole("");
    setFormExpertise("intermediate");
    setFormStyle("");
    setFormTraits("");
    setFormGroup("");
  };

  const uniqueGroups = Array.from(new Set(personas.map((p) => p.group).filter(Boolean)));

  if (!agentConfigId) {
    return (
      <div className="flex flex-col items-center justify-center py-20 text-center">
        <div className="w-14 h-14 rounded-2xl bg-accent/10 flex items-center justify-center mb-4">
          <Users className="w-7 h-7 text-accent" />
        </div>
        <h2 className="text-xl font-semibold text-primary mb-2">Create Personas</h2>
        <p className="text-sm text-t-secondary max-w-md">
          Please define an agent configuration first before creating personas.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-3">
        <div className="w-10 h-10 rounded-xl bg-accent/20 flex items-center justify-center">
          <Users className="w-5 h-5 text-accent" />
        </div>
        <div>
          <h2 className="text-lg font-semibold text-primary">Personas</h2>
          <p className="text-sm text-t-secondary">Define synthetic user profiles for diverse interactions</p>
        </div>
      </div>

      {/* Actions row */}
      <div className="flex items-center gap-3 flex-wrap">
        <button
          onClick={() => { setShowAddForm(true); setShowGenerateForm(false); }}
          className="flex items-center gap-2 px-4 py-2 text-sm bg-accent/20 text-accent rounded-lg hover:bg-accent/30 transition-colors"
        >
          <Plus className="w-4 h-4" /> Add Persona
        </button>
        <button
          onClick={() => { setShowGenerateForm(true); setShowAddForm(false); }}
          className="flex items-center gap-2 px-4 py-2 text-sm bg-secondary/20 text-secondary rounded-lg hover:bg-secondary/30 transition-colors"
        >
          <Sparkles className="w-4 h-4" /> Generate Personas
        </button>

        {/* Group filter */}
        {uniqueGroups.length > 0 && (
          <div className="flex items-center gap-2 ml-auto">
            <Filter className="w-4 h-4 text-t-secondary" />
            <select
              value={groupFilter}
              onChange={(e) => setGroupFilter(e.target.value)}
              className="px-3 py-2 bg-surface-100 border border-surface-200/50 rounded-lg text-primary text-sm focus:outline-none focus:ring-2 focus:ring-accent/40"
            >
              <option value="">All Groups</option>
              {uniqueGroups.map((g) => (
                <option key={g} value={g}>{g}</option>
              ))}
            </select>
          </div>
        )}
      </div>

      {/* Error */}
      {error && (
        <div className="flex items-center gap-2 p-3 bg-red-500/10 border border-red-500/30 rounded-lg text-red-400 text-sm">
          <AlertCircle className="w-4 h-4 flex-shrink-0" />
          {error}
        </div>
      )}

      {/* Generate form */}
      {showGenerateForm && (
        <div className="bg-surface-100 rounded-xl border border-secondary/30 p-5 space-y-4">
          <h4 className="text-sm font-semibold text-primary">Generate Personas with AI</h4>
          <div>
            <label className="block text-xs text-t-secondary mb-1">Audience Description</label>
            <textarea
              value={genAudience}
              onChange={(e) => setGenAudience(e.target.value)}
              placeholder="Describe your target audience (e.g., technical support users ranging from beginners to experts)"
              rows={3}
              className="w-full px-3 py-2 bg-surface-100 border border-surface-200/50 rounded-lg text-primary text-sm placeholder:text-t-secondary/50 focus:outline-none focus:ring-2 focus:ring-accent/40 resize-y"
            />
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-xs text-t-secondary mb-1">Count</label>
              <input
                type="number"
                value={genCount}
                onChange={(e) => setGenCount(parseInt(e.target.value) || 5)}
                min={1}
                max={20}
                className="w-full px-3 py-2 bg-surface-100 border border-surface-200/50 rounded-lg text-primary text-sm focus:outline-none focus:ring-2 focus:ring-accent/40"
              />
            </div>
            <div>
              <label className="block text-xs text-t-secondary mb-1">Interaction Count</label>
              <input
                type="number"
                value={genInteractionCount}
                onChange={(e) => setGenInteractionCount(parseInt(e.target.value) || 3)}
                min={1}
                max={20}
                className="w-full px-3 py-2 bg-surface-100 border border-surface-200/50 rounded-lg text-primary text-sm focus:outline-none focus:ring-2 focus:ring-accent/40"
              />
            </div>
          </div>
          <div className="flex gap-2">
            <button
              onClick={handleGenerate}
              disabled={generating || !genAudience.trim()}
              className="flex items-center gap-1.5 px-4 py-2 text-sm bg-secondary text-primary rounded-lg hover:bg-secondary/90 transition-colors disabled:opacity-50"
            >
              {generating ? <Loader2 className="w-4 h-4 animate-spin" /> : <Sparkles className="w-4 h-4" />}
              Generate
            </button>
            <button
              onClick={() => setShowGenerateForm(false)}
              className="px-4 py-2 text-sm bg-surface-200/50 text-t-secondary rounded-lg hover:text-primary transition-colors"
            >
              Cancel
            </button>
          </div>
        </div>
      )}

      {/* Add persona form */}
      {showAddForm && (
        <div className="bg-surface-100 rounded-xl border border-accent/30 p-5 space-y-3">
          <h4 className="text-sm font-semibold text-primary">Add Persona</h4>
          <div className="grid grid-cols-2 gap-3">
            <input
              type="text"
              value={formName}
              onChange={(e) => setFormName(e.target.value)}
              placeholder="Name"
              className="px-3 py-2 bg-surface-100 border border-surface-200/50 rounded-lg text-primary text-sm placeholder:text-t-secondary/50 focus:outline-none focus:ring-2 focus:ring-accent/40"
            />
            <input
              type="text"
              value={formRole}
              onChange={(e) => setFormRole(e.target.value)}
              placeholder="Role (e.g., Developer)"
              className="px-3 py-2 bg-surface-100 border border-surface-200/50 rounded-lg text-primary text-sm placeholder:text-t-secondary/50 focus:outline-none focus:ring-2 focus:ring-accent/40"
            />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <select
              value={formExpertise}
              onChange={(e) => setFormExpertise(e.target.value)}
              className="px-3 py-2 bg-surface-100 border border-surface-200/50 rounded-lg text-primary text-sm focus:outline-none focus:ring-2 focus:ring-accent/40"
            >
              <option value="beginner">Beginner</option>
              <option value="intermediate">Intermediate</option>
              <option value="advanced">Advanced</option>
              <option value="expert">Expert</option>
            </select>
            <input
              type="text"
              value={formStyle}
              onChange={(e) => setFormStyle(e.target.value)}
              placeholder="Communication style"
              className="px-3 py-2 bg-surface-100 border border-surface-200/50 rounded-lg text-primary text-sm placeholder:text-t-secondary/50 focus:outline-none focus:ring-2 focus:ring-accent/40"
            />
          </div>
          <input
            type="text"
            value={formTraits}
            onChange={(e) => setFormTraits(e.target.value)}
            placeholder="Traits (comma-separated)"
            className="w-full px-3 py-2 bg-surface-100 border border-surface-200/50 rounded-lg text-primary text-sm placeholder:text-t-secondary/50 focus:outline-none focus:ring-2 focus:ring-accent/40"
          />
          <input
            type="text"
            value={formGroup}
            onChange={(e) => setFormGroup(e.target.value)}
            placeholder="Group (optional)"
            className="w-full px-3 py-2 bg-surface-100 border border-surface-200/50 rounded-lg text-primary text-sm placeholder:text-t-secondary/50 focus:outline-none focus:ring-2 focus:ring-accent/40"
          />
          <div className="flex gap-2">
            <button
              onClick={handleAdd}
              disabled={!formName.trim()}
              className="flex items-center gap-1.5 px-4 py-2 text-sm bg-accent text-primary rounded-lg hover:bg-accent/90 transition-colors disabled:opacity-50"
            >
              <Check className="w-3.5 h-3.5" /> Add
            </button>
            <button onClick={resetAddForm} className="px-4 py-2 text-sm bg-surface-200/50 text-t-secondary rounded-lg hover:text-primary transition-colors">
              Cancel
            </button>
          </div>
        </div>
      )}

      {/* Templates */}
      {templates.length > 0 && (
        <div className="bg-surface-100 rounded-xl border border-surface-200/50 p-4">
          <h4 className="text-xs font-semibold text-t-secondary uppercase tracking-wider mb-3">Quick Add Templates</h4>
          <div className="flex flex-wrap gap-2">
            {templates.map((t, idx) => (
              <button
                key={idx}
                onClick={() => handleAddTemplate(t)}
                className="flex items-center gap-1.5 px-3 py-1.5 text-xs bg-surface-100 border border-surface-200/50 rounded-lg text-t-secondary hover:text-accent hover:border-accent/30 transition-colors"
              >
                <UserPlus className="w-3 h-3" />
                {t.name}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Persona grid */}
      {loading ? (
        <div className="flex items-center justify-center py-12 text-t-secondary">
          <Loader2 className="w-5 h-5 animate-spin mr-2" />
          Loading personas...
        </div>
      ) : personas.length === 0 ? (
        <div className="text-center py-12 text-t-secondary text-sm">
          No personas yet. Add manually, use templates, or generate with AI.
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {personas.map((p) => (
            <div key={p.id} className="bg-surface-100 rounded-xl border border-surface-200/50 p-4 space-y-3">
              <div className="flex items-start justify-between">
                <div>
                  <h4 className="text-sm font-semibold text-primary">{p.name}</h4>
                  {p.role && <p className="text-xs text-t-secondary">{p.role}</p>}
                </div>
                <button onClick={() => handleDelete(p.id)} className="text-t-secondary hover:text-red-400 transition-colors">
                  <Trash2 className="w-3.5 h-3.5" />
                </button>
              </div>

              <div className="flex items-center gap-2 flex-wrap">
                {p.expertise_level && (
                  <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${EXPERTISE_COLORS[p.expertise_level] || "bg-surface-200/50 text-t-secondary"}`}>
                    {p.expertise_level}
                  </span>
                )}
                {p.group && (
                  <span className="px-2 py-0.5 rounded-full text-xs bg-surface-200/50 text-t-secondary">
                    {p.group}
                  </span>
                )}
              </div>

              {p.communication_style && (
                <p className="text-xs text-t-secondary">
                  <span className="font-medium">Style:</span> {p.communication_style}
                </p>
              )}

              {p.traits && p.traits.length > 0 && (
                <div className="flex flex-wrap gap-1">
                  {(Array.isArray(p.traits) ? p.traits : []).map((trait: string, i: number) => (
                    <span key={i} className="px-1.5 py-0.5 rounded text-xs bg-accent/10 text-accent/80">
                      {trait}
                    </span>
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
