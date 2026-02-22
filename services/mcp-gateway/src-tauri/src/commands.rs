use std::path::PathBuf;

use serde::{Deserialize, Serialize};
use tauri::AppHandle;
use tauri_plugin_shell::ShellExt;

// ---------------------------------------------------------------------------
// IDE Auto-Config
// ---------------------------------------------------------------------------

// ---------------------------------------------------------------------------
// BYOK — native API key storage
// ---------------------------------------------------------------------------

/// All API keys stored in `{app_config_dir}/config.json`.
/// Field names match Python env-var names so Python can `os.environ.update()` directly.
#[derive(Serialize, Deserialize, Default)]
pub struct VocoApiKeys {
    #[serde(rename = "ANTHROPIC_API_KEY", default)]
    pub anthropic_api_key: String,
    #[serde(rename = "DEEPGRAM_API_KEY", default)]
    pub deepgram_api_key: String,
    #[serde(rename = "CARTESIA_API_KEY", default)]
    pub cartesia_api_key: String,
    #[serde(rename = "GITHUB_TOKEN", default)]
    pub github_token: String,
    #[serde(rename = "TTS_VOICE", default)]
    pub tts_voice: String,
}

/// Persist API keys to `{app_config_dir}/config.json`.
#[tauri::command]
pub async fn save_api_keys(app: AppHandle, keys: VocoApiKeys) -> Result<(), String> {
    use tauri::Manager;
    let config_dir = app
        .path()
        .app_config_dir()
        .map_err(|e| format!("Cannot resolve app config dir: {e}"))?;
    std::fs::create_dir_all(&config_dir)
        .map_err(|e| format!("Cannot create config dir: {e}"))?;
    let json = serde_json::to_string_pretty(&keys)
        .map_err(|e| format!("Serialization error: {e}"))?;
    std::fs::write(config_dir.join("config.json"), json)
        .map_err(|e| format!("Write error: {e}"))?;
    Ok(())
}

/// Load API keys from `{app_config_dir}/config.json`.
/// Returns defaults (empty strings) if the file doesn't exist yet.
#[tauri::command]
pub async fn load_api_keys(app: AppHandle) -> Result<VocoApiKeys, String> {
    use tauri::Manager;
    let config_path = app
        .path()
        .app_config_dir()
        .map_err(|e| format!("Cannot resolve app config dir: {e}"))?
        .join("config.json");
    if !config_path.exists() {
        return Ok(VocoApiKeys::default());
    }
    let raw = std::fs::read_to_string(&config_path)
        .map_err(|e| format!("Read error: {e}"))?;
    serde_json::from_str(&raw).map_err(|e| format!("Parse error: {e}"))
}

// ---------------------------------------------------------------------------
// IDE Auto-Config
// ---------------------------------------------------------------------------

/// Per-IDE result returned from `sync_ide_config`.
#[derive(Serialize)]
pub struct IdeSyncResult {
    pub ide: String,
    pub success: bool,
    pub message: String,
    pub path: String,
}

/// Resolve the user's home directory without an external crate.
fn home_dir() -> Option<PathBuf> {
    let key = if cfg!(target_os = "windows") { "USERPROFILE" } else { "HOME" };
    std::env::var(key).ok().map(PathBuf::from)
}

/// Inject a `voco-local` MCP server entry into Cursor and Windsurf config files.
///
/// - Reads the existing `mcp.json` (or starts with `{}`).
/// - Merges `mcpServers.voco-local` pointing to the cognitive engine's MCP SSE endpoint.
/// - Writes back, creating the file if it didn't exist.
/// - Skips any IDE whose config directory doesn't exist (i.e. not installed).
#[tauri::command]
pub async fn sync_ide_config() -> Result<Vec<IdeSyncResult>, String> {
    let home = home_dir().ok_or_else(|| "Cannot determine home directory".to_string())?;

    // SSE transport — cognitive engine will expose this endpoint.
    let voco_entry = serde_json::json!({
        "url": "http://localhost:8001/mcp"
    });

    let targets: Vec<(&str, PathBuf)> = vec![
        ("Cursor", home.join(".cursor").join("mcp.json")),
        ("Windsurf", home.join(".windsurf").join("mcp.json")),
    ];

    let mut results = Vec::new();

    for (ide_name, config_path) in targets {
        let dir = match config_path.parent() {
            Some(d) => d.to_owned(),
            None => {
                results.push(IdeSyncResult {
                    ide: ide_name.to_string(),
                    success: false,
                    message: "Invalid config path".to_string(),
                    path: config_path.display().to_string(),
                });
                continue;
            }
        };

        // If the IDE config directory doesn't exist, the IDE isn't installed.
        if !dir.exists() {
            results.push(IdeSyncResult {
                ide: ide_name.to_string(),
                success: false,
                message: format!("{ide_name} not found — config directory does not exist."),
                path: config_path.display().to_string(),
            });
            continue;
        }

        // Read existing config or start fresh.
        let mut config: serde_json::Value = if config_path.exists() {
            let raw = std::fs::read_to_string(&config_path).unwrap_or_default();
            serde_json::from_str(&raw).unwrap_or(serde_json::json!({}))
        } else {
            serde_json::json!({})
        };

        if !config.is_object() {
            config = serde_json::json!({});
        }

        // Merge voco-local into mcpServers.
        let map = config.as_object_mut().unwrap();
        let servers = map
            .entry("mcpServers")
            .or_insert_with(|| serde_json::json!({}));

        if let Some(servers_map) = servers.as_object_mut() {
            servers_map.insert("voco-local".to_string(), voco_entry.clone());
        }

        match serde_json::to_string_pretty(&config) {
            Ok(json_str) => match std::fs::write(&config_path, json_str) {
                Ok(()) => results.push(IdeSyncResult {
                    ide: ide_name.to_string(),
                    success: true,
                    message: format!("voco-local synced to {ide_name}"),
                    path: config_path.display().to_string(),
                }),
                Err(e) => results.push(IdeSyncResult {
                    ide: ide_name.to_string(),
                    success: false,
                    message: format!("Write failed: {e}"),
                    path: config_path.display().to_string(),
                }),
            },
            Err(e) => results.push(IdeSyncResult {
                ide: ide_name.to_string(),
                success: false,
                message: format!("Serialization failed: {e}"),
                path: config_path.display().to_string(),
            }),
        }
    }

    Ok(results)
}

// ---------------------------------------------------------------------------
// Billing — open Stripe Checkout / Portal URLs in the system browser
// ---------------------------------------------------------------------------

/// Open a URL in the system default browser.
///
/// Used by the PricingModal to redirect the user to Stripe Checkout or the
/// Customer Portal without keeping the URL inside the Tauri webview.
#[tauri::command]
pub async fn open_url(app: AppHandle, url: String) -> Result<(), String> {
    app.shell()
        .open(&url, None)
        .map_err(|e| format!("Failed to open URL: {e}"))
}

/// Execute a shell command within an authorized project directory.
///
/// # Security — Double-Lock
/// - `project_path` must be absolute and canonicalizable.
/// - Command runs with `current_dir` locked to the project path.
/// - Selects `cmd /C` on Windows, `sh -c` on Unix.
#[tauri::command]
pub async fn execute_command(
    app: AppHandle,
    command: String,
    project_path: PathBuf,
) -> Result<String, String> {
    if !project_path.is_absolute() {
        return Err(format!(
            "project_path must be absolute: '{}'",
            project_path.display()
        ));
    }

    let canonical_path = project_path
        .canonicalize()
        .map_err(|e| format!("Cannot canonicalize project_path: {e}"))?;

    let path_str = canonical_path
        .to_str()
        .ok_or_else(|| "Invalid project path encoding".to_string())?;

    // Select shell based on OS
    #[cfg(target_os = "windows")]
    let output = app
        .shell()
        .command("cmd")
        .args(["/C", &command])
        .current_dir(path_str)
        .output()
        .await
        .map_err(|e| format!("Command execution failed: {e}"))?;

    #[cfg(not(target_os = "windows"))]
    let output = app
        .shell()
        .command("sh")
        .args(["-c", &command])
        .current_dir(path_str)
        .output()
        .await
        .map_err(|e| format!("Command execution failed: {e}"))?;

    let stdout = String::from_utf8_lossy(&output.stdout).into_owned();
    let stderr = String::from_utf8_lossy(&output.stderr).into_owned();

    if !output.status.success() {
        return Err(format!(
            "Command failed (exit {:?})\nstdout: {}\nstderr: {}",
            output.status.code(),
            stdout,
            stderr
        ));
    }

    Ok(format!("{}\n{}", stdout, stderr).trim().to_string())
}

/// Write content to a file within a project directory.
///
/// # Security
/// - Both `file_path` and `project_root` must be absolute.
/// - The canonical parent of `file_path` must start with the canonical `project_root`.
/// - Parent directories are created automatically.
#[tauri::command]
pub async fn write_file(
    file_path: PathBuf,
    content: String,
    project_root: PathBuf,
) -> Result<String, String> {
    if !file_path.is_absolute() {
        return Err(format!(
            "file_path must be absolute: '{}'",
            file_path.display()
        ));
    }
    if !project_root.is_absolute() {
        return Err(format!(
            "project_root must be absolute: '{}'",
            project_root.display()
        ));
    }

    let canonical_root = project_root
        .canonicalize()
        .map_err(|e| format!("Cannot canonicalize project_root: {e}"))?;

    // Ensure parent directory exists before canonicalizing the file path
    let parent = file_path
        .parent()
        .ok_or_else(|| "file_path has no parent directory".to_string())?;

    std::fs::create_dir_all(parent)
        .map_err(|e| format!("Failed to create parent directories: {e}"))?;

    let canonical_parent = parent
        .canonicalize()
        .map_err(|e| format!("Cannot canonicalize file parent: {e}"))?;

    if !canonical_parent.starts_with(&canonical_root) {
        return Err(format!(
            "Security Violation: file_path '{}' is outside project_root '{}'",
            file_path.display(),
            project_root.display()
        ));
    }

    std::fs::write(&file_path, &content)
        .map_err(|e| format!("Failed to write file: {e}"))?;

    Ok(format!("Written {} bytes to {}", content.len(), file_path.display()))
}

/// Search a project directory using the bundled ripgrep sidecar.
///
/// # Security
/// - Path must be absolute and exist (ripgrep validates).
/// - Pattern is passed directly to ripgrep (no shell injection via sidecar).
/// - Ripgrep respects .gitignore and filesystem permissions.
#[tauri::command]
pub async fn search_project(
    app: AppHandle,
    pattern: String,
    project_path: PathBuf,
) -> Result<String, String> {
    // Validate path: accept both Windows (C:\...) and Unix-style (/...) absolute paths
    let path_str = project_path.to_string_lossy();
    let is_absolute = project_path.is_absolute() || path_str.starts_with('/');
    
    if !is_absolute {
        return Err(format!(
            "Project path must be absolute (Windows C:\\... or Unix /...): '{}'",
            project_path.display()
        ));
    }

    let path_str = project_path
        .to_str()
        .ok_or_else(|| "Invalid project path encoding".to_string())?;

    // LAYER 2: Execute ripgrep sidecar (scoped via ACL validators)
    let output = app
        .shell()
        .sidecar("rg")
        .map_err(|e| format!("Failed to spawn ripgrep sidecar: {e}"))?
        .args(["--column", "--line-number", "--no-heading", "--color=never"])
        .args([&pattern, path_str])
        .output()
        .await
        .map_err(|e| format!("ripgrep execution failed: {e}"))?;

    if !output.status.success() && !output.stderr.is_empty() {
        let stderr = String::from_utf8_lossy(&output.stderr);
        // Exit code 1 from rg means "no matches" — not an error
        if output.status.code() != Some(1) {
            return Err(format!("ripgrep error: {stderr}"));
        }
    }

    Ok(String::from_utf8_lossy(&output.stdout).into_owned())
}
