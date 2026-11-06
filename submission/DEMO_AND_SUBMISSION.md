# Homework Coach: demo video, X post and hackathon form

Deadline: **Wednesday, November 11, 2026, 5 PM ET (4 PM Central)**. You need all three:
1. a catalog PR (card t_9f0d1f8d),
2. a demo video **under 90 seconds** posted on X tagging **@NousResearch**,
3. both links submitted at <https://form.typeform.com/to/FwJLvOln>.

The form can be submitted as soon as the PR is open; the catalog CI doesn't need to be green yet.

Everything on screen is the fictional Maple family (Nova, grade 3; Pip, K). No real child's work.

---

## 1. Recording setup (about 10 minutes, once)

Use a throwaway profile so your real Hermes stays untouched. This is the same setup card
t_ffb2f3fb asks you to approve, so one setup covers both.

```bash
cd <this repo>                                       # Git Bash
hermes profile create hc-demo                       # throwaway; delete after recording
hermes -p hc-demo plugins install "file://$(pwd -W)" --enable
# pwd -W gives C:/...; file:// + that (two slashes) is the form Git for Windows clones. It installs the last commit,
# and file:// prints a security warning, which is expected for a local install.

# Seed "a week of practice": real engine, all-I ratings until hint lines have faded.
.venv/Scripts/python demo/video_demo.py --seed "$LOCALAPPDATA/hermes/profiles/hc-demo/plugin-data/homework-coach"
# (macOS/Linux: ~/.hermes/profiles/hc-demo/plugin-data/homework-coach)
```

The seed writes the demo family config and Nova's state into the profile's plugin data. It
refuses to write into a folder that isn't empty. After seeding, multiplication support is
at `scaffold=3`, so today's packet has **no hint lines**. One **N** brings them back on the
next packet. That's the visible adaptation in shot 5.

Rehearse once before recording: `python demo/video_demo.py` replays the same story offline
and writes the frames to `demo/out/video/frames/` (`A_child_packet.png`, `A_parent_key.png`,
`B_child_packet.png`) plus `video_transcript.md`. Use the frames as B-roll if a live step
misbehaves.

Screen: 1920×1080, Hermes Desktop or CLI at about 125% zoom, dark mode off (the PDFs are white).
Open PDFs in a viewer zoomed to page width, since full pages are too small to read on a phone.

---

## 2. Script (~85 s, ~190 spoken words)

| # | Time | On screen | Voiceover |
|---|---|---|---|
| 1 | 0:00–0:07 | Title card: **Homework Coach**, a Hermes plugin. Under it: banner.png (photo → packet → key). | "My kids bring home math homework every night. Homework Coach turns it into tomorrow's practice." |
| 2 | 0:07–0:22 | Chat in the `hc-demo` profile: `Read Nova's homework: <repo>\demo\homework\nova_2026-09-14_arrays.png` (full path). The tool call runs. Hold on the reply: strengths, **likely slip** on item 3 (4×6=26), **checking target** on item 7. Quick zoom on the worksheet's crossed-out item 8. | "I snap a photo. It reads what she was practising, the format of each task, and where she slipped. It only scores what she attempted. A crossed-out problem isn't a wrong answer." |
| 3 | 0:22–0:40 | `/homework packet nova`. The reply lists the focus with two PDF attachments. Open `nova_practice.pdf` (fresh formats, no answers), then `parent_key.pdf` with the I/S/N boxes. | "Then it builds a fresh packet in new formats, not a copy of the worksheet. A printable page for her, and a separate answer key for me. Every answer is recomputed and every picture is counted before I see it. A child page that leaks an answer never ships." |
| 4 | 0:40–0:55 | Type the reply: `nova 1=N 2=I 3=I 4=I 5=I 6=I` (rate a multiplication item N; check the key for which one). Hermes replies: `… multiplication down (next packet <date>)`. | "After practice I rate each problem: I for independent, S for supported, N for not yet. One line in chat." |
| 5 | 0:55–1:12 | `/homework packet <tomorrow's date> nova`. Split screen: today's page (no hints) next to tomorrow's (gray **Hint:** lines back on the multiplication items). Circle the hints. | "She missed one, so tomorrow's multiplication brings back the hints. When she nails a few days in a row, they fade. It moves one step at a time, never a cliff." |
| 6 | 1:12–1:22 | `/homework schedule` prints the `/blueprint homework-coach:daily-packet …` command. Optional: the Desktop panel with Nova's and Pip's skill levels (only if t_ffb2f3fb is done). | "Schedule it once and packets arrive in Telegram or wherever you chat, every school morning." |
| 7 | 1:22–1:28 | End card: `hermes plugins install homework-coach`, plus "Children's data stays on your machine." | "Homework Coach. Your kid's homework, turned into tomorrow's practice." |

Notes:
- Shot 2 uses the real vision model on the synthetic page. If it misreads, use the
  Desktop panel's **Add homework photo** instead, or cut to the README's
  `01-homework-photo.png` with the offline transcript text.
- Shot 4: the reply text must name item ids that exist in that day's packet. The key
  shows which items are multiplication. `video_demo.py` rated the first multiplication item N.
- Shot 5: an explicit date is allowed with `/homework packet`. Today's packet is reused
  as-is, so re-running shot 3 is safe.
- Captions: burn in short labels ("photo in", "packet out", "1-line feedback", "adapts")
  because most people watch on X with the sound off.

---

## 3. X post (paste; attach the video)

> My kids' math homework → tomorrow's practice, automatically.
>
> Homework Coach for @NousResearch Hermes Agent: snap a photo, get a fresh printable packet + parent key. Rate each problem I/S/N and the next packet adapts.
>
> Every answer is checked before it ships. Kids' data stays local.
>
> #HermesAgent

(About 270 characters. Add the PR link as a reply under the post, not in the post itself,
because X downranks posts with links.)

---

## 4. Typeform answers (fields as of Nov 5; all required)

| Field | Answer |
|---|---|
| Plugin Title | `Homework Coach` |
| Plugin Description | `Photograph your child's homework; Homework Coach builds a fresh, verified daily practice packet (child PDF + parent answer key) in new formats, and adapts difficulty from one-line I/S/N parent feedback. Children's data stays local.` |
| Email Address | your choice (contact email for the prize) |
| Discord Username | your Discord handle (the entry thread opens in the Nous Discord after close) |
| X Demo Post Link | URL of the post from section 3 |
| (statement) | Click **Continue** |
| GitHub Link to your Hermes Plugin Pull Request | `https://github.com/NousResearch/hermes-agent/pull/<n>` from card t_9f0d1f8d |

---

## 5. Checklist (in order)

- [ ] **t_9f0d1f8d**: public repo pushed, sha pinned in `catalog/homework-coach.yaml`, PR opened.
- [ ] Add the X post link to the PR description once it's posted.
- [ ] Recording setup (section 1), plus one offline rehearsal (`python demo/video_demo.py`).
- [ ] Record. Keep it **under 90 s**. Check that no real names, paths with personal data or other chats are visible.
- [ ] Post on X with **@NousResearch** in the text. Copy the post URL.
- [ ] Submit the Typeform (section 4). Screenshot the "Submission Received" page.
- [ ] Clean up: `hermes profile delete hc-demo` (approve the confirmation prompt).
- [ ] Before Nov 11 4 PM CT: check that the PR is still open and the catalog CI result (once a maintainer runs it).
