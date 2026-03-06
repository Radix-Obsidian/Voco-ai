import { useEffect, useRef } from "react";
import { Volume2, Square } from "lucide-react";
import type { ChatMessage } from "@/hooks/use-voco-socket";

interface ChatThreadProps {
  messages: ChatMessage[];
  isThinking: boolean;
  isTTSPlaying: boolean;
  onRequestTTS: (text: string) => void;
  onStopTTS: () => void;
}

export function ChatThread({ messages, isThinking, isTTSPlaying, onRequestTTS, onStopTTS }: ChatThreadProps) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isThinking]);

  if (messages.length === 0 && !isThinking) {
    return (
      <div className="flex-1 flex items-center justify-center">
        <div className="text-center space-y-3">
          <p className="text-zinc-500 text-sm">Start a conversation with Voco</p>
          <p className="text-zinc-600 text-xs">Ask me to search code, fix bugs, build apps, or analyze your screen.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex-1 overflow-y-auto px-4 py-6 space-y-4">
      {messages.map((msg) => (
        <div
          key={msg.id}
          className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}
        >
          <div
            className={`max-w-[80%] rounded-2xl px-4 py-3 text-sm leading-relaxed ${
              msg.role === "user"
                ? "bg-voco-green/10 border border-voco-green/20 text-zinc-200"
                : "bg-white/[0.04] border border-white/[0.06] text-zinc-300"
            }`}
          >
            <div className="whitespace-pre-wrap break-words">{msg.text}</div>
            {msg.role === "assistant" && (
              <div className="flex items-center gap-2 mt-2 pt-2 border-t border-white/[0.04]">
                {isTTSPlaying ? (
                  <button
                    onClick={onStopTTS}
                    className="flex items-center gap-1 text-xs text-red-400 hover:text-red-300 transition-colors"
                  >
                    <Square className="w-3 h-3" />
                    Stop
                  </button>
                ) : (
                  <button
                    onClick={() => onRequestTTS(msg.text)}
                    className="flex items-center gap-1 text-xs text-zinc-500 hover:text-zinc-300 transition-colors"
                  >
                    <Volume2 className="w-3 h-3" />
                    Read aloud
                  </button>
                )}
              </div>
            )}
          </div>
        </div>
      ))}

      {isThinking && (
        <div className="flex justify-start">
          <div className="bg-white/[0.04] border border-white/[0.06] rounded-2xl px-4 py-3">
            <div className="flex items-center gap-2 text-xs text-zinc-500">
              <div className="flex gap-1">
                <div className="w-1.5 h-1.5 rounded-full bg-voco-green/60 animate-bounce" style={{ animationDelay: "0ms" }} />
                <div className="w-1.5 h-1.5 rounded-full bg-voco-green/60 animate-bounce" style={{ animationDelay: "150ms" }} />
                <div className="w-1.5 h-1.5 rounded-full bg-voco-green/60 animate-bounce" style={{ animationDelay: "300ms" }} />
              </div>
              Thinking...
            </div>
          </div>
        </div>
      )}

      <div ref={bottomRef} />
    </div>
  );
}
