use std::path::PathBuf;

use tauri::AppHandle;
use tauri_plugin_shell::ShellExt;

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
