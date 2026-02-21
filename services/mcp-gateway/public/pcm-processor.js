/**
 * PCMProcessor — AudioWorklet for low-latency 16kHz PCM-16 streaming.
 * Buffer: 512 samples = 32ms at 16kHz (vs 256ms with ScriptProcessorNode).
 */
class PCMProcessor extends AudioWorkletProcessor {
  process(inputs, outputs, parameters) {
    const input = inputs[0][0]; // Float32 mono channel
    if (!input) return true;

    // Convert Float32 [-1, 1] → Int16 [-32768, 32767]
    const int16 = new Int16Array(input.length);
    for (let i = 0; i < input.length; i++) {
      const s = Math.max(-1, Math.min(1, input[i]));
      int16[i] = s < 0 ? s * 0x8000 : s * 0x7fff;
    }

    // Transfer ownership (zero-copy) to main thread
    this.port.postMessage(int16.buffer, [int16.buffer]);
    return true;
  }
}

registerProcessor("pcm-processor", PCMProcessor);
