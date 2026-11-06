# plugin-catalog: add homework-coach (community, tools)

Adds `plugin-catalog/homework-coach.yaml`, pinned to `<SHA>` of
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

`hermes plugins validate .` at the pinned commit, on Hermes v0.22.7 (deps reportlab and pypdf
were already present; catalog CI's `--install-deps` run is the authoritative check):

```
✓ manifest / manifest fields / requires_hermes '>=0.22.5' / config schema
✓ requires_env / oauth — not declared
✓ loadable — entry: __init__.py, desktop/plugin.js
✓ python dependencies — 2 requirements from pyproject (reportlab>=4.0,<6; pypdf>=4.0,<7)
✓ capability probe / declared tools / hooks / middleware
✓ built-in tool collisions — no collisions
✓ security scan — safe
✓ no core override
✓ desktop surface — stays inside the plugin SDK surface
◆ Isolation — runs in the plugin host; dashboard backend API served through the plugin host
Validation passed.
```

Also: `hermes plugins doctor . --ci` OK. pytest: 175 passed, 2 skipped (the skips are panel
router tests that need fastapi). Node SSR tests for the Desktop page: 4/4.
`scripts/validate_plugin_catalog.py` passes on the entry.

## Screenshots

All generated from the fictional demo (`demo/run_demo.py`):

- Homework photo (input): `docs/screenshots/01-homework-photo.png`
- Child packet: `docs/screenshots/02-child-packet-nova.png`
- Parent key with I/S/N boxes: `docs/screenshots/03-parent-key.png`
- Packet two days later, adapted from feedback: `docs/screenshots/05-adapted-packet-nova-wed.png`
- Desktop panel: `<add after live Desktop check>`

## Checklist

- [x] One file, `plugin-catalog/homework-coach.yaml`
- [ ] `sha` is a full 40-char commit; `version` quoted and matches `plugin.yaml` (0.1.0)
- [x] `requires_hermes` matches `plugin.yaml` (`>=0.22.5`), SemVer, not newer than current
- [x] Capabilities match registrations (validate: declared tools/hooks/middleware ✓)
- [x] No self-updater, no binaries/bytecode, no credential reads, no core overrides
- [x] Images on raw.githubusercontent.com, pinned to the entry sha
