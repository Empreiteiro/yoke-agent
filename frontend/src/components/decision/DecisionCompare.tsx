"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import {
  AlertCircle,
  Brain,
  Check,
  ChevronDown,
  ChevronRight,
  Copy,
  Loader2,
  Play,
  Plus,
  Regex,
  Scale,
  Settings,
  ShieldCheck,
  Timer,
  X,
  Zap,
} from "lucide-react";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";
import { KindBadge, ModelKind, SectionCard, SeriesDot, VariantBadge, formatCost, formatInt, useSeriesColors } from "./shared";

const MAX_MODELS = 8;
const SAMPLE_PRESETS = [100, 250, 500, 1000];
const SAFE_NAMES = ["safe", "benign", "allow", "allowed", "clean", "harmless", "legitimate"];

// Starter patterns for a regex baseline, keyed by common guardrail label
// names. Deliberately simple — the point is to measure what a cheap rule
// set catches, not to win.
const STARTER_RULES: Record<string, string[]> = {
  pii_exposure: [
    String.raw`\b\d{3}-\d{2}-\d{4}\b`,
    String.raw`\b(?:\d[ -]?){13,16}\b`,
    String.raw`\bpassword\b`,
    String.raw`\b(ssn|social security|iban|routing number|account number)\b`,
  ],
  jailbreak: [
    String.raw`\byou are dan\b`,
    String.raw`developer mode`,
    String.raw`\b(no|zero|without)\s+(limitations|restrictions|filters|rules|policies|safety)`,
    String.raw`\b(pretend|act as|role-?play|stay in character|persona|evil twin)\b`,
    String.raw`\b(unrestricted|unlocked)\b`,
  ],
  prompt_injection: [
    String.raw`\b(ignore|disregard|forget)\b.{0,40}\b(instructions|guidelines|rules|prompt|you are)\b`,
    String.raw`\b(system|hidden|admin|developer|internal)\s+(prompt|instructions|message|tools)\b`,
    String.raw`\b(reveal|show|print|repeat|encode)\b.{0,40}\b(instructions|prompt|tools)\b`,
    String.raw`\bnew instruction`,
  ],
};

interface LabelMapRow {
  from: string;
  to: string;
}

interface SelectedModel {
  uid: string;
  kind: ModelKind;
  provider_id: number | null;
  provider_name: string;
  provider_type: string;
  model: string;
  label: string;
  input_price: string;
  output_price: string;
  pricing_source: string;
  infra_cost: string;
  variant: string;
  // Policy overrides (decision models & LLMs)
  task: string;
  label_descriptions: Record<string, string>;
  system_prompt: string;
  user_prompt: string;
  // Answer aliases / classifier label map
  label_map: LabelMapRow[];
  threshold: string;
  fallback_label: string;
  // Rules baseline: one pattern per line, keyed by label
  rules: Record<string, string>;
  default_label: string;
  case_sensitive: boolean;
  deployment: { hardware: string; parameters: string; serving: string; region: string };
  expanded: boolean;
}

const baseKey = (m: { kind: string; provider_id: number | null; model: string }) => `${m.kind}:${m.provider_id ?? "-"}:${m.model}`;

const toPrice = (v: number | null | undefined) => (v === null || v === undefined ? "" : String(v));

let uidCounter = 0;
const nextUid = () => `m${Date.now().toString(36)}${(uidCounter++).toString(36)}`;

function safeLabel(labels: any[]): string {
  return labels.find((l) => SAFE_NAMES.includes(l.name.toLowerCase()))?.name || "";
}

function starterRules(labels: any[]): Record<string, string> {
  const out: Record<string, string> = {};
  labels.forEach((l) => {
    out[l.name] = (STARTER_RULES[l.name] || []).join("\n");
  });
  return out;
}

function blankConfig(kind: ModelKind, labels: any[]) {
  const safe = safeLabel(labels);
  return {
    variant: "",
    task: "",
    label_descriptions: {},
    system_prompt: "",
    user_prompt: "",
    label_map: [],
    threshold: "",
    fallback_label: kind === "classifier" ? safe : "",
    rules: kind === "rules" ? starterRules(labels) : {},
    default_label: kind === "rules" ? safe || labels[0]?.name || "" : "",
    case_sensitive: false,
    deployment: { hardware: "", parameters: "", serving: "", region: "" },
  };
}

function toSelected(m: any, labels: any[]): SelectedModel {
  return {
    uid: nextUid(),
    kind: m.kind,
    provider_id: m.provider_id,
    provider_name: m.provider_name,
    provider_type: m.provider_type,
    model: m.model,
    label: m.label ?? m.model,
    input_price: toPrice(m.input_price_per_million),
    output_price: toPrice(m.output_price_per_million),
    pricing_source: m.pricing_source,
    infra_cost: "",
    expanded: false,
    ...blankConfig(m.kind, labels),
  };
}

function rulesModel(labels: any[]): SelectedModel {
  return toSelected(
    {
      kind: "rules",
      provider_id: null,
      provider_name: "Rules",
      provider_type: "rules",
      model: "regex-rules",
      input_price_per_million: 0,
      output_price_per_million: 0,
      pricing_source: "local",
    },
    labels
  );
}

const orNull = (v: string) => (v.trim() === "" ? null : v.trim());
const numOrNull = (v: string) => (v.trim() === "" || Number.isNaN(Number(v)) ? null : Number(v));

function toSpec(m: SelectedModel) {
  const descriptions = Object.fromEntries(Object.entries(m.label_descriptions).filter(([, v]) => v.trim() !== ""));
  const labelMap = Object.fromEntries(m.label_map.filter((r) => r.from.trim() && r.to).map((r) => [r.from.trim(), r.to]));
  const deployment = Object.fromEntries(Object.entries(m.deployment).filter(([, v]) => v.trim() !== ""));
  const rules =
    m.kind === "rules"
      ? Object.entries(m.rules)
          .map(([label, text]) => ({ label, patterns: text.split("\n").map((p) => p.trim()).filter(Boolean) }))
          .filter((r) => r.patterns.length > 0 && r.label !== m.default_label)
      : null;
  const usesPolicy = m.kind === "decision" || m.kind === "llm";
  return {
    kind: m.kind,
    provider_id: m.provider_id,
    model: m.model,
    input_price_per_million: numOrNull(m.input_price),
    output_price_per_million: numOrNull(m.output_price),
    infra_cost_per_hour: m.kind === "rules" ? null : numOrNull(m.infra_cost),
    variant: orNull(m.variant),
    task: usesPolicy ? orNull(m.task) : null,
    label_descriptions: usesPolicy && Object.keys(descriptions).length ? descriptions : null,
    system_prompt: m.kind === "llm" ? orNull(m.system_prompt) : null,
    user_prompt: m.kind === "llm" ? orNull(m.user_prompt) : null,
    label_map: m.kind !== "rules" && Object.keys(labelMap).length ? labelMap : null,
    threshold: m.kind === "classifier" ? numOrNull(m.threshold) : null,
    fallback_label: m.kind === "classifier" ? m.fallback_label || null : null,
    rules,
    default_label: m.kind === "rules" ? m.default_label || null : null,
    case_sensitive: m.kind === "rules" ? m.case_sensitive : false,
    deployment: m.kind !== "rules" && Object.keys(deployment).length ? deployment : null,
  };
}

export default function DecisionCompare() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const colors = useSeriesColors();

  const [datasets, setDatasets] = useState<any[]>([]);
  const [available, setAvailable] = useState<{
    decision_models: any[];
    classifier_models: any[];
    llm_models: any[];
    default_prompts?: { system: string; user: string };
  }>({ decision_models: [], classifier_models: [], llm_models: [] });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [datasetId, setDatasetId] = useState<number | null>(null);
  const [sampleMode, setSampleMode] = useState<"preset" | "all" | "custom">("preset");
  const [samplePreset, setSamplePreset] = useState(250);
  const [customSample, setCustomSample] = useState("");
  const [sampling, setSampling] = useState("stratified");
  const [selected, setSelected] = useState<SelectedModel[]>([]);
  const [name, setName] = useState("");
  const [concurrency, setConcurrency] = useState(8);
  const [temperature, setTemperature] = useState(0);
  const [seed, setSeed] = useState(42);
  const [latencyMode, setLatencyMode] = useState(false);
  const [warmup, setWarmup] = useState(3);

  const [estimate, setEstimate] = useState<any>(null);
  const [estimating, setEstimating] = useState(false);
  const [starting, setStarting] = useState(false);

  const dataset = datasets.find((d) => d.id === datasetId);
  const labels: any[] = useMemo(() => dataset?.labels || [], [dataset]);

  useEffect(() => {
    Promise.all([api.listDecisionDatasets(), api.listComparableModels()])
      .then(([ds, models]) => {
        setDatasets(ds);
        setAvailable(models);
        const fromUrl = Number(searchParams.get("dataset"));
        const initial = ds.find((d: any) => d.id === fromUrl) || ds[0];
        if (initial) setDatasetId(initial.id);
        // Sensible default: the first decision model + the first two LLMs.
        const defaults = [...models.decision_models.slice(0, 1), ...models.llm_models.slice(0, 2)];
        setSelected(defaults.map((m) => toSelected(m, initial?.labels || [])));
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // Label-dependent settings don't carry over to another dataset.
  useEffect(() => {
    setSelected((prev) =>
      prev.map((m) => ({ ...m, ...blankConfig(m.kind, labels), variant: m.variant, deployment: m.deployment }))
    );
  }, [labels]);

  const sampleSize: number | null = useMemo(() => {
    if (sampleMode === "all") return null;
    if (sampleMode === "custom") {
      const n = parseInt(customSample, 10);
      return Number.isFinite(n) && n > 0 ? n : null;
    }
    return samplePreset;
  }, [sampleMode, samplePreset, customSample]);

  const effectiveItems = dataset ? Math.min(sampleSize ?? dataset.item_count, dataset.item_count) : 0;

  const payloadModels = useMemo(() => selected.map(toSpec), [selected]);

  // Live cost projection, debounced.
  useEffect(() => {
    if (!datasetId || selected.length === 0) {
      setEstimate(null);
      return;
    }
    const handle = setTimeout(() => {
      setEstimating(true);
      api
        .estimateComparison({ dataset_id: datasetId, models: payloadModels, sample_size: sampleSize, sampling, seed })
        .then(setEstimate)
        .catch(() => setEstimate(null))
        .finally(() => setEstimating(false));
    }, 500);
    return () => clearTimeout(handle);
  }, [datasetId, payloadModels, sampleSize, sampling, seed, selected.length]);

  const toggle = (m: any) => {
    const key = baseKey(m);
    setSelected((prev) => {
      if (prev.some((s) => baseKey(s) === key)) return prev.filter((s) => baseKey(s) !== key);
      if (prev.length >= MAX_MODELS) return prev;
      return [...prev, toSelected(m, labels)];
    });
  };

  const update = (uid: string, patch: Partial<SelectedModel>) =>
    setSelected((prev) => prev.map((s) => (s.uid === uid ? { ...s, ...patch } : s)));

  const duplicate = (m: SelectedModel) =>
    setSelected((prev) => {
      if (prev.length >= MAX_MODELS) return prev;
      const siblings = prev.filter((s) => baseKey(s) === baseKey(m)).length;
      const copy: SelectedModel = {
        ...m,
        uid: nextUid(),
        variant: `variant ${siblings + 1}`,
        expanded: true,
        label_descriptions: { ...m.label_descriptions },
        label_map: m.label_map.map((r) => ({ ...r })),
        rules: { ...m.rules },
        deployment: { ...m.deployment },
      };
      const firstUnnamed = prev.map((s) => (s.uid === m.uid && !s.variant ? { ...s, variant: "default" } : s));
      const idx = firstUnnamed.findIndex((s) => s.uid === m.uid);
      return [...firstUnnamed.slice(0, idx + 1), copy, ...firstUnnamed.slice(idx + 1)];
    });

  const start = async () => {
    if (!datasetId || selected.length === 0) return;
    setStarting(true);
    setError(null);
    try {
      const comp = await api.createComparison({
        name: name.trim() || undefined,
        dataset_id: datasetId,
        models: payloadModels,
        sample_size: sampleSize,
        sampling,
        seed,
        concurrency,
        temperature,
        latency_mode: latencyMode,
        warmup: latencyMode ? warmup : 0,
      });
      router.push(`/?view=decision-results&comparison=${comp.id}`);
    } catch (e: any) {
      setError(e.message);
      setStarting(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="w-6 h-6 text-accent animate-spin" />
      </div>
    );
  }

  const noModels =
    available.decision_models.length === 0 && available.classifier_models.length === 0 && available.llm_models.length === 0;
  const unknownPrices = selected.filter((m) => m.input_price === "" && m.output_price === "" && m.infra_cost === "");
  const hasRules = selected.some((m) => m.kind === "rules");

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <div className="w-10 h-10 rounded-xl bg-accent/15 flex items-center justify-center">
          <Scale className="w-5 h-5 text-accent" />
        </div>
        <div>
          <h2 className="text-lg font-semibold text-primary">Compare Decision Models vs LLMs</h2>
          <p className="text-sm text-t-secondary">
            Run the same labeled sample through Jev-style decision models, pre-trained classifiers, regex baselines and LLM
            classifiers, then compare accuracy, errors, latency and total cost.
          </p>
        </div>
      </div>

      {error && (
        <div className="flex items-start gap-2 px-4 py-3 bg-danger/10 border border-danger/20 rounded-xl text-danger text-sm">
          <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
          <span className="flex-1">{error}</span>
          <button onClick={() => setError(null)}>
            <X className="w-4 h-4" />
          </button>
        </div>
      )}

      {/* 1 — Dataset */}
      <SectionCard title="1. Dataset" description="Pick a built-in dataset or one you uploaded.">
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
          <div className="lg:col-span-2 space-y-2">
            <select
              value={datasetId ?? ""}
              onChange={(e) => setDatasetId(Number(e.target.value))}
              className="w-full px-3 py-2 bg-surface-50 border border-visible rounded-lg text-primary text-sm focus:outline-none focus:border-accent/50"
            >
              {datasets.map((d) => (
                <option key={d.id} value={d.id}>
                  {d.name} — {formatInt(d.item_count)} rows · {d.labels.length} labels{d.is_builtin ? "" : " (custom)"}
                </option>
              ))}
            </select>
            {dataset && (
              <div className="bg-surface-50 border border-visible rounded-lg px-3 py-2">
                <p className="text-[11px] uppercase tracking-wider text-muted">Task</p>
                <p className="text-sm text-primary">{dataset.task}</p>
                <div className="flex flex-wrap gap-1 mt-2">
                  {dataset.labels.slice(0, 16).map((l: any) => (
                    <code key={l.name} className="px-1.5 py-0.5 rounded bg-surface-200 text-[11px] text-t-hover">
                      {l.name}
                    </code>
                  ))}
                  {dataset.labels.length > 16 && <span className="text-[11px] text-muted">+{dataset.labels.length - 16} more</span>}
                </div>
              </div>
            )}
            <button
              onClick={() => router.push("/?view=decision-datasets")}
              className="text-xs text-accent hover:underline"
            >
              Browse or upload datasets →
            </button>
          </div>
          <div className="space-y-3">
            <div>
              <span className="block text-xs font-medium text-t-hover mb-1.5">Sample size</span>
              <div className="flex flex-wrap gap-1.5">
                {SAMPLE_PRESETS.map((n) => (
                  <Chip key={n} active={sampleMode === "preset" && samplePreset === n} onClick={() => { setSampleMode("preset"); setSamplePreset(n); }}>
                    {formatInt(n)}
                  </Chip>
                ))}
                <Chip active={sampleMode === "all"} onClick={() => setSampleMode("all")}>
                  All
                </Chip>
                <Chip active={sampleMode === "custom"} onClick={() => setSampleMode("custom")}>
                  Custom
                </Chip>
              </div>
              {sampleMode === "custom" && (
                <input
                  type="number"
                  min={1}
                  value={customSample}
                  onChange={(e) => setCustomSample(e.target.value)}
                  placeholder="Number of rows"
                  className="mt-2 w-full px-3 py-1.5 bg-surface-50 border border-visible rounded-lg text-primary text-sm focus:outline-none focus:border-accent/50"
                />
              )}
              <p className="text-[11px] text-muted mt-1.5">
                {formatInt(effectiveItems)} rows × {selected.length} model{selected.length === 1 ? "" : "s"} ={" "}
                {formatInt(effectiveItems * selected.length)} requests
              </p>
            </div>
            <div>
              <span className="block text-xs font-medium text-t-hover mb-1.5">Sampling</span>
              <select
                value={sampling}
                onChange={(e) => setSampling(e.target.value)}
                className="w-full px-3 py-1.5 bg-surface-50 border border-visible rounded-lg text-primary text-sm focus:outline-none focus:border-accent/50"
              >
                <option value="stratified">Stratified — keep the label mix</option>
                <option value="random">Random</option>
                <option value="first">First rows</option>
              </select>
            </div>
          </div>
        </div>
      </SectionCard>

      {/* 2 — Models */}
      <SectionCard
        title="2. Models"
        description={`Select up to ${MAX_MODELS}. Every model sees the same rows; open a model to change its policy, prompt or deployment, or duplicate it to compare policy variants.`}
      >
        {noModels && !hasRules ? (
          <EmptyProviders onOpenSettings={() => router.push("/?view=settings")} onAddRules={() => setSelected((p) => [...p, rulesModel(labels)])} />
        ) : (
          <div className="space-y-5">
            <ModelPicker
              title="Decision models"
              icon={Zap}
              hint="Typed choice + probability — TypeSafe Jev, OpenAI's Decisions API and System One-compatible endpoints."
              models={available.decision_models}
              selected={selected}
              onToggle={toggle}
              empty={
                <div className="flex flex-wrap items-center gap-3 text-xs text-t-secondary bg-warning/5 border border-warning/20 rounded-lg px-3 py-2.5">
                  <Zap className="w-4 h-4 text-warning" />
                  <span className="flex-1">
                    No decision provider yet. Add <strong className="text-primary">TypeSafe (Jev)</strong>, select{" "}
                    <strong className="text-primary">gpt-6-luna</strong> under Decision Models on an OpenAI provider, or add
                    any System One-compatible endpoint (such as a self-hosted DiffusionGemma) in Settings → Providers.
                  </span>
                  <button
                    onClick={() => router.push("/?view=settings")}
                    className="flex items-center gap-1 px-2.5 py-1 rounded-md border border-visible text-primary hover:bg-surface-200/50"
                  >
                    <Settings className="w-3 h-3" /> Providers
                  </button>
                </div>
              }
            />
            <ModelPicker
              title="Text classifiers"
              icon={ShieldCheck}
              hint="Pre-trained guardrail classifiers (DeBERTa, Granite Guardian…) behind a Hugging Face / TEI or detector endpoint, and guard models such as Nemotron-3.5 Content Safety on NVIDIA NIM. Map their native labels in the model's settings."
              models={available.classifier_models}
              selected={selected}
              onToggle={toggle}
              empty={
                <p className="text-xs text-muted">
                  No classifier provider. Add a <strong className="text-t-hover">Text classifier</strong> provider in Settings →
                  Providers to benchmark the traditional guardrails.
                </p>
              }
            />
            <ModelPicker
              title="LLMs"
              icon={Brain}
              hint="Prompted to answer with exactly one label as JSON — or with your own prompt template."
              models={available.llm_models}
              selected={selected}
              onToggle={toggle}
              empty={<p className="text-xs text-muted">No LLM providers configured.</p>}
            />
            <div>
              <div className="flex items-center gap-2 mb-1">
                <Regex className="w-3.5 h-3.5 text-t-secondary" />
                <span className="text-xs font-semibold text-primary uppercase tracking-wider">Rule baseline</span>
              </div>
              <p className="text-[11px] text-muted mb-2">Regex patterns per label, run in-process — the floor every model should beat.</p>
              <button
                onClick={() => setSelected((p) => (p.length >= MAX_MODELS ? p : [...p, rulesModel(labels)]))}
                disabled={selected.length >= MAX_MODELS}
                className="px-3 py-1.5 rounded-lg text-sm border transition-colors disabled:opacity-40 bg-surface-50 border-visible text-t-hover hover:text-primary hover:border-accent/50"
              >
                <Plus className="w-3 h-3 inline mr-1 opacity-60" />
                Add regex baseline
              </button>
            </div>

            {selected.length > 0 && (
              <div>
                <div className="flex items-baseline justify-between mb-2">
                  <span className="text-xs font-medium text-t-hover">Selected models & pricing</span>
                  <span className="text-[11px] text-muted">USD per 1M tokens — edit to match your contract</span>
                </div>
                <div className="border border-visible rounded-xl divide-y divide-[color:var(--input-border)]">
                  {selected.map((m, idx) => (
                    <SelectedRow
                      key={m.uid}
                      m={m}
                      color={colors[idx % colors.length]}
                      labels={labels}
                      task={dataset?.task || ""}
                      defaultPrompts={available.default_prompts}
                      canDuplicate={selected.length < MAX_MODELS}
                      onChange={(patch) => update(m.uid, patch)}
                      onDuplicate={() => duplicate(m)}
                      onRemove={() => setSelected((prev) => prev.filter((s) => s.uid !== m.uid))}
                    />
                  ))}
                </div>
                {unknownPrices.length > 0 && (
                  <p className="text-[11px] text-warning mt-1.5">
                    {unknownPrices.length} model{unknownPrices.length > 1 ? "s have" : " has"} no known price — its total cost will
                    show as “—”. Enter a price (or 0, or a $/hour for self-hosted hardware) to include it.
                  </p>
                )}
              </div>
            )}
          </div>
        )}
      </SectionCard>

      {/* 3 — Run settings */}
      <SectionCard title="3. Run settings">
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <label className="block md:col-span-2">
            <span className="block text-xs font-medium text-t-hover mb-1">Comparison name</span>
            <input
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder={dataset ? `${dataset.name} — ${selected.length} models` : "My comparison"}
              className="w-full px-3 py-2 bg-surface-50 border border-visible rounded-lg text-primary placeholder-muted text-sm focus:outline-none focus:border-accent/50"
            />
          </label>
          <label className="block">
            <span className="block text-xs font-medium text-t-hover mb-1">Parallel requests per model</span>
            <input
              type="number"
              min={1}
              max={32}
              value={latencyMode ? 1 : concurrency}
              disabled={latencyMode}
              onChange={(e) => setConcurrency(Math.max(1, Math.min(32, Number(e.target.value) || 1)))}
              className="w-full px-3 py-2 bg-surface-50 border border-visible rounded-lg text-primary text-sm focus:outline-none focus:border-accent/50 disabled:opacity-60"
            />
          </label>
          <label className="block">
            <span className="block text-xs font-medium text-t-hover mb-1">LLM temperature</span>
            <input
              type="number"
              min={0}
              max={2}
              step={0.1}
              value={temperature}
              onChange={(e) => setTemperature(Math.max(0, Math.min(2, Number(e.target.value) || 0)))}
              className="w-full px-3 py-2 bg-surface-50 border border-visible rounded-lg text-primary text-sm focus:outline-none focus:border-accent/50"
            />
          </label>
        </div>
        <div className="flex flex-wrap items-end gap-4 mt-3">
          <label className="block w-40">
            <span className="block text-xs font-medium text-t-hover mb-1">Sampling seed</span>
            <input
              type="number"
              value={seed}
              onChange={(e) => setSeed(Number(e.target.value) || 0)}
              className="w-full px-3 py-1.5 bg-surface-50 border border-visible rounded-lg text-primary text-sm focus:outline-none focus:border-accent/50"
            />
          </label>
          <div className="flex-1 min-w-[280px] bg-surface-50 border border-visible rounded-lg px-3 py-2.5">
            <label className="flex items-start gap-2.5 cursor-pointer">
              <input
                type="checkbox"
                checked={latencyMode}
                onChange={(e) => setLatencyMode(e.target.checked)}
                className="mt-0.5 w-4 h-4 accent-accent"
              />
              <span className="flex-1">
                <span className="text-xs font-medium text-primary flex items-center gap-1.5">
                  <Timer className="w-3.5 h-3.5" /> Latency benchmark mode
                </span>
                <span className="block text-[11px] text-t-secondary mt-0.5">
                  One request in flight and one model at a time, so percentiles aren&apos;t skewed by queueing or by models
                  competing for the same hardware. Slower to run.
                </span>
              </span>
            </label>
            {latencyMode && (
              <label className="flex items-center gap-2 mt-2 ml-6 text-[11px] text-t-hover">
                Warm-up requests per model (discarded)
                <input
                  type="number"
                  min={0}
                  max={20}
                  value={warmup}
                  onChange={(e) => setWarmup(Math.max(0, Math.min(20, Number(e.target.value) || 0)))}
                  className="w-16 px-2 py-1 bg-surface-100 border border-visible rounded-md text-primary text-xs"
                />
              </label>
            )}
          </div>
        </div>
      </SectionCard>

      {/* Estimate + start */}
      <div className="bg-surface-100 rounded-2xl border border-visible p-6">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="flex-1 min-w-[280px]">
            <h3 className="text-sm font-semibold text-primary flex items-center gap-2">
              Projected cost
              {estimating && <Loader2 className="w-3.5 h-3.5 animate-spin text-muted" />}
            </h3>
            <p className="text-xs text-t-secondary mt-0.5">
              Estimated from text length (≈4 characters per token). Actual usage — and hardware cost for models with a $/hour —
              is measured during the run.
            </p>
            {estimate && (
              <table className="w-full text-xs mt-3">
                <thead>
                  <tr className="text-left text-[10px] uppercase tracking-wider text-muted">
                    <th className="py-1 font-medium">Model</th>
                    <th className="py-1 font-medium text-right">Input tokens</th>
                    <th className="py-1 font-medium text-right">Output tokens</th>
                    <th className="py-1 font-medium text-right">Est. cost</th>
                  </tr>
                </thead>
                <tbody>
                  {estimate.models.map((m: any, idx: number) => (
                    <tr key={idx} className="border-t border-[color:var(--input-border)]">
                      <td className="py-1.5 text-primary">
                        <span className="inline-flex items-center gap-2">
                          <SeriesDot color={colors[idx % colors.length]} />
                          {m.display_name}
                        </span>
                      </td>
                      <td className="py-1.5 text-right tabular-nums text-t-hover">{formatInt(m.input_tokens)}</td>
                      <td className="py-1.5 text-right tabular-nums text-t-hover">{formatInt(m.output_tokens)}</td>
                      <td className="py-1.5 text-right tabular-nums text-primary font-medium">
                        {formatCost(m.estimated_cost)}
                        {m.infra_cost_per_hour !== null && m.infra_cost_per_hour !== undefined && (
                          <span className="block text-[10px] text-muted font-normal">+ ${m.infra_cost_per_hour}/h hardware</span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
          <div className="flex flex-col items-end gap-2">
            <div className="text-right">
              <p className="text-[11px] uppercase tracking-wider text-muted">Estimated total</p>
              <p className="text-2xl font-semibold text-primary">{formatCost(estimate?.estimated_total_cost)}</p>
              <p className="text-[11px] text-t-secondary">{formatInt(estimate?.requests ?? 0)} requests</p>
            </div>
            <button
              onClick={start}
              disabled={starting || !datasetId || selected.length === 0}
              className="flex items-center gap-2 px-6 py-2.5 bg-accent text-accent-foreground rounded-xl text-sm font-semibold hover:bg-accent/90 transition-colors disabled:opacity-50"
            >
              {starting ? <Loader2 className="w-4 h-4 animate-spin" /> : <Play className="w-4 h-4" />}
              Run comparison
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

/* ═══════════════════════════ Selected model row ═══════════════════════════ */

const inputCls =
  "w-full px-2.5 py-1.5 bg-surface-50 border border-visible rounded-md text-primary text-xs placeholder-muted focus:outline-none focus:border-accent/50";

function SelectedRow({
  m,
  color,
  labels,
  task,
  defaultPrompts,
  canDuplicate,
  onChange,
  onDuplicate,
  onRemove,
}: {
  m: SelectedModel;
  color: string;
  labels: any[];
  task: string;
  defaultPrompts?: { system: string; user: string };
  canDuplicate: boolean;
  onChange: (patch: Partial<SelectedModel>) => void;
  onDuplicate: () => void;
  onRemove: () => void;
}) {
  const customized = summarize(m);
  return (
    <div>
      <div className="flex flex-wrap items-center gap-3 px-3 py-2.5">
        <SeriesDot color={color} />
        <div className="flex-1 min-w-[200px]">
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-sm text-primary font-medium">{m.label}</span>
            <KindBadge kind={m.kind} />
            <VariantBadge variant={m.variant} />
          </div>
          <span className="text-[11px] text-muted">
            {m.provider_name}
            {customized && <span className="text-accent"> · {customized}</span>}
          </span>
        </div>
        {m.kind !== "rules" && (
          <>
            <PriceInput label="Input" value={m.input_price} onChange={(v) => onChange({ input_price: v })} />
            <PriceInput label="Output" value={m.output_price} onChange={(v) => onChange({ output_price: v })} />
          </>
        )}
        <span
          className={cn(
            "text-[11px] w-28",
            m.input_price === "" && m.output_price === "" && m.infra_cost === "" ? "text-warning" : "text-muted"
          )}
        >
          {m.infra_cost !== ""
            ? `+ $${m.infra_cost}/h hardware`
            : m.input_price === "" && m.output_price === ""
              ? "Price unknown"
              : m.pricing_source}
        </span>
        <button
          onClick={() => onChange({ expanded: !m.expanded })}
          className="flex items-center gap-1 px-2 py-1 rounded-md text-[11px] text-t-hover border border-visible hover:text-primary hover:bg-surface-200/50"
          aria-expanded={m.expanded}
        >
          {m.expanded ? <ChevronDown className="w-3 h-3" /> : <ChevronRight className="w-3 h-3" />}
          Configure
        </button>
        <button
          onClick={onDuplicate}
          disabled={!canDuplicate}
          title="Duplicate as a variant (compare policies or prompts)"
          className="p-1 rounded-md hover:bg-surface-200/60 disabled:opacity-40"
          aria-label={`Duplicate ${m.model} as a variant`}
        >
          <Copy className="w-3.5 h-3.5 text-muted" />
        </button>
        <button onClick={onRemove} className="p-1 rounded-md hover:bg-surface-200/60" aria-label={`Remove ${m.model}`}>
          <X className="w-3.5 h-3.5 text-muted" />
        </button>
      </div>
      {m.expanded && (
        <div className="px-3 pb-4 pt-1 ml-5 space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            <Field label="Variant name" hint="Shown next to the model; variants of one model are compared for policy sensitivity.">
              <input value={m.variant} onChange={(e) => onChange({ variant: e.target.value })} placeholder="e.g. tuned policy" className={inputCls} />
            </Field>
          </div>

          {(m.kind === "decision" || m.kind === "llm") && (
            <PolicyEditor m={m} labels={labels} task={task} onChange={onChange} />
          )}
          {m.kind === "llm" && <PromptEditor m={m} defaults={defaultPrompts} onChange={onChange} />}
          {m.kind !== "rules" && (
            <LabelMapEditor
              m={m}
              labels={labels}
              title={m.kind === "classifier" ? "Label map" : "Answer aliases"}
              hint={
                m.kind === "classifier"
                  ? "Native classifier label → dataset label (e.g. INJECTION → prompt_injection). Labels already equal to a dataset label (any case) need no row."
                  : "Extra answers accepted as a label, e.g. a safety model's “unsafe” → jailbreak."
              }
              onChange={onChange}
            />
          )}
          {m.kind === "classifier" && (
            <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
              <Field label="Threshold" hint="Below this top score the model answers the fallback label.">
                <input
                  type="number"
                  min={0}
                  max={1}
                  step={0.05}
                  value={m.threshold}
                  onChange={(e) => onChange({ threshold: e.target.value })}
                  placeholder="none"
                  className={inputCls}
                />
              </Field>
              <Field label="Fallback label" hint="Used below the threshold and when a detector finds nothing.">
                <LabelSelect labels={labels} value={m.fallback_label} onChange={(v) => onChange({ fallback_label: v })} allowEmpty />
              </Field>
            </div>
          )}
          {m.kind === "rules" && <RulesEditor m={m} labels={labels} onChange={onChange} />}
          {m.kind !== "rules" && <DeploymentEditor m={m} onChange={onChange} />}
        </div>
      )}
    </div>
  );
}

function summarize(m: SelectedModel): string {
  const parts: string[] = [];
  if (m.task.trim()) parts.push("custom task");
  if (Object.values(m.label_descriptions).some((v) => v.trim())) parts.push("custom label definitions");
  if (m.system_prompt.trim() || m.user_prompt.trim()) parts.push("custom prompt");
  if (m.label_map.some((r) => r.from.trim() && r.to)) parts.push(m.kind === "classifier" ? "label map" : "aliases");
  if (m.threshold.trim()) parts.push(`threshold ${m.threshold}`);
  if (m.deployment.hardware.trim()) parts.push(m.deployment.hardware.trim());
  return parts.join(" · ");
}

function Field({ label, hint, children }: { label: string; hint?: string; children: React.ReactNode }) {
  return (
    <label className="block">
      <span className="block text-[11px] font-medium text-t-hover mb-1">{label}</span>
      {children}
      {hint && <span className="block text-[10px] text-muted mt-1">{hint}</span>}
    </label>
  );
}

function LabelSelect({
  labels,
  value,
  onChange,
  allowEmpty,
}: {
  labels: any[];
  value: string;
  onChange: (v: string) => void;
  allowEmpty?: boolean;
}) {
  return (
    <select value={value} onChange={(e) => onChange(e.target.value)} className={inputCls}>
      {allowEmpty && <option value="">— none —</option>}
      {labels.map((l) => (
        <option key={l.name} value={l.name}>
          {l.name}
        </option>
      ))}
    </select>
  );
}

function PolicyEditor({
  m,
  labels,
  task,
  onChange,
}: {
  m: SelectedModel;
  labels: any[];
  task: string;
  onChange: (patch: Partial<SelectedModel>) => void;
}) {
  return (
    <div className="space-y-2">
      <p className="text-[11px] font-semibold text-primary uppercase tracking-wider">Policy</p>
      <p className="text-[10px] text-muted -mt-1">
        The question and risk definitions this model sees. Leave empty to use the dataset&apos;s — wording alone can move accuracy by
        double digits.
      </p>
      <Field label="Task / instructions">
        <textarea value={m.task} onChange={(e) => onChange({ task: e.target.value })} placeholder={task} rows={2} className={inputCls} />
      </Field>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
        {labels.map((l) => (
          <Field key={l.name} label={l.name}>
            <textarea
              value={m.label_descriptions[l.name] || ""}
              onChange={(e) => onChange({ label_descriptions: { ...m.label_descriptions, [l.name]: e.target.value } })}
              placeholder={l.description || "(no description)"}
              rows={2}
              className={inputCls}
            />
          </Field>
        ))}
      </div>
    </div>
  );
}

function PromptEditor({
  m,
  defaults,
  onChange,
}: {
  m: SelectedModel;
  defaults?: { system: string; user: string };
  onChange: (patch: Partial<SelectedModel>) => void;
}) {
  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <p className="text-[11px] font-semibold text-primary uppercase tracking-wider">Prompt template</p>
        {defaults && !m.system_prompt && (
          <button
            onClick={() => onChange({ system_prompt: defaults.system, user_prompt: defaults.user })}
            className="text-[11px] text-accent hover:underline"
          >
            Start from the default prompt
          </button>
        )}
      </div>
      <p className="text-[10px] text-muted -mt-1">
        Placeholders: <code>{"{task}"}</code> <code>{"{labels}"}</code> <code>{"{label_names}"}</code> <code>{"{text}"}</code>. The
        answer must name a label (or an alias below).
      </p>
      <Field label="System prompt">
        <textarea
          value={m.system_prompt}
          onChange={(e) => onChange({ system_prompt: e.target.value })}
          placeholder={defaults?.system || "Built-in classification prompt"}
          rows={5}
          className={cn(inputCls, "font-mono")}
        />
      </Field>
      <Field label="User message">
        <textarea
          value={m.user_prompt}
          onChange={(e) => onChange({ user_prompt: e.target.value })}
          placeholder={defaults?.user || "Text to classify: {text}"}
          rows={2}
          className={cn(inputCls, "font-mono")}
        />
      </Field>
    </div>
  );
}

function LabelMapEditor({
  m,
  labels,
  title,
  hint,
  onChange,
}: {
  m: SelectedModel;
  labels: any[];
  title: string;
  hint: string;
  onChange: (patch: Partial<SelectedModel>) => void;
}) {
  const rows = m.label_map;
  const set = (next: LabelMapRow[]) => onChange({ label_map: next });
  return (
    <div className="space-y-1.5">
      <p className="text-[11px] font-semibold text-primary uppercase tracking-wider">{title}</p>
      <p className="text-[10px] text-muted -mt-0.5">{hint}</p>
      {rows.map((r, i) => (
        <div key={i} className="flex items-center gap-2">
          <input
            value={r.from}
            onChange={(e) => set(rows.map((x, j) => (j === i ? { ...x, from: e.target.value } : x)))}
            placeholder={m.kind === "classifier" ? "INJECTION" : "unsafe"}
            className={cn(inputCls, "max-w-[200px] font-mono")}
          />
          <span className="text-muted text-xs">→</span>
          <div className="max-w-[200px] w-full">
            <LabelSelect labels={labels} value={r.to} onChange={(v) => set(rows.map((x, j) => (j === i ? { ...x, to: v } : x)))} allowEmpty />
          </div>
          <button onClick={() => set(rows.filter((_, j) => j !== i))} className="p-1 rounded-md hover:bg-surface-200/60" aria-label="Remove mapping">
            <X className="w-3 h-3 text-muted" />
          </button>
        </div>
      ))}
      <button onClick={() => set([...rows, { from: "", to: "" }])} className="text-[11px] text-accent hover:underline">
        + Add mapping
      </button>
    </div>
  );
}

function RulesEditor({
  m,
  labels,
  onChange,
}: {
  m: SelectedModel;
  labels: any[];
  onChange: (patch: Partial<SelectedModel>) => void;
}) {
  return (
    <div className="space-y-2">
      <p className="text-[11px] font-semibold text-primary uppercase tracking-wider">Rules</p>
      <p className="text-[10px] text-muted -mt-1">
        One regular expression per line. Labels are checked top to bottom; the first match wins, otherwise the default label.
      </p>
      <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
        <Field label="Default label (no match)">
          <LabelSelect labels={labels} value={m.default_label} onChange={(v) => onChange({ default_label: v })} />
        </Field>
        <label className="flex items-center gap-2 text-[11px] text-t-hover mt-5">
          <input
            type="checkbox"
            checked={m.case_sensitive}
            onChange={(e) => onChange({ case_sensitive: e.target.checked })}
            className="w-3.5 h-3.5 accent-accent"
          />
          Case-sensitive
        </label>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
        {labels
          .filter((l) => l.name !== m.default_label)
          .map((l) => (
            <Field key={l.name} label={l.name}>
              <textarea
                value={m.rules[l.name] || ""}
                onChange={(e) => onChange({ rules: { ...m.rules, [l.name]: e.target.value } })}
                placeholder="one pattern per line"
                rows={3}
                className={cn(inputCls, "font-mono")}
              />
            </Field>
          ))}
      </div>
    </div>
  );
}

function DeploymentEditor({ m, onChange }: { m: SelectedModel; onChange: (patch: Partial<SelectedModel>) => void }) {
  const setDep = (field: keyof SelectedModel["deployment"], value: string) =>
    onChange({ deployment: { ...m.deployment, [field]: value } });
  return (
    <div className="space-y-2">
      <p className="text-[11px] font-semibold text-primary uppercase tracking-wider">Deployment & hardware cost</p>
      <p className="text-[10px] text-muted -mt-1">
        Latency is only comparable with the hardware next to it. A $/hour is charged for the time this model keeps the
        hardware busy during the run.
      </p>
      <div className="grid grid-cols-2 md:grid-cols-5 gap-2">
        <Field label="Hardware">
          <input value={m.deployment.hardware} onChange={(e) => setDep("hardware", e.target.value)} placeholder="CPU — M1 laptop" className={inputCls} />
        </Field>
        <Field label="Parameters">
          <input value={m.deployment.parameters} onChange={(e) => setDep("parameters", e.target.value)} placeholder="184M" className={inputCls} />
        </Field>
        <Field label="Serving">
          <input value={m.deployment.serving} onChange={(e) => setDep("serving", e.target.value)} placeholder="vLLM, TEI, API" className={inputCls} />
        </Field>
        <Field label="Region">
          <input value={m.deployment.region} onChange={(e) => setDep("region", e.target.value)} placeholder="us-east-1" className={inputCls} />
        </Field>
        <Field label="Hardware $/hour">
          <input
            type="number"
            min={0}
            step="0.01"
            value={m.infra_cost}
            onChange={(e) => onChange({ infra_cost: e.target.value })}
            placeholder="0.00"
            className={inputCls}
          />
        </Field>
      </div>
    </div>
  );
}

/* ═══════════════════════════ Small pieces ═══════════════════════════ */

function Chip({ active, onClick, children }: { active: boolean; onClick: () => void; children: React.ReactNode }) {
  return (
    <button
      onClick={onClick}
      className={cn(
        "px-2.5 py-1 rounded-lg text-xs border transition-colors",
        active
          ? "bg-accent/20 border-accent text-accent"
          : "bg-surface-50 border-visible text-t-hover hover:text-primary hover:border-accent/50"
      )}
    >
      {children}
    </button>
  );
}

function PriceInput({ label, value, onChange }: { label: string; value: string; onChange: (v: string) => void }) {
  return (
    <label className="flex items-center gap-1.5 text-[11px] text-muted">
      {label}
      <span className="relative">
        <span className="absolute left-2 top-1/2 -translate-y-1/2 text-muted">$</span>
        <input
          type="number"
          min={0}
          step="0.001"
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder="?"
          className="w-24 pl-5 pr-2 py-1 bg-surface-50 border border-visible rounded-md text-primary text-xs tabular-nums focus:outline-none focus:border-accent/50"
        />
      </span>
    </label>
  );
}

function ModelPicker({
  title,
  icon: Icon,
  hint,
  models,
  selected,
  onToggle,
  empty,
}: {
  title: string;
  icon: any;
  hint: string;
  models: any[];
  selected: SelectedModel[];
  onToggle: (m: any) => void;
  empty: React.ReactNode;
}) {
  const full = selected.length >= MAX_MODELS;
  return (
    <div>
      <div className="flex items-center gap-2 mb-1">
        <Icon className="w-3.5 h-3.5 text-t-secondary" />
        <span className="text-xs font-semibold text-primary uppercase tracking-wider">{title}</span>
      </div>
      <p className="text-[11px] text-muted mb-2">{hint}</p>
      {models.length === 0 ? (
        empty
      ) : (
        <div className="flex flex-wrap gap-2">
          {models.map((m) => {
            const count = selected.filter((s) => baseKey(s) === baseKey(m)).length;
            const isSelected = count > 0;
            return (
              <button
                key={baseKey(m)}
                onClick={() => onToggle(m)}
                disabled={!isSelected && full}
                className={cn(
                  "px-3 py-1.5 rounded-lg text-sm border transition-colors disabled:opacity-40",
                  isSelected
                    ? "bg-accent/20 border-accent text-accent"
                    : "bg-surface-50 border-visible text-t-hover hover:text-primary hover:border-accent/50"
                )}
              >
                {isSelected ? <Check className="w-3 h-3 inline mr-1" /> : <Plus className="w-3 h-3 inline mr-1 opacity-60" />}
                {m.label ?? m.model}
                <span className="text-xs text-muted ml-1">({m.provider_name})</span>
                {count > 1 && <span className="text-[10px] ml-1">×{count}</span>}
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}

function EmptyProviders({ onOpenSettings, onAddRules }: { onOpenSettings: () => void; onAddRules: () => void }) {
  return (
    <div className="text-center py-8">
      <Scale className="w-10 h-10 text-muted mx-auto mb-3" />
      <p className="text-sm text-primary font-medium">No models available yet</p>
      <p className="text-xs text-t-secondary mt-1 max-w-md mx-auto">
        Add a decision-model provider (TypeSafe Jev or OpenAI&apos;s Decisions API), a text classifier and at least one LLM
        provider in Settings → Providers — or start with a regex baseline, which needs no provider.
      </p>
      <div className="mt-4 flex justify-center gap-2">
        <button
          onClick={onOpenSettings}
          className="inline-flex items-center gap-2 px-4 py-2 bg-accent text-accent-foreground rounded-lg text-sm font-medium hover:bg-accent/90"
        >
          <Settings className="w-4 h-4" /> Open Providers
        </button>
        <button
          onClick={onAddRules}
          className="inline-flex items-center gap-2 px-4 py-2 border border-visible rounded-lg text-sm text-primary hover:bg-surface-200/50"
        >
          <Regex className="w-4 h-4" /> Add regex baseline
        </button>
      </div>
    </div>
  );
}
