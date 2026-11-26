import { useEffect, useRef, useState } from "react";
import { api } from "../api/client";
import { useAuth } from "../context/AuthContext";
import { useRepo } from "../context/RepoContext";
import { LogoutIcon } from "./Icons";

export default function Header({ title, onMenuToggle }) {
  const { repositories, selectedRepoId, selectRepository } = useRepo();
  const { user, signOut } = useAuth();
  const [backendStatus, setBackendStatus] = useState("checking");
  const [menuOpen, setMenuOpen] = useState(false);
  const menuRef = useRef(null);

  useEffect(() => {
    let active = true;
    api
      .checkHealth()
      .then(() => {
        if (active) setBackendStatus("online");
      })
      .catch(() => {
        if (active) setBackendStatus("offline");
      });
    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    function handleOutsideClick(e) {
      if (menuRef.current && !menuRef.current.contains(e.target)) {
        setMenuOpen(false);
      }
    }
    if (menuOpen) {
      document.addEventListener("mousedown", handleOutsideClick);
    }
    return () => document.removeEventListener("mousedown", handleOutsideClick);
  }, [menuOpen]);

  const initials = (user?.display_name || user?.email || "U")
    .split(/\s+/)
    .map((p) => p[0])
    .join("")
    .slice(0, 2)
    .toUpperCase();

  return (
    <header className="flex h-14 shrink-0 items-center justify-between gap-3 border-b border-zinc-800/80 bg-[#0b0b0e] px-4 sm:px-6">
      <div className="flex min-w-0 items-center gap-3">
        <button
          type="button"
          onClick={onMenuToggle}
          className="rounded p-1.5 text-zinc-400 hover:bg-zinc-800 hover:text-zinc-100 lg:hidden"
          aria-label="Open navigation"
        >
          <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
            <path strokeLinecap="round" strokeLinejoin="round" d="M4 6h16M4 12h16M4 18h16" />
          </svg>
        </button>
        <h1 className="truncate text-sm font-semibold tracking-tight text-zinc-100">{title}</h1>
      </div>

      <div className="flex items-center gap-2.5">
        {repositories.length > 0 && (
          <select
            aria-label="Active repository"
            value={selectedRepoId}
            onChange={(e) => selectRepository(e.target.value)}
            className="max-w-[160px] rounded-md border border-zinc-800 bg-[#09090b] px-2.5 py-1 font-mono text-xs text-zinc-200 focus:border-zinc-600 focus:outline-none sm:max-w-[240px]"
          >
            {repositories.map((repo) => (
              <option key={repo.id} value={repo.id}>
                {repo.owner}/{repo.name}
              </option>
            ))}
          </select>
        )}

        <div
          className="hidden items-center gap-1.5 rounded-md border border-zinc-800 bg-[#09090b] px-2.5 py-1 text-[11px] text-zinc-400 sm:inline-flex"
          title={`Backend API is ${backendStatus}`}
        >
          <span
            className={`h-1.5 w-1.5 rounded-full ${
              backendStatus === "online"
                ? "bg-emerald-400"
                : backendStatus === "offline"
                ? "bg-red-400"
                : "bg-zinc-500"
            }`}
          />
          <span className="capitalize">{backendStatus}</span>
        </div>

        {user && (
          <div className="relative" ref={menuRef}>
            <button
              type="button"
              onClick={() => setMenuOpen((prev) => !prev)}
              className="flex items-center gap-2 rounded-md border border-zinc-800 bg-[#09090b] px-2 py-1 text-xs text-zinc-200 transition-colors hover:border-zinc-700 hover:bg-zinc-900"
              aria-expanded={menuOpen}
              aria-label="Account menu"
            >
              {user.avatar_url ? (
                <img
                  src={user.avatar_url}
                  alt={user.display_name || user.email}
                  className="h-5 w-5 rounded-full object-cover"
                  referrerPolicy="no-referrer"
                />
              ) : (
                <span className="flex h-5 w-5 items-center justify-center rounded-full bg-zinc-800 text-[10px] font-semibold text-zinc-200">
                  {initials}
                </span>
              )}
              <span className="hidden max-w-[120px] truncate md:inline">
                {user.display_name || user.email}
              </span>
            </button>

            {menuOpen && (
              <div className="absolute right-0 z-50 mt-1.5 w-60 rounded-md border border-zinc-800 bg-[#111114] p-1.5 shadow-lg">
                <div className="border-b border-zinc-800 px-2.5 py-2">
                  <p className="truncate text-xs font-medium text-zinc-100">
                    {user.display_name || "Signed in"}
                  </p>
                  <p className="truncate text-[11px] text-zinc-400">{user.email}</p>
                </div>
                <button
                  type="button"
                  onClick={() => {
                    setMenuOpen(false);
                    signOut();
                  }}
                  className="mt-1 flex w-full items-center gap-2 rounded px-2.5 py-1.5 text-left text-xs text-zinc-300 transition-colors hover:bg-zinc-800 hover:text-white"
                >
                  <LogoutIcon className="h-3.5 w-3.5" />
                  <span>Sign out</span>
                </button>
              </div>
            )}
          </div>
        )}
      </div>
    </header>
  );
}
