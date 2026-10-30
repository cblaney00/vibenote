# VibeNote

*Created by the `vibe` command. Keep the two sections below current as the app grows —
a future session starts by reading them.*

> **The rules for working here are in `../CLAUDE.md`** (one directory up, alongside the
> other apps). They are loaded automatically; if for any reason they are not in your
> context, read that file before doing anything else.

## What this app is

VibeNote is a to-do list app for insideabush, in its own desktop window. He can keep
several lists (shown down the left side), add tasks by typing and pressing Enter, tick
them off, and clear ticked ones away. Ticked tasks sink to the bottom with a line
through them. Everything saves by itself.

Look: **warm paper** — cream page, a slightly darker cream sidebar, dark brown ink,
Georgia (serif) text, a brick-red margin line down the page and faint ruled lines under
each task, like a paper notebook. These were his choices; ask him before changing them.

## How it is built

- Python 3 with tkinter (Python's built-in window toolkit) — the `vibe-python` dev
  shell has it, and it needs nothing extra.
- `main.py` — the window and everything you see.
- `store.py` — loading and saving lists; no window code. Data lives in
  `~/.local/share/vibenote/lists.json` (or the file named by `VIBENOTE_DATA`, used
  for testing).
- `tests/test_store.py` — tests for the saving logic.

Run: `nix develop /home/insideabush/nixos-config#vibe-python --command python main.py`
Test: `nix develop /home/insideabush/nixos-config#vibe-python --command python -m unittest discover -s tests`
Lint: `... --command ruff check .`

Screenshots: `xvfb-run`/`xdotool` are not on PATH here; borrow them with
`nix shell nixpkgs#xvfb-run nixpkgs#xdotool --command xvfb-run -a sh -c '<python> main.py & ...'`
and point `VIBENOTE_DATA` at a scratch file. `screenshots/` is gitignored.
