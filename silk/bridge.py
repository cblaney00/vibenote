"""The Silk window's Python side: his notes, projects and to-do lists for the QML to show.

Everything here goes through store.py, projects.py and sender.py, the same as the Tk app,
so both windows can be used on the same notes.
"""

import html
import threading
from datetime import date, datetime

from PyQt6.QtCore import QObject, QTimer, pyqtProperty, pyqtSignal, pyqtSlot

import projects
import sender
from store import Store, condense, group_notes, size_score, tokens_in


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
    busyChanged = pyqtSignal()
    layoutChanged = pyqtSignal()
    viewChanged = pyqtSignal()
    _workEnded = pyqtSignal(str)  # from the side thread that hands the items to Claude
    _learned = pyqtSignal(object, bool)  # usage re-read on a side thread; True: say so

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
        self._busy = False  # handing a Work batch to Claude
        self._view = ""  # "" (the notes), "usage", "find" or "summary"
        self._query = ""
        self._workEnded.connect(self._work_ended)
        self._learned.connect(self._apply_learned)
        # learn again from Claude's chats every 5 minutes, like the Tk app
        self._learn_timer = QTimer(self)
        self._learn_timer.timeout.connect(lambda: self._relearn(False))
        self._learn_timer.start(5 * 60_000)
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

    def _guessed_used(self, note):
        """" · guessed ~29k · used ~13k" for a note Claude worked on (his ask, 2026-11-09)."""
        parts = []
        if note.get("expected"):
            parts.append(f"guessed {sender.short_tokens(note['expected'])}")
        if note.get("worked") or note.get("work_at") or note["status"] in ("done", "review"):
            used = sender.actual_tokens(note, self.current.slug, self.guess.usage)
            if used:
                parts.append(f"used {sender.short_tokens(used)}")
        return "".join(" · " + p for p in parts)

    def _card(self, note, kind):
        when = (note.get("done") or note.get("review") or note.get("worked")
                or note.get("sent") or note.get("added"))
        when = nice_date(when) if when else ""
        if when and kind != "waiting":
            when += self._guessed_used(note)
        return {"id": note["id"], "text": note["text"], "kind": kind,
                "send": bool(note.get("send")), "work": bool(note.get("work")),
                "tokens": sender.short_tokens(self._tokens(note)) if "size" in note else "",
                "size": note.get("size", 0), "when": when,
                "group": note.get("group", "") if kind in ("waiting", "sent", "worked") else "",
                "snap": sender.snapshot_line(note["snap"]) if note.get("snap") else ""}

    def _total(self, notes):
        return sender.short_tokens(sum(self._tokens(n) for n in notes))

    def _work_notes(self):
        p = self.current
        if p is None:
            return [], []
        return ([n for n in self.store.get(p.slug) if n["work"]],
                [n for n in self.store.get(p.slug, "sent") if n["work"]])

    @pyqtProperty(int, notify=countsChanged)
    def workCount(self):
        waiting, sent = self._work_notes()
        return len(waiting) + len(sent)

    @pyqtProperty(str, notify=countsChanged)
    def workTokens(self):
        waiting, sent = self._work_notes()
        return self._total(waiting + sent) if waiting or sent else ""

    @pyqtProperty(bool, constant=True)
    def isLando(self):
        return self.lando

    @pyqtProperty(bool, notify=busyChanged)
    def busy(self):
        return self._busy

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
                groups = {}
                for n in notes:
                    if kind in ("waiting", "sent", "worked") and n.get("group"):
                        groups[n["group"]] = groups.get(n["group"], 0) + self._tokens(n)
                open_ = kind in ("waiting", "sent", "worked")
                sections.append({
                    "key": key, "title": title, "count": len(notes),
                    "total": self._total(notes) if open_ else "",
                    "send": kind == "waiting", "work": open_ and not self.lando,
                    "groups": {g: sender.short_tokens(t) for g, t in groups.items()},
                    "notes": [self._card(n, kind) for n in notes]})
        counts = (f"{len(waiting)} waiting · {len(sent)} sent · "
                  + (f"{len(review)} with Lando · " if review else "") + f"{len(done)} done"
                  + (f" · {len(later)} later" if later else ""))
        return {"title": p.title, "counts": counts, "sections": sections,
                "tickAll": bool(waiting or (sent and not self.lando)),
                "canOrganize": bool(waiting or sent)}

    LAYOUTS = ("list", "board", "sky", "timeline", "compact")

    @pyqtProperty(str, notify=layoutChanged)
    def layout(self):
        """The view (his ask, 2026-11-12): kept in notes.json, shared with the Tk VibeNote."""
        at = self.store.settings.get("layout", "list")
        return at if at in self.LAYOUTS else "list"

    @pyqtSlot(str)
    def setLayout(self, name):
        if name in self.LAYOUTS and name != self.layout:
            self.store.settings["layout"] = name
            self.store.save()
            self.layoutChanged.emit()

    @pyqtProperty("QVariantList", notify=pageChanged)
    def everyNote(self):
        """Every note of the open project for Board, Sky, Timeline and Compact, in status
        order (waiting, later, sent, worked, with Lando, done), each with its day."""
        p = self.current
        if p is None:
            return []
        st = self.store
        sent = st.get(p.slug, "sent")
        done = st.get(p.slug, "done")
        done = sorted((n for n in done if n.get("done")), key=lambda n: n["done"],
                      reverse=True) + [n for n in done if not n.get("done")]
        out = []
        for kind, notes in (("waiting", st.get(p.slug)), ("later", st.get(p.slug, "later")),
                            ("sent", [n for n in sent if not n.get("worked")]),
                            ("worked", [n for n in sent if n.get("worked")]),
                            ("review", st.get(p.slug, "review")), ("done", done)):
            for n in notes:
                card = self._card(n, kind)
                day = str(n.get("done") or n.get("review") or n.get("worked") or n.get("sent")
                          or n.get("added") or "")[:10]
                try:
                    card["dayTitle"] = date.fromisoformat(day).strftime("%A %-d %B")
                except ValueError:
                    card["dayTitle"] = "Earlier"
                card["day"] = day
                card["tokens"] = (sender.short_tokens(self._tokens(n))
                                  if "size" in n and kind not in ("done", "review") else "")
                out.append(card)
        return out

    @pyqtSlot(str, str)
    def boardDrop(self, note_id, column):
        """A card tossed into another Board column: Waiting → Sent sends it; Worked on →
        Done ticks it finished; Sent → Waiting puts it in Later. Anything else springs back."""
        note = self._note(note_id)
        if note is None:
            return
        kind = "worked" if note["status"] == "sent" and note.get("worked") else note["status"]
        if kind == "waiting" and column == "sent":
            p = self.current
            try:
                todo = sender.add_to_list(p, [note["text"]])
            except OSError as err:
                self.said.emit(f"Couldn't add it to the list: {err.strerror or err}.")
                self._changed()
                return
            self.store.mark_sent(p.slug, [note_id])
            self.said.emit(f"✓ Added to {todo.name}")
            self._changed()
        elif kind == "worked" and column == "done":
            self.finish(note_id)
        elif kind in ("sent", "worked") and column == "waiting":
            self.later(note_id)
        elif kind == "later" and column == "waiting":
            self.now(note_id)
        else:
            self._changed()  # springs back

    # --- the sidebar: his order and the Pinned box (his ask, 2026-11-06) -------------

    @pyqtSlot("QVariantList", "QVariantList")
    def setOrder(self, order, pinned):
        self.store.set_order([str(s) for s in order], [str(s) for s in pinned])
        self._sort()
        self.projectsChanged.emit()

    @pyqtSlot(str)
    def togglePin(self, slug):
        self.store.toggle_pin(slug, [p.slug for p in self.projects])
        self._sort()
        self.projectsChanged.emit()

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

    motionChanged = pyqtSignal()

    @pyqtProperty(bool, notify=motionChanged)
    def motion(self):
        """Slow motion with an off switch (his pick, 2026-11-12); shared with the Tk app."""
        return self.store.settings.get("motion", True) is not False

    @pyqtSlot()
    def toggleMotion(self):
        self.store.settings["motion"] = not self.motion
        self.store.save()
        self.motionChanged.emit()
        self.said.emit("Motion on" if self.motion else "Motion off: everything holds still")

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
        if self._view:
            self._view = ""
            self.viewChanged.emit()
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

    # --- ticking many at once ------------------------------------------------------

    def _section_notes(self, key):
        p, st = self.current, self.store
        sent = st.get(p.slug, "sent")
        return {"waiting": st.get(p.slug),
                "sent": [n for n in sent if not n.get("worked")],
                "worked": [n for n in sent if n.get("worked")]}.get(key, [])

    @pyqtSlot(str, str)
    def tickSection(self, key, which):
        """Clicking a section's "Send" or "Work": tick them all, or untick them if all are."""
        notes = self._section_notes(key) if self.current else []
        if notes:
            on = not all(n[which] for n in notes)
            self.store.tick(self.current.slug, [n["id"] for n in notes], which, on)
            self._changed()

    @pyqtSlot(str)
    def tickAll(self, which):
        """The "Tick all" row (his ask, 2026-11-02): every waiting note for Send, everything
        open for Work, or "none" to untick it all."""
        p = self.current
        if p is None:
            return
        waiting, sent = self.store.get(p.slug), self.store.get(p.slug, "sent")
        ids = [n["id"] for n in waiting + sent]
        if which == "send":
            self.store.tick(p.slug, [n["id"] for n in waiting], "send", True)
        elif which == "work":
            self.store.tick(p.slug, ids, "work", True)
        else:
            self.store.tick(p.slug, ids, "send", False)
            self.store.tick(p.slug, ids, "work", False)
        self._changed()

    # --- Organize, Move, New chat --------------------------------------------------

    def _relearn(self, tell):
        """Learn again from Claude's chats (a second or two, so on a side thread)."""
        def read():
            sender.refresh_own_usage(collect=True)
            self._learned.emit(sender.load_usage(), tell)

        threading.Thread(target=read, daemon=True).start()

    def _apply_learned(self, usage, tell):
        if usage:
            self.guess = sender.TokenGuess(usage)
            if not self._editing and not self._busy:
                self._changed()
        self.liveChanged.emit()
        if tell:
            self.said.emit("✓ Organized · estimates up to date")

    @pyqtSlot()
    def organize(self):
        """Sort and group the waiting and sent notes, smallest first, each with a size guess;
        no Claude. Also re-learns the token guesses for this time of day (his ask)."""
        p = self.current
        if p is None or not (self.store.get(p.slug) or self.store.get(p.slug, "sent")):
            self.said.emit("Nothing to organize yet.")
            return
        self.store.organize(p.slug)
        self.said.emit("Organized · updating the estimates…")
        self._changed()
        self._relearn(True)

    @pyqtSlot(str, result="QVariantList")
    def moveTargets(self, note_id):
        """What the right-click menu offers for this note."""
        note = self._note(note_id)
        if note is None:
            return []
        out = []
        if note["status"] == "later":
            out.append({"label": "Now: bring it back", "act": "now"})
        elif note["status"] in ("waiting", "sent"):
            out.append({"label": "Later: put it aside", "act": "later"})
        if note["status"] != "sent":  # on the list already: it stays in this project
            out += [{"label": "Move to " + p.title, "act": "move", "slug": p.slug}
                    for p in self.projects if p is not self.current]
        return out

    @pyqtSlot(str, str)
    def moveNote(self, note_id, slug):
        to = next((p for p in self.projects if p.slug == slug), None)
        if to and self._note(note_id):
            self.store.move(self.current.slug, note_id, to.slug)
            self.said.emit(f"Moved to {to.title}")
            self._changed()

    @pyqtSlot()
    def newChat(self):
        """A fresh plan-mode Claude chat on the project, with none of the notes (his ask,
        2026-11-10)."""
        p = self.current
        if p is None:
            return
        try:
            sender.new_chat(p)
        except OSError as err:
            self.said.emit(f"Couldn't open Claude: {err.strerror or err}")
            return
        self.said.emit(f"✓ Opening a new Claude chat on {p.title}.")

    @pyqtSlot(str)
    def showSnapshot(self, note_id):
        note = self._note(note_id)
        if note and note.get("snap"):
            self.said.emit(sender.snapshot_line(note["snap"]))

    # --- Work ------------------------------------------------------------------------

    @pyqtSlot(result="QVariantMap")
    def workAsk(self):
        """What the token warning says before Work (it always asks: his ask, 2026-10-30)."""
        p = self.current
        waiting, sent = self._work_notes()
        chosen = sent + waiting
        if p is None or not chosen or self._busy or self.lando:
            return {}
        n = len(chosen)
        extra = (f", including {len(waiting)} note{'s' * (len(waiting) != 1)} not sent yet, "
                 "which get added to its list first" if waiting else "")
        cost = sum(self._tokens(x) for x in chosen)
        usage_text = sender.usage_after(self.guess.usage, cost)
        fresh, why = sender.work_plan(p, self.guess.usage)
        if fresh:
            usage_text = (f"VibeNote will start {p.title}'s Claude fresh first: {why}. Claude "
                          "reads the project's notes again, so nothing is lost.\n\n"
                          + usage_text)
        return {"text": f"{p.title}'s Claude will start working on the {n} item{'s' * (n != 1)}"
                        f" you ticked for Work{extra}. It keeps going until they are done or "
                        "you stop it, using your tokens as it works. If no Claude chat is "
                        "open for it, a new terminal opens.",
                "cost": f"VibeNote's guess: {sender.short_tokens(cost)} tokens." if cost else "",
                "usage": usage_text}

    @pyqtSlot()
    def workGo(self):
        """He pressed "I agree, start work"."""
        p = self.current
        waiting, sent = self._work_notes()
        chosen = sent + waiting
        if p is None or not chosen or self._busy:
            return
        if waiting:
            try:
                sender.add_to_list(p, [n["text"] for n in waiting])
            except OSError as err:
                self.said.emit(f"Couldn't add them to the list: {err.strerror or err}.")
                return
            self.store.mark_sent(p.slug, [n["id"] for n in waiting])
        self.store.mark_worked(p.slug, [n["id"] for n in chosen],
                               {n["id"]: self._tokens(n) for n in chosen})
        items = [n["text"] for n in chosen]
        usage = self.guess.usage
        self._busy = True
        self.busyChanged.emit()
        self.said.emit("Starting…")
        self._changed()

        def go():
            try:
                self._workEnded.emit("✓ " + sender.start_work(p, items, usage))
            except OSError as err:
                self._workEnded.emit(f"Couldn't reach Claude: {err.strerror or err}")

        threading.Thread(target=go, daemon=True).start()

    def _work_ended(self, msg):
        self._busy = False
        self.busyChanged.emit()
        self.said.emit(msg)
        self._changed()

    # --- the other pages: Claude usage + tips, Find, Summary ------------------------
    # Each is a list of lines for InfoPage.qml: {text, style, slug?, email?, rich?}.
    # Styles: line, faded, good, warn, head, small, link, copy (a button).

    @pyqtProperty(str, notify=viewChanged)
    def view(self):
        return self._view

    @pyqtSlot(str)
    def setView(self, view):
        if view == "summary" and self.current is None:
            return
        self._view = view if view in ("usage", "find", "summary") else ""
        self.viewChanged.emit()

    @pyqtSlot(str)
    def setQuery(self, text):
        self._query = text
        self.viewChanged.emit()

    def _title_of(self, slug):
        if slug == "computer":
            return "Your computer (setup)"
        return next((p.title for p in self.projects if p.slug == slug), slug)

    @pyqtProperty("QVariantMap", notify=viewChanged)
    def info(self):
        try:
            return {"usage": self._usage_page, "find": self._find_page,
                    "summary": self._summary_page}.get(self._view, lambda: {})()
        except (KeyError, ValueError, TypeError) as err:  # never leave him on a broken page
            return {"title": "Something went wrong", "counts": str(err), "lines": []}

    def _usage_page(self):
        """Claude usage, broken down, for both accounts (his ask, 2026-11-02), and tips for
        lighter tokens at the bottom (his pick, 2026-11-04)."""
        t = sender.short_tokens
        usage = self.guess.usage or {}
        report = sender.usage_report(usage, sender.load_accounts())
        try:
            updated = datetime.fromisoformat(usage["updated"]).astimezone().strftime("%-d %b %H:%M")
        except (KeyError, ValueError):
            updated = "never"
        lines = []

        def add(text, style="line", **kw):
            lines.append({"text": text, "style": style, **kw})

        if not usage:
            add("No usage learned yet. It appears after Claude finishes a Work batch.", "faded")
        else:
            logged = next((a for a in report["accounts"] if a["logged_in"]), None)
            if report["use_now"]:
                best = next(a for a in report["accounts"] if a["name"] == report["use_now"])
                add(f"Use {best['name']} now: its week ends sooner ({sender.refresh_text(best)}),"
                    " and what it doesn't use is lost then.", "good")
            if logged:
                add(f"Logged in to Claude now: {logged['name']} ({logged['email']})", "faded")
            if report["five_hour"]:
                add(f"Last 5 hours: {t(usage.get('last5h', 0))} of the {t(report['five_hour'])} "
                    f"a 5-hour window holds (learned from the "
                    f"{len(usage.get('five_hour_fills', []))} times you hit one).")
            now = datetime.now().astimezone()
            for a in report["accounts"]:
                add(f"{a['name']} · {a['email']}" + (" · logged in now" if a["logged_in"] else ""),
                    "head")
                left = a["end"] - now
                add(f"Week refreshes {sender.refresh_text(a)}"
                    + (" (a guess)" if a.get("guess") else "")
                    + f" · in {left.days} d {left.seconds // 3600} h   ·   Change", "link",
                    email=a["email"])
                add(f"Used this week: {t(a['used'])} · your pace: {t(a['pace'])} a day")
                add(f"At this pace by the refresh: {t(a['projected'])}")
                if a["weekly_learned"]:
                    limit_text = f"its weekly limit, {t(a['limit'])}"
                elif a["limit"]:
                    limit_text = (f"at least {t(a['limit'])}: the most you've used in a week "
                                  "without hitting the limit, so the real one is bigger")
                else:
                    limit_text = None
                if limit_text:
                    add(f"A week can hold {limit_text}.", "faded")
                    state = "On track" if a["on_track"] else "Off track: you'll run out first"
                    add(f"{state} · to last the week: {t(a['daily_budget'])} a day for the "
                        f"{max(a['days_left'], 0):.1f} days left",
                        "good" if a["on_track"] else "warn")
                if a["projects"]:
                    parts = sorted(a["projects"].items(), key=lambda kv: -kv[1])
                    add("By project: " + " · ".join(f"{self._title_of(k)} {t(v)}"
                                                    for k, v in parts), "faded")
                if a["days"]:
                    add("By day: " + " · ".join(f"{k} {t(v)}" for k, v in a["days"].items()),
                        "faded")
            add("Which account was logged in is only known from 2 Nov; before that it counts "
                "as Account 2. The numbers get better as VibeNote sees more.", "small")
        add("Tips for lighter tokens · learned from your chats", "head", tips=True)
        for tip in sender.token_tips(usage, self.guess, self._title_of, direct=self.lando):
            add("•  " + tip)
        return {"title": "Claude usage",
                "counts": f"Tokens Claude wrote, from your chats · updated {updated}",
                "lines": lines}

    @pyqtSlot(str, str, result=str)
    def setRefresh(self, email, text):
        """He typed when an account's week refreshes ("Thu 11pm"). Returns what to say."""
        when = sender.parse_refresh(text)
        if when is None:
            return "Couldn't read that; try like \u201cThu 11pm\u201d."
        accounts = sender.load_accounts()
        for a in accounts:
            if a["email"] == email:
                a.update(when, guess=False)
                name = a["name"]
        sender.save_accounts(accounts)
        self.viewChanged.emit()
        return f"✓ {name} refreshes {sender.refresh_text({**when})}"

    def _find_page(self):
        """Every note in every project with all these words (Ctrl+F, his ask)."""
        query = self._query.strip().lower()
        if not query:
            return {"title": "Find", "counts": "Type to find notes in every project · Esc to go back",
                    "lines": []}
        words = query.split()
        mark = {"waiting": "waiting", "sent": "on its list", "done": "done", "later": "in Later",
                "review": "with Lando"}
        lines, found = [], 0
        for p in self.projects:
            for n in self.store.all(p.slug):
                snap = sender.snapshot_line(n["snap"]) if n.get("snap") else ""
                if not all(w in (n["text"] + " " + snap).lower() for w in words):
                    continue
                found += 1
                if found > 200:
                    continue
                lit = html.escape(n["text"])
                for w in sorted(set(words), key=len, reverse=True):  # light up his words
                    lit = _light(lit, html.escape(w))
                lines.append({"text": f"{p.title} · {mark.get(n['status'], n['status'])}",
                              "style": "where", "slug": p.slug, "note": n["id"]})
                lines.append({"text": lit, "style": "hit", "rich": True, "slug": p.slug,
                              "note": n["id"]})
                if snap:
                    lines.append({"text": snap, "style": "small", "slug": p.slug,
                                  "note": n["id"]})
        return {"title": "Find", "counts": f"{found} found · click one to open its project",
                "lines": lines}

    def _summary_page(self):
        """Everything ever noted for this project, condensed (his ask, 2026-11-02): grouped,
        each said shorter, open ones first, and the open ones ready to copy for Claude."""
        p = self.current
        notes = self.store.all(p.slug)
        open_notes = [n for n in notes if n["status"] in ("waiting", "sent")]  # not Later
        mine = " ".join(n["text"] for n in open_notes)
        self._short = "\n".join(f"- {condense(n['text'])}" for n in open_notes)
        lines = []
        if open_notes:
            lines.append({"text": "Copy the open ones for Claude", "style": "copy"})
        mark = {"waiting": "•", "sent": "→", "done": "✓", "later": "◦", "review": "✓"}
        groups = group_notes([dict(n) for n in notes])
        groups.sort(key=lambda g: (g[0] == "On their own", -len(g[1])))
        for heading, members in groups:
            open_n = sum(m["status"] not in ("done", "review") for m in members)
            lines.append({"text": f"{heading} · {len(members)} notes, {open_n} open",
                          "style": "group"})
            for m in sorted(members, key=lambda m: m["status"] in ("done", "review")):
                lines.append({"text": f"{mark.get(m['status'], '•')}  {condense(m['text'])}",
                              "style": "faded" if m["status"] in ("done", "review") else "line"})
        return {"title": f"{p.title}: summary",
                "counts": f"{len(notes)} notes · {len(open_notes)} open · for Claude: "
                          f"~{tokens_in(mine)} → ~{tokens_in(self._short)} tokens",
                "lines": lines}

    @pyqtSlot()
    def copySummary(self):
        from PyQt6.QtGui import QGuiApplication
        QGuiApplication.clipboard().setText(getattr(self, "_short", ""))
        self.said.emit("✓ Copied: paste it into a Claude chat")


def _light(text, word):
    """Wrap each match of word (ignoring case) in a lit span, outside of tags."""
    import re
    return re.sub("(" + re.escape(word) + ")(?![^<]*>)",
                  r'<span style="background-color:#173027;color:#d79a74">\1</span>', text,
                  flags=re.IGNORECASE)
