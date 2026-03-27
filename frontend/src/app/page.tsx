"use client";

import { useState } from "react";
import Sidebar from "@/components/Sidebar";
import PipelineHeader from "@/components/PipelineHeader";
import StepUpload from "@/components/steps/StepUpload";
import StepDataset from "@/components/steps/StepDataset";
import StepReview from "@/components/steps/StepReview";
import StepGridSearch from "@/components/steps/StepGridSearch";
import StepExecution from "@/components/steps/StepExecution";
import StepResults from "@/components/steps/StepResults";
import SettingsProviders from "@/components/SettingsProviders";
import History from "@/components/History";
import Logs from "@/components/Logs";

const STEPS = [
  { id: "upload", label: "Upload Documents", icon: "upload", description: "Upload one or more documents to analyze. Supported formats: PDF, TXT, DOCX, MD." },
  { id: "dataset", label: "Generate Dataset", icon: "database", description: "An LLM will analyze your documents and generate question-answer pairs for evaluation." },
  { id: "review", label: "Review & Approve", icon: "check-circle", description: "Review, edit, add, or remove Q&A pairs. Import additional items from a JSON file." },
  { id: "grid-search", label: "Grid Search Config", icon: "grid", description: "Name your experiment and configure RAG hyperparameters." },
  { id: "execution", label: "Run Experiments", icon: "play", description: "Execute all combinations and evaluate with RAGAS." },
  { id: "results", label: "Results & Report", icon: "bar-chart", description: "View the best configurations and detailed results." },
] as const;

type StepId = (typeof STEPS)[number]["id"];

export default function Home() {
  const [currentStep, setCurrentStep] = useState<StepId>("upload");
  const [completedSteps, setCompletedSteps] = useState<Set<StepId>>(new Set());
  const [showSettings, setShowSettings] = useState(false);
  const [showHistory, setShowHistory] = useState(false);
  const [showLogs, setShowLogs] = useState(false);
  const [pipelineData, setPipelineData] = useState<{
    documentIds: number[];
    datasetId: number | null;
    experimentId: number | null;
  }>({
    documentIds: [],
    datasetId: null,
    experimentId: null,
  });

  const handleStepComplete = (stepId: StepId, data?: Partial<typeof pipelineData>) => {
    setCompletedSteps((prev) => new Set([...prev, stepId]));
    if (data) {
      setPipelineData((prev) => ({ ...prev, ...data }));
    }
    const currentIndex = STEPS.findIndex((s) => s.id === stepId);
    if (currentIndex < STEPS.length - 1) {
      setCurrentStep(STEPS[currentIndex + 1].id);
    }
  };

  // Steps that require the previous step to be completed
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

  const handleStepClick = (id: string) => {
    if (!isStepAccessible(id)) return;
    setCurrentStep(id as StepId);
    setShowSettings(false);
    setShowHistory(false);
    setShowLogs(false);
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
                // When reusing a dataset, mark upload as completed too
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

  return (
    <div className="flex h-screen bg-surface-50">
      <Sidebar
        steps={STEPS}
        currentStep={currentStep}
        completedSteps={completedSteps}
        onStepClick={handleStepClick}
        isStepAccessible={isStepAccessible}
        showSettings={showSettings}
        onSettingsClick={() => {
          setShowSettings(true);
          setShowHistory(false);
          setShowLogs(false);
        }}
        showHistory={showHistory}
        onHistoryClick={() => {
          setShowHistory(true);
          setShowSettings(false);
          setShowLogs(false);
        }}
        showLogs={showLogs}
        onLogsClick={() => {
          setShowLogs(true);
          setShowSettings(false);
          setShowHistory(false);
        }}
      />
      <main className="flex-1 overflow-y-auto p-3 pl-0">
        <div className="h-full bg-surface-100 rounded-2xl border border-surface-200/30 overflow-y-auto">
          {showSettings ? (
            <div className="p-6 max-w-6xl mx-auto">
              <SettingsProviders />
            </div>
          ) : showHistory ? (
            <div className="p-6 max-w-6xl mx-auto">
              <History />
            </div>
          ) : showLogs ? (
            <div className="p-6 max-w-6xl mx-auto">
              <Logs />
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
    </div>
  );
}
