#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]
use std::sync::Mutex;
use tauri::{Manager, RunEvent};
use tauri_plugin_shell::{ShellExt, process::CommandChild};

struct Backend(Mutex<Option<CommandChild>>);
fn main() {
    let app = tauri::Builder::default()
        .plugin(tauri_plugin_single_instance::init(|app, _, _| {
            if let Some(window) = app.get_webview_window("main") { let _ = window.set_focus(); }
        }))
        .plugin(tauri_plugin_shell::init())
        .manage(Backend(Mutex::new(None)))
        .setup(|app| {
            let (mut receiver, child) = app.shell().sidecar("atmosight-backend")?.spawn()?;
            *app.state::<Backend>().0.lock().unwrap() = Some(child);
            tauri::async_runtime::spawn(async move {
                while let Some(event) = receiver.recv().await { eprintln!("Backend: {:?}", event); }
            });
            Ok(())
        })
        .build(tauri::generate_context!())
        .expect("Could not start Atmosight");
    app.run(|handle, event| {
        if let RunEvent::Exit = event {
            if let Some(child) = handle.state::<Backend>().0.lock().unwrap().take() {
                // PyInstaller onefile owns a worker process; close the entire owned tree.
                #[cfg(target_os = "windows")]
                {
                    use std::os::windows::process::CommandExt;
                    let _ = std::process::Command::new("taskkill")
                        .args(["/PID", &child.pid().to_string(), "/T", "/F"])
                        .creation_flags(0x08000000).status();
                }
                let _ = child.kill();
            }
        }
    });
}
