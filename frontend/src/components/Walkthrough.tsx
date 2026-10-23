"use client";

import { useEffect, useState, useCallback, useRef } from "react";
import { useWalkthrough } from "@/contexts/WalkthroughContext";
import { ChevronLeft, ChevronRight, X, Sparkles } from "lucide-react";

interface Rect {
  top: number;
  left: number;
  width: number;
  height: number;
}

const PAD = 8;
const TOOLTIP_W = 340;
const TOOLTIP_GAP = 16;
const ARROW_SIZE = 12;

export default function WalkthroughOverlay() {
  const {
    isActive,
    currentStep,
    currentStepIndex,
    totalSteps,
    nextStep,
    prevStep,
    skipAll,
    activeScreenId,
  } = useWalkthrough();

  const [targetRect, setTargetRect] = useState<Rect | null>(null);
  const [visible, setVisible] = useState(false);
  const rafRef = useRef<number>(0);
  const prevScreenRef = useRef<string | null>(null);

  const measure = useCallback(() => {
    if (!currentStep) {
      setTargetRect(null);
      return;
    }
    const el = document.querySelector(
      `[data-walkthrough="${currentStep.target}"]`
    );
    if (!el) {
      // Target not in DOM — auto-advance
      nextStep();
      return;
    }
    const r = el.getBoundingClientRect();
    setTargetRect({
      top: r.top,
      left: r.left,
      width: r.width,
      height: r.height,
    });
    // Scroll into view if needed
    if (r.top < 0 || r.bottom > window.innerHeight) {
      el.scrollIntoView({ behavior: "smooth", block: "center" });
    }
  }, [currentStep, nextStep]);

  // Measure on step change
  useEffect(() => {
    if (!isActive || !currentStep) return;

    // Fade in
    setVisible(false);
    const t = setTimeout(() => {
      measure();
      setVisible(true);
    }, 80);

    return () => clearTimeout(t);
  }, [isActive, currentStep, currentStepIndex, measure]);

  // Re-measure on resize / scroll
  useEffect(() => {
    if (!isActive) return;

    const onResize = () => measure();
    window.addEventListener("resize", onResize);

    // Also listen for scroll in the main content area
    const main = document.querySelector("main");
    if (main) main.addEventListener("scroll", onResize, { passive: true });

    return () => {
      window.removeEventListener("resize", onResize);
      if (main) main.removeEventListener("scroll", onResize);
    };
  }, [isActive, measure]);

  // Escape key
  useEffect(() => {
    if (!isActive) return;
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") skipAll();
      if (e.key === "ArrowRight") nextStep();
      if (e.key === "ArrowLeft") prevStep();
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [isActive, skipAll, nextStep, prevStep]);

  // Reset visibility on screen change
  useEffect(() => {
    if (activeScreenId !== prevScreenRef.current) {
      setVisible(false);
      prevScreenRef.current = activeScreenId;
    }
  }, [activeScreenId]);

  useEffect(() => {
    return () => cancelAnimationFrame(rafRef.current);
  }, []);

  if (!isActive || !currentStep || !targetRect) return null;

  // Compute tooltip position
  const pos = currentStep.position;
  let tooltipStyle: React.CSSProperties = {};
  let arrowStyle: React.CSSProperties = {};
  let arrowRotation = "0deg";

  const cx = targetRect.left + targetRect.width / 2;
  const cy = targetRect.top + targetRect.height / 2;

  if (pos === "bottom") {
    tooltipStyle = {
      top: targetRect.top + targetRect.height + PAD + TOOLTIP_GAP + ARROW_SIZE,
      left: Math.max(16, Math.min(cx - TOOLTIP_W / 2, window.innerWidth - TOOLTIP_W - 16)),
    };
    arrowStyle = {
      top: targetRect.top + targetRect.height + PAD + TOOLTIP_GAP - 2,
      left: cx - ARROW_SIZE / 2,
    };
    arrowRotation = "180deg";
  } else if (pos === "top") {
    tooltipStyle = {
      top: targetRect.top - PAD - TOOLTIP_GAP - ARROW_SIZE - 200,
      left: Math.max(16, Math.min(cx - TOOLTIP_W / 2, window.innerWidth - TOOLTIP_W - 16)),
    };
    // If tooltip goes above viewport, switch to bottom
    if ((tooltipStyle.top as number) < 16) {
      tooltipStyle.top = targetRect.top + targetRect.height + PAD + TOOLTIP_GAP + ARROW_SIZE;
      arrowStyle = {
        top: targetRect.top + targetRect.height + PAD + TOOLTIP_GAP - 2,
        left: cx - ARROW_SIZE / 2,
      };
      arrowRotation = "180deg";
    } else {
      arrowStyle = {
        top: targetRect.top - PAD - TOOLTIP_GAP + 2,
        left: cx - ARROW_SIZE / 2,
      };
      arrowRotation = "0deg";
    }
  } else if (pos === "right") {
    tooltipStyle = {
      top: Math.max(16, cy - 80),
      left: targetRect.left + targetRect.width + PAD + TOOLTIP_GAP + ARROW_SIZE,
    };
    arrowStyle = {
      top: cy - ARROW_SIZE / 2,
      left: targetRect.left + targetRect.width + PAD + TOOLTIP_GAP - 2,
    };
    arrowRotation = "90deg";
  } else {
    tooltipStyle = {
      top: Math.max(16, cy - 80),
      left: targetRect.left - PAD - TOOLTIP_GAP - ARROW_SIZE - TOOLTIP_W,
    };
    arrowStyle = {
      top: cy - ARROW_SIZE / 2,
      left: targetRect.left - PAD - TOOLTIP_GAP + 2,
    };
    arrowRotation = "270deg";
  }

  // Spotlight clip-path (invert: darken everything except the target)
  const spotX = targetRect.left - PAD;
  const spotY = targetRect.top - PAD;
  const spotW = targetRect.width + PAD * 2;
  const spotH = targetRect.height + PAD * 2;
  const radius = 12;

  return (
    <div
      className={`fixed inset-0 z-[100] transition-opacity duration-300 ${
        visible ? "opacity-100" : "opacity-0 pointer-events-none"
      }`}
    >
      {/* Dark overlay with spotlight cutout */}
      <svg className="absolute inset-0 w-full h-full" style={{ pointerEvents: "auto" }}>
        <defs>
          <mask id="wt-mask">
            <rect width="100%" height="100%" fill="white" />
            <rect
              x={spotX}
              y={spotY}
              width={spotW}
              height={spotH}
              rx={radius}
              ry={radius}
              fill="black"
            />
          </mask>
        </defs>
        <rect
          width="100%"
          height="100%"
          fill="var(--overlay)"
          mask="url(#wt-mask)"
        />
      </svg>

      {/* Spotlight border glow */}
      <div
        className="absolute rounded-xl border-2 border-accent/60 pointer-events-none transition-all duration-300"
        style={{
          top: spotY,
          left: spotX,
          width: spotW,
          height: spotH,
          boxShadow: "0 0 20px oklch(var(--c-accent) / 0.3), inset 0 0 20px oklch(var(--c-accent) / 0.05)",
        }}
      />

      {/* Animated arrow */}
      <div
        className="absolute pointer-events-none animate-bounce-subtle"
        style={{
          ...arrowStyle,
          transform: `rotate(${arrowRotation})`,
        }}
      >
        <svg
          width={ARROW_SIZE * 2}
          height={ARROW_SIZE * 2}
          viewBox="0 0 24 24"
          fill="none"
          className="-translate-x-1/4 -translate-y-1/4"
        >
          <path
            d="M12 4L6 14h12L12 4z"
            fill="var(--accent)"
            opacity="0.9"
          />
        </svg>
      </div>

      {/* Tooltip card */}
      <div
        className="absolute bg-surface-100 rounded-2xl border border-themed shadow-2xl p-5 transition-all duration-300"
        style={{
          ...tooltipStyle,
          width: TOOLTIP_W,
          pointerEvents: "auto",
        }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-start justify-between mb-3">
          <div className="flex items-center gap-2">
            <div className="w-7 h-7 rounded-lg bg-accent/15 flex items-center justify-center flex-shrink-0">
              <Sparkles className="w-4 h-4 text-accent" />
            </div>
            <h3 className="text-sm font-semibold text-primary leading-tight">
              {currentStep.title}
            </h3>
          </div>
          <button
            onClick={skipAll}
            className="p-1 hover:bg-surface-200 rounded-lg transition-colors flex-shrink-0"
            title="Skip tutorial"
          >
            <X className="w-3.5 h-3.5 text-muted" />
          </button>
        </div>

        {/* Description */}
        <p className="text-xs text-t-secondary leading-relaxed mb-4">
          {currentStep.description}
        </p>

        {/* Footer: progress dots + nav buttons */}
        <div className="flex items-center justify-between">
          {/* Progress dots */}
          <div className="flex items-center gap-1.5">
            {Array.from({ length: totalSteps }).map((_, i) => (
              <div
                key={i}
                className={`w-1.5 h-1.5 rounded-full transition-colors ${
                  i === currentStepIndex
                    ? "bg-accent"
                    : i < currentStepIndex
                    ? "bg-accent/40"
                    : "bg-surface-300"
                }`}
              />
            ))}
          </div>

          {/* Nav buttons */}
          <div className="flex items-center gap-1.5">
            <button
              onClick={skipAll}
              className="px-2.5 py-1 text-[10px] text-muted hover:text-t-secondary transition-colors"
            >
              Skip
            </button>
            {currentStepIndex > 0 && (
              <button
                onClick={prevStep}
                className="p-1.5 rounded-lg bg-surface-200 hover:bg-surface-300 transition-colors"
              >
                <ChevronLeft className="w-3.5 h-3.5 text-t-secondary" />
              </button>
            )}
            <button
              onClick={nextStep}
              className="flex items-center gap-1 px-3 py-1.5 rounded-lg bg-accent text-accent-foreground text-xs font-medium hover:opacity-90 transition-opacity"
            >
              {currentStepIndex === totalSteps - 1 ? "Done" : "Next"}
              {currentStepIndex < totalSteps - 1 && (
                <ChevronRight className="w-3.5 h-3.5" />
              )}
            </button>
          </div>
        </div>
      </div>

      {/* CSS for bounce animation */}
      <style jsx global>{`
        @keyframes bounce-subtle {
          0%, 100% { transform: translateY(0) rotate(var(--arrow-rot, 0deg)); }
          50% { transform: translateY(-4px) rotate(var(--arrow-rot, 0deg)); }
        }
        .animate-bounce-subtle {
          animation: bounce-subtle 1.5s ease-in-out infinite;
        }
      `}</style>
    </div>
  );
}
