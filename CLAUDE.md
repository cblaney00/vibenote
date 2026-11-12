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
(Move / right-click) or delete (×) them. **Sidebar order is his** (his ask, 2026-11-04;
his pick: "your order sticks"). Since 2026-11-06 (his ask: "cramped ... easily drag AND pin
projects as well as order the pins"; his pick: a Pinned box on top) it has a **PINNED** box
and a **PROJECTS** box; each row has a grip (⠿) and a flag to click (⚑ pinned, ⚐ not;
right-click still pins). Drag a row anywhere (`_drag_start/_move/_end` over `self._items`,
box titles included: the row is re-packed as it passes each neighbour, saved on the drop with
`Store.set_order(order, pinned)`); dropping it in the other box pins/unpins it. A click
without moving picks it; the sidebar is not redrawn mid-drag. The list scrolls
(`side_canvas`) when it doesn't fit, so the sign and usage bars always show; long names end
in "…" (`_fit_name`).
`Store.order`/`pinned` in notes.json, `Store.sidebar_order`: pinned first, then his order;
projects never placed go at the bottom, longest lists first (the old order). It opens on the
first with notes waiting, else the top one.

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
  message. **In plan mode** (his ask, 2026-11-06): Claude plans and waits for his OK before
  changing anything — a new chat starts with `--permission-mode plan` (`open_chat.sh`'s
  `run`), an open one is sent `/plan` first (`sender.to_plan_mode`; safe if already in it).

**Fresh chats** (his ask, 2026-11-02: "make sure that the cache is cleared for each project
often but not all the time, i just dont want the referencing to take too many tokens"). Every
step Claude re-reads the whole chat; a fresh one is ~60k, his long ones had reached 500k–970k.
`collect_usage` keeps each chat's current size (`chats`: last reply's input + cache read +
cache write). `sender.work_plan` / `fresh_reason`: Work starts the chat fresh first when it is
over `LONG_CHAT` (200k), or over `IDLE_CHAT` (120k) and idle over an hour (Claude's cache has
expired, so it would all be read in again at full price); never while the chat is working.
In an open chat it types `/clear` first; else `open_chat.sh … fresh` starts a new chat
instead of resuming the last. The token warning says when and why.

**New chat** (his ask, 2026-11-10: "start a new chat in that project without the vibenote
script and organization"; his picks: a "New chat ›" small button beside "Summary ›", plan
mode). `_new_chat` → `sender.new_chat` → `open_new_chat(project, "", fresh=True)`: always a
new kitty with a fresh chat, even if one is open; no notes, no token warning. `open_chat.sh`
reads an empty message as this: it never resumes (`-c`) and the prompt ends "hasn't said
what he wants yet ... ask him". Hidden in Lando mode and on the usage/find/summary views.

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

**Live usage bars** (his ask, 2026-11-06: "a live usage bar from claude /usage"; his pick:
sidebar bottom). Two bars, "5 hours" and "This week", each with its % and reset time: the
numbers Claude's `/usage` shows, from `api.anthropic.com/api/oauth/usage` with the login in
`/root/.claude/.credentials.json`, so **only root can ask**. `vibenote --live-usage`
(`sender.save_live_usage`, at most once a minute) saves them to
`~/.local/share/vibenote/live.json`; the **Glade's** Claude hook (`glade/claude_state.py`,
`refresh_vibenote_usage`, on Stop/PostToolUse) runs it, and `--collect-usage` does too.
VibeNote re-reads the file every 30 s (`_show_live`); a limit past its reset shows 0%. Only
the logged-in account is known (named from accounts.json by email).

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
hours *cheaper*; he caught that, 2026-11-02 — don't bring it back.) Tags read "~29k", coloured by size (the word went, 2026-11-06); the Work button
shows the total for the ticked items, and each section and group heading its own sum
(his ask, 2026-11-01). The sign (sidebar bottom, `good_time`): *Not a great
time* on weekday 5–11am Pacific (Anthropic made 5-hour limits run out faster then in March
2026; later reports say not for Claude Code, so it says "may") (it says how much more estimates count); else *Good*. Time of day only: it used to turn
bad after he had used a lot himself, which read as a bad time (his catch, 2026-11-06); the
usage bars show that now. Don't bring it back.

**Guessed vs used** (his ask, 2026-11-09): Work keeps each note's guess (`expected`) and the
time (`work_at`, `Store.mark_worked`); `sender.actual_tokens` finds its Work batch (first in
that project after `work_at`, else the latest naming it) and splits the batch's tokens across
its items by size score. Shown after the date: on hover for sent/worked items, always in
Done — "1 Nov · guessed ~29k · used ~13k". Batches record `plan` (the Work message's
`permissionMode`); once there are `PLAN_ENOUGH` (3) plan-mode batches, `TokenGuess` learns only
from those (a project keeps its old rate until it has 2 of its own).

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

**Tips for lighter tokens** (his ask, 2026-11-04; his pick: at the bottom of the usage
page, plus "Tips ›" by "Claude usage ›" which opens it scrolled down). `sender.token_tips`:
learned ones where his chats say enough (batch of 3+ vs one item per-item cost; chats past
`LONG_CHAT` this week; his 5-hour limit hits and when; the busy-hours factor; costliest vs
cheapest project per Medium change), then general ones (Send is free, one thing per note,
Later, questions up front). **`save_if_better`**: a collection that found no chats never
overwrites a saved one that had some — a run that couldn't see `/root/.claude` (as him, or
sandboxed) wiped usage.json on 2026-11-04.

**Later box** (his ask, 2026-11-02: "pin it in a box for getting it done later so it doesnt
clutter up the rest of the jobs that can be staged and done immidiately"). His picks: above
Done, folded to one line ("▸ Later (3) · ~40k tokens", click to open; `later_open`, starts
folded each run); a "Later" word under the mouse (by Move, and on sent items) or right-click
puts a note in; "Now" brings it back as a waiting note ticked for Send; Later notes stay **off
the to-do list** (a sent one is taken off it: `Project.remove_from_todo`) and Send, Work, Tick
all and Summary's "open ones for Claude" skip them. Status `later` in the store; `sync` counts
an open item matching a Later note as known (a shared game's other branches may still list it).

**Worked on / up for review** (his ask, 2026-11-04: "separate between notes that i have
checked and completed ... from the notes that i havent quite finished", review ones "not
include themselves in the work all button"; his picks: its own section, and a "Finished"
word). The sent list splits into "Sent: on its to-do list" (not started) and "Worked on, not
finished" (`worked` set by Work). A "Finished" word under the mouse on a worked item ticks it
on the to-do file (`Project.finish_in_todo`). Status `review` = **Up for review by Lando**:
for a shared game, an item ticked on some branch but not on `origin/main` (else `main`) —
`Project.read()` returns `(open, done, review)`, review `None` if git couldn't tell (then
nothing moves). Shown as its own section above Done, faded, ✓ in green and "with Lando"; no
ticks, so Work and Tick all skip it; done once lando merges. Matching (`store.same`) ignores
the `*(...)*` notes Claude writes under an item, so a note no longer turns into a new item
when Claude adds one; `sync` merges old twins left by that.

**Copying notes** (his ask, 2026-11-06: "the notes should be copy/paste-able ... i just
want to be able to click and drag it"): drag across any note (waiting, sent, Later) to pick
text, Ctrl+C copies; a click without moving still edits a waiting note. Notes are labels, so
`_selectable` lays a plain-text copy over the note on the first move (`_sel_box`, same wrap)
and selects in that; Esc or clicking away clears it. The Done block uses Tk's own selecting.
Sidebar rows are thin since then (his pick: "thinner rows, same text", `pady=3`).

**Growing note boxes** (his ask, 2026-11-09: a long unsent note hid in a one-line box, so he
had to arrow along it): the "Write a note…" box and the edit box are `tk.Text`s that grow with
the wrapped text (`_growing`: up to 6 lines for the new-note box, then it scrolls; 20 for an
edit, so the whole note shows). Enter still adds/saves; pasted line breaks become spaces. The
edit box carries `editing = True`, which the 10 s to-do re-read checks.

**Lando mode** (his ask, 2026-11-09; details and the config change it needs:
`docs/lando-mode/README.md`). For Lando, who talks to Claude himself. On by itself for anyone
but insideabush/root (`store.HIS`, `sender.LANDO`); `vibenote --lando` previews it. Opens as a
**mini player** (`Mini`, his pick "bars + one tip": dot, two usage bars, one tip, Notes ›
Usage › Tips ›), which opens the full app with `lando=True`: no Work button, Work column or
Work tick-all; tips are for using Claude directly (`token_tips(direct=True)`). Lando's own
`~/.claude` and data dir; it refreshes them itself (`refresh_own_usage`). One account, its
week from Claude's reset time (`lando_account`). `vibenote --bar` = Waybar JSON for his
top bar; `--toggle` (its click) closes an open VibeNote instead of opening another. The
Waybar module and installing it on Lando's machines are a **config** change, not done yet.

**Views** (his ask, 2026-11-12: "more view types"; his picks: all four). Top right over the
sky: **List · Board · Sky · Timeline · Compact** (`LAYOUTS`, `_set_layout`; the lit one is
`SmallButton.light`). Remembered in notes.json (`Store.settings["layout"]`) and part of
`_page_key`. List is the old page. **Board** (`_draw_board`/`_card`): four columns of silk
cards, Waiting (+Later) · Sent · Worked on (+with Lando) · Done (30 each, then "more in
List"); a waiting card edits on click, others open in List; right-click = the move menu;
cards wrap to a quarter of the page (`_cols`, `_card_wrap`, in `_rewrap_all`). **Sky**
(`SkyView`, one canvas the height of the page): cards in perspective, waiting nearest, then
sent/worked, Later, done farthest (newer nearer; the nearest always start close), spread
wider the farther off; the wheel flies (`fly`), the mouse tilts it, hover shows the whole
note at the bottom, click opens it in List. Four font sizes by distance (`f_sky`).
**Timeline** and **Compact** are one `tk.Text` each (`_text_block`/`_finish_block`, shared
with Done): a diary by day, newest first; one cut-to-fit line per note under status
headings. Clicking a line (`_link`) opens it in List: `_goto_note` scrolls to its row
(`notes_frame._rows`) and lights it for a moment (`_flash`). The note box, Send and Work
work in every view; the ticks are set in List.

**The silk night city** (his ask, 2026-11-12; see Look). `Horizon` (top of the page): sky
bands, stars, two `Silk` ribbons, a glow, a 3-layer skyline (`far/mid/near` tags, drawn
2600 px wide so resizing never shows an edge) with copper/peach windows that twinkle, a floor
in perspective to the vanishing point, the title (`CanvasLabel`: answers `.configure(text=)`
like the old label), the counts row (`count_row`, bottom, on flat PAPER) and the view tabs.
`Thread` = the margin as a copper thread with a glint; `Brand` = the sidebar name on a
ribbon with the **motion switch** ✦/✧ (`toggle_motion`, `Store.settings["motion"]`).
**One ticker** (`_ambient` → `_frame`): 5 frames a second idle, 16 while the mouse moves
(parallax), 2 when VibeNote isn't the window in use; the ribbons only once a second (each
step makes the whole skyline redraw: that cost ~16% of a core); SkyView only touches cards
that moved a pixel or changed show/hide. Measured: motion costs under 1% of a core. Don't
redraw the ribbons every frame again. All shapes are plain Tk canvas: the installed app has
only tkinter (no Pillow), and only the five listed source files, so new code goes in main.py.

**Mini player for everyone** (his ask, 2026-11-12: "update the lando minimal version and also
add that setting to all vibenotes"; his picks: rebuild it in the Silk look, and the setting is
"open as the mini player"). `Mini(lando)` is anyone's now. **No tip in the mini** (his ask, 2026-11-12:
"there should be no tips shown in this version"): the dot, the bars, Notes ›, Usage ›.
**It must shrink** (his catch: "the window is still regular size"): Hyprland reuses the last
floating size of the class and puts a remembered one back a moment after mapping, so both
minis ask for their own size (Tk `Mini._float`, Silk `app.py` `place`) and keep checking for
~3 s; the Silk mini also re-asks when its height drifts (`drifted`, 10 times at most), using
`Mini.qml`'s `wantHeight` (Qt's own height follows the desktop, not the contents). **"Open small like this"** (in the mini) = `Store.settings
["start_mini"]` (`start_small`: unset → yes for Lando, no for him); `--mini`/`--full` override.
The ◱ by the brand (`Brand.small` → `go_mini`: cancels its timers, closes, `.next = "mini"`)
shrinks the whole app to the mini; the startup loop hands between the two until one is
simply closed. `--view usage|tips` opens the whole app on that page. Silk has the same:
`silk/qml/Mini.qml` (city strip, breathing dot, `LiveBars`, the toggle),
◱/◳ to switch (`bridge.open` → `app.py`'s `show`, which loads the new window before closing
the old and quits only when he closes one); its Usage › opens the Tk page for now.

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
over the note (his pick; since 2026-11-06 in a small box floating just under it, so nothing
moves); click it for `SnapshotDetails`. Older notes have none.

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
  of `main.py` (emerald silk since 2026-11-12, below).
- 2026-11-02: "clearer places where you are able to click and less cluttery small text". His
  picks: the little clickable things are **small outlined buttons** (`SmallButton`: Summary /
  Back, Claude usage, Tick all, Change) that light up under the mouse; small text is 12 pt
  and upright, not italic (section headings 11 pt); dates on sent items show only while the
  mouse is over them; the sidebar sign is one short line ("Busy hours: estimates +25% until
  2pm."). He kept the token numbers on each note and on the group headings.
- 2026-11-06: "lets just overhaul vibenote". His picks: the Pinned-box sidebar, usage bars at
  the sidebar bottom, a roomier note page (bigger gaps), **bigger text everywhere** (a step
  up: notes 15, sidebar 15, small 13), fewer small words (size tags are just "~29k"), and
  "make the app window bigger as well but if i make it smaller then it should still work and
  resize everything smoothly": opens 1120×780 (`WIDE`/`TALL`), smallest 760×520; the
  sidebar is ~27% of the width (220–310, `_fit_sidebar`, on the settled resize) and the page
  margins narrow when the window does.
- 2026-11-12: "Vibenote should have more view types and needs a graphic overhaul. it needs to
  feel made of an exotic fabric, something with almost magical properties. be creative with
  this, feel I'm going to bed in silk pajamas in a night city utopia, add light animations
  for a sense of space, add perpective as well". His picks: **emerald silk, copper and
  peach lights** (replaces the brown and terracotta; still dim, cream text, never white);
  the night city as a **horizon behind the page**; **slow and subtle motion with an off
  switch**; views Board, Sky, Timeline, Compact. Then: "update the desktop, file, and dock
  icons when youre done with the design" → `assets/icon.svg` is now a silk notepad over the
  night city (it is the menu, dock, file and Glade-squid icon); the loading notepad matches.
- 2026-11-12, later: "the perspective doesnt feel laggy [he meant: it does] and this doesnt
  quite feel like a graphics overhaul, we can make insane changes to this app if we
  prioritize efficiency when it comes to frames. maybe i do want it more lively and
  interactive, i want the app to feel textured and tangible". His picks: **rebuild on the
  graphics card**; silk you can touch, notes with weight, a living city (not sounds). This
  is the **Silk window** (`silk/`, `./run-silk.sh`), built in steps: plan, progress and how
  it works in **docs/silk-rebuild.md** (read it before working on silk/).
- 2026-11-12, later: "the dock still opens the old version of vibenote". His pick: finish
  Silk first, then switch. Silk now has everything the Tk window has (steps 2–3 in
  docs/silk-rebuild.md), and `main.py` opens Silk wherever PyQt6 is there; the dock opens
  Silk once the config package has PyQt6 and `silk/` (step 4).
Ask him before changing the look.

**Ticks** (his ask): each waiting note has a **Send** tick (terracotta, new notes start ticked)
and a **Work** tick (green, starts unticked); items already on the list have only a Work tick.
Send sends only Send-ticked notes; Work gives Claude only Work-ticked items (a Work-ticked
note not yet sent is added to the list first), then the Work tick comes off and the item
moves to "Worked on, not finished". Clicking a column title ticks or unticks the whole column.
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
- `silk/` — the new Silk window (Qt Quick on the graphics card, being built; see
  docs/silk-rebuild.md): `app.py`, `bridge.py` (uses store/projects/sender), `qml/`,
  `shaders/` (`.frag` + compiled `.qsb`, `build_shaders.sh`). `run-silk.sh` starts it.
  Testing: `VIBENOTE_SHOT=file.png,secs` saves a screenshot and quits, `VIBENOTE_OPEN=slug`
  opens a project; in xvfb, focus the window with `xdotool search --class vibenote` first.
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
**Switching and hover** (his ask, 2026-11-06: "a bit laggy when switching between projects
and also hovering over notes is a bit jumpy"): each project's page is **kept** once built
(`_pages`: frame, `_page_key` = its notes + Later fold + its token rate) and swapped into
the canvas when picked; `refresh()` (after a change) rebuilds the current one, others
rebuild when their key no longer matches. `_build_ahead` builds the other pages out of
sight after opening and after changes. Switching re-colours two sidebar rows
(`_mark_picked`) instead of rebuilding the sidebar, and `show()` re-packs only when the view
changes. Pages are built hidden and wrapped *before* they show: `_room` works out each
label's width from the layout (Tk can't measure hidden widgets), so notes no longer jump
as they re-wrap. Back to a project ~10 ms, first visit ~30–80 ms (Tk mapping its windows).
The snapshot line floats in a small box over the notes below (`_show_snap`), instead of
pushing them down.

**Quick start** (his ask, 2026-11-01): it took ~9 s to open. Causes, both fixed: each note
re-wrapped itself on its own `<Configure>` (a chain of re-layouts) — now all notes wrap in
one pass (`_rewrap_all`, after a page is drawn or the canvas resizes), and the note text is
packed *last* in its row so it never squeezes the ticks; and `self.bind("<Configure>")` on
the window fired for every child widget — now a bindtag only the window has. Opens in
~0.5 s. A pulsing pixel notepad (`Loading`, his pick: the icon, page dimmed) covers the
window while it builds, at least 0.5 s so it never flickers. Never bind `<Configure>` per
note or on the root window again.
