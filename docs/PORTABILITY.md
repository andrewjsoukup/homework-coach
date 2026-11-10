# Portability model

Homework Coach has two parts with different locations.

| Part | Lives on | Holds |
|---|---|---|
| **Backend**: Python tools, `/homework` commands, blueprint, `/api/plugins/homework-coach/` routes | The host running the Hermes gateway/plugin host for the profile | All data: family config, briefs, feedback, photos, materials, packets |
| **Desktop UI**: `desktop/plugin.js` | Each client running Desktop | No authoritative family store; it uses the authenticated API. Downloads and normal browser caches can leave client-side copies. |

One profile has one backend that owns the data. Any number of clients can show the UI.

## What this means in practice

- **Paths are server-side.** `output_dir`, `family_config` and the plugin-data folder are on the
  backend, not your laptop. `~` and environment variables expand; relative paths anchor to the
  profile's plugin-data folder. Back up and persist those locations.
- **Uploads** are JPG/PNG/WEBP, downsized in the UI (long edge up to 2048 px, about 2 MiB) and
  sent as base64 JSON to `/intake64`. Teacher PDF/TXT/MD files are up to 15 MiB. A proxy needs to
  allow about 24 MiB bodies. No multipart or `python-multipart` is required.
- **Downloads.** Native Save is the default; cancelling does nothing further (the SDK reports
  nothing on cancel or error). **Direct download** is an explicit authenticated POST `/download`
  saved through a browser Blob. It serves only registered packet PDFs and material files of the
  active profile, up to 25 MiB. Use it where native file doors are blocked (remote/SSH,
  browser-hosted renderer).
- **Long reads** run as background threads/jobs in the plugin host. Jobs are in memory,
  isolated by profile/connection scope, and discarded from the UI when you switch. They need a
  single long-lived gateway/plugin-host process: stateless/serverless or round-robin
  multi-worker deployments are not supported, and a restart loses running jobs.
- **Time zones.** The first family takes the browser's IANA timezone (UTC fallback); existing
  families are preserved. Editing it does not move existing cron jobs; keep the Hermes job and
  family timezones the same. `tzdata` is bundled as a dependency.
- **Second laptop.** Copy the same-version UI-only ZIP into
  `desktop-plugins/homework-coach/plugin.js` (Capabilities → Plugins → folder icon), then
  reload desktop plugins. Do not duplicate the backend or copy family/auth data.

## Surfaces

| Surface | Status |
|---|---|
| Local Desktop + local backend | Supported; native Desktop QA was run on v0.22.7 against the 0.1.x UI |
| Desktop to remote/cloud backend | Designed for; not live-tested by the maintainer for 0.2.1 |
| Browser-hosted Desktop renderer | Supported by Hermes core; plugin not live-tested there |
| Headless chat/CLI | Tools and commands work wherever the channel exposes them |
| Legacy web dashboard, native phone app | Different surfaces; phone panel not verified |

## Privacy summary

Data resides on the backend; photos, extracted teacher text and child context go to the
configured model provider; exports put a copy on the client; scheduled delivery sends PDFs
and the parent key to the chosen channel. No direct third-party service, telemetry or
credentials. Details: [../PRIVACY.md](../PRIVACY.md).
