# Rebuilding VibeNote on the graphics card ("Silk")

His ask (2026-11-12), after the Tk silk look: "the perspective doesnt feel laggy [he meant:
it does feel laggy] and this doesnt quite feel like a graphics overhaul, we can make insane
changes to this app if we prioritize efficiency when it comes to frames. maybe i do want it
more lively and interactive, i want the app to feel textured and tangible".

His picks: **rebuild on the graphics card** (a big job, done in steps he tries as we go);
**silk you can touch** (woven texture, a sheen that follows the mouse, ripples where he
clicks), **notes with weight** (cards that lift with a soft shadow, drag and toss between
columns with a springy feel), **a living city** (lights streaming along the streets,
drifting fog, light reflected on a glossy floor, the odd flying light). Not picked: sounds.
Still dim for his eyes: emerald and copper, cream text, never white.

## How it is built

- **Qt Quick** (QML) through **PyQt6**, which the vibe-python dev shell has. It draws on the
  graphics card at the screen's frame rate. The Python side (`silk/bridge.py`) reuses
  `store.py`, `projects.py` and `sender.py` as they are; only the window is new.
- QML modules (QtQuick, Effects, Particles, Shapes, Quick3D) are in PyQt6's own closure but
  not on its search path; `silk/app.py` finds them from the Qt libraries it has loaded
  (`/proc/self/maps`) and adds them to the engine.
- **Shaders** (`silk/shaders/*.frag`) are compiled to `.qsb` with Qt's `qsb` (found in the
  Nix store; `silk/build_shaders.sh`) and the `.qsb` files are committed, so running needs no
  compiler. Change a `.frag` → run the script → commit both.
- Efficiency: every moving thing is a shader or a GPU-animated item; no per-frame Python.
  Time stops (animations pause) when the window is minimised or hidden.
- Run it: `./run-silk.sh`. The installed VibeNote stays the Tk one until the switch-over.

## Steps

1. **Foundation** (2026-11-12, done): window, silk shader (weave, folds, mouse sheen, click
   ripples), living-city horizon shader, sidebar of projects, notes as lifting cards: write,
   edit, delete, Send tick and Send, Later/Now, Finished, sections for sent / worked / Later
   / with Lando / done, usage bars. Re-reads the to-do lists every 10 s like the Tk app.
1b. **Mini player** (2026-11-12, done): `Mini.qml`, the "open small" setting, ◱/◳ switching.
   (In xvfb the shaders render on the CPU, so timers run late: give tests more time.)
2. **Views** (2026-11-12, done): tabs over the sky (`ViewTabs.qml`, `bridge.layout`, shared
   with Tk in notes.json). `Board.qml`/`BoardCard.qml`: pick a card up, it follows on a
   spring and can be tossed (release speed carries it on); `bridge.boardDrop`: Waiting → Sent
   sends, Worked on → Done finishes, open → Waiting is Later, Later → Waiting is Now, else it
   springs home. `Sky.qml`: perspective done in plain Qt Quick (scale/opacity by depth, wheel
   flies, mouse tilts), not Quick3D: simpler and as fast. `LineView.qml` = Timeline and
   Compact. Clicking a note in any of them → `win.gotoNote` (List, scrolled, lit up).
   Sidebar (`Sidebar.qml`): a ListModel, so dragging only moves rows; Pinned box always
   shown; ⚑/⚐ flag and right-click pin (`bridge.setOrder`, `togglePin`).
3a. (2026-11-12, done) Work + token warning (`TokenWarning.qml`, inside the window so it is
   always centred), Organize (sizes, groups, token totals), Tick all (`TickAllRow.qml`),
   section Send/Work words, Move menu (`PopMenu.qml`, right-click), New chat, snapshot line
   on hover, guessed/used on dates. `sender.usage_after` is shared with Tk.
3. (2026-11-12, done) The rest: Find (Ctrl+F), Summary (with "Copy the open ones"), Claude
   usage + tips (`InfoPage.qml`: lines from `bridge.info`; "Claude usage ›" / "Tips ›" under
   the sign; a refresh line is clicked to type a new time), notes copyable (read-only
   `TextEdit`s; a click without dragging still edits), the ✦/✧ motion switch
   (`settings["motion"]`, shared with Tk), Lando mode on by itself (`sender.LANDO`), one
   copy at a time (`sender.close_other_copies`, Tk and Silk both; Python processes only, so
   it never kills the shell or nix that started it). Not carried over: the snapshot details
   pop-up (the hover line shows the snapshot instead).
4. **Switch-over**. In this folder it is done: `main.py`, started the normal way, `execv`s
   `silk/app.py` whenever PyQt6 is importable and `silk/` is there (`--tk` forces the old
   window; the flag modes `--collect-usage`, `--live-usage`, `--bar` stay in main.py). So
   `run.sh` (dev shell) already opens Silk. The **installed** app (dock, menu) stays Tk until
   the config's `pkgs/vibenote` (a config change; he asks via `vibe` → "Change or fix
   something on your computer"): its Python gets the same `pyqt6` the vibe-python dev shell
   has (with Qt Quick, Quick 3D, Effects, Shapes), and `installPhase` also copies `silk/`
   (without `__pycache__`) and `assets/`. Nothing else in the config changes.

## Ripples calmed (2026-11-13)

His note: "causing a fair bit of lag, they also dont have to be quite as aggressive".
`silk.frag`: a ripple lives 2 s (was 3.2), its ring is narrower, it bends the cloth less
(displacement 2, height 0.7, glow 0.12), and pixels more than 55 px from the ring skip the
sums. Measured in software rendering with four ripples going at once: +40% drawing cost
before, +13% after. Tapping a note card or a sidebar row no longer ripples; the other
triggers are gentler (0.6–0.9).
