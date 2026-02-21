import { useState, useEffect, useCallback } from "react";

export interface Settings {
  language: string;
  model: string;
  outputFormat: string;
  byokProvider: string | null;
  byokKey: string | null;
}

const STORAGE_KEY = "voco-settings";

const DEFAULT_SETTINGS: Settings = {
  language: "en-US",
  model: "google/gemini-3-flash-preview",
  outputFormat: "prp",
  byokProvider: null,
  byokKey: null,
};

function loadSettings(): Settings {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? { ...DEFAULT_SETTINGS, ...JSON.parse(raw) } : DEFAULT_SETTINGS;
  } catch {
    return DEFAULT_SETTINGS;
  }
}

export function useSettings() {
  const [settings, setSettings] = useState<Settings>(loadSettings);

  useEffect(() => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(settings));
  }, [settings]);

  const updateSetting = useCallback(<K extends keyof Settings>(key: K, value: Settings[K]) => {
    setSettings((prev) => ({ ...prev, [key]: value }));
  }, []);

  const resetSettings = useCallback(() => {
    setSettings(DEFAULT_SETTINGS);
  }, []);

  return { settings, updateSetting, resetSettings };
}

export const LANGUAGES = [
  { value: "en-US", label: "English (US)" },
  { value: "en-GB", label: "English (UK)" },
  { value: "es-ES", label: "Spanish" },
  { value: "fr-FR", label: "French" },
  { value: "de-DE", label: "German" },
  { value: "pt-BR", label: "Portuguese (BR)" },
  { value: "ja-JP", label: "Japanese" },
  { value: "ko-KR", label: "Korean" },
  { value: "zh-CN", label: "Chinese (Simplified)" },
  { value: "hi-IN", label: "Hindi" },
];

export const MODELS = [
  { value: "google/gemini-3-flash-preview", label: "Gemini 3 Flash", description: "Fast & balanced" },
  { value: "google/gemini-2.5-flash", label: "Gemini 2.5 Flash", description: "Cost-effective" },
  { value: "google/gemini-2.5-flash-lite", label: "Gemini 2.5 Flash Lite", description: "Fastest Gemini, lowest cost" },
  { value: "google/gemini-2.5-pro", label: "Gemini 2.5 Pro", description: "Top-tier reasoning" },
  { value: "google/gemini-3-pro-preview", label: "Gemini 3 Pro", description: "Next-gen reasoning" },
  { value: "openai/gpt-5-nano", label: "GPT-5 Nano", description: "Ultra-fast, cost-efficient" },
  { value: "openai/gpt-5-mini", label: "GPT-5 Mini", description: "Strong all-rounder" },
  { value: "openai/gpt-5", label: "GPT-5", description: "Maximum accuracy" },
  { value: "openai/gpt-5.2", label: "GPT-5.2", description: "Latest enhanced reasoning" },
  { value: "anthropic/claude-haiku-3.5", label: "Claude Haiku 3.5", description: "Fast + affordable", byok: true },
  { value: "anthropic/claude-sonnet-4", label: "Claude Sonnet 4", description: "Fast + capable", byok: true },
  { value: "anthropic/claude-opus-4", label: "Claude Opus 4", description: "Maximum reasoning", byok: true },
];

export const OUTPUT_FORMATS = [
  { value: "prp", label: "PRP (Persona-Rules-Protocol)", description: "Full structured prompt" },
  { value: "concise", label: "Concise", description: "Shorter, action-focused prompt" },
  { value: "technical", label: "Technical Spec", description: "Detailed technical specification" },
];

export const BYOK_PROVIDERS = [
  { value: "anthropic", label: "Anthropic" },
  { value: "openai", label: "OpenAI" },
  { value: "google", label: "Google" },
];
