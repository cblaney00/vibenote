"""Saving and loading VibeNote's lists. No window code lives here."""

import json
import os
import uuid
from pathlib import Path


def data_file() -> Path:
    override = os.environ.get("VIBENOTE_DATA")
    if override:
        return Path(override)
    base = os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share"
    return Path(base) / "vibenote" / "lists.json"


def new_id() -> str:
    return uuid.uuid4().hex[:12]


class Store:
    """All lists, each with a name and tasks. Every change is saved straight away."""

    def __init__(self, path: Path | None = None):
        self.path = path or data_file()
        self.lists: list[dict] = []
        self.load()

    # --- disk -------------------------------------------------------------

    def load(self):
        try:
            self.lists = json.loads(self.path.read_text())["lists"]
        except (FileNotFoundError, KeyError, ValueError):
            self.lists = []
        if not self.lists:
            self.lists = [{"id": new_id(), "name": "My list", "tasks": []}]

    def save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps({"lists": self.lists}, indent=2))
        tmp.replace(self.path)

    # --- lists ------------------------------------------------------------

    def get_list(self, list_id: str) -> dict:
        return next(lst for lst in self.lists if lst["id"] == list_id)

    def add_list(self, name: str) -> dict:
        lst = {"id": new_id(), "name": name.strip() or "New list", "tasks": []}
        self.lists.append(lst)
        self.save()
        return lst

    def rename_list(self, list_id: str, name: str):
        if name.strip():
            self.get_list(list_id)["name"] = name.strip()
            self.save()

    def delete_list(self, list_id: str):
        self.lists = [lst for lst in self.lists if lst["id"] != list_id]
        if not self.lists:
            self.lists = [{"id": new_id(), "name": "My list", "tasks": []}]
        self.save()

    # --- tasks ------------------------------------------------------------

    def add_task(self, list_id: str, text: str) -> dict | None:
        if not text.strip():
            return None
        task = {"id": new_id(), "text": text.strip(), "done": False}
        self.get_list(list_id)["tasks"].append(task)
        self.save()
        return task

    def toggle_task(self, list_id: str, task_id: str):
        for task in self.get_list(list_id)["tasks"]:
            if task["id"] == task_id:
                task["done"] = not task["done"]
        self.save()

    def delete_task(self, list_id: str, task_id: str):
        lst = self.get_list(list_id)
        lst["tasks"] = [t for t in lst["tasks"] if t["id"] != task_id]
        self.save()

    def clear_done(self, list_id: str):
        lst = self.get_list(list_id)
        lst["tasks"] = [t for t in lst["tasks"] if not t["done"]]
        self.save()
