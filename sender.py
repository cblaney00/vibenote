"""Getting a batch of notes to a project's Claude: typed into its open chat, or a new chat opened.

Finding the chat works like the Glade's Claude panel (glade/claude_panel.py): every Claude chat
writes ~/.local/state/glade/claude/<pid>.json saying which folder it works in, and the kitty
window it runs in is found by kitty's remote control (`kitty @ ls`).
"""

import glob
import json
import os
import subprocess
import time
from pathlib import Path

from projects import Project

HERE = Path(__file__).resolve().parent
STATE = Path.home() / ".local/state/glade/claude"
OUTBOX = Path.home() / ".local/state/vibenote"


def message_for(project: Project, notes: list[str], todo: Path) -> str:
    where = todo.relative_to(project.path)
    lines = [f"New notes from VibeNote for {project.title}, in my words. "
             f"They are also on the bottom of {where} now. Please work on them:", ""]
    lines += [f"{i}. {n}" for i, n in enumerate(notes, 1)]
    return "\n".join(lines)


# --- an open chat -----------------------------------------------------------------------

def _alive(pid: int) -> bool:
    return Path(f"/proc/{pid}").exists()


def open_chat_pid(project: Project) -> int | None:
    """The newest running Claude chat working in this project's folder."""
    best = None
    for f in STATE.glob("*.json"):
        try:
            st = json.loads(f.read_text())
        except (OSError, ValueError):
            continue
        pid = st.get("pid")
        cwd = os.path.realpath(st.get("cwd") or "")
        if pid and cwd == os.path.realpath(project.path) and _alive(pid):
            if best is None or st.get("started", 0) > best[1]:
                best = (pid, st.get("started", 0))
    return best[0] if best else None


def _ancestors(pid):
    chain = []
    for _ in range(12):
        if not pid or pid <= 1:
            break
        chain.append(pid)
        try:
            with open(f"/proc/{pid}/stat") as f:
                pid = int(f.read().rsplit(")", 1)[1].split()[1])
        except (OSError, ValueError, IndexError):
            break
    return chain


def kitty_cmd() -> str:
    user = os.environ.get("USER", "")
    for cand in (f"/etc/profiles/per-user/{user}/bin/kitty", "/run/current-system/sw/bin/kitty"):
        if os.path.exists(cand):
            return cand
    return "kitty"


def find_window(pid):
    """(socket, window id) of the kitty window Claude (process `pid`) runs in."""
    chain = set(_ancestors(pid))
    runtime = os.environ.get("XDG_RUNTIME_DIR", "/tmp")
    for sock in glob.glob(os.path.join(runtime, "kitty-*")) + glob.glob("/tmp/kitty-*"):
        try:
            out = subprocess.run([kitty_cmd(), "@", "--to", "unix:" + sock, "ls"],
                                 capture_output=True, timeout=5).stdout
            for osw in json.loads(out or b"[]"):
                for tab in osw.get("tabs", []):
                    for w in tab.get("windows", []):
                        pids = {w.get("pid")} | {p.get("pid") for p in w.get("foreground_processes", [])}
                        if pids & chain:
                            return sock, w["id"]
        except (OSError, subprocess.SubprocessError, ValueError):
            continue
    return None


def type_into_chat(pid: int, text: str) -> bool:
    found = find_window(pid)
    if not found:
        return False
    sock, wid = found
    base = [kitty_cmd(), "@", "--to", "unix:" + sock]
    try:
        # Bracketed paste, so the lines arrive as one message rather than one per line
        subprocess.run(base + ["send-text", "--match", f"id:{wid}", "--bracketed-paste", "enable",
                               "--stdin"], input=text.encode(), timeout=5, check=True,
                       capture_output=True)
        time.sleep(0.5)
        subprocess.run(base + ["send-key", "--match", f"id:{wid}", "enter"], timeout=5, check=True,
                       capture_output=True)
    except (OSError, subprocess.SubprocessError):
        return False
    _focus(_ancestors(pid))
    return True


def _focus(chain):
    for p in chain:
        try:
            if "kitty" in Path(f"/proc/{p}/comm").read_text():
                subprocess.run(["hyprctl", "dispatch", "focuswindow", f"pid:{p}"],
                               capture_output=True, timeout=5)
                return
        except (OSError, subprocess.SubprocessError):
            continue


# --- no chat open: start one --------------------------------------------------------------

def open_new_chat(project: Project, text: str):
    """A new terminal with Claude on the project (its last chat, else a fresh one), given `text`."""
    OUTBOX.mkdir(parents=True, exist_ok=True)
    msg = OUTBOX / f"to-{project.slug}-{int(time.time())}.txt"
    msg.write_text(text)
    subprocess.Popen(
        [kitty_cmd(), "--title", f"{project.title} · Claude", "--directory", str(project.path),
         "bash", str(HERE / "open_chat.sh"), str(project.path), project.title, str(msg)],
        start_new_session=True, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL)


def send(project: Project, notes: list[str]) -> str:
    """Add the notes to the project's to-do list and hand them to its Claude. Says what happened."""
    todo = project.add_to_todo(notes)
    text = message_for(project, notes, todo)
    pid = open_chat_pid(project)
    if pid and type_into_chat(pid, text):
        return f"Sent to {project.title}'s Claude"
    open_new_chat(project, text)
    return f"Opened a new Claude terminal for {project.title}"
