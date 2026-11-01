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
             "- When all are done, run `vibenote --collect-usage` (it lets VibeNote learn "
             "how many tokens this took).",
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


# --- learning how many tokens Claude uses (his ask, 2026-11-01) ---------------------------
# Claude's chats record the tokens of every reply (/root/.claude/projects/*/*.jsonl; only
# root can read them, so `vibenote --collect-usage`, run as root, sums them up into USAGE,
# which VibeNote reads). Tokens are the ones Claude writes (its replies, thinking and code),
# the count Claude shows him. Counting what it re-reads every step as well gave millions per
# note, which he called "crazy high" (2026-11-01: his 3-item batch was ~50k, and it was 52.7k).

TRANSCRIPTS = Path(os.environ.get("VIBENOTE_TRANSCRIPTS", "/root/.claude/projects"))
USAGE = Path(os.environ.get("VIBENOTE_USAGE",
                            "/home/insideabush/.local/share/vibenote/usage.json"))
WORK_START = "Please work on these items from my to-do list"


def _weighted(u: dict) -> float:
    return u.get("output_tokens", 0)


def _user_text(msg: dict) -> str:
    content = msg.get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(c.get("text", "") for c in content
                       if isinstance(c, dict) and c.get("type") == "text")
    return ""


def collect_usage(transcripts: Path = TRANSCRIPTS) -> dict:
    """Sum up every chat: tokens per hour of the day, and what each Work batch cost."""
    from datetime import datetime, timedelta, timezone
    hours = {h: [0, 0.0] for h in range(24)}  # replies, tokens
    batches, stamps, seen = [], [], set()
    for f in sorted(transcripts.glob("*/*.jsonl")):
        batch = None
        try:
            lines = f.open(errors="replace")
        except OSError:
            continue
        with lines:
            for line in lines:
                if '"usage"' not in line and WORK_START not in line:
                    continue
                try:
                    d = json.loads(line)
                except ValueError:
                    continue
                msg = d.get("message") or {}
                if d.get("type") == "user":
                    text = _user_text(msg)
                    if text.startswith(WORK_START):
                        items = [m.split(". ", 1)[1] for m in text.split("\n")
                                 if m[:1].isdigit() and ". " in m]
                        batch = {"items": items, "tokens": 0.0, "started": d.get("timestamp"),
                                 "project": f.parent.name.split("-projects-")[-1]}
                        batches.append(batch)
                    continue
                u = msg.get("usage")
                key = (msg.get("id"), d.get("requestId"))
                if not u or key in seen:
                    continue
                seen.add(key)
                tokens = _weighted(u)
                try:
                    when = datetime.fromisoformat(d["timestamp"].replace("Z", "+00:00"))
                except (KeyError, ValueError):
                    continue
                local = when.astimezone()
                hours[local.hour][0] += 1
                hours[local.hour][1] += tokens
                stamps.append((when, tokens))
                if batch is not None:
                    batch["tokens"] += tokens
    # Busiest 5 hours ever, and the last 5 hours (Claude's limits run in 5-hour windows)
    stamps.sort()
    window, start, biggest = 0.0, 0, 0.0
    for when, tokens in stamps:
        window += tokens
        while stamps[start][0] < when - timedelta(hours=5):
            window -= stamps[start][1]
            start += 1
        biggest = max(biggest, window)
    now = datetime.now(timezone.utc)
    last5 = sum(t for w, t in stamps if w > now - timedelta(hours=5))
    return {"updated": now.isoformat(), "hours": hours,
            "batches": [b for b in batches if b["items"] and b["tokens"]],
            "last5h": round(last5), "max5h": round(biggest)}


def save_usage(usage: dict, path: Path = USAGE):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(usage, indent=1))
    tmp.replace(path)
    if os.geteuid() == 0:  # root collected it; it is his file
        st = path.parent.stat()
        os.chown(path, st.st_uid, st.st_gid)


def load_usage(path: Path = USAGE) -> dict | None:
    """The latest summary: collected here if this user can read the chats, else the file."""
    if os.access(TRANSCRIPTS, os.R_OK | os.X_OK):
        try:
            usage = collect_usage()
            save_usage(usage, path)
            return usage
        except OSError:
            pass
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError):
        return None


class TokenGuess:
    """Turns a note's size guess (store.size_score) into tokens, learned from what his
    Work batches cost, and adjusted for the hour of the day from all his chats."""

    PER_POINT = 6_000  # before any Work batch has been measured

    def __init__(self, usage: dict | None):
        from store import size_score
        self.usage = usage or {}
        def median(xs):
            xs = sorted(xs)
            return xs[len(xs) // 2] if xs else None

        # Tokens per point of size, from each Work batch; per project too, since some
        # projects cost more per change than others (VibeNote ~6.6k, R62D ~3k)
        rates = {}
        for b in self.usage.get("batches", []):
            rate = b["tokens"] / max(sum(size_score(t) for t in b["items"]), 1)
            rates.setdefault(b.get("project"), []).append(rate)
        everything = [r for rs in rates.values() for r in rs]
        self.per_point = median(everything) or self.PER_POINT
        self.per_project = {p: median(rs) for p, rs in rates.items() if p}
        self.learned = len(everything)
        hours = {int(h): v for h, v in self.usage.get("hours", {}).items()}
        replies = sum(v[0] for v in hours.values())
        self.average = sum(v[1] for v in hours.values()) / replies if replies else 0
        self.hours = hours

    def hour_factor(self, hour: int) -> float:
        """How much more (or less) his chats use per reply at this hour than on average,
        from at least 40 replies at that hour; kept between 0.75 and 1.35."""
        count, tokens = self.hours.get(hour, (0, 0))
        if count < 40 or not self.average:
            return 1.0
        return min(max(tokens / count / self.average, 0.75), 1.35)

    def tokens(self, size: float, hour: int, project: str | None = None) -> int:
        rate = self.per_project.get(project, self.per_point)
        return round(max(size, 0.5) * rate * self.hour_factor(hour))


def short_tokens(n: float) -> str:
    """59_400 -> "~59k", 1_250_000 -> "~1.3M"."""
    if n >= 1_000_000:
        return f"~{n / 1_000_000:.1f}M"
    if n >= 1000:
        return f"~{round(n / 1000)}k"
    return f"~{round(n)}"


def good_time(guess: TokenGuess, now=None) -> tuple[str, str]:
    """The sign (his ask: "if it is a good time to claude or not from a token perspective").
    Returns (level, why): level is "good", "ok" or "bad"."""
    from datetime import datetime, timezone
    from zoneinfo import ZoneInfo
    now = now or datetime.now().astimezone()
    usage = guess.usage
    # Claude's busiest hours are weekday mornings in California; Anthropic has made the
    # 5-hour limits run out faster then (March 2026), though later reports say not for
    # Claude Code. Said as "may".
    pacific = now.astimezone(ZoneInfo("America/Los_Angeles"))
    if pacific.weekday() < 5 and 5 <= pacific.hour < 11:
        return "bad", "Claude's busiest hours (weekday mornings in the US): limits may run out faster."
    try:
        fresh = (datetime.now(timezone.utc)
                 - datetime.fromisoformat(usage["updated"])).total_seconds() < 20 * 60
    except (KeyError, ValueError, TypeError):
        fresh = False
    if fresh and usage.get("max5h") and usage.get("last5h", 0) > 0.7 * usage["max5h"]:
        return "bad", "You've used a lot in the last 5 hours; your limit may be close."
    if guess.hour_factor(now.hour) > 1.15:
        return "ok", "Quiet for Claude, but your chats tend to use more tokens at this hour."
    return "good", "Quiet hours for Claude."
