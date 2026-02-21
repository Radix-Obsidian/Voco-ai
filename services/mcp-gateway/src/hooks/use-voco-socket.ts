import { useState, useRef, useCallback, useEffect } from "react";

const WS_URL = "ws://localhost:8000/ws/voco-stream";

export function useVocoSocket() {
  const [isConnected, setIsConnected] = useState(false);
  const [bargeInActive, setBargeInActive] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);

  const sendAudioChunk = useCallback((bytes: Uint8Array) => {
    const ws = wsRef.current;
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(bytes.buffer);
    }
  }, []);

  const disconnect = useCallback(() => {
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }
  }, []);

  const connect = useCallback(() => {
    // Avoid duplicate connections
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      return;
    }
    disconnect();

    const ws = new WebSocket(WS_URL);

    ws.onopen = () => {
      setIsConnected(true);
      console.log("[VocoSocket] Connected to", WS_URL);
    };

    ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data);
        if (msg.type === "control") {
          if (msg.action === "halt_audio_playback") {
            setBargeInActive(true);
            console.log("[Barge-in] Halting audio!");
          } else if (msg.action === "turn_ended") {
            setBargeInActive(false);
          }
        }
      } catch {
        // Binary or non-JSON frame — ignore
      }
    };

    ws.onclose = () => {
      setIsConnected(false);
      console.log("[VocoSocket] Disconnected");
    };

    ws.onerror = () => {
      setIsConnected(false);
    };

    wsRef.current = ws;
  }, [disconnect]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      wsRef.current?.close();
    };
  }, []);

  return { isConnected, bargeInActive, sendAudioChunk, connect, disconnect };
}
