"""Send (notes onto a project's to-do list) and Work (its Claude starts on that list: its open
chat, or a new chat opened).

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


def work_message(project: Project, todo: Path, items: list[str]) -> str:
    """What Work types into the chat: the items he ticked, and how to get through them
    efficiently (his ask)."""
    where = todo.relative_to(project.path)
    lines = [f"Please work on these items from my to-do list for {project.title} ({where}). "
             "Only these ones; leave the rest of the list for later. "
             "Do it in the most efficient way:",
             "- First read them all and plan the order yourself. Group items that touch "
             "the same part of the code so each part is opened, changed and tested once; do "
             "small items in the same pass as related bigger ones.",
             "- If any items need me to decide how something looks or feels, ask me about all "
             "of them together at the start, then carry on without stopping for each one.",
             "- Don't redo work or re-read things you already know; keep your messages to me short.",
             "- Tick each item off as it's finished, the way the list's own rules say.",
             "", "The items:"]
    lines += [f"{i}. {t}" for i, t in enumerate(items, 1)]
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


def add_to_list(project: Project, notes: list[str]) -> Path:
    """Send: the notes go on the bottom of the project's to-do list. No Claude, no tokens."""
    return project.add_to_todo(notes)


def start_work(project: Project, items: list[str]) -> str:
    """Work (uses his tokens; he has agreed by now): its Claude starts on these items, in the
    open chat if there is one, else a new one. Says what happened."""
    text = work_message(project, project.todo_file(), items)
    pid = open_chat_pid(project)
    if pid and type_into_chat(pid, text):
        return f"{project.title}'s Claude is on it"
    open_new_chat(project, text)
    return f"Opened a new Claude terminal for {project.title}"
