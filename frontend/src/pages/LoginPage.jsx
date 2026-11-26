import { useState } from "react";
import { Navigate } from "react-router-dom";
import { GoogleLogo } from "../components/Icons";
import { ErrorBanner } from "../components/StatusAlert";
import { useAuth } from "../context/AuthContext";

export default function LoginPage() {
  const { isAuthenticated, isConfigured, loading, authError, signInWithGoogle } = useAuth();
  const [submitting, setSubmitting] = useState(false);

  if (!loading && isAuthenticated) {
    return <Navigate to="/" replace />;
  }

  async function handleGoogleLogin() {
    setSubmitting(true);
    try {
      await signInWithGoogle();
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-[#09090b] px-4 py-12 text-zinc-100">
      <div className="w-full max-w-sm">
        <div className="mb-8 flex items-center gap-2.5">
          <div className="flex h-7 w-7 items-center justify-center rounded border border-zinc-700 bg-zinc-100 text-xs font-bold tracking-tight text-zinc-950">
            RS
          </div>
          <span className="text-base font-semibold tracking-tight text-zinc-100">RepoSense</span>
          <span className="rounded border border-zinc-800 bg-zinc-900 px-1.5 py-0.5 font-mono text-[10px] text-zinc-400">
            AI
          </span>
        </div>

        <div className="rounded-lg border border-zinc-800/80 bg-[#0b0b0e] p-6">
          <h1 className="text-base font-semibold tracking-tight text-zinc-100">
            Sign in to RepoSense AI
          </h1>
          <p className="mt-1.5 text-xs leading-relaxed text-zinc-400">
            Use your Google account to access repository analysis, semantic code search, and the Gemini RAG assistant.
          </p>

          <div className="mt-4">
            <ErrorBanner message={authError} />
          </div>

          <button
            type="button"
            onClick={handleGoogleLogin}
            disabled={loading || submitting || !isConfigured}
            className="mt-5 flex w-full items-center justify-center gap-2.5 rounded-md border border-zinc-700 bg-zinc-100 px-4 py-2.5 text-xs font-semibold text-zinc-950 transition-colors hover:bg-white disabled:cursor-not-allowed disabled:opacity-50"
          >
            <GoogleLogo className="h-4 w-4 shrink-0" />
            <span>{submitting ? "Redirecting to Google..." : "Continue with Google"}</span>
          </button>

          <p className="mt-4 text-[11px] leading-relaxed text-zinc-500">
            Secured via Supabase OAuth 2.0. RepoSense AI never asks for or stores your Google password.
          </p>
        </div>
      </div>
    </div>
  );
}
