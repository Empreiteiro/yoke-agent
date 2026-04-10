"use client";

import { useState, useEffect } from "react";
import {
  Upload,
  Database,
  CheckCircle,
  Grid3X3,
  Play,
  BarChart3,
  Bot,
  Settings,
  Clock,
  FileText,
  BookOpen,
  MessageSquare,
  Cable,
  FlaskConical,
  Users,
  ChevronDown,
  ChevronRight,
  Archive,
  Search,
  FlaskRound,
  User,
} from "lucide-react";
import { cn } from "@/lib/utils";
import Logo from "@/components/Logo";

const iconMap: Record<string, any> = {
  bot: Bot,
  upload: Upload,
  database: Database,
  "check-circle": CheckCircle,
  grid: Grid3X3,
  play: Play,
  "bar-chart": BarChart3,
  "flask-conical": FlaskConical,
  users: Users,
};

interface Step {
  id: string;
  label: string;
  icon: string;
}

interface SidebarProps {
  steps: readonly Step[];
  ragSteps: readonly Step[];
  agentSteps: readonly Step[];
  chatStep: Step;
  currentStep: string;
  currentView: string | null;
  completedSteps: Set<string>;
  onNavigate: (params: string) => void;
  isStepAccessible?: (id: string) => boolean;
  currentPipeline: "rag" | "agent";
}

const HISTORY_ITEMS = [
  { id: "logs", label: "Logs", icon: FileText },
  { id: "history", label: "Results", icon: Clock },
  { id: "collections", label: "Collections", icon: MessageSquare },
];

const SETTINGS_ITEMS = [
  { id: "settings", label: "Providers", icon: Settings },
  { id: "vectorstores", label: "Vector Stores", icon: Database },
  { id: "mcp", label: "MCP Server", icon: Cable },
  { id: "glossary", label: "Concepts", icon: BookOpen },
  { id: "user-settings", label: "User", icon: User },
];

// ── Reusable: render a single step button ────────────────────────────

function StepButton({
  step,
  isActive,
  isCompleted,
  isLocked,
  pipelineParam,
  onNavigate,
}: {
  step: Step;
  isActive: boolean;
  isCompleted: boolean;
  isLocked: boolean;
  pipelineParam: string;
  onNavigate: (path: string) => void;
}) {
  const Icon = iconMap[step.icon] || Database;
  return (
    <button
      onClick={() => onNavigate(`/?${pipelineParam}step=${step.id}`)}
      disabled={isLocked}
      className={cn(
        "w-full flex items-center gap-2.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-all duration-200",
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
          "w-5 h-5 rounded flex items-center justify-center flex-shrink-0",
          isLocked
            ? "bg-surface-200/50 text-muted"
            : isActive
            ? "bg-accent/20 text-accent"
            : isCompleted
            ? "bg-emerald-500/20 text-emerald-400"
            : "bg-surface-200 text-muted"
        )}
      >
        {isCompleted ? <CheckCircle className="w-3 h-3" /> : <Icon className="w-3 h-3" />}
      </div>
      <span className="truncate">{step.label}</span>
    </button>
  );
}

// ── Reusable: collapsible group with sub-items (for views) ───────────

function CollapsibleViewGroup({
  label,
  icon: GroupIcon,
  items,
  isOpen,
  onToggle,
  isGroupActive,
  currentView,
  onNavigate,
}: {
  label: string;
  icon: any;
  items: { id: string; label: string; icon: any }[];
  isOpen: boolean;
  onToggle: () => void;
  isGroupActive: boolean;
  currentView: string | null;
  onNavigate: (path: string) => void;
}) {
  return (
    <div className="space-y-0.5">
      <button
        onClick={onToggle}
        className={cn(
          "w-full flex items-center gap-2.5 px-3 py-2 rounded-lg text-xs font-medium transition-all duration-200",
          isGroupActive
            ? "bg-accent/10 text-accent"
            : "text-t-secondary hover:bg-surface-100 hover:text-t-hover"
        )}
      >
        <div
          className={cn(
            "w-6 h-6 rounded-md flex items-center justify-center flex-shrink-0",
            isGroupActive ? "bg-accent/20 text-accent" : "bg-surface-200 text-muted"
          )}
        >
          <GroupIcon className="w-3.5 h-3.5" />
        </div>
        <span className="flex-1 text-left">{label}</span>
        {isOpen ? <ChevronDown className="w-3 h-3 text-muted" /> : <ChevronRight className="w-3 h-3 text-muted" />}
      </button>
      {isOpen && (
        <div className="ml-4 space-y-0.5">
          {items.map((item) => {
            const ItemIcon = item.icon;
            const isActive = currentView === item.id;
            return (
              <button
                key={item.id}
                onClick={() => onNavigate(`/?view=${item.id}`)}
                className={cn(
                  "w-full flex items-center gap-2.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-all duration-200",
                  isActive
                    ? "bg-accent/10 text-accent"
                    : "text-t-secondary hover:bg-surface-100 hover:text-t-hover"
                )}
              >
                <div
                  className={cn(
                    "w-5 h-5 rounded flex items-center justify-center flex-shrink-0",
                    isActive ? "bg-accent/20 text-accent" : "bg-surface-200 text-muted"
                  )}
                >
                  <ItemIcon className="w-3 h-3" />
                </div>
                <span>{item.label}</span>
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}

// ══════════════════════════════════════════════════════════════════════

export default function Sidebar({
  steps,
  ragSteps,
  agentSteps,
  chatStep,
  currentStep,
  currentView,
  completedSteps,
  onNavigate,
  isStepAccessible,
  currentPipeline,
}: SidebarProps) {
  const isAnySpecialView = currentView !== null;
  const isSettingsView = SETTINGS_ITEMS.some((item) => item.id === currentView);
  const isHistoryView = HISTORY_ITEMS.some((item) => item.id === currentView);

  // Determine which pipeline group is active based on current step
  const ragStepIds = new Set(ragSteps.map((s) => s.id));
  const agentStepIds = new Set(agentSteps.map((s) => s.id));
  const isRagActive = ragStepIds.has(currentStep) && !isAnySpecialView;
  const isAgentActive = agentStepIds.has(currentStep) && !isAnySpecialView;

  const [ragOpen, setRagOpen] = useState(currentPipeline === "rag" || isRagActive);
  const [agentOpen, setAgentOpen] = useState(currentPipeline === "agent" || isAgentActive);
  const [historyOpen, setHistoryOpen] = useState(isHistoryView);
  const [settingsOpen, setSettingsOpen] = useState(isSettingsView);

  // Mutually exclusive pipeline groups: when the pipeline switches (e.g. via
  // "View results" from History), open the active one and collapse the other.
  useEffect(() => {
    if (isAnySpecialView) return;
    if (currentPipeline === "agent") {
      setAgentOpen(true);
      setRagOpen(false);
    } else {
      setRagOpen(true);
      setAgentOpen(false);
    }
  }, [currentPipeline, isAnySpecialView]);

  const chatIsActive = currentStep === chatStep.id && !isAnySpecialView;
  const ChatIcon = iconMap[chatStep.icon] || Bot;

  return (
    <aside className="w-60 bg-surface-50 flex flex-col h-screen">
      {/* Logo */}
      <div className="px-4 py-4">
        <div className="flex items-center gap-2.5" data-walkthrough="sidebar-welcome">
          <Logo size={32} />
          <div>
            <h1 className="text-sm font-bold text-primary leading-tight">Yoke Agent</h1>
            <p className="text-[10px] text-t-secondary">AI Quality Studio</p>
          </div>
        </div>
      </div>

      <nav className="flex-1 px-3 space-y-0.5 overflow-y-auto" data-walkthrough="sidebar-steps">
        {/* AI Assistant — always visible, not inside any group */}
        <button
          onClick={() => onNavigate("/?step=chat")}
          className={cn(
            "w-full flex items-center gap-2.5 px-3 py-2 rounded-lg text-xs font-medium transition-all duration-200",
            chatIsActive
              ? "bg-accent/10 text-accent"
              : "text-t-secondary hover:bg-surface-100 hover:text-t-hover"
          )}
        >
          <div
            className={cn(
              "w-6 h-6 rounded-md flex items-center justify-center flex-shrink-0",
              chatIsActive ? "bg-accent/20 text-accent" : "bg-surface-200 text-muted"
            )}
          >
            <ChatIcon className="w-3.5 h-3.5" />
          </div>
          <span className="truncate">{chatStep.label}</span>
        </button>

        <div className="!my-2 mx-2 border-t border-surface-200/40" />

        {/* ── Augmented Retrieval — collapsible group ──────────────── */}
        <div className="space-y-0.5">
          <button
            onClick={() => { setRagOpen(!ragOpen); if (!ragOpen) onNavigate("/?pipeline=rag"); }}
            className={cn(
              "w-full flex items-center gap-2.5 px-3 py-2 rounded-lg text-xs font-medium transition-all duration-200",
              isRagActive
                ? "bg-accent/10 text-accent"
                : "text-t-secondary hover:bg-surface-100 hover:text-t-hover"
            )}
          >
            <div
              className={cn(
                "w-6 h-6 rounded-md flex items-center justify-center flex-shrink-0",
                isRagActive ? "bg-accent/20 text-accent" : "bg-surface-200 text-muted"
              )}
            >
              <Search className="w-3.5 h-3.5" />
            </div>
            <span className="flex-1 text-left">Augmented Retrieval</span>
            {ragOpen ? <ChevronDown className="w-3 h-3 text-muted" /> : <ChevronRight className="w-3 h-3 text-muted" />}
          </button>
          {ragOpen && (
            <div className="ml-4 space-y-0.5">
              {ragSteps.map((step) => {
                const isActive = currentStep === step.id && !isAnySpecialView;
                const isCompleted = completedSteps.has(step.id);
                const accessible = isStepAccessible ? isStepAccessible(step.id) : true;
                const isLocked = !accessible && !isCompleted;
                return (
                  <StepButton
                    key={step.id}
                    step={step}
                    isActive={isActive}
                    isCompleted={isCompleted}
                    isLocked={isLocked}
                    pipelineParam=""
                    onNavigate={onNavigate}
                  />
                );
              })}
            </div>
          )}
        </div>

        {/* ── Agent Evaluation — collapsible group ─────────────── */}
        <div className="space-y-0.5">
          <button
            onClick={() => { setAgentOpen(!agentOpen); if (!agentOpen) onNavigate("/?pipeline=agent"); }}
            className={cn(
              "w-full flex items-center gap-2.5 px-3 py-2 rounded-lg text-xs font-medium transition-all duration-200",
              isAgentActive
                ? "bg-accent/10 text-accent"
                : "text-t-secondary hover:bg-surface-100 hover:text-t-hover"
            )}
          >
            <div
              className={cn(
                "w-6 h-6 rounded-md flex items-center justify-center flex-shrink-0",
                isAgentActive ? "bg-accent/20 text-accent" : "bg-surface-200 text-muted"
              )}
            >
              <FlaskRound className="w-3.5 h-3.5" />
            </div>
            <span className="flex-1 text-left">Agent Evaluation</span>
            {agentOpen ? <ChevronDown className="w-3 h-3 text-muted" /> : <ChevronRight className="w-3 h-3 text-muted" />}
          </button>
          {agentOpen && (
            <div className="ml-4 space-y-0.5">
              {agentSteps.map((step) => {
                const isActive = currentStep === step.id && !isAnySpecialView;
                const isCompleted = completedSteps.has(step.id);
                const accessible = isStepAccessible ? isStepAccessible(step.id) : true;
                const isLocked = !accessible && !isCompleted;
                return (
                  <StepButton
                    key={step.id}
                    step={step}
                    isActive={isActive}
                    isCompleted={isCompleted}
                    isLocked={isLocked}
                    pipelineParam="pipeline=agent&"
                    onNavigate={onNavigate}
                  />
                );
              })}
            </div>
          )}
        </div>

        <div className="!my-2 mx-2 border-t border-surface-200/40" />

        {/* ── History — collapsible group ───────────────────────── */}
        <CollapsibleViewGroup
          label="History"
          icon={Archive}
          items={HISTORY_ITEMS}
          isOpen={historyOpen}
          onToggle={() => setHistoryOpen(!historyOpen)}
          isGroupActive={isHistoryView}
          currentView={currentView}
          onNavigate={onNavigate}
        />

        {/* ── Settings — collapsible group ──────────────────────── */}
        <CollapsibleViewGroup
          label="Settings"
          icon={Settings}
          items={SETTINGS_ITEMS}
          isOpen={settingsOpen}
          onToggle={() => setSettingsOpen(!settingsOpen)}
          isGroupActive={isSettingsView}
          currentView={currentView}
          onNavigate={onNavigate}
        />
      </nav>
    </aside>
  );
}
