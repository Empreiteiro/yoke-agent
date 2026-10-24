"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import {
  AlertCircle,
  Check,
  ChevronLeft,
  ChevronRight,
  Copy,
  Database,
  Download,
  FileUp,
  Loader2,
  Lock,
  Pencil,
  Scale,
  Search,
  Trash2,
  Upload,
  X,
} from "lucide-react";
import { api, downloadFile } from "@/lib/api";
import { cn } from "@/lib/utils";
import { SectionCard, formatInt, useSeriesColors } from "./shared";

const PAGE_SIZE = 25;

export default function DecisionDatasets() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [datasets, setDatasets] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showUpload, setShowUpload] = useState(false);
  const selectedId = searchParams.get("dataset") ? Number(searchParams.get("dataset")) : null;

  const load = useCallback(async () => {
    try {
      setDatasets(await api.listDecisionDatasets());
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const select = (id: number | null) => {
    router.push(id ? `/?view=decision-datasets&dataset=${id}` : "/?view=decision-datasets");
  };

  const builtins = datasets.filter((d) => d.is_builtin);
  const custom = datasets.filter((d) => !d.is_builtin);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="w-6 h-6 text-accent animate-spin" />
      </div>
    );
  }

  if (selectedId) {
    return (
      <DatasetDetail
        datasetId={selectedId}
        onBack={() => select(null)}
        onChanged={load}
        onSelect={select}
      />
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-accent/15 flex items-center justify-center">
            <Database className="w-5 h-5 text-accent" />
          </div>
          <div>
            <h2 className="text-lg font-semibold text-primary">Comparison Datasets</h2>
            <p className="text-sm text-t-secondary">
              Labeled classification sets used to compare decision models and LLMs.
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => downloadFile("/decision/dataset-template", "decision_dataset_template.csv").catch((e) => setError(e.message))}
            className="flex items-center gap-1.5 px-3 py-2 text-xs font-medium text-t-secondary border border-visible rounded-lg hover:text-primary hover:bg-surface-200/50 transition-colors"
          >
            <Download className="w-3.5 h-3.5" />
            CSV template
          </button>
          <button
            onClick={() => setShowUpload((v) => !v)}
            className="flex items-center gap-2 px-4 py-2 bg-accent text-accent-foreground rounded-lg text-sm font-medium hover:bg-accent/90 transition-colors"
          >
            <Upload className="w-4 h-4" />
            Upload dataset
          </button>
        </div>
      </div>

      {error && <ErrorBanner message={error} onClose={() => setError(null)} />}

      {showUpload && (
        <UploadPanel
          onCancel={() => setShowUpload(false)}
          onCreated={async (ds) => {
            setShowUpload(false);
            await load();
            select(ds.id);
          }}
        />
      )}

      <div>
        <h3 className="text-xs font-semibold uppercase tracking-wider text-muted mb-3">Built-in datasets</h3>
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3">
          {builtins.map((d) => (
            <DatasetCard key={d.id} dataset={d} onClick={() => select(d.id)} />
          ))}
          {builtins.length === 0 && (
            <p className="text-sm text-muted">No built-in datasets were found. Restart the backend to seed them.</p>
          )}
        </div>
      </div>

      <div>
        <h3 className="text-xs font-semibold uppercase tracking-wider text-muted mb-3">Your datasets</h3>
        {custom.length === 0 ? (
          <button
            onClick={() => setShowUpload(true)}
            className="w-full border border-dashed border-visible rounded-2xl p-8 text-center hover:border-accent/50 transition-colors"
          >
            <FileUp className="w-8 h-8 text-muted mx-auto mb-2" />
            <p className="text-sm text-primary font-medium">Upload your own labeled data</p>
            <p className="text-xs text-t-secondary mt-1">CSV, TSV, JSON or JSONL with a text column and a label column.</p>
          </button>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3">
            {custom.map((d) => (
              <DatasetCard key={d.id} dataset={d} onClick={() => select(d.id)} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function ErrorBanner({ message, onClose }: { message: string; onClose?: () => void }) {
  return (
    <div className="flex items-start gap-2 px-4 py-3 bg-danger/10 border border-danger/20 rounded-xl text-danger text-sm">
      <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
      <span className="flex-1">{message}</span>
      {onClose && (
        <button onClick={onClose}>
          <X className="w-4 h-4" />
        </button>
      )}
    </div>
  );
}

function DatasetCard({ dataset, onClick }: { dataset: any; onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      className="text-left bg-surface-100 border border-visible rounded-2xl p-4 hover:border-accent/50 transition-colors flex flex-col gap-2"
    >
      <div className="flex items-start justify-between gap-2">
        <h4 className="text-sm font-semibold text-primary leading-snug">{dataset.name}</h4>
        {dataset.is_builtin && <Lock className="w-3.5 h-3.5 text-muted flex-shrink-0 mt-0.5" />}
      </div>
      {dataset.description && <p className="text-xs text-t-secondary line-clamp-2">{dataset.description}</p>}
      <div className="flex flex-wrap items-center gap-1.5 mt-auto pt-1">
        <span className="px-2 py-0.5 rounded-md bg-surface-200 text-[11px] text-t-hover">{formatInt(dataset.item_count)} rows</span>
        <span className="px-2 py-0.5 rounded-md bg-surface-200 text-[11px] text-t-hover">{dataset.labels?.length || 0} labels</span>
        {dataset.language && (
          <span className="px-2 py-0.5 rounded-md bg-surface-200 text-[11px] text-t-hover uppercase">{dataset.language}</span>
        )}
      </div>
    </button>
  );
}

/* ═══════════════════════════ Detail ═══════════════════════════ */

function DatasetDetail({
  datasetId,
  onBack,
  onChanged,
  onSelect,
}: {
  datasetId: number;
  onBack: () => void;
  onChanged: () => void;
  onSelect: (id: number) => void;
}) {
  const router = useRouter();
  const colors = useSeriesColors();
  const [dataset, setDataset] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);
  const [items, setItems] = useState<any[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(0);
  const [labelFilter, setLabelFilter] = useState("");
  const [search, setSearch] = useState("");
  const [searchInput, setSearchInput] = useState("");
  const [editing, setEditing] = useState(false);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    setDataset(null);
    api.getDecisionDataset(datasetId).then(setDataset).catch((e) => setError(e.message));
  }, [datasetId]);

  useEffect(() => {
    api
      .listDecisionDatasetItems(datasetId, { label: labelFilter, search, offset: page * PAGE_SIZE, limit: PAGE_SIZE })
      .then((res) => {
        setItems(res.items);
        setTotal(res.total);
      })
      .catch((e) => setError(e.message));
  }, [datasetId, labelFilter, search, page]);

  const maxCount = useMemo(
    () => Math.max(1, ...Object.values((dataset?.label_counts || {}) as Record<string, number>)),
    [dataset]
  );

  const handleDuplicate = async () => {
    setBusy(true);
    try {
      const copy = await api.duplicateDecisionDataset(datasetId);
      onChanged();
      onSelect(copy.id);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  };

  const handleDelete = async () => {
    if (!confirm(`Delete "${dataset.name}"? Comparisons that used it are deleted too.`)) return;
    setBusy(true);
    try {
      await api.deleteDecisionDataset(datasetId);
      onChanged();
      onBack();
    } catch (e: any) {
      setError(e.message);
      setBusy(false);
    }
  };

  if (!dataset) {
    return (
      <div className="space-y-4">
        <BackButton onClick={onBack} />
        {error ? <ErrorBanner message={error} /> : <Loader2 className="w-6 h-6 text-accent animate-spin" />}
      </div>
    );
  }

  const pages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  return (
    <div className="space-y-5">
      <BackButton onClick={onBack} />

      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <h2 className="text-lg font-semibold text-primary">{dataset.name}</h2>
            {dataset.is_builtin && (
              <span className="flex items-center gap-1 px-2 py-0.5 rounded-md bg-surface-200 text-[11px] text-t-secondary">
                <Lock className="w-3 h-3" /> Built-in
              </span>
            )}
          </div>
          {dataset.description && <p className="text-sm text-t-secondary mt-1 max-w-3xl">{dataset.description}</p>}
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <button
            onClick={() => router.push(`/?view=decision-compare&dataset=${dataset.id}`)}
            className="flex items-center gap-2 px-4 py-2 bg-accent text-accent-foreground rounded-lg text-sm font-medium hover:bg-accent/90 transition-colors"
          >
            <Scale className="w-4 h-4" />
            Compare models
          </button>
          <IconButton onClick={handleDuplicate} disabled={busy} icon={Copy} label="Duplicate" />
          <IconButton
            onClick={() =>
              downloadFile(`/decision/datasets/${dataset.id}/export`, `${dataset.slug || `dataset_${dataset.id}`}.json`).catch((e) => setError(e.message))
            }
            icon={Download}
            label="Export"
          />
          {!dataset.is_builtin && (
            <>
              <IconButton onClick={() => setEditing((v) => !v)} icon={Pencil} label="Edit" />
              <IconButton onClick={handleDelete} disabled={busy} icon={Trash2} label="Delete" danger />
            </>
          )}
        </div>
      </div>

      {error && <ErrorBanner message={error} onClose={() => setError(null)} />}

      {editing ? (
        <EditDataset
          dataset={dataset}
          onCancel={() => setEditing(false)}
          onSaved={(updated) => {
            setDataset({ ...dataset, ...updated });
            setEditing(false);
            onChanged();
          }}
        />
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-5 gap-4">
          <SectionCard title="Task" description="The question every model answers for each row." className="lg:col-span-2">
            <p className="text-sm text-primary bg-surface-50 border border-visible rounded-lg px-3 py-2">{dataset.task}</p>
            <div className="grid grid-cols-3 gap-2 mt-4">
              <Stat label="Rows" value={formatInt(dataset.item_count)} />
              <Stat label="Labels" value={String(dataset.labels.length)} />
              <Stat label="Language" value={(dataset.language || "—").toUpperCase()} />
            </div>
            {Object.keys(dataset.difficulty_counts || {}).length > 0 && (
              <p className="text-xs text-t-secondary mt-3">
                Difficulty:{" "}
                {Object.entries(dataset.difficulty_counts).map(([k, v]) => (
                  <span key={k} className="mr-2">
                    {k} <span className="text-primary font-medium">{formatInt(v as number)}</span>
                  </span>
                ))}
              </p>
            )}
          </SectionCard>

          <SectionCard
            title="Labels"
            description="Rows per label. Descriptions are sent to every model as the label definition."
            className="lg:col-span-3"
          >
            <div className="space-y-2.5 max-h-80 overflow-y-auto pr-1">
              {dataset.labels.map((l: any) => {
                const count = dataset.label_counts?.[l.name] || 0;
                return (
                  <button
                    key={l.name}
                    onClick={() => {
                      setLabelFilter(labelFilter === l.name ? "" : l.name);
                      setPage(0);
                    }}
                    className={cn(
                      "w-full text-left rounded-lg px-2 py-1.5 transition-colors",
                      labelFilter === l.name ? "bg-accent/10" : "hover:bg-surface-200/40"
                    )}
                    title="Filter rows by this label"
                  >
                    <div className="flex items-center justify-between gap-3 text-xs">
                      <code className="text-primary font-medium">{l.name}</code>
                      <span className="text-t-secondary tabular-nums">{formatInt(count)}</span>
                    </div>
                    <div className="h-1.5 bg-surface-200/60 rounded-full mt-1 overflow-hidden">
                      <div className="h-full rounded-full" style={{ width: `${(count / maxCount) * 100}%`, backgroundColor: colors[0] }} />
                    </div>
                    {l.description && <p className="text-[11px] text-t-secondary mt-1 leading-snug">{l.description}</p>}
                  </button>
                );
              })}
            </div>
          </SectionCard>
        </div>
      )}

      <SectionCard
        title="Rows"
        description={`${formatInt(total)} row${total === 1 ? "" : "s"}${labelFilter ? ` labeled “${labelFilter}”` : ""}${search ? ` matching “${search}”` : ""}`}
        actions={
          <form
            onSubmit={(e) => {
              e.preventDefault();
              setSearch(searchInput.trim());
              setPage(0);
            }}
            className="flex items-center gap-2"
          >
            <select
              value={labelFilter}
              onChange={(e) => {
                setLabelFilter(e.target.value);
                setPage(0);
              }}
              className="bg-surface-50 border border-visible rounded-lg px-2 py-1.5 text-xs text-primary focus:outline-none focus:border-accent/50"
            >
              <option value="">All labels</option>
              {dataset.labels.map((l: any) => (
                <option key={l.name} value={l.name}>
                  {l.name}
                </option>
              ))}
            </select>
            <div className="relative">
              <Search className="w-3.5 h-3.5 text-muted absolute left-2 top-1/2 -translate-y-1/2" />
              <input
                value={searchInput}
                onChange={(e) => setSearchInput(e.target.value)}
                placeholder="Search text…"
                className="pl-7 pr-2 py-1.5 w-48 bg-surface-50 border border-visible rounded-lg text-xs text-primary placeholder-muted focus:outline-none focus:border-accent/50"
              />
            </div>
          </form>
        }
      >
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-[11px] uppercase tracking-wider text-muted border-b border-visible">
                <th className="py-2 pr-3 font-medium w-16">#</th>
                <th className="py-2 pr-3 font-medium">Text</th>
                <th className="py-2 pr-3 font-medium w-48">Expected label</th>
                <th className="py-2 font-medium w-20">Difficulty</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[color:var(--input-border)]">
              {items.map((it, idx) => (
                <tr key={it.id} className="align-top">
                  <td className="py-2 pr-3 text-xs text-muted tabular-nums">{page * PAGE_SIZE + idx + 1}</td>
                  <td className="py-2 pr-3 text-primary text-[13px] leading-snug">{it.text}</td>
                  <td className="py-2 pr-3">
                    <code className="text-xs text-accent">{it.expected_label}</code>
                  </td>
                  <td className="py-2 text-xs text-t-secondary">{it.difficulty || "—"}</td>
                </tr>
              ))}
              {items.length === 0 && (
                <tr>
                  <td colSpan={4} className="py-8 text-center text-sm text-muted">
                    No rows match.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
        <Pager page={page} pages={pages} onChange={setPage} />
      </SectionCard>
    </div>
  );
}

function BackButton({ onClick }: { onClick: () => void }) {
  return (
    <button onClick={onClick} className="flex items-center gap-1 text-xs text-t-secondary hover:text-primary transition-colors">
      <ChevronLeft className="w-3.5 h-3.5" />
      All datasets
    </button>
  );
}

function IconButton({
  onClick,
  icon: Icon,
  label,
  disabled,
  danger,
}: {
  onClick: () => void;
  icon: any;
  label: string;
  disabled?: boolean;
  danger?: boolean;
}) {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      className={cn(
        "flex items-center gap-1.5 px-3 py-2 text-xs font-medium border border-visible rounded-lg transition-colors disabled:opacity-50",
        danger ? "text-danger hover:bg-danger/10" : "text-t-secondary hover:text-primary hover:bg-surface-200/50"
      )}
    >
      <Icon className="w-3.5 h-3.5" />
      {label}
    </button>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="bg-surface-50 border border-visible rounded-lg px-3 py-2">
      <p className="text-[10px] uppercase tracking-wider text-muted">{label}</p>
      <p className="text-sm font-semibold text-primary mt-0.5">{value}</p>
    </div>
  );
}

export function Pager({ page, pages, onChange }: { page: number; pages: number; onChange: (p: number) => void }) {
  if (pages <= 1) return null;
  return (
    <div className="flex items-center justify-end gap-2 mt-3 text-xs text-t-secondary">
      <button
        onClick={() => onChange(Math.max(0, page - 1))}
        disabled={page === 0}
        className="p-1.5 rounded-md border border-visible disabled:opacity-40 hover:bg-surface-200/50"
        aria-label="Previous page"
      >
        <ChevronLeft className="w-3.5 h-3.5" />
      </button>
      <span className="tabular-nums">
        Page {page + 1} of {pages}
      </span>
      <button
        onClick={() => onChange(Math.min(pages - 1, page + 1))}
        disabled={page >= pages - 1}
        className="p-1.5 rounded-md border border-visible disabled:opacity-40 hover:bg-surface-200/50"
        aria-label="Next page"
      >
        <ChevronRight className="w-3.5 h-3.5" />
      </button>
    </div>
  );
}

/* ═══════════════════════════ Edit ═══════════════════════════ */

function EditDataset({ dataset, onCancel, onSaved }: { dataset: any; onCancel: () => void; onSaved: (d: any) => void }) {
  const [name, setName] = useState(dataset.name);
  const [task, setTask] = useState(dataset.task);
  const [description, setDescription] = useState(dataset.description || "");
  const [labels, setLabels] = useState<any[]>(dataset.labels.map((l: any) => ({ ...l })));
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const save = async () => {
    setSaving(true);
    setError(null);
    try {
      onSaved(await api.updateDecisionDataset(dataset.id, { name, task, description, labels }));
    } catch (e: any) {
      setError(e.message);
    } finally {
      setSaving(false);
    }
  };

  return (
    <SectionCard title="Edit dataset" description="Label names are fixed; refine the task question and label definitions.">
      <div className="space-y-4">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          <Field label="Name">
            <input value={name} onChange={(e) => setName(e.target.value)} className={inputCls} />
          </Field>
          <Field label="Description">
            <input value={description} onChange={(e) => setDescription(e.target.value)} className={inputCls} />
          </Field>
        </div>
        <Field label="Task question">
          <textarea value={task} onChange={(e) => setTask(e.target.value)} rows={2} className={inputCls} />
        </Field>
        <LabelEditor labels={labels} onChange={setLabels} />
        {error && <ErrorBanner message={error} />}
        <div className="flex justify-end gap-2">
          <button onClick={onCancel} className="px-4 py-2 text-sm text-t-secondary hover:text-primary">
            Cancel
          </button>
          <button
            onClick={save}
            disabled={saving}
            className="flex items-center gap-2 px-4 py-2 bg-accent text-accent-foreground rounded-lg text-sm font-medium hover:bg-accent/90 disabled:opacity-50"
          >
            {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Check className="w-4 h-4" />}
            Save
          </button>
        </div>
      </div>
    </SectionCard>
  );
}

const inputCls =
  "w-full px-3 py-2 bg-surface-50 border border-visible rounded-lg text-primary placeholder-muted text-sm focus:outline-none focus:border-accent/50";

function Field({ label, hint, children }: { label: string; hint?: string; children: React.ReactNode }) {
  return (
    <label className="block">
      <span className="block text-xs font-medium text-t-hover mb-1">{label}</span>
      {hint && <span className="block text-[11px] text-muted mb-1.5">{hint}</span>}
      {children}
    </label>
  );
}

function LabelEditor({
  labels,
  onChange,
  counts,
}: {
  labels: any[];
  onChange: (labels: any[]) => void;
  counts?: Record<string, number>;
}) {
  return (
    <div>
      <span className="block text-xs font-medium text-t-hover mb-1">Label definitions</span>
      <span className="block text-[11px] text-muted mb-2">
        One line per label. Decision models receive these as the choice criteria; LLMs see them in the prompt.
      </span>
      <div className="space-y-1.5 max-h-72 overflow-y-auto pr-1">
        {labels.map((l, idx) => (
          <div key={l.name} className="flex items-center gap-2">
            <code className="w-44 flex-shrink-0 text-xs text-primary truncate" title={l.name}>
              {l.name}
              {counts && <span className="text-muted ml-1">({counts[l.name] ?? 0})</span>}
            </code>
            <input
              value={l.description}
              onChange={(e) => {
                const next = [...labels];
                next[idx] = { ...l, description: e.target.value };
                onChange(next);
              }}
              placeholder="What belongs in this label?"
              className="flex-1 px-2.5 py-1.5 bg-surface-50 border border-visible rounded-md text-primary placeholder-muted text-xs focus:outline-none focus:border-accent/50"
            />
          </div>
        ))}
      </div>
    </div>
  );
}

/* ═══════════════════════════ Upload ═══════════════════════════ */

function UploadPanel({ onCancel, onCreated }: { onCancel: () => void; onCreated: (ds: any) => void }) {
  const fileRef = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<any>(null);
  const [textColumn, setTextColumn] = useState("");
  const [labelColumn, setLabelColumn] = useState("");
  const [name, setName] = useState("");
  const [task, setTask] = useState("");
  const [labels, setLabels] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const runPreview = async (f: File, cols: { text_column?: string; label_column?: string } = {}) => {
    setLoading(true);
    setError(null);
    try {
      const res = await api.uploadDecisionDataset(f, { ...cols, dry_run: true });
      setPreview(res);
      setTextColumn(res.text_column || "");
      setLabelColumn(res.label_column || "");
      setLabels(res.labels);
      setName((prev) => prev || res.name || f.name.replace(/\.[^.]+$/, ""));
      setTask((prev) => prev || res.task || "");
    } catch (e: any) {
      setPreview(null);
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  const onFile = (f: File | null) => {
    setFile(f);
    setPreview(null);
    setName("");
    setTask("");
    if (f) runPreview(f);
  };

  const importDataset = async () => {
    if (!file || !preview) return;
    setLoading(true);
    setError(null);
    try {
      const res = await api.uploadDecisionDataset(file, {
        name: name.trim() || undefined,
        task: task.trim() || undefined,
        text_column: textColumn,
        label_column: labelColumn,
        label_descriptions: Object.fromEntries(labels.map((l) => [l.name, l.description || ""])),
      });
      onCreated(res.dataset);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <SectionCard
      title="Upload a custom dataset"
      description="Each row needs a text and its expected label. JSON files exported from Yoke (with task and labels) are accepted too."
      actions={
        <button onClick={onCancel} className="p-1 hover:bg-surface-200 rounded-lg">
          <X className="w-4 h-4 text-t-secondary" />
        </button>
      }
    >
      <div className="space-y-4">
        <div
          onClick={() => fileRef.current?.click()}
          onDragOver={(e) => e.preventDefault()}
          onDrop={(e) => {
            e.preventDefault();
            onFile(e.dataTransfer.files?.[0] || null);
          }}
          className="border border-dashed border-visible rounded-xl p-6 text-center cursor-pointer hover:border-accent/50 transition-colors"
        >
          <FileUp className="w-7 h-7 text-muted mx-auto mb-2" />
          {file ? (
            <p className="text-sm text-primary font-medium">{file.name}</p>
          ) : (
            <p className="text-sm text-primary">Drop a file here or click to browse</p>
          )}
          <p className="text-[11px] text-muted mt-1">.csv · .tsv · .json · .jsonl — up to 50,000 rows and 100 labels</p>
          <input
            ref={fileRef}
            type="file"
            accept=".csv,.tsv,.txt,.json,.jsonl,.ndjson"
            className="hidden"
            onChange={(e) => onFile(e.target.files?.[0] || null)}
          />
        </div>

        {loading && (
          <div className="flex items-center gap-2 text-sm text-t-secondary">
            <Loader2 className="w-4 h-4 animate-spin" /> Reading file…
          </div>
        )}
        {error && <ErrorBanner message={error} />}

        {preview && (
          <>
            <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
              <Field label="Text column">
                <select
                  value={textColumn}
                  onChange={(e) => {
                    setTextColumn(e.target.value);
                    if (e.target.value && labelColumn) {
                      runPreview(file!, { text_column: e.target.value, label_column: labelColumn });
                    }
                  }}
                  className={inputCls}
                >
                  {!textColumn && <option value="">Select column…</option>}
                  {preview.columns.map((c: string) => (
                    <option key={c} value={c}>
                      {c}
                    </option>
                  ))}
                </select>
              </Field>
              <Field label="Label column">
                <select
                  value={labelColumn}
                  onChange={(e) => {
                    setLabelColumn(e.target.value);
                    if (e.target.value && textColumn) {
                      runPreview(file!, { text_column: textColumn, label_column: e.target.value });
                    }
                  }}
                  className={inputCls}
                >
                  {!labelColumn && <option value="">Select column…</option>}
                  {preview.columns.map((c: string) => (
                    <option key={c} value={c}>
                      {c}
                    </option>
                  ))}
                </select>
              </Field>
              <div className="md:col-span-2 grid grid-cols-3 gap-2">
                <Stat label="Valid rows" value={formatInt(preview.rows_valid)} />
                <Stat label="In file" value={formatInt(preview.rows_total)} />
                <Stat label="Labels" value={String(preview.labels.length)} />
              </div>
            </div>

            {preview.warnings?.length > 0 && (
              <ul className="space-y-1">
                {preview.warnings.map((w: string) => (
                  <li key={w} className="flex items-start gap-2 text-xs text-warning">
                    <AlertCircle className="w-3.5 h-3.5 mt-0.5 flex-shrink-0" />
                    {w}
                  </li>
                ))}
              </ul>
            )}

            {preview.needs_mapping ? (
              <div>
                <span className="block text-xs font-medium text-t-hover mb-1.5">
                  Pick the column with the text and the column with the expected label.
                </span>
                <div className="overflow-x-auto border border-visible rounded-lg">
                  <table className="w-full text-xs">
                    <thead>
                      <tr className="text-left text-[10px] uppercase tracking-wider text-muted border-b border-visible">
                        {preview.columns.map((c: string) => (
                          <th key={c} className="px-3 py-1.5 font-medium">
                            {c}
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-[color:var(--input-border)]">
                      {preview.raw_sample.map((row: any, i: number) => (
                        <tr key={i}>
                          {preview.columns.map((c: string) => (
                            <td key={c} className="px-3 py-1.5 text-primary">
                              {row[c]}
                            </td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            ) : (
            <>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              <Field label="Dataset name">
                <input value={name} onChange={(e) => setName(e.target.value)} className={inputCls} />
              </Field>
              <Field label="Task question" hint="What should every model decide? e.g. “Which team should handle this ticket?”">
                <input
                  value={task}
                  onChange={(e) => setTask(e.target.value)}
                  placeholder="Which label best describes this text?"
                  className={inputCls}
                />
              </Field>
            </div>

            <LabelEditor labels={labels} onChange={setLabels} counts={preview.label_counts} />

            <div>
              <span className="block text-xs font-medium text-t-hover mb-1.5">Sample rows</span>
              <div className="border border-visible rounded-lg divide-y divide-[color:var(--input-border)]">
                {preview.sample.slice(0, 5).map((row: any, i: number) => (
                  <div key={i} className="flex items-start gap-3 px-3 py-2 text-xs">
                    <span className="flex-1 text-primary">{row.text}</span>
                    <code className="text-accent flex-shrink-0">{row.label}</code>
                  </div>
                ))}
              </div>
            </div>

            <div className="flex justify-end gap-2">
              <button onClick={onCancel} className="px-4 py-2 text-sm text-t-secondary hover:text-primary">
                Cancel
              </button>
              <button
                onClick={importDataset}
                disabled={loading || !name.trim()}
                className="flex items-center gap-2 px-4 py-2 bg-accent text-accent-foreground rounded-lg text-sm font-medium hover:bg-accent/90 disabled:opacity-50"
              >
                {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Upload className="w-4 h-4" />}
                Import {formatInt(preview.rows_valid)} rows
              </button>
            </div>
            </>
            )}
          </>
        )}
      </div>
    </SectionCard>
  );
}
