"use client";

import React, { useState } from "react";
import { Loader2, Lock, UserPlus } from "lucide-react";
import { useAuth } from "@/contexts/AuthContext";
import Logo from "@/components/Logo";

/** Login / register gate (issue #123).
 *
 * Rendered before the main app when multi-tenancy is enabled and the user
 * doesn't have an active session. On a fresh install (no users exist yet),
 * `auth.bootstrap === true` and we skip this gate entirely so single-user
 * deployments keep working.
 */
export default function AuthGate({ children }: { children: React.ReactNode }) {
  const auth = useAuth();
  const [mode, setMode] = useState<"login" | "register">("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (auth.loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-surface text-sm text-t-secondary">
        <Loader2 className="w-4 h-4 animate-spin mr-2 text-muted" />
        Loading…
      </div>
    );
  }

  if (auth.user || auth.bootstrap) {
    return <>{children}</>;
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    if (!email || !password) {
      setError("Email and password are required.");
      return;
    }
    if (mode === "register" && password.length < 8) {
      setError("Password must be at least 8 characters.");
      return;
    }
    setSubmitting(true);
    try {
      if (mode === "login") {
        await auth.login(email.trim(), password);
      } else {
        await auth.register(email.trim(), password);
      }
    } catch (err: any) {
      setError(err?.message || "Authentication failed");
    } finally {
      setSubmitting(false);
    }
  };

  const inputClass =
    "w-full h-11 px-3.5 bg-surface-100 border border-visible rounded-xl text-sm text-primary focus:outline-none focus:border-accent";

  return (
    <div className="relative min-h-screen flex items-center justify-center bg-surface px-4 overflow-hidden">
      {/* Soft brand wash behind the card */}
      <div aria-hidden className="pointer-events-none absolute inset-0 bg-arc-gradient-soft opacity-80" />
      <div className="relative w-full max-w-sm bg-surface-100 rounded-3xl border border-themed shadow-floating p-8 animate-fade-up">
        <div className="flex flex-col items-center text-center mb-7">
          <div className="w-12 h-12 rounded-2xl bg-surface-50 border border-themed shadow-resting flex items-center justify-center mb-4">
            <Logo size={28} />
          </div>
          <h1 className="text-xl font-semibold text-primary leading-tight">
            {mode === "login" ? "Sign in to Yoke Agent" : "Create your account"}
          </h1>
          <p className="text-sm text-t-secondary mt-1.5">
            {mode === "login" ? "Welcome back to your AI Quality Studio." : "Start evaluating your AI pipelines."}
          </p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-primary mb-2">Email</label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              autoComplete="email"
              placeholder="you@company.com"
              className={inputClass}
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-primary mb-2">Password</label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              autoComplete={mode === "login" ? "current-password" : "new-password"}
              minLength={mode === "register" ? 8 : undefined}
              className={inputClass}
            />
            {mode === "register" && (
              <p className="pt-2 text-xs text-muted">At least 8 characters.</p>
            )}
          </div>

          {error && (
            <div role="alert" className="text-xs text-danger bg-danger/10 border border-danger/25 rounded-xl px-3 py-2.5">
              {error}
            </div>
          )}

          <button
            type="submit"
            disabled={submitting}
            className="w-full h-11 flex items-center justify-center gap-2 px-4 bg-accent text-accent-foreground text-sm font-medium rounded-xl shadow-resting hover:opacity-90 active:opacity-85 transition-opacity disabled:opacity-50"
          >
            {submitting ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : mode === "login" ? (
              <Lock className="w-4 h-4" />
            ) : (
              <UserPlus className="w-4 h-4" />
            )}
            {mode === "login" ? "Sign in" : "Create account"}
          </button>
        </form>

        <div className="mt-6 pt-5 border-t border-themed text-center text-sm text-t-secondary">
          {mode === "login" ? "Don't have an account?" : "Already registered?"}{" "}
          <button
            onClick={() => {
              setMode(mode === "login" ? "register" : "login");
              setError(null);
            }}
            className="font-medium text-primary hover:text-accent transition-colors"
          >
            {mode === "login" ? "Register" : "Sign in"}
          </button>
        </div>
      </div>
    </div>
  );
}
