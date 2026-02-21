import { useState, useRef, useCallback } from "react";

export function useAudioCapture(
  sendAudioChunk: ((bytes: Uint8Array) => void) | null
) {
  const [isCapturing, setIsCapturing] = useState(false);
  const audioContextRef = useRef<AudioContext | null>(null);
  const processorRef = useRef<ScriptProcessorNode | null>(null);
  const streamRef = useRef<MediaStream | null>(null);

  const stopCapture = useCallback(() => {
    processorRef.current?.disconnect();
    processorRef.current = null;

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

    const source = ctx.createMediaStreamSource(stream);
    const processor = ctx.createScriptProcessor(4096, 1, 1);
    processorRef.current = processor;

    processor.onaudioprocess = (e) => {
      const float32 = e.inputBuffer.getChannelData(0);
      const int16 = new Int16Array(float32.length);
      for (let i = 0; i < float32.length; i++) {
        const s = Math.max(-1, Math.min(1, float32[i]));
        int16[i] = s * 0x7fff;
      }
      sendAudioChunk(new Uint8Array(int16.buffer));
    };

    source.connect(processor);
    processor.connect(ctx.destination);

    setIsCapturing(true);
    console.log("[AudioCapture] Started — 16kHz PCM-16 streaming");
  }, [sendAudioChunk]);

  return { isCapturing, startCapture, stopCapture };
}
