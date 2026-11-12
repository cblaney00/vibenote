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
2. Views: Board with drag-and-toss cards (springs), Sky in real 3D (Quick3D), Timeline,
   Compact. Sidebar drag to order / pin.
3. Everything else from the Tk app: Work + token warning, Organize (sizes, groups, token
   tags), New chat, Move menu, snapshots on hover, Find, Summary, usage page and tips, copy
   text, Lando mode and its mini player, one copy at a time, pop-ups in the middle.
4. **Switch-over** (a config change, for Lando to approve): the package's Python gets
   `pyqt6` and copies `silk/`, and `vibenote` starts the Silk window. He asks via `vibe` →
   "Change or fix something on your computer". Until then the menu VibeNote is the Tk one.
