use std::sync::Mutex;

use tauri::Manager;
use tauri_plugin_shell::process::{CommandChild, CommandEvent};
use tauri_plugin_shell::ShellExt;

struct SidecarProcess(Mutex<Option<CommandChild>>);

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
  tauri::Builder::default()
    .plugin(tauri_plugin_shell::init())
    .setup(|app| {
      if cfg!(debug_assertions) {
        app.handle().plugin(
          tauri_plugin_log::Builder::default()
            .level(log::LevelFilter::Info)
            .build(),
        )?;
      } else {
        // In dev, the backend is started separately via `npm run dev`. In
        // production there's no such step, so spawn the frozen FastAPI
        // backend (backend/pyinstaller/backend.spec, bundled via
        // tauri.conf.json's bundle.externalBin) as a sidecar here. Killed on
        // app exit below so it doesn't linger as an orphan process.
        let (mut events, child) = app.shell().sidecar("open-vision-backend")?.spawn()?;
        app.manage(SidecarProcess(Mutex::new(Some(child))));

        tauri::async_runtime::spawn(async move {
          while let Some(event) = events.recv().await {
            if let CommandEvent::Stderr(line) = event {
              log::error!("backend: {}", String::from_utf8_lossy(&line));
            }
          }
        });
      }
      Ok(())
    })
    .build(tauri::generate_context!())
    .expect("error while running tauri application")
    .run(|app_handle, event| {
      if let tauri::RunEvent::ExitRequested { .. } = event {
        if let Some(state) = app_handle.try_state::<SidecarProcess>() {
          if let Some(child) = state.0.lock().unwrap().take() {
            let _ = child.kill();
          }
        }
      }
    });
}
