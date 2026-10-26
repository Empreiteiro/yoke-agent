"use client";

import { cn } from "@/lib/utils";

interface Step {
  id: string;
  label: string;
  icon: string;
  description: string;
}

interface PipelineHeaderProps {
  step: Step | undefined;
  // Steps of the active pipeline. A step outside this list (the AI
  // Assistant) is not part of the process, so it gets no counter or progress.
  steps: readonly Step[];
  currentStep: string;
  completedSteps: Set<string>;
}

export default function PipelineHeader({
  step,
  steps,
  currentStep,
  completedSteps,
}: PipelineHeaderProps) {
  const currentIndex = steps.findIndex((s) => s.id === currentStep);
  const isPipelineStep = currentIndex !== -1;

  return (
    <header className="sticky top-0 z-10 border-b border-themed bg-surface-100/85 backdrop-blur-md">
      <div className="px-8 pt-9 pb-7 max-w-6xl mx-auto">
        {isPipelineStep && (
          <span className="inline-flex items-center h-[22px] px-2 mb-2.5 rounded-full border border-themed bg-surface-50 text-xs font-medium tabular-nums text-t-secondary">
            Step {currentIndex + 1} of {steps.length}
          </span>
        )}
        <h2 className="text-[26px] font-semibold text-primary leading-tight">{step?.label}</h2>
        {step?.description && (
          <p className="text-sm text-t-secondary mt-2 max-w-2xl text-pretty">{step.description}</p>
        )}

        {/* Segmented progress — one bar per step */}
        {isPipelineStep && (
          <ol className="mt-6 grid gap-1.5" style={{ gridTemplateColumns: `repeat(${steps.length}, minmax(0, 1fr))` }}>
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
        )}
      </div>
    </header>
  );
}
