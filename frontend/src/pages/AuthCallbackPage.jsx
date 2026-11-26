import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { ErrorBanner, LoadingSpinner } from "../components/StatusAlert";
import { useAuth } from "../context/AuthContext";
import { supabase } from "../lib/supabase";

export default function AuthCallbackPage() {
  const navigate = useNavigate();
  const { isAuthenticated, loading } = useAuth();
  const [callbackError, setCallbackError] = useState("");

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const errDesc = params.get("error_description") || params.get("error");
    if (errDesc) {
      setCallbackError(errDesc);
      return;
    }

    if (!supabase) {
      setCallbackError("Supabase authentication is not configured.");
      return;
    }

    if (!loading && isAuthenticated) {
      navigate("/", { replace: true });
    }
  }, [isAuthenticated, loading, navigate]);

  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-[#09090b] px-4 text-zinc-100">
      <div className="w-full max-w-sm rounded-lg border border-zinc-800/80 bg-[#0b0b0e] p-6">
        {callbackError ? (
          <div className="space-y-4">
            <ErrorBanner message={callbackError} />
            <Link
              to="/login"
              className="inline-flex w-full items-center justify-center rounded-md border border-zinc-700 bg-zinc-900 px-3 py-2 text-xs font-medium text-zinc-200 hover:bg-zinc-800"
            >
              Back to Sign In
            </Link>
          </div>
        ) : (
          <LoadingSpinner label="Completing Google sign-in..." />
        )}
      </div>
    </div>
  );
}
