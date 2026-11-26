import { Link } from "react-router-dom";

export function ErrorBanner({ message, onRetry }) {
  if (!message) return null;
  return (
    <div
      role="alert"
      className="flex flex-wrap items-center justify-between gap-3 rounded-md border border-red-500/30 bg-red-950/30 px-4 py-3 text-xs text-red-200"
    >
      <span>{message}</span>
      {onRetry && (
        <button
          type="button"
          onClick={onRetry}
          className="rounded border border-red-500/40 bg-red-500/10 px-2.5 py-1 text-xs font-medium text-red-100 transition-colors hover:bg-red-500/20"
        >
          Retry
        </button>
      )}
    </div>
  );
}

export function EmptyRepoState({ title = "No repository selected" }) {
  return (
    <div className="rounded-lg border border-dashed border-zinc-800 bg-[#0f0f12] px-6 py-12 text-center">
      <h2 className="text-sm font-medium text-zinc-100">{title}</h2>
      <p className="mx-auto mt-1.5 max-w-md text-xs text-zinc-400">
        Register and analyze a public GitHub repository from the Workspace home to inspect files, dependencies, semantic search, and AI Q&amp;A.
      </p>
      <Link
        to="/"
        className="mt-4 inline-flex items-center rounded-md bg-zinc-100 px-3.5 py-1.5 text-xs font-medium text-zinc-950 transition-colors hover:bg-white"
      >
        Select Repository
      </Link>
    </div>
  );
}

export function LoadingSpinner({ label = "Loading..." }) {
  return (
    <div className="flex items-center justify-center gap-2.5 py-10 text-xs text-zinc-400">
      <span className="h-4 w-4 animate-spin rounded-full border-2 border-zinc-700 border-t-zinc-200" />
      <span>{label}</span>
    </div>
  );
}
