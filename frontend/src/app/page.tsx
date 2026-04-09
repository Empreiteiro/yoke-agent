"use client";

import { useState, useEffect, Suspense, useCallback } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import Sidebar from "@/components/Sidebar";
import PipelineHeader from "@/components/PipelineHeader";
import StepChat from "@/components/steps/StepChat";
import StepUpload from "@/components/steps/StepUpload";
import StepDataset from "@/components/steps/StepDataset";
import StepReview from "@/components/steps/StepReview";
import StepGridSearch from "@/components/steps/StepGridSearch";
import StepExecution from "@/components/steps/StepExecution";
import StepResults from "@/components/steps/StepResults";
import StepAgentDefine from "@/components/steps/StepAgentDefine";
import StepAgentScenarios from "@/components/steps/StepAgentScenarios";
import StepAgentPersonas from "@/components/steps/StepAgentPersonas";
import StepAgentGridSearch from "@/components/steps/StepAgentGridSearch";
import StepAgentExecution from "@/components/steps/StepAgentExecution";
import StepAgentResults from "@/components/steps/StepAgentResults";
import SettingsProviders from "@/components/SettingsProviders";
import SettingsVectorStores from "@/components/SettingsVectorStores";
import History from "@/components/History";
import Logs from "@/components/Logs";
import Glossary from "@/components/Glossary";
import Collections from "@/components/Collections";
import McpSettings from "@/components/McpSettings";
import WalkthroughOverlay from "@/components/Walkthrough";
import { useWalkthrough } from "@/contexts/WalkthroughContext";

const STEP_CHAT = { id: "chat", label: "AI Assistant", icon: "bot", description: "Chat with an AI assistant to learn about the platform and get help." } as const;

const RAG_STEPS = [
  { id: "upload", label: "Upload Documents", icon: "upload", description: "Upload one or more documents to analyze. Supported formats: PDF, TXT, DOCX, MD." },
  { id: "dataset", label: "Generate Dataset", icon: "database", description: "An LLM will analyze your documents and generate question-answer pairs for evaluation." },
  { id: "review", label: "Review & Approve", icon: "check-circle", description: "Review, edit, add, or remove Q&A pairs. Import additional items from a JSON file." },
  { id: "grid-search", label: "Grid Search Config", icon: "grid", description: "Name your experiment and configure RAG hyperparameters." },
  { id: "execution", label: "Run Experiments", icon: "play", description: "Execute all combinations and evaluate with RAGAS." },
  { id: "results", label: "Results & Report", icon: "bar-chart", description: "View the best configurations and detailed results." },
] as const;

const AGENT_STEPS = [
  { id: "agent-define", label: "Define Agent", icon: "bot", description: "Define your agent's system prompt, tools, and constraints." },
  { id: "agent-scenarios", label: "Create Scenarios", icon: "flask-conical", description: "Build test cases for tool use, decision paths, response quality, and guardrails." },
  { id: "agent-personas", label: "Create Personas", icon: "users", description: "Define synthetic user profiles to simulate diverse interactions." },
  { id: "agent-grid", label: "Grid Search Config", icon: "grid", description: "Configure combinations of models, prompts, temperatures, and personas." },
  { id: "agent-execution", label: "Run Simulations", icon: "play", description: "Execute simulated conversations across all combinations." },
  { id: "agent-results", label: "Results & Report", icon: "bar-chart", description: "View metrics, compare configurations, and get prompt improvement suggestions." },
] as const;

type PipelineType = "rag" | "agent";

type RagStepId = typeof STEP_CHAT.id | (typeof RAG_STEPS)[number]["id"];
type AgentStepId = typeof STEP_CHAT.id | (typeof AGENT_STEPS)[number]["id"];
type StepId = RagStepId | AgentStepId;

const ALL_RAG_STEPS = [STEP_CHAT, ...RAG_STEPS] as const;
const ALL_AGENT_STEPS = [STEP_CHAT, ...AGENT_STEPS] as const;

const VALID_VIEWS = ["history", "logs", "settings", "glossary", "collections", "vectorstores", "mcp"];
const VALID_STEPS: string[] = [
  STEP_CHAT.id,
  ...RAG_STEPS.map((s) => s.id),
  ...AGENT_STEPS.map((s) => s.id),
];

function HomeContent() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const { startIfNew } = useWalkthrough();

  // Trigger sidebar walkthrough on first ever visit
  useEffect(() => {
    startIfNew("sidebar");
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // Derive pipeline and current view from URL
  const pipeline: PipelineType = searchParams.get("pipeline") === "agent" ? "agent" : "rag";
  const ACTIVE_STEPS = pipeline === "agent" ? ALL_AGENT_STEPS : ALL_RAG_STEPS;

  const urlView = searchParams.get("view");
  const urlStep = searchParams.get("step");
  const currentView = urlView && VALID_VIEWS.includes(urlView) ? urlView : null;
  const currentStep: StepId = (urlStep && VALID_STEPS.includes(urlStep) ? urlStep : "chat") as StepId;

  const [completedSteps, setCompletedSteps] = useState<Set<StepId>>(new Set());
  const [pipelineData, setPipelineData] = useState<{
    documentIds: number[];
    datasetId: number | null;
    experimentId: number | null;
    agentConfigId: number | null;
    agentExperimentId: number | null;
  }>({
    documentIds: [],
    datasetId: null,
    experimentId: null,
    agentConfigId: null,
    agentExperimentId: null,
  });

  const navigate = useCallback((path: string) => {
    router.push(path);
  }, [router]);

  const handleStepComplete = (stepId: StepId, data?: Partial<typeof pipelineData>) => {
    setCompletedSteps((prev) => new Set([...prev, stepId]));
    if (data) {
      setPipelineData((prev) => ({ ...prev, ...data }));
    }
    const currentIndex = ACTIVE_STEPS.findIndex((s) => s.id === stepId);
    if (currentIndex < ACTIVE_STEPS.length - 1) {
      const nextStep = ACTIVE_STEPS[currentIndex + 1].id;
      const pipelineParam = pipeline === "agent" ? "pipeline=agent&" : "";
      router.push(`/?${pipelineParam}step=${nextStep}`);
    }
  };

  const stepPrerequisites: Record<string, string | null> = {
    // Shared
    chat: null,
    // RAG steps
    upload: null,
    dataset: null,
    review: "dataset",
    "grid-search": "review",
    execution: "grid-search",
    results: "execution",
    // Agent steps (all independent for now)
    "agent-define": null,
    "agent-scenarios": null,
    "agent-personas": null,
    "agent-grid": null,
    "agent-execution": null,
    "agent-results": null,
  };

  const isStepAccessible = (stepId: string): boolean => {
    const prereq = stepPrerequisites[stepId];
    if (prereq === null || prereq === undefined) return true;
    return completedSteps.has(prereq as StepId);
  };

  const handleNavigate = (path: string) => {
    // Extract step from path and check accessibility
    const stepMatch = path.match(/step=([^&]+)/);
    if (stepMatch) {
      const stepId = stepMatch[1];
      if (!isStepAccessible(stepId)) return;
    }
    navigate(path);
  };

  const renderStep = () => {
    switch (currentStep) {
      case "chat":
        return <StepChat />;
      case "upload":
        return (
          <StepUpload
            onComplete={(docIds) =>
              handleStepComplete("upload", { documentIds: docIds })
            }
          />
        );
      case "dataset":
        return (
          <StepDataset
            documentIds={pipelineData.documentIds}
            onComplete={(datasetId, reused) => {
              if (reused) {
                setCompletedSteps((prev) => new Set([...prev, "upload"]));
              }
              handleStepComplete("dataset", { datasetId });
            }}
          />
        );
      case "review":
        return (
          <StepReview
            datasetId={pipelineData.datasetId}
            onComplete={() => handleStepComplete("review")}
          />
        );
      case "grid-search":
        return (
          <StepGridSearch
            datasetId={pipelineData.datasetId}
            onComplete={(experimentId) =>
              handleStepComplete("grid-search", { experimentId })
            }
          />
        );
      case "execution":
        return (
          <StepExecution
            experimentId={pipelineData.experimentId}
            onComplete={() => handleStepComplete("execution")}
          />
        );
      case "results":
        return (
          <StepResults experimentId={pipelineData.experimentId} />
        );
      // Agent pipeline steps
      case "agent-define":
        return (
          <StepAgentDefine
            onComplete={(configId) =>
              handleStepComplete("agent-define" as StepId, { agentConfigId: configId } as any)
            }
          />
        );
      case "agent-scenarios":
        return (
          <StepAgentScenarios
            agentConfigId={pipelineData.agentConfigId}
            onComplete={() => handleStepComplete("agent-scenarios" as StepId)}
          />
        );
      case "agent-personas":
        return (
          <StepAgentPersonas
            agentConfigId={pipelineData.agentConfigId}
            onComplete={() => handleStepComplete("agent-personas" as StepId)}
          />
        );
      case "agent-grid":
        return (
          <StepAgentGridSearch
            agentConfigId={pipelineData.agentConfigId}
            onComplete={(expId) =>
              handleStepComplete("agent-grid" as StepId, { agentExperimentId: expId } as any)
            }
          />
        );
      case "agent-execution":
        return (
          <StepAgentExecution
            experimentId={pipelineData.agentExperimentId}
            onComplete={() => handleStepComplete("agent-execution" as StepId)}
          />
        );
      case "agent-results":
        return <StepAgentResults experimentId={pipelineData.agentExperimentId} />;
      default:
        return null;
    }
  };

  const VIEW_COMPONENTS: Record<string, React.ReactNode> = {
    settings: <SettingsProviders />,
    vectorstores: <SettingsVectorStores />,
    history: <History onViewResults={(experimentId: number) => {
      setPipelineData((prev) => ({ ...prev, experimentId }));
      setCompletedSteps((prev) => new Set([...prev, "upload", "dataset", "review", "grid-search", "execution"] as StepId[]));
      router.push("/?step=results");
    }} />,
    logs: <Logs />,
    glossary: <Glossary />,
    collections: <Collections />,
    mcp: <McpSettings />,
  };

  return (
    <div className="flex h-screen bg-surface-50">
      <Sidebar
        steps={ACTIVE_STEPS}
        currentStep={currentStep}
        currentView={currentView}
        completedSteps={completedSteps}
        onNavigate={handleNavigate}
        isStepAccessible={isStepAccessible}
        currentPipeline={pipeline}
      />
      <main className="flex-1 overflow-y-auto p-3 pl-0">
        <div className="h-full bg-surface-100 rounded-2xl border border-surface-200/30 overflow-y-auto">
          {currentView && VIEW_COMPONENTS[currentView] ? (
            <div className="p-6 max-w-6xl mx-auto">
              {VIEW_COMPONENTS[currentView]}
            </div>
          ) : (
            <>
              <PipelineHeader
                steps={ACTIVE_STEPS}
                currentStep={currentStep}
                completedSteps={completedSteps}
              />
              <div className="p-6 max-w-6xl mx-auto">{renderStep()}</div>
            </>
          )}
        </div>
      </main>
      <WalkthroughOverlay />
    </div>
  );
}

export default function Home() {
  return (
    <Suspense fallback={<div className="flex h-screen items-center justify-center bg-surface-50 text-t-secondary">Loading...</div>}>
      <HomeContent />
    </Suspense>
  );
}
