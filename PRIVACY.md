# Privacy: children's data stays local

Homework Coach handles children's schoolwork. The design rule is that **everything it
stores stays on the machine running Hermes**, and the only thing that ever leaves is what
you explicitly route through your own Hermes setup.

## What is stored, and where

Everything lives under `<HERMES_HOME>/plugin-data/homework-coach/` (or the `output_dir`
you configure). Nothing is written anywhere else.

| Data | File(s) | Removable |
|---|---|---|
| Family config: first names (or nicknames), grades, curricula, schedule | `family.yaml` (or your `family_config` path) | Edit or delete the file |
| Per-child learning brief: skills seen, task formats, likely slips, classroom anchors | `children/<id>/brief.md`, `observations.jsonl`, `state.json` | Delete the child's folder |
| I/S/N feedback history | `children/<id>/feedback.jsonl` | Delete the file; skill levels rebuild from what remains |
| Copies of homework photos | `children/<id>/sources/` | Set `keep_source_images: false`; delete the folder |
| Daily packets (child PDFs + parent key) | `packets/<YYYY-MM-DD>/` | Delete any dated folder |
| Desktop-panel upload staging | `uploads/<id>/` | Deleted automatically after intake |

To wipe everything, disable the plugin and delete `plugin-data/homework-coach/`. Any
cron jobs you created from the blueprint are yours: remove them with `hermes cron`.

## What leaves the machine, and only when you choose it

1. **Homework photos go to your model provider.** Reading handwriting requires a vision
   model, so intake sends the photo(s) through Hermes's `ctx.llm` to whatever provider you
   have configured (or the model you assign to the `homework_vision` auxiliary task). If
   that provider is a cloud API, the photo leaves your machine under that provider's
   terms. To keep photos fully local, assign `homework_vision` to a local vision model.
   Packet generation and answer checking are deterministic local code. No model sees the
   packets.
2. **Packets go wherever you deliver them.** If you schedule the
   `homework-coach:daily-packet` blueprint, Hermes's normal cron delivery posts the PDFs,
   including the parent answer key, to the chat you picked. Anyone in that chat can see
   them.

Homework Coach itself makes **no network calls**, runs **no shell commands** or background
processes, has **no telemetry or analytics**, and **holds and reads no credentials** (no
`requires_env`, no OAuth, no `.env` reads).

## Recommendations for parents

- Use first names or nicknames in `family.yaml`. The plugin never needs surnames, schools
  or teacher names.
- Crop photos to the worksheet. Avoid faces, name labels and school letterheads.
- Deliver packets to a private chat, not a group.
- Results are practice signals from a few photos. They are not diagnoses, grades or
  mastery claims.

## For contributors

The repository contains **only fictional data** (the "Maple" family: Nova and Pip;
synthetic, generated worksheet images). `tests/test_repo_hygiene.py` fails the build on
committed bytecode or binaries, credential reads, or absolute user paths. Never commit a
real child's name, photo or work, even in an issue or test fixture.
