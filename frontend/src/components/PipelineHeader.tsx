"use client";

import { cn } from "@/lib/utils";

interface Step {
  id: string;
  label: string;
  icon: string;
  description: string;
}

interface PipelineHeaderProps {
  steps: readonly Step[];
  currentStep: string;
  completedSteps: Set<string>;
}

export default function PipelineHeader({
  steps,
  currentStep,
  completedSteps,
}: PipelineHeaderProps) {
  const currentIndex = steps.findIndex((s) => s.id === currentStep);
  const step = steps[currentIndex];

  return (
    <header className="sticky top-0 z-10 border-b border-themed bg-surface-100/85 backdrop-blur-md">
      <div className="px-8 pt-6 pb-5 max-w-6xl mx-auto">
        <span className="inline-flex items-center h-[22px] px-2 mb-2 rounded-full border border-themed bg-surface-50 text-xs font-medium tabular-nums text-t-secondary">
          Step {currentIndex + 1} of {steps.length}
        </span>
        <h2 className="text-2xl font-semibold text-primary leading-tight">{step?.label}</h2>
        {step?.description && (
          <p className="text-sm text-t-secondary mt-1.5 max-w-2xl text-pretty">{step.description}</p>
        )}

        {/* Segmented progress — one bar per step */}
        <ol className="mt-5 grid gap-1.5" style={{ gridTemplateColumns: `repeat(${steps.length}, minmax(0, 1fr))` }}>
          {steps.map((s, i) => {
            const isCurrent = s.id === currentStep;
            const isDone = completedSteps.has(s.id);
            return (
              <li key={s.id} title={s.label} aria-current={isCurrent ? "step" : undefined}>
                <div
                  className={cn(
                    "h-1 rounded-full transition-colors duration-[480ms]",
                    isCurrent ? "bg-accent" : isDone ? "bg-success/70" : "bg-surface-200"
                  )}
                />
                <span
                  className={cn(
                    "mt-1.5 block truncate text-[11px] transition-colors",
                    isCurrent ? "text-primary font-medium" : i < currentIndex || isDone ? "text-t-secondary" : "text-muted"
                  )}
                >
                  {s.label}
                </span>
              </li>
            );
          })}
        </ol>
      </div>
    </header>
  );
}
