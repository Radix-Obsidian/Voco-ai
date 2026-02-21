import { useState, useRef, useCallback } from "react";

export function useAudioCapture(
  sendAudioChunk: ((bytes: Uint8Array) => void) | null
) {
  const [isCapturing, setIsCapturing] = useState(false);
  const audioContextRef = useRef<AudioContext | null>(null);
  const workletNodeRef = useRef<AudioWorkletNode | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const sourceRef = useRef<MediaStreamAudioSourceNode | null>(null);

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

    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    streamRef.current = stream;

    const ctx = new AudioContext({ sampleRate: 16000 });
    audioContextRef.current = ctx;

    // Load AudioWorklet processor (512 samples = 32ms buffer)
    await ctx.audioWorklet.addModule("/pcm-processor.js");

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
  }, [sendAudioChunk]);

  return { isCapturing, startCapture, stopCapture };
}
