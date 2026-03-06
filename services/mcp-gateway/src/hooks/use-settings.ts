import { useState, useEffect, useCallback } from "react";

const isTauri = () => typeof window !== "undefined" && "__TAURI_INTERNALS__" in window;

async function _nativeLoad(): Promise<Partial<VocoSettings> | null> {
  if (!isTauri()) return null;
  try {
    const { invoke } = await import("@tauri-apps/api/core");
    return await invoke<VocoSettings>("load_api_keys");
  } catch {
    return null;
  }
}

async function _nativeSave(settings: VocoSettings): Promise<void> {
  if (!isTauri()) return;
  try {
    const { invoke } = await import("@tauri-apps/api/core");
    await invoke("save_api_keys", { keys: settings });
  } catch (e) {
    console.warn("[Settings] Native save failed:", e);
  }
}

export interface VocoSettings {
  GITHUB_TOKEN: string;
  TTS_VOICE: string;
  WAKE_WORD: boolean;
  STT_PROVIDER: "deepgram" | "whisper-local";
  WHISPER_MODEL: string;
  GLOBAL_HOTKEY: string;
}

const STORAGE_KEY = "voco-settings";

const DEFAULT_SETTINGS: VocoSettings = {
  GITHUB_TOKEN: "",
  TTS_VOICE: "british-professional",
  WAKE_WORD: true,
  STT_PROVIDER: "deepgram",
  WHISPER_MODEL: "base.en",
  GLOBAL_HOTKEY: "Alt+Space",
};

function loadSettings(): VocoSettings {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? { ...DEFAULT_SETTINGS, ...JSON.parse(raw) } : { ...DEFAULT_SETTINGS };
  } catch {
    return { ...DEFAULT_SETTINGS };
  }
}

export const TTS_VOICES = [
  { value: "british-professional", label: "British Professional" },
  { value: "american-casual", label: "American Casual" },
  { value: "upbeat-startup", label: "Upbeat Startup" },
  { value: "calm-narrator", label: "Calm Narrator" },
];

export const STT_PROVIDERS = [
  { value: "deepgram", label: "Deepgram (Cloud)", description: "Fast, accurate — requires internet" },
  { value: "whisper-local", label: "Whisper (Local)", description: "Fully offline — runs on your machine" },
] as const;

export const WHISPER_MODELS = [
  { value: "tiny.en", label: "Tiny (English)", size: "~75 MB", speed: "fastest" },
  { value: "base.en", label: "Base (English)", size: "~150 MB", speed: "fast" },
  { value: "small.en", label: "Small (English)", size: "~500 MB", speed: "balanced" },
  { value: "medium.en", label: "Medium (English)", size: "~1.5 GB", speed: "accurate" },
  { value: "tiny", label: "Tiny (Multilingual)", size: "~75 MB", speed: "fastest" },
  { value: "base", label: "Base (Multilingual)", size: "~150 MB", speed: "fast" },
  { value: "small", label: "Small (Multilingual)", size: "~500 MB", speed: "balanced" },
] as const;

export function useSettings() {
  const [settings, setSettings] = useState<VocoSettings>(loadSettings);

  // Persist to localStorage on every change.
  useEffect(() => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(settings));
  }, [settings]);

  // On mount: hydrate from native OS storage (overrides localStorage if present).
  useEffect(() => {
    _nativeLoad().then((native) => {
      if (native) setSettings((prev) => ({ ...prev, ...native }));
    });
  }, []);

  const updateSetting = useCallback(
    <K extends keyof VocoSettings>(key: K, value: VocoSettings[K]) => {
      setSettings((prev) => ({ ...prev, [key]: value }));
    },
    []
  );

  const resetSettings = useCallback(() => {
    setSettings({ ...DEFAULT_SETTINGS });
  }, []);

  const hasRequiredKeys = true;

  /**
   * Push the current keys to the Python cognitive engine over the WebSocket.
   * Sends a ``{ type: "update_env", env: {...} }`` message so the backend
   * can hot-swap ``os.environ`` without restarting.
   */
  const pushToBackend = useCallback(
    (ws: WebSocket | null) => {
      if (!ws || ws.readyState !== WebSocket.OPEN) return;
      ws.send(
        JSON.stringify({
          type: "update_env",
          env: {
            GITHUB_TOKEN: settings.GITHUB_TOKEN,
            TTS_VOICE: settings.TTS_VOICE,
            STT_PROVIDER: settings.STT_PROVIDER,
            WHISPER_MODEL: settings.WHISPER_MODEL,
            wake_word: settings.WAKE_WORD ? "true" : "false",
          },
        })
      );
    },
    [settings]
  );

  /** Persist current settings to the native OS config file (called on explicit save). */
  const saveSettings = useCallback(() => _nativeSave(settings), [settings]);

  return { settings, updateSetting, resetSettings, hasRequiredKeys, pushToBackend, saveSettings };
}
