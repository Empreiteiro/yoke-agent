"use client";

import { useState, useEffect, useCallback } from "react";
import {
  Settings,
  Plus,
  Trash2,
  Zap,
  Check,
  X,
  AlertCircle,
  Loader2,
  Eye,
  EyeOff,
  Brain,
  Box,
  ChevronDown,
  ChevronUp,
  Sparkles,
  Pencil,
} from "lucide-react";
import { api } from "@/lib/api";

interface Provider {
  id: number;
  name: string;
  provider_type: string;
  base_url?: string;
  is_active: boolean;
  supports_llm: boolean;
  supports_embedding: boolean;
  llm_models: string[];
  embedding_models: string[];
  default_llm_model?: string;
  default_embedding_model?: string;
  extra_config: Record<string, any>;
  has_api_key: boolean;
}

interface CatalogEntry {
  label: string;
  supports_llm: boolean;
  supports_embedding: boolean;
  llm_models: string[];
  embedding_models: string[];
  requires_api_key: boolean;
  supports_base_url: boolean;
  default_base_url?: string;
}

const PROVIDER_ICONS: Record<string, string> = {
  openai: "🟢",
  anthropic: "🟤",
  google: "🔵",
  cohere: "🟣",
  ollama: "🦙",
  azure_openai: "☁️",
  huggingface: "🤗",
  claude_code: "🟠",
  custom: "⚙️",
};

export default function SettingsProviders() {
  const [providers, setProviders] = useState<Provider[]>([]);
  const [catalog, setCatalog] = useState<Record<string, CatalogEntry>>({});
  const [loading, setLoading] = useState(true);
  const [showAddForm, setShowAddForm] = useState(false);
  const [expandedId, setExpandedId] = useState<number | null>(null);
  const [testingId, setTestingId] = useState<number | null>(null);
  const [testResult, setTestResult] = useState<Record<number, any>>({});
  const [error, setError] = useState<string | null>(null);

  const loadData = useCallback(async () => {
    try {
      const [provs, cat] = await Promise.all([
        api.listProviders(),
        api.getProviderCatalog(),
      ]);
      setProviders(provs);
      setCatalog(cat);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const handleTest = async (id: number) => {
    setTestingId(id);
    try {
      const result = await api.testProvider(id);
      setTestResult((prev) => ({ ...prev, [id]: result }));
    } catch (e: any) {
      setTestResult((prev) => ({
        ...prev,
        [id]: { success: false, message: e.message },
      }));
    } finally {
      setTestingId(null);
    }
  };

  const handleDelete = async (id: number) => {
    try {
      await api.deleteProvider(id);
      setProviders((prev) => prev.filter((p) => p.id !== id));
    } catch (e: any) {
      setError(e.message);
    }
  };

  const handleToggleActive = async (provider: Provider) => {
    try {
      const updated = await api.updateProvider(provider.id, {
        is_active: !provider.is_active,
      });
      setProviders((prev) =>
        prev.map((p) => (p.id === provider.id ? updated : p))
      );
    } catch (e: any) {
      setError(e.message);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="w-8 h-8 text-accent animate-spin" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Settings className="w-6 h-6 text-accent" />
          <div>
            <h2 className="text-xl font-bold text-primary">LLM & Embedding Providers</h2>
            <p className="text-sm text-t-secondary">
              Configure AI providers for dataset generation, RAG pipeline, and evaluation
            </p>
          </div>
        </div>
        <button
          onClick={() => setShowAddForm(!showAddForm)}
          className="flex items-center gap-2 px-4 py-2 bg-accent text-primary rounded-xl hover:bg-accent/90 transition-colors"
        >
          <Plus className="w-4 h-4" />
          Add Provider
        </button>
      </div>

      {error && (
        <div className="flex items-center gap-2 px-4 py-3 bg-red-500/10 border border-red-500/20 rounded-xl text-red-400 text-sm">
          <AlertCircle className="w-4 h-4 shrink-0" />
          {error}
          <button onClick={() => setError(null)} className="ml-auto">
            <X className="w-4 h-4" />
          </button>
        </div>
      )}

      {/* Add Provider Form */}
      {showAddForm && (
        <AddProviderForm
          catalog={catalog}
          onCreated={(p) => {
            setProviders((prev) => [p, ...prev]);
            setShowAddForm(false);
          }}
          onCancel={() => setShowAddForm(false)}
        />
      )}

      {/* Provider List */}
      {providers.length === 0 && !showAddForm ? (
        <div className="bg-surface-100 rounded-2xl border border-visible p-12 text-center">
          <Sparkles className="w-12 h-12 text-muted mx-auto mb-4" />
          <h3 className="text-lg font-semibold text-primary mb-2">
            No providers configured
          </h3>
          <p className="text-sm text-t-secondary mb-6">
            Add an AI provider to start using the pipeline. OpenAI, Anthropic, Google, Ollama, and more are supported.
          </p>
          <button
            onClick={() => setShowAddForm(true)}
            className="px-6 py-3 bg-accent text-primary rounded-xl hover:bg-accent/90 transition-colors"
          >
            Add your first provider
          </button>
        </div>
      ) : (
        <div className="space-y-3">
          {providers.map((provider) => (
            <div
              key={provider.id}
              className="bg-surface-100 rounded-2xl border border-visible overflow-hidden"
            >
              {/* Provider header row */}
              <div className="flex items-center gap-4 px-6 py-4">
                <span className="text-2xl">{PROVIDER_ICONS[provider.provider_type] || "⚙️"}</span>
                <div className="flex-1 min-w-0">
                  <h3 className="font-semibold text-primary truncate">{provider.name}</h3>
                  <div className="flex items-center gap-3 mt-1">
                    {provider.supports_llm && (
                      <span className="flex items-center gap-1 text-xs text-accent font-medium">
                        <Brain className="w-3 h-3" />
                        {provider.llm_models.length} LLM{provider.llm_models.length !== 1 ? "s" : ""}
                      </span>
                    )}
                    {provider.supports_embedding && (
                      <span className="flex items-center gap-1 text-xs text-secondary font-medium">
                        <Box className="w-3 h-3" />
                        {provider.embedding_models.length} Embedding{provider.embedding_models.length !== 1 ? "s" : ""}
                      </span>
                    )}
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  {/* Test button */}
                  <button
                    onClick={() => handleTest(provider.id)}
                    disabled={testingId === provider.id}
                    className="p-2 hover:bg-surface-200 rounded-lg transition-colors"
                    title="Test connection"
                  >
                    {testingId === provider.id ? (
                      <Loader2 className="w-4 h-4 text-accent animate-spin" />
                    ) : testResult[provider.id]?.success === true ? (
                      <Check className="w-4 h-4 text-emerald-400" />
                    ) : testResult[provider.id]?.success === false ? (
                      <AlertCircle className="w-4 h-4 text-red-400" />
                    ) : (
                      <Zap className="w-4 h-4 text-t-secondary" />
                    )}
                  </button>
                  {/* Toggle active */}
                  <button
                    onClick={() => handleToggleActive(provider)}
                    className={`px-3 py-1 text-xs rounded-full transition-colors ${
                      provider.is_active
                        ? "bg-emerald-500/20 text-emerald-400"
                        : "bg-surface-200 text-muted"
                    }`}
                  >
                    {provider.is_active ? "Active" : "Inactive"}
                  </button>
                  {/* Edit / Expand */}
                  <button
                    onClick={() => setExpandedId(expandedId === provider.id ? null : provider.id)}
                    className="flex items-center gap-1 px-2.5 py-1.5 hover:bg-surface-200 rounded-lg transition-colors"
                    title={expandedId === provider.id ? "Collapse" : "Edit provider"}
                  >
                    <Pencil className="w-3.5 h-3.5 text-t-secondary" />
                    {expandedId === provider.id ? (
                      <ChevronUp className="w-4 h-4 text-t-secondary" />
                    ) : (
                      <ChevronDown className="w-4 h-4 text-t-secondary" />
                    )}
                  </button>
                  {/* Delete */}
                  <button
                    onClick={() => handleDelete(provider.id)}
                    className="p-2 hover:bg-red-500/10 rounded-lg transition-colors"
                  >
                    <Trash2 className="w-4 h-4 text-muted hover:text-red-400" />
                  </button>
                </div>
              </div>

              {/* Test result banner */}
              {testResult[provider.id] && (
                <div
                  className={`px-6 py-2 text-xs ${
                    testResult[provider.id].success
                      ? "bg-emerald-500/10 text-emerald-400"
                      : "bg-red-500/10 text-red-400"
                  }`}
                >
                  {testResult[provider.id].message}
                </div>
              )}

              {/* Expanded details */}
              {expandedId === provider.id && (
                <ProviderDetails
                  provider={provider}
                  catalog={catalog[provider.provider_type]}
                  onUpdate={(updated) =>
                    setProviders((prev) =>
                      prev.map((p) => (p.id === updated.id ? updated : p))
                    )
                  }
                />
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

/* ==================== Add Provider Form ==================== */

function AddProviderForm({
  catalog,
  onCreated,
  onCancel,
}: {
  catalog: Record<string, CatalogEntry>;
  onCreated: (p: Provider) => void;
  onCancel: () => void;
}) {
  const [providerType, setProviderType] = useState("");
  const [name, setName] = useState("");
  const [apiKey, setApiKey] = useState("");
  const [baseUrl, setBaseUrl] = useState("");
  const [showKey, setShowKey] = useState(false);
  const [selectedLlmModels, setSelectedLlmModels] = useState<string[]>([]);
  const [selectedEmbModels, setSelectedEmbModels] = useState<string[]>([]);
  const [customModel, setCustomModel] = useState("");
  const [customEmbModel, setCustomEmbModel] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [discovering, setDiscovering] = useState(false);
  const [discoveredLlm, setDiscoveredLlm] = useState<string[]>([]);
  const [discoveredEmb, setDiscoveredEmb] = useState<string[]>([]);

  const isOllama = providerType === "ollama";
  const isClaudeCode = providerType === "claude_code";
  const supportsFlex = providerType === "openai" || providerType === "google";
  const [flexTier, setFlexTier] = useState(false);
  const [claudeStatus, setClaudeStatus] = useState<any>(null);
  const [claudeToken, setClaudeToken] = useState("");
  const [savingToken, setSavingToken] = useState(false);
  const [tokenSaved, setTokenSaved] = useState(false);

  useEffect(() => {
    if (isClaudeCode) {
      api.getClaudeCodeStatus().then(setClaudeStatus).catch(() => {});
    }
  }, [isClaudeCode]);

  const handleSaveClaudeToken = async () => {
    if (!claudeToken.trim()) return;
    setSavingToken(true);
    try {
      const res = await api.saveClaudeCodeToken(claudeToken.trim());
      setClaudeStatus(res.status);
      setTokenSaved(true);
      setTimeout(() => setTokenSaved(false), 3000);
    } catch (e: any) {
      setError(e.message || "Failed to save token");
    } finally {
      setSavingToken(false);
    }
  };

  const handleDiscover = async () => {
    if (!baseUrl) return;
    setDiscovering(true);
    setError(null);
    try {
      const result = await api.discoverOllamaModels(baseUrl);
      setDiscoveredLlm(result.llm_models);
      setDiscoveredEmb(result.embedding_models);
      setSelectedLlmModels(result.llm_models);
      setSelectedEmbModels(result.embedding_models);
    } catch (e: any) {
      setError(e.message || "Failed to discover models");
    } finally {
      setDiscovering(false);
    }
  };

  const entry = providerType ? catalog[providerType] : null;

  useEffect(() => {
    if (entry) {
      setName(entry.label);
      setSelectedLlmModels(entry.llm_models.slice(0, 3));
      setSelectedEmbModels(entry.embedding_models.slice(0, 2));
      setBaseUrl(entry.default_base_url || "");
    }
  }, [providerType, entry]);

  const toggleModel = (model: string, list: string[], setter: (v: string[]) => void) => {
    setter(list.includes(model) ? list.filter((m) => m !== model) : [...list, model]);
  };

  const addCustomModel = (model: string, list: string[], setter: (v: string[]) => void, clearFn: (v: string) => void) => {
    if (model.trim() && !list.includes(model.trim())) {
      setter([...list, model.trim()]);
      clearFn("");
    }
  };

  const handleSave = async () => {
    if (!providerType || !name) return;
    setSaving(true);
    setError(null);

    try {
      const provider = await api.createProvider({
        name,
        provider_type: providerType,
        api_key: apiKey || undefined,
        base_url: baseUrl || undefined,
        is_active: true,
        supports_llm: entry?.supports_llm ?? true,
        supports_embedding: entry?.supports_embedding ?? false,
        llm_models: selectedLlmModels,
        embedding_models: selectedEmbModels,
        default_llm_model: selectedLlmModels[0] || undefined,
        default_embedding_model: selectedEmbModels[0] || undefined,
        extra_config: supportsFlex && flexTier ? { flex_tier: true } : {},
      });
      onCreated(provider);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="bg-surface-100 rounded-2xl border border-visible p-6 space-y-5">
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-semibold text-primary">Add Provider</h3>
        <button onClick={onCancel} className="p-1 hover:bg-surface-200 rounded-lg">
          <X className="w-5 h-5 text-t-secondary" />
        </button>
      </div>

      {/* Provider type selection */}
      <div>
        <label className="block text-sm font-medium text-t-secondary mb-2">
          Provider Type
        </label>
        <div className="grid grid-cols-4 gap-2">
          {Object.entries(catalog).map(([key, val]) => (
            <button
              key={key}
              onClick={() => setProviderType(key)}
              className={`flex items-center gap-2 px-3 py-2.5 rounded-xl border text-sm transition-all ${
                providerType === key
                  ? "border-accent bg-accent/10 text-primary"
                  : "border-visible text-t-secondary hover:border-surface-300"
              }`}
            >
              <span>{PROVIDER_ICONS[key]}</span>
              <span className="truncate">{val.label}</span>
            </button>
          ))}
        </div>
      </div>

      {entry && (
        <>
          {/* Name */}
          <div>
            <label className="block text-sm font-medium text-t-secondary mb-1">Display Name</label>
            <input
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="w-full px-4 py-2.5 bg-surface-50 border border-visible rounded-xl text-primary text-sm focus:outline-none focus:border-accent"
            />
          </div>

          {/* API Key */}
          {entry.requires_api_key && (
            <div>
              <label className="block text-sm font-medium text-t-secondary mb-1">API Key</label>
              <div className="relative">
                <input
                  type={showKey ? "text" : "password"}
                  value={apiKey}
                  onChange={(e) => setApiKey(e.target.value)}
                  placeholder="sk-..."
                  className="w-full px-4 py-2.5 pr-10 bg-surface-50 border border-visible rounded-xl text-primary text-sm focus:outline-none focus:border-accent"
                />
                <button
                  type="button"
                  onClick={() => setShowKey(!showKey)}
                  className="absolute right-3 top-1/2 -translate-y-1/2"
                >
                  {showKey ? (
                    <EyeOff className="w-4 h-4 text-muted" />
                  ) : (
                    <Eye className="w-4 h-4 text-muted" />
                  )}
                </button>
              </div>
            </div>
          )}

          {/* Flex tier — OpenAI and Google Gemini */}
          {supportsFlex && (
            <div className="bg-surface-50 rounded-xl border border-visible p-4">
              <label className="flex items-start gap-3 cursor-pointer">
                <input
                  type="checkbox"
                  checked={flexTier}
                  onChange={(e) => setFlexTier(e.target.checked)}
                  className="mt-0.5 w-4 h-4 accent-accent"
                />
                <div className="flex-1">
                  <div className="text-sm font-medium text-primary flex items-center gap-2">
                    Use Flex service tier
                    <span className="px-1.5 py-0.5 text-[10px] font-bold rounded bg-emerald-500/15 text-emerald-400 uppercase">
                      ~50% cheaper
                    </span>
                  </div>
                  <p className="text-xs text-t-secondary mt-1">
                    Sends requests with{" "}
                    <code className="px-1 bg-surface-200/50 rounded text-accent">service_tier=flex</code>.
                    Best-effort latency (may be slower under load), no SLA, but
                    roughly half the price of standard on-demand.{" "}
                    {providerType === "openai"
                      ? "Supported on o3, o4-mini, and the gpt-5 family (gpt-5, gpt-5-mini, gpt-5-nano)."
                      : "Supported on gemini-2.5-pro, gemini-2.5-flash, gemini-2.5-flash-lite, and the gemini-3.x preview lineage."}
                  </p>
                </div>
              </label>
            </div>
          )}

          {/* Base URL */}
          {entry.supports_base_url && (
            <div>
              <label className="block text-sm font-medium text-t-secondary mb-1">Base URL</label>
              <div className="flex gap-2">
                <input
                  value={baseUrl}
                  onChange={(e) => setBaseUrl(e.target.value)}
                  placeholder={entry.default_base_url || "https://..."}
                  className="flex-1 px-4 py-2.5 bg-surface-50 border border-visible rounded-xl text-primary text-sm focus:outline-none focus:border-accent"
                />
                {isOllama && (
                  <button
                    onClick={handleDiscover}
                    disabled={discovering || !baseUrl}
                    className="px-4 py-2.5 bg-accent text-primary rounded-xl text-sm font-medium hover:bg-accent/90 transition-colors disabled:opacity-50 flex items-center gap-2 whitespace-nowrap"
                  >
                    {discovering ? <Loader2 className="w-4 h-4 animate-spin" /> : <Zap className="w-4 h-4" />}
                    {discovering ? "Discovering..." : "Discover Models"}
                  </button>
                )}
              </div>
              {isOllama && <p className="text-xs text-muted mt-1.5">Enter the Ollama server URL and click Discover to fetch available models.</p>}
            </div>
          )}

          {/* Claude Code CLI — status & auth */}
          {isClaudeCode && (
            <div className="bg-surface-50 rounded-xl border border-surface-200/50 p-4 space-y-3">
              <div className="flex items-center gap-2">
                <span className="text-sm font-medium text-primary">Claude Code CLI Status</span>
              </div>

              {claudeStatus ? (
                <div className="space-y-2">
                  <div className="flex items-center gap-2 text-sm">
                    <span className={claudeStatus.installed ? "text-emerald-400" : "text-red-400"}>
                      {claudeStatus.installed ? "✓" : "✗"}
                    </span>
                    <span className="text-t-secondary">
                      {claudeStatus.installed ? `CLI found: ${claudeStatus.binary_path?.split("/").pop()}` : "CLI not found"}
                    </span>
                  </div>
                  <div className="flex items-center gap-2 text-sm">
                    <span className={claudeStatus.authenticated ? "text-emerald-400" : "text-amber-400"}>
                      {claudeStatus.authenticated ? "✓" : "⚠"}
                    </span>
                    <span className="text-t-secondary">
                      {claudeStatus.authenticated ? "Authenticated" : "Not authenticated"}
                    </span>
                  </div>
                  {!claudeStatus.authenticated && claudeStatus.error && (
                    <p className="text-xs text-amber-400/80">{claudeStatus.error}</p>
                  )}
                </div>
              ) : (
                <div className="flex items-center gap-2 text-sm text-t-secondary">
                  <Loader2 className="w-3.5 h-3.5 animate-spin" />
                  Checking status...
                </div>
              )}

              {claudeStatus && !claudeStatus.authenticated && (
                <div className="space-y-2 pt-2 border-t border-surface-200/50">
                  <p className="text-xs text-t-secondary">
                    Paste your Claude OAuth token below. You can get it by running{" "}
                    <code className="px-1.5 py-0.5 bg-surface-200/50 rounded text-accent text-[11px]">claude auth print-token</code>{" "}
                    in a terminal where Claude CLI is authenticated, or copy the{" "}
                    <code className="px-1.5 py-0.5 bg-surface-200/50 rounded text-accent text-[11px]">CLAUDE_CODE_OAUTH_TOKEN</code>{" "}
                    environment variable from a Claude Desktop session.
                  </p>
                  <div className="flex gap-2">
                    <input
                      type="password"
                      value={claudeToken}
                      onChange={(e) => setClaudeToken(e.target.value)}
                      placeholder="Paste OAuth token..."
                      className="flex-1 px-3 py-2 bg-surface-100 border border-surface-200/50 rounded-lg text-primary text-sm placeholder:text-t-secondary/50 focus:outline-none focus:ring-2 focus:ring-accent/40 font-mono"
                    />
                    <button
                      onClick={handleSaveClaudeToken}
                      disabled={savingToken || !claudeToken.trim()}
                      className="px-4 py-2 bg-accent text-white rounded-lg text-sm font-medium hover:bg-accent/90 transition-colors disabled:opacity-50 flex items-center gap-2 whitespace-nowrap"
                    >
                      {savingToken ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : tokenSaved ? <Check className="w-3.5 h-3.5" /> : null}
                      {tokenSaved ? "Saved!" : "Save Token"}
                    </button>
                  </div>
                </div>
              )}

              {claudeStatus?.authenticated && (
                <p className="text-xs text-emerald-400/80">✓ Ready to use. Save the provider to start using Claude Code.</p>
              )}
            </div>
          )}

          {/* LLM Models */}
          {entry.supports_llm && (
            <div>
              <label className="block text-sm font-medium text-t-secondary mb-2">
                <Brain className="w-4 h-4 inline mr-1 text-accent" />
                LLM Models
                {isOllama && discoveredLlm.length === 0 && <span className="text-xs text-muted font-normal ml-2">(click Discover to load)</span>}
              </label>
              {isOllama && discoveredLlm.length === 0 && !discovering ? (
                <p className="text-xs text-muted px-3 py-3 border border-dashed border-surface-300 rounded-lg text-center">
                  Enter the Base URL above and click &quot;Discover Models&quot; to fetch available models.
                </p>
              ) : (<>
              <div className="flex flex-wrap gap-2 mb-2">
                {(isOllama ? discoveredLlm : entry.llm_models).map((m) => (
                  <button
                    key={m}
                    onClick={() => toggleModel(m, selectedLlmModels, setSelectedLlmModels)}
                    className={`px-3 py-1.5 rounded-lg text-xs transition-all ${
                      selectedLlmModels.includes(m)
                        ? "bg-accent/15 text-accent border border-visible"
                        : "bg-surface-50 text-muted border border-dashed border-surface-300 hover:border-visible hover:text-accent"
                    }`}
                  >
                    {m}
                  </button>
                ))}
                {selectedLlmModels
                  .filter((m) => !(isOllama ? discoveredLlm : entry.llm_models).includes(m))
                  .map((m) => (
                    <button
                      key={m}
                      onClick={() => toggleModel(m, selectedLlmModels, setSelectedLlmModels)}
                      className="px-3 py-1.5 rounded-lg text-xs bg-accent/15 text-accent border border-visible"
                    >
                      {m} ✕
                    </button>
                  ))}
              </div>
              <div className="flex gap-2">
                <input
                  value={customModel}
                  onChange={(e) => setCustomModel(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && addCustomModel(customModel, selectedLlmModels, setSelectedLlmModels, setCustomModel)}
                  placeholder="Add custom model..."
                  className="flex-1 px-3 py-1.5 bg-surface-50 border border-visible rounded-lg text-primary text-xs focus:outline-none focus:border-accent"
                />
                <button
                  onClick={() => addCustomModel(customModel, selectedLlmModels, setSelectedLlmModels, setCustomModel)}
                  className="px-3 py-1.5 bg-surface-200 text-t-hover rounded-lg text-xs hover:bg-surface-300"
                >
                  Add
                </button>
              </div>
              </>)}
            </div>
          )}

          {/* Embedding Models */}
          {entry.supports_embedding && (
            <div>
              <label className="block text-sm font-medium text-t-secondary mb-2">
                <Box className="w-4 h-4 inline mr-1 text-secondary" />
                Embedding Models
                {isOllama && discoveredEmb.length === 0 && <span className="text-xs text-muted font-normal ml-2">(click Discover to load)</span>}
              </label>
              {isOllama && discoveredEmb.length === 0 && !discovering ? (
                <p className="text-xs text-muted px-3 py-3 border border-dashed border-surface-300 rounded-lg text-center">
                  Embedding models will appear after discovery.
                </p>
              ) : (<>
              <div className="flex flex-wrap gap-2 mb-2">
                {(isOllama ? discoveredEmb : entry.embedding_models).map((m) => (
                  <button
                    key={m}
                    onClick={() => toggleModel(m, selectedEmbModels, setSelectedEmbModels)}
                    className={`px-3 py-1.5 rounded-lg text-xs transition-all ${
                      selectedEmbModels.includes(m)
                        ? "bg-secondary/15 text-secondary border border-visible"
                        : "bg-surface-50 text-muted border border-dashed border-surface-300 hover:border-secondary/30 hover:text-secondary"
                    }`}
                  >
                    {m}
                  </button>
                ))}
                {selectedEmbModels
                  .filter((m) => !(isOllama ? discoveredEmb : entry.embedding_models).includes(m))
                  .map((m) => (
                    <button
                      key={m}
                      onClick={() => toggleModel(m, selectedEmbModels, setSelectedEmbModels)}
                      className="px-3 py-1.5 rounded-lg text-xs bg-secondary/15 text-secondary border border-visible"
                    >
                      {m} ✕
                    </button>
                  ))}
              </div>
              <div className="flex gap-2">
                <input
                  value={customEmbModel}
                  onChange={(e) => setCustomEmbModel(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && addCustomModel(customEmbModel, selectedEmbModels, setSelectedEmbModels, setCustomEmbModel)}
                  placeholder="Add custom model..."
                  className="flex-1 px-3 py-1.5 bg-surface-50 border border-visible rounded-lg text-primary text-xs focus:outline-none focus:border-accent"
                />
                <button
                  onClick={() => addCustomModel(customEmbModel, selectedEmbModels, setSelectedEmbModels, setCustomEmbModel)}
                  className="px-3 py-1.5 bg-surface-200 text-t-hover rounded-lg text-xs hover:bg-surface-300"
                >
                  Add
                </button>
              </div>
              </>)}
            </div>
          )}

          {error && (
            <p className="text-sm text-red-400">{error}</p>
          )}

          {/* Save */}
          <div className="flex justify-end gap-3 pt-2">
            <button
              onClick={onCancel}
              className="px-4 py-2 text-sm text-t-secondary hover:text-primary transition-colors"
            >
              Cancel
            </button>
            <button
              onClick={handleSave}
              disabled={saving || !name || !providerType}
              className="px-6 py-2 bg-accent text-primary rounded-xl text-sm hover:bg-accent/90 transition-colors disabled:opacity-50"
            >
              {saving ? "Saving..." : "Save Provider"}
            </button>
          </div>
        </>
      )}
    </div>
  );
}

/* ==================== Provider Details (expanded — full inline edit) ==================== */

function ProviderDetails({
  provider,
  catalog,
  onUpdate,
}: {
  provider: Provider;
  catalog?: CatalogEntry;
  onUpdate: (p: Provider) => void;
}) {
  const [name, setName] = useState(provider.name);
  const [apiKey, setApiKey] = useState("");
  const [baseUrl, setBaseUrl] = useState(provider.base_url || "");
  const [showKey, setShowKey] = useState(false);
  const [llmModels, setLlmModels] = useState<string[]>(provider.llm_models);
  const [embModels, setEmbModels] = useState<string[]>(provider.embedding_models);
  const [defaultLlm, setDefaultLlm] = useState(provider.default_llm_model || "");
  const [defaultEmb, setDefaultEmb] = useState(provider.default_embedding_model || "");
  const [customLlm, setCustomLlm] = useState("");
  const [customEmb, setCustomEmb] = useState("");
  const [flexTier, setFlexTier] = useState<boolean>(
    Boolean(provider.extra_config?.flex_tier)
  );
  const [saving, setSaving] = useState(false);
  const [dirty, setDirty] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const supportsFlex =
    provider.provider_type === "openai" || provider.provider_type === "google";

  const markDirty = () => setDirty(true);

  const toggleModel = (model: string, list: string[], setter: (v: string[]) => void) => {
    setter(list.includes(model) ? list.filter((m) => m !== model) : [...list, model]);
    markDirty();
  };

  const addModel = (value: string, list: string[], setter: (v: string[]) => void, clearFn: (v: string) => void) => {
    if (value.trim() && !list.includes(value.trim())) {
      setter([...list, value.trim()]);
      clearFn("");
      markDirty();
    }
  };

  const removeModel = (model: string, list: string[], setter: (v: string[]) => void) => {
    setter(list.filter((m) => m !== model));
    markDirty();
  };

  const handleSave = async () => {
    setSaving(true);
    setError(null);
    try {
      const payload: any = {
        name,
        base_url: baseUrl || undefined,
        llm_models: llmModels,
        embedding_models: embModels,
        default_llm_model: defaultLlm || (llmModels[0] ?? undefined),
        default_embedding_model: defaultEmb || (embModels[0] ?? undefined),
      };
      if (apiKey) payload.api_key = apiKey;
      if (supportsFlex) {
        payload.extra_config = {
          ...(provider.extra_config || {}),
          flex_tier: flexTier,
        };
      }
      const updated = await api.updateProvider(provider.id, payload);
      onUpdate(updated);
      setApiKey("");
      setDirty(false);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setSaving(false);
    }
  };

  const catalogModels = catalog?.llm_models || [];
  const catalogEmbModels = catalog?.embedding_models || [];

  return (
    <div className="px-6 pb-5 pt-3 border-t border-visible space-y-5">
      {/* Display Name */}
      <div>
        <label className="block text-xs font-medium text-t-secondary mb-1">Display Name</label>
        <input
          value={name}
          onChange={(e) => { setName(e.target.value); markDirty(); }}
          className="w-full px-3 py-2 bg-surface-50 border border-visible rounded-lg text-primary text-sm focus:outline-none focus:border-accent"
        />
      </div>

      {/* API Key */}
      {catalog?.requires_api_key && (
        <div>
          <label className="block text-xs font-medium text-t-secondary mb-1">
            API Key {provider.has_api_key && <span className="text-emerald-400">(currently set)</span>}
          </label>
          <div className="relative">
            <input
              type={showKey ? "text" : "password"}
              value={apiKey}
              onChange={(e) => { setApiKey(e.target.value); markDirty(); }}
              placeholder="Enter new API key to update..."
              className="w-full px-3 py-2 pr-8 bg-surface-50 border border-visible rounded-lg text-primary text-sm focus:outline-none focus:border-accent"
            />
            <button
              onClick={() => setShowKey(!showKey)}
              className="absolute right-2.5 top-1/2 -translate-y-1/2"
            >
              {showKey ? <EyeOff className="w-3.5 h-3.5 text-muted" /> : <Eye className="w-3.5 h-3.5 text-muted" />}
            </button>
          </div>
        </div>
      )}

      {/* Base URL */}
      {catalog?.supports_base_url && (
        <div>
          <label className="block text-xs font-medium text-t-secondary mb-1">Base URL</label>
          <input
            value={baseUrl}
            onChange={(e) => { setBaseUrl(e.target.value); markDirty(); }}
            placeholder={catalog.default_base_url || "https://..."}
            className="w-full px-3 py-2 bg-surface-50 border border-visible rounded-lg text-primary text-sm focus:outline-none focus:border-accent"
          />
        </div>
      )}

      {/* Flex tier — OpenAI and Google Gemini */}
      {supportsFlex && (
        <div className="bg-surface-50 rounded-lg border border-visible p-3">
          <label className="flex items-start gap-3 cursor-pointer">
            <input
              type="checkbox"
              checked={flexTier}
              onChange={(e) => { setFlexTier(e.target.checked); markDirty(); }}
              className="mt-0.5 w-4 h-4 accent-accent"
            />
            <div className="flex-1">
              <div className="text-xs font-medium text-primary flex items-center gap-2">
                Use Flex service tier
                <span className="px-1.5 py-0.5 text-[10px] font-bold rounded bg-emerald-500/15 text-emerald-400 uppercase">
                  ~50% cheaper
                </span>
              </div>
              <p className="text-[11px] text-t-secondary mt-1 leading-relaxed">
                Sends requests with{" "}
                <code className="px-1 bg-surface-200/50 rounded text-accent">service_tier=flex</code>.
                Best-effort latency, no SLA, roughly half the cost.{" "}
                {provider.provider_type === "openai"
                  ? "Supported on o3, o4-mini and the gpt-5 family (gpt-5, gpt-5-mini, gpt-5-nano)."
                  : "Supported on gemini-2.5-pro, gemini-2.5-flash, gemini-2.5-flash-lite and the gemini-3.x preview lineage."}
              </p>
            </div>
          </label>
        </div>
      )}

      {/* LLM Models */}
      {provider.supports_llm && (
        <div>
          <label className="block text-xs font-medium text-t-secondary mb-2">
            <Brain className="w-3.5 h-3.5 inline mr-1 text-accent" />
            LLM Models
            {defaultLlm && <span className="text-muted ml-2">(default: {defaultLlm})</span>}
          </label>
          <div className="flex flex-wrap gap-1.5 mb-2">
            {llmModels.map((m) => (
              <span
                key={m}
                className={`inline-flex items-center gap-1 px-2.5 py-1 rounded-lg text-xs cursor-pointer transition-all ${
                  m === defaultLlm
                    ? "bg-accent/15 text-accent border border-visible"
                    : "bg-surface-200 text-t-hover border border-surface-200"
                }`}
                onClick={() => { setDefaultLlm(m); markDirty(); }}
                title="Click to set as default"
              >
                {m === defaultLlm && "★ "}{m}
                <button
                  onClick={(e) => { e.stopPropagation(); removeModel(m, llmModels, setLlmModels); }}
                  className="hover:text-red-400 ml-0.5"
                >
                  <X className="w-3 h-3" />
                </button>
              </span>
            ))}
          </div>
          {/* Add from catalog */}
          <div className="flex flex-wrap gap-1.5 mb-2">
            {catalogModels.filter((m) => !llmModels.includes(m)).map((m) => (
              <button
                key={m}
                onClick={() => toggleModel(m, llmModels, setLlmModels)}
                className="px-2.5 py-1 bg-surface-50 text-muted text-xs rounded-lg border border-dashed border-surface-300 hover:border-visible hover:text-accent transition-all"
              >
                + {m}
              </button>
            ))}
          </div>
          <div className="flex gap-2">
            <input
              value={customLlm}
              onChange={(e) => setCustomLlm(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && addModel(customLlm, llmModels, setLlmModels, setCustomLlm)}
              placeholder="Add custom model..."
              className="flex-1 px-3 py-1.5 bg-surface-50 border border-visible rounded-lg text-primary text-xs focus:outline-none focus:border-accent"
            />
            <button
              onClick={() => addModel(customLlm, llmModels, setLlmModels, setCustomLlm)}
              className="px-3 py-1.5 bg-surface-200 text-t-hover rounded-lg text-xs hover:bg-surface-300"
            >
              Add
            </button>
          </div>
        </div>
      )}

      {/* Embedding Models */}
      {provider.supports_embedding && (
        <div>
          <label className="block text-xs font-medium text-t-secondary mb-2">
            <Box className="w-3.5 h-3.5 inline mr-1 text-secondary" />
            Embedding Models
            {defaultEmb && <span className="text-muted ml-2">(default: {defaultEmb})</span>}
          </label>
          <div className="flex flex-wrap gap-1.5 mb-2">
            {embModels.map((m) => (
              <span
                key={m}
                className={`inline-flex items-center gap-1 px-2.5 py-1 rounded-lg text-xs cursor-pointer transition-all ${
                  m === defaultEmb
                    ? "bg-secondary/15 text-secondary border border-secondary/30"
                    : "bg-surface-200 text-t-hover border border-surface-200"
                }`}
                onClick={() => { setDefaultEmb(m); markDirty(); }}
                title="Click to set as default"
              >
                {m === defaultEmb && "★ "}{m}
                <button
                  onClick={(e) => { e.stopPropagation(); removeModel(m, embModels, setEmbModels); }}
                  className="hover:text-red-400 ml-0.5"
                >
                  <X className="w-3 h-3" />
                </button>
              </span>
            ))}
          </div>
          <div className="flex flex-wrap gap-1.5 mb-2">
            {catalogEmbModels.filter((m) => !embModels.includes(m)).map((m) => (
              <button
                key={m}
                onClick={() => toggleModel(m, embModels, setEmbModels)}
                className="px-2.5 py-1 bg-surface-50 text-muted text-xs rounded-lg border border-dashed border-surface-300 hover:border-secondary/30 hover:text-secondary transition-all"
              >
                + {m}
              </button>
            ))}
          </div>
          <div className="flex gap-2">
            <input
              value={customEmb}
              onChange={(e) => setCustomEmb(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && addModel(customEmb, embModels, setEmbModels, setCustomEmb)}
              placeholder="Add custom model..."
              className="flex-1 px-3 py-1.5 bg-surface-50 border border-visible rounded-lg text-primary text-xs focus:outline-none focus:border-accent"
            />
            <button
              onClick={() => addModel(customEmb, embModels, setEmbModels, setCustomEmb)}
              className="px-3 py-1.5 bg-surface-200 text-t-hover rounded-lg text-xs hover:bg-surface-300"
            >
              Add
            </button>
          </div>
        </div>
      )}

      {/* Error */}
      {error && <p className="text-xs text-red-400">{error}</p>}

      {/* Save button */}
      {dirty && (
        <div className="flex justify-end pt-1">
          <button
            onClick={handleSave}
            disabled={saving}
            className="px-5 py-2 bg-accent text-primary rounded-xl text-sm hover:bg-accent/90 transition-colors disabled:opacity-50 flex items-center gap-2"
          >
            {saving ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Check className="w-3.5 h-3.5" />}
            {saving ? "Saving..." : "Save Changes"}
          </button>
        </div>
      )}
    </div>
  );
}
