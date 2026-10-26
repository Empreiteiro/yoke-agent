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
  ChevronRight,
  Archive,
  Search,
  FlaskRound,
  User,
  Activity,
  Scale,
  Lock,
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
  { id: "traces", label: "Traces", icon: Activity },
];

const COMPARISON_ITEMS = [
  { id: "decision-compare", label: "Run Comparison", icon: Play },
  { id: "decision-results", label: "Results", icon: BarChart3 },
  { id: "decision-datasets", label: "Datasets", icon: Database },
];

const SETTINGS_ITEMS = [
  { id: "settings", label: "Providers", icon: Settings },
  { id: "vectorstores", label: "Vector Stores", icon: Database },
  { id: "mcp", label: "MCP Server", icon: Cable },
  { id: "glossary", label: "Concepts", icon: BookOpen },
  { id: "user-settings", label: "User", icon: User },
];

// Shared look for every row in the nav. The active row lifts onto the raised
// surface (hairline + resting shadow) instead of being tinted.
const rowBase =
  "group w-full flex items-center gap-2.5 rounded-lg border text-[13px] font-medium transition-colors";
const rowIdle = "border-transparent text-t-secondary hover:bg-surface-200/60 hover:text-primary";
const rowActive = "border-themed bg-surface-100 text-primary shadow-resting";

function SectionLabel({ children }: { children: React.ReactNode }) {
  return (
    <div className="px-2.5 pt-4 pb-1.5 text-[11px] font-medium uppercase tracking-[0.08em] text-muted">
      {children}
    </div>
  );
}

// ── Reusable: group header that expands a nested list ───────────────

function GroupHeader({
  label,
  icon: GroupIcon,
  isOpen,
  isActive,
  onClick,
}: {
  label: string;
  icon: any;
  isOpen: boolean;
  isActive: boolean;
  onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      aria-expanded={isOpen}
      className={cn(rowBase, "h-9 px-2.5", isActive && !isOpen ? rowActive : rowIdle)}
    >
      <GroupIcon
        className={cn(
          "w-4 h-4 flex-shrink-0 transition-colors",
          isActive ? "text-accent" : "text-muted group-hover:text-t-secondary"
        )}
      />
      <span className={cn("flex-1 text-left truncate", isActive && "text-primary")}>{label}</span>
      <ChevronRight
        className={cn(
          "w-3.5 h-3.5 text-muted transition-transform duration-[240ms]",
          isOpen && "rotate-90"
        )}
      />
    </button>
  );
}

// Nested list with a hairline guide on the left, like a tree.
function SubList({ children }: { children: React.ReactNode }) {
  return (
    <div className="ml-[17px] mt-0.5 mb-1 pl-2 border-l border-themed space-y-0.5 animate-fade-in">
      {children}
    </div>
  );
}

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
      title={isLocked ? "Complete the previous step first" : undefined}
      className={cn(
        rowBase,
        "h-8 px-2.5",
        isLocked
          ? "border-transparent text-muted/70 cursor-not-allowed"
          : isActive
          ? rowActive
          : rowIdle
      )}
    >
      {isCompleted && !isActive ? (
        <CheckCircle className="w-3.5 h-3.5 flex-shrink-0 text-success" />
      ) : (
        <Icon className={cn("w-3.5 h-3.5 flex-shrink-0", isActive ? "text-accent" : "text-muted")} />
      )}
      <span className="flex-1 text-left truncate">{step.label}</span>
      {isLocked && <Lock className="w-3 h-3 flex-shrink-0 text-muted/60" />}
    </button>
  );
}

// ── Reusable: collapsible group with sub-items (for views) ───────────

function CollapsibleViewGroup({
  label,
  icon,
  items,
  isOpen,
  onToggle,
  isGroupActive,
  currentView,
  onNavigate,
  walkthroughId,
}: {
  label: string;
  icon: any;
  items: { id: string; label: string; icon: any }[];
  isOpen: boolean;
  onToggle: () => void;
  isGroupActive: boolean;
  currentView: string | null;
  onNavigate: (path: string) => void;
  walkthroughId?: string;
}) {
  return (
    <div data-walkthrough={walkthroughId}>
      <GroupHeader label={label} icon={icon} isOpen={isOpen} isActive={isGroupActive} onClick={onToggle} />
      {isOpen && (
        <SubList>
          {items.map((item) => {
            const ItemIcon = item.icon;
            const isActive = currentView === item.id;
            return (
              <button
                key={item.id}
                onClick={() => onNavigate(`/?view=${item.id}`)}
                className={cn(rowBase, "h-8 px-2.5", isActive ? rowActive : rowIdle)}
              >
                <ItemIcon className={cn("w-3.5 h-3.5 flex-shrink-0", isActive ? "text-accent" : "text-muted")} />
                <span className="truncate">{item.label}</span>
              </button>
            );
          })}
        </SubList>
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
  const isComparisonView = COMPARISON_ITEMS.some((item) => item.id === currentView);

  // Determine which pipeline group is active based on current step
  const ragStepIds = new Set(ragSteps.map((s) => s.id));
  const agentStepIds = new Set(agentSteps.map((s) => s.id));
  const isRagActive = ragStepIds.has(currentStep) && !isAnySpecialView;
  const isAgentActive = agentStepIds.has(currentStep) && !isAnySpecialView;

  // Pipeline groups start collapsed. They only auto-open when the current
  // step actually belongs to the group (e.g. the user navigates to Define
  // Agent). Landing on "/" — where the default step is "chat" — leaves both
  // groups collapsed so the sidebar matches what the user is looking at.
  const [ragOpen, setRagOpen] = useState(isRagActive);
  const [agentOpen, setAgentOpen] = useState(isAgentActive);
  const [historyOpen, setHistoryOpen] = useState(isHistoryView);
  const [comparisonOpen, setComparisonOpen] = useState(isComparisonView);
  const [settingsOpen, setSettingsOpen] = useState(isSettingsView);

  // Mutually exclusive pipeline groups: when the active step actually lives
  // inside a group (e.g. arriving via "View results" from History), open
  // that group and collapse the other. When neither group is active (chat,
  // settings, etc.) leave the state alone so we don't clobber a group the
  // user expanded manually.
  useEffect(() => {
    if (isAnySpecialView) return;
    if (isRagActive) {
      setRagOpen(true);
      setAgentOpen(false);
    } else if (isAgentActive) {
      setAgentOpen(true);
      setRagOpen(false);
    }
  }, [isRagActive, isAgentActive, isAnySpecialView]);

  // In-page links (e.g. "Compare models" on a dataset) land on comparison
  // views without touching the sidebar — open the group so it matches.
  useEffect(() => {
    if (isComparisonView) setComparisonOpen(true);
  }, [isComparisonView]);

  const chatIsActive = currentStep === chatStep.id && !isAnySpecialView;
  const ChatIcon = iconMap[chatStep.icon] || Bot;

  const renderSteps = (list: readonly Step[], pipelineParam: string) =>
    list.map((step) => {
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
          pipelineParam={pipelineParam}
          onNavigate={onNavigate}
        />
      );
    });

  return (
    <aside className="w-64 flex-shrink-0 flex flex-col h-screen">
      {/* Brand */}
      <div className="px-5 pt-5 pb-2">
        <div className="flex items-center gap-3" data-walkthrough="sidebar-welcome">
          <div className="w-9 h-9 rounded-xl bg-surface-100 border border-themed shadow-resting flex items-center justify-center">
            <Logo size={22} />
          </div>
          <div className="min-w-0">
            <h1 className="text-[15px] font-semibold text-primary leading-tight">Yoke Agent</h1>
            <p className="text-[11px] text-muted leading-tight mt-0.5">AI Quality Studio</p>
          </div>
        </div>
      </div>

      <nav className="flex-1 px-3 pb-3 overflow-y-auto" data-walkthrough="sidebar-steps">
        {/* AI Assistant — always visible, not inside any group */}
        <div className="pt-3">
          <button
            onClick={() => onNavigate("/?step=chat")}
            className={cn(rowBase, "h-9 px-2.5", chatIsActive ? rowActive : rowIdle)}
          >
            <ChatIcon
              className={cn(
                "w-4 h-4 flex-shrink-0",
                chatIsActive ? "text-accent" : "text-muted group-hover:text-t-secondary"
              )}
            />
            <span className="truncate">{chatStep.label}</span>
          </button>
        </div>

        <SectionLabel>Pipelines</SectionLabel>

        {/* ── Augmented Retrieval — collapsible group ──────────────── */}
        <div>
          <GroupHeader
            label="Augmented Retrieval"
            icon={Search}
            isOpen={ragOpen}
            isActive={isRagActive}
            onClick={() => { setRagOpen(!ragOpen); if (!ragOpen) onNavigate("/?pipeline=rag"); }}
          />
          {ragOpen && <SubList>{renderSteps(ragSteps, "")}</SubList>}
        </div>

        {/* ── Agent Evaluation — collapsible group ─────────────── */}
        <div>
          <GroupHeader
            label="Agent Evaluation"
            icon={FlaskRound}
            isOpen={agentOpen}
            isActive={isAgentActive}
            onClick={() => { setAgentOpen(!agentOpen); if (!agentOpen) onNavigate("/?pipeline=agent"); }}
          />
          {agentOpen && <SubList>{renderSteps(agentSteps, "pipeline=agent&")}</SubList>}
        </div>

        {/* ── Model Comparison — decision models vs. LLMs ──────── */}
        <CollapsibleViewGroup
          label="Model Comparison"
          icon={Scale}
          items={COMPARISON_ITEMS}
          isOpen={comparisonOpen}
          onToggle={() => setComparisonOpen(!comparisonOpen)}
          isGroupActive={isComparisonView}
          currentView={currentView}
          onNavigate={onNavigate}
        />

        <SectionLabel>Workspace</SectionLabel>

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
          walkthroughId="sidebar-history"
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
          walkthroughId="sidebar-settings"
        />
      </nav>
    </aside>
  );
}
