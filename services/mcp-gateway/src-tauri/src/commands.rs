use std::path::PathBuf;

use serde::{Deserialize, Serialize};
use tauri::AppHandle;
use tauri_plugin_shell::ShellExt;

// ---------------------------------------------------------------------------
// IDE Auto-Config
// ---------------------------------------------------------------------------

// ---------------------------------------------------------------------------
// Audio & voice key storage (AI keys are proxied via LiteLLM gateway)
// ---------------------------------------------------------------------------

/// Audio/voice API keys stored in `{app_config_dir}/config.json`.
/// Field names match Python env-var names so Python can `os.environ.update()` directly.
#[derive(Serialize, Deserialize, Default)]
pub struct VocoApiKeys {
    #[serde(rename = "DEEPGRAM_API_KEY", default)]
    pub deepgram_api_key: String,
    #[serde(rename = "CARTESIA_API_KEY", default)]
    pub cartesia_api_key: String,
    #[serde(rename = "GITHUB_TOKEN", default)]
    pub github_token: String,
    #[serde(rename = "TTS_VOICE", default)]
    pub tts_voice: String,
    #[serde(rename = "GOOGLE_API_KEY", default)]
    pub google_api_key: String,
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

// ---------------------------------------------------------------------------
// Phase 4: Voco Auto-Sec — Local security scanner
// ---------------------------------------------------------------------------

/// Scan a project for exposed secrets and dependency metadata.
///
/// Performs two checks without any network calls:
///   1. Reads `package.json` (deps + devDeps) at the project root.
///   2. Walks for `.env*` files and flags lines that match known secret
///      patterns (API key prefixes, private key headers, OAuth tokens, etc.).
///
/// Returns a JSON string that Python passes to Claude for threat analysis.
#[tauri::command]
pub async fn scan_security(project_path: PathBuf) -> Result<String, String> {
    if !project_path.is_absolute() {
        return Err(format!(
            "project_path must be absolute: '{}'",
            project_path.display()
        ));
    }

    // --- 1. Read package.json dependency manifest ---
    let pkg_path = project_path.join("package.json");
    let lock_path = project_path.join("package-lock.json");

    let dependencies: serde_json::Value = if pkg_path.exists() {
        match std::fs::read_to_string(&pkg_path) {
            Ok(content) => {
                if let Ok(pkg) = serde_json::from_str::<serde_json::Value>(&content) {
                    let deps = pkg.get("dependencies").cloned().unwrap_or(serde_json::json!({}));
                    let dev_deps = pkg.get("devDependencies").cloned().unwrap_or(serde_json::json!({}));
                    serde_json::json!({
                        "source": "package.json",
                        "dependencies": deps,
                        "devDependencies": dev_deps
                    })
                } else {
                    serde_json::json!({ "source": "package.json", "error": "parse error" })
                }
            }
            Err(e) => serde_json::json!({ "source": "package.json", "error": e.to_string() }),
        }
    } else if lock_path.exists() {
        serde_json::json!({
            "source": "package-lock.json",
            "note": "package-lock.json present — run npm audit for full CVE report"
        })
    } else {
        serde_json::json!(null)
    };

    // --- 2. Scan .env* files for secrets ---
    // Pattern: (substring to match, human description, severity)
    let patterns: &[(&str, &str, &str)] = &[
        ("sk-proj-", "OpenAI project API key", "critical"),
        ("sk-", "OpenAI/Anthropic-style API key", "high"),
        ("sk_test_", "Stripe test secret key", "high"),
        ("sk_live_", "Stripe live secret key", "critical"),
        ("AKIA", "AWS Access Key ID", "critical"),
        ("ghp_", "GitHub Personal Access Token", "high"),
        ("github_pat_", "GitHub Fine-grained PAT", "high"),
        ("xai-", "xAI API key", "high"),
        ("-----BEGIN", "Private key or certificate", "critical"),
        ("ya29.", "Google OAuth access token", "high"),
        ("EAA", "Facebook/Meta access token", "medium"),
    ];

    let env_issues = scan_env_files_for_secrets(&project_path, patterns);

    let report = serde_json::json!({
        "project_path": project_path.display().to_string(),
        "dependencies": dependencies,
        "env_issues": env_issues,
        "scan_timestamp": "local"
    });

    serde_json::to_string(&report).map_err(|e| format!("Serialization error: {e}"))
}

/// Walk the project root (and common service subdirs) for `.env*` files,
/// check each non-comment line for known secret prefixes.
fn scan_env_files_for_secrets(
    project_path: &PathBuf,
    patterns: &[(&str, &str, &str)],
) -> Vec<serde_json::Value> {
    let mut issues = Vec::new();

    // Directories to check — project root + common monorepo service dirs
    let search_dirs: Vec<PathBuf> = {
        let mut dirs = vec![project_path.clone()];
        if let Ok(entries) = std::fs::read_dir(project_path.join("services")) {
            for entry in entries.flatten() {
                let p = entry.path();
                if p.is_dir() {
                    dirs.push(p);
                }
            }
        }
        dirs
    };

    for dir in &search_dirs {
        if !dir.exists() {
            continue;
        }
        let entries = match std::fs::read_dir(dir) {
            Ok(e) => e,
            Err(_) => continue,
        };
        for entry in entries.flatten() {
            let fname = entry.file_name();
            let fname_str = fname.to_string_lossy();
            // Only scan .env, .env.local, .env.production, .env.development, etc.
            if !fname_str.starts_with(".env") {
                continue;
            }
            let path = entry.path();
            if !path.is_file() {
                continue;
            }
            let content = match std::fs::read_to_string(&path) {
                Ok(c) => c,
                Err(_) => continue,
            };

            let is_example =
                fname_str.contains("example") || fname_str.contains("sample") || fname_str.contains("template");

            let rel_path = path
                .strip_prefix(project_path)
                .map(|p| p.display().to_string())
                .unwrap_or_else(|_| path.display().to_string());

            for (line_num, line) in content.lines().enumerate() {
                let trimmed = line.trim();
                // Skip blank lines and comments
                if trimmed.is_empty() || trimmed.starts_with('#') {
                    continue;
                }
                // Skip placeholder/template lines (no real value)
                let value_part = line.splitn(2, '=').nth(1).unwrap_or("").trim();
                if value_part.is_empty()
                    || value_part.starts_with('<')
                    || value_part.to_lowercase().contains("your_")
                    || value_part.to_lowercase().contains("replace_me")
                    || value_part == "\"\"" || value_part == "''"
                {
                    continue;
                }

                for (pattern, description, severity) in patterns {
                    if line.contains(pattern) {
                        let key = line.splitn(2, '=').next().unwrap_or("").trim().to_string();
                        issues.push(serde_json::json!({
                            "file": rel_path,
                            "line": line_num + 1,
                            "key": key,
                            "severity": if is_example { "low" } else { severity },
                            "pattern_matched": pattern,
                            "issue_type": description,
                            "note": if is_example {
                                "Example/template file — verify this is not a real secret"
                            } else {
                                "Potentially real secret detected in env file"
                            }
                        }));
                        break; // one issue per line
                    }
                }
            }
        }
    }

    issues
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

// ---------------------------------------------------------------------------
// License validation via Keygen.sh
// ---------------------------------------------------------------------------

#[derive(Serialize)]
pub struct LicenseResult {
    pub valid: bool,
    pub tier: String,
    pub expiry: Option<String>,
}

#[tauri::command]
pub async fn validate_license(license_key: String) -> Result<LicenseResult, String> {
    let account_id = std::env::var("KEYGEN_ACCOUNT_ID").unwrap_or_default();
    if account_id.is_empty() {
        return Ok(LicenseResult {
            valid: false,
            tier: "listener".into(),
            expiry: None,
        });
    }

    let url = format!(
        "https://api.keygen.sh/v1/accounts/{}/licenses/actions/validate-key",
        account_id
    );

    let body = serde_json::json!({
        "meta": { "key": license_key }
    });

    let client = reqwest::Client::new();
    let resp = client
        .post(&url)
        .header("Content-Type", "application/vnd.api+json")
        .header("Accept", "application/vnd.api+json")
        .json(&body)
        .send()
        .await
        .map_err(|e| format!("License validation request failed: {e}"))?;

    let data: serde_json::Value = resp
        .json()
        .await
        .map_err(|e| format!("Failed to parse license response: {e}"))?;

    let valid = data
        .pointer("/meta/valid")
        .and_then(|v| v.as_bool())
        .unwrap_or(false);

    let tier = data
        .pointer("/data/attributes/metadata/tier")
        .and_then(|v| v.as_str())
        .unwrap_or("listener")
        .to_string();

    let expiry = data
        .pointer("/data/attributes/expiry")
        .and_then(|v| v.as_str())
        .map(|s| s.to_string());

    Ok(LicenseResult { valid, tier, expiry })
}
