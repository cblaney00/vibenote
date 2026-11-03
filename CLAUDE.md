# VibeNote

*Created by the `vibe` command. Keep the two sections below current as the app grows —
a future session starts by reading them.*

> **The rules for working here are in `../CLAUDE.md`** (one directory up, alongside the
> other apps). They are loaded automatically; if for any reason they are not in your
> context, read that file before doing anything else.

## What this app is

VibeNote is insideabush's idea pad for his other projects (R62D, Sub of Seas, the Glade, ...),
in its own floating desktop window. The sidebar lists every project in `~/projects` (any
folder with a `.vibe-project`, VibeNote included, so he can keep its own to-do list in it
— his ask, 2026-10-31), with how many notes are waiting.
He picks a project, types notes into it, can edit (click), move to another project
(Move / right-click) or delete (×) them. Projects with the longest lists (all notes ever:
waiting + sent + done) sit at the top of the sidebar (his ask), and it opens on the top one
(or the first with notes waiting).

**History** (his ask: "a history of all notes sent and not sent"): every note is kept with a
status — *waiting* (not sent), *sent* (on the project's to-do list), *done* (gone from the
list, so Claude finished it; dated). The first time VibeNote sees a project it imports that
project's whole to-do file, finished items included (`Store.sync`, `imported` in notes.json).
After that the to-do files are re-read every 10 s: an item VibeNote has not seen (added in a
chat) becomes *sent*, a sent one that is no longer listed becomes *done*. A project whose
to-do file is missing (e.g. on another branch) finishes nothing. Matching is by text, so if
Claude rewords an open item it shows as one done and one new sent.

Two buttons (his ask, 2026-10-30):
- **Send** only updates the project's to-do list: the Send-ticked waiting notes go on the bottom of it
  (made as `docs/todo.md` if it has none) and become *sent*. No Claude, no tokens.
- **Work** has the project's Claude start on the Work-ticked items. It always shows a warning that this uses his Claude tokens, and nothing happens
  unless he presses "I agree, start work". The message (`sender.work_message`) lists what is
  open and asks Claude to work "in the most efficient way" (his words): plan the order, group
  items touching the same code, ask all look-and-feel questions at once up front, no redoing
  work, short messages. It goes into the project's open chat; if none is open, a new kitty
  terminal opens Claude on the project (his last chat, or a fresh one) with it as the first
  message.

**Fresh chats** (his ask, 2026-11-02: "make sure that the cache is cleared for each project
often but not all the time, i just dont want the referencing to take too many tokens"). Every
step Claude re-reads the whole chat; a fresh one is ~60k, his long ones had reached 500k–970k.
`collect_usage` keeps each chat's current size (`chats`: last reply's input + cache read +
cache write). `sender.work_plan` / `fresh_reason`: Work starts the chat fresh first when it is
over `LONG_CHAT` (200k), or over `IDLE_CHAT` (120k) and idle over an hour (Claude's cache has
expired, so it would all be read in again at full price); never while the chat is working.
In an open chat it types `/clear` first; else `open_chat.sh … fresh` starts a new chat
instead of resuming the last. The token warning says when and why.

**Organize** (his ask, 2026-10-30: "figure out which changes will take the most and least
tokens"): a button left of Send. His picks: a free rough guess (no Claude), and sort + label.
It sorts the waiting and the sent notes smallest first and tags each Small / Medium / Big
(green / faded / terracotta). The guess (`store.size_score`) scores telling words (big: new
level, map, tutorial, system...; small: typo, darker, a bit...), each counted once, plus a
little for length and for several asks in one note; tuned on his real notes. The guess is
kept on the note (`size`); notes added later have no tag until he presses Organize again.
Organize also **groups** (his ask, 2026-11-01: "grouped together if claude is going to be
working with similar stuff"; his pick: small terracotta headings): `store.group_notes` puts
notes sharing a theme (`THEMES`: Sound, Tutorial, Weapons...) or a telling word (a
character's name, "planks") together, greedily, biggest share first; leftovers go under "On
their own", last. Groups run smallest (summed size) first, notes small to big inside. The
heading is kept on the note (`group`). Pressing Organize also re-learns the usage at once
(`_relearn(again=False)`), so the token guesses, sign and usage numbers are right for this
time of day and week (his ask, 2026-11-02).

**Token estimate and the "good time?" sign** (his asks, 2026-11-01: "a token estimator that
learns how many tokens it uses based on time of day", and "a sign ... if it is a good time to
claude or not from a token perspective"; his pick: on each tag + a total). In `sender.py`:
`collect_usage` reads every Claude chat (`/root/.claude/projects/*/*.jsonl`, root only) —
tokens Claude *writes* per reply (output only: the count Claude shows him; counting re-read
context too gave millions, which he called "crazy high", 2026-11-01), per hour of the day, and each
Work batch (from its "Please work on these items" message to the next one / chat end; these
run long, so the median is used). `vibenote --collect-usage` (as root) saves that to
`~/.local/share/vibenote/usage.json`; the Work message asks Claude to run it when a batch is
done, and VibeNote re-reads it every 5 min on a side thread. `TokenGuess`: tokens = size
score × learned tokens per point (median over that project's batches, else all) × the busy-hours
factor: during Claude's busy hours (`is_busy`: weekday 5–11am Pacific = 8am–2pm his time) the
same work uses up more of his limit, so estimates count more — learned from his 5-hour limit
hits (median quiet fill ÷ median busy fill, by each window's middle, ≥2 of each, 1.0–2.0),
`BUSY_GUESS` 1.25 until then. (It used to follow his own reply lengths by hour, which made busy
hours *cheaper*; he caught that, 2026-11-02 — don't bring it back.) Tags read "Big · ~29k"; the Work button
shows the total for the ticked items, and each section and group heading its own sum
(his ask, 2026-11-01). The sign (sidebar bottom, `good_time`): *Not a great
time* on weekday 5–11am Pacific (Anthropic made 5-hour limits run out faster then in March
2026; later reports say not for Claude Code, so it says "may") (it says how much more estimates count) or when the last 5 hours used
over 70% of his busiest 5 hours ever (only if the summary is <20 min old); else *Good*.

**Claude usage page** (his ask, 2026-11-02; his pick: click the sign → "Claude usage ›").
Two accounts, each with a week that refreshes at a set time — his words: **Account 1 refreshes
Monday 11am; Account 2 "sometime nov 5"** (Thu 11pm is a guess; he can click the refresh line
to change it). Which email is which is only in `~/.local/share/vibenote/accounts.json` on his
computer — **never put his emails in this repo: it is public on GitHub.** (His to-do note
said the reverse numbering; his later answer wins.) Chats don't say which account they used,
so `collect_usage` keeps `logins` (who `/root/.claude.json` says is logged in, each run and
from Claude's `backups/`); before the first one seen (2 Nov) everything counts as the account
marked `earlier` (Account 2). It also keeps tokens per UTC hour per project (`buckets`, 21
days) and every limit hit (`hits`, with Claude's own reset times). `usage_report`: per account
used since its refresh, by project and day, pace, projection to the refresh, the weekly limit
(exact once a `seven_day` limit is hit; until then "at least" the biggest week seen), a daily
budget, on/off track, and which to use now (the one whose week ends soonest, if it has room).
A 5-hour window = median of what was written in the 5 h before each 5-hour hit. The Work
warning shows the request's guess and what it does to the logged-in account (`_usage_after`).

**Find** (Ctrl+F, his ask): a box over the page; every note in every project (and its
snapshot) with all the words, lit up; click one to open its project; Esc goes back.

**Summary** ("Summary ›" next to the counts; his ask: "grab past notes about each project so
that the information can be condensed"): all the project's notes ever, grouped like
Organize, each said shorter, open ones first; "Copy the open ones for Claude" copies them.
**Said shorter for Claude** (his ask: "summarizes everything i said into a language that
claude can easily understand"): `store.condense` drops filler ("i think", "just", "really"),
shortens phrasings ("there should be" → "add"), fixes common slips ("dont", "sheild"); the
Work message uses it, the to-do list keeps his words. The saving is small (a few %), as most
tokens are Claude's work, not the message.

**Snapshots** (his ask: "when i take notes, make the app take a screenshot of what was
happening in the project"): each new note keeps `snap` (`sender.snapshot`, on a side thread):
the time, git branch, last commit and its message, files changed since, and what the
project's Claude chat was doing (Glade state file). Shown as a faint line while the mouse is
over the note (his pick); click it for `SnapshotDetails`. Older notes have none.

**Spelling check of the UI**: he asked for it, then said to disregard it (2026-11-02); not done.

Earlier picks: he chooses the project for each note himself (no guessing); the window floats freely.

**It must work without Claude** (his ask): writing and sorting notes never uses Claude; only
Work does, behind the token warning. He can open it from the app menu
(`~/.local/share/applications/vibenote.desktop` → `run.sh`), no Claude needed.

Look (his calls, in order):
- 2026-10-30: "warm paper" — cream page, Georgia serif text, a notebook margin line and faint
  ruled lines under each note.
- 2026-10-30: "i need this theme darker, i like warm colors but it cant hurt my eyes, im
  light sensitive." Now **dark warm**: deep brown page and sidebar, soft cream text (never
  white), muted terracotta for headings / Send / the main button, a dim margin line, Georgia.
  Keep everything low-glare; no bright or white areas. Colours are the constants at the top
  of `main.py`.
- 2026-11-02: "clearer places where you are able to click and less cluttery small text". His
  picks: the little clickable things are **small outlined buttons** (`SmallButton`: Summary /
  Back, Claude usage, Tick all, Change) that light up under the mouse; small text is 12 pt
  and upright, not italic (section headings 11 pt); dates on sent items show only while the
  mouse is over them; the sidebar sign is one short line ("Busy hours: estimates +25% until
  2pm."). He kept the token numbers on each note and on the group headings.
Ask him before changing the look.

**Ticks** (his ask): each waiting note has a **Send** tick (terracotta, new notes start ticked)
and a **Work** tick (green, starts unticked); items already on the list have only a Work tick.
Send sends only Send-ticked notes; Work gives Claude only Work-ticked items (a Work-ticked
note not yet sent is added to the list first), then the Work tick comes off and the item
shows "Claude on it · date". Clicking a column title ticks or unticks the whole column.
A **"Tick all:"** row above the lists (his ask, 2026-11-02) ticks every waiting note for Send,
everything open for Work, or unticks it all (`_tick_all_row`).

**Pop-ups open in the middle of VibeNote** (his ask, 2026-11-02: the token warning came up in
the screen's corner): `centre_on` asks Hyprland (`hyprctl clients`/`movewindowpixel` by the
pop-up's address) to move it there, checking again until it stays put, since Hyprland places
new windows itself just after they appear. If it still doesn't stay, `centre_on` writes what the desktop
said to `~/.local/state/vibenote/centre.log`. **One VibeNote at a time** (`close_older_copies`):
opening it closes any other copy he has running — an older copy left open (minimized) after an
update kept the old code and put the warning in the corner again.
Pop-ups are made with `class_=POPUP_CLASS` ("Vibenote"): a bare Tk pop-up has window class
"Toplevel", and his desktop showed it as another app (Your Only Move Is HUSTLE, 2026-11-02).
Any new pop-up must do the same.

## How it is built

- Python 3 with tkinter (Python's built-in window toolkit) — the `vibe-python` dev
  shell has it, and it needs nothing extra.
- `main.py` — the window and everything you see. On Hyprland it asks to float
  (`hyprctl dispatch setfloating pid:...`), since his desktop tiles windows by default.
- `store.py` — his waiting notes, per project folder name, in
  `~/.local/share/vibenote/notes.json` (or the file in `VIBENOTE_DATA`, for testing).
- `projects.py` — finds the projects (`VIBENOTE_PROJECTS` overrides the folder, for
  testing) and reads/adds to each one's to-do file: `docs/todo.md`, else a `*todo*.md`
  (R62D's is `r6-todo.md`), else any doc with a heading containing "Blaney's list" — Sub of
  Seas keeps his ideas as "## M8 — Blaney's list" in `docs/roadmap.md`, among Lando's
  milestones, which must never be read as his. New items go at the end of that section
  (else "## To do"). For a shared game the list is read from the working tree *and* every
  local/origin branch (its folder hops branches): open = open somewhere and ticked nowhere;
  branches whose copy lacks his heading are skipped. `**bold**` is stripped from items.
- `sender.py` — finds a project's open Claude chat the way the Glade's Claude panel does
  (`~/.local/state/glade/claude/<pid>.json` says each chat's folder; `kitty @ ls` finds its
  window) and types the message in with bracketed paste, then Enter.
- `open_chat.sh` — run inside a new kitty when no chat is open; starts Claude exactly the
  way `vibe` does, reading the launchers, hooks and session rules out of the installed
  `vibe` script so it follows rebuilds. It asks for his sudo password in that terminal.
- `run.sh` — starts the app through the dev shell (what the menu entry runs).
- `tests/` — tests for the notes, the to-do files, tokens and usage.

Run: `./run.sh` (or `nix develop /home/insideabush/nixos-config#vibe-python --command python main.py`)
Test: `nix develop /home/insideabush/nixos-config#vibe-python --command python -m unittest discover -s tests`
Lint: `... --command ruff check .`

Screenshots: `xvfb-run`/`xdotool` are not on PATH here; borrow them with
`nix shell nixpkgs#xvfb-run nixpkgs#xdotool --command xvfb-run -a sh -c '<python> main.py & ...'`
and point `VIBENOTE_DATA`/`VIBENOTE_PROJECTS` at scratch copies. `screenshots/` is gitignored.
On his screen, run it as him with his session's DISPLAY/WAYLAND_DISPLAY/XDG_RUNTIME_DIR/
HYPRLAND_INSTANCE_SIGNATURE (copy them from one of his processes' `/proc/<pid>/environ`).

GitHub: **github.com/cblaney00/vibenote** (public, his pick, 2026-10-30). Push `main` after
every commit — that push is the backup.

**Installed app** (2026-10-30, from a config session, branch `blaney/package-vibenote`):
`pkgs/vibenote` + `modules/nixos/programs/vibenote.nix` give a `vibenote` command and the
"VibeNote" menu entry; it is in `localApps`, so it is built from **this folder**. To get a
change into it: commit, push, then `cd /home/insideabush/nixos-config && rebuild`, and tell
him to close VibeNote and open it again. The package copies `main.py projects.py sender.py
store.py open_chat.sh` — a new source file must be added to its `installPhase` (a config
change: hand it to him for `vibe` → "Change or fix something on your computer"). The old
hand-made `~/.local/share/applications/vibenote.desktop` is gone; `run.sh` remains for running
from here. Asked for next: pin it in the Glade dock (dock.nix favourites; config) and an
object in the Glade scene (Glade project).

**Keep it smooth** (his ask: "the app generally is choppy when adjusted, just smooth everything
out"). Rebuilding R62D's page used to take ~300 ms. Now: the Done list is one `tk.Text` block
(`_draw_done`), not widgets per item; a tick changes only its box (`tick`); a resize repaints
by hiding/showing the page (`_redraw`; this also fixes the undrawn patches XWayland left
after a resize) instead of rebuilding it; the 10 s to-do re-read runs on a side thread
(`_reread_todo`); the mouse wheel glides (`_scroll`). Rebuild ~50 ms, resize steps ~25 ms.
Don't bring back per-item widgets for long lists or full rebuilds on resize/ticks.

**Quick start** (his ask, 2026-11-01): it took ~9 s to open. Causes, both fixed: each note
re-wrapped itself on its own `<Configure>` (a chain of re-layouts) — now all notes wrap in
one pass (`_rewrap_all`, after a page is drawn or the canvas resizes), and the note text is
packed *last* in its row so it never squeezes the ticks; and `self.bind("<Configure>")` on
the window fired for every child widget — now a bindtag only the window has. Opens in
~0.5 s. A pulsing pixel notepad (`Loading`, his pick: the icon, page dimmed) covers the
window while it builds, at least 0.5 s so it never flickers. Never bind `<Configure>` per
note or on the root window again.
