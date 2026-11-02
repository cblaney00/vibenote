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
from store import condense

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
    # Said shorter for Claude (his ask); the list keeps his own words
    lines += [f"{i}. {condense(t)}" for i, t in enumerate(items, 1)]
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
CLAUDE_JSON = Path(os.environ.get("VIBENOTE_CLAUDE_JSON", "/root/.claude.json"))
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


def collect_usage(transcripts: Path = TRANSCRIPTS, previous: dict | None = None,
                  claude_json: Path = CLAUDE_JSON) -> dict:
    """Sum up every chat: tokens per hour of the day, what each Work batch cost, tokens per
    hour and project (for the Usage page), every limit Claude hit, and which account was
    logged in when (kept from the previous summary, as the chats don't record it)."""
    from datetime import datetime, timedelta, timezone
    hours = {h: [0, 0.0] for h in range(24)}  # replies, tokens
    batches, stamps, seen, hits, hit_keys = [], [], set(), [], set()
    buckets = {}  # "2026-11-02T15" (UTC hour) -> {project: tokens}
    for f in sorted(transcripts.glob("*/*.jsonl")):
        folder = f.parent.name
        project = folder.split("-projects-")[-1] if "-projects-" in folder else "computer"
        batch = None
        try:
            lines = f.open(errors="replace")
        except OSError:
            continue
        with lines:
            for line in lines:
                if ('"usage"' not in line and WORK_START not in line
                        and '"apiErrorParams"' not in line):
                    continue
                try:
                    d = json.loads(line)
                except ValueError:
                    continue
                msg = d.get("message") or {}
                limit = (d.get("apiErrorParams") or {}).get("rate_limit_info")
                if limit and (limit.get("rateLimitType"), limit.get("resetsAt")) not in hit_keys:
                    hit_keys.add((limit.get("rateLimitType"), limit.get("resetsAt")))
                    hits.append({"at": d.get("timestamp"), "type": limit.get("rateLimitType"),
                                 "resets": limit.get("resetsAt")})
                if d.get("type") == "user":
                    text = _user_text(msg)
                    if text.startswith(WORK_START):
                        items = [m.split(". ", 1)[1] for m in text.split("\n")
                                 if m[:1].isdigit() and ". " in m]
                        batch = {"items": items, "tokens": 0.0, "started": d.get("timestamp"),
                                 "project": project}
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
                hour = when.astimezone(timezone.utc).strftime("%Y-%m-%dT%H")
                per = buckets.setdefault(hour, {})
                per[project] = per.get(project, 0) + tokens
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
    # What a 5-hour limit holds: the tokens written in the 5 hours before each time he hit one
    five = []
    for hit in hits:
        if hit["type"] == "five_hour" and hit["at"]:
            at = datetime.fromisoformat(hit["at"].replace("Z", "+00:00"))
            five.append({"at": hit["at"], "tokens": round(
                sum(t for w, t in stamps if at - timedelta(hours=5) < w <= at))})
    keep = (now - timedelta(days=21)).strftime("%Y-%m-%dT%H")
    return {"updated": now.isoformat(), "hours": hours,
            "batches": [b for b in batches if b["items"] and b["tokens"]],
            "last5h": round(last5), "max5h": round(biggest),
            "buckets": {h: {p: round(t) for p, t in v.items()}
                        for h, v in sorted(buckets.items()) if h >= keep},
            "hits": sorted(hits, key=lambda h: h["at"] or ""), "five_hour_fills": five,
            "logins": _logins((previous or {}).get("logins", []), claude_json, now)}


def _logins(known: list, claude_json: Path, now) -> list:
    """[[time, email]]: who Claude was logged in as, from each time this ran and from
    Claude's own backups of its settings (named by the time they were made)."""
    from datetime import datetime, timezone
    found = {tuple(x) for x in known}
    for f in [claude_json, *claude_json.parent.glob(".claude/backups/.claude.json.backup.*")]:
        try:
            email = json.loads(f.read_text()).get("oauthAccount", {}).get("emailAddress")
        except (OSError, ValueError, AttributeError):
            continue
        if not email:
            continue
        stamp = f.name.rsplit(".", 1)[-1]
        when = (datetime.fromtimestamp(int(stamp) / 1000, timezone.utc) if stamp.isdigit()
                else now)
        found.add((when.isoformat(), email))
    return sorted([list(x) for x in found])


def save_usage(usage: dict, path: Path = USAGE):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(usage, indent=1))
    tmp.replace(path)
    if os.geteuid() == 0:  # root collected it; it is his file
        st = path.parent.stat()
        os.chown(path, st.st_uid, st.st_gid)


def load_saved_usage(path: Path = USAGE) -> dict | None:
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError):
        return None


def load_usage(path: Path = USAGE) -> dict | None:
    """The latest summary: collected here if this user can read the chats, else the file."""
    if os.access(TRANSCRIPTS, os.R_OK | os.X_OK):
        try:
            usage = collect_usage(previous=load_saved_usage(path))
            save_usage(usage, path)
            return usage
        except OSError:
            pass
    return load_saved_usage(path)


def is_busy(when) -> bool:
    """Claude's busiest hours: weekday mornings in California (8am-2pm for him). Anthropic
    made the 5-hour limits run out faster then (March 2026); later reports say not for Claude
    Code, so VibeNote learns how much it really is from his own limit hits (BUSY_GUESS until
    it can)."""
    from zoneinfo import ZoneInfo
    pacific = when.astimezone(ZoneInfo("America/Los_Angeles"))
    return pacific.weekday() < 5 and 5 <= pacific.hour < 11


class TokenGuess:
    """Turns a note's size guess (store.size_score) into tokens, learned from what his
    Work batches cost, and counted higher in Claude's busy hours, when the same work uses up
    more of his limit (his ask, 2026-11-02: the estimate was getting cheaper in the busy
    hours, as it used to follow his own reply lengths by hour instead)."""

    PER_POINT = 6_000  # before any Work batch has been measured
    BUSY_GUESS = 1.25  # busy hours count this much more until his limit hits show it

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
        # How much more a busy hour uses of his limit: a 5-hour limit filled up in busy hours
        # holds fewer tokens than one in quiet hours. Needs 2 of each to say.
        from datetime import datetime, timedelta
        busy, quiet = [], []
        for f in self.usage.get("five_hour_fills", []):
            if not isinstance(f, dict) or not f.get("tokens"):
                continue
            middle = (datetime.fromisoformat(f["at"].replace("Z", "+00:00"))
                      - timedelta(hours=2.5))
            (busy if is_busy(middle) else quiet).append(f["tokens"])
        self.busy_learned = len(busy) >= 2 and len(quiet) >= 2
        self.busy_factor = (min(max(median(quiet) / median(busy), 1.0), 2.0)
                            if self.busy_learned else self.BUSY_GUESS)

    def factor(self, when=None) -> float:
        from datetime import datetime
        return self.busy_factor if is_busy(when or datetime.now().astimezone()) else 1.0

    def tokens(self, size: float, when=None, project: str | None = None) -> int:
        """when: the time it would run (now if not given)."""
        rate = self.per_project.get(project, self.per_point)
        return round(max(size, 0.5) * rate * self.factor(when))


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
    now = now or datetime.now().astimezone()
    usage = guess.usage
    # Claude's busiest hours are weekday mornings in California; Anthropic has made the
    # 5-hour limits run out faster then (March 2026), though later reports say not for
    # Claude Code. Said as "may".
    if is_busy(now):
        more = round((guess.busy_factor - 1) * 100)
        return "bad", (f"Claude's busiest hours (weekday mornings in the US): your limit may "
                       f"run out faster, so estimates count {more}% more until 2pm.")
    try:
        fresh = (datetime.now(timezone.utc)
                 - datetime.fromisoformat(usage["updated"])).total_seconds() < 20 * 60
    except (KeyError, ValueError, TypeError):
        fresh = False
    if fresh and usage.get("max5h") and usage.get("last5h", 0) > 0.7 * usage["max5h"]:
        return "bad", "You've used a lot in the last 5 hours; your limit may be close."
    return "good", "Quiet hours for Claude."


# --- his two Claude accounts (his ask, 2026-11-02) -------------------------------------
# Each has a week that refreshes at a set time, 3.5 days apart. His words: account 1
# refreshes Monday 11am; account 2 "sometime nov 5" (Thursday) - 11pm is a guess (3.5 days
# after account 1) until he changes it. Which email is which lives only in ACCOUNTS on his
# computer, never in this code: the code is public on GitHub.

ACCOUNTS = Path(os.environ.get("VIBENOTE_ACCOUNTS",
                               "/home/insideabush/.local/share/vibenote/accounts.json"))
DEFAULT_ACCOUNTS = [
    {"name": "Account 1", "email": "", "weekday": 0, "hour": 11, "minute": 0, "guess": False},
    # "earlier": chats from before VibeNote first saw who was logged in (2 Nov 2026) count
    # as this account's
    {"name": "Account 2", "email": "", "weekday": 3, "hour": 23, "minute": 0, "guess": True,
     "earlier": True},
]
DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def load_accounts(path: Path = ACCOUNTS) -> list[dict]:
    try:
        accounts = json.loads(path.read_text())
        if isinstance(accounts, list) and accounts:
            return accounts
    except (OSError, ValueError):
        pass
    return [dict(a) for a in DEFAULT_ACCOUNTS]


def save_accounts(accounts: list[dict], path: Path = ACCOUNTS):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(accounts, indent=1))


def parse_refresh(text: str) -> dict | None:
    """"Thu 11pm", "thursday 23:00", "Mon 11am" -> {"weekday", "hour", "minute"}."""
    import re
    m = re.match(r"\s*([a-z]{3})[a-z]*\.?\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)?\s*$",
                 text.lower())
    if not m or m.group(1).capitalize() not in DAYS:
        return None
    hour, minute = int(m.group(2)), int(m.group(3) or 0)
    if m.group(4) == "pm" and hour < 12:
        hour += 12
    if m.group(4) == "am" and hour == 12:
        hour = 0
    if hour > 23 or minute > 59:
        return None
    return {"weekday": DAYS.index(m.group(1).capitalize()), "hour": hour, "minute": minute}


def refresh_text(acc: dict) -> str:
    h = acc["hour"] % 12 or 12
    mm = f":{acc['minute']:02d}" if acc["minute"] else ""
    return f"{DAYS[acc['weekday']]} {h}{mm}{'am' if acc['hour'] < 12 else 'pm'}"


def _last_refresh(acc: dict, now):
    from datetime import timedelta
    t = now.replace(hour=acc["hour"], minute=acc["minute"], second=0, microsecond=0)
    t -= timedelta(days=(now.weekday() - acc["weekday"]) % 7)
    if t > now:
        t -= timedelta(days=7)
    return t


def _account_at(logins: list, when_iso: str, earlier: str = "") -> str:
    """Who was logged in at that time: the last login seen before it."""
    email = earlier
    for at, who in logins:
        if at[:13] <= when_iso:
            email = who
        else:
            break
    return email


def _used(buckets: dict, logins: list, email: str, start, end, earlier: str = "") -> float:
    from datetime import timezone
    a = start.astimezone(timezone.utc).strftime("%Y-%m-%dT%H")
    b = end.astimezone(timezone.utc).strftime("%Y-%m-%dT%H")
    return sum(t for h, per in buckets.items()
               if a <= h < b and _account_at(logins, h, earlier) == email for t in per.values())


def usage_report(usage: dict | None, accounts: list[dict], now=None,
                 extra: int = 0) -> dict:
    """Everything the Usage page shows. extra: tokens about to be used (a Work request),
    added to the account logged in now."""
    from datetime import datetime, timedelta, timezone
    now = now or datetime.now().astimezone()
    usage = usage or {}
    buckets = usage.get("buckets", {})
    logins = usage.get("logins", [])
    earlier = next((a["email"] for a in accounts if a.get("earlier")), "")
    current = logins[-1][1] if logins else earlier
    fills = sorted(f["tokens"] if isinstance(f, dict) else f
                   for f in usage.get("five_hour_fills", []))
    five_hour = fills[len(fills) // 2] if fills else None
    report = {"current": current, "five_hour": five_hour, "accounts": []}
    for acc in accounts:
        start = _last_refresh(acc, now)
        end = start + timedelta(days=7)
        since = start.astimezone(timezone.utc).strftime("%Y-%m-%dT%H")
        used, projects, days = 0, {}, {}
        for hour, per in buckets.items():
            if hour < since or _account_at(logins, hour, earlier) != acc["email"]:
                continue
            day = datetime.fromisoformat(hour + ":00+00:00").astimezone(now.tzinfo)
            for p, t in per.items():
                used += t
                projects[p] = projects.get(p, 0) + t
                key = day.strftime("%a %-d %b")
                days[key] = days.get(key, 0) + t
        if acc["email"] == current:
            used += extra
        # The weekly limit: what this account had used when it hit a weekly limit. Until
        # then it is only known to be at least the most any account used in a week
        weekly, learned = None, False
        for hit in usage.get("hits", []):
            if hit["type"] == "seven_day" and _account_at(logins, hit["at"][:13], earlier) == acc["email"]:
                at = datetime.fromisoformat(hit["at"].replace("Z", "+00:00"))
                week_start = _last_refresh(acc, at.astimezone(now.tzinfo))
                weekly = _used(buckets, logins, acc["email"], week_start, at, earlier)
                learned = True
        days_in = max((now - start).total_seconds() / 86400, 0.25)
        days_left = (end - now).total_seconds() / 86400
        pace = used / days_in
        projected = used + pace * days_left
        report["accounts"].append({
            **acc, "start": start, "end": end, "used": used, "projects": projects,
            "days": days, "pace": pace, "projected": projected, "days_left": days_left,
            "weekly": weekly, "weekly_learned": learned,
            "logged_in": acc["email"] == current})
    # The biggest week seen without hitting a weekly limit: the limit is at least that
    at_least = 0
    for acc in accounts:
        week = _last_refresh(acc, now)
        for back in range(4):
            start = week - timedelta(days=7 * back)
            at_least = max(at_least, _used(buckets, logins, acc["email"], start,
                                           start + timedelta(days=7), earlier))
    report["at_least"] = at_least
    for a in report["accounts"]:
        limit = a["weekly"] if a["weekly_learned"] else at_least
        a["limit"] = limit
        a["left"] = (limit - a["used"]) if limit else None
        a["daily_budget"] = (max(limit - a["used"], 0) / max(a["days_left"], 0.1)
                             if limit else None)
        a["on_track"] = (a["projected"] <= limit) if limit else None
    # Use first the account whose week ends soonest, if it has room: what it doesn't use
    # is lost when it refreshes
    room = [a for a in report["accounts"] if a["left"] is None or a["left"] > 0]
    best = min(room or report["accounts"], key=lambda a: a["end"]) if report["accounts"] else None
    report["use_now"] = best["name"] if best else None
    return report


# --- a snapshot of the project when he writes a note (his ask, 2026-11-02) ---------------

def _git(path: Path, *args: str) -> str:
    try:
        out = subprocess.run(["git", "-C", str(path), *args], capture_output=True, text=True,
                             timeout=3)
        return out.stdout.strip() if out.returncode == 0 else ""
    except (OSError, subprocess.SubprocessError):
        return ""


def snapshot(project: Project) -> dict:
    """The time, where the project's code was (branch, last save point, files changed since)
    and what its Claude chat was doing, so the moment can be looked up later."""
    from datetime import datetime
    snap = {"at": datetime.now().astimezone().isoformat(timespec="minutes")}
    branch = _git(project.path, "branch", "--show-current")
    last = _git(project.path, "log", "-1", "--format=%h%x00%s%x00%cr")
    if last:
        commit, subject, ago = (last.split("\0") + ["", ""])[:3]
        changed = _git(project.path, "status", "--porcelain")
        snap.update({"branch": branch, "commit": commit, "subject": subject, "saved": ago,
                     "changed": len(changed.splitlines()) if changed else 0})
    for f in STATE.glob("*.json"):
        try:
            st = json.loads(f.read_text())
        except (OSError, ValueError):
            continue
        if Path(st.get("cwd", "")) == project.path and _alive(int(st.get("pid", 0))):
            progress = st.get("progress") or {}
            snap["claude"] = {"title": st.get("title") or "", "said": st.get("message") or "",
                              "now": progress.get("now") or "",
                              "working": bool(st.get("working"))}
            break
    return snap


def snapshot_line(snap: dict) -> str:
    """One faint line: "2 Nov 11:24 · main a1b2c3d "Fix shield walk" · 3 files changed ·
    Claude: Ranked mode"."""
    from datetime import datetime
    try:
        when = datetime.fromisoformat(snap["at"]).strftime("%-d %b %H:%M")
    except (KeyError, ValueError):
        when = ""
    parts = [when]
    if snap.get("commit"):
        parts.append(f"{snap.get('branch') or 'code'} {snap['commit']} \u201c{snap['subject']}\u201d")
        if snap.get("changed"):
            parts.append(f"{snap['changed']} file{'s' * (snap['changed'] != 1)} changed since")
    chat = snap.get("claude")
    if chat:
        parts.append("Claude: " + (chat["now"] or chat["title"] or "open"))
    else:
        parts.append("no Claude chat open")
    return " · ".join(p for p in parts if p)
