"""The Silk window's Python side: his notes, projects and to-do lists for the QML to show.

Everything here goes through store.py, projects.py and sender.py, the same as the Tk app,
so both windows can be used on the same notes.
"""

import threading
from datetime import date, datetime

from PyQt6.QtCore import QObject, QTimer, pyqtProperty, pyqtSignal, pyqtSlot

import projects
import sender
from store import Store, size_score


def nice_date(iso):
    try:
        return date.fromisoformat(str(iso)[:10]).strftime("%-d %b")
    except ValueError:
        return ""


class Bridge(QObject):
    projectsChanged = pyqtSignal()
    pageChanged = pyqtSignal()
    liveChanged = pyqtSignal()
    countsChanged = pyqtSignal()
    smallChanged = pyqtSignal()
    # which window to show next: "notes" (the whole app) or "mini"; "usage" opens the Tk
    # VibeNote's page until Silk has its own (docs/silk-rebuild.md, step 3)
    wantWindow = pyqtSignal(str)
    said = pyqtSignal(str)

    def __init__(self, lando=False):
        super().__init__()
        self.lando = lando
        self.store = Store()
        self.guess = sender.TokenGuess(sender.load_usage())
        self.projects = projects.find_projects()
        self._sync()
        self._sort()
        waiting = [p for p in self.projects if self.store.get(p.slug)]
        self.current = (waiting or self.projects or [None])[0]
        self._editing = False
        self._found = None
        # Claude ticks things off the lists while he works: keep up, every 10 s
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._reread)
        self._timer.start(10_000)
        self._live_timer = QTimer(self)
        self._live_timer.timeout.connect(self._live_tick)
        self._live_timer.start(30_000)
        self._live_tick()

    def _live_tick(self):
        # Lando's VibeNote fetches his own numbers (for next time's bars), like the Tk one
        threading.Thread(target=sender.refresh_own_usage, daemon=True).start()
        self.liveChanged.emit()

    # --- reading ------------------------------------------------------------------

    def _sort(self):
        order = self.store.sidebar_order([p.slug for p in self.projects])
        self.projects.sort(key=lambda p: order.index(p.slug))

    def _sync(self, results=None):
        if results is None:
            results = {p.slug: p.read() for p in self.projects}
        changed = False
        for p in self.projects:
            if p.slug in results:
                open_items, done, review = results[p.slug]
                changed |= self.store.sync(p.slug, open_items, done, review)
        return changed

    def _reread(self):
        """The lists (and a shared game's branches) are read on a side thread; the result is
        applied on the next tick, so the window never waits for git."""
        if self._found is not None:
            found, self._found = self._found, None
            if not self._editing and self._sync(found):
                self._changed()
            return
        box = {}

        def read():
            for p in list(self.projects):
                box[p.slug] = p.read()
            self._found = box

        threading.Thread(target=read, daemon=True).start()
        QTimer.singleShot(1500, self._reread_apply)

    def _reread_apply(self):
        if self._found is not None:
            found, self._found = self._found, None
            if not self._editing and self._sync(found):
                self._changed()

    def _changed(self):
        self.projectsChanged.emit()
        self.pageChanged.emit()
        self.countsChanged.emit()

    @pyqtProperty(int, notify=countsChanged)
    def sendCount(self):
        p = self.current
        return len([n for n in self.store.get(p.slug) if n["send"]]) if p else 0

    def _tokens(self, note):
        size = note["size"] if "size" in note else size_score(note["text"])
        slug = self.current.slug if self.current else None
        return self.guess.tokens(size, datetime.now().astimezone(), slug)

    def _card(self, note, kind):
        when = (note.get("done") or note.get("review") or note.get("worked")
                or note.get("sent") or note.get("added"))
        return {"id": note["id"], "text": note["text"], "kind": kind,
                "send": bool(note.get("send")), "work": bool(note.get("work")),
                "tokens": sender.short_tokens(self._tokens(note)) if "size" in note else "",
                "size": note.get("size", 0), "when": nice_date(when) if when else ""}

    @pyqtProperty("QVariantList", notify=projectsChanged)
    def projectList(self):
        return [{"slug": p.slug, "title": p.title, "waiting": len(self.store.get(p.slug)),
                 "pinned": p.slug in self.store.pinned,
                 "current": self.current is not None and p.slug == self.current.slug}
                for p in self.projects]

    @pyqtProperty("QVariantMap", notify=pageChanged)
    def page(self):
        p = self.current
        if p is None:
                return {"title": "No projects yet", "counts": "Start one with vibe", "sections": []}
        st = self.store
        waiting, sent = st.get(p.slug), st.get(p.slug, "sent")
        later, review = st.get(p.slug, "later"), st.get(p.slug, "review")
        done = st.get(p.slug, "done")
        done = sorted((n for n in done if n.get("done")), key=lambda n: n["done"],
                      reverse=True) + [n for n in done if not n.get("done")]
        fresh = [n for n in sent if not n.get("worked")]
        worked = [n for n in sent if n.get("worked")]
        sections = []
        for key, title, notes, kind in (
                ("waiting", "Waiting to send", waiting, "waiting"),
                ("sent", "Sent: on its to-do list", fresh, "sent"),
                ("worked", "Worked on, not finished", worked, "worked"),
                ("later", "Later", later, "later"),
                ("review", "Up for review by Lando", review, "review"),
                ("done", "Done", done, "done")):
            if notes:
                sections.append({"key": key, "title": title, "count": len(notes),
                                 "notes": [self._card(n, kind) for n in notes]})
        counts = (f"{len(waiting)} waiting · {len(sent)} sent · "
                  + (f"{len(review)} with Lando · " if review else "") + f"{len(done)} done"
                  + (f" · {len(later)} later" if later else ""))
        return {"title": p.title, "counts": counts, "sections": sections}

    @pyqtProperty("QVariantMap", notify=liveChanged)
    def live(self):
        """The two bars Claude's /usage shows."""
        live = sender.load_live_usage()
        if not live:
            return {"name": "", "bars": []}
        name = next((a["name"] for a in sender.load_accounts()
                     if a.get("email") and a["email"] == live.get("email")), "")
        bars = []
        for key, title, when in (("five_hour", "5 hours", "%-I:%M%p"),
                                 ("week", "This week", "%a %-I%p")):
            part = live.get(key)
            if not part:
                continue
            try:
                resets = datetime.fromisoformat(part["resets"]).astimezone().strftime(when)
                resets = "resets " + resets.replace("AM", "am").replace("PM", "pm")
            except (TypeError, ValueError, KeyError):
                resets = "starts fresh"
            bars.append({"title": title, "percent": max(0.0, min(100.0, part["percent"])),
                         "resets": resets})
        return {"name": name or "Claude", "bars": bars}

    @pyqtProperty("QVariantMap", notify=liveChanged)
    def sign(self):
        level, why = sender.good_time(self.guess)
        return {"level": level, "why": why}

    @pyqtProperty(bool, notify=smallChanged)
    def startSmall(self):
        """Open as the mini player (his ask, 2026-11-12, in every VibeNote): his setting,
        else yes for Lando and no for insideabush, the same as the Tk app."""
        return self.store.settings.get("start_mini", self.lando)

    @pyqtSlot()
    def toggleSmall(self):
        self.store.settings["start_mini"] = not self.startSmall
        self.store.save()
        self.smallChanged.emit()

    @pyqtSlot(str)
    def open(self, which):
        self.wantWindow.emit(which)

    # --- changing -------------------------------------------------------------------

    def _note(self, note_id):
        return next((n for n in self.store.all(self.current.slug) if n["id"] == note_id), None)

    @pyqtSlot(str)
    def pick(self, slug):
        self.current = next((p for p in self.projects if p.slug == slug), self.current)
        self._changed()

    @pyqtSlot(bool)
    def setEditing(self, on):
        self._editing = on

    @pyqtSlot(str)
    def addNote(self, text):
        p = self.current
        note = p and self.store.add(p.slug, " ".join(text.split()))
        if not note:
            return
        self._changed()

        def snap():
            found = sender.snapshot(p)
            if found:
                self.store.set_snapshot(p.slug, note["id"], found)

        threading.Thread(target=snap, daemon=True).start()

    @pyqtSlot(str, str)
    def editNote(self, note_id, text):
        if " ".join(text.split()):
            self.store.edit(self.current.slug, note_id, " ".join(text.split()))
        self._changed()

    @pyqtSlot(str)
    def deleteNote(self, note_id):
        self.store.delete(self.current.slug, note_id)
        self._changed()

    @pyqtSlot(str, str)
    def tick(self, note_id, which):
        note = self._note(note_id)
        if note:
            self.store.tick(self.current.slug, [note_id], which, not note[which])
            self.countsChanged.emit()  # the card already shows its tick

    @pyqtSlot()
    def send(self):
        p = self.current
        notes = [n for n in self.store.get(p.slug) if n["send"]] if p else []
        if not notes:
            return
        try:
            todo = sender.add_to_list(p, [n["text"] for n in notes])
        except OSError as err:
            self.said.emit(f"Couldn't add them to the list: {err.strerror or err}. "
                           "Your notes are still here.")
            return
        self.store.mark_sent(p.slug, [n["id"] for n in notes])
        self.said.emit(f"✓ {len(notes)} note{'s' * (len(notes) != 1)} added to {todo.name}")
        self._changed()

    @pyqtSlot(str)
    def later(self, note_id):
        note, p = self._note(note_id), self.current
        if note is None:
            return
        if note["status"] == "sent":
            try:
                p.remove_from_todo(note["text"])
            except OSError as err:
                self.said.emit(f"Couldn't take it off the list: {err.strerror or err}.")
                return
        self.store.later(p.slug, note_id)
        self.said.emit("Put aside in Later")
        self._changed()

    @pyqtSlot(str)
    def now(self, note_id):
        self.store.now(self.current.slug, note_id)
        self.said.emit("Back in Waiting to send")
        self._changed()

    @pyqtSlot(str)
    def finish(self, note_id):
        note, p = self._note(note_id), self.current
        if note is None:
            return
        try:
            found = p.finish_in_todo(note["text"])
        except OSError as err:
            self.said.emit(f"Couldn't tick it on the list: {err.strerror or err}.")
            return
        if not found:
            self.said.emit("Couldn't find it on the list (it may be on another branch).")
            return
        self._sync({p.slug: p.read()})
        self.said.emit("Ticked off as finished")
        self._changed()
