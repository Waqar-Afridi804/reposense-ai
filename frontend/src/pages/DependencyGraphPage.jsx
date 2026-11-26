import { useEffect, useId, useRef, useState } from "react";
import { api } from "../api/client";
import { EmptyRepoState, ErrorBanner, LoadingSpinner } from "../components/StatusAlert";
import { useRepo } from "../context/RepoContext";

let mermaidInitialized = false;

function sanitizeSvg(rawSvg) {
  if (!rawSvg) return "";
  const parser = new DOMParser();
  const doc = parser.parseFromString(rawSvg, "image/svg+xml");
  const svg = doc.querySelector("svg");
  if (!svg) return "";
  doc.querySelectorAll("script, foreignObject").forEach((el) => el.remove());
  doc.querySelectorAll("*").forEach((el) => {
    for (const attr of [...el.attributes]) {
      if (attr.name.toLowerCase().startsWith("on") || attr.value.trim().toLowerCase().startsWith("javascript:")) {
        el.removeAttribute(attr.name);
      }
    }
  });
  return svg.outerHTML;
}

export default function DependencyGraphPage() {
  const { selectedRepo } = useRepo();
  const [deps, setDeps] = useState(null);
  const [svgMarkup, setSvgMarkup] = useState("");
  const [renderError, setRenderError] = useState("");
  const [edgeFilter, setEdgeFilter] = useState("all");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const diagramId = useId().replace(/:/g, "_");
  const renderCounter = useRef(0);

  useEffect(() => {
    if (!selectedRepo?.id) return;
    let active = true;
    setLoading(true);
    setError("");
    setSvgMarkup("");

    api
      .getRepositoryDependencies(selectedRepo.id)
      .then(async (data) => {
        if (!active) return;
        setDeps(data);
        if (data?.mermaid) {
          try {
            const { default: mermaid } = await import("mermaid");
            if (!mermaidInitialized) {
              mermaid.initialize({
                startOnLoad: false,
                theme: "dark",
                securityLevel: "strict",
                flowchart: { curve: "basis" },
              });
              mermaidInitialized = true;
            }
            renderCounter.current += 1;
            const { svg } = await mermaid.render(`dep_graph_${diagramId}_${renderCounter.current}`, data.mermaid);
            if (active) {
              setSvgMarkup(sanitizeSvg(svg));
              setRenderError("");
            }
          } catch {
            if (active) setRenderError("Mermaid could not render this graph SVG. Inspect the structured edge table below.");
          }
        }
      })
      .catch((err) => {
        if (!active) return;
        setDeps(null);
        setError(err.message || "Failed to load dependency graph.");
      })
      .finally(() => {
        if (active) setLoading(false);
      });

    return () => {
      active = false;
    };
  }, [selectedRepo?.id, diagramId]);

  if (!selectedRepo) {
    return <EmptyRepoState title="No repository selected" />;
  }

  if (loading) {
    return <LoadingSpinner label="Loading dependency graph..." />;
  }

  const edges = deps?.edges || [];
  const filteredEdges = edges.filter((e) => {
    if (edgeFilter === "internal") return e.target_type === "internal";
    if (edgeFilter === "external") return e.target_type !== "internal";
    return true;
  });

  return (
    <div className="space-y-5">
      <ErrorBanner message={error} />

      {deps && (
        <>
          {/* Summary Strip */}
          <section className="grid grid-cols-1 divide-y divide-zinc-800/80 rounded-lg border border-zinc-800/80 bg-[#0b0b0e] sm:grid-cols-3 sm:divide-x sm:divide-y-0">
            <div className="px-4 py-3.5">
              <p className="text-[11px] font-medium text-zinc-500">Graph Nodes</p>
              <p className="mt-1 font-mono text-xl font-semibold text-zinc-100 tabular-nums">
                {deps.nodes.length}
              </p>
            </div>
            <div className="px-4 py-3.5">
              <p className="text-[11px] font-medium text-zinc-500">Internal Module Edges</p>
              <p className="mt-1 font-mono text-xl font-semibold text-emerald-400 tabular-nums">
                {deps.internal_dependency_count}
              </p>
            </div>
            <div className="px-4 py-3.5">
              <p className="text-[11px] font-medium text-zinc-500">External / Unresolved Packages</p>
              <p className="mt-1 font-mono text-xl font-semibold text-amber-400 tabular-nums">
                {deps.external_dependencies.length}
              </p>
            </div>
          </section>

          {/* Mermaid Graph */}
          <section className="rounded-lg border border-zinc-800/80 bg-[#0b0b0e] p-5">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <h2 className="text-xs font-semibold uppercase tracking-wider text-zinc-400">
                Dependency Flowchart
              </h2>
              <span className="font-mono text-[11px] text-zinc-500">
                Solid = internal · Dashed = external/unresolved
              </span>
            </div>
            {edges.length > 60 && (
              <p className="mt-2 text-xs text-amber-300">
                Large graph ({edges.length} edges). Rendering the top 60 prioritized edges in the flowchart; all edges are listed below.
              </p>
            )}
            {renderError && <p className="mt-3 text-xs text-red-400">{renderError}</p>}
            {svgMarkup && (
              <div
                className="mt-4 max-h-[520px] overflow-auto rounded-md border border-zinc-800/80 bg-[#09090b] p-4"
                dangerouslySetInnerHTML={{ __html: svgMarkup }}
              />
            )}
          </section>

          {/* Edge Table */}
          <section className="rounded-lg border border-zinc-800/80 bg-[#0b0b0e]">
            <div className="flex flex-wrap items-center justify-between gap-3 border-b border-zinc-800/80 px-5 py-3.5">
              <h3 className="text-xs font-semibold uppercase tracking-wider text-zinc-400">
                Detected Relationships ({filteredEdges.length})
              </h3>
              <div className="flex gap-1.5">
                {["all", "internal", "external"].map((mode) => (
                  <button
                    key={mode}
                    type="button"
                    onClick={() => setEdgeFilter(mode)}
                    className={`rounded px-2.5 py-1 text-xs font-medium capitalize transition-colors ${
                      edgeFilter === mode
                        ? "bg-zinc-100 text-zinc-950"
                        : "border border-zinc-800 bg-[#09090b] text-zinc-400 hover:text-zinc-200"
                    }`}
                  >
                    {mode}
                  </button>
                ))}
              </div>
            </div>

            <div className="max-h-80 overflow-auto">
              <table className="w-full text-left text-xs">
                <thead className="sticky top-0 border-b border-zinc-800 bg-[#0b0b0e] text-[11px] text-zinc-500">
                  <tr>
                    <th className="px-5 py-2.5 font-medium">Source Module</th>
                    <th className="px-4 py-2.5 font-medium">Target</th>
                    <th className="px-4 py-2.5 font-medium">Classification</th>
                    <th className="px-5 py-2.5 font-medium">Lines</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-zinc-800/60 text-zinc-300">
                  {filteredEdges.map((edge, idx) => (
                    <tr key={`${edge.source}-${edge.target}-${idx}`} className="hover:bg-zinc-900/30">
                      <td className="px-5 py-2 font-mono text-[11px]">{edge.source}</td>
                      <td className="px-4 py-2 font-mono text-[11px]">{edge.target.replace(/^ext:/, "")}</td>
                      <td className="px-4 py-2">
                        <span
                          className={`rounded border px-1.5 py-0.5 text-[11px] ${
                            edge.target_type === "internal"
                              ? "border-emerald-500/25 bg-emerald-950/20 text-emerald-300"
                              : "border-amber-500/25 bg-amber-950/20 text-amber-300"
                          }`}
                        >
                          {edge.target_type === "internal" ? "Internal" : "External / Unresolved"}
                        </span>
                      </td>
                      <td className="px-5 py-2 font-mono text-[11px] text-zinc-500 tabular-nums">
                        {(edge.line_numbers || []).join(", ")}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        </>
      )}
    </div>
  );
}
