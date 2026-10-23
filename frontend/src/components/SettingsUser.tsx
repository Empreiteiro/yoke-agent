"use client";

import { User, Sun, Moon, Zap, LogOut, Check } from "lucide-react";
import { useTheme, Theme, Accent } from "@/contexts/ThemeContext";
import { useAuth } from "@/contexts/AuthContext";
import { cn } from "@/lib/utils";

const THEMES: { key: Theme; icon: any; label: string; description: string }[] = [
  { key: "light", icon: Sun, label: "Light", description: "Bright surfaces with high contrast text" },
  { key: "dark", icon: Moon, label: "Dark", description: "Dimmed surfaces, easier on the eyes" },
  { key: "neon", icon: Zap, label: "Neon", description: "Vibrant accents on a deep background" },
];

// Swatch colors are the light-theme accent values from globals.css.
const ACCENT_SWATCHES: { key: Accent; label: string; color: string }[] = [
  { key: "violet", label: "Violet", color: "#7747ff" },
  { key: "blue", label: "Blue", color: "#0562ef" },
  { key: "green", label: "Green", color: "#0db879" },
  { key: "amber", label: "Amber", color: "#f3ad20" },
  { key: "orange", label: "Orange", color: "#f48120" },
  { key: "coral", label: "Coral", color: "#f15f55" },
  { key: "rose", label: "Rose", color: "#ed4e9d" },
  // Split swatch: neutral is near-black in light themes and near-white in dark ones.
  { key: "neutral", label: "Neutral", color: "linear-gradient(135deg, #3a3a3a 50%, #d4d4d4 50%)" },
];

// Miniature of the app shell, painted with the theme's own surfaces.
function ThemePreview({ theme, accent }: { theme: Theme; accent: Accent }) {
  return (
    <div data-theme={theme} data-accent={accent} className="h-20 rounded-xl border border-themed bg-surface p-2 flex gap-1.5 overflow-hidden">
      <div className="w-1/4 space-y-1 pt-1">
        <div className="h-1.5 w-3/4 rounded-full bg-surface-300" />
        <div className="h-1.5 w-full rounded-full bg-accent/70" />
        <div className="h-1.5 w-2/3 rounded-full bg-surface-200" />
        <div className="h-1.5 w-3/4 rounded-full bg-surface-200" />
      </div>
      <div className="flex-1 rounded-lg border border-themed bg-surface-100 p-2 space-y-1.5">
        <div className="h-2 w-1/2 rounded-full bg-primary/80" />
        <div className="h-1.5 w-3/4 rounded-full bg-surface-200" />
        <div className="h-4 w-12 rounded-md bg-accent mt-2" />
      </div>
    </div>
  );
}

export default function SettingsUser() {
  const { theme, setTheme, accent, setAccent } = useTheme();
  const { user, logout } = useAuth();

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-3">
        <div className="w-10 h-10 rounded-xl bg-accent/10 flex items-center justify-center">
          <User className="w-5 h-5 text-accent" />
        </div>
        <div>
          <h2 className="text-lg font-semibold text-primary">User Preferences</h2>
          <p className="text-sm text-t-secondary">
            Personalize how Yoke Agent looks and feels for you.
          </p>
        </div>
      </div>

      {/* Account (issue #123) */}
      {user && (
        <div className="bg-surface-100 rounded-2xl border border-themed p-6 flex items-center justify-between">
          <div>
            <h3 className="text-sm font-semibold text-primary">Account</h3>
            <p className="text-xs text-t-secondary mt-1">
              Signed in as <span className="text-primary font-medium">{user.email}</span> · role:{" "}
              <span className="text-accent capitalize">{user.role}</span>
            </p>
          </div>
          <button
            onClick={() => {
              logout();
              window.location.reload();
            }}
            className="flex items-center gap-1.5 h-9 px-3 text-xs font-medium text-danger bg-surface-100 border border-themed rounded-lg hover:border-danger hover:bg-surface-50 transition-colors"
          >
            <LogOut className="w-3.5 h-3.5" />
            Sign out
          </button>
        </div>
      )}

      {/* ─── Appearance ─── */}
      <div className="bg-surface-100 rounded-2xl border border-themed p-6">
        <div className="mb-4">
          <h3 className="text-sm font-semibold text-primary">Theme</h3>
          <p className="text-xs text-t-secondary mt-1">
            Choose the theme that suits your environment. Your selection is saved locally.
          </p>
        </div>

        <div role="radiogroup" aria-label="Theme" className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          {THEMES.map(({ key, icon: ThemeIcon, label, description }) => {
            const isActive = theme === key;
            return (
              <button
                key={key}
                type="button"
                role="radio"
                onClick={() => setTheme(key)}
                className={cn(
                  "text-left p-2 rounded-2xl border transition-[border-color,box-shadow,background-color]",
                  isActive
                    ? "border-accent/60 bg-accent/5 shadow-raised"
                    : "border-themed bg-surface-50 hover:border-themed-strong hover:shadow-resting"
                )}
                aria-checked={isActive}
              >
                <ThemePreview theme={key} accent={accent} />
                <div className="px-2 pt-3 pb-1.5">
                  <div className="flex items-center gap-2 mb-1">
                    <ThemeIcon className={cn("w-4 h-4", isActive ? "text-accent" : "text-muted")} />
                    <span className="text-sm font-medium text-primary">{label}</span>
                    {isActive && <Check className="w-3.5 h-3.5 text-accent ml-auto" />}
                  </div>
                  <p className="text-xs text-t-secondary leading-relaxed">{description}</p>
                </div>
              </button>
            );
          })}
        </div>
      </div>

      <div className="bg-surface-100 rounded-2xl border border-themed p-6">
        <div className="mb-4">
          <h3 className="text-sm font-semibold text-primary">Accent color</h3>
          <p className="text-xs text-t-secondary mt-1">
            Used for buttons, selections and highlights. Each accent is tuned separately for light and dark themes.
          </p>
        </div>
        <div role="radiogroup" aria-label="Accent color" className="flex flex-wrap gap-2">
          {ACCENT_SWATCHES.map(({ key, label, color }) => {
            const isActive = accent === key;
            return (
              <button
                key={key}
                type="button"
                role="radio"
                aria-checked={isActive}
                onClick={() => setAccent(key)}
                className={cn(
                  "flex items-center gap-2 h-9 pl-2 pr-3 rounded-full border text-xs font-medium transition-colors",
                  isActive
                    ? "border-accent/60 bg-accent/10 text-primary"
                    : "border-themed bg-surface-50 text-t-secondary hover:text-primary hover:border-themed-strong"
                )}
              >
                <span
                  className="w-5 h-5 rounded-full flex items-center justify-center shadow-resting"
                  style={{ background: color }}
                >
                  {isActive && <Check className="w-3 h-3 text-white" strokeWidth={3} />}
                </span>
                {label}
              </button>
            );
          })}
        </div>
      </div>
    </div>
  );
}
