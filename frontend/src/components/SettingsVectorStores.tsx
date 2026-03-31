"use client";

import { useState, useEffect, useCallback } from "react";
import {
  Database,
  Plus,
  Trash2,
  Zap,
  Check,
  X,
  AlertCircle,
  Loader2,
  Eye,
  EyeOff,
  Pencil,
  ChevronDown,
  ChevronUp,
} from "lucide-react";
import { api } from "@/lib/api";

interface VectorStoreConfigEntry {
  id: number;
  name: string;
  vectorstore_type: string;
  is_active: boolean;
  has_api_key: boolean;
  config: Record<string, any>;
  created_at: string;
  updated_at: string;
}

interface CatalogField {
  name: string;
  label: string;
  required: boolean;
  placeholder: string;
}

interface CatalogEntry {
  label: string;
  description: string;
  icon: string;
  requires_api_key: boolean;
  config_fields: CatalogField[];
}

export default function SettingsVectorStores() {
  const [configs, setConfigs] = useState<VectorStoreConfigEntry[]>([]);
  const [catalog, setCatalog] = useState<Record<string, CatalogEntry>>({});
  const [loading, setLoading] = useState(true);
  const [showAddForm, setShowAddForm] = useState(false);
  const [expandedId, setExpandedId] = useState<number | null>(null);
  const [testingId, setTestingId] = useState<number | null>(null);
  const [testResult, setTestResult] = useState<Record<number, any>>({});
  const [error, setError] = useState<string | null>(null);

  const loadData = useCallback(async () => {
    try {
      const [cfgs, cat] = await Promise.all([
        api.listVectorStoreConfigs(),
        api.getVectorStoreCatalog(),
      ]);
      setConfigs(cfgs);
      setCatalog(cat);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { loadData(); }, [loadData]);

  const handleTest = async (id: number) => {
    setTestingId(id);
    try {
      const result = await api.testVectorStoreConfig(id);
      setTestResult((prev) => ({ ...prev, [id]: result }));
    } catch (e: any) {
      setTestResult((prev) => ({ ...prev, [id]: { success: false, message: e.message } }));
    } finally {
      setTestingId(null);
    }
  };

  const handleDelete = async (id: number) => {
    try {
      await api.deleteVectorStoreConfig(id);
      setConfigs((prev) => prev.filter((c) => c.id !== id));
    } catch (e: any) {
      setError(e.message);
    }
  };

  const handleToggleActive = async (entry: VectorStoreConfigEntry) => {
    try {
      const updated = await api.updateVectorStoreConfig(entry.id, { is_active: !entry.is_active });
      setConfigs((prev) => prev.map((c) => (c.id === entry.id ? updated : c)));
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
          <Database className="w-6 h-6 text-accent" />
          <div>
            <h2 className="text-xl font-bold text-primary">Vector Stores</h2>
            <p className="text-sm text-t-secondary">
              Configure external vector databases for experiments. ChromaDB is always available by default.
            </p>
          </div>
        </div>
        <button
          onClick={() => setShowAddForm(!showAddForm)}
          className="flex items-center gap-2 px-4 py-2 bg-accent text-primary rounded-xl hover:bg-accent/90 transition-colors"
        >
          <Plus className="w-4 h-4" />
          Add Vector Store
        </button>
      </div>

      {error && (
        <div className="flex items-center gap-2 px-4 py-3 bg-red-500/10 border border-red-500/20 rounded-xl text-red-400 text-sm">
          <AlertCircle className="w-4 h-4 shrink-0" />
          {error}
          <button onClick={() => setError(null)} className="ml-auto"><X className="w-4 h-4" /></button>
        </div>
      )}

      {/* Add form */}
      {showAddForm && (
        <AddVectorStoreForm
          catalog={catalog}
          onCreated={(c) => { setConfigs((prev) => [c, ...prev]); setShowAddForm(false); }}
          onCancel={() => setShowAddForm(false)}
        />
      )}

      {/* ChromaDB info */}
      <div className="bg-surface-100 rounded-2xl border border-visible p-5">
        <div className="flex items-center gap-3">
          <span className="text-2xl">💎</span>
          <div className="flex-1">
            <h3 className="font-semibold text-primary">ChromaDB</h3>
            <p className="text-xs text-t-secondary">Embedded vector database — always available, no configuration needed.</p>
          </div>
          <span className="px-3 py-1 text-xs rounded-full bg-emerald-500/20 text-emerald-400">Default</span>
        </div>
      </div>

      {/* Configured stores */}
      {configs.map((entry) => {
        const catEntry = catalog[entry.vectorstore_type];
        const isExpanded = expandedId === entry.id;

        return (
          <div key={entry.id} className="bg-surface-100 rounded-2xl border border-visible overflow-hidden">
            <div className="flex items-center gap-4 px-6 py-4">
              <span className="text-2xl">{catEntry?.icon || "🔗"}</span>
              <div className="flex-1 min-w-0">
                <h3 className="font-semibold text-primary truncate">{entry.name}</h3>
                <p className="text-xs text-t-secondary">{catEntry?.label || entry.vectorstore_type}</p>
              </div>
              <div className="flex items-center gap-2">
                <button
                  onClick={() => handleTest(entry.id)}
                  disabled={testingId === entry.id}
                  className="p-2 hover:bg-surface-200 rounded-lg transition-colors"
                  title="Test connection"
                >
                  {testingId === entry.id ? (
                    <Loader2 className="w-4 h-4 text-accent animate-spin" />
                  ) : testResult[entry.id]?.success === true ? (
                    <Check className="w-4 h-4 text-emerald-400" />
                  ) : testResult[entry.id]?.success === false ? (
                    <AlertCircle className="w-4 h-4 text-red-400" />
                  ) : (
                    <Zap className="w-4 h-4 text-t-secondary" />
                  )}
                </button>
                <button
                  onClick={() => handleToggleActive(entry)}
                  className={`px-3 py-1 text-xs rounded-full transition-colors ${
                    entry.is_active ? "bg-emerald-500/20 text-emerald-400" : "bg-surface-200 text-muted"
                  }`}
                >
                  {entry.is_active ? "Active" : "Inactive"}
                </button>
                <button
                  onClick={() => setExpandedId(isExpanded ? null : entry.id)}
                  className="flex items-center gap-1 px-2.5 py-1.5 hover:bg-surface-200 rounded-lg transition-colors"
                >
                  <Pencil className="w-3.5 h-3.5 text-t-secondary" />
                  {isExpanded ? <ChevronUp className="w-4 h-4 text-t-secondary" /> : <ChevronDown className="w-4 h-4 text-t-secondary" />}
                </button>
                <button
                  onClick={() => handleDelete(entry.id)}
                  className="p-2 hover:bg-red-500/10 rounded-lg transition-colors"
                >
                  <Trash2 className="w-4 h-4 text-muted hover:text-red-400" />
                </button>
              </div>
            </div>

            {testResult[entry.id] && (
              <div className={`px-6 py-2 text-xs ${testResult[entry.id].success ? "bg-emerald-500/10 text-emerald-400" : "bg-red-500/10 text-red-400"}`}>
                {testResult[entry.id].message}
              </div>
            )}

            {isExpanded && (
              <EditVectorStoreForm
                entry={entry}
                catalog={catEntry}
                onUpdate={(updated) => setConfigs((prev) => prev.map((c) => (c.id === updated.id ? updated : c)))}
              />
            )}
          </div>
        );
      })}
    </div>
  );
}


function AddVectorStoreForm({
  catalog,
  onCreated,
  onCancel,
}: {
  catalog: Record<string, CatalogEntry>;
  onCreated: (c: VectorStoreConfigEntry) => void;
  onCancel: () => void;
}) {
  const [vsType, setVsType] = useState("");
  const [name, setName] = useState("");
  const [apiKey, setApiKey] = useState("");
  const [showKey, setShowKey] = useState(false);
  const [configValues, setConfigValues] = useState<Record<string, string>>({});
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const entry = vsType ? catalog[vsType] : null;

  useEffect(() => {
    if (entry) {
      setName(entry.label);
      setConfigValues({});
    }
  }, [vsType, entry]);

  const handleSave = async () => {
    if (!vsType || !name) return;
    setSaving(true);
    setError(null);
    try {
      const created = await api.createVectorStoreConfig({
        name,
        vectorstore_type: vsType,
        api_key: apiKey || undefined,
        config: configValues,
      });
      onCreated(created);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="bg-surface-100 rounded-2xl border border-accent/30 p-6 space-y-5">
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-semibold text-primary">Add Vector Store</h3>
        <button onClick={onCancel} className="p-1 hover:bg-surface-200 rounded-lg"><X className="w-5 h-5 text-t-secondary" /></button>
      </div>

      {/* Type selection */}
      <div>
        <label className="block text-sm font-medium text-t-secondary mb-2">Type</label>
        <div className="grid grid-cols-4 gap-2">
          {Object.entries(catalog).map(([key, val]) => (
            <button
              key={key}
              onClick={() => setVsType(key)}
              className={`flex items-center gap-2 px-3 py-2.5 rounded-xl border text-sm transition-all ${
                vsType === key ? "border-accent bg-accent/10 text-primary" : "border-visible text-t-secondary hover:border-accent/50"
              }`}
            >
              <span>{val.icon}</span>
              <span className="truncate">{val.label}</span>
            </button>
          ))}
        </div>
      </div>

      {entry && (
        <>
          <div>
            <label className="block text-sm font-medium text-t-secondary mb-1">Display Name</label>
            <input
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="w-full px-4 py-2.5 bg-surface-50 border border-visible rounded-xl text-primary text-sm focus:outline-none focus:border-accent"
            />
          </div>

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
                <button onClick={() => setShowKey(!showKey)} className="absolute right-3 top-1/2 -translate-y-1/2">
                  {showKey ? <EyeOff className="w-4 h-4 text-muted" /> : <Eye className="w-4 h-4 text-muted" />}
                </button>
              </div>
            </div>
          )}

          {entry.config_fields.map((field) => (
            <div key={field.name}>
              <label className="block text-sm font-medium text-t-secondary mb-1">
                {field.label} {field.required && <span className="text-red-400">*</span>}
              </label>
              <input
                value={configValues[field.name] || ""}
                onChange={(e) => setConfigValues((prev) => ({ ...prev, [field.name]: e.target.value }))}
                placeholder={field.placeholder}
                className="w-full px-4 py-2.5 bg-surface-50 border border-visible rounded-xl text-primary text-sm focus:outline-none focus:border-accent"
              />
            </div>
          ))}

          {error && <p className="text-sm text-red-400">{error}</p>}

          <div className="flex justify-end gap-3 pt-2">
            <button onClick={onCancel} className="px-4 py-2 text-sm text-t-secondary hover:text-primary transition-colors">Cancel</button>
            <button
              onClick={handleSave}
              disabled={saving || !name || !vsType}
              className="px-6 py-2 bg-accent text-primary rounded-xl text-sm hover:bg-accent/90 transition-colors disabled:opacity-50"
            >
              {saving ? "Saving..." : "Save"}
            </button>
          </div>
        </>
      )}
    </div>
  );
}


function EditVectorStoreForm({
  entry,
  catalog,
  onUpdate,
}: {
  entry: VectorStoreConfigEntry;
  catalog?: CatalogEntry;
  onUpdate: (c: VectorStoreConfigEntry) => void;
}) {
  const [name, setName] = useState(entry.name);
  const [apiKey, setApiKey] = useState("");
  const [showKey, setShowKey] = useState(false);
  const [configValues, setConfigValues] = useState<Record<string, string>>(entry.config || {});
  const [saving, setSaving] = useState(false);
  const [dirty, setDirty] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const markDirty = () => setDirty(true);

  const handleSave = async () => {
    setSaving(true);
    setError(null);
    try {
      const payload: any = { name, config: configValues };
      if (apiKey) payload.api_key = apiKey;
      const updated = await api.updateVectorStoreConfig(entry.id, payload);
      onUpdate(updated);
      setApiKey("");
      setDirty(false);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="px-6 pb-5 pt-3 border-t border-visible space-y-4">
      <div>
        <label className="block text-xs font-medium text-t-secondary mb-1">Display Name</label>
        <input
          value={name}
          onChange={(e) => { setName(e.target.value); markDirty(); }}
          className="w-full px-3 py-2 bg-surface-50 border border-visible rounded-lg text-primary text-sm focus:outline-none focus:border-accent"
        />
      </div>

      {catalog?.requires_api_key && (
        <div>
          <label className="block text-xs font-medium text-t-secondary mb-1">
            API Key {entry.has_api_key && <span className="text-emerald-400">(currently set)</span>}
          </label>
          <div className="relative">
            <input
              type={showKey ? "text" : "password"}
              value={apiKey}
              onChange={(e) => { setApiKey(e.target.value); markDirty(); }}
              placeholder="Enter new API key to update..."
              className="w-full px-3 py-2 pr-8 bg-surface-50 border border-visible rounded-lg text-primary text-sm focus:outline-none focus:border-accent"
            />
            <button onClick={() => setShowKey(!showKey)} className="absolute right-2.5 top-1/2 -translate-y-1/2">
              {showKey ? <EyeOff className="w-3.5 h-3.5 text-muted" /> : <Eye className="w-3.5 h-3.5 text-muted" />}
            </button>
          </div>
        </div>
      )}

      {catalog?.config_fields.map((field) => (
        <div key={field.name}>
          <label className="block text-xs font-medium text-t-secondary mb-1">{field.label}</label>
          <input
            value={configValues[field.name] || ""}
            onChange={(e) => { setConfigValues((prev) => ({ ...prev, [field.name]: e.target.value })); markDirty(); }}
            placeholder={field.placeholder}
            className="w-full px-3 py-2 bg-surface-50 border border-visible rounded-lg text-primary text-sm focus:outline-none focus:border-accent"
          />
        </div>
      ))}

      {error && <p className="text-xs text-red-400">{error}</p>}

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
