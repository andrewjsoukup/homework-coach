# plugin-catalog: add homework-coach (community, tools)

Adds `plugin-catalog/homework-coach.yaml`, pinned to `acd3d0e3c8b47ea7dd1b855041ce675fca5a5308` of
https://github.com/andrewjsoukup/homework-coach (I own and maintain the repo).

## What it does

A parent photographs a child's homework. Homework Coach reads the photo, records the skill
practised, the *format* of each task and the likely slips in a per-child learning brief,
then builds a short daily practice packet: one printable PDF per child plus a separate
parent answer key. The parent rates each item **I** (independent), **S** (supported) or
**N** (not yet), either in chat (`nova 1=I 2=S S1=N`) or in the Desktop panel. The next
packet moves at most one difficulty dimension per skill. Scope for 0.1.0 is elementary
math: counting through fractions, 31 task formats, grades K–5.

Before any packet is delivered, every answer is recomputed by an independent arithmetic
checker (no `eval`), every drawn picture is counted against its prompt and answer, child
PDFs are re-read to confirm they contain no answers, and pages are rasterised to check
they are non-blank. If a check fails, the tool returns an error plus a text fallback, never
an unverified PDF.

## Hermes surfaces used (all public)

| Surface | Use |
|---|---|
| `ctx.register_tool` ×4 | `homework_coach_intake`, `_generate_packet`, `_record_feedback`, `_status` |
| `ctx.register_command` | `/homework status\|packet\|feedback\|schedule` |
| `ctx.register_skill` | bundled `workflow` skill |
| `ctx.register_auxiliary_task` | `homework_vision` (inherits `vision`), so users can route photo reading to a specific or local model |
| `ctx.register_automation_blueprint` | `homework-coach:daily-packet`: the user schedules it; the plugin never creates cron jobs |
| `ctx.llm` | vision read of homework photos on the user's provider |
| `ctx.current_cron_execution` | replies `[SILENT]` on off days, `[CRON_FAILURE]` on build failure |
| `ctx.get_config` | `config_schema`: family config path, output dir, history days, keep photos |
| `plugins.plugin_storage.plugin_data_dir` | all state under `plugin-data/homework-coach/` |
| Desktop SDK (`desktop/plugin.js`) | route page, sidebar row, palette command; imports only `@hermes/plugin-sdk/react` |
| Dashboard backend (`dashboard/plugin_api.py`) | `/api/plugins/homework-coach/` routes for the panel (overview, intake upload, feedback) |

No hooks, no middleware, no `requires_env`, no `requires_auth`, no `oauth`.

## Disclosures (rule 13)

- **Third-party network:** none made by the plugin. Homework photos are sent to the
  **user's configured model provider** through `ctx.llm` (or the model assigned to the
  `homework_vision` aux task). With a cloud provider, a child's handwriting leaves the
  machine. This is stated in the README and in PRIVACY.md.
- **Reads outside its own data:** only image paths the user passes to the intake tool, and
  the family YAML at the configured `family_config` path.
- **Writes:** only `<HERMES_HOME>/plugin-data/homework-coach/`, or the user's `output_dir`
  for packets.
- **Shell commands / background processes / threads:** none.
- **Credentials:** none stored or read.
- **Telemetry:** none.
- **Scheduled delivery:** only through a cron job the user creates from the blueprint. It
  posts the PDFs, including the parent answer key, to that job's delivery target.
  Disabling the plugin leaves those jobs in place (standard Hermes behaviour); the README
  says how to remove them.
- **Desktop panel upload:** accepts JPG/PNG/WEBP/GIF/HEIC up to 20 MB, checked by magic
  bytes. It stages the file under plugin-data and deletes it after intake.
- **Children's data:** the repository contains only fictional data (a synthetic "Maple"
  family with generated worksheet images). A hygiene test fails the build on bytecode or
  binaries, credential reads or absolute user paths.

## Validation

`hermes plugins validate <checkout> --install-deps` **passed** on the exact pinned
commit in a fresh Ubuntu GitHub Actions runner. Hermes was checked out at
`b200f5bc60e31588ba2cb60e288029c4a54ba5fa` (v0.22.7), with a separate, locked
validator runtime and throwaway `HERMES_HOME`. The run installed the declared
`reportlab` and `pypdf` dependencies; it did not touch a live Hermes installation.

Evidence: https://github.com/andrewjsoukup/homework-coach/actions/runs/42140161188

All admission checks passed, including capability registration, built-in tool
collisions, the security scan (`safe`), no core override, and the Desktop SDK
surface check. The dashboard backend runs through the plugin host.

Also verified against this publication snapshot:
- pytest: **176 passed, 2 skipped** (optional panel-router tests requiring FastAPI).
- Desktop React SSR tests: **4/4 passed**.
- `scripts/validate_plugin_catalog.py catalog/homework-coach.yaml`: **OK** with the
  real 40-character pin.
- Banner and all four catalog screenshots: HTTP 200 at the pinned URLs; SHA-256
  hashes match the local files.

The live Desktop smoke test and real scheduled-chat delivery remain unverified;
this PR does not claim those checks have run.

## Screenshots

All generated from the fictional demo (`demo/run_demo.py`):

- Homework photo (input): `docs/screenshots/01-homework-photo.png`
- Child packet: `docs/screenshots/02-child-packet-nova.png`
- Parent key with I/S/N boxes: `docs/screenshots/03-parent-key.png`
- Packet two days later, adapted from feedback: `docs/screenshots/05-adapted-packet-nova-wed.png`
- Desktop panel: not included yet; the live Desktop smoke check is still in progress.

## Checklist

- [x] One file, `plugin-catalog/homework-coach.yaml`
- [x] `sha` is a full 40-char commit; `version` quoted and matches `plugin.yaml` (0.1.0)
- [x] `requires_hermes` matches `plugin.yaml` (`>=0.22.5`), SemVer, not newer than current
- [x] Capabilities match registrations (validate: declared tools/hooks/middleware ✓)
- [x] No self-updater, no binaries/bytecode, no credential reads, no core overrides
- [x] Images on raw.githubusercontent.com, pinned to the entry sha
