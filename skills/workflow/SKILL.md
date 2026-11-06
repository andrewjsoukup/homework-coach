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
`homework_coach_record_feedback`, `homework_coach_status`.

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
