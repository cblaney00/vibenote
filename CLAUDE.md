# VibeNote

*Created by the `vibe` command. Keep the two sections below current as the app grows —
a future session starts by reading them.*

> **The rules for working here are in `../CLAUDE.md`** (one directory up, alongside the
> other apps). They are loaded automatically; if for any reason they are not in your
> context, read that file before doing anything else.

## What this app is

VibeNote is insideabush's idea pad for his other projects (R62D, Sub of Seas, the Glade, ...),
in its own floating desktop window. The sidebar lists every project in `~/projects` (any
folder with a `.vibe-project`, except VibeNote itself), with how many notes are waiting.
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
- **Send** only updates the project's to-do list: the waiting notes go on the bottom of it
  (made as `docs/todo.md` if it has none) and become *sent*. No Claude, no tokens.
- **Work** has the project's Claude start on its to-do list (sending any waiting notes
  first). It always shows a warning that this uses his Claude tokens, and nothing happens
  unless he presses "I agree, start work". The message (`sender.work_message`) lists what is
  open and asks Claude to work "in the most efficient way" (his words): plan the order, group
  items touching the same code, ask all look-and-feel questions at once up front, no redoing
  work, short messages. It goes into the project's open chat; if none is open, a new kitty
  terminal opens Claude on the project (his last chat, or a fresh one) with it as the first
  message.

Earlier picks: he chooses the project for each note himself (no guessing); the window floats freely.

**It must work without Claude** (his ask): writing and sorting notes never uses Claude; only
Work does, behind the token warning. He can open it from the app menu
(`~/.local/share/applications/vibenote.desktop` → `run.sh`), no Claude needed.

Look: **warm paper** — cream page, a slightly darker cream sidebar, dark brown ink,
Georgia (serif) text, a brick-red margin line down the page and faint ruled lines under
each note, like a paper notebook. These were his choices; ask him before changing them.

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
- `tests/` — tests for the notes and the to-do files.

Run: `./run.sh` (or `nix develop /home/insideabush/nixos-config#vibe-python --command python main.py`)
Test: `nix develop /home/insideabush/nixos-config#vibe-python --command python -m unittest discover -s tests`
Lint: `... --command ruff check .`

Screenshots: `xvfb-run`/`xdotool` are not on PATH here; borrow them with
`nix shell nixpkgs#xvfb-run nixpkgs#xdotool --command xvfb-run -a sh -c '<python> main.py & ...'`
and point `VIBENOTE_DATA`/`VIBENOTE_PROJECTS` at scratch copies. `screenshots/` is gitignored.
On his screen, run it as him with his session's DISPLAY/WAYLAND_DISPLAY/XDG_RUNTIME_DIR/
HYPRLAND_INSTANCE_SIGNATURE (copy them from one of his processes' `/proc/<pid>/environ`).
