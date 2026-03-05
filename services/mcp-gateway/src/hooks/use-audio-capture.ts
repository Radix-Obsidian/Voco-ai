import { useState, useRef, useCallback } from "react";
import { useToast } from "@/hooks/use-toast";

export function useAudioCapture(
  sendAudioChunk: ((bytes: Uint8Array) => void) | null
) {
  const [isCapturing, setIsCapturing] = useState(false);
  const [micError, setMicError] = useState<string | null>(null);
  const audioContextRef = useRef<AudioContext | null>(null);
  const workletNodeRef = useRef<AudioWorkletNode | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const sourceRef = useRef<MediaStreamAudioSourceNode | null>(null);
  const { toast } = useToast();

  const stopCapture = useCallback(() => {
    workletNodeRef.current?.port.close();
    workletNodeRef.current?.disconnect();
    workletNodeRef.current = null;

    sourceRef.current?.disconnect();
    sourceRef.current = null;

    streamRef.current?.getTracks().forEach((t) => t.stop());
    streamRef.current = null;

    audioContextRef.current?.close();
    audioContextRef.current = null;

    setIsCapturing(false);
    console.log("[AudioCapture] Stopped");
  }, []);

  const startCapture = useCallback(async () => {
    if (!sendAudioChunk) return;
    setMicError(null);

    let stream: MediaStream;
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    } catch (err) {
      const msg = err instanceof DOMException && err.name === "NotAllowedError"
        ? "Microphone access denied. Please allow mic access in your browser/OS settings and try again."
        : `Microphone error: ${err instanceof Error ? err.message : String(err)}`;
      setMicError(msg);
      toast({ title: "Microphone Unavailable", description: msg, variant: "destructive" });
      console.error("[AudioCapture]", msg);
      return;
    }
    streamRef.current = stream;

    let ctx: AudioContext;
    try {
      ctx = new AudioContext({ sampleRate: 16000 });
      audioContextRef.current = ctx;
      await ctx.audioWorklet.addModule("/pcm-processor.js");
    } catch (err) {
      stream.getTracks().forEach((t) => t.stop());
      const msg = `Audio setup failed: ${err instanceof Error ? err.message : String(err)}`;
      setMicError(msg);
      toast({ title: "Audio Error", description: msg, variant: "destructive" });
      console.error("[AudioCapture]", msg);
      return;
    }

    const source = ctx.createMediaStreamSource(stream);
    sourceRef.current = source;

    const workletNode = new AudioWorkletNode(ctx, "pcm-processor");
    workletNodeRef.current = workletNode;

    // Receive Int16 PCM from worklet, forward to WebSocket
    workletNode.port.onmessage = (e: MessageEvent<ArrayBuffer>) => {
      sendAudioChunk(new Uint8Array(e.data));
    };

    source.connect(workletNode);
    // No need to connect to destination — worklet only posts messages

    setIsCapturing(true);
    console.log("[AudioCapture] Started — 16kHz PCM-16 via AudioWorklet (32ms buffer)");
  }, [sendAudioChunk, toast]);

  return { isCapturing, startCapture, stopCapture, micError };
}
