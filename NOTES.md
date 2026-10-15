# Drill — notes

Current release: **drill-v3** (`CACHE` in `sw.js`; `VERSION` in `index.html` mirrors it).
Built: Phase 0a from `PLAN.md` (bug fixes B1–B6), iPhone XS polish, and a "tables" add-on
(sizes, spaced review across days). Phase 0b and later are not started.

## What changed in drill-v3 — negative numbers
- **New ± button** after + − × ÷ on Home: "Negative numbers" (`cfg.signed`, default off). When it is on:
  - One or both numbers in a question can be negative, in all four operations: −7 × 8, 6 − (−4), −36 ÷ (−9), −15 + 9.
  - A negative second number is put in brackets.
  - A quarter of questions stay positive, so the sign always needs a thought.
  - It uses whichever size is picked; Squares ignore it.
- **The ± key stays on the keypad** while Negatives is on. Before this it was blank unless "Allow negative answers" was on and − was picked, which made it look missing.
- **Auto-submit never gives the sign away.** With Negatives on, it fires on the digit count alone, so tap ± before the last digit.
  Typing 56 for −56 is marked wrong. Without this, a missing auto-submit would reveal that the answer is negative.
  The grey placeholder digits also show for negative answers.
- **Timing and review.** Negative facts have their own review keys (e.g. `-7×8`) and a target time 1 s longer than the positive fact.
  Positive data is untouched.
- Fixed: at 320 px the five buttons in the operation row overflowed by about 4 px.

## What changed in drill-v2

### Phase 0a bug fixes
- **B1 Enter key.** The keypad is now the 4 × 4 grid from PLAN §4.4: `1 2 3 ⌫ / 4 5 6 ± / 7 8 9 ↵ / . 0 – ↵`.
  ↵ is always there, so negative and decimal answers can be submitted by touch, with or without auto-submit.
  Keys a question cannot use (± when negatives are off, `.` for whole answers) are blank and disabled.
- **B2 Local dates.** `today()` builds `YYYY-MM-DD` from local date parts; "yesterday" uses calendar arithmetic.
  The home screen shows 0 when a streak has lapsed, rather than the stale number.
- **B3 Session limit.** A 20-question session stops at exactly 20, and the bar is clamped at 100%.
  Misses still waiting go to the review queue and are listed in the summary.
- **B4 Input lock.** Input unlocks only after the new prompt is on screen, and the answer timer starts there too.
  Auto-submit locks at once, so a digit typed in the 30 ms gap cannot count.
- **B5.** "Fastest" counts correct answers only (shows "—" if none). The duplicate streak ternary is gone.
  The new setting "Show answer length" (default on) controls the grey placeholder digits.
- **B6.** `sw.js` installs the shell with `new Request(url, { cache: 'reload' })`.
- Also fixed: a timer left over from a wrong answer could fire after you tapped × and throw an error.
  It could also skip a question in the next session. Timers now check that their session is still current.

### iPhone XS polish
- Keys act on **touch-down** (`pointerdown`), like the iOS keyboard, so two overlapping thumbs both register.
  The click that follows a touch is swallowed, so one tap is one digit. A keyboard or VoiceOver click with no touch first still works.
- **Haptics on iPhone.** iOS has no `navigator.vibrate`. On iOS 18+, flipping a native `<input type="checkbox" switch>` plays the
  system tick, so a hidden one is flipped through its label:
  - one tick per key
  - two ticks for a correct answer
  - three ticks for a wrong one

  Android still uses `navigator.vibrate`. The setting is now called "Haptics".
- The settings gear is an inline SVG. The `&#9881;` character was drawn as a colour emoji on iOS, breaking the greyscale design.
- **Start** sits in a bottom dock above the home indicator, with a one-line caption (size · session · facts due).
- The + − × ÷ buttons fill the row evenly.
- No long-press callout or text selection on the practice screen; `:active` styles work on iOS.
- `format-detection: telephone=no` (iOS no longer turns long numbers into phone links), `apple-mobile-web-app-title`,
  `text-size-adjust`, and an icon link (no more `/favicon.ico` 404).
- Long prompts and answers shrink to fit the width (minimum 22 px), part of G10.
- The practice top bar shows the size or set name.

### Tables add-on (uses parts of Phase 0b, built to the plan's storage format)
- **Sizes** (home tiles), applied to the chosen operations. For ÷ the pair is quotient and divisor:
  - Facts ≤ 12
  - Teens ≤ 19
  - Squares 11²–99² (× only; the operation buttons dim)
  - Custom: the old min/max range. A version 1 user with a changed range lands on Custom automatically.
  - 2 · 1, 2 · 2, 3 · 1 and 3 · 3 digits
- **Spaced review across days** (PLAN §4.6), stored as `drill.srs = { key: [box, 'YYYY-MM-DD'] }`:
  - Boxes are `[0, 1, 3, 7, 21]` days.
  - Wrong → box 0, due today. Right → next box. Right in box 4 → retired (box 5). Over 5,000 entries, retired items are dropped first.
  - **Deviation from the plan:** a right answer slower than the fact's target time keeps its box, since the goal is fast recall. Targets follow PLAN §4.5, for example 2.5 s for facts and 20 s for 2-digit × 2-digit.
- **Weak facts first.** Starting a quick drill serves the most overdue matching fact first, then due facts fill about half the session.
  New questions skip facts already scheduled for a later day, so a big range like 2 · 2 digits is covered rather than repeated.
  About 5% are retired facts.
- **Inside a session,** a miss comes back 2, then 5 questions later (the `LEITNER` box is now advanced).
- **First run** seeds `drill.srs` from version 1 `drill.facts`: under 80% → due today; the rest → box 2, due in 3 days.
  It only adds a key. `drill.meta` is **not** written, so Phase 0b's migration still runs.
- **Progress** has a Review list (Due today / Learning / Learned). The home Progress row shows the facts due.
- Export now also includes `srs` (still `v: 1`). Import restores it, or seeds it from the imported facts. Reset clears it.
- **Seeded randomness:** mulberry32, `?seed=N`. `Math.random` is no longer used.
- **Test hooks:** `window.__drill` (version, today, addDays, state, current, qid, typed, ready, srsUpdate, hapticCount).

## Test results
`python3 -m http.server 8000` then `python3 tests/smoke.py http://localhost:8000/`. This needs `pip install playwright`;
the test finds Chromium in `/opt/pw-browsers` or uses `DRILL_CHROMIUM`.

**23 passed, 0 failed** (drill-v3). The run uses headless Chromium at 375 × 812 with touch on and timezone Asia/Ho_Chi_Minh.

| Check | Covers |
|---|---|
| enter-key | B1 |
| negative-touch | B1 |
| decimal-touch | B1 |
| local-date | B2 (06:30 local) |
| streak-midnight | B2 (23:30 → 00:30 is two days) |
| session-limit | B3 (18/20, bar ≤ 100%) |
| input-lock | B4 |
| fastest-correct-only | B5 |
| show-length | B5 |
| single-tap | touch-down without double entry |
| haptics | haptic counter, on and off |
| lefty | left-handed keypad mirrors the columns |
| shapes | all 8 sizes × 4 operations stay in range |
| seeded | `?seed=N` |
| srs-rules | `[0,1,3,7,21]` with a fixed clock, including slow answers and retiring |
| srs-seed-v1 | seeding from the v1 fixture; other data untouched; no `drill.meta` |
| srs-due-first | the most overdue fact comes first |
| srs-miss | a miss lands in box 0 |
| import-v1 | importing a v1 backup |
| negatives | 16 signed questions across all four operations: answers whole and correct, brackets on a negative second number, ± key on; digits without the sign auto-submit as wrong |
| sw | `sw.js` content |
| layout | 320 × 568 and 375 × 812, light and dark: no sideways scroll, Start visible, keys ≥ 44 px, prompt fits |
| screenshot | `tests/shots/iphone-xs.png` |

Every check also fails on any console error.

**Gesture review.** One reviewer agent read only the keypad and haptics code. It found two defects, both fixed and re-tested (still 22/22):
- A key held for more than 1 s typed twice. The click window now starts at finger-up; a 1.3 s hold types one digit.
- Enter on a keypad key reached with Tab submitted the answer instead of pressing that key.

It raised no objection to the haptics method.

## How to test on the iPhone
1. Upload the files to the branch GitHub Pages serves. Open Drill from the home screen, close it fully, and open it again.
   Do this twice: the new service worker takes over on the second launch.
2. Haptics need iOS 18 or later and Settings → Sounds & Haptics → System Haptics on. Tap keys: each should tick.
   A wrong answer should give a short triple buzz. If nothing happens on iOS 18, report it (see open issues).
3. Pick ×, the "2 · 2" tile, and 20 questions. Tap fast with two thumbs: every digit should land, and none twice.
4. Get one wrong on purpose. Tomorrow the home caption should say "1 due for review", and that fact should come first.

## Open issues
- **Haptics are unverified on a real iPhone.** The hidden-switch method is an undocumented WebKit behaviour (iOS 18+). It cannot be tested
  in headless Chromium. If iOS changes it, haptics go silent; nothing breaks.
- **`drill.facts` has no size cap** (version 1 never needed one). With 2 · 2 digits and all four operations it can reach about 20,000 keys
  (about 0.7 MB), which nears the plan's 1 MB budget. Cap or compact it in Phase 0b without losing the heatmap data.
- **Session chips:** in headless Chromium's fallback font, "20 questions / 60 seconds / Endless" wrap to two lines at 375 px.
  On the iPhone (SF Pro) they fit on one row, as in your screenshot.
- **Phase 0b must keep `drill.srs` when it migrates** (merge; never re-seed over it). Set items are not in spaced review yet.
- Not built yet (Phase 0b):
  - a 99 × 99 overview on Progress (the heatmap still shows 1–12)
  - digit grouping (G9)
  - question count and sprint length settings (G8)
  - Today, Skills and Learn cards; hints and "Show working"
  - the update notice
  - export format v2
- `PLAN.md` and `CLAUDE.md` are not in the repository; they were supplied in the chat.
