# Open Vision Vite

An on-site network management tool for Windows tablets. Each tablet is deployed standalone at a single site and provides live network topology visualization and device monitoring.

## v1.0.0 scope

- **Topology graph** — built from SNMP LLDP-MIB / CDP-MIB neighbor discovery and ARP table reads.
- **Device info query** — standard SNMP MIBs (sysDescr, ifTable) plus ARP/mDNS passive discovery.

Remote control (port shutdown, VLAN config) and configuration backup/diff are out of scope for v1.0.0 — they require vendor-specific device drivers and are deferred to a later release.

## Architecture

- `frontend/` — Vite + React + TypeScript + Tailwind CSS. Renders the topology graph (Cytoscape.js) and device info views.
- `backend/` — Python FastAPI. Owns SNMP polling / LLDP / ARP discovery logic, exposes a localhost-only REST API.
- `src-tauri/` — Tauri desktop shell. Wraps the built frontend and launches the backend as a local sidecar process. No cloud backend, no cross-site communication.

## Security posture

Designed against IEC 62443 principles as a baseline (not formally certified): localhost-only API binding, no wildcard CORS, encrypted-at-rest credential storage, minimal-privilege backend process, structured logging groundwork.

## Development

```bash
npm run dev   # starts backend (FastAPI) + frontend (Vite) together
cargo tauri dev   # from src-tauri/, or via root script — runs the desktop shell against the dev servers
```

See `CHANGELOG.md` for release history.
