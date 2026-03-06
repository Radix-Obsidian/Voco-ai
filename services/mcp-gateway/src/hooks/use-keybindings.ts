import { useState, useEffect, useCallback } from "react";

export type KeybindingAction =
  | "toggle_mode"
  | "open_settings"
  | "toggle_sidebar"
  | "voice_commands"
  | "dismiss";

export type KeybindingMap = Record<KeybindingAction, string>;

export const KEYBINDING_LABELS: Record<KeybindingAction, string> = {
  toggle_mode: "Toggle voice / text mode",
  open_settings: "Open settings",
  toggle_sidebar: "Toggle sidebar",
  voice_commands: "Voice commands reference",
  dismiss: "Close modals / stop capture",
};

const STORAGE_KEY = "voco-keybindings";

const EMPTY_BINDINGS: KeybindingMap = {
  toggle_mode: "",
  open_settings: "",
  toggle_sidebar: "",
  voice_commands: "",
  dismiss: "",
};

function loadBindings(): KeybindingMap {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? { ...EMPTY_BINDINGS, ...JSON.parse(raw) } : { ...EMPTY_BINDINGS };
  } catch {
    return { ...EMPTY_BINDINGS };
  }
}

/** Map DOM e.key / e.code to a stable key name that Rust parse_shortcut understands. */
function normalizeKey(e: KeyboardEvent): string {
  // Use e.code for reliable physical-key mapping, fall back to e.key
  const code = e.code;
  const key = e.key;

  if (key === " ") return "Space";

  // Arrow keys
  if (code === "ArrowUp") return "ArrowUp";
  if (code === "ArrowDown") return "ArrowDown";
  if (code === "ArrowLeft") return "ArrowLeft";
  if (code === "ArrowRight") return "ArrowRight";

  // Navigation
  if (code === "Home") return "Home";
  if (code === "End") return "End";
  if (code === "PageUp") return "PageUp";
  if (code === "PageDown") return "PageDown";
  if (code === "Insert") return "Insert";
  if (code === "Delete") return "Delete";

  // Punctuation / symbols — use code for layout-independent mapping
  const codeMap: Record<string, string> = {
    Backquote: "`", Minus: "-", Equal: "=",
    BracketLeft: "[", BracketRight: "]", Backslash: "\\",
    Semicolon: ";", Quote: "'", Comma: ",", Period: ".", Slash: "/",
    NumpadAdd: "NumAdd", NumpadSubtract: "NumSub",
    NumpadMultiply: "NumMul", NumpadDivide: "NumDiv",
    NumpadDecimal: "NumDec", NumpadEnter: "NumEnter",
    Numpad0: "Num0", Numpad1: "Num1", Numpad2: "Num2", Numpad3: "Num3",
    Numpad4: "Num4", Numpad5: "Num5", Numpad6: "Num6", Numpad7: "Num7",
    Numpad8: "Num8", Numpad9: "Num9",
    PrintScreen: "PrintScreen", ScrollLock: "ScrollLock", Pause: "Pause",
    ContextMenu: "ContextMenu", CapsLock: "CapsLock", NumLock: "NumLock",
  };
  if (code in codeMap) return codeMap[code];

  // Function keys
  const fnMatch = code.match(/^F(\d+)$/);
  if (fnMatch) return `F${fnMatch[1]}`;

  // Single printable char — uppercase
  if (key.length === 1) return key.toUpperCase();

  // Named keys (Enter, Tab, Escape, Backspace, etc.)
  return key;
}

/** Convert a KeyboardEvent into a combo string like "Ctrl+K" or "Meta+Shift+?" */
export function eventToCombo(e: KeyboardEvent): string {
  const parts: string[] = [];
  if (e.ctrlKey) parts.push("Ctrl");
  if (e.metaKey) parts.push("Meta");
  if (e.altKey) parts.push("Alt");
  if (e.shiftKey) parts.push("Shift");

  // Ignore bare modifier presses
  if (["Control", "Meta", "Alt", "Shift"].includes(e.key)) return "";

  parts.push(normalizeKey(e));
  return parts.join("+");
}

/** Format a combo string for display — replace "Meta" with platform symbol */
export function formatCombo(combo: string): string {
  if (!combo) return "Not set";
  const isMac = navigator.platform.toUpperCase().includes("MAC");
  return combo
    .replace(/Meta/g, isMac ? "\u2318" : "Win")
    .replace(/Ctrl/g, isMac ? "\u2303" : "Ctrl")
    .replace(/Alt/g, isMac ? "\u2325" : "Alt")
    .replace(/Shift/g, isMac ? "\u21E7" : "Shift");
}

export function useKeybindings() {
  const [bindings, setBindings] = useState<KeybindingMap>(loadBindings);

  useEffect(() => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(bindings));
  }, [bindings]);

  const updateBinding = useCallback((action: KeybindingAction, combo: string) => {
    setBindings((prev) => ({ ...prev, [action]: combo }));
  }, []);

  const resetBindings = useCallback(() => {
    setBindings({ ...EMPTY_BINDINGS });
  }, []);

  return { bindings, updateBinding, resetBindings };
}

/**
 * Single global keydown listener that maps combos to handler functions.
 * Replaces all scattered addEventListener calls.
 */
export function useGlobalShortcuts(
  bindings: KeybindingMap,
  handlers: Partial<Record<KeybindingAction, () => void>>
) {
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      const combo = eventToCombo(e);
      if (!combo) return;

      // Build reverse lookup: combo → action
      for (const [action, bound] of Object.entries(bindings) as [KeybindingAction, string][]) {
        if (bound && bound === combo) {
          const fn = handlers[action];
          if (fn) {
            e.preventDefault();
            fn();
          }
          return;
        }
      }
    };

    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [bindings, handlers]);
}
