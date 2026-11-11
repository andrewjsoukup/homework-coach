# Privacy: where children's data lives and where it goes

Homework Coach handles children's schoolwork. Everything it stores stays on the **backend
host**: the machine running the Hermes gateway/plugin host for the active profile. With a
local install that is your own computer; with a remote or cloud backend it is that server,
**not necessarily the device you are looking at**. Beyond the backend, data leaves only
through your own Hermes setup, as listed below.

## What is stored, and where

Everything lives under the active profile's `plugin-data/homework-coach/` on the backend
(or the `output_dir` / `family_config` paths you configure; those are server-side paths).
`~` and environment variables are expanded; a relative path setting is anchored to the
profile's plugin-data folder. Nothing is written anywhere else.

| Data | File(s) | Removable |
|---|---|---|
| Family config: first names (or nicknames), grades, curricula, schedule | `family.yaml` (or your `family_config` path) | Edit or delete the file |
| Per-child learning brief: skills seen, task formats, likely slips, classroom anchors | `children/<id>/brief.md`, `observations.jsonl`, `state.json` | Delete the child's folder |
| I/S/N feedback history | `children/<id>/feedback.jsonl` | Delete the file; skill levels rebuild from what remains |
| Copies of homework photos | `children/<id>/sources/` | Set `keep_source_images: false`; delete the folder |
| Daily packets (child PDFs + parent key) | `packets/<YYYY-MM-DD>/` | Delete any dated folder |
| Teacher originals and reviewed summaries/goals | `children/<id>/materials/`, `children/<id>/materials.jsonl` | Delete the files/folder |
| Panel upload staging | `uploads/<id>/` | Homework staging is removed after intake; teacher staging is removed after saving. Abandoned/failed teacher reads may remain here until you remove them. |
| Daily sheets switch, chosen writer, last automatic run | `daily.json`, `daily_state.json`, `daily_timer.json` | Delete the files; Daily sheets is then off |
| Background read jobs | In memory only | Lost on gateway restart |

To wipe everything, disable the plugin and delete `plugin-data/homework-coach/`. Any
cron jobs you created from the blueprint are yours: remove them with `hermes cron`.

## What leaves the backend, and only when you choose it

1. **Homework photos and teacher material go to your model provider.** Reading handwriting
   or teacher image requires a model, so the plugin sends homework/teacher images,
   text extracted from teacher PDFs/text files, and child context through Hermes's
   `ctx.llm` to whatever provider you have configured (or the model you assign to the
   `homework_vision` auxiliary task). If that provider is a cloud API, the content leaves
   your backend under that provider's terms. To keep it local, assign `homework_vision` to a
   local vision model. With the built-in writer, packet generation and answer checking are
   deterministic local code and send nothing.
2. **Model-written sheets, only if you choose "Your model".** Each time a sheet is made, the
   child's grade, school program, class unit and goals, the learning brief, the latest
   homework reading (problems, what the child wrote, expected answers), your recent ratings
   and notes, what you asked the sheets to work on, and recent sheet problems go to your
   configured provider (or the model you assign to the `homework_writer` auxiliary task).
   The children's names and file paths are removed from that text before it is sent, and
   the family name is never included; other details you typed in a note are sent as
   written. The model writes the problems. A second call sends the written problems back
   to the same provider to be solved blind. Number answers are recomputed by local code.
   With Daily sheets on, this happens on each child's practice days without anyone opening
   the app.
3. **Chat results enter the conversation.** Output returned by the tools in ordinary chat
   becomes part of that conversation and your channel's/provider's history.
4. **Packets go wherever you deliver them.** If you schedule the
   `homework-coach:daily-packet` blueprint, Hermes's cron delivery sends the PDFs,
   including the parent answer key, to the channel you picked. Anyone in that chat can see
   them.
5. **Exports and downloads put a copy on the client.** Save and Direct download write a PDF
   to the machine running the Desktop UI. Direct download is an authenticated request that
   serves only registered packet PDFs and material files of the active profile (max 25 MiB).

Homework Coach itself makes **no direct third-party service calls**, runs **no shell
commands**, has **no telemetry or analytics**, and **holds and reads no credentials** (no
`requires_env`, no OAuth, no `.env` reads). Photo/material reads run as in-process
background threads inside the plugin host, as does the once-a-minute Daily sheets check,
which does nothing until you turn Daily sheets on. The plugin creates no cron jobs.

## Recommendations for parents

- Use first names or nicknames in `family.yaml`. The plugin never needs surnames, schools
  or teacher names.
- Crop photos to the worksheet. Avoid faces, name labels and school letterheads.
- Deliver packets to a private chat, not a group.
- On a remote/cloud backend, protect that host (disk, backups, access) as you would the
  child's records, and use a persistent volume so the data survives restarts.
- Results are practice signals from a few photos. They are not diagnoses, grades or
  mastery claims.

## For contributors

The repository contains **only fictional data** (the "Maple" family: Nova and Pip;
synthetic, generated worksheet images). `tests/test_repo_hygiene.py` fails the build on
committed bytecode or binaries, credential reads, or absolute user paths. Never commit a
real child's name, photo or work, even in an issue or test fixture.
