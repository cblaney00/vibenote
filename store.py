"""Saving and loading his notes, kept per project, with their whole history. No window code here.

Every note has a status:
  waiting  written in VibeNote, not sent yet
  sent     on the project's to-do list, not finished yet
  done     gone from the to-do list (Claude finished it), or found already finished on import
Nothing is ever forgotten unless he deletes a waiting note himself.

Two ticks per note (his ask): "send" (only ticked waiting notes are sent; new notes start
ticked) and "work" (only ticked ones are given to Claude by Work; start unticked).
"""

import json
import os
import re
import uuid
from datetime import date
from pathlib import Path


def data_file() -> Path:
    override = os.environ.get("VIBENOTE_DATA")
    if override:
        return Path(override)
    base = os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share"
    return Path(base) / "vibenote" / "notes.json"


def new_id() -> str:
    return uuid.uuid4().hex[:12]


def today() -> str:
    return date.today().isoformat()


def same(a: str, b: str) -> bool:
    return " ".join(a.split()).lower() == " ".join(b.split()).lower()


# --- how big a change is: a free rough guess, no Claude (his ask: "Organize") ---
# Words that usually mean a lot of new work for Claude (more reading and writing, so more
# tokens), and words that usually mean a quick tweak. Matched as whole words / phrases,
# each counted once. Tuned on his real notes (2026-10-30): long, detailed notes are not
# always big ones, so length only counts a little.
BIG_WORDS = [
    "new level", "new levels", "new game", "new mode", "new world", "new map", "new app",
    "new page", "new screen", "new feature", "new system", "new attacker", "new operator",
    "new character", "multiplayer", "online", "co-op", "rewrite", "redo", "rework",
    "redesign", "overhaul", "rebuild", "from scratch", "entire", "system", "save", "saving",
    "load game", "story", "quest", "quests", "boss", "bosses", "ai", "inventory", "shop",
    "crafting", "levels", "world", "map", "room", "cutscene", "dialogue", "physics",
    "procedural", "generate", "editor", "achievements", "account", "integrate", "connect",
    "package", "install", "tutorial", "tutorials", "minigame", "game where", "instruments",
    "song",
]
MEDIUM_WORDS = [
    "add", "create", "build", "feature", "mode", "menu", "screen", "page", "animation",
    "animations", "animate", "sound", "sounds", "music", "enemy", "enemies", "weapon",
    "button", "option", "setting", "settings", "fix", "bug", "broken", "crash", "crashes",
    "doesn't work", "doesnt work", "not working", "glitch", "issue", "problem", "score",
    "timer", "health", "list", "window", "panel", "sort", "search", "history", "effect",
    "particles", "camera", "cameras", "aiming", "sensitivity", "balance", "balanced",
    "walk", "walking", "move around",
]
SMALL_WORDS = [
    "typo", "spelling", "rename", "color", "colour", "colors", "colours", "darker",
    "lighter", "brighter", "dimmer", "bigger", "smaller", "larger", "font", "text", "word",
    "wording", "label", "title", "tweak", "slightly", "a bit", "a little", "faster",
    "slower", "louder", "quieter", "speed", "size", "move the", "swap", "change the",
    "remove the", "hide", "icon",
]


def _phrases(words):
    return re.compile(r"\b(" + "|".join(re.escape(w) for w in words) + r")\b")


_BIG, _MEDIUM, _SMALL = _phrases(BIG_WORDS), _phrases(MEDIUM_WORDS), _phrases(SMALL_WORDS)


def size_score(text: str) -> float:
    """A rough guess at how many tokens a change will take: higher is bigger."""
    t = " ".join(text.lower().split())
    score = 1.0
    score += 2.5 * len(set(_BIG.findall(t)))
    score += 1.0 * len(set(_MEDIUM.findall(t)))
    score -= 0.8 * len(set(_SMALL.findall(t)))
    score += len(t.split()) / 40  # a longer note often asks for a bit more
    asks = len(re.findall(r"\band\b|,|;|\balso\b|\bplus\b", t))  # several asks in one
    score += min(0.4 * asks, 1.5)
    return round(max(score, 0.0), 2)


def size_label(score: float) -> str:
    return "Small" if score < 2.2 else "Medium" if score < 5 else "Big"


class Store:
    """All notes, per project folder name. Every change is saved straight away."""

    def __init__(self, path: Path | None = None):
        self.path = path or data_file()
        self.notes: dict[str, list[dict]] = {}
        self.imported: list[str] = []  # projects whose old to-do lists have been brought in
        self.load()

    def load(self):
        try:
            data = json.loads(self.path.read_text())
            self.notes = data["notes"]
            self.imported = data.get("imported", [])
        except (FileNotFoundError, KeyError, ValueError, TypeError):
            self.notes, self.imported = {}, []
        for notes in self.notes.values():
            for n in notes:
                n.setdefault("status", "waiting")
                n.setdefault("send", True)
                n.setdefault("work", False)

    def save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps({"notes": self.notes, "imported": self.imported}, indent=2))
        tmp.replace(self.path)

    # --- reading ----------------------------------------------------------

    def all(self, slug: str) -> list[dict]:
        return self.notes.get(slug, [])

    def get(self, slug: str, status: str = "waiting") -> list[dict]:
        return [n for n in self.all(slug) if n["status"] == status]

    # --- his waiting notes ------------------------------------------------

    def add(self, slug: str, text: str) -> dict | None:
        if not text.strip():
            return None
        note = {"id": new_id(), "text": " ".join(text.split()), "status": "waiting",
                "added": today(), "send": True, "work": False}
        self.notes.setdefault(slug, []).append(note)
        self.save()
        return note

    def edit(self, slug: str, note_id: str, text: str):
        if not text.strip():
            return self.delete(slug, note_id)
        for note in self.all(slug):
            if note["id"] == note_id:
                note["text"] = " ".join(text.split())
                if "size" in note:
                    note["size"] = size_score(note["text"])
        self.save()

    def delete(self, slug: str, note_id: str):
        self.notes[slug] = [n for n in self.all(slug) if n["id"] != note_id]
        self.save()

    def move(self, slug: str, note_id: str, to_slug: str):
        note = next((n for n in self.all(slug) if n["id"] == note_id), None)
        if note and to_slug != slug:
            self.notes[slug] = [n for n in self.all(slug) if n["id"] != note_id]
            self.notes.setdefault(to_slug, []).append(note)
            self.save()

    def tick(self, slug: str, note_ids: list[str], which: str, on: bool):
        """Set the "send" or "work" tick on some notes."""
        for note in self.all(slug):
            if note["id"] in note_ids:
                note[which] = on
        self.save()

    def mark_worked(self, slug: str, note_ids: list[str]):
        """Work started on them: the work tick comes off and the day is kept."""
        for note in self.all(slug):
            if note["id"] in note_ids:
                note["work"] = False
                note["worked"] = today()
        self.save()

    def mark_sent(self, slug: str, note_ids: list[str]):
        for note in self.all(slug):
            if note["id"] in note_ids:
                note["status"] = "sent"
                note["sent"] = today()
        self.save()

    def organize(self, slug: str):
        """Guess each waiting and sent note's size and sort both lists smallest first.
        Done notes keep their place. Ties keep the order they were in."""
        notes = self.all(slug)
        for n in notes:
            if n["status"] != "done":
                n["size"] = size_score(n["text"])
        live = sorted((n for n in notes if n["status"] != "done"), key=lambda n: n["size"])
        self.notes[slug] = live + [n for n in notes if n["status"] == "done"]
        self.save()

    # --- keeping up with the project's to-do list -------------------------

    def sync(self, slug: str, open_items: list[str] | None, done_items: list[str]) -> bool:
        """Match the history to what the to-do list says now. Returns whether anything changed.

        open_items is None when the project has no to-do list to read; then nothing is
        marked done (a list that has gone missing, say on another branch, finishes nothing).
        """
        if open_items is None:
            return False
        notes = self.notes.setdefault(slug, [])
        changed = False

        first = slug not in self.imported
        if first:
            # First look at this project: bring in its whole list, finished items too
            for text in done_items:
                notes.append({"id": new_id(), "text": text, "status": "done", "imported": True,
                              "send": True, "work": False})
            self.imported.append(slug)
            changed = True

        # Something on the list VibeNote has not seen (added in a chat, or already there
        # on import): it counts as sent
        for text in open_items:
            if not any(n["status"] == "sent" and same(n["text"], text) for n in notes):
                note = {"id": new_id(), "text": text, "status": "sent", "imported": True,
                        "send": True, "work": False}
                if not first:
                    note["sent"] = today()  # the day VibeNote first saw it there
                notes.append(note)
                changed = True

        # Sent, but no longer on the list: Claude finished it
        for n in notes:
            if n["status"] == "sent" and not any(same(n["text"], t) for t in open_items):
                n["status"] = "done"
                n["work"] = False
                n["done"] = today()
                changed = True

        if changed:
            self.save()
        return changed
