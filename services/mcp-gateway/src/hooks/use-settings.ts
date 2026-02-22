import { useState, useEffect, useCallback } from "react";

export interface VocoSettings {
  // BYOK API keys (Milestone 10)
  ANTHROPIC_API_KEY: string;
  DEEPGRAM_API_KEY: string;
  CARTESIA_API_KEY: string;
  GITHUB_TOKEN: string;
  TTS_VOICE: string;
}

const STORAGE_KEY = "voco-settings";

const DEFAULT_SETTINGS: VocoSettings = {
  ANTHROPIC_API_KEY: "",
  DEEPGRAM_API_KEY: "",
  CARTESIA_API_KEY: "",
  GITHUB_TOKEN: "",
  TTS_VOICE: "british-professional",
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

export function useSettings() {
  const [settings, setSettings] = useState<VocoSettings>(loadSettings);

  useEffect(() => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(settings));
  }, [settings]);

  const updateSetting = useCallback(
    <K extends keyof VocoSettings>(key: K, value: VocoSettings[K]) => {
      setSettings((prev) => ({ ...prev, [key]: value }));
    },
    []
  );

  const resetSettings = useCallback(() => {
    setSettings({ ...DEFAULT_SETTINGS });
  }, []);

  const hasRequiredKeys =
    settings.ANTHROPIC_API_KEY.length > 0 &&
    settings.DEEPGRAM_API_KEY.length > 0 &&
    settings.CARTESIA_API_KEY.length > 0;

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
            ANTHROPIC_API_KEY: settings.ANTHROPIC_API_KEY,
            DEEPGRAM_API_KEY: settings.DEEPGRAM_API_KEY,
            CARTESIA_API_KEY: settings.CARTESIA_API_KEY,
            GITHUB_TOKEN: settings.GITHUB_TOKEN,
            TTS_VOICE: settings.TTS_VOICE,
          },
        })
      );
    },
    [settings]
  );

  return { settings, updateSetting, resetSettings, hasRequiredKeys, pushToBackend };
}
