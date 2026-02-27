import { useState, useEffect, useMemo } from "react";
import { Search, Copy, Check, Command } from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { VOICE_COMMANDS, type VoiceCommand } from "@/data/voice-commands";
import { openExternalLink, EXTERNAL_LINKS } from "@/lib/external-links";

interface CommandsModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

const CommandsModal = ({ open, onOpenChange }: CommandsModalProps) => {
  const [filter, setFilter] = useState("");
  const [copiedId, setCopiedId] = useState<string | null>(null);

  // Keyboard shortcut: Ctrl+? / Cmd+? to toggle
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "?") {
        e.preventDefault();
        onOpenChange(!open);
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [open, onOpenChange]);

  // Reset filter when modal opens
  useEffect(() => {
    if (open) setFilter("");
  }, [open]);

  const filtered = useMemo(() => {
    if (!filter.trim()) return VOICE_COMMANDS;
    const q = filter.toLowerCase();
    return VOICE_COMMANDS.filter(
      (c) =>
        c.category.toLowerCase().includes(q) ||
        c.command.toLowerCase().includes(q) ||
        c.description.toLowerCase().includes(q) ||
        c.example.toLowerCase().includes(q)
    );
  }, [filter]);

  const categories = useMemo(() => {
    const cats = new Map<string, VoiceCommand[]>();
    for (const cmd of filtered) {
      const list = cats.get(cmd.category) ?? [];
      list.push(cmd);
      cats.set(cmd.category, list);
    }
    return cats;
  }, [filtered]);

  const handleCopy = (text: string, id: string) => {
    navigator.clipboard.writeText(text).then(() => {
      setCopiedId(id);
      setTimeout(() => setCopiedId(null), 1500);
    });
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="bg-zinc-950 border-zinc-800 text-zinc-100 max-w-xl max-h-[80vh] flex flex-col">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2 text-zinc-100">
            <Command className="h-4 w-4 text-voco-cyan" />
            Voice Commands
          </DialogTitle>
          <DialogDescription className="text-zinc-500">
            Say these commands hands-free or type them in the input box.
          </DialogDescription>
        </DialogHeader>

        {/* Search */}
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-zinc-500" />
          <Input
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
            placeholder="Filter commands..."
            className="pl-9 bg-zinc-900 border-zinc-800 text-zinc-200 placeholder:text-zinc-600 h-9 text-sm"
            autoFocus
          />
        </div>

        {/* Commands list */}
        <div className="flex-1 overflow-y-auto space-y-4 pr-1 -mr-1">
          {categories.size === 0 && (
            <p className="text-center text-zinc-600 text-sm py-6">
              No commands match &ldquo;{filter}&rdquo;
            </p>
          )}
          {[...categories.entries()].map(([cat, cmds]) => (
            <div key={cat}>
              <Badge
                variant="outline"
                className="mb-2 text-[10px] font-medium border-zinc-700 text-zinc-400"
              >
                {cat}
              </Badge>
              <div className="space-y-1.5">
                {cmds.map((cmd, i) => {
                  const uid = `${cat}-${i}`;
                  return (
                    <button
                      key={uid}
                      onClick={() => handleCopy(cmd.example, uid)}
                      className="w-full text-left group flex items-start gap-3 rounded-lg px-3 py-2.5 bg-zinc-900/50 hover:bg-zinc-900 border border-transparent hover:border-zinc-800 transition-colors"
                    >
                      <div className="flex-1 min-w-0">
                        <p className="text-sm font-medium text-zinc-200 truncate">
                          {cmd.command}
                        </p>
                        <p className="text-xs text-zinc-500 mt-0.5">
                          {cmd.description}
                        </p>
                        <p className="text-xs text-zinc-600 mt-1 italic truncate">
                          e.g. &ldquo;{cmd.example}&rdquo;
                        </p>
                      </div>
                      <div className="pt-1 opacity-0 group-hover:opacity-100 transition-opacity">
                        {copiedId === uid ? (
                          <Check className="h-3.5 w-3.5 text-voco-green" />
                        ) : (
                          <Copy className="h-3.5 w-3.5 text-zinc-500" />
                        )}
                      </div>
                    </button>
                  );
                })}
              </div>
            </div>
          ))}
        </div>

        {/* Footer hint */}
        <div className="pt-2 border-t border-zinc-800 flex items-center justify-between">
          <span className="text-[10px] text-zinc-600">
            Press{" "}
            <kbd className="px-1 py-0.5 rounded bg-zinc-800 text-zinc-400 font-mono text-[10px]">
              Ctrl+?
            </kbd>{" "}
            to toggle &middot; Click a command to copy
          </span>
          <button
            type="button"
            onClick={() => openExternalLink(EXTERNAL_LINKS.website)}
            className="text-[10px] text-voco-cyan hover:text-voco-cyan/80 underline underline-offset-2 transition-colors"
          >
            Visit Website
          </button>
        </div>
      </DialogContent>
    </Dialog>
  );
};

export default CommandsModal;
