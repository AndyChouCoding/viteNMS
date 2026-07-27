# Open Vision Vite

An on-site network management tool for Windows tablets. Each tablet is deployed standalone at a single site and provides live network topology visualization and device monitoring.

## v1.0.0 scope

- **Topology graph** — built from SNMP LLDP-MIB / CDP-MIB neighbor discovery and ARP table reads.
- **Device info query** — standard SNMP MIBs (sysDescr, ifTable) plus ARP/mDNS passive discovery.

Remote control (port shutdown, VLAN config) and configuration backup/diff are out of scope for v1.0.0 — they require vendor-specific device drivers and are deferred to a later release.

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
uv run --project backend fastapi dev app/main.py --host 127.0.0.1 --port 8756   # backend, separately
npx tauri dev   # from repo root — starts its own frontend dev server and opens the native window
```

## Backend sidecar (not yet wired)

Production builds are meant to bundle the FastAPI backend as a frozen executable (`backend/pyinstaller/backend.spec`, PyInstaller) and launch it as a Tauri sidecar. This is **not yet wired into `tauri.conf.json`**: Tauri's build script requires the sidecar binary to physically exist even for `cargo check`/`tauri dev`, and PyInstaller cannot cross-compile — a Windows `.exe` must be built on Windows (VM, hardware, or CI), which isn't available in this scaffold's dev environment (macOS). Once a Windows build environment exists, add `"externalBin": ["binaries/open-vision-backend"]` back to `tauri.conf.json`'s `bundle` section and drop the built binary at `src-tauri/binaries/open-vision-backend-<target-triple>.exe`.

See `CHANGELOG.md` for release history.
