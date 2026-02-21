use std::path::PathBuf;

use tauri::AppHandle;
use tauri_plugin_fs::FsExt;
use tauri_plugin_shell::ShellExt;

/// Search a project directory using the bundled ripgrep sidecar.
///
/// # Security — Double-Lock
/// Layer 1: `fs_scope().is_allowed()` — verifies the path is within the
///           Tauri-configured filesystem scope before any shell execution.
/// Layer 2: ACL validators in `capabilities/default.json` enforce that only
///           safe ripgrep flags and project-bounded paths reach this point.
#[tauri::command]
pub async fn search_project(
    app: AppHandle,
    pattern: String,
    project_path: PathBuf,
) -> Result<String, String> {
    // LAYER 1: Zero-Trust FS scope check (SDD §1)
    if !app.fs_scope().is_allowed(&project_path) {
        return Err(format!(
            "Access Denied: '{}' is outside the configured project scope.",
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
