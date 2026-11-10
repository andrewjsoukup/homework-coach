# Homework Coach — Specification

Status: v0.1 — spec + scaffold (t_3252ef0b), scheduling/delivery/feedback (t_a62d383f, §9.3–9.4), core intake/brief/packet/PDF/verification
(t_55bb9476: `arith.py`, `catalog.py`, `generators.py`, `verify.py`, `packet.py`,
`render.py`, `intake.py`).

Core implementation notes:
- Intake accepts the vision model's skill labels either as catalog ids or dotted/free
  labels (`div.equal_sharing` → `division`). Local arithmetic overrides the model only
  where it can recompute; an explicit model "incorrect" is kept (it saw the working) and
  confirmed by one narrow re-read; a model "correct" overturned by arithmetic becomes a
  *likely slip* when the same format is right elsewhere. Max 3 re-reads per intake.
- Packet split: ~2/3 classroom target, ~1/3 supporting review, + 1 optional stretch
  (`S1`, harder by one notch on number_range and steps, no hint). Formats are ordered
  least-recently-used over the last `packet_history_days` packets.
- Packets are built in a temp folder and moved into `packets/<date>/` only after all
  checks pass; failed attempts go to `packets/.failed-<date>/` and are never reused.

## 1. Problem

A parent photographs a child's school homework. The plugin reads it, records
*what skill* and *what task format* the class is practising and where the child
slips, keeps that in a per-child **learning brief**, and on a schedule produces a
short, fresh **daily practice packet**: one printable PDF per child plus a
separate **parent answer key**. Parent feedback per item — **I** (independent),
**S** (supported), **N** (not yet) — steers difficulty gently, one dimension at
a time.

Generic: any family, any number of children, any grade/curriculum. Nothing in
this repository refers to a real family; all fixtures are fictional.

## 2. Goals / non-goals

Goals
- Photo → structured observation (printed prompt vs child work vs marks vs
  teacher feedback; score **attempted** items only).
- Durable per-child brief with dated "classroom anchor" sections.
- Packet generator that rotates **formats/representations**, not just operands.
- Programmatic verification: every answer computed, every drawn count matches
  its inventory, no answers on child pages, render/bounds check.
- Daily sheets: opt-in, made by the plugin's own once-a-minute check and on opening the
  workspace; no cron job. Built-in writer or the parent's model chooses the problems.
- Optional chat delivery via a Hermes Automation Blueprint (user creates the job).
- Desktop panel: children, skill progress, recent packets, upload photo, record
  feedback.

Non-goals
- Diagnosing learning disabilities, grading against official pacing, or
  claiming mastery from one photo.
- Sending email or messages itself. Delivery is Hermes's normal cron delivery
  (`deliver:` on the job the user creates).
- Storing images anywhere except the plugin's own data directory.
- Coloring pages, conference transcription (stay in the private skill).

## 3. Ported behaviour (from the private family-learning workflow)

These rules are encoded in the bundled skill (`skills/workflow/SKILL.md`) and,
where mechanical, in code:

1. **Observe before adapting.** Separate printed prompt, child working, final
   answer, skip/not-assigned marks, teacher/parent marks. Re-ask vision with a
   narrow question before reporting any single error. Validate arithmetic in
   code, never mentally.
2. **Score attempted items only.** Crossed-out/blank ≠ wrong. A right answer
   with a wrong intermediate line is a *checking target*. A miss where the same
   rule is applied correctly elsewhere is a *likely slip*. "True but beyond grade
   level" is not an error.
3. **Record skill + task format** (e.g. `array -> equation`, `select-all
   equivalents`, `multi-score story -> compare and justify`).
4. **Fresh analogues of formats.** Avoid the same ordered template on
   consecutive days; compare against the last 3 packets.
5. **Mix:** current classroom target + relevant review + small optional stretch.
6. **Progress one dimension at a time** from I/S/N evidence; never raise the
   whole core automatically because a day passed.
7. **New classroom topic** → add a dated *Current classroom anchor* to the brief
   (lesson/page, rules taught, observed work, rotating fresh formats); demote the
   prior topic to supporting review; keep the item budget.
8. **Idempotent dates.** A dated packet folder is never overwritten; a retry
   reuses verified same-date output.
9. **Honest delivery.** Distinguish "brief updated" from "packet generated". If
   PDF rendering fails, return the full problems + separated key as text and say so.

## 4. Configuration

### 4.1 Plugin settings (`plugins.entries.homework-coach.settings`, `config_schema`)

| key | type | default | meaning |
|---|---|---|---|
| `family_config` | str | `""` | Path to the family YAML (§4.2). Empty → `<data>/family.yaml`. |
| `output_dir` | str | `""` | Where dated packet folders go. Empty → `<data>/packets`. |
| `packet_history_days` | int | `3` | Prior packets compared for format rotation. |
| `keep_source_images` | bool | `true` | Copy intake photos into `<data>/children/<id>/sources/`. |

No secrets. No `requires_env`. No OAuth.

### 4.2 Family config file (`schemas/family.schema.json`)

```yaml
family_id: maple            # slug, [a-z0-9-]
timezone: America/Chicago   # IANA
schedule:                   # default for every child
  days: [mon, tue, wed, thu, fri, sat]
  time: "09:00"
children:
  - id: nova                # slug, unique
    name: Nova              # display name (fictional in fixtures)
    grade: "3"              # "K", "1".."12"
    curriculum: "District Grade 3 Math"   # free text label
    subjects: [math]        # v1 supports math; others are future
    minutes_per_day: 15     # 5..60; sets the item budget
    schedule:               # optional per-child override
      days: [mon, wed, fri]
      time: "08:30"
    reading_support: false  # true → adult-read directions (K/1 default true)
```

Validation is implemented in pure Python (`homework_coach/config.py`); the JSON
Schema file is the published contract (Desktop form, docs) and is tested to
agree with the validator.

Item budget: `items = clamp(round(minutes_per_day / 2.5), 3, 12)`; K/1 cap at 6.

## 5. Data layout (plugin data root, never the install tree)

Root = `plugins.plugin_storage.plugin_data_dir("homework-coach")`
(`<HERMES_HOME>/plugin-data/homework-coach/`, profile-scoped).

```
family.yaml                         # default family config location
children/<child_id>/
  brief.md                          # human-readable learning brief (append-only sections)
  state.json                        # machine state: skill levels, recent formats
  observations.jsonl                # one record per analysed homework page
  feedback.jsonl                    # one record per I/S/N submission
  sources/YYYY-MM-DD_<slug>.<ext>   # copied homework photos (if enabled)
packets/YYYY-MM-DD/
  <child_id>_practice.pdf
  parent_key.pdf
  packet.json                       # items, answers, formats, verification result
  progression.md                    # what changed vs previous packets and why
```

## 6. Data model (`homework_coach/models.py`)

- `Observation{date, child_id, source, items[ObservedItem], skills[], formats[], notes}`
- `ObservedItem{prompt, child_answer, expected_answer?, status: correct|incorrect|slip|checking_target|beyond_grade|unattempted|not_assigned, skill, format, confidence}`
- `SkillState{skill, level:int 1..5, dims{scaffold, number_range, steps, representation}, last_feedback[]}`
- `Feedback{date, child_id, packet_date, item_ratings{item_id: I|S|N}, note}`
- `PacketItem{id, skill, format, prompt, answer, worked_solution, visual_inventory?, optional:bool}`

## 7. Difficulty engine (`homework_coach/difficulty.py`) — implemented in scaffold

Per child, per skill:
- Each rating maps I=+1, S=0, N=−1.
- Window = last 2 feedback submissions touching that skill.
- **Step up** when every rating in the window is I (≥2 ratings) → raise exactly
  *one* dimension, rotating `scaffold → steps → representation → number_range`.
- **Step down** when the most recent submission has any N → lower the
  most-recently-raised dimension (or add scaffold if none).
- Otherwise hold. Levels clamp to 1..5. At most one dimension moves per skill per
  packet, and at most two skills move per child per packet.
- An explicit parent override ("one notch harder") is a recorded `adjustment`
  event that applies once.

## 8. Hermes surfaces (catalog-safe)

| Surface | Name | Purpose |
|---|---|---|
| tool | `homework_coach_intake` | Analyse homework photo(s) for a child → observation, brief update. Vision via `ctx.llm.complete_structured` (host-owned credentials and vision routing; no provider/model override). |
| tool | `homework_coach_generate_packet` | Build + verify + render today's packet(s); idempotent per date. |
| tool | `homework_coach_record_feedback` | Record I/S/N ratings (+note) for a packet; update skill levels. |
| tool | `homework_coach_status` | Children, current anchors, skill levels, recent packets. |
| slash command | `/homework` | `status`, `feedback <child> <date> <ratings>`, `packet [date]`. |
| automation blueprint | `homework-coach:daily-packet` | Fill-in cron job (days/time/deliver) that calls `homework_coach_generate_packet`. The user schedules it; the plugin never writes cron files. |
| skill | `homework-coach:workflow` | The observation + design rules (§3) for the model. |
| auxiliary task | `homework_vision` | Optional operator-routable slot (`inherit_from: vision`). |
| Desktop | `desktop/plugin.js` + `dashboard/plugin_api.py` | Route page `/homework-coach` + sidebar row + palette command. REST under `/api/plugins/homework-coach/`: `GET overview`, `GET packets`, `GET packets/{date}/{name}`, `POST feedback`, `POST intake` (multipart). Logic in `homework_coach/panel.py`; PDFs saved via `captureGatewayFileDownload`. |

Not used: core patching, `tools.override`, provider/model overrides,
`llm.side_question`, credentials of any kind.

`requires_hermes: ">=0.22.5"` (current stable). Python deps (pyproject):
`reportlab>=4.0,<6`, `pypdf>=4.0,<7`; render check uses `pypdfium2` *if present*
(Hermes `documents-pdf` extra) and degrades to text-bounds checks otherwise.

## 9. Pipelines

### 9.1 Intake
1. Resolve child; copy image(s) to `sources/` (if enabled).
2. `complete_structured(instructions=OBSERVE_PROMPT, input=[text, image...], json_schema=OBSERVATION_SCHEMA, task="homework_vision")`.
3. Post-process: recompute every `expected_answer` the model offered for
   arithmetic items with a safe evaluator; disagreements become `needs_recheck`
   and trigger one narrow re-ask per item (bounded, max 3).
4. Append to `observations.jsonl`; if skill/format set differs from current
   anchor → write a dated *Current classroom anchor* section to `brief.md`.
5. Return a parent-facing summary (strengths, likely slips, checking targets) —
   no diagnosis language.

### 9.2 Packet
1. Date from the host clock in the family timezone; if `packets/<date>/packet.json`
   verified → return existing paths (retry safety).
2. Per child: item budget; choose formats from anchor rotation minus formats used
   in last `packet_history_days` packets; target/review/stretch ≈ 60/30/10.
3. Item generators (deterministic, seeded by `family_id+child_id+date`) produce
   prompt, answer, worked solution, visual inventory.
4. Verifier: recompute answers, assert inventories, option exhaustiveness,
   no answer strings on child pages, text inside page bounds.
5. Render child PDFs + parent key (reportlab), re-open with pypdf, optional
   raster render; write `packet.json` + `progression.md`.
6. Return MEDIA-ready absolute paths.

### 9.3 Feedback
Accepts the parent's chat reply (`reply="nova 1=I 2=S S1=N\npip 1=S"`, optional packet
date per line, child name optional with one child) or `child_id` + `ratings`. Packet date
defaults to the child's latest packet. Item ids are checked against `packet.json`
(unknown ids reported, never stored). Each submission is appended to `feedback.jsonl`;
skill state is then **rebuilt by replay** (`difficulty.replay`): submissions for the same
packet merge (later rating wins), so re-sending a reply is a no-op and a correction
replaces the earlier rating. Only skills rated in a packet can move for that packet. The
result names the changes and the date of the next packet they apply to.

### 9.4 Scheduling and delivery (t_a62d383f)
- Public surface only: blueprint `homework-coach:daily-packet`
  (`schedule_template "{minute} {hour} * * {days}"`, slots `time`, `days` (cron dow text),
  `children` (ids or `all`), `deliver` (origin/local/any platform)). The user creates the
  job; `/homework schedule` prints one `/blueprint …` command per distinct child schedule
  (`delivery.schedule_groups`). The plugin never writes cron files.
- The job prompt makes the agent reply with the tool's `message` verbatim. `message` has a
  focus line per child and `MEDIA:<abs path>` per PDF (child sheets, then key part(s)); the
  gateway's `extract_media` turns those into native attachments (tested against the real
  parser).
- `ctx.current_cron_execution()` tells the tool it runs inside a scheduled job: unscheduled
  day → `message="[SILENT]"` (no post); failure → first line `[CRON_FAILURE]` (run recorded
  failed) followed by the text fallback.
- Idempotency: per-date lock file (`packets/.<date>.build.lock`, O_EXCL, stale after
  10 min). Verified folder → reuse. Children missing from an existing verified folder (a
  later per-child job) are built in a temp dir and added as new files only
  (`<child>_practice.pdf`, `parent_key-<child>.pdf`), then `packet.json` is rewritten
  atomically with `keys: {key_file: [child ids]}` and `parts`. Existing files are never
  replaced.

## 10. Risk disclosure (README + catalog PR)

- Reads image files the user points the tool at; copies them into the plugin data dir.
- Sends homework images and text to the user's **configured model provider**
  (via Hermes `ctx.llm`) — children's handwriting leaves the machine if the
  provider is remote.
- Writes PDFs/JSON/Markdown under the plugin data dir (or configured `output_dir`).
- No network calls of its own, no shell commands, no background processes, no
  telemetry, no credentials.
- Daily sheets run only after the parent turns them on; chat-delivery runs only exist if
  the user creates the blueprint job. The plugin never writes cron files.

## 11. Testing

- `pytest` unit tests: config validation, schema/validator agreement, schedule →
  cron, difficulty engine, feedback parsing, storage paths, plugin registration
  against a fake `ctx` (capabilities declared == registered).
- Core card adds: generator determinism, verifier negative tests, PDF smoke
  (page count, no answers in child text), intake with a fake `ctx.llm`.
- Fixtures: fictional family only (card t_286440eb).
- `hermes plugins validate .` before the catalog PR (without `--install-deps`
  on Andy's live install; CI does that).

## 12. Card map

- t_3252ef0b — this spec + scaffold.
- t_55bb9476 — core: intake, brief, generators, verifier, PDF.
- t_286440eb — fictional demo family + sample homework + 3-day progression.
- t_c3e9fbd8 — Desktop panel.
- downstream — catalog PR + demo (deadline Tue Nov 11, 5 PM ET).

## 13. Open questions (non-blocking)

- Public repo owner/URL for the catalog entry (Andy).
- License: MIT assumed.
- Non-math subjects (reading/spelling) — v2.
