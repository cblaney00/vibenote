"""Saving and loading his notes, kept per project. No window code lives here."""

import json
import os
import uuid
from pathlib import Path


def data_file() -> Path:
    override = os.environ.get("VIBENOTE_DATA")
    if override:
        return Path(override)
    base = os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share"
    return Path(base) / "vibenote" / "notes.json"


def new_id() -> str:
    return uuid.uuid4().hex[:12]


class Store:
    """Notes waiting to be sent, per project folder name. Every change is saved straight away."""

    def __init__(self, path: Path | None = None):
        self.path = path or data_file()
        self.notes: dict[str, list[dict]] = {}
        self.load()

    def load(self):
        try:
            self.notes = json.loads(self.path.read_text())["notes"]
        except (FileNotFoundError, KeyError, ValueError, TypeError):
            self.notes = {}

    def save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps({"notes": self.notes}, indent=2))
        tmp.replace(self.path)

    def get(self, slug: str) -> list[dict]:
        return self.notes.get(slug, [])

    def add(self, slug: str, text: str) -> dict | None:
        if not text.strip():
            return None
        note = {"id": new_id(), "text": " ".join(text.split())}
        self.notes.setdefault(slug, []).append(note)
        self.save()
        return note

    def edit(self, slug: str, note_id: str, text: str):
        if not text.strip():
            return self.delete(slug, note_id)
        for note in self.get(slug):
            if note["id"] == note_id:
                note["text"] = " ".join(text.split())
        self.save()

    def delete(self, slug: str, note_id: str):
        self.notes[slug] = [n for n in self.get(slug) if n["id"] != note_id]
        self.save()

    def move(self, slug: str, note_id: str, to_slug: str):
        note = next((n for n in self.get(slug) if n["id"] == note_id), None)
        if note and to_slug != slug:
            self.notes[slug] = [n for n in self.get(slug) if n["id"] != note_id]
            self.notes.setdefault(to_slug, []).append(note)
            self.save()

    def clear(self, slug: str):
        self.notes[slug] = []
        self.save()
