/**
 * External links to the official Voco website and documentation.
 * All marketing, docs, and feature content lives at https://itsvoco.com
 */

export const EXTERNAL_LINKS = {
  website: "https://itsvoco.com",
  docs: "https://itsvoco.com/docs",
  features: "https://itsvoco.com/features",
  pricing: "https://itsvoco.com/pricing",
  blog: "https://itsvoco.com/blog",
} as const;

/**
 * Open an external URL in the system browser.
 * Uses Tauri's open_url command when available (desktop app),
 * falls back to window.open() for browser environments.
 */
export async function openExternalLink(url: string): Promise<void> {
  if (typeof window !== "undefined" && "__TAURI_INTERNALS__" in window) {
    // Desktop app — use Tauri to open in system browser
    try {
      const { invoke } = await import("@tauri-apps/api/core");
      await invoke("open_url", { url });
    } catch (err) {
      console.error("[openExternalLink] Tauri invoke failed:", err);
      // Fallback to window.open if Tauri fails
      window.open(url, "_blank", "noopener,noreferrer");
    }
  } else {
    // Browser environment
    window.open(url, "_blank", "noopener,noreferrer");
  }
}
