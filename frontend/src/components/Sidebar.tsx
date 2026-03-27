"use client";

import {
  Upload,
  Database,
  CheckCircle,
  Grid3X3,
  Play,
  BarChart3,
  Zap,
  Settings,
} from "lucide-react";
import { cn } from "@/lib/utils";

const iconMap: Record<string, any> = {
  upload: Upload,
  database: Database,
  "check-circle": CheckCircle,
  grid: Grid3X3,
  play: Play,
  "bar-chart": BarChart3,
};

interface Step {
  id: string;
  label: string;
  icon: string;
}

interface SidebarProps {
  steps: readonly Step[];
  currentStep: string;
  completedSteps: Set<string>;
  onStepClick: (id: string) => void;
  showSettings?: boolean;
  onSettingsClick?: () => void;
}

export default function Sidebar({
  steps,
  currentStep,
  completedSteps,
  onStepClick,
  showSettings = false,
  onSettingsClick,
}: SidebarProps) {
  return (
    <aside className="w-72 bg-surface-50 border-r border-surface-200/50 flex flex-col">
      <div className="p-6 border-b border-surface-200/50">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-accent to-secondary flex items-center justify-center">
            <Zap className="w-5 h-5 text-white" />
          </div>
          <div>
            <h1 className="text-lg font-bold text-white">RAG Pipeline</h1>
            <p className="text-xs text-slate-400">Optimization Studio</p>
          </div>
        </div>
      </div>

      <nav className="flex-1 p-4 space-y-1">
        {steps.map((step) => {
          const Icon = iconMap[step.icon] || Database;
          const isActive = currentStep === step.id && !showSettings;
          const isCompleted = completedSteps.has(step.id);

          return (
            <button
              key={step.id}
              onClick={() => onStepClick(step.id)}
              className={cn(
                "w-full flex items-center gap-3 px-4 py-3 rounded-xl text-sm font-medium transition-all duration-200",
                isActive
                  ? "bg-accent/10 text-accent border border-accent/20"
                  : isCompleted
                  ? "text-emerald-400 hover:bg-surface-100"
                  : "text-slate-400 hover:bg-surface-100 hover:text-slate-300"
              )}
            >
              <div
                className={cn(
                  "w-8 h-8 rounded-lg flex items-center justify-center text-xs font-bold",
                  isActive
                    ? "bg-accent/20 text-accent"
                    : isCompleted
                    ? "bg-emerald-500/20 text-emerald-400"
                    : "bg-surface-200 text-slate-500"
                )}
              >
                {isCompleted ? (
                  <CheckCircle className="w-4 h-4" />
                ) : (
                  <Icon className="w-4 h-4" />
                )}
              </div>
              <span>{step.label}</span>
            </button>
          );
        })}
      </nav>

      {/* Settings button */}
      <div className="p-4 space-y-3 border-t border-surface-200/50">
        <button
          onClick={onSettingsClick}
          className={cn(
            "w-full flex items-center gap-3 px-4 py-3 rounded-xl text-sm font-medium transition-all duration-200",
            showSettings
              ? "bg-accent/10 text-accent border border-accent/20"
              : "text-slate-400 hover:bg-surface-100 hover:text-slate-300"
          )}
        >
          <div
            className={cn(
              "w-8 h-8 rounded-lg flex items-center justify-center",
              showSettings
                ? "bg-accent/20 text-accent"
                : "bg-surface-200 text-slate-500"
            )}
          >
            <Settings className="w-4 h-4" />
          </div>
          <span>Providers</span>
        </button>

        <div className="px-4 py-3 rounded-xl bg-surface-100 border border-surface-200/50">
          <div className="flex items-center justify-between text-xs text-slate-400 mb-2">
            <span>Progress</span>
            <span>
              {completedSteps.size}/{steps.length}
            </span>
          </div>
          <div className="w-full h-1.5 bg-surface-200 rounded-full overflow-hidden">
            <div
              className="h-full bg-gradient-to-r from-accent to-secondary rounded-full transition-all duration-500"
              style={{
                width: `${(completedSteps.size / steps.length) * 100}%`,
              }}
            />
          </div>
        </div>
      </div>
    </aside>
  );
}
