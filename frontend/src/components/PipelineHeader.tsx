"use client";

interface Step {
  id: string;
  label: string;
  icon: string;
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
    <header className="border-b border-surface-200/50 bg-surface-50/80 backdrop-blur-sm sticky top-0 z-10">
      <div className="px-6 py-4 max-w-6xl mx-auto">
        <div className="flex items-center justify-between">
          <div>
            <div className="flex items-center gap-2 text-xs text-muted mb-1">
              <span>Step {currentIndex + 1} of {steps.length}</span>
              <span className="text-surface-300">|</span>
              <span className="text-accent">{step?.label}</span>
            </div>
            <h2 className="text-xl font-semibold text-primary">{step?.label}</h2>
          </div>
          <div className="flex items-center gap-2">
            {steps.map((s, i) => (
              <div
                key={s.id}
                className={`w-2 h-2 rounded-full transition-colors ${
                  s.id === currentStep
                    ? "bg-accent"
                    : completedSteps.has(s.id)
                    ? "bg-emerald-500"
                    : "bg-surface-300"
                }`}
              />
            ))}
          </div>
        </div>
      </div>
    </header>
  );
}
