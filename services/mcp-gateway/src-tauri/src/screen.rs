//! Voco Eyes — rolling screen frame buffer (Phase 3).
//!
//! A background thread captures the primary monitor every 500 ms and stores
//! the last 10 JPEG frames (~5 s of recent history) in a global VecDeque.
//!
//! ``get_recent_frames`` is a Tauri command invoked by the React frontend
//! in response to a ``screen_capture_request`` WebSocket message sent by the
//! Python cognitive engine when Claude calls the ``analyze_screen`` tool.

use std::{
    collections::VecDeque,
    io::Cursor,
    sync::{Arc, Mutex, OnceLock},
    thread,
    time::Duration,
};

use base64::{engine::general_purpose::STANDARD, Engine};

// Maximum frames to keep in memory (~5 s at 500 ms / frame).
const BUFFER_SIZE: usize = 10;
// Interval between captures in milliseconds.
const CAPTURE_INTERVAL_MS: u64 = 500;
// Maximum dimension for the resized frame (reduces JPEG payload size).
const MAX_DIM: u32 = 1280;
// JPEG quality (0-100). 75 gives a good quality/size tradeoff.
const JPEG_QUALITY: u8 = 75;

// ---------------------------------------------------------------------------
// Global frame buffer
// ---------------------------------------------------------------------------

static FRAME_BUFFER: OnceLock<Arc<Mutex<VecDeque<Vec<u8>>>>> = OnceLock::new();

fn get_buffer() -> Arc<Mutex<VecDeque<Vec<u8>>>> {
    Arc::clone(
        FRAME_BUFFER
            .get_or_init(|| Arc::new(Mutex::new(VecDeque::with_capacity(BUFFER_SIZE)))),
    )
}

// ---------------------------------------------------------------------------
// Background capture thread
// ---------------------------------------------------------------------------

/// Spawn the screen capture background thread. Call once at app startup.
///
/// The thread is intentionally detached — it runs for the lifetime of the
/// process. All errors are silently swallowed so a permission denial or
/// monitor change never crashes the app.
pub fn start_capture_thread() {
    let buffer = get_buffer();
    thread::spawn(move || loop {
        capture_one_frame(&buffer);
        thread::sleep(Duration::from_millis(CAPTURE_INTERVAL_MS));
    });
}

fn capture_one_frame(buffer: &Arc<Mutex<VecDeque<Vec<u8>>>>) {
    // Find the primary monitor. Silently bail on any error.
    let monitors = match xcap::Monitor::all() {
        Ok(m) => m,
        Err(_) => return,
    };

    let monitor = match monitors.into_iter().find(|m| m.is_primary()) {
        Some(m) => m,
        None => return,
    };

    // Capture as RGBA image.
    let rgba_image = match monitor.capture_image() {
        Ok(img) => img,
        Err(_) => return,
    };

    // Convert RGBA → DynamicImage, resize, then encode as JPEG.
    let dynamic = image::DynamicImage::ImageRgba8(rgba_image);
    let resized = dynamic.resize(MAX_DIM, MAX_DIM, image::imageops::FilterType::Nearest);

    // Encode to JPEG bytes. DynamicImage::write_to strips alpha for JPEG automatically.
    let mut jpeg_bytes: Vec<u8> = Vec::new();
    if resized
        .write_to(&mut Cursor::new(&mut jpeg_bytes), image::ImageFormat::Jpeg)
        .is_err()
    {
        return;
    }

    // Overwrite JPEG quality by re-encoding with the codecs encoder if needed.
    // (The default write_to JPEG quality is ~75, which is our target — good enough.)

    // Push to rolling buffer.
    let mut buf = match buffer.lock() {
        Ok(b) => b,
        Err(_) => return,
    };
    if buf.len() >= BUFFER_SIZE {
        buf.pop_front();
    }
    buf.push_back(jpeg_bytes);
}

// ---------------------------------------------------------------------------
// Tauri command
// ---------------------------------------------------------------------------

/// Return the current frame buffer as a list of Base64-encoded JPEG strings.
///
/// The React frontend calls this in response to a ``screen_capture_request``
/// message from the WebSocket, then immediately sends the frames back to
/// Python as a ``screen_frames`` message for Claude's vision pipeline.
#[tauri::command]
pub fn get_recent_frames() -> Vec<String> {
    let binding = get_buffer();
    let buf = match binding.lock() {
        Ok(b) => b,
        Err(_) => return vec![],
    };
    buf.iter().map(|frame| STANDARD.encode(frame)).collect()
}
