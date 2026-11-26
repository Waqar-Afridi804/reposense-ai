import { useEffect, useState } from "react";
import { api } from "../api/client";
import { EmptyRepoState, ErrorBanner, LoadingSpinner } from "../components/StatusAlert";
import { useRepo } from "../context/RepoContext";

export default function AnalysisReportPage() {
  const { selectedRepo } = useRepo();
  const [analysis, setAnalysis] = useState(null);
  const [deps, setDeps] = useState(null);
  const [filter, setFilter] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!selectedRepo?.id) return;
    let active = true;
    setLoading(true);
    setError("");

    Promise.all([
      api.getRepositoryAnalysis(selectedRepo.id),
      api.getRepositoryDependencies(selectedRepo.id).catch(() => null),
    ])
      .then(([an, dep]) => {
        if (!active) return;
        setAnalysis(an);
        setDeps(dep);
      })
      .catch((err) => {
        if (!active) return;
        setAnalysis(null);
        setError(err.message || "Failed to load analysis report.");
      })
      .finally(() => {
        if (active) setLoading(false);
      });

    return () => {
      active = false;
    };
  }, [selectedRepo?.id]);

  if (!selectedRepo) {
    return <EmptyRepoState title="No repository selected" />;
  }

  if (loading) {
    return <LoadingSpinner label="Loading analysis report..." />;
  }

  const astFiles = (analysis?.ast_details?.files || []).filter((f) =>
    f.file_path.toLowerCase().includes(filter.toLowerCase())
  );

  return (
    <div className="space-y-5">
      <ErrorBanner message={error} />

      {/* Repository Metadata */}
      <section className="rounded-lg border border-zinc-800/80 bg-[#0b0b0e] p-5">
        <h2 className="text-xs font-semibold uppercase tracking-wider text-zinc-400">
          Repository Overview
        </h2>
        <dl className="mt-4 grid grid-cols-1 gap-4 text-xs sm:grid-cols-2 lg:grid-cols-3">
          <div>
            <dt className="text-zinc-500">Repository</dt>
            <dd className="mt-1 font-mono font-medium text-zinc-100">
              <a
                href={selectedRepo.github_url}
                target="_blank"
                rel="noreferrer"
                className="hover:underline"
              >
                {selectedRepo.owner}/{selectedRepo.name}
              </a>
            </dd>
          </div>
          <div>
            <dt className="text-zinc-500">Primary Language / Branch</dt>
            <dd className="mt-1 font-mono text-zinc-200">
              {selectedRepo.primary_language || "Unknown"} · {selectedRepo.default_branch || "main"}
            </dd>
          </div>
          <div>
            <dt className="text-zinc-500">Analysis Status</dt>
            <dd className="mt-1 capitalize text-zinc-200">{analysis?.status || selectedRepo.status}</dd>
          </div>
          <div>
            <dt className="text-zinc-500">Stars / Forks</dt>
            <dd className="mt-1 font-mono text-zinc-200 tabular-nums">
              {selectedRepo.stars_count} stars · {selectedRepo.forks_count} forks
            </dd>
          </div>
          <div>
            <dt className="text-zinc-500">GitHub Created / Updated</dt>
            <dd className="mt-1 font-mono text-zinc-200 tabular-nums">
              {selectedRepo.github_created_at ? new Date(selectedRepo.github_created_at).toLocaleDateString() : "—"} /{" "}
              {selectedRepo.github_updated_at ? new Date(selectedRepo.github_updated_at).toLocaleDateString() : "—"}
            </dd>
          </div>
          <div>
            <dt className="text-zinc-500">Last Analyzed</dt>
            <dd className="mt-1 font-mono text-zinc-200 tabular-nums">
              {selectedRepo.last_analyzed_at ? new Date(selectedRepo.last_analyzed_at).toLocaleString() : "Not yet"}
            </dd>
          </div>
        </dl>

        {analysis?.summary && (
          <div className="mt-4 rounded-md border border-zinc-800/80 bg-[#09090b] p-3.5 text-xs leading-relaxed text-zinc-300">
            {analysis.summary}
          </div>
        )}
      </section>

      {analysis && (
        <>
          {/* Statistics & Dependencies */}
          <section className="grid grid-cols-1 gap-5 lg:grid-cols-2">
            <div className="rounded-lg border border-zinc-800/80 bg-[#0b0b0e] p-5">
              <h3 className="text-xs font-semibold uppercase tracking-wider text-zinc-400">
                Code &amp; Language Statistics
              </h3>
              <div className="mt-4 grid grid-cols-2 divide-x divide-y divide-zinc-800/80 rounded-md border border-zinc-800/80 bg-[#09090b] text-xs">
                <div className="p-3">
                  <span className="text-[11px] text-zinc-500">Python Files</span>
                  <p className="mt-1 font-mono text-base font-semibold text-zinc-100 tabular-nums">
                    {analysis.python_files_count}
                  </p>
                </div>
                <div className="p-3">
                  <span className="text-[11px] text-zinc-500">Other Supported</span>
                  <p className="mt-1 font-mono text-base font-semibold text-zinc-100 tabular-nums">
                    {analysis.other_supported_files_count}
                  </p>
                </div>
                <div className="p-3">
                  <span className="text-[11px] text-zinc-500">Classes</span>
                  <p className="mt-1 font-mono text-base font-semibold text-zinc-100 tabular-nums">
                    {analysis.total_classes}
                  </p>
                </div>
                <div className="p-3">
                  <span className="text-[11px] text-zinc-500">Functions / Methods</span>
                  <p className="mt-1 font-mono text-base font-semibold text-zinc-100 tabular-nums">
                    {analysis.total_functions} / {analysis.total_methods}
                  </p>
                </div>
              </div>
              <div className="mt-4 flex flex-wrap gap-1.5">
                {Object.entries(analysis.language_stats || {}).map(([lang, count]) => (
                  <span
                    key={lang}
                    className="rounded border border-zinc-800 bg-[#09090b] px-2 py-0.5 font-mono text-[11px] text-zinc-300"
                  >
                    {lang}: {count}
                  </span>
                ))}
              </div>
            </div>

            <div className="rounded-lg border border-zinc-800/80 bg-[#0b0b0e] p-5">
              <h3 className="text-xs font-semibold uppercase tracking-wider text-zinc-400">
                Dependency Summary
              </h3>
              {deps ? (
                <>
                  <p className="mt-2 font-mono text-xs text-zinc-400 tabular-nums">
                    {deps.internal_dependency_count} internal module edges · {deps.external_dependencies.length} external/unresolved packages
                  </p>
                  <div className="mt-3 flex max-h-48 flex-wrap gap-1.5 overflow-y-auto">
                    {deps.external_dependencies.map((pkg) => (
                      <span
                        key={pkg}
                        className="rounded border border-amber-500/25 bg-amber-950/20 px-2 py-0.5 font-mono text-[11px] text-amber-300"
                      >
                        {pkg}
                      </span>
                    ))}
                  </div>
                </>
              ) : (
                <p className="mt-2 text-xs text-zinc-500">No dependency data available.</p>
              )}
            </div>
          </section>

          {/* Detected Python AST Structures */}
          <section className="rounded-lg border border-zinc-800/80 bg-[#0b0b0e]">
            <div className="flex flex-col justify-between gap-3 border-b border-zinc-800/80 px-5 py-3.5 sm:flex-row sm:items-center">
              <h3 className="text-xs font-semibold uppercase tracking-wider text-zinc-400">
                Python AST Structures ({astFiles.length} files)
              </h3>
              <input
                type="text"
                value={filter}
                onChange={(e) => setFilter(e.target.value)}
                placeholder="Filter by file path..."
                className="rounded-md border border-zinc-800 bg-[#09090b] px-3 py-1.5 font-mono text-xs text-zinc-100 placeholder-zinc-500 focus:border-zinc-600 focus:outline-none sm:w-64"
              />
            </div>

            <div className="max-h-[460px] divide-y divide-zinc-800/70 overflow-y-auto">
              {astFiles.length === 0 ? (
                <p className="px-5 py-8 text-center text-xs text-zinc-500">No matching Python AST files.</p>
              ) : (
                astFiles.map((f) => (
                  <div key={f.file_path} className="px-5 py-3.5">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <span className="font-mono text-xs font-medium text-zinc-200">{f.file_path}</span>
                      <span className="font-mono text-[11px] text-zinc-500 tabular-nums">
                        {f.classes.length} classes · {f.functions.length} functions · {f.methods_count} methods
                      </span>
                    </div>
                    {f.parse_error && (
                      <p className="mt-1.5 font-mono text-[11px] text-red-400">{f.parse_error}</p>
                    )}
                    {(f.classes.length > 0 || f.functions.length > 0) && (
                      <div className="mt-2 flex flex-wrap gap-1.5">
                        {f.classes.map((c) => (
                          <span
                            key={`${f.file_path}-c-${c.name}-${c.line_start}`}
                            className="rounded border border-emerald-500/25 bg-emerald-950/20 px-2 py-0.5 font-mono text-[11px] text-emerald-300"
                          >
                            class {c.name} L{c.line_start}-{c.line_end}
                          </span>
                        ))}
                        {f.functions.map((fn) => (
                          <span
                            key={`${f.file_path}-f-${fn.name}-${fn.line_start}`}
                            className="rounded border border-sky-500/25 bg-sky-950/20 px-2 py-0.5 font-mono text-[11px] text-sky-300"
                          >
                            def {fn.name} L{fn.line_start}-{fn.line_end}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>
                ))
              )}
            </div>
          </section>
        </>
      )}
    </div>
  );
}
