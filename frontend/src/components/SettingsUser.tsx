"use client";

import { User, Sun, Moon, Zap } from "lucide-react";
import { useTheme, Theme } from "@/contexts/ThemeContext";
import { cn } from "@/lib/utils";

const THEMES: { key: Theme; icon: any; label: string; description: string }[] = [
  { key: "light", icon: Sun, label: "Light", description: "Bright surfaces with high contrast text" },
  { key: "dark", icon: Moon, label: "Dark", description: "Dimmed surfaces, easier on the eyes" },
  { key: "neon", icon: Zap, label: "Neon", description: "Vibrant accents on a deep background" },
];

export default function SettingsUser() {
  const { theme, setTheme } = useTheme();

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="flex items-center gap-3">
        <div
          className="w-10 h-10 rounded-xl flex items-center justify-center"
          style={{ backgroundColor: "color-mix(in srgb, var(--accent) 12%, transparent)" }}
        >
          <User className="w-5 h-5 text-accent" />
        </div>
        <div>
          <h2 className="text-lg font-semibold text-primary">User Preferences</h2>
          <p className="text-sm text-t-secondary">
            Personalize how Yoke Agent looks and feels for you.
          </p>
        </div>
      </div>

      {/* ─── Appearance ─── */}
      <div className="bg-surface-100 rounded-2xl border border-surface-200/50 p-6">
        <div className="mb-4">
          <h3 className="text-sm font-semibold text-primary">Appearance</h3>
          <p className="text-xs text-t-secondary mt-1">
            Choose the theme that suits your environment. Your selection is saved locally.
          </p>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          {THEMES.map(({ key, icon: ThemeIcon, label, description }) => {
            const isActive = theme === key;
            return (
              <button
                key={key}
                type="button"
                onClick={() => setTheme(key)}
                className={cn(
                  "text-left p-4 rounded-xl border transition-all duration-200",
                  isActive
                    ? "theme-card-active"
                    : "border-surface-200/50 bg-surface-50 hover:border-surface-200 hover:bg-surface-100"
                )}
                aria-pressed={isActive}
              >
                <div className="flex items-center gap-2 mb-2">
                  <div
                    className={cn(
                      "w-7 h-7 rounded-lg flex items-center justify-center",
                      isActive ? "text-accent" : "bg-surface-200 text-muted"
                    )}
                    style={
                      isActive
                        ? { backgroundColor: "color-mix(in srgb, var(--accent) 20%, transparent)" }
                        : undefined
                    }
                  >
                    <ThemeIcon className="w-4 h-4" />
                  </div>
                  <span
                    className={cn(
                      "text-sm font-medium",
                      isActive ? "text-accent" : "text-primary"
                    )}
                  >
                    {label}
                  </span>
                </div>
                <p className="text-xs text-t-secondary leading-relaxed">{description}</p>
              </button>
            );
          })}
        </div>
      </div>
    </div>
  );
}
