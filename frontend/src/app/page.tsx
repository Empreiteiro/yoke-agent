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
  { id: "upload", label: "Upload Documents", icon: "upload" },
  { id: "dataset", label: "Generate Dataset", icon: "database" },
  { id: "review", label: "Review & Approve", icon: "check-circle" },
  { id: "grid-search", label: "Grid Search Config", icon: "grid" },
  { id: "execution", label: "Run Experiments", icon: "play" },
  { id: "results", label: "Results & Report", icon: "bar-chart" },
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

  const handleStepClick = (id: string) => {
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
            onComplete={(datasetId) =>
              handleStepComplete("dataset", { datasetId })
            }
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
    <div className="flex h-screen">
      <Sidebar
        steps={STEPS}
        currentStep={currentStep}
        completedSteps={completedSteps}
        onStepClick={handleStepClick}
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
      <main className="flex-1 overflow-y-auto">
        {showSettings ? (
          <div className="p-6 max-w-6xl mx-auto">
            <SettingsProviders onBack={() => setShowSettings(false)} />
          </div>
        ) : showHistory ? (
          <div className="p-6 max-w-6xl mx-auto">
            <History onBack={() => setShowHistory(false)} />
          </div>
        ) : showLogs ? (
          <div className="p-6 max-w-6xl mx-auto">
            <Logs onBack={() => setShowLogs(false)} />
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
      </main>
    </div>
  );
}
