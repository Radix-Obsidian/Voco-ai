import { useState, useEffect, useCallback } from "react";

const isTauri = () => typeof window !== "undefined" && "__TAURI_INTERNALS__" in window;

export interface BackendStatus {
  engine_ready: boolean;
  litellm_ready: boolean;
  error: string | null;
}

/**
 * Polls Rust's `get_backend_status` command and listens for the
 * `backend-ready` Tauri event.  Returns the current readiness state
 * so the App can gate the main UI behind a splash screen.
 */
export function useBackendReady() {
  const [status, setStatus] = useState<BackendStatus>({
    engine_ready: false,
    litellm_ready: false,
    error: null,
  });
  const [checking, setChecking] = useState(true);

  const pollStatus = useCallback(async () => {
    if (!isTauri()) {
      // Running in plain browser (e.g. Vite dev server without Tauri)
      // — assume backend is managed externally and skip gating.
      setStatus({ engine_ready: true, litellm_ready: true, error: null });
      setChecking(false);
      return;
    }

    try {
      const { invoke } = await import("@tauri-apps/api/core");
      const s = await invoke<BackendStatus>("get_backend_status");
      setStatus(s);

      if (s.engine_ready || s.error) {
        setChecking(false);
      }
    } catch (err) {
      console.warn("[useBackendReady] poll error:", err);
    }
  }, []);

  useEffect(() => {
    // Initial poll
    pollStatus();

    // Poll every 500ms until ready
    const interval = setInterval(() => {
      if (!checking) return;
      pollStatus();
    }, 500);

    // Also listen for the Rust-side "backend-ready" event for instant notification
    let unlisten: (() => void) | undefined;
    if (isTauri()) {
      import("@tauri-apps/api/event").then(({ listen }) => {
        listen("backend-ready", () => {
          pollStatus();
        }).then((fn) => {
          unlisten = fn;
        });
      });
    }

    return () => {
      clearInterval(interval);
      unlisten?.();
    };
  }, [checking, pollStatus]);

  const isReady = status.engine_ready;

  return { status, isReady, checking, error: status.error };
}
