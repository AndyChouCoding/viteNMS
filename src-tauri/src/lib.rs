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
      }
      // Production builds spawn the frozen FastAPI backend as a sidecar here
      // (see backend/pyinstaller/backend.spec + tauri.conf.json's
      // bundle.externalBin). Not yet wired: the sidecar binary must be built
      // on Windows, which this scaffold doesn't have access to — see the
      // project plan's "Risks" section. In dev, the backend is started
      // separately via `npm run dev`.
      Ok(())
    })
    .run(tauri::generate_context!())
    .expect("error while running tauri application");
}
