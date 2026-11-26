import { NavLink } from "react-router-dom";
import { useRepo } from "../context/RepoContext";
import {
  AssistantIcon,
  DashboardIcon,
  FolderIcon,
  GraphIcon,
  HomeIcon,
  ReportIcon,
  SearchIcon,
} from "./Icons";

const NAV_ITEMS = [
  { to: "/", label: "Repositories", Icon: HomeIcon },
  { to: "/dashboard", label: "Overview", Icon: DashboardIcon },
  { to: "/report", label: "Analysis Report", Icon: ReportIcon },
  { to: "/explorer", label: "File Explorer", Icon: FolderIcon },
  { to: "/dependencies", label: "Dependencies", Icon: GraphIcon },
  { to: "/search", label: "Semantic Search", Icon: SearchIcon },
  { to: "/assistant", label: "AI Assistant", Icon: AssistantIcon },
];

export default function Sidebar({ isOpen, onClose }) {
  const { selectedRepo } = useRepo();

  return (
    <>
      {isOpen && (
        <div
          className="fixed inset-0 z-30 bg-black/70 lg:hidden"
          onClick={onClose}
          aria-hidden="true"
        />
      )}

      <aside
        className={`fixed inset-y-0 left-0 z-40 flex w-60 shrink-0 flex-col border-r border-zinc-800/80 bg-[#0b0b0e] transition-transform duration-150 ease-out lg:static lg:translate-x-0 ${
          isOpen ? "translate-x-0" : "-translate-x-full"
        }`}
      >
        <div className="flex h-14 items-center justify-between border-b border-zinc-800/80 px-4">
          <div className="flex items-center gap-2.5">
            <div className="flex h-6 w-6 items-center justify-center rounded border border-zinc-700 bg-zinc-100 text-[11px] font-bold tracking-tight text-zinc-950">
              RS
            </div>
            <span className="text-sm font-semibold tracking-tight text-zinc-100">RepoSense</span>
            <span className="rounded border border-zinc-800 bg-zinc-900 px-1.5 py-0.5 font-mono text-[10px] text-zinc-400">
              AI
            </span>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded p-1 text-zinc-400 hover:bg-zinc-800 hover:text-zinc-100 lg:hidden"
            aria-label="Close navigation"
          >
            <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
              <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        <nav className="flex-1 space-y-0.5 overflow-y-auto px-2.5 py-3" aria-label="Main navigation">
          <p className="px-2.5 pb-1.5 text-[11px] font-medium uppercase tracking-wider text-zinc-500">
            Workspace
          </p>
          {NAV_ITEMS.map(({ to, label, Icon }) => (
            <NavLink
              key={to}
              to={to}
              end={to === "/"}
              onClick={onClose}
              className={({ isActive }) =>
                `flex items-center gap-2.5 rounded-md px-2.5 py-1.5 text-[13px] font-medium transition-colors ${
                  isActive
                    ? "bg-zinc-800/80 text-white"
                    : "text-zinc-400 hover:bg-zinc-900 hover:text-zinc-100"
                }`
              }
            >
              <Icon className="h-4 w-4 shrink-0" />
              <span className="truncate">{label}</span>
            </NavLink>
          ))}
        </nav>

        <div className="border-t border-zinc-800/80 p-3">
          <div className="rounded-md border border-zinc-800/80 bg-[#09090b] px-3 py-2">
            <p className="text-[11px] font-medium text-zinc-500">Active repository</p>
            {selectedRepo ? (
              <div className="mt-1 flex items-center justify-between gap-2">
                <span
                  className="truncate font-mono text-xs text-zinc-200"
                  title={`${selectedRepo.owner}/${selectedRepo.name}`}
                >
                  {selectedRepo.owner}/{selectedRepo.name}
                </span>
                <span
                  className={`h-1.5 w-1.5 shrink-0 rounded-full ${
                    selectedRepo.status === "completed"
                      ? "bg-emerald-400"
                      : selectedRepo.status === "failed"
                      ? "bg-red-400"
                      : "bg-amber-400"
                  }`}
                  title={selectedRepo.status}
                />
              </div>
            ) : (
              <p className="mt-1 text-xs text-zinc-500">None selected</p>
            )}
          </div>
        </div>
      </aside>
    </>
  );
}
