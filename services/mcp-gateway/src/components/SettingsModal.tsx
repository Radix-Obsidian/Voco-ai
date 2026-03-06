import { useState, useRef, useEffect, useCallback } from "react";
import { Settings, Eye, EyeOff, Save, Zap, CheckCircle2, XCircle, Loader2, Keyboard } from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import type { VocoSettings } from "@/hooks/use-settings";
import { TTS_VOICES, STT_PROVIDERS, WHISPER_MODELS } from "@/hooks/use-settings";
import { openExternalLink, EXTERNAL_LINKS } from "@/lib/external-links";
import {
  type KeybindingAction,
  type KeybindingMap,
  KEYBINDING_LABELS,
  eventToCombo,
  formatCombo,
} from "@/hooks/use-keybindings";

interface IdeSyncResult {
  ide: string;
  success: boolean;
  message: string;
  path: string;
}

async function invokeTauri<T>(cmd: string, args?: Record<string, unknown>): Promise<T> {
  if (typeof window === "undefined" || !("__TAURI_INTERNALS__" in window)) {
    throw new Error("Not running inside Tauri");
  }
  const { invoke } = await import("@tauri-apps/api/core");
  return invoke<T>(cmd, args);
}

interface SettingsModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  settings: VocoSettings;
  onUpdate: <K extends keyof VocoSettings>(key: K, value: VocoSettings[K]) => void;
  onSave: () => void;
  keybindings: KeybindingMap;
  onUpdateBinding: (action: KeybindingAction, combo: string) => void;
  onResetBindings: () => void;
}

function KeyField({
  id,
  label,
  value,
  placeholder,
  onChange,
}: {
  id: string;
  label: string;
  value: string;
  placeholder: string;
  onChange: (v: string) => void;
}) {
  const [visible, setVisible] = useState(false);

  return (
    <div className="space-y-2">
      <Label htmlFor={id} className="text-sm font-medium text-zinc-300">
        {label}
      </Label>
      <div className="relative">
        <Input
          id={id}
          type={visible ? "text" : "password"}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder={placeholder}
          className="pr-10 bg-zinc-900 border-zinc-700 text-zinc-100 placeholder:text-zinc-600 font-mono text-sm"
        />
        <button
          type="button"
          onClick={() => setVisible(!visible)}
          className="absolute right-2 top-1/2 -translate-y-1/2 text-zinc-500 hover:text-zinc-300 transition-colors"
        >
          {visible ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
        </button>
      </div>
    </div>
  );
}

function ShortcutRecorder({
  action,
  combo,
  onRecord,
  onClear,
}: {
  action: KeybindingAction;
  combo: string;
  onRecord: (action: KeybindingAction, combo: string) => void;
  onClear: (action: KeybindingAction) => void;
}) {
  const [listening, setListening] = useState(false);
  const ref = useRef<HTMLButtonElement>(null);

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      e.preventDefault();
      e.stopPropagation();
      const parsed = eventToCombo(e.nativeEvent);
      if (!parsed) return;
      onRecord(action, parsed);
      setListening(false);
    },
    [action, onRecord]
  );

  return (
    <div className="flex items-center justify-between py-2">
      <span className="text-sm text-zinc-300">{KEYBINDING_LABELS[action]}</span>
      <div className="flex items-center gap-2">
        <button
          ref={ref}
          type="button"
          onClick={() => setListening(true)}
          onKeyDown={listening ? handleKeyDown : undefined}
          onBlur={() => setListening(false)}
          className={`inline-flex items-center justify-center min-w-[90px] h-7 px-2 rounded text-[11px] font-mono border transition-colors cursor-pointer ${
            listening
              ? "bg-zinc-800 border-voco-cyan/50 text-voco-cyan animate-pulse"
              : "bg-zinc-800 border-zinc-700 text-zinc-400 hover:border-zinc-500 hover:text-zinc-300"
          }`}
        >
          {listening ? "Press keys..." : formatCombo(combo)}
        </button>
        {combo && !listening && (
          <button
            type="button"
            onClick={() => onClear(action)}
            className="px-1.5 py-0.5 text-[10px] rounded text-zinc-500 hover:text-red-400 transition-colors"
          >
            Clear
          </button>
        )}
      </div>
    </div>
  );
}

function GlobalHotkeyRecorder({
  combo,
  onRecord,
}: {
  combo: string;
  onRecord: (combo: string) => void;
}) {
  const [listening, setListening] = useState(false);

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      e.preventDefault();
      e.stopPropagation();
      const parsed = eventToCombo(e.nativeEvent);
      if (!parsed) return;
      onRecord(parsed);
      setListening(false);
    },
    [onRecord]
  );

  return (
    <button
      type="button"
      onClick={() => setListening(true)}
      onKeyDown={listening ? handleKeyDown : undefined}
      onBlur={() => setListening(false)}
      className={`inline-flex items-center justify-center min-w-[90px] h-7 px-3 rounded text-[11px] font-mono border transition-colors cursor-pointer ${
        listening
          ? "bg-zinc-800 border-voco-cyan/50 text-voco-cyan animate-pulse"
          : "bg-zinc-800 border-zinc-700 text-zinc-400 hover:border-zinc-500 hover:text-zinc-300"
      }`}
    >
      {listening ? "Press keys..." : formatCombo(combo)}
    </button>
  );
}

export function SettingsModal({
  open,
  onOpenChange,
  settings,
  onUpdate,
  onSave,
  keybindings,
  onUpdateBinding,
  onResetBindings,
}: SettingsModalProps) {
  const [syncStatus, setSyncStatus] = useState<"idle" | "syncing" | "done">("idle");
  const [syncResults, setSyncResults] = useState<IdeSyncResult[]>([]);

  const handleSyncIde = async () => {
    setSyncStatus("syncing");
    setSyncResults([]);
    try {
      const results = await invokeTauri<IdeSyncResult[]>("sync_ide_config");
      setSyncResults(results);
    } catch (err) {
      setSyncResults([{ ide: "Error", success: false, message: String(err), path: "" }]);
    } finally {
      setSyncStatus("done");
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="bg-zinc-950 border-zinc-800 text-zinc-100 sm:max-w-lg max-h-[85vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2 text-voco-cyan">
            <Settings className="h-5 w-5" />
            Voco Settings
          </DialogTitle>
          <DialogDescription className="text-zinc-400">
            Voice &amp; IDE preferences. Audio keys are managed by Voco's backend.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4 py-4">
          <KeyField
            id="github"
            label="GitHub Token (optional)"
            value={settings.GITHUB_TOKEN}
            placeholder="ghp_..."
            onChange={(v) => onUpdate("GITHUB_TOKEN", v)}
          />

          <div className="space-y-2">
            <Label htmlFor="tts-voice" className="text-sm font-medium text-zinc-300">
              TTS Voice
            </Label>
            <Select
              value={settings.TTS_VOICE}
              onValueChange={(v) => onUpdate("TTS_VOICE", v)}
            >
              <SelectTrigger
                id="tts-voice"
                className="bg-zinc-900 border-zinc-700 text-zinc-100"
              >
                <SelectValue />
              </SelectTrigger>
              <SelectContent className="bg-zinc-900 border-zinc-700">
                {TTS_VOICES.map((voice) => (
                  <SelectItem
                    key={voice.value}
                    value={voice.value}
                    className="text-zinc-100"
                  >
                    {voice.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {/* STT Provider */}
          <div className="space-y-2">
            <Label htmlFor="stt-provider" className="text-sm font-medium text-zinc-300">
              Speech Recognition
            </Label>
            <Select
              value={settings.STT_PROVIDER}
              onValueChange={(v) => onUpdate("STT_PROVIDER", v as VocoSettings["STT_PROVIDER"])}
            >
              <SelectTrigger
                id="stt-provider"
                className="bg-zinc-900 border-zinc-700 text-zinc-100"
              >
                <SelectValue />
              </SelectTrigger>
              <SelectContent className="bg-zinc-900 border-zinc-700">
                {STT_PROVIDERS.map((p) => (
                  <SelectItem key={p.value} value={p.value} className="text-zinc-100">
                    <span>{p.label}</span>
                    <span className="ml-2 text-zinc-500 text-xs">{p.description}</span>
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {/* Whisper Model — only shown when local STT is selected */}
          {settings.STT_PROVIDER === "whisper-local" && (
            <div className="space-y-2 pl-2 border-l-2 border-voco-cyan/20">
              <Label htmlFor="whisper-model" className="text-sm font-medium text-zinc-300">
                Whisper Model
              </Label>
              <p className="text-xs text-zinc-500">
                Larger models are more accurate but slower. Downloads automatically on first use.
              </p>
              <Select
                value={settings.WHISPER_MODEL}
                onValueChange={(v) => onUpdate("WHISPER_MODEL", v)}
              >
                <SelectTrigger
                  id="whisper-model"
                  className="bg-zinc-900 border-zinc-700 text-zinc-100"
                >
                  <SelectValue />
                </SelectTrigger>
                <SelectContent className="bg-zinc-900 border-zinc-700">
                  {WHISPER_MODELS.map((m) => (
                    <SelectItem key={m.value} value={m.value} className="text-zinc-100">
                      <span>{m.label}</span>
                      <span className="ml-2 text-zinc-500 text-xs">{m.size} · {m.speed}</span>
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          )}

          {/* Wake Word */}
          <div className="flex items-center justify-between py-1">
            <div>
              <Label className="text-sm font-medium text-zinc-300">
                Wake Word — "Hey Voco"
              </Label>
              <p className="text-xs text-zinc-500 mt-0.5">
                Only respond when you say "Hey Voco" first. Prevents picking up ambient speech.
              </p>
            </div>
            <button
              type="button"
              onClick={() => onUpdate("WAKE_WORD", !settings.WAKE_WORD)}
              className={`relative inline-flex h-6 w-11 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none ${
                settings.WAKE_WORD ? "bg-voco-cyan" : "bg-zinc-700"
              }`}
            >
              <span
                className={`pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out ${
                  settings.WAKE_WORD ? "translate-x-5" : "translate-x-0"
                }`}
              />
            </button>
          </div>
        </div>

          {/* Global Hotkey */}
          <div className="pt-2 border-t border-zinc-800 space-y-2">
            <Label className="text-sm font-medium text-zinc-300">
              Global Hotkey
            </Label>
            <p className="text-xs text-zinc-500">
              System-wide shortcut to wake/pause mic or barge-in during TTS. Works even when Voco isn't focused.
            </p>
            <GlobalHotkeyRecorder
              combo={settings.GLOBAL_HOTKEY ?? "Alt+Space"}
              onRecord={(combo) => onUpdate("GLOBAL_HOTKEY", combo)}
            />
          </div>

          {/* Keyboard Shortcuts */}
          <div className="pt-2 border-t border-zinc-800 space-y-2">
            <div className="flex items-center justify-between">
              <Label className="text-sm font-medium text-zinc-300 flex items-center gap-1.5">
                <Keyboard className="h-3.5 w-3.5 text-voco-cyan" />
                Keyboard Shortcuts
              </Label>
              {Object.values(keybindings).some(Boolean) && (
                <button
                  type="button"
                  onClick={onResetBindings}
                  className="text-[10px] text-zinc-500 hover:text-red-400 underline underline-offset-2 transition-colors"
                >
                  Reset all
                </button>
              )}
            </div>
            <p className="text-xs text-zinc-500">
              Click a shortcut, then press your desired key combo. All shortcuts start unbound to avoid clashes.
            </p>
            <div className="divide-y divide-zinc-800/50">
              {(Object.keys(KEYBINDING_LABELS) as KeybindingAction[]).map((action) => (
                <ShortcutRecorder
                  key={action}
                  action={action}
                  combo={keybindings[action]}
                  onRecord={onUpdateBinding}
                  onClear={(a) => onUpdateBinding(a, "")}
                />
              ))}
            </div>
          </div>

          {/* IDE Sync */}
          <div className="pt-2 border-t border-zinc-800 space-y-3">
            <Label className="text-sm font-medium text-zinc-300">IDE Auto-Config</Label>
            <p className="text-xs text-zinc-500">
              Inject Voco into your Cursor / Windsurf MCP config automatically.
            </p>
            <Button
              type="button"
              onClick={handleSyncIde}
              disabled={syncStatus === "syncing"}
              variant="outline"
              className="w-full border-zinc-700 bg-zinc-900 text-zinc-200 hover:bg-zinc-800 hover:text-white disabled:opacity-50"
            >
              {syncStatus === "syncing" ? (
                <Loader2 className="h-4 w-4 mr-2 animate-spin" />
              ) : (
                <Zap className="h-4 w-4 mr-2 text-voco-cyan" />
              )}
              {syncStatus === "syncing" ? "Syncing…" : "Sync to Cursor / Windsurf"}
            </Button>

            {syncResults.length > 0 && (
              <div className="space-y-1.5">
                {syncResults.map((r) => (
                  <div key={r.ide} className="flex items-start gap-2 text-xs">
                    {r.success ? (
                      <CheckCircle2 className="h-3.5 w-3.5 mt-0.5 shrink-0 text-voco-cyan" />
                    ) : (
                      <XCircle className="h-3.5 w-3.5 mt-0.5 shrink-0 text-red-400" />
                    )}
                    <span className={r.success ? "text-zinc-300" : "text-zinc-500"}>
                      <span className="font-medium">{r.ide}:</span> {r.message}
                    </span>
                  </div>
                ))}
              </div>
            )}
          </div>

        <div className="flex items-center justify-between text-xs text-zinc-500 pt-2 border-t border-zinc-800">
          <div className="flex gap-3">
            <button
              type="button"
              onClick={() => openExternalLink(EXTERNAL_LINKS.docs)}
              className="text-voco-cyan hover:text-voco-cyan/80 underline underline-offset-2 transition-colors"
            >
              Documentation
            </button>
            <button
              type="button"
              onClick={() => openExternalLink(EXTERNAL_LINKS.website)}
              className="text-voco-cyan hover:text-voco-cyan/80 underline underline-offset-2 transition-colors"
            >
              Website
            </button>
          </div>
          <Button
            onClick={() => {
              onSave();
              onOpenChange(false);
            }}
            className="bg-gradient-to-r from-voco-green to-voco-cyan hover:opacity-90 text-white"
          >
            <Save className="h-4 w-4 mr-2" />
            Save & Apply
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
