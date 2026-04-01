"use client";

import {
  createContext,
  useContext,
  useState,
  useCallback,
  useEffect,
  useRef,
  type ReactNode,
} from "react";
import { getWalkthrough, type WalkthroughStep } from "@/lib/walkthroughSteps";

const STORAGE_KEY = "rag-walkthrough-seen";

interface WalkthroughContextType {
  startIfNew: (screenId: string) => void;
  nextStep: () => void;
  prevStep: () => void;
  skipAll: () => void;
  skipCurrent: () => void;
  isActive: boolean;
  currentStep: WalkthroughStep | null;
  currentStepIndex: number;
  totalSteps: number;
  activeScreenId: string | null;
}

const WalkthroughContext = createContext<WalkthroughContextType | null>(null);

function loadSeen(): Set<string> {
  if (typeof window === "undefined") return new Set();
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw) return new Set(JSON.parse(raw));
  } catch {}
  return new Set();
}

function saveSeen(seen: Set<string>) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify([...seen]));
  } catch {}
}

export function WalkthroughProvider({ children }: { children: ReactNode }) {
  const [mounted, setMounted] = useState(false);
  const [seenScreens, setSeenScreens] = useState<Set<string>>(new Set());
  const [activeScreenId, setActiveScreenId] = useState<string | null>(null);
  const [stepIndex, setStepIndex] = useState(0);
  const startingRef = useRef(false);

  useEffect(() => {
    setSeenScreens(loadSeen());
    setMounted(true);
  }, []);

  const markSeen = useCallback(
    (screenId: string) => {
      setSeenScreens((prev) => {
        const next = new Set(prev);
        next.add(screenId);
        saveSeen(next);
        return next;
      });
    },
    []
  );

  const startIfNew = useCallback(
    (screenId: string) => {
      if (!mounted || startingRef.current) return;
      if (seenScreens.has(screenId)) return;
      const wt = getWalkthrough(screenId);
      if (!wt || wt.steps.length === 0) return;
      startingRef.current = true;
      // Small delay so DOM elements with data-walkthrough render first
      setTimeout(() => {
        setActiveScreenId(screenId);
        setStepIndex(0);
        startingRef.current = false;
      }, 400);
    },
    [mounted, seenScreens]
  );

  const finish = useCallback(() => {
    if (activeScreenId) markSeen(activeScreenId);
    setActiveScreenId(null);
    setStepIndex(0);
  }, [activeScreenId, markSeen]);

  const wt = activeScreenId ? getWalkthrough(activeScreenId) : null;
  const steps = wt?.steps ?? [];

  const nextStep = useCallback(() => {
    if (stepIndex < steps.length - 1) {
      setStepIndex((i) => i + 1);
    } else {
      finish();
    }
  }, [stepIndex, steps.length, finish]);

  const prevStep = useCallback(() => {
    setStepIndex((i) => Math.max(0, i - 1));
  }, []);

  const skipCurrent = useCallback(() => {
    finish();
  }, [finish]);

  const skipAll = useCallback(() => {
    const allIds = [
      "sidebar",
      "upload",
      "dataset",
      "review",
      "grid-search",
      "execution",
      "results",
    ];
    setSeenScreens(() => {
      const next = new Set(allIds);
      saveSeen(next);
      return next;
    });
    setActiveScreenId(null);
    setStepIndex(0);
  }, []);

  const value: WalkthroughContextType = {
    startIfNew,
    nextStep,
    prevStep,
    skipAll,
    skipCurrent,
    isActive: mounted && activeScreenId !== null,
    currentStep: steps[stepIndex] ?? null,
    currentStepIndex: stepIndex,
    totalSteps: steps.length,
    activeScreenId,
  };

  return (
    <WalkthroughContext.Provider value={value}>
      {children}
    </WalkthroughContext.Provider>
  );
}

export function useWalkthrough(): WalkthroughContextType {
  const ctx = useContext(WalkthroughContext);
  if (!ctx)
    throw new Error("useWalkthrough must be used within WalkthroughProvider");
  return ctx;
}
