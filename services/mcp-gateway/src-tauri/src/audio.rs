use std::sync::mpsc;
use std::sync::Mutex;

/// Messages sent from the main thread to the dedicated audio thread.
enum AudioMsg {
    /// Raw PCM-16 LE mono 16kHz bytes to play.
    Play(Vec<u8>),
    /// Kill all queued audio immediately (barge-in).
    Halt,
}

/// Thread-safe handle to the native audio thread.
/// Managed by Tauri's state system — Send + Sync safe.
pub struct AudioState {
    tx: Mutex<mpsc::Sender<AudioMsg>>,
}

impl AudioState {
    pub fn new() -> Self {
        let (tx, rx) = mpsc::channel::<AudioMsg>();

        // Spawn a dedicated thread that owns the OS audio output.
        // OutputStream is !Send, so it must live on a single thread.
        std::thread::spawn(move || {
            audio_thread(rx);
        });

        Self {
            tx: Mutex::new(tx),
        }
    }
}

/// The audio thread — owns OutputStream + Sink, processes messages forever.
fn audio_thread(rx: mpsc::Receiver<AudioMsg>) {
    use rodio::buffer::SamplesBuffer;
    use rodio::{OutputStream, Sink};

    let (stream, stream_handle) = match OutputStream::try_default() {
        Ok(pair) => pair,
        Err(e) => {
            eprintln!("[NativeAudio] No audio output device: {e}");
            return;
        }
    };

    let mut sink = match Sink::try_new(&stream_handle) {
        Ok(s) => s,
        Err(e) => {
            eprintln!("[NativeAudio] Failed to create sink: {e}");
            return;
        }
    };

    // Keep _stream alive for the lifetime of the thread
    let _stream = stream;

    loop {
        match rx.recv() {
            Ok(AudioMsg::Play(bytes)) => {
                if bytes.len() < 2 {
                    continue;
                }

                let samples: Vec<i16> = bytes
                    .chunks_exact(2)
                    .map(|pair| i16::from_le_bytes([pair[0], pair[1]]))
                    .collect();

                let buffer = SamplesBuffer::new(1, 16000, samples);
                sink.append(buffer);
            }
            Ok(AudioMsg::Halt) => {
                // Stop current playback and create a fresh sink
                sink.stop();
                sink = match Sink::try_new(&stream_handle) {
                    Ok(s) => s,
                    Err(e) => {
                        eprintln!("[NativeAudio] Failed to recreate sink: {e}");
                        return;
                    }
                };
            }
            Err(_) => {
                // Channel closed — app is shutting down
                break;
            }
        }
    }
}

/// Append raw PCM-16 audio bytes to the native playback queue.
///
/// Format expected: signed 16-bit little-endian mono at 16 kHz
/// (matches Cartesia TTS output exactly).
#[tauri::command]
pub fn play_native_audio(
    state: tauri::State<'_, AudioState>,
    audio_bytes: Vec<u8>,
) -> Result<(), String> {
    let tx = state.tx.lock().map_err(|e| format!("Lock poisoned: {e}"))?;
    tx.send(AudioMsg::Play(audio_bytes))
        .map_err(|e| format!("Audio thread dead: {e}"))?;
    Ok(())
}

/// Instantly kill all queued audio — the barge-in kill switch.
#[tauri::command]
pub fn halt_native_audio(state: tauri::State<'_, AudioState>) -> Result<(), String> {
    let tx = state.tx.lock().map_err(|e| format!("Lock poisoned: {e}"))?;
    tx.send(AudioMsg::Halt)
        .map_err(|e| format!("Audio thread dead: {e}"))?;
    Ok(())
}
