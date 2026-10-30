"""His projects (every folder with a .vibe-project) and the to-do list file inside each."""

import os
import re
import subprocess
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
        found = next((p for p in candidates if p.is_file()), None)
        if found:
            return found
        # Or a section headed "... Blaney's list" in one of its documents (Sub of Seas keeps
        # his ideas as "## M8 — Blaney's list" in docs/roadmap.md, among Lando's plans)
        for f in sorted(self.path.glob("*.md")) + sorted((self.path / "docs").glob("*.md")):
            try:
                if re.search(HIS_LIST, f.read_text(), re.I | re.M):
                    return f
            except OSError:
                continue
        return None

    def _versions(self) -> list[list[str]]:
        """The to-do file's lines as it is now, and, for a game shared with lando, also as it is
        on each of the repo's branches: its folder hops between branches, and an item must not
        look finished just because the branch on show is one that never had it."""
        f = self.todo_file()
        if not f:
            return []
        versions = []
        try:
            versions.append(f.read_text().splitlines())
        except OSError:
            pass
        if self.shared:
            rel = f.relative_to(self.path).as_posix()
            try:
                branches = subprocess.run(
                    ["git", "-C", str(self.path), "for-each-ref", "--format=%(refname)",
                     "refs/heads", "refs/remotes/origin"],
                    capture_output=True, text=True, timeout=5).stdout.split()
                for ref in branches:
                    if ref.endswith("/HEAD"):
                        continue
                    out = subprocess.run(["git", "-C", str(self.path), "show", f"{ref}:{rel}"],
                                         capture_output=True, text=True, timeout=5)
                    if out.returncode == 0:
                        versions.append(out.stdout.splitlines())
            except (OSError, subprocess.SubprocessError):
                pass
        return versions

    def _read(self):
        """(open items, finished items) across every version; None for open when there is no list."""
        versions = self._versions()
        if not versions:
            return None, []
        whole_file = "todo" in self.todo_file().name.lower()  # a list file with no headings
        open_items, done = [], []
        for lines in versions:
            start, end = _todo_section(lines)
            if start is None and not whole_file:
                continue  # e.g. an older branch of the roadmap, from before his list was in it
            part = lines[start:end] if start is not None else lines
            for ticked, text in _items(part):
                _add(done if ticked else open_items, text)
            d_start, d_end = _section(lines, r"done")
            if d_start is not None:
                for _, text in _items(lines[d_start:d_end]):
                    _add(done, text)
        open_items = [t for t in open_items if not any(_same(t, d) for d in done)]
        return open_items, done

    def read(self):
        """(open items, finished items) in one go: what VibeNote's history is matched against."""
        return self._read()

    def todo_items(self) -> list[str] | None:
        """What is waiting on its to-do list (unticked, under its list heading). None: no list."""
        return self._read()[0]

    def done_items(self) -> list[str]:
        """What its to-do list says is finished: ticked items, and everything under "Done"."""
        return self._read()[1]

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


HIS_LIST = r"^#+ .*\bblaney'?s list\b"


def _todo_section(lines):
    """(first line, end line) of his list: under a "... Blaney's list" heading if there is one,
    else under "## To do"; (None, None) when there is neither."""
    for i, line in enumerate(lines):
        if re.match(HIS_LIST, line.strip(), re.I):
            end = next((j for j in range(i + 1, len(lines)) if lines[j].startswith("#")), len(lines))
            return i + 1, end
    return _section(lines, r"to[\s-]?do")


def _section(lines, name):
    for i, line in enumerate(lines):
        if re.match(rf"#+\s*{name}\b", line.strip(), re.I):
            end = next((j for j in range(i + 1, len(lines)) if lines[j].startswith("#")), len(lines))
            return i + 1, end
    return None, None


def _items(lines):
    """(ticked, text) for each "- " item; indented lines after one carry it on."""
    items = []
    for line in lines:
        m = re.match(r"\s{0,3}[-*] (\[( |x|X)\] )?(.*)", line)
        if m:
            text = re.sub(r"^\d{4}-\d\d-\d\d:\s*", "", m.group(3).strip())  # "2026-10-30: ..."
            text = text.replace("**", "")
            items.append([bool(m.group(2) and m.group(2) != " "), text])
        elif items and line.startswith("    ") and line.strip():
            items[-1][1] += " " + line.strip()
    return [(ticked, text) for ticked, text in items if text]


def _same(a, b):
    return " ".join(a.split()).lower() == " ".join(b.split()).lower()


def _add(items, text):
    if not any(_same(text, t) for t in items):
        items.append(text)


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
