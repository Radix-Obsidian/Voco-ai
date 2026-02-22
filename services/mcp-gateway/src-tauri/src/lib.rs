mod audio;
mod commands;

use audio::AudioState;

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_fs::init())
        .manage(AudioState::new())
        .invoke_handler(tauri::generate_handler![
            commands::search_project,
            commands::write_file,
            commands::execute_command,
            audio::play_native_audio,
            audio::halt_native_audio,
        ])
        .run(tauri::generate_context!())
        .expect("error while running Voco MCP Gateway");
}
