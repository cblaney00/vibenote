"""His projects (every folder with a .vibe-project) and the to-do list file inside each."""

import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

from store import HIS, same as _same

PROJECTS_DIR = Path(os.environ.get("VIBENOTE_PROJECTS", "/home/insideabush/projects" if HIS
                                   else Path.home() / "projects"))


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

    def _versions(self) -> list[tuple[str, list[str]]]:
        """(where, lines) of the to-do file as it is now ("" for the folder), and, for a game
        shared with lando, also as it is on each of the repo's branches: its folder hops
        between branches, and an item must not look finished just because the branch on show
        is one that never had it."""
        f = self.todo_file()
        if not f:
            return []
        versions = []
        try:
            versions.append(("", f.read_text().splitlines()))
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
                        versions.append((ref, out.stdout.splitlines()))
            except (OSError, subprocess.SubprocessError):
                pass
        return versions

    def _read(self):
        """(open items, finished items, up for review) across every version; None for open
        when there is no list, and None for review when that couldn't be told. Up for review (his ask, 2026-11-04): in a game shared with
        lando, finished on one of Blaney's branches but not yet on main, so waiting on lando's
        PR review; it turns plain finished once lando merges it."""
        versions = self._versions()
        if not versions:
            return None, [], []
        whole_file = "todo" in self.todo_file().name.lower()  # a list file with no headings
        refs = [ref for ref, _ in versions]
        main = next((r for r in ("refs/remotes/origin/main", "refs/heads/main") if r in refs),
                    None)
        open_items, done, main_done = [], [], []
        for ref, lines in versions:
            start, end = _todo_section(lines)
            if start is None and not whole_file:
                continue  # e.g. an older branch of the roadmap, from before his list was in it
            part = lines[start:end] if start is not None else lines
            finished = [text for ticked, text in _items(part) if ticked]
            for ticked, text in _items(part):
                if not ticked:
                    _add(open_items, text)
            d_start, d_end = _section(lines, r"done")
            if d_start is not None:
                finished += [text for _, text in _items(lines[d_start:d_end])]
            for text in finished:
                _add(done, text)
                if ref == main:
                    _add(main_done, text)
        open_items = [t for t in open_items if not any(_same(t, d) for d in done)]
        review = None if self.shared else []  # None: couldn't tell (no main branch read)
        if main:
            review = [d for d in done if not any(_same(d, m) for m in main_done)]
            done = [d for d in done if d not in review]
        return open_items, done, review

    def read(self):
        """(open items, finished items, up for review) in one go: what VibeNote's history is matched against."""
        return self._read()

    def todo_items(self) -> list[str] | None:
        """What is waiting on its to-do list (unticked, under its list heading). None: no list."""
        return self._read()[0]

    def done_items(self) -> list[str]:
        """What its to-do list says is finished: ticked items, and everything under "Done"."""
        return self._read()[1]

    def review_items(self) -> list[str]:
        """Finished on one of Blaney's branches, waiting for lando to merge it into main."""
        return self._read()[2]

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

    def _find_item(self, text: str):
        """(lines, first line, end line) of an open item on its to-do list, or None."""
        f = self.todo_file()
        if f is None:
            return None
        lines = f.read_text().splitlines()
        start, end = _todo_section(lines)
        if start is None:
            start, end = 0, len(lines)
        for i in range(start, end):
            m = re.match(r"\s{0,3}[-*] (\[ \] )?(.*)", lines[i])
            if not m:
                continue
            j = i + 1  # the indented lines that carry the item on
            while j < end and lines[j].startswith("    ") and lines[j].strip():
                j += 1
            whole = " ".join([m.group(2)] + [ln.strip() for ln in lines[i + 1:j]])
            whole = re.sub(r"^\d{4}-\d\d-\d\d:\s*", "", whole.strip()).replace("**", "")
            if _same(whole, text):
                return lines, i, j
        return None

    def remove_from_todo(self, text: str) -> bool:
        """Take an open item off its to-do list (into Later). Returns whether it was there."""
        found = self._find_item(text)
        if found is None:
            return False
        lines, i, j = found
        self.todo_file().write_text("\n".join(lines[:i] + lines[j:]) + "\n")
        return True

    def finish_in_todo(self, text: str) -> bool:
        """Tick an open item on its to-do list: he has checked it and it is done as far as he
        is going (his ask, 2026-11-04, "Finished"). Returns whether it was there."""
        found = self._find_item(text)
        if found is None:
            return False
        lines, i, _ = found
        lines[i] = re.sub(r"^(\s{0,3}[-*] )(\[ \] )?", r"\1[x] ", lines[i], count=1)
        self.todo_file().write_text("\n".join(lines) + "\n")
        return True


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


def _add(items, text):
    if not any(_same(text, t) for t in items):
        items.append(text)


def _field(text, name):
    m = re.search(rf"^{name}=(.*)$", text, re.M)
    return m.group(1).strip() if m else ""


def find_projects(base: Path = PROJECTS_DIR) -> list[Project]:
    found = []
    markers = sorted(base.glob("*/.vibe-project"))
    if not HIS and not markers:
        # Lando's projects are plain git folders, in ~/projects or his home (Lando mode)
        roots = [base] if base.is_dir() else [Path.home()]
        markers = sorted(m for r in roots for m in r.glob("*/.git"))
    for marker in markers:
        folder = marker.parent
        try:
            text = marker.read_text() if marker.is_file() else ""
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
