mod audio;
mod backend;
mod commands;
mod screen;

use std::sync::Arc;

use tauri::Manager;
use tauri::WindowEvent;
use tauri::menu::{Menu, MenuItem};
use tauri::tray::TrayIconBuilder;

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
        .plugin(tauri_plugin_global_shortcut::Builder::new().build())
        .manage(AudioState::new())
        .manage(Arc::new(BackendState::new()))
        .setup(|app| {
            // Phase 3: start the background screen capture thread.
            screen::start_capture_thread();

            // Auto-start backend services (cognitive-engine + LiteLLM).
            let state: Arc<BackendState> = app.state::<Arc<BackendState>>().inner().clone();
            let handle = app.handle().clone();
            std::thread::spawn(move || backend::start_services(handle, state));

            // --- System tray icon with menu ---
            let show_item = MenuItem::with_id(app, "show_voco", "Show Voco", true, None::<&str>)?;
            let quit_item = MenuItem::with_id(app, "quit", "Quit", true, None::<&str>)?;
            let menu = Menu::with_items(app, &[&show_item, &quit_item])?;

            TrayIconBuilder::new()
                .icon(app.default_window_icon().unwrap().clone())
                .menu(&menu)
                .tooltip("Voco")
                .on_menu_event(|app, event| {
                    match event.id.as_ref() {
                        "show_voco" => {
                            if let Some(w) = app.get_webview_window("main") {
                                w.show().ok();
                                w.set_focus().ok();
                            }
                        }
                        "quit" => app.exit(0),
                        _ => {}
                    }
                })
                .build(app)?;

            // --- Intercept main window close: hide to system tray instead of destroy ---
            let handle2 = app.handle().clone();
            if let Some(main_window) = app.get_webview_window("main") {
                main_window.on_window_event(move |event| {
                    if let WindowEvent::CloseRequested { api, .. } = event {
                        api.prevent_close();
                        if let Some(w) = handle2.get_webview_window("main") {
                            w.hide().ok();
                        }
                    }
                });
            }

            // --- Register default global hotkey (Alt+Space) ---
            if let Err(e) = commands::register_global_hotkey(app.handle(), "Alt+Space") {
                eprintln!("[Voco] Failed to register default global hotkey: {e}");
            }

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
            commands::billing_checkout,
            commands::open_url,
            commands::scan_security,
            commands::validate_license,
            commands::check_signup_ip,
            commands::record_signup_ip,
            commands::type_text,
            commands::type_diff,
            commands::show_main_window,
            commands::hide_main_window,
            commands::quit_app,
            commands::set_global_hotkey,
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
