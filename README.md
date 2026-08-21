# NMS Vite

An on-site network management tool for Windows tablets. Each tablet is deployed standalone at a single site and provides live network topology visualization and device monitoring.

## v1.0.0 scope

- **Topology graph** — built from SNMP LLDP-MIB / CDP-MIB neighbor discovery and ARP table reads, including this tablet's own IP/MAC as the root node.
- **Device info query** — standard SNMP MIBs (sysDescr, ifTable) plus ARP passive discovery, with an offline MAC OUI lookup filling in the vendor for devices that have no SNMP agent.
- **Host Monitor** — lists every discovered device (including this tablet itself) with an on-demand ping button, showing reply status and round-trip latency.
- **System Log** — records login/logout, every ping attempt, device connected/disconnected transitions, and account changes as a Title/Description/Time feed, auto-refreshing every 10s.
- **Access control** — per-user login with Viewer/Operator/Admin roles; active operations like Host Monitor's ping require Operator or higher.
- **User management** — an account menu lets Admins list, create, and manage accounts (Admins get a password-change action instead of delete, so a tablet can't be locked out of admin access from the UI).
- **Tablet-responsive layout** — header, topology view, and tables adapt to narrower/portrait tablet widths, with touch targets sized to the ~44px guideline.
- **Kiosk-style startup** — the app window launches fullscreen and locked (non-resizable), matching how each tablet is actually deployed on-site.

Remote control (port shutdown, VLAN config) and configuration backup/diff are still out of scope — they require vendor-specific device drivers and are deferred to a later release.

## Architecture

- `frontend/` — Vite + React + TypeScript + Tailwind CSS. Renders the topology graph (Cytoscape.js) and device info views.
- `backend/` — Python FastAPI. Owns SNMP polling / LLDP / ARP discovery logic, exposes a localhost-only REST API.
- `src-tauri/` — Tauri desktop shell. Wraps the built frontend and, in production, launches the backend as a local sidecar process (see "Backend sidecar" below).

No cloud backend, no cross-site communication — each tablet is a standalone deployment.

## Security posture

Designed against IEC 62443 principles as a baseline (not formally certified): localhost-only API binding, no wildcard CORS, encrypted-at-rest credential storage, minimal-privilege backend process, structured logging groundwork, a restrictive CSP, and a Tauri shell permission scoped to executing only the bundled backend sidecar (no general shell access).

## Development

Two ways to run this, depending on what you're working on:

**Browser only** (fastest iteration on frontend/backend logic):
```bash
npm run dev   # starts backend (FastAPI) + frontend (Vite) together, open http://localhost:5173
```

**Desktop shell** (testing the Tauri window itself):
```bash
uv run --directory backend uvicorn app.main:app --reload --host 127.0.0.1 --port 8756   # backend, separately
npx tauri dev   # from repo root — starts its own frontend dev server and opens the native window
```

## Version control

Gitflow: `main` holds released state, `develop` integrates finished feature/fix branches. A release merges `develop` into `main` and gets tagged `vX.Y.Z`, with the tag's date matching that version's entry in `CHANGELOG.md` — pushing that tag is what triggers the Windows build below.

## Windows build (CI)

Production builds bundle the FastAPI backend as a frozen executable (`backend/pyinstaller/backend.spec`, PyInstaller) and launch it as a Tauri sidecar (`src-tauri/src/lib.rs`, wired via `tauri.conf.json`'s `bundle.externalBin`). PyInstaller cannot cross-compile, so the `.exe`/`.msi` must be built on Windows — this isn't available in local dev (macOS), so it's built in CI instead.

Pushing a tag matching `v*.*.*` (the same tags used for releases — see "Version control" above) triggers `.github/workflows/build-windows.yml` on a `windows-latest` runner, which:
1. Freezes the backend with PyInstaller and stages it at `src-tauri/binaries/nms-vite-backend-x86_64-pc-windows-msvc.exe`
2. Runs `tauri build`, producing an NSIS `.exe` installer and a `.msi`
3. Attaches both to a GitHub Release for that tag

The workflow can also be run manually (`workflow_dispatch`) without pushing a tag, e.g. to test the build pipeline itself. Locally on macOS, `cargo check`/`tauri dev` against the desktop shell still require *some* file at `src-tauri/binaries/nms-vite-backend-aarch64-apple-darwin` to exist (any placeholder executable) since Tauri's build script checks for it, but that file is gitignored and never produced automatically — only CI produces the real sidecar binaries.

## macOS build (CI)

The same tag push also triggers `.github/workflows/build-macos.yml`. Since PyInstaller can't cross-compile, the backend is frozen separately on an Intel (`macos-13`) and an Apple Silicon (`macos-14`) runner, then combined into one `.dmg` via `tauri build --target universal-apple-darwin` and attached to the same GitHub Release.

This build is **not code-signed or notarized** (no Apple Developer account yet), so Gatekeeper will flag it as from an unidentified developer — on first launch, right-click the app and choose Open, or run `xattr -cr` on it, rather than double-clicking.

See `CHANGELOG.md` for release history.
