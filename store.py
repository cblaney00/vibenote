"""Saving and loading his notes, kept per project, with their whole history. No window code here.

Every note has a status:
  waiting  written in VibeNote, not sent yet
  sent     on the project's to-do list, not finished yet
  done     gone from the to-do list (Claude finished it), or found already finished on import
Nothing is ever forgotten unless he deletes a waiting note himself.
"""

import json
import os
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
                "added": today()}
        self.notes.setdefault(slug, []).append(note)
        self.save()
        return note

    def edit(self, slug: str, note_id: str, text: str):
        if not text.strip():
            return self.delete(slug, note_id)
        for note in self.all(slug):
            if note["id"] == note_id:
                note["text"] = " ".join(text.split())
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

    def mark_sent(self, slug: str, note_ids: list[str]):
        for note in self.all(slug):
            if note["id"] in note_ids:
                note["status"] = "sent"
                note["sent"] = today()
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
                notes.append({"id": new_id(), "text": text, "status": "done", "imported": True})
            self.imported.append(slug)
            changed = True

        # Something on the list VibeNote has not seen (added in a chat, or already there
        # on import): it counts as sent
        for text in open_items:
            if not any(n["status"] == "sent" and same(n["text"], text) for n in notes):
                note = {"id": new_id(), "text": text, "status": "sent", "imported": True}
                if not first:
                    note["sent"] = today()  # the day VibeNote first saw it there
                notes.append(note)
                changed = True

        # Sent, but no longer on the list: Claude finished it
        for n in notes:
            if n["status"] == "sent" and not any(same(n["text"], t) for t in open_items):
                n["status"] = "done"
                n["done"] = today()
                changed = True

        if changed:
            self.save()
        return changed
