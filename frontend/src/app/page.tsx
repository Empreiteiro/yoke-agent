"use client";

import { useState, useEffect, Suspense, useCallback } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import Sidebar from "@/components/Sidebar";
import PipelineHeader from "@/components/PipelineHeader";
import StepUpload from "@/components/steps/StepUpload";
import StepDataset from "@/components/steps/StepDataset";
import StepReview from "@/components/steps/StepReview";
import StepGridSearch from "@/components/steps/StepGridSearch";
import StepExecution from "@/components/steps/StepExecution";
import StepResults from "@/components/steps/StepResults";
import SettingsProviders from "@/components/SettingsProviders";
import SettingsVectorStores from "@/components/SettingsVectorStores";
import History from "@/components/History";
import Logs from "@/components/Logs";
import Glossary from "@/components/Glossary";
import Collections from "@/components/Collections";
import WalkthroughOverlay from "@/components/Walkthrough";
import { useWalkthrough } from "@/contexts/WalkthroughContext";

const STEPS = [
  { id: "upload", label: "Upload Documents", icon: "upload", description: "Upload one or more documents to analyze. Supported formats: PDF, TXT, DOCX, MD." },
  { id: "dataset", label: "Generate Dataset", icon: "database", description: "An LLM will analyze your documents and generate question-answer pairs for evaluation." },
  { id: "review", label: "Review & Approve", icon: "check-circle", description: "Review, edit, add, or remove Q&A pairs. Import additional items from a JSON file." },
  { id: "grid-search", label: "Grid Search Config", icon: "grid", description: "Name your experiment and configure RAG hyperparameters." },
  { id: "execution", label: "Run Experiments", icon: "play", description: "Execute all combinations and evaluate with RAGAS." },
  { id: "results", label: "Results & Report", icon: "bar-chart", description: "View the best configurations and detailed results." },
] as const;

type StepId = (typeof STEPS)[number]["id"];

const VALID_VIEWS = ["history", "logs", "settings", "glossary", "collections", "vectorstores"];
const VALID_STEPS = STEPS.map((s) => s.id);

function HomeContent() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const { startIfNew } = useWalkthrough();

  // Trigger sidebar walkthrough on first ever visit
  useEffect(() => {
    startIfNew("sidebar");
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // Derive current view from URL
  const urlView = searchParams.get("view");
  const urlStep = searchParams.get("step");
  const currentView = urlView && VALID_VIEWS.includes(urlView) ? urlView : null;
  const currentStep: StepId = (urlStep && VALID_STEPS.includes(urlStep as StepId) ? urlStep : (currentView ? "upload" : "upload")) as StepId;

  const [completedSteps, setCompletedSteps] = useState<Set<StepId>>(new Set());
  const [pipelineData, setPipelineData] = useState<{
    documentIds: number[];
    datasetId: number | null;
    experimentId: number | null;
  }>({
    documentIds: [],
    datasetId: null,
    experimentId: null,
  });

  const navigate = useCallback((path: string) => {
    router.push(path);
  }, [router]);

  const handleStepComplete = (stepId: StepId, data?: Partial<typeof pipelineData>) => {
    setCompletedSteps((prev) => new Set([...prev, stepId]));
    if (data) {
      setPipelineData((prev) => ({ ...prev, ...data }));
    }
    const currentIndex = STEPS.findIndex((s) => s.id === stepId);
    if (currentIndex < STEPS.length - 1) {
      const nextStep = STEPS[currentIndex + 1].id;
      router.push(`/?step=${nextStep}`);
    }
  };

  const stepPrerequisites: Record<string, string | null> = {
    upload: null,
    dataset: null,
    review: "dataset",
    "grid-search": "review",
    execution: "grid-search",
    results: "execution",
  };

  const isStepAccessible = (stepId: string): boolean => {
    const prereq = stepPrerequisites[stepId];
    if (prereq === null) return true;
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
  };

  return (
    <div className="flex h-screen bg-surface-50">
      <Sidebar
        steps={STEPS}
        currentStep={currentStep}
        currentView={currentView}
        completedSteps={completedSteps}
        onNavigate={handleNavigate}
        isStepAccessible={isStepAccessible}
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
                steps={STEPS}
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
