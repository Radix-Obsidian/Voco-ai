import { useState } from "react";
import { Settings, Eye, EyeOff, Save, Zap, CheckCircle2, XCircle, Loader2 } from "lucide-react";
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
import { TTS_VOICES } from "@/hooks/use-settings";

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

export function SettingsModal({
  open,
  onOpenChange,
  settings,
  onUpdate,
  onSave,
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
      <DialogContent className="bg-zinc-950 border-zinc-800 text-zinc-100 sm:max-w-lg">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2 text-emerald-500">
            <Settings className="h-5 w-5" />
            Voco Settings
          </DialogTitle>
          <DialogDescription className="text-zinc-400">
            Bring Your Own Keys. All keys are stored locally on your device.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4 py-4">
          <KeyField
            id="anthropic"
            label="Anthropic API Key"
            value={settings.ANTHROPIC_API_KEY}
            placeholder="sk-ant-..."
            onChange={(v) => onUpdate("ANTHROPIC_API_KEY", v)}
          />
          <KeyField
            id="deepgram"
            label="Deepgram API Key"
            value={settings.DEEPGRAM_API_KEY}
            placeholder="dg-..."
            onChange={(v) => onUpdate("DEEPGRAM_API_KEY", v)}
          />
          <KeyField
            id="cartesia"
            label="Cartesia API Key"
            value={settings.CARTESIA_API_KEY}
            placeholder="cart-..."
            onChange={(v) => onUpdate("CARTESIA_API_KEY", v)}
          />
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
                <Zap className="h-4 w-4 mr-2 text-emerald-400" />
              )}
              {syncStatus === "syncing" ? "Syncing…" : "Sync to Cursor / Windsurf"}
            </Button>

            {syncResults.length > 0 && (
              <div className="space-y-1.5">
                {syncResults.map((r) => (
                  <div key={r.ide} className="flex items-start gap-2 text-xs">
                    {r.success ? (
                      <CheckCircle2 className="h-3.5 w-3.5 mt-0.5 shrink-0 text-emerald-400" />
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

        <DialogFooter>
          <Button
            onClick={() => {
              onSave();
              onOpenChange(false);
            }}
            className="bg-emerald-600 hover:bg-emerald-700 text-white"
          >
            <Save className="h-4 w-4 mr-2" />
            Save & Apply
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
