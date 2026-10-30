"""His projects (every folder with a .vibe-project) and the to-do list file inside each."""

import os
import re
from dataclasses import dataclass
from pathlib import Path

PROJECTS_DIR = Path(os.environ.get("VIBENOTE_PROJECTS", "/home/insideabush/projects"))
SELF = "vibenote"


@dataclass
class Project:
    slug: str      # the folder name
    title: str     # the name shown in the sidebar
    path: Path
    kind: str      # app, game or re
    shared: str    # "owner/repo" for a game shared with lando, else ""

    def todo_file(self) -> Path | None:
        """The project's to-do list file, if it has one."""
        candidates = [self.path / "docs" / "todo.md"]
        candidates += sorted(self.path.glob("*todo*.md"))
        candidates += sorted((self.path / "docs").glob("*todo*.md"))
        return next((p for p in candidates if p.is_file()), None)

    def todo_items(self) -> list[str]:
        """What is waiting on its to-do list (unticked items under "To do")."""
        f = self.todo_file()
        if not f:
            return []
        try:
            lines = f.read_text().splitlines()
        except OSError:
            return []
        start, end = _todo_section(lines)
        items = []
        for line in lines[start:end] if start is not None else lines:
            m = re.match(r"\s*- \[ \]\s+(.*)", line)
            if m:
                items.append(m.group(1).strip())
        return items

    def add_to_todo(self, notes: list[str]) -> Path:
        """Put the notes on the bottom of its to-do list, making the file if there is none."""
        f = self.todo_file()
        if f is None:
            f = self.path / "docs" / "todo.md"
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_text(
                f"# {self.title} to do\n\n"
                "His ideas, in his words (sent from VibeNote). Work through them top to bottom:\n"
                "when one is finished, tick it and move it to **Done**.\n\n"
                "## To do\n\n## Done\n"
            )
        lines = f.read_text().splitlines()
        new = [f"- [ ] {n}" for n in notes]
        start, end = _todo_section(lines)
        if start is None:
            while lines and not lines[-1].strip():
                lines.pop()
            lines += [""] + new
        else:
            # Drop a "(nothing waiting ...)" placeholder line, if there is one
            body = [ln for ln in lines[start:end] if not re.match(r"\s*\(.*\)\s*$", ln)]
            while body and not body[-1].strip():
                body.pop()
            if not body or body[0].strip():
                body.insert(0, "")
            lines = lines[:start] + body + new + [""] + lines[end:]
        f.write_text("\n".join(lines) + "\n")
        return f


def _todo_section(lines):
    """(first line, end line) of the body under the "## To do" heading, or (None, None)."""
    for i, line in enumerate(lines):
        if re.match(r"#+\s*to[\s-]?do\b", line.strip(), re.I):
            end = next((j for j in range(i + 1, len(lines)) if lines[j].startswith("#")), len(lines))
            return i + 1, end
    return None, None


def _field(text, name):
    m = re.search(rf"^{name}=(.*)$", text, re.M)
    return m.group(1).strip() if m else ""


def find_projects(base: Path = PROJECTS_DIR) -> list[Project]:
    found = []
    for marker in sorted(base.glob("*/.vibe-project")):
        folder = marker.parent
        if folder.name == SELF:
            continue
        try:
            text = marker.read_text()
        except OSError:
            continue
        title = _field(text, "title") or folder.name
        title = re.sub(r"\s*\(.*\)\s*$", "", title)  # "sub-of-seas (the ... game)" -> "sub-of-seas"
        if title == folder.name and "-" in title:
            small = {"of", "the", "and", "a"}               # "sub-of-seas" -> "Sub of Seas"
            title = " ".join(w if w in small else w.capitalize() for w in title.split("-"))
        kind = _field(text, "kind") or "app"
        found.append(Project(folder.name, title, folder, kind, _field(text, "shared")))
    return found
