# Changelog

## [Unreleased]

## [v1.0.0] - 2026-08-21
### Added
- **Topology graph** — built from SNMP LLDP-MIB / CDP-MIB neighbor discovery and ARP table reads, including this tablet's own IP/MAC as the root node. Auto-refreshes every 5s.
- **Device info** — standard SNMP MIBs (sysDescr, ifTable) plus ARP passive discovery; when a device has no SNMP agent, its vendor is filled in from an offline MAC OUI lookup (IEEE's public registry) instead of being left blank.
- **Host Monitor** — lists every discovered device (including this tablet itself) with an on-demand ping button, showing reply status and round-trip latency.
- **System Log** — records login/logout, ping attempts, device connected/disconnected transitions, and account changes as a Title/Description/Time feed, auto-refreshing every 10s.
- **Access control** — per-user login with Viewer/Operator/Admin roles; active operations like Host Monitor's ping require Operator or higher. The first account created on a fresh tablet is bootstrapped as Admin.
- **User management** — an account menu (top-right, expands on hover or tap) lets Admins list, create, and manage accounts. Admin accounts get a password-change action instead of delete, to prevent locking a tablet out of admin access from the UI.
- **Tablet-responsive layout** — header, topology view, and tables adapt to narrower/portrait tablet widths, with touch targets sized to the ~44px guideline.
- **Kiosk-style startup** — the app window launches fullscreen and locked (non-resizable), matching how each tablet is actually deployed on-site.
- **Security baseline** — designed against IEC 62443 principles (not formally certified): localhost-only API binding, scoped CORS, encrypted-at-rest credential storage, a restrictive CSP, and a Tauri shell permission scoped to executing only the bundled backend sidecar.
- **Windows packaging** — the backend ships as a PyInstaller-frozen sidecar launched by the Tauri shell; CI builds and attaches the installer (`.msi`/`.exe`) to a GitHub Release on each version tag.

Remote control (port shutdown, VLAN config) and configuration backup/diff are still out of scope — they require vendor-specific device drivers and are deferred to a later release.
