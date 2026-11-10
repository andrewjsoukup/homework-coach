# Installing Homework Coach (0.2.0)

Requires Hermes **>=0.22.5**. The built Desktop UI ships in the package; you do not need
Node. How the pieces fit together: [PORTABILITY.md](PORTABILITY.md).

## Install from Desktop (recommended)

On the computer that will display the interface, connect Hermes Desktop to the intended
backend/profile, then open **Capabilities → Plugins → Install** and enter:

```text
https://github.com/andrewjsoukup/homework-coach
```

Install/enable both the backend and Desktop components. The app installs the backend on the
selected gateway and the Desktop bundle on this client. Open **Homework**, then
**Family & settings → Add child**. A new family adopts your browser's IANA timezone
(UTC fallback); existing families keep their configured timezone.

### Backend-only / CLI installation

Run this on the host and profile that will hold the family data:

```bash
hermes plugins install https://github.com/andrewjsoukup/homework-coach --enable
# After catalog admission: hermes plugins install homework-coach --enable
```

**Running the CLI on a remote server does not install the interface on your laptop.**
Install the Desktop component on that client using the app installer, or use the matching
UI-only ZIP below. No Node installation is needed by end users.

## By setup

**Local (Desktop and backend on one machine).** The standard install is all you need. Data is
under the active profile's `plugin-data/homework-coach/`.

**Remote / cloud backend, Desktop on your laptop.** Use the Desktop installer on that
laptop with the intended remote gateway/profile selected. If you installed the backend by
CLI instead, install the matching Desktop component on the laptop too (the UI-only ZIP
below works). The Desktop UI is client-local, but all data, packets, output and family paths are on
the backend, so:
- Give the Hermes profile's plugin-data folder, and any custom `output_dir` / `family_config`
  paths, a **persistent volume**.
- Settings paths are server-side. `~` and environment variables expand; relative paths are
  anchored to the profile's plugin-data folder.
- Run one long-lived gateway/plugin-host process. Photo and material reads are in-memory
  background jobs, so stateless/serverless or round-robin multi-worker hosting is not
  supported.
- If you use a reverse proxy, allow request bodies of at least 24 MiB (photos and teacher
  files are sent as base64 JSON, up to 15 MiB for teacher files).
- Use **Direct download** in the panel if the native Save dialog or file access is blocked
  by the host (e.g. SSH).

**Browser-hosted Desktop renderer.** Supported by Hermes core. Install and enable the plugin on
the backend as above; Save may be restricted by the browser, so use **Direct download**.
The legacy web dashboard and the native phone app are different surfaces and are not
verified; chat tools depend on which channels/tools you have enabled.

**Headless (no Desktop).** Install on the backend and use chat/CLI: put `family.yaml` in
`plugin-data/homework-coach/` (start from `examples/family.example.yaml`), send photos to
`homework_coach_intake`, schedule with `/homework schedule` and `/blueprint`, and rate with
`nova 1=I 2=S S1=N`.

## Using a second laptop (UI only)

Download the [0.2.0 Desktop UI-only ZIP](https://github.com/andrewjsoukup/homework-coach/releases/download/v0.2.0/Homework-Coach-Desktop-UI-0.2.0.zip)
when your backend is also on 0.2.0. The [release page](https://github.com/andrewjsoukup/homework-coach/releases/tag/v0.2.0)
also provides the matching public source archive.

Do **not** install a second backend or copy `family.yaml`, packets, photos or credentials.
Instead:
1. Get the UI-only ZIP that matches your backend's plugin version (same version).
2. Extract it and copy only its `homework-coach` folder into the local folder opened by
   **Capabilities → Plugins → folder icon**, so the result is
   `desktop-plugins/homework-coach/plugin.js`. Back up an existing folder outside
   `desktop-plugins` before replacing it.
3. Refresh or **Reload desktop plugins**, then connect that Desktop to the same backend.

## Upgrading from 0.1.x

- Relative path settings used to resolve elsewhere; if you rely on the old location, set
  explicit absolute paths before upgrading.
- Photo upload now uses `/intake64` JSON; the multipart `/intake` route and the
  `python-multipart` dependency are gone. HEIC/GIF are no longer accepted (use JPG, PNG, WEBP).
- The family `timezone` is editable in the schedule form. Changing it does **not** reschedule
  existing blueprint jobs; edit or recreate the cron job so Hermes's job timezone and the
  family timezone agree.
- `tzdata` is now a dependency (needed on Windows and minimal Linux).

## Verify your install

```bash
hermes plugins validate .
hermes plugins doctor . --ci
uv run --group dev pytest
npm ci && npm run build && npm test && npm run check:bundle   # development checkout only
```

Then in your own setup: open the panel, add a fictional or cropped photo, confirm the intake
job finishes, build a packet, try **Save** and **Direct download**, rate an item, and (if you
schedule) confirm the cron job's timezone. Maintainer test receipts for this release are
published with the release/PR, not asserted here.

## Uninstall / remove data

Disable the plugin, delete `plugin-data/homework-coach/` on the backend, and remove any
blueprint cron jobs with `hermes cron`. Remove `desktop-plugins/homework-coach/` on UI-only
laptops. See [../PRIVACY.md](../PRIVACY.md).
