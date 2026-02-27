mod audio;
mod backend;
mod commands;
mod screen;

use std::sync::Arc;

use tauri::Manager;

use audio::AudioState;
use backend::BackendState;

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    let app = tauri::Builder::default()
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_opener::init())
        .plugin(tauri_plugin_updater::Builder::new().build())
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_fs::init())
        .manage(AudioState::new())
        .manage(Arc::new(BackendState::new()))
        .setup(|app| {
            // Phase 3: start the background screen capture thread.
            // Frames accumulate silently; get_recent_frames() reads them on demand.
            screen::start_capture_thread();

            // Auto-start backend services (cognitive-engine + LiteLLM).
            // In dev mode this only polls health; in release it spawns processes.
            let state: Arc<BackendState> = app.state::<Arc<BackendState>>().inner().clone();
            let handle = app.handle().clone();
            std::thread::spawn(move || backend::start_services(handle, state));

            Ok(())
        })
        .invoke_handler(tauri::generate_handler![
            commands::search_project,
            commands::read_file,
            commands::list_directory,
            commands::glob_find,
            commands::write_file,
            commands::execute_command,
            commands::sync_ide_config,
            commands::save_api_keys,
            commands::load_api_keys,
            commands::open_url,
            commands::scan_security,
            commands::validate_license,
            audio::play_native_audio,
            audio::halt_native_audio,
            screen::get_recent_frames,
            backend::get_backend_status,
        ])
        .build(tauri::generate_context!())
        .expect("error while building Voco MCP Gateway");

    app.run(|app_handle, event| {
        if let tauri::RunEvent::Exit = event {
            let state: Arc<BackendState> = app_handle.state::<Arc<BackendState>>().inner().clone();
            backend::shutdown_services(&state);
        }
    });
}
