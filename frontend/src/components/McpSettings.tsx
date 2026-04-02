"use client";

import { useState, useEffect } from "react";
import {
  Cable,
  Plus,
  Trash2,
  Copy,
  Check,
  Key,
  ToggleLeft,
  ToggleRight,
  AlertCircle,
  Loader2,
  Shield,
  Eye,
  EyeOff,
} from "lucide-react";
import { api, setStoredApiKey, getStoredApiKey } from "@/lib/api";

interface ApiKeyItem {
  id: number;
  name: string;
  key_prefix: string;
  is_active: boolean;
  created_at: string;
}

interface McpTool {
  name: string;
  description: string;
  group: string;
  enabled: boolean;
}

type Platform = "claude-code" | "cursor" | "windsurf" | "vscode" | "continue";

const PLATFORMS: { key: Platform; label: string; file: string }[] = [
  { key: "claude-code", label: "Claude Code", file: "~/.claude/settings.json" },
  { key: "cursor", label: "Cursor", file: ".cursor/mcp.json" },
  { key: "windsurf", label: "Windsurf", file: "~/.codeium/windsurf/mcp_config.json" },
  { key: "vscode", label: "VS Code", file: ".vscode/mcp.json" },
  { key: "continue", label: "Continue", file: "~/.continue/config.json" },
];

function buildPayload(platform: Platform, serverPath: string, apiKey: string): string {
  const key = apiKey || "your-api-key-here";
  const server = {
    command: "uvx",
    args: ["fastmcp", "run", serverPath],
    env: { RAG_API_KEY: key },
  };

  if (platform === "vscode") {
    return JSON.stringify({ servers: { "rag-pipeline": server } }, null, 2);
  }

  if (platform === "continue") {
    return JSON.stringify(
      {
        experimental: {
          modelContextProtocolServers: [
            { transport: { type: "stdio", ...server } },
          ],
        },
      },
      null,
      2
    );
  }

  // claude-code, cursor, windsurf all use the same format
  return JSON.stringify({ mcpServers: { "rag-pipeline": server } }, null, 2);
}

export default function McpSettings() {
  // API Keys state
  const [keys, setKeys] = useState<ApiKeyItem[]>([]);
  const [bootstrapMode, setBootstrapMode] = useState(true);
  const [newKeyName, setNewKeyName] = useState("");
  const [justCreatedKey, setJustCreatedKey] = useState<string | null>(null);
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [loadingKeys, setLoadingKeys] = useState(true);
  const [showKey, setShowKey] = useState(true);

  // MCP Tools state
  const [tools, setTools] = useState<McpTool[]>([]);
  const [loadingTools, setLoadingTools] = useState(true);
  const [savingTools, setSavingTools] = useState(false);
  const [toolsDirty, setToolsDirty] = useState(false);

  // Connection state
  const [platform, setPlatform] = useState<Platform>("claude-code");
  const [serverPath, setServerPath] = useState("");
  const [copied, setCopied] = useState<string | null>(null);

  const [error, setError] = useState<string | null>(null);

  // Load data
  useEffect(() => {
    loadKeys();
    loadTools();
    loadConnectionInfo();
  }, []);

  const loadKeys = async () => {
    try {
      setLoadingKeys(true);
      const [status, keyList] = await Promise.all([
        api.getAuthStatus(),
        api.listApiKeys(),
      ]);
      setBootstrapMode(status.bootstrap_mode);
      setKeys(keyList);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoadingKeys(false);
    }
  };

  const loadTools = async () => {
    try {
      setLoadingTools(true);
      const res = await api.listMcpTools();
      setTools(res.tools);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoadingTools(false);
    }
  };

  const loadConnectionInfo = async () => {
    try {
      const info = await api.getMcpConnectionInfo();
      setServerPath(info.server_path);
    } catch {}
  };

  const handleCreateKey = async () => {
    try {
      setError(null);
      const res = await api.createApiKey(newKeyName || "Default");
      setJustCreatedKey(res.key);
      // Auto-store as the active key for frontend requests
      if (!getStoredApiKey()) {
        setStoredApiKey(res.key);
      }
      setShowKey(true);
      setNewKeyName("");
      setShowCreateForm(false);
      await loadKeys();
    } catch (err: any) {
      setError(err.message);
    }
  };

  const handleDeleteKey = async (id: number) => {
    try {
      setError(null);
      await api.deleteApiKey(id);
      await loadKeys();
    } catch (err: any) {
      setError(err.message);
    }
  };

  const handleToggleTool = (name: string) => {
    setTools((prev) =>
      prev.map((t) => (t.name === name ? { ...t, enabled: !t.enabled } : t))
    );
    setToolsDirty(true);
  };

  const handleSaveTools = async () => {
    try {
      setSavingTools(true);
      const disabled = tools.filter((t) => !t.enabled).map((t) => t.name);
      await api.updateMcpTools(disabled);
      setToolsDirty(false);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setSavingTools(false);
    }
  };

  const copyToClipboard = (text: string, label: string) => {
    navigator.clipboard.writeText(text);
    setCopied(label);
    setTimeout(() => setCopied(null), 2000);
  };

  const toolGroups = tools.reduce<Record<string, McpTool[]>>((acc, t) => {
    (acc[t.group] = acc[t.group] || []).push(t);
    return acc;
  }, {});

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="flex items-center gap-3">
        <div className="w-10 h-10 rounded-xl bg-accent/10 flex items-center justify-center">
          <Cable className="w-5 h-5 text-accent" />
        </div>
        <div>
          <h2 className="text-lg font-semibold text-primary">MCP Server</h2>
          <p className="text-sm text-t-secondary">
            Manage API keys, configure tools, and connect to AI platforms.
          </p>
        </div>
      </div>

      {error && (
        <div className="flex items-center gap-2 p-3 bg-red-500/5 border border-red-500/20 rounded-xl text-sm text-red-400">
          <AlertCircle className="w-4 h-4 flex-shrink-0" />
          {error}
          <button onClick={() => setError(null)} className="ml-auto text-red-400/60 hover:text-red-400">x</button>
        </div>
      )}

      {/* ─── Section 1: API Keys ─── */}
      <div className="bg-surface-100 rounded-2xl border border-surface-200/50 p-6">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <Shield className="w-4 h-4 text-accent" />
            <h3 className="text-sm font-semibold text-primary">API Keys</h3>
            {bootstrapMode && (
              <span className="text-[10px] px-2 py-0.5 rounded-full bg-amber-500/10 text-amber-400">
                No auth — create a key to protect your API
              </span>
            )}
          </div>
          {!showCreateForm && (
            <button
              onClick={() => setShowCreateForm(true)}
              className="flex items-center gap-1.5 px-3 py-1.5 bg-accent text-white text-xs font-medium rounded-lg hover:opacity-90"
            >
              <Plus className="w-3.5 h-3.5" /> New Key
            </button>
          )}
        </div>

        {/* Create form */}
        {showCreateForm && (
          <div className="mb-4 p-4 bg-surface-50 rounded-xl border border-surface-200/50">
            <label className="block text-xs text-t-secondary mb-1.5">Key Name</label>
            <div className="flex gap-2">
              <input
                value={newKeyName}
                onChange={(e) => setNewKeyName(e.target.value)}
                placeholder="e.g., Development, CI/CD, Claude Code"
                className="flex-1 px-3 py-2 bg-surface border border-surface-200/50 rounded-lg text-primary text-sm placeholder-muted focus:outline-none focus:border-accent/50"
                onKeyDown={(e) => e.key === "Enter" && handleCreateKey()}
              />
              <button
                onClick={handleCreateKey}
                className="px-4 py-2 bg-accent text-white text-sm font-medium rounded-lg hover:opacity-90"
              >
                Generate
              </button>
              <button
                onClick={() => setShowCreateForm(false)}
                className="px-3 py-2 bg-surface-200 text-t-secondary text-sm rounded-lg hover:bg-surface-300"
              >
                Cancel
              </button>
            </div>
          </div>
        )}

        {/* Just created key display */}
        {justCreatedKey && (
          <div className="mb-4 p-4 bg-emerald-500/5 border border-emerald-500/20 rounded-xl">
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs font-medium text-emerald-400">
                Key created! Copy it now — it won't be shown again.
              </span>
              <button
                onClick={() => setShowKey(!showKey)}
                className="p-1 hover:bg-surface-200 rounded"
              >
                {showKey ? <EyeOff className="w-3.5 h-3.5 text-muted" /> : <Eye className="w-3.5 h-3.5 text-muted" />}
              </button>
            </div>
            <div className="flex items-center gap-2">
              <code className="flex-1 px-3 py-2 bg-surface-100 rounded-lg text-sm font-mono text-primary break-all">
                {showKey ? justCreatedKey : "••••••••••••••••••••••••"}
              </code>
              <button
                onClick={() => copyToClipboard(justCreatedKey, "key")}
                className="flex-shrink-0 p-2 bg-emerald-500/10 text-emerald-400 rounded-lg hover:bg-emerald-500/20"
              >
                {copied === "key" ? <Check className="w-4 h-4" /> : <Copy className="w-4 h-4" />}
              </button>
            </div>
            <button
              onClick={() => setJustCreatedKey(null)}
              className="mt-2 text-xs text-muted hover:text-t-secondary"
            >
              Dismiss
            </button>
          </div>
        )}

        {/* Key list */}
        {loadingKeys ? (
          <div className="flex items-center justify-center py-8 text-t-secondary">
            <Loader2 className="w-4 h-4 animate-spin mr-2" /> Loading...
          </div>
        ) : keys.length === 0 ? (
          <p className="text-sm text-muted py-4 text-center">
            No API keys created. Your API is currently unprotected.
          </p>
        ) : (
          <div className="space-y-2">
            {keys.map((k) => (
              <div
                key={k.id}
                className="flex items-center justify-between px-4 py-3 bg-surface-50 rounded-xl border border-surface-200/50"
              >
                <div className="flex items-center gap-3 min-w-0">
                  <Key className="w-4 h-4 text-muted flex-shrink-0" />
                  <div className="min-w-0">
                    <span className="text-sm text-primary font-medium">{k.name}</span>
                    <div className="flex items-center gap-2 text-xs text-muted">
                      <code>{k.key_prefix}...••••</code>
                      <span>{new Date(k.created_at).toLocaleDateString()}</span>
                    </div>
                  </div>
                </div>
                <button
                  onClick={() => handleDeleteKey(k.id)}
                  className="p-1.5 text-muted hover:text-red-400 hover:bg-red-500/10 rounded-lg transition-colors"
                  title="Delete key"
                >
                  <Trash2 className="w-4 h-4" />
                </button>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* ─── Section 2: Connect to Platform ─── */}
      <div className="bg-surface-100 rounded-2xl border border-surface-200/50 p-6">
        <div className="flex items-center gap-2 mb-4">
          <Cable className="w-4 h-4 text-accent" />
          <h3 className="text-sm font-semibold text-primary">Connect to Platform</h3>
        </div>

        {/* Platform selector — equal width grid */}
        <div className="grid grid-cols-5 gap-1.5 mb-4">
          {PLATFORMS.map((p) => (
            <button
              key={p.key}
              onClick={() => setPlatform(p.key)}
              className={`px-2 py-2 text-xs font-medium rounded-lg transition-colors text-center ${
                platform === p.key
                  ? "bg-accent/15 text-accent border border-accent"
                  : "bg-surface-50 text-t-secondary border border-surface-200/50 hover:border-surface-300"
              }`}
            >
              {p.label}
            </button>
          ))}
        </div>

        {/* Instructions */}
        <p className="text-xs text-t-secondary mb-3">
          Add to <code className="text-accent">{PLATFORMS.find((p) => p.key === platform)?.file}</code>:
        </p>

        {/* Payload */}
        <div className="relative">
          <pre className="p-4 bg-surface-50 rounded-xl border border-surface-200/50 text-xs font-mono text-primary overflow-x-auto whitespace-pre">
            {buildPayload(platform, serverPath, justCreatedKey || "")}
          </pre>
          <button
            onClick={() =>
              copyToClipboard(
                buildPayload(platform, serverPath, justCreatedKey || ""),
                "payload"
              )
            }
            className="absolute top-2 right-2 p-1.5 bg-surface-200/80 hover:bg-surface-300 rounded-lg transition-colors"
            title="Copy JSON"
          >
            {copied === "payload" ? (
              <Check className="w-3.5 h-3.5 text-emerald-400" />
            ) : (
              <Copy className="w-3.5 h-3.5 text-muted" />
            )}
          </button>
        </div>

      </div>

      {/* ─── Section 3: MCP Tool Toggles ─── */}
      <div className="bg-surface-100 rounded-2xl border border-surface-200/50 p-6">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <ToggleRight className="w-4 h-4 text-accent" />
            <h3 className="text-sm font-semibold text-primary">MCP Tools</h3>
            <span className="text-[10px] text-muted">
              {tools.filter((t) => t.enabled).length}/{tools.length} enabled
            </span>
          </div>
          {toolsDirty && (
            <button
              onClick={handleSaveTools}
              disabled={savingTools}
              className="flex items-center gap-1.5 px-3 py-1.5 bg-accent text-white text-xs font-medium rounded-lg hover:opacity-90 disabled:opacity-50"
            >
              {savingTools ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Check className="w-3.5 h-3.5" />}
              Save Changes
            </button>
          )}
        </div>

        {loadingTools ? (
          <div className="flex items-center justify-center py-8 text-t-secondary">
            <Loader2 className="w-4 h-4 animate-spin mr-2" /> Loading...
          </div>
        ) : (
          <div className="space-y-4">
            {Object.entries(toolGroups).map(([group, groupTools]) => (
              <div key={group}>
                <h4 className="text-xs font-medium text-muted uppercase tracking-wider mb-2">
                  {group}
                </h4>
                <div className="rounded-xl bg-surface-50 border border-surface-200/30 overflow-hidden">
                  {groupTools.map((tool) => (
                    <div
                      key={tool.name}
                      className="flex items-center justify-between px-4 py-2.5"
                    >
                      <div className="min-w-0 flex-1 mr-3">
                        <span className="text-sm text-primary">
                          {tool.name.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase())}
                        </span>
                        <p className="text-xs text-muted truncate">{tool.description}</p>
                      </div>
                      <button
                        onClick={() => handleToggleTool(tool.name)}
                        className="flex-shrink-0"
                      >
                        {tool.enabled ? (
                          <ToggleRight className="w-8 h-8 text-accent" />
                        ) : (
                          <ToggleLeft className="w-8 h-8 text-surface-300" />
                        )}
                      </button>
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
        )}

        {toolsDirty && (
          <p className="mt-3 text-xs text-amber-400">
            Restart the MCP server after saving for changes to take effect.
          </p>
        )}
      </div>
    </div>
  );
}
