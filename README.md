# Homework Coach (Hermes plugin)

A personal tutor and coach that follows your child's class. School homework is the
steering wheel: snap a photo of what the teacher sent home and practice shifts to
what the class is on this week. It supplements school, it doesn't replace it.

Take a photo of your child's homework. Homework Coach notes the skill being practised,
the *format* of each task, and where your child slips. It keeps all of that in a
per-child learning brief. On the schedule you choose, it builds a short, fresh practice
packet: a printable PDF for each child plus a separate parent answer key. Rate each item
**I** (independent), **S** (supported) or **N** (not yet), and the next packet adjusts
one step at a time.

> Status: **0.2.4**. Elementary math (counting, place value, add/sub, multiplication,
> division, fractions; 31 task formats). See [SPEC.md](SPEC.md).

![Homework Coach: a tutor and a student working through practice problems](docs/screenshots/banner.png)

**Privacy:** data is stored on the **backend** host (the machine running the Hermes
gateway/plugin host for the active profile), which may not be the machine you are looking at.
Homework photos, extracted teacher-material text and child context go to the model provider
you configure. See [PRIVACY.md](PRIVACY.md) and the
[disclosure](#what-this-plugin-does-with-your-data-disclosure) below.

### What it looks like

All of these come from the fictional demo family (`python demo/run_demo.py`). Nothing here
is a real child's work.

| Homework photo (input) | Child packet | Parent key with I/S/N boxes |
|---|---|---|
| ![Synthetic grade-3 arrays worksheet](docs/screenshots/01-homework-photo.png) | ![Nova's practice packet](docs/screenshots/02-child-packet-nova.png) | ![Parent answer key](docs/screenshots/03-parent-key.png) |

| Kindergarten packet (read-aloud) | Two days later, after feedback |
|---|---|
| ![Pip's kindergarten packet](docs/screenshots/04-child-packet-pip-k.png) | ![Nova's adapted Wednesday packet](docs/screenshots/05-adapted-packet-nova-wed.png) |

### How a packet is checked before you see it

- Every answer is recomputed from the item's printed numbers by an independent
  arithmetic checker (no `eval`), not trusted from the generator.
- Every drawn picture (dots, arrays, groups, ten frames, bars, blocks) is counted
  as it is drawn and compared with the prompt and the answer.
- Child PDFs are re-read and must contain every item and no answers or worked
  solutions; the parent key must contain every answer.
- Pages are rasterised (when `pypdfium2` is installed) and must be non-blank with
  clear margins; all text is bounds-checked while drawing.
- If any check fails, nothing is delivered as a packet: the tool returns the
  error plus a text version with a separated key.

## Install

Requires Hermes **>=0.22.5**. Full steps for local, remote/cloud, browser-hosted Desktop and
headless setups, plus adding a second laptop, are in
[docs/INSTALLATION.md](docs/INSTALLATION.md); the portability model is in
[docs/PORTABILITY.md](docs/PORTABILITY.md).

```bash
hermes plugins install https://github.com/andrewjsoukup/homework-coach --enable
# After catalog admission: hermes plugins install homework-coach --enable
```

A standard **Desktop-app** install provides both the backend and the client-local UI.
Running the CLI on a remote server does **not** install the interface on your laptop;
install its Desktop component there too (or use the same-version UI-only release ZIP).
The UI creates the first family from **Family & settings → Add child**; you can also copy
`examples/family.example.yaml` into the plugin-data folder as `family.yaml` and edit it.
Fields are name, grade, curriculum, minutes per day, schedule and timezone; the schema is in
[`schemas/family.schema.json`](schemas/family.schema.json). To get a new sheet every practice
day, turn on **Daily sheets** in **Family & settings** (or run `/homework daily on`).

## How to get the best results

1. **Preload the curriculum.** Tell Hermes the school program (e.g. "Nova is grade 3,
   Savvas enVision"). It researches the district pacing guide and standards and saves
   the year's units, dates and goals, so practice follows class even in weeks with no
   homework. Share teacher newsletters or unit overviews any time; they sharpen the goals.
2. **Steer with real homework.** Photograph school-assigned homework a couple of times a
   week, especially when a new unit starts. The newest photo sets the class focus; the
   previous topic becomes review.
3. **Rate every packet in one line.** `nova 1=I 2=S 3=N` takes ten seconds and is what
   moves difficulty: one step per skill, never a jump.
4. **Check in weekly.** Ask "how is Nova doing?" or run `/homework progress`. You'll see
   what class is on, how many days were practised, and whether more items are being done
   on their own than two weeks ago. If the last photo is over a week old, it tells you.

## Tools and commands

| | |
|---|---|
| `homework_coach_intake` | Analyse homework photo(s) for a child |
| `homework_coach_generate_packet` | Build + verify today's PDFs (idempotent per date) |
| `homework_coach_record_feedback` | Record I/S/N ratings, e.g. the parent's chat reply `nova 1=I 2=S S1=N` |
| `homework_coach_status` | Children, skill levels, recent packets |
| `homework_coach_set_curriculum` | Save the researched school-year plan: units, dates, goals, standards, sources |
| `homework_coach_add_material` | Save teacher material (newsletter, unit overview, study guide) and the goals it states |
| `homework_coach_progress` | Parent progress report: class focus, practice days, share done on their own vs the prior window, per-skill trends |
| `/homework status [child]` | Status |
| `/homework packet [YYYY-MM-DD] [child...]` | Build (or re-send) a packet; replies with the PDFs attached |
| `/homework feedback <child> [YYYY-MM-DD] 1=I 2=S S1=N` | Record ratings (latest packet if no date) |
| `/homework progress [child] [days]` | Progress report (default 14 days) |
| `/homework daily [on\|off] [builtin\|model]` | Show or change Daily sheets and who writes the sheet |
| `/homework schedule` | Print the exact `/blueprint` command(s) for your family's schedules |

## Daily sheets

Turn on **Daily sheets** in **Family & settings** (or run `/homework daily on`) and each
child gets a new sheet, plus the parent key, at their practice time on their practice days.
There is no job to create. The sheet appears on Today, ready to print.

- **Off until you turn it on.** Installing the plugin makes nothing by itself.
- **How it runs.** While the Hermes gateway or Desktop backend is running, the plugin checks
  once a minute whether a scheduled child still has no sheet for today. If Hermes was not
  running at the practice time, the sheet is made when you next open Homework Coach that
  day. A day on which Hermes never runs and nobody opens Homework Coach gets no sheet.
- **One sheet per child per day.** A sheet that already exists is never rebuilt, whether it
  came from Daily sheets, the Make button, chat or a blueprint job.
- **Time zone.** Practice days and times use the family time zone, not the server's.
- **Failures.** A failed attempt is retried every 10 minutes, up to 6 times that day, and
  the reason is shown on Today and in Family & settings.
- **Sheets land in the workspace only.** Daily sheets does not send anything to a chat.

### Who writes the sheet

- **Built-in writer** (default): chooses the problems itself. No model call.
- **Your model**: your Hermes model writes the problems itself, aimed at what the child's
  latest homework reading, class unit, learning brief and your ratings show is needed:
  the exact slip rebuilt in a fresh setting, two-step stories, find-the-mistake, choose the
  matching equation, explain your thinking. Problems can carry fill-in lines that make the
  child show the first step, write the equation, check with the inverse operation or fix a
  made-up student's mistake, plus number paths and number lines with jumps drawn in. Each
  sheet gets its own short title. You can add a line per child saying what the sheets
  should work on and what the child likes.
  Nothing the model writes is printed on trust:
  1. every number answer, including every fill-in line, is recomputed by Homework Coach
     from the problem's own arithmetic;
  2. a second model call solves each problem seeing only what the child sees, and a
     different answer or an unclear problem is thrown out;
  3. the usual page checks run on the finished PDF.

  A problem that fails is rewritten once, then replaced by a built-in problem. If the model
  is unavailable the built-in writer makes that day's sheet. Expect two to four model calls
  per child per day. Assign a specific model with the `homework_writer` auxiliary task;
  otherwise your main model is used. Explain-your-thinking problems have no single answer;
  the parent key says what to look for.

## Daily packets in your chat (optional)

Daily sheets puts the sheet in the workspace. To also have the PDFs sent to a chat,
schedule the **`homework-coach:daily-packet`** Automation Blueprint. Homework Coach never
creates cron jobs or sends messages on its own; you schedule the blueprint like any other,
and Hermes's normal cron delivery sends the result:

1. In the chat where packets should arrive, run `/homework schedule`. It prints one
   command per distinct schedule in your family config, for example
   `/blueprint homework-coach:daily-packet time=08:30 days=1,3,5 children=pip deliver=origin`.
2. Run the printed command(s) (or pick **Daily homework practice packet** on the Desktop
   Cron page / dashboard Blueprints tab). That creates an ordinary cron job you can pause,
   edit or delete with the usual `hermes cron` tools.
3. At the scheduled time the job calls `homework_coach_generate_packet` and replies with
   one line per child plus `MEDIA:` lines; the gateway uploads the child PDFs and the
   separate parent key as native attachments (Telegram, Discord, Slack, ...).
4. After practice, reply in the same chat with one line per child:
   `nova 1=I 2=S S1=N` (I = on their own, S = with support, N = not yet). The agent records
   it with `homework_coach_record_feedback`, which says what changes in the next packet.

Behaviour you can rely on:

- **Same-day re-runs are safe.** A verified dated folder is never overwritten; re-running
  the job (or `/homework packet`) re-sends the same PDFs. Concurrent runs for one date
  serialize on a lock file, so exactly one builds.
- **Per-child schedules.** If children have different times, each job adds only its
  children's sheet and a separate key part (`parent_key-<child>.pdf`) to that day's folder;
  files already delivered are never rewritten.
- **Quiet on days off.** A scheduled run on a day no requested child is scheduled replies
  `[SILENT]`, so nothing is posted.
- **Honest failures.** If PDFs can't be produced, a scheduled run reports a cron failure
  (`[CRON_FAILURE]`) and still delivers the full problems plus a separated key as text.
- **Feedback is idempotent.** Re-sending the same reply changes nothing; a later rating for
  the same item replaces the earlier one (skill state is rebuilt from the feedback log).
  Difficulty moves at most one dimension per skill per packet.
- Keep the Hermes timezone and the family `timezone` the same: cron fires on the former,
  packet dates use the latter. The first family created in the UI takes the browser's IANA
  timezone (UTC if unavailable); existing families keep theirs. The timezone is editable in
  the schedule form, but changing it does **not** reschedule existing blueprint cron jobs:
  edit or recreate the job so the two agree.

## Desktop panel

The package ships a native Hermes Desktop page (`desktop/plugin.js`, prebuilt: no Node needed
to use it) plus its backend routes (`dashboard/plugin_api.py`, mounted at
`/api/plugins/homework-coach/`). Open it from the **Homework** sidebar row or
⌘K (Ctrl+K on Windows) → *Homework Coach: Open workspace*. It shows:

- each child's grade, item budget, current classroom anchor and per-skill level
  (scaffold / steps / representation / number range) with recent I/S/N tallies;
- recent packets, with **Save** (native save dialog, the default) and **Direct download**
  for each child PDF, the parent key and saved material files. Direct download is an
  authenticated browser download for hosts where the native save dialog or file access is
  blocked (e.g. remote/SSH hosts). It only serves registered packet PDFs and material files
  owned by the active profile, up to 25 MiB. Cancelling a native Save never starts a second
  download. The native chat card's **Open sheet** reaches the same buttons;
- **Add homework photo**: JPG, PNG or WEBP. Larger photos are downsized in the browser
  (long edge up to 2048 px, roughly 2 MiB) and sent as base64 JSON to `/intake64`.
  HEIC and GIF are not supported;
- **Teacher material**: images plus PDF, TXT or MD (documents up to 15 MiB). The model
  reads the material for stated goals; the original and reviewed summary/goals are saved;
- **Rate**: an I/S/N picker per packet item that records feedback through the same tool
  the agent uses;
- an editable schedule form including the family timezone.

Photo and material reads run as background jobs in the plugin host. Progress is shown in the
panel; jobs are held in memory, are scoped to the profile/connection and are discarded from
the UI if you switch profile or connection. Restarting the gateway drops running jobs.

Both halves are opt-in, like every Desktop plugin: toggle it on in **Capabilities →
Plugins**, and the backend routes only load when `homework-coach` is in
`plugins.enabled`. The panel uses only the Desktop plugin SDK (no app internals, no
`window.hermesDesktop`). The UI is client-local; data lives with the one backend/profile.
Another laptop can use a same-version UI-only ZIP (see [docs/INSTALLATION.md](docs/INSTALLATION.md))
without duplicating the backend or copying family data.

![Live Homework Coach Desktop panel with fictional Nova and Pip](docs/screenshots/06-desktop-panel.png)

This is a crop of a real Desktop capture with fictional fixture data, not a mockup. It
predates 0.2.0 and shows the earlier panel layout.

**What has and has not been verified.** An earlier native Desktop smoke check (Hermes
v0.22.7, 0.1.x UI) covered navigation, child cards, packet listing, native PDF save, folder
reveal and I/S/N feedback. 0.2.0 replaces upload, download and job handling; how to verify it
in your own setup is in [docs/INSTALLATION.md](docs/INSTALLATION.md#verify-your-install).
Live testing on a cloud-hosted backend, a browser-hosted Desktop renderer and the native
phone app has not been performed by the maintainer; the browser-hosted Desktop renderer is
supported by Hermes core, but the legacy web dashboard and the native phone app are
different surfaces, and the phone panel is not verified. Chat tools work wherever your
channel exposes them.

## What this plugin does with your data (disclosure)

- **Where data lives:** on the backend host for the active Hermes profile, under its
  plugin-data folder (and your custom output/family paths). With a remote backend that is
  the remote host, not your laptop. See [PRIVACY.md](PRIVACY.md).
- **Model provider:** homework photos, text extracted from teacher PDFs/images, and child
  context (grade, curriculum, skill state) go to your **configured Hermes model provider**
  via Hermes's `ctx.llm`. If that provider is remote, your child's handwriting and
  schoolwork leave the backend. Route this to a specific or local model with the
  `homework_vision` auxiliary task. Tool results shown in ordinary chat also enter the
  conversation history.
- **Model-written sheets (only if you choose "Your model"):** each time a sheet is made,
  the child's grade, school program, class unit and goals, the learning brief, the latest
  homework reading (problems, what the child wrote, the expected answers), your recent
  ratings and notes, what you asked the sheets to work on, and recent sheet problems go to
  your configured model provider (or the model assigned to `homework_writer`). The
  children's names and file paths are removed from that text first; the family name is
  never included. With the built-in writer nothing is sent.
- **Files read:** image paths you hand the intake tool, uploads through the panel, teacher
  material you add, and its own config. Panel uploads are staged under
  `plugin-data/homework-coach/uploads/`. Homework staging is removed after intake;
  teacher staging is removed after a reviewed save. Abandoned or failed teacher reads
  can leave staging copies until removed. `keep_source_images` controls retained homework photos.
- **Files written:** under the profile's `plugin-data/homework-coach/` (packets go to
  your `output_dir` if set): briefs, JSON state, feedback logs, copied photos (turn off
  with `keep_source_images: false`), material, packet PDFs.
- **Downloads and exports:** Save and Direct download put a copy of a PDF on the machine
  running the UI.
- **Not done:** no direct third-party service calls, no telemetry, no credentials stored or
  read, no shell commands. On-demand daemon threads run photo/material reads in the
  background. One more background thread checks once a minute whether a Daily sheet is due;
  it does nothing unless you turned Daily sheets on. The plugin creates no cron jobs: a
  chat-delivery schedule only exists if you create the blueprint job.
- **Scheduled delivery:** a job you create from the blueprint sends the packet PDFs
  (including the parent answer key) to that job's delivery channel, by default the chat you
  created it from. Anyone who can read that chat sees them. Disabling the plugin
  leaves existing jobs in place (Hermes keeps them); delete them with `hermes cron`.
- It does not diagnose or grade against official pacing, and it does not claim mastery
  from a single photo.

## Development

```bash
uv run --group dev pytest                 # Python tests
npm ci                                    # Desktop build/test dependencies
npm run build                             # rebuild desktop/plugin.js after editing desktop/src/
npm test                                  # Desktop tests
npm run check:bundle                      # confirm the committed bundle matches the source
hermes plugins validate .
hermes plugins doctor . --ci
```

The built `desktop/plugin.js` ships in the repository; Node is only needed to develop it.
Run the checks above for your own receipts; this README does not claim a particular
result for the current source.

Regenerate the README screenshots from the demo PDFs with
`python demo/run_demo.py --out demo/out --keep` followed by `python demo/make_screenshots.py`.

All fixtures are fictional. Never commit real children's names, photos or work.

License: MIT
