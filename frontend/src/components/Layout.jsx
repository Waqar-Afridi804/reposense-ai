import { useState } from "react";
import { useLocation } from "react-router-dom";
import Sidebar from "./Sidebar";
import Header from "./Header";

const ROUTE_TITLES = {
  "/": "Repositories",
  "/dashboard": "Overview",
  "/report": "Analysis Report",
  "/explorer": "File Explorer",
  "/dependencies": "Dependency Graph",
  "/search": "Semantic Search",
  "/assistant": "AI Assistant",
};

export default function Layout({ children }) {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const { pathname } = useLocation();
  const pageTitle = ROUTE_TITLES[pathname] || "RepoSense AI";

  return (
    <div className="flex min-h-screen bg-[#09090b] text-zinc-100">
      <Sidebar isOpen={sidebarOpen} onClose={() => setSidebarOpen(false)} />

      <div className="flex min-w-0 flex-1 flex-col">
        <Header title={pageTitle} onMenuToggle={() => setSidebarOpen(true)} />
        <main className="flex-1 px-4 py-5 sm:px-6 lg:px-8">
          <div className="mx-auto max-w-6xl">{children}</div>
        </main>
      </div>
    </div>
  );
}
