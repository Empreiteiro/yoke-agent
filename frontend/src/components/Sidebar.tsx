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
  Clock,
  FileText,
  Sun,
  Moon,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { useTheme, Theme } from "@/contexts/ThemeContext";

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
  showHistory?: boolean;
  onHistoryClick?: () => void;
  showLogs?: boolean;
  onLogsClick?: () => void;
}

const themes: { key: Theme; icon: any; label: string }[] = [
  { key: "light", icon: Sun, label: "Light" },
  { key: "dark", icon: Moon, label: "Dark" },
  { key: "neon", icon: Zap, label: "Neon" },
];

export default function Sidebar({
  steps,
  currentStep,
  completedSteps,
  onStepClick,
  showSettings = false,
  onSettingsClick,
  showHistory = false,
  onHistoryClick,
  showLogs = false,
  onLogsClick,
}: SidebarProps) {
  const { theme, setTheme } = useTheme();
  const isAnySpecialView = showSettings || showHistory || showLogs;

  return (
    <aside className="w-60 bg-surface-50 flex flex-col h-screen">
      <div className="px-4 py-4">
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-accent to-secondary flex items-center justify-center">
            <Zap className="w-4 h-4 text-white" />
          </div>
          <div>
            <h1 className="text-sm font-bold text-primary leading-tight">RAG Pipeline</h1>
            <p className="text-[10px] text-t-secondary">Optimization Studio</p>
          </div>
        </div>
      </div>

      {/* Progress bar at top */}
      <div className="px-4 pb-3">
        <div className="flex items-center justify-between text-[10px] text-t-secondary mb-1.5">
          <span>Progress</span>
          <span>
            {completedSteps.size}/{steps.length}
          </span>
        </div>
        <div className="w-full h-1 bg-surface-200 rounded-full overflow-hidden">
          <div
            className="h-full bg-gradient-to-r from-accent to-secondary rounded-full transition-all duration-500"
            style={{
              width: `${(completedSteps.size / steps.length) * 100}%`,
            }}
          />
        </div>
      </div>

      <nav className="flex-1 px-3 space-y-0.5 overflow-y-auto">
        {steps.map((step) => {
          const Icon = iconMap[step.icon] || Database;
          const isActive = currentStep === step.id && !isAnySpecialView;
          const isCompleted = completedSteps.has(step.id);

          return (
            <button
              key={step.id}
              onClick={() => onStepClick(step.id)}
              className={cn(
                "w-full flex items-center gap-2.5 px-3 py-2 rounded-lg text-xs font-medium transition-all duration-200",
                isActive
                  ? "bg-accent/10 text-accent border border-accent/20"
                  : isCompleted
                  ? "text-emerald-400 hover:bg-surface-100"
                  : "text-t-secondary hover:bg-surface-100 hover:text-t-hover"
              )}
            >
              <div
                className={cn(
                  "w-6 h-6 rounded-md flex items-center justify-center flex-shrink-0",
                  isActive
                    ? "bg-accent/20 text-accent"
                    : isCompleted
                    ? "bg-emerald-500/20 text-emerald-400"
                    : "bg-surface-200 text-muted"
                )}
              >
                {isCompleted ? (
                  <CheckCircle className="w-3.5 h-3.5" />
                ) : (
                  <Icon className="w-3.5 h-3.5" />
                )}
              </div>
              <span className="truncate">{step.label}</span>
            </button>
          );
        })}

        {/* History, Logs, Providers - no divider */}
        <div className="pt-2 space-y-0.5">
          <button
            onClick={onHistoryClick}
            className={cn(
              "w-full flex items-center gap-2.5 px-3 py-2 rounded-lg text-xs font-medium transition-all duration-200",
              showHistory
                ? "bg-accent/10 text-accent border border-accent/20"
                : "text-t-secondary hover:bg-surface-100 hover:text-t-hover"
            )}
          >
            <div
              className={cn(
                "w-6 h-6 rounded-md flex items-center justify-center flex-shrink-0",
                showHistory
                  ? "bg-accent/20 text-accent"
                  : "bg-surface-200 text-muted"
              )}
            >
              <Clock className="w-3.5 h-3.5" />
            </div>
            <span>History</span>
          </button>

          <button
            onClick={onLogsClick}
            className={cn(
              "w-full flex items-center gap-2.5 px-3 py-2 rounded-lg text-xs font-medium transition-all duration-200",
              showLogs
                ? "bg-accent/10 text-accent border border-accent/20"
                : "text-t-secondary hover:bg-surface-100 hover:text-t-hover"
            )}
          >
            <div
              className={cn(
                "w-6 h-6 rounded-md flex items-center justify-center flex-shrink-0",
                showLogs
                  ? "bg-accent/20 text-accent"
                  : "bg-surface-200 text-muted"
              )}
            >
              <FileText className="w-3.5 h-3.5" />
            </div>
            <span>Logs</span>
          </button>

          <button
            onClick={onSettingsClick}
            className={cn(
              "w-full flex items-center gap-2.5 px-3 py-2 rounded-lg text-xs font-medium transition-all duration-200",
              showSettings
                ? "bg-accent/10 text-accent border border-accent/20"
                : "text-t-secondary hover:bg-surface-100 hover:text-t-hover"
            )}
          >
            <div
              className={cn(
                "w-6 h-6 rounded-md flex items-center justify-center flex-shrink-0",
                showSettings
                  ? "bg-accent/20 text-accent"
                  : "bg-surface-200 text-muted"
              )}
            >
              <Settings className="w-3.5 h-3.5" />
            </div>
            <span>Providers</span>
          </button>
        </div>
      </nav>

      {/* Theme toggle at bottom */}
      <div className="px-3 py-3">
        <div className="flex items-center gap-1 px-1.5 py-1 bg-surface-100 rounded-lg border border-surface-200/50">
          {themes.map(({ key, icon: ThemeIcon, label }) => (
            <button
              key={key}
              onClick={() => setTheme(key)}
              className={cn(
                "flex-1 flex items-center justify-center gap-1 px-1.5 py-1.5 rounded-md text-[10px] font-medium transition-all duration-200",
                theme === key
                  ? "bg-accent/15 text-accent shadow-sm"
                  : "text-muted hover:text-t-secondary hover:bg-surface-200/50"
              )}
              title={label}
            >
              <ThemeIcon className="w-3 h-3" />
              <span className="hidden sm:inline">{label}</span>
            </button>
          ))}
        </div>
      </div>
    </aside>
  );
}
