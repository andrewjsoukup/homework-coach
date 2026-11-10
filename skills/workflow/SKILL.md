---
name: workflow
description: "Use when analysing a child's homework photo or designing their practice packet."
version: 0.1.0
metadata:
  hermes:
    tags: [homework, worksheets, family-learning]
---

# Homework Coach workflow

Tools: `homework_coach_intake`, `homework_coach_generate_packet`,
`homework_coach_record_feedback`, `homework_coach_status`, `homework_coach_progress`,
`homework_coach_set_curriculum`, `homework_coach_add_material`.

Homework Coach supplements school; it does not replace it. The school-assigned
homework photo is the steering signal: practice follows what the class is doing
this week, and the parent's I/S/N ratings tune difficulty between photos.

## Preload the curriculum (once per school year)
1. Research it yourself first: the child's district pacing guide / scope and
   sequence, the publisher program in the child's `curriculum`, and the grade
   standards. Prefer official district or publisher pages; cite them.
2. Call `homework_coach_set_curriculum` with units in order, best-estimate
   dates, goals, standards and source URLs. Map each unit to the closest skill;
   leave `skill` empty when none fits (it is recorded, not practised).
3. Tell the parent the dates are estimates and that homework photos win.

## Teacher materials
When the parent shares a newsletter, unit overview, study guide or practice
page, read it, then call `homework_coach_add_material` with the skill, stated
goals and a one-line summary. If it shows the class is ahead of or behind the
plan, offer to correct the unit dates with `homework_coach_set_curriculum`.

Steering order for each packet: homework photo from the last 14 days →
curriculum unit active today → grade default.

## Observe before adapting
1. Separate printed prompts, the child's working, final answers, skip or
   not-assigned marks, and teacher/parent marks. Crop or re-ask vision about one
   item before telling a parent it is wrong.
2. Score **attempted** items only. Blank or crossed-out ≠ incorrect.
3. Right answer + wrong intermediate line → *checking target*. A miss where the
   same rule is applied correctly elsewhere → *likely slip*. A true answer
   beyond grade level is not an error; give the expected grade-level answer.
4. Record the **skill and the task format** (e.g. `array -> equation`,
   `select-all equivalents`), not just the numbers.
5. Never infer mastery, pacing, or a diagnosis from one photo.

## Design the next packet
- Fresh analogues of formats, not copies of the homework. Rotate
  representations; changing names/operands alone is not variety. Avoid the same
  ordered template as the last three packets.
- Mix current classroom target, supporting review, small optional stretch.
- Move difficulty one dimension at a time from I/S/N feedback; never raise the
  whole core because a day passed.
- New topic → dated *Current classroom anchor* in the brief; prior topic becomes
  supporting review; item budget unchanged.
- No answers on child pages. Separate parent key with worked solutions and an
  I/S/N prompt.

## Measure and monitor
- When the parent asks how a child is doing, whether practice still matches
  class, or wants a weekly check-in, call `homework_coach_progress` and reply
  with its `message`. It reports the current class focus (latest photo), rated
  practice days, share done on their own vs the prior window, and per-skill
  trends.
- If the last homework photo is more than a week old, ask for a new one rather
  than guessing what class is on.
- Describe trends plainly; never turn a few ratings into a diagnosis or grade.

## Delivery
Report "brief updated" separately from "packet generated". When delivering a
packet, reply with the tool's `message` verbatim — its `MEDIA:` lines attach the
PDFs; never retype paths or answers. If rendering fails, the `message` carries the
full problems and a separated key as text; send it and state the failure.

## Feedback replies
A parent reply like `nova 1=I 2=S S1=N` (one line per child) is feedback on the
latest packet: call `homework_coach_record_feedback` with `reply` set to the text
and tell the parent what changes next time (the result's `message`). If the tool
reports unknown items, ask about those only. To set up daily packets, run
`/homework schedule` and follow the printed blueprint commands.
