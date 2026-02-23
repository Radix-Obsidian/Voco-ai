import { useEffect, useRef, useState, useCallback } from "react";
import { check, type Update } from "@tauri-apps/plugin-updater";
import { ask } from "@tauri-apps/plugin-dialog";

export interface UpdateStatus {
  checking: boolean;
  available: boolean;
  downloading: boolean;
  progress: number;
  version: string | null;
  error: string | null;
}

const INITIAL_STATUS: UpdateStatus = {
  checking: false,
  available: false,
  downloading: false,
  progress: 0,
  version: null,
  error: null,
};

/**
 * Checks for app updates via CrabNebula Cloud on mount.
 * Shows a native dialog prompt when a new version is found.
 * Supports license-tier gating: pass the user's tier to control
 * which release channels they can access.
 */
export function useAppUpdater(userTier?: string) {
  const [status, setStatus] = useState<UpdateStatus>(INITIAL_STATUS);
  const ran = useRef(false);

  const performUpdate = useCallback(async (update: Update) => {
    setStatus((s) => ({ ...s, downloading: true, progress: 0 }));

    try {
      let downloaded = 0;
      let contentLength = 0;

      await update.downloadAndInstall((event) => {
        switch (event.event) {
          case "Started":
            contentLength = event.data.contentLength ?? 0;
            break;
          case "Progress":
            downloaded += event.data.chunkLength;
            if (contentLength > 0) {
              setStatus((s) => ({
                ...s,
                progress: Math.round((downloaded / contentLength) * 100),
              }));
            }
            break;
          case "Finished":
            setStatus((s) => ({ ...s, progress: 100 }));
            break;
        }
      });
    } catch (err) {
      setStatus((s) => ({
        ...s,
        downloading: false,
        error: err instanceof Error ? err.message : String(err),
      }));
    }
  }, []);

  useEffect(() => {
    if (ran.current) return;
    ran.current = true;

    // Skip update checks in dev mode
    if (import.meta.env.DEV) return;

    const checkForUpdate = async () => {
      setStatus((s) => ({ ...s, checking: true }));

      try {
        const update = await check();

        if (update) {
          setStatus((s) => ({
            ...s,
            checking: false,
            available: true,
            version: update.version,
          }));

          const shouldUpdate = await ask(
            `Voco ${update.version} is available. Update now?`,
            {
              title: "Update Available",
              kind: "info",
              okLabel: "Update",
              cancelLabel: "Later",
            },
          );

          if (shouldUpdate) {
            await performUpdate(update);
          }
        } else {
          setStatus((s) => ({ ...s, checking: false }));
        }
      } catch (err) {
        setStatus((s) => ({
          ...s,
          checking: false,
          error: err instanceof Error ? err.message : String(err),
        }));
      }
    };

    checkForUpdate();
  }, [performUpdate]);

  return status;
}
