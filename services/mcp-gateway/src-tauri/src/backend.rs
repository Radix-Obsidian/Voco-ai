//! Backend service lifecycle manager.
//!
//! Spawns the cognitive-engine (FastAPI on :8001) and LiteLLM proxy (:4000)
//! as child processes, polls their `/health` endpoints until ready, and
//! gracefully terminates them when the Tauri app shuts down.
//!
//! Auto-spawns in BOTH dev and release builds.  If services are already
//! running (e.g. via `npm run dev`), the health check detects them and
//! skips spawning — no double-spawn.
//!
//! Python runtime: prefers bundled `uv` from resources/uv/, falls back to
//! system `uv`, then system `python3`/`python`.  On first launch the bundled
//! uv auto-downloads Python 3.12 and installs deps (one-time ~60s setup).

use std::sync::{Arc, Mutex};
use std::process::{Child, Command, Stdio};
use std::time::Duration;

use serde::Serialize;
use tauri::{AppHandle, Emitter, Manager};

// ---------------------------------------------------------------------------
// Public state shared via Tauri's managed state
// ---------------------------------------------------------------------------

/// Tracks backend readiness so the frontend can gate its UI.
#[derive(Clone, Serialize)]
pub struct BackendStatus {
    pub engine_ready: bool,
    pub litellm_ready: bool,
    pub error: Option<String>,
    /// First-launch setup message shown in the splash screen.
    pub setup_message: Option<String>,
}

impl Default for BackendStatus {
    fn default() -> Self {
        Self {
            engine_ready: false,
            litellm_ready: false,
            error: None,
            setup_message: None,
        }
    }
}

/// Shared handle to the spawned child processes + their readiness state.
pub struct BackendState {
    pub status: Mutex<BackendStatus>,
    engine_process: Mutex<Option<Child>>,
    litellm_process: Mutex<Option<Child>>,
}

impl BackendState {
    pub fn new() -> Self {
        Self {
            status: Mutex::new(BackendStatus::default()),
            engine_process: Mutex::new(None),
            litellm_process: Mutex::new(None),
        }
    }
}

// ---------------------------------------------------------------------------
// Tauri command — frontend polls this to know when to connect
// ---------------------------------------------------------------------------

#[tauri::command]
pub fn get_backend_status(state: tauri::State<'_, Arc<BackendState>>) -> BackendStatus {
    state.status.lock().unwrap().clone()
}

// ---------------------------------------------------------------------------
// Resolve the uv binary — bundled first, then system PATH
// ---------------------------------------------------------------------------

/// Look for the bundled `uv` binary in Tauri's resource directory.
/// Falls back to system PATH if not found.
fn resolve_uv(app: &AppHandle) -> Option<String> {
    // 1. Check bundled resources/uv/uv[.exe]
    if let Ok(resource) = app.path().resource_dir() {
        #[cfg(target_os = "windows")]
        let bundled = resource.join("uv").join("uv.exe");
        #[cfg(not(target_os = "windows"))]
        let bundled = resource.join("uv").join("uv");

        if bundled.exists() {
            eprintln!("[Backend] Using bundled uv: {}", bundled.display());
            return Some(bundled.to_string_lossy().to_string());
        }

        // Also check flat layout (resources/uv.exe)
        #[cfg(target_os = "windows")]
        let flat = resource.join("uv.exe");
        #[cfg(not(target_os = "windows"))]
        let flat = resource.join("uv");

        if flat.exists() {
            eprintln!("[Backend] Using bundled uv (flat): {}", flat.display());
            return Some(flat.to_string_lossy().to_string());
        }
    }

    // 2. Fall back to system PATH
    which_executable("uv")
}

// ---------------------------------------------------------------------------
// Service spawning
// ---------------------------------------------------------------------------

/// Resolve the path to the `cognitive-engine` service directory.
///
/// In release mode the services directory lives next to the Tauri resource
/// dir, but during development it is relative to the workspace root.
fn resolve_engine_dir(app: &AppHandle) -> Result<std::path::PathBuf, String> {
    // Prefer VOCO_ENGINE_DIR env override (useful for custom installs)
    if let Ok(dir) = std::env::var("VOCO_ENGINE_DIR") {
        let p = std::path::PathBuf::from(dir);
        if p.exists() {
            return Ok(p);
        }
    }

    // Release: check resources/cognitive-engine (bundled by build script)
    if let Ok(resource) = app.path().resource_dir() {
        let bundled_engine = resource.join("cognitive-engine");
        if bundled_engine.exists() && bundled_engine.join("pyproject.toml").exists() {
            return Ok(bundled_engine);
        }

        // Also check resource_dir/../services/cognitive-engine
        let candidate: std::path::PathBuf = resource
            .parent()
            .unwrap_or(&resource)
            .join("services")
            .join("cognitive-engine");
        if candidate.exists() {
            return Ok(candidate);
        }
        // Flat layout: right next to the binary
        let flat = resource.join("cognitive-engine");
        if flat.exists() {
            return Ok(flat);
        }
    }

    // Development fallback: walk up from cwd looking for the monorepo layout
    let workspace = std::env::current_dir().unwrap_or_default();

    // Try common relative paths from various possible cwd locations
    let candidates = [
        // cwd = src-tauri → ../cognitive-engine (sibling under services/)
        workspace.join("..").join("..").join("cognitive-engine"),
        // cwd = mcp-gateway → ../cognitive-engine
        workspace.join("..").join("cognitive-engine"),
        // cwd = monorepo root → services/cognitive-engine
        workspace.join("services").join("cognitive-engine"),
        // cwd = services/ → cognitive-engine
        workspace.join("cognitive-engine"),
    ];

    for c in &candidates {
        let resolved = c.canonicalize().unwrap_or_else(|_| c.clone());
        if resolved.exists() && resolved.join("src").join("main.py").exists() {
            eprintln!("[Backend] Found engine at: {}", resolved.display());
            return Ok(resolved);
        }
    }

    Err(format!(
        "Cannot locate cognitive-engine directory. Checked env VOCO_ENGINE_DIR, resource_dir, and {} relative paths from {}.",
        candidates.len(),
        workspace.display(),
    ))
}

/// Run `uv sync` to install Python + dependencies on first launch.
/// Returns Ok(()) if deps are already installed or were installed successfully.
/// Streams progress to BackendStatus.setup_message so the splash screen shows
/// which package is being installed.
fn ensure_python_deps(
    uv_path: &str,
    engine_dir: &std::path::Path,
    state: &Arc<BackendState>,
) -> Result<(), String> {
    // Quick check: if .venv exists with a python binary, deps are likely installed
    let venv_python = if cfg!(target_os = "windows") {
        engine_dir.join(".venv").join("Scripts").join("python.exe")
    } else {
        engine_dir.join(".venv").join("bin").join("python")
    };

    if venv_python.exists() {
        eprintln!("[Backend] Python venv already exists at {}", venv_python.display());
        return Ok(());
    }

    // First launch — install Python + deps via uv
    eprintln!("[Backend] First launch detected — running uv sync to install Python + deps...");
    {
        let mut s = state.status.lock().unwrap();
        s.setup_message = Some("Setting up Python environment...".into());
    }

    // Spawn uv sync with stderr piped so we can stream progress
    let mut child = Command::new(uv_path)
        .args(["sync", "--frozen"])
        .current_dir(engine_dir)
        .stdin(Stdio::null())
        .stdout(Stdio::null())
        .stderr(Stdio::piped())
        .spawn()
        .map_err(|e| format!("Failed to run uv sync: {e}"))?;

    // Stream stderr line by line to update the splash screen
    if let Some(stderr) = child.stderr.take() {
        use std::io::{BufRead, BufReader};
        let reader = BufReader::new(stderr);
        for line in reader.lines() {
            let line = line.unwrap_or_default();
            eprintln!("[uv sync] {}", line);

            // Parse uv output to show meaningful progress
            let msg = if line.contains("Downloading") || line.contains("downloading") {
                // e.g. "Downloading onnxruntime-1.24.2..."
                let pkg = line.split_whitespace().last().unwrap_or("packages");
                format!("Downloading {}...", pkg.trim_end_matches("..."))
            } else if line.contains("Installing") || line.contains("installing") {
                let pkg = line.split_whitespace().last().unwrap_or("packages");
                format!("Installing {}...", pkg.trim_end_matches("..."))
            } else if line.contains("Using CPython") || line.contains("Using Python") {
                "Found Python runtime...".into()
            } else if line.contains("Creating virtual environment") || line.contains("creating virtualenv") {
                "Creating virtual environment...".into()
            } else if line.contains("Resolved") {
                "Resolving dependencies...".into()
            } else if line.contains("Prepared") {
                "Preparing packages...".into()
            } else if line.contains("Installed") && line.contains("package") {
                "Finishing installation...".into()
            } else {
                continue; // Skip noisy lines
            };

            state.status.lock().unwrap().setup_message = Some(msg);
        }
    }

    let status = child.wait().map_err(|e| format!("uv sync wait failed: {e}"))?;

    if !status.success() {
        return Err(format!(
            "uv sync failed (exit {}). Check that the cognitive-engine directory has a valid pyproject.toml and uv.lock.",
            status.code().unwrap_or(-1),
        ));
    }

    eprintln!("[Backend] Python + deps installed successfully.");
    {
        let mut s = state.status.lock().unwrap();
        s.setup_message = Some("Python installed! Starting services...".into());
    }

    Ok(())
}

/// Spawn the cognitive-engine and LiteLLM proxy as child processes.
///
/// This runs on a background thread kicked off from `.setup()`.
/// It updates `BackendState.status` as each service becomes healthy.
///
/// Both dev and release builds auto-spawn the backend so the app "just
/// works" when launched — exactly like Claude Code.  If the services are
/// already running externally (e.g. via `npm run dev`), the health poll
/// detects them and skips the spawn.
pub fn start_services(app: AppHandle, state: Arc<BackendState>) {
    // --- Quick-check: is the engine already running? ---
    if check_health_sync("http://127.0.0.1:8001/health") {
        eprintln!("[Backend] cognitive-engine already healthy — skipping spawn.");
        state.status.lock().unwrap().engine_ready = true;

        if check_health_sync("http://127.0.0.1:4000/health") {
            state.status.lock().unwrap().litellm_ready = true;
            eprintln!("[Backend] LiteLLM proxy already healthy.");
        }

        let _ = app.emit("backend-ready", ());
        return;
    }

    eprintln!("[Backend] Services not running — auto-spawning...");

    // --- Resolve the uv binary (bundled or system) ---
    let uv_path = resolve_uv(&app);

    // --- Resolve the cognitive-engine directory ---
    let engine_dir = match resolve_engine_dir(&app) {
        Ok(d) => d,
        Err(e) => {
            eprintln!("[Backend] {}", e);
            let mut s = state.status.lock().unwrap();
            s.error = Some(e);
            let _ = app.emit("backend-ready", ());
            return;
        }
    };

    eprintln!("[Backend] Engine dir: {}", engine_dir.display());

    // --- First-launch: ensure Python + deps are installed ---
    if let Some(ref uv) = uv_path {
        if let Err(e) = ensure_python_deps(uv, &engine_dir, &state) {
            eprintln!("[Backend] Python setup failed: {}", e);
            let mut s = state.status.lock().unwrap();
            s.error = Some(format!("Python setup failed: {e}"));
            s.setup_message = None;
            let _ = app.emit("backend-ready", ());
            return;
        }
    }

    // Clear setup message
    {
        let mut s = state.status.lock().unwrap();
        s.setup_message = None;
    }

    // --- Spawn LiteLLM proxy ---
    let litellm_result = spawn_litellm(&engine_dir, uv_path.as_deref());
    match litellm_result {
        Ok(child) => {
            *state.litellm_process.lock().unwrap() = Some(child);
            eprintln!("[Backend] LiteLLM proxy spawned.");
        }
        Err(e) => {
            eprintln!("[Backend] Failed to spawn LiteLLM: {}", e);
            // Non-fatal: engine can use direct API keys
        }
    }

    // --- Spawn cognitive-engine ---
    let engine_result = spawn_engine(&engine_dir, uv_path.as_deref());
    match engine_result {
        Ok(child) => {
            *state.engine_process.lock().unwrap() = Some(child);
            eprintln!("[Backend] Cognitive-engine spawned.");
        }
        Err(e) => {
            eprintln!("[Backend] Failed to spawn cognitive-engine: {}", e);
            let mut s = state.status.lock().unwrap();
            s.error = Some(format!("Engine spawn failed: {e}"));
        }
    }

    // --- Poll health endpoints ---
    let state_clone = Arc::clone(&state);
    let app_clone = app.clone();
    std::thread::spawn(move || {
        poll_health_blocking(&state_clone, 60);
        let _ = app_clone.emit("backend-ready", ());
    });
}

// Bundled API keys — used as fallback when no .env or config.json provides them.
// .env and config.json values take precedence (load_dotenv runs first in Python).
const BUNDLED_DEEPGRAM_KEY: &str = "1cf8c03421a3252501b42cc9cc166babc29b51bc";
const BUNDLED_CARTESIA_KEY: &str = "sk_car_GvemEWJA39GriBqvjkScVr";

/// Inject bundled API keys as env vars for the child process.
/// Only sets keys that aren't already in the environment (user's .env wins).
fn build_engine_env() -> Vec<(String, String)> {
    let mut env: Vec<(String, String)> = std::env::vars().collect();

    // Only inject if not already set
    if std::env::var("DEEPGRAM_API_KEY").unwrap_or_default().is_empty() {
        env.push(("DEEPGRAM_API_KEY".into(), BUNDLED_DEEPGRAM_KEY.into()));
    }
    if std::env::var("CARTESIA_API_KEY").unwrap_or_default().is_empty() {
        env.push(("CARTESIA_API_KEY".into(), BUNDLED_CARTESIA_KEY.into()));
    }

    env
}

fn spawn_engine(engine_dir: &std::path::Path, uv_path: Option<&str>) -> Result<Child, String> {
    let env = build_engine_env();

    if let Some(uv) = uv_path {
        Command::new(uv)
            .args([
                "run", "uvicorn", "src.main:app",
                "--host", "127.0.0.1",
                "--port", "8001",
            ])
            .current_dir(engine_dir)
            .envs(env)
            .stdin(Stdio::null())
            // Inherit stderr so subprocess output goes to the parent's console
            // (prevents pipe buffer deadlock on Windows)
            .stdout(Stdio::null())
            .stderr(Stdio::inherit())
            .spawn()
            .map_err(|e| format!("uv spawn error: {e}"))
    } else {
        // Fallback: python -m uvicorn
        let python = which_executable("python3")
            .or_else(|| which_executable("python"))
            .ok_or_else(|| "Neither uv nor python found on PATH. Install uv: https://docs.astral.sh/uv/".to_string())?;

        Command::new(python)
            .args([
                "-m", "uvicorn", "src.main:app",
                "--host", "127.0.0.1",
                "--port", "8001",
            ])
            .current_dir(engine_dir)
            .envs(env)
            .stdin(Stdio::null())
            .stdout(Stdio::null())
            .stderr(Stdio::inherit())
            .spawn()
            .map_err(|e| format!("python spawn error: {e}"))
    }
}

fn spawn_litellm(engine_dir: &std::path::Path, uv_path: Option<&str>) -> Result<Child, String> {
    // Check that litellm_config.yaml exists — skip silently if not
    if !engine_dir.join("litellm_config.yaml").exists() {
        return Err("litellm_config.yaml not found — skipping LiteLLM spawn".into());
    }

    if let Some(uv) = uv_path {
        Command::new(uv)
            .args([
                "run", "litellm",
                "--config", "litellm_config.yaml",
                "--port", "4000",
            ])
            .current_dir(engine_dir)
            .stdin(Stdio::null())
            .stdout(Stdio::null())
            .stderr(Stdio::inherit())
            .spawn()
            .map_err(|e| format!("uv litellm spawn error: {e}"))
    } else {
        let python = which_executable("python3")
            .or_else(|| which_executable("python"))
            .ok_or_else(|| "Neither uv nor python found on PATH".to_string())?;

        Command::new(python)
            .args([
                "-m", "litellm",
                "--config", "litellm_config.yaml",
                "--port", "4000",
            ])
            .current_dir(engine_dir)
            .stdin(Stdio::null())
            .stdout(Stdio::null())
            .stderr(Stdio::inherit())
            .spawn()
            .map_err(|e| format!("python litellm spawn error: {e}"))
    }
}

/// Locate an executable on PATH (cross-platform).
fn which_executable(name: &str) -> Option<String> {
    #[cfg(target_os = "windows")]
    let cmd = Command::new("where").arg(name).output();
    #[cfg(not(target_os = "windows"))]
    let cmd = Command::new("which").arg(name).output();

    cmd.ok()
        .filter(|o| o.status.success())
        .and_then(|o| {
            String::from_utf8_lossy(&o.stdout)
                .lines()
                .next()
                .map(|s| s.trim().to_string())
        })
}

// ---------------------------------------------------------------------------
// Health polling
// ---------------------------------------------------------------------------

/// Blocking poll of both service health endpoints.
/// Updates `BackendState.status` fields as each becomes reachable.
fn poll_health_blocking(state: &Arc<BackendState>, max_seconds: u64) {
    let engine_url = "http://127.0.0.1:8001/health";
    let litellm_url = "http://127.0.0.1:4000/health";
    let interval = Duration::from_millis(500);
    let deadline = std::time::Instant::now() + Duration::from_secs(max_seconds);

    let mut engine_ok = false;
    let mut litellm_ok = false;

    while std::time::Instant::now() < deadline {
        if !engine_ok {
            if check_health_sync(engine_url) {
                engine_ok = true;
                state.status.lock().unwrap().engine_ready = true;
                eprintln!("[Backend] cognitive-engine healthy.");
            }
        }
        if !litellm_ok {
            if check_health_sync(litellm_url) {
                litellm_ok = true;
                state.status.lock().unwrap().litellm_ready = true;
                eprintln!("[Backend] LiteLLM proxy healthy.");
            }
        }

        if engine_ok && litellm_ok {
            eprintln!("[Backend] All services ready.");
            return;
        }

        std::thread::sleep(interval);
    }

    // Timeout — mark error for whichever didn't respond
    let mut s = state.status.lock().unwrap();
    if !engine_ok && !litellm_ok {
        s.error = Some("Both cognitive-engine and LiteLLM failed to start within timeout.".into());
    } else if !engine_ok {
        s.error = Some("Cognitive-engine failed to start within timeout.".into());
    } else if !litellm_ok {
        // LiteLLM not starting is non-fatal — engine can still work with direct API keys
        eprintln!("[Backend] LiteLLM did not start — engine will use direct API keys.");
        s.litellm_ready = false;
    }
}

/// Synchronous HTTP GET to a health endpoint.  Returns `true` if 200 OK.
fn check_health_sync(url: &str) -> bool {
    // Use a minimal blocking HTTP request via std::net to avoid async runtime dependency.
    // Parse host:port from URL.
    let url_trimmed = url.strip_prefix("http://").unwrap_or(url);
    let (host_port, path) = match url_trimmed.find('/') {
        Some(i) => (&url_trimmed[..i], &url_trimmed[i..]),
        None => (url_trimmed, "/"),
    };

    let stream = match std::net::TcpStream::connect_timeout(
        &host_port.parse().unwrap_or_else(|_| {
            std::net::SocketAddr::from(([127, 0, 0, 1], 8001))
        }),
        Duration::from_secs(2),
    ) {
        Ok(s) => s,
        Err(_) => return false,
    };

    let _ = stream.set_read_timeout(Some(Duration::from_secs(2)));
    let _ = stream.set_write_timeout(Some(Duration::from_secs(2)));

    use std::io::{Read, Write};
    let request = format!(
        "GET {} HTTP/1.1\r\nHost: {}\r\nConnection: close\r\n\r\n",
        path, host_port
    );
    if stream.try_clone().ok().and_then(|mut s| s.write_all(request.as_bytes()).ok()).is_none() {
        return false;
    }

    let mut buf = [0u8; 512];
    match (&stream).read(&mut buf) {
        Ok(n) if n > 0 => {
            let resp = String::from_utf8_lossy(&buf[..n]);
            resp.contains("200 OK") || resp.contains("200")
        }
        _ => false,
    }
}

// ---------------------------------------------------------------------------
// Graceful shutdown
// ---------------------------------------------------------------------------

/// Kill spawned child processes. Called from Tauri's `on_event` / `Exit`.
pub fn shutdown_services(state: &Arc<BackendState>) {
    if let Ok(mut guard) = state.engine_process.lock() {
        if let Some(ref mut child) = *guard {
            eprintln!("[Backend] Stopping cognitive-engine (pid {})...", child.id());
            let _ = child.kill();
            let _ = child.wait();
        }
        *guard = None;
    }
    if let Ok(mut guard) = state.litellm_process.lock() {
        if let Some(ref mut child) = *guard {
            eprintln!("[Backend] Stopping LiteLLM proxy (pid {})...", child.id());
            let _ = child.kill();
            let _ = child.wait();
        }
        *guard = None;
    }
    eprintln!("[Backend] All services stopped.");
}
