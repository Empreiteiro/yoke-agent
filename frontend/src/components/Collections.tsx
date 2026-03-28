"use client";

import { useState, useEffect, useRef } from "react";
import {
  Database,
  Trash2,
  MessageSquare,
  Send,
  Loader2,
  X,
  ChevronDown,
  ChevronRight,
  HardDrive,
} from "lucide-react";
import { api } from "@/lib/api";

interface Message {
  role: "user" | "assistant";
  content: string;
  contexts?: string[];
}

export default function Collections() {
  const [collections, setCollections] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [activeId, setActiveId] = useState<number | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [confirmDeleteId, setConfirmDeleteId] = useState<number | null>(null);
  const [expandedContextIdx, setExpandedContextIdx] = useState<number | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    loadCollections();
  }, []);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const loadCollections = async () => {
    try {
      const data = await api.listCollections();
      setCollections(data);
    } catch (err) {
      console.error("Failed to load collections:", err);
    } finally {
      setLoading(false);
    }
  };

  const handleDelete = async (id: number) => {
    try {
      await api.deleteCollection(id);
      setCollections((prev) => prev.filter((c) => c.id !== id));
      if (activeId === id) {
        setActiveId(null);
        setMessages([]);
      }
    } catch (err) {
      console.error("Failed to delete collection:", err);
    } finally {
      setConfirmDeleteId(null);
    }
  };

  const handleStartChat = (id: number) => {
    setActiveId(id);
    setMessages([]);
    setInput("");
  };

  const handleSend = async () => {
    if (!input.trim() || !activeId || sending) return;

    const question = input.trim();
    setInput("");
    setMessages((prev) => [...prev, { role: "user", content: question }]);
    setSending(true);

    try {
      const res = await api.queryCollection(activeId, { question });
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: res.answer, contexts: res.contexts },
      ]);
    } catch (err: any) {
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: `Error: ${err.message}` },
      ]);
    } finally {
      setSending(false);
    }
  };

  const formatSize = (bytes: number) => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  const activeCollection = collections.find((c) => c.id === activeId);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20 text-t-secondary">
        <Loader2 className="w-5 h-5 animate-spin mr-2" />
        Loading collections...
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-primary">Saved Collections</h2>
        <p className="text-sm text-t-secondary mt-1">
          Query winning vectorstores and test retrieval quality
        </p>
      </div>

      {collections.length === 0 && !activeId ? (
        <div className="text-center py-20">
          <Database className="w-12 h-12 text-muted mx-auto mb-4" />
          <p className="text-t-secondary">No saved collections yet.</p>
          <p className="text-muted text-sm mt-1">
            Run an experiment to completion — the winning configuration is saved automatically.
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          {/* Collection list */}
          <div className="space-y-3">
            {collections.map((col) => (
              <div
                key={col.id}
                className={`bg-surface-100 rounded-xl border p-4 transition-colors ${
                  activeId === col.id
                    ? "border-accent/40 bg-accent/5"
                    : "border-surface-200/50"
                }`}
              >
                <div className="flex items-start justify-between mb-2">
                  <div className="min-w-0 flex-1">
                    <h3 className="text-sm font-semibold text-primary truncate">{col.name}</h3>
                    <div className="flex items-center gap-3 mt-1 text-xs text-t-secondary">
                      <span>{col.embedding_model}</span>
                      <span>{col.chunk_size}t / {col.chunk_overlap}%</span>
                      <span>k={col.top_k}</span>
                      <span>{col.search_type}</span>
                    </div>
                  </div>
                  {col.overall_score != null && (
                    <span
                      className={`text-sm font-bold ${
                        col.overall_score >= 0.8
                          ? "text-emerald-400"
                          : col.overall_score >= 0.6
                          ? "text-amber-400"
                          : "text-red-400"
                      }`}
                    >
                      {(col.overall_score * 100).toFixed(1)}%
                    </span>
                  )}
                </div>

                <div className="flex items-center justify-between mt-3">
                  <div className="flex items-center gap-2 text-xs text-muted">
                    <HardDrive className="w-3 h-3" />
                    {formatSize(col.size_bytes)}
                  </div>
                  <div className="flex items-center gap-1">
                    <button
                      onClick={() => setConfirmDeleteId(col.id)}
                      className="p-1.5 rounded-lg text-muted hover:text-red-400 hover:bg-red-500/10 transition-colors"
                      title="Delete collection"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                    <button
                      onClick={() => handleStartChat(col.id)}
                      className={`flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-lg transition-colors ${
                        activeId === col.id
                          ? "bg-accent text-white"
                          : "bg-accent/10 text-accent hover:bg-accent/20"
                      }`}
                    >
                      <MessageSquare className="w-3 h-3" />
                      Chat
                    </button>
                  </div>
                </div>
              </div>
            ))}
          </div>

          {/* Chat interface */}
          {activeCollection && (
            <div className="bg-surface-100 rounded-xl border border-surface-200/50 flex flex-col" style={{ height: "70vh" }}>
              {/* Chat header */}
              <div className="flex items-center justify-between px-4 py-3 border-b border-surface-200/50">
                <div className="min-w-0">
                  <h3 className="text-sm font-semibold text-primary truncate">
                    {activeCollection.name}
                  </h3>
                  <p className="text-xs text-muted">
                    {activeCollection.embedding_model} | k={activeCollection.top_k} | {activeCollection.search_type}
                  </p>
                </div>
                <button
                  onClick={() => { setActiveId(null); setMessages([]); }}
                  className="p-1.5 rounded-lg text-muted hover:text-primary hover:bg-surface-200 transition-colors"
                >
                  <X className="w-4 h-4" />
                </button>
              </div>

              {/* Messages */}
              <div className="flex-1 overflow-y-auto px-4 py-4 space-y-4">
                {messages.length === 0 && (
                  <div className="text-center py-12 text-muted text-sm">
                    Ask a question to test retrieval quality
                  </div>
                )}
                {messages.map((msg, i) => (
                  <div key={i} className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}>
                    <div
                      className={`max-w-[85%] rounded-xl px-4 py-2.5 text-sm ${
                        msg.role === "user"
                          ? "bg-accent text-white rounded-br-sm"
                          : "bg-surface-50 text-primary border border-surface-200/50 rounded-bl-sm"
                      }`}
                    >
                      <p className="whitespace-pre-wrap">{msg.content}</p>
                      {msg.contexts && msg.contexts.length > 0 && (
                        <div className="mt-2 pt-2 border-t border-surface-200/30">
                          <button
                            onClick={() => setExpandedContextIdx(expandedContextIdx === i ? null : i)}
                            className="flex items-center gap-1 text-xs text-t-secondary hover:text-primary transition-colors"
                          >
                            {expandedContextIdx === i ? (
                              <ChevronDown className="w-3 h-3" />
                            ) : (
                              <ChevronRight className="w-3 h-3" />
                            )}
                            {msg.contexts.length} retrieved context{msg.contexts.length !== 1 ? "s" : ""}
                          </button>
                          {expandedContextIdx === i && (
                            <div className="mt-2 space-y-2">
                              {msg.contexts.map((ctx, j) => (
                                <div
                                  key={j}
                                  className="text-xs text-t-secondary bg-surface-100 rounded-lg px-3 py-2 border-l-2 border-accent/30"
                                >
                                  {ctx.length > 300 ? ctx.slice(0, 300) + "..." : ctx}
                                </div>
                              ))}
                            </div>
                          )}
                        </div>
                      )}
                    </div>
                  </div>
                ))}
                {sending && (
                  <div className="flex justify-start">
                    <div className="bg-surface-50 rounded-xl px-4 py-3 border border-surface-200/50">
                      <Loader2 className="w-4 h-4 text-accent animate-spin" />
                    </div>
                  </div>
                )}
                <div ref={messagesEndRef} />
              </div>

              {/* Input */}
              <div className="px-4 py-3 border-t border-surface-200/50">
                <div className="flex gap-2">
                  <input
                    value={input}
                    onChange={(e) => setInput(e.target.value)}
                    onKeyDown={(e) => e.key === "Enter" && !e.shiftKey && handleSend()}
                    placeholder="Ask a question..."
                    disabled={sending}
                    className="flex-1 px-4 py-2.5 bg-surface-50 border border-surface-200/50 rounded-xl text-primary text-sm placeholder-muted focus:outline-none focus:border-accent/50 disabled:opacity-50"
                  />
                  <button
                    onClick={handleSend}
                    disabled={!input.trim() || sending}
                    className="px-4 py-2.5 bg-accent text-white rounded-xl hover:bg-accent/90 disabled:opacity-50 transition-colors"
                  >
                    <Send className="w-4 h-4" />
                  </button>
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Delete confirmation modal */}
      {confirmDeleteId && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
          <div className="bg-surface-100 border border-surface-200/50 rounded-2xl p-6 max-w-sm w-full mx-4 shadow-xl">
            <h3 className="text-primary font-semibold mb-2">Delete collection?</h3>
            <p className="text-sm text-t-secondary mb-5">
              This will permanently remove the vectorstore files from disk. Experiment history will not be affected.
            </p>
            <div className="flex justify-end gap-3">
              <button
                onClick={() => setConfirmDeleteId(null)}
                className="px-4 py-2 text-sm text-t-secondary hover:text-primary bg-surface-200 rounded-lg transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={() => handleDelete(confirmDeleteId)}
                className="px-4 py-2 text-sm text-white bg-red-500 hover:bg-red-600 rounded-lg transition-colors"
              >
                Delete
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
