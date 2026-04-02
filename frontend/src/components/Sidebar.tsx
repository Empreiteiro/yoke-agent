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
  BookOpen,
  MessageSquare,
  Sun,
  Moon,
  Cable,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { useTheme, Theme } from "@/contexts/ThemeContext";
import Logo from "@/components/Logo";

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
  currentView: string | null;
  completedSteps: Set<string>;
  onNavigate: (params: string) => void;
  isStepAccessible?: (id: string) => boolean;
}

const themes: { key: Theme; icon: any; label: string }[] = [
  { key: "light", icon: Sun, label: "Light" },
  { key: "dark", icon: Moon, label: "Dark" },
  { key: "neon", icon: Zap, label: "Neon" },
];

const UTILITY_ITEMS = [
  { id: "history", label: "History", icon: Clock },
  { id: "collections", label: "Collections", icon: MessageSquare },
  { id: "logs", label: "Logs", icon: FileText },
  { id: "glossary", label: "Concepts", icon: BookOpen },
  { id: "vectorstores", label: "Vector Stores", icon: Database },
  { id: "settings", label: "Providers", icon: Settings },
  { id: "mcp", label: "MCP Server", icon: Cable },
];

export default function Sidebar({
  steps,
  currentStep,
  currentView,
  completedSteps,
  onNavigate,
  isStepAccessible,
}: SidebarProps) {
  const { theme, setTheme } = useTheme();
  const isAnySpecialView = currentView !== null;

  return (
    <aside className="w-60 bg-surface-50 flex flex-col h-screen">
      <div className="px-4 py-4">
        <div className="flex items-center gap-2.5" data-walkthrough="sidebar-welcome">
          <Logo size={32} />
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

      <nav className="flex-1 px-3 space-y-0.5 overflow-y-auto" data-walkthrough="sidebar-steps">
        {steps.map((step) => {
          const Icon = iconMap[step.icon] || Database;
          const isActive = currentStep === step.id && !isAnySpecialView;
          const isCompleted = completedSteps.has(step.id);
          const accessible = isStepAccessible ? isStepAccessible(step.id) : true;
          const isLocked = !accessible && !isCompleted;

          return (
            <button
              key={step.id}
              onClick={() => onNavigate(`/?step=${step.id}`)}
              disabled={isLocked}
              className={cn(
                "w-full flex items-center gap-2.5 px-3 py-2 rounded-lg text-xs font-medium transition-all duration-200",
                isLocked
                  ? "text-muted cursor-not-allowed opacity-50"
                  : isActive
                  ? "bg-accent/10 text-accent"
                  : isCompleted
                  ? "text-emerald-400 hover:bg-surface-100"
                  : "text-t-secondary hover:bg-surface-100 hover:text-t-hover"
              )}
            >
              <div
                className={cn(
                  "w-6 h-6 rounded-md flex items-center justify-center flex-shrink-0",
                  isLocked
                    ? "bg-surface-200/50 text-muted"
                    : isActive
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

        {/* Separator */}
        <div className="!my-3 mx-2 border-t border-surface-200/40" />

        {/* Utility pages - always accessible */}
        <div className="space-y-0.5" data-walkthrough="sidebar-history">
          {UTILITY_ITEMS.map((item) => {
            const ItemIcon = item.icon;
            const isActive = currentView === item.id;
            return (
              <button
                key={item.id}
                onClick={() => onNavigate(`/?view=${item.id}`)}
                {...(item.id === "settings" ? { "data-walkthrough": "sidebar-settings" } : {})}
                className={cn(
                  "w-full flex items-center gap-2.5 px-3 py-2 rounded-lg text-xs font-medium transition-all duration-200",
                  isActive
                    ? "bg-accent/10 text-accent"
                    : "text-t-secondary hover:bg-surface-100 hover:text-t-hover"
                )}
              >
                <div
                  className={cn(
                    "w-6 h-6 rounded-md flex items-center justify-center flex-shrink-0",
                    isActive
                      ? "bg-accent/20 text-accent"
                      : "bg-surface-200 text-muted"
                  )}
                >
                  <ItemIcon className="w-3.5 h-3.5" />
                </div>
                <span>{item.label}</span>
              </button>
            );
          })}
        </div>
      </nav>

      {/* Theme toggle at bottom */}
      <div className="px-3 py-3" data-walkthrough="sidebar-theme">
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
