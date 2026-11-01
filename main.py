"""VibeNote: notes for each of his projects, on warm paper, sent to that project's Claude in batches.

Writing and sorting notes never needs Claude; only the Send button talks to it.
"""

import json
import os
import sys
import subprocess
from datetime import date, datetime
import threading
import time
import tkinter as tk
from tkinter import font as tkfont

import projects
import sender
from store import Store, size_label, size_score

# Dark warm colours (his ask, 2026-10-30: "darker, i like warm colors but it cant hurt my
# eyes, im light sensitive"): deep brown, soft cream text (never white), muted terracotta.
PAPER = "#211b16"           # the page
SIDEBAR = "#19140f"
SIDEBAR_PICKED = "#30271f"
INK = "#d9c8ab"             # main text: soft cream, not bright
FADED_INK = "#8a7a64"
RULE = "#382f27"            # ruled lines, quiet borders
ACCENT = "#c47650"          # muted terracotta: headings, Send tick, main button
ACCENT_DARK = "#d58a63"     # main button when the mouse is on it
MARGIN = "#5e3a2a"          # the notebook margin line, kept dim
FIELD = "#2a231d"           # text boxes
WORK_GREEN = "#8ea36b"      # the Work tick, so it never looks like the Send tick

SERIF = "Georgia"


def nice_date(iso):
    """"2026-10-30" -> "30 Oct"."""
    try:
        return date.fromisoformat(iso).strftime("%-d %b")
    except ValueError:
        return iso


class VibeNote(tk.Tk):
    def __init__(self):
        super().__init__(className="vibenote")
        self.title("VibeNote")
        self.geometry("920x640")
        self.minsize(520, 380)
        self.configure(bg=PAPER)

        self.store = Store()
        self.guess = sender.TokenGuess(self._read_usage())
        self.projects = projects.find_projects()
        waiting = [p for p in self.projects if self.store.get(p.slug)]
        self.current = (waiting or self.projects)[0] if self.projects else None
        self.sending = None  # the message from a send running in the background

        self.f_brand = tkfont.Font(family=SERIF, size=20, weight="bold", slant="italic")
        self.f_head = tkfont.Font(family=SERIF, size=10, slant="italic")
        self.f_side = tkfont.Font(family=SERIF, size=13)
        self.f_side_picked = tkfont.Font(family=SERIF, size=13, weight="bold")
        self.f_title = tkfont.Font(family=SERIF, size=24, weight="bold")
        self.f_note = tkfont.Font(family=SERIF, size=14)
        self.f_todo = tkfont.Font(family=SERIF, size=12)
        self.f_box = tkfont.Font(family="DejaVu Sans", size=15)
        # Tick columns sized from the text itself: his screen draws text ~1/3 bigger than
        # a plain one, and fixed pixel sizes cut the ticks off there
        self.tick_w = max(self.f_head.measure("Work"), self.f_box.measure("☑")) + 20
        self.tick_h = self.f_box.metrics("linespace") + 4
        self.head_h = self.f_head.metrics("linespace") + 4
        self.f_small = tkfont.Font(family=SERIF, size=11, slant="italic")
        self.f_button = tkfont.Font(family=SERIF, size=13, weight="bold")

        # The glowing notepad shows while the page is built (his pick, 2026-11-01)
        loading = Loading(self)
        self.update()
        self._build_sidebar()
        self._build_page()
        tk.Misc.lift(loading)  # stays on top of the page being built under it
        self.sync()  # the first one in the open; later ones on a side thread
        self._sort()
        waiting = [p for p in self.projects if self.store.get(p.slug)]
        self.current = (waiting or self.projects or [None])[0]
        self.refresh()
        self._show_sign()
        self.after(10_000, self._reread_todo)
        self.after(1500, self._relearn)
        self.after(200, self._float)
        self._size = None
        self._redraw_soon = None
        # Only the window itself: a plain bind here also fires for every widget inside it,
        # tens of thousands of times while the page is first laid out
        self.bindtags(("vibenote-window",) + self.bindtags())
        self.bind_class("vibenote-window", "<Configure>", self._resized)
        self._rewrap_all()  # notes wrapped before the notepad goes
        loading.finish()

    def _resized(self, event):
        """On his desktop, parts of the page were left undrawn after the window changed size
        (the ticks looked cut off), so repaint the page once the size settles."""
        if event.widget is not self or (event.width, event.height) == self._size:
            return
        self._size = (event.width, event.height)
        if self._redraw_soon:
            self.after_cancel(self._redraw_soon)
        self._redraw_soon = self.after(150, self._redraw)

    def _redraw(self):
        """Hide and show the page in one go: everything on it is drawn afresh, without the
        cost of building it all again."""
        self._redraw_soon = None
        self.canvas.itemconfigure(self._win, state="hidden")
        self.update_idletasks()
        self.canvas.itemconfigure(self._win, state="normal")

    # --- the window floats freely (his pick) ------------------------------

    def _float(self):
        """On his desktop (Hyprland) windows snap into tiles; ask for this one to float instead."""
        if not os.environ.get("HYPRLAND_INSTANCE_SIGNATURE"):
            return
        me = f"pid:{os.getpid()}"
        for args in (["setfloating", me], ["resizewindowpixel", f"exact 920 640,{me}"],
                     ["centerwindow"]):
            try:
                subprocess.run(["hyprctl", "dispatch", *args], capture_output=True, timeout=3)
            except (OSError, subprocess.SubprocessError):
                return

    # --- layout -----------------------------------------------------------

    def _build_sidebar(self):
        side = tk.Frame(self, bg=SIDEBAR, width=220)
        side.pack(side="left", fill="y")
        side.pack_propagate(False)

        tk.Label(side, text="VibeNote", font=self.f_brand, bg=SIDEBAR, fg=ACCENT,
                 anchor="w").pack(fill="x", padx=18, pady=(18, 4))
        tk.Label(side, text="Your projects", font=self.f_head, bg=SIDEBAR, fg=FADED_INK,
                 anchor="w").pack(fill="x", padx=18, pady=(0, 10))

        # "Is now a good time for Claude?" (his ask, 2026-11-01), at the bottom
        sign = tk.Frame(side, bg=SIDEBAR)
        sign.pack(side="bottom", fill="x", padx=18, pady=(0, 18))
        self.sign_title = tk.Label(sign, font=self.f_side_picked, bg=SIDEBAR, anchor="w",
                                   justify="left", wraplength=184)
        self.sign_title.pack(fill="x")
        self.sign_why = tk.Label(sign, font=self.f_small, bg=SIDEBAR, fg=FADED_INK, anchor="w",
                                 justify="left", wraplength=184)
        self.sign_why.pack(fill="x")

        self.list_box = tk.Frame(side, bg=SIDEBAR)
        self.list_box.pack(fill="both", expand=True)

    def _build_page(self):
        page = tk.Frame(self, bg=PAPER)
        page.pack(side="left", fill="both", expand=True)

        # Red margin line down the left of the page, like notebook paper
        tk.Frame(page, bg=MARGIN, width=2).pack(side="left", fill="y", padx=(36, 0))

        body = tk.Frame(page, bg=PAPER)
        body.pack(side="left", fill="both", expand=True, padx=(24, 36), pady=(22, 16))

        self.title_label = tk.Label(body, font=self.f_title, bg=PAPER, fg=INK, anchor="w")
        self.title_label.pack(fill="x")
        self.count_label = tk.Label(body, font=self.f_small, bg=PAPER, fg=FADED_INK, anchor="w")
        self.count_label.pack(fill="x", pady=(0, 14))

        # Box for typing a new note
        entry_row = tk.Frame(body, bg=FIELD, highlightthickness=1, highlightbackground=RULE)
        entry_row.pack(fill="x", pady=(0, 10))
        self.entry = tk.Entry(entry_row, font=self.f_note, bg=FIELD, fg=INK,
                              insertbackground=INK, relief="flat", highlightthickness=0)
        self.entry.pack(fill="x", ipady=8, padx=10)
        self.entry.bind("<Return>", lambda e: self.add_note())
        self._placeholder = "Write a note and press Enter…"
        self._show_placeholder()
        self.entry.bind("<FocusIn>", lambda e: self._hide_placeholder())
        self.entry.bind("<FocusOut>", lambda e: self._show_placeholder())

        # The bottom bar: what happened, Send (onto the to-do list, no tokens) and Work
        # (Claude starts on the list, uses tokens: he has to agree first)
        bottom = tk.Frame(body, bg=PAPER)
        bottom.pack(side="bottom", fill="x", pady=(10, 0))
        self.work_btn = Button(bottom, self.f_button, self.work, main=True)
        self.work_btn.pack(side="right")
        self.send_btn = Button(bottom, self.f_button, self.send, main=False)
        self.send_btn.pack(side="right", padx=(0, 10))
        # Organize (his ask): a free rough guess at each change's size, smallest first
        self.organize_btn = Button(bottom, self.f_button, self.organize, main=False)
        self.organize_btn.set("Organize")
        self.organize_btn.pack(side="right", padx=(0, 10))
        self.status = tk.Label(bottom, font=self.f_small, bg=PAPER, fg=FADED_INK, anchor="w",
                               justify="left")
        self.status.pack(side="left", fill="x", expand=True)

        # Scrolling area for the notes and the project's to-do list
        holder = tk.Frame(body, bg=PAPER)
        holder.pack(fill="both", expand=True)
        self.canvas = tk.Canvas(holder, bg=PAPER, highlightthickness=0, yscrollincrement=6)
        self.canvas.pack(side="left", fill="both", expand=True)
        self.notes_frame = tk.Frame(self.canvas, bg=PAPER)
        self._win = self.canvas.create_window(0, 0, window=self.notes_frame, anchor="nw")
        self.notes_frame.bind("<Configure>", lambda e: self.canvas.configure(
            scrollregion=self.canvas.bbox("all")))
        self._wrapping, self._wrap_guess, self._rewrap_job = [], {}, None

        def canvas_resized(e):
            self.canvas.itemconfigure(self._win, width=e.width)
            self._rewrap_soon()

        self.canvas.bind("<Configure>", canvas_resized)
        self.bind_all("<Button-4>", lambda e: self._scroll(-1))
        self.bind_all("<Button-5>", lambda e: self._scroll(1))
        self.bind_all("<MouseWheel>", lambda e: self._scroll(-1 if e.delta > 0 else 1))

    def _scroll(self, steps):
        """Smooth scrolling: each turn of the wheel glides 72 px over a few frames."""
        if self.notes_frame.winfo_height() <= self.canvas.winfo_height():
            return
        self._glide = getattr(self, "_glide", 0) + steps * 12  # in 6 px units
        if not getattr(self, "_gliding", False):
            self._gliding = True
            self._glide_step()

    def _glide_step(self):
        if not self._glide:
            self._gliding = False
            return
        step = max(1, abs(self._glide) // 4)  # quick at first, easing off
        step = step if self._glide > 0 else -step
        self.canvas.yview_scroll(step, "units")
        self._glide -= step
        top, bottom = self.canvas.yview()
        if (self._glide < 0 and top <= 0) or (self._glide > 0 and bottom >= 1):
            self._glide = 0  # at the end: stop, don't store up scrolling
        self.after(12, self._glide_step)

    def _show_placeholder(self):
        if not self.entry.get():
            self.entry.insert(0, self._placeholder)
            self.entry.configure(fg=FADED_INK)

    def _hide_placeholder(self):
        if self.entry.get() == self._placeholder and self.entry.cget("fg") == FADED_INK:
            self.entry.delete(0, "end")
            self.entry.configure(fg=INK)

    # --- drawing ----------------------------------------------------------

    def refresh(self, keep_scroll=False):
        self._draw_sidebar()
        self._draw_page(keep_scroll)

    def _sort(self):
        """Longest lists on top (his ask): every note it has ever had, waiting, sent and done."""
        self.projects.sort(key=lambda p: (-len(self.store.all(p.slug)), p.title.lower()))

    def _draw_sidebar(self):
        for w in self.list_box.winfo_children():
            w.destroy()
        self._sort()
        for p in self.projects:
            picked = p is self.current
            waiting = len(self.store.get(p.slug))
            bg = SIDEBAR_PICKED if picked else SIDEBAR
            row = tk.Frame(self.list_box, bg=bg, cursor="hand2")
            row.pack(fill="x")
            name = tk.Label(row, text=p.title, bg=bg, fg=INK, anchor="w",
                            font=self.f_side_picked if picked else self.f_side)
            name.pack(side="left", fill="x", expand=True, padx=(18, 4), pady=7)
            num = tk.Label(row, text=str(waiting) if waiting else "", bg=bg, fg=ACCENT,
                           font=self.f_side_picked)
            num.pack(side="right", padx=14)
            for w in (row, name, num):
                w.bind("<Button-1>", lambda e, proj=p: self.pick(proj))

    def _draw_page(self, keep_scroll=False):
        self._wrapping = []
        self._rewrap_soon()
        for w in self.notes_frame.winfo_children():
            w.destroy()
        p = self.current
        if p is None:
            self.title_label.configure(text="No projects yet")
            self.count_label.configure(text="Start one with vibe, and it shows up here")
            self.send_btn.pack_forget()
            self.work_btn.pack_forget()
            self.organize_btn.pack_forget()
            return

        notes = self.store.get(p.slug)
        sent = self.store.get(p.slug, "sent")
        done = self.store.get(p.slug, "done")
        # Newest first: finished since VibeNote started watching, then the imported ones
        # in the order the to-do file had them (its newest are at the top)
        done = sorted((n for n in done if n.get("done")), key=lambda n: n["done"],
                      reverse=True) + [n for n in done if not n.get("done")]
        self.title_label.configure(text=p.title)
        self.count_label.configure(
            text=f"{len(notes)} waiting · {len(sent)} sent · {len(done)} done")

        if not notes:
            tk.Label(self.notes_frame, text="No notes waiting. Write one above.",
                     font=self.f_small, bg=PAPER, fg=FADED_INK, anchor="w").pack(fill="x", pady=6)
        else:
            self._heading(f"Waiting to send ({len(notes)})", notes, send=True, top=True)
        group = None
        for note in notes:
            group = self._group_heading(note, group)
            self._draw_note(note)

        if sent:
            self._heading(f"Sent: on its to-do list ({len(sent)})", sent, send=False)
            group = None
            for note in sent:
                group = self._group_heading(note, group)
                self._draw_history(note)
        if done:
            self._heading(f"Done ({len(done)})")
            self._draw_done(done)

        self._update_buttons()
        if not keep_scroll:
            self.canvas.yview_moveto(0)

    def _draw_note(self, note):
        row = tk.Frame(self.notes_frame, bg=PAPER)
        row.pack(fill="x")
        line = tk.Frame(row, bg=PAPER)
        line.pack(fill="x", pady=5)

        dot = tk.Label(line, text="•", font=self.f_note, bg=PAPER, fg=ACCENT)
        dot.pack(side="left", padx=(2, 10), anchor="n")
        text = tk.Label(line, text=note["text"], bg=PAPER, fg=INK, anchor="w", justify="left",
                        font=self.f_note, cursor="xterm")
        self._tick_cell(line, note, "work")
        self._tick_cell(line, note, "send")
        remove = tk.Label(line, text="×", font=self.f_note, bg=PAPER, fg=PAPER, cursor="hand2")
        remove.pack(side="right", padx=(8, 4), anchor="n")
        move = tk.Label(line, text="Move", font=self.f_small, bg=PAPER, fg=PAPER, cursor="hand2")
        move.pack(side="right", padx=(8, 0), anchor="n", pady=(3, 0))
        self._size_tag(line, note, pady=(3, 0))
        # The text goes in last, so it gets the room left over and never squeezes the ticks
        text.pack(side="left", fill="x", expand=True)
        self._wrap(text)

        # Ruled line under each note, like lined paper
        tk.Frame(row, bg=RULE, height=1).pack(fill="x")

        text.bind("<Button-1>", lambda e: self.edit_note(note, line, text))
        remove.bind("<Button-1>", lambda e: self.delete_note(note))
        move.bind("<Button-1>", lambda e: self.move_menu(note, e))
        for w in (row, line, dot, text):
            w.bind("<Button-3>", lambda e: self.move_menu(note, e))

        # "Move" and × only show while the mouse is over the note
        def show(_):
            remove.configure(fg=FADED_INK)
            move.configure(fg=FADED_INK)

        def hide(_):
            remove.configure(fg=PAPER)
            move.configure(fg=PAPER)

        for w in (row, line, dot, text, remove, move):
            w.bind("<Enter>", show, add="+")
            w.bind("<Leave>", hide, add="+")
        remove.bind("<Enter>", lambda e: remove.configure(fg=ACCENT), add="+")
        move.bind("<Enter>", lambda e: move.configure(fg=ACCENT), add="+")

    def _heading(self, text, notes=None, send=False, top=False):
        """A section title; with notes, also the "Send"/"Work" column titles over the ticks.
        Clicking a column title ticks the whole column (or unticks it, if all are ticked)."""
        row = tk.Frame(self.notes_frame, bg=PAPER)
        row.pack(fill="x", pady=(6 if top else 26, 4))
        if notes:
            for which, colour, shown in (("work", WORK_GREEN, True), ("send", ACCENT, send)):
                cell = tk.Frame(row, bg=PAPER, width=self.tick_w, height=self.head_h)
                cell.pack(side="right")
                cell.pack_propagate(False)
                if shown:
                    lab = tk.Label(cell, text=which.capitalize(), font=self.f_head, bg=PAPER,
                                   fg=colour, cursor="hand2")
                    lab.pack(expand=True)
                    lab.bind("<Button-1>", lambda e, w=which: self.tick_all(notes, w))
        tk.Label(row, text=text, font=self.f_head, bg=PAPER, fg=FADED_INK,
                 anchor="w").pack(side="left", fill="x", expand=True)

    def _group_heading(self, note, current):
        """After Organize, a quiet heading over each group of related notes (his pick).
        Returns the group now showing."""
        group = note.get("group")
        if group and group != current:
            tk.Label(self.notes_frame, text=group, font=self.f_small, bg=PAPER, fg=ACCENT,
                     anchor="w").pack(fill="x", padx=(20, 0), pady=(10, 0))
        return group

    def _tick_cell(self, parent, note, which):
        """One tick box in the "send" or "work" column; None draws an empty cell."""
        cell = tk.Frame(parent, bg=PAPER, width=self.tick_w, height=self.tick_h)
        cell.pack(side="right", anchor="n")
        cell.pack_propagate(False)
        if note is None:
            return
        on = note[which]
        colour = ACCENT if which == "send" else WORK_GREEN
        box = tk.Label(cell, text="☑" if on else "☐", font=self.f_box, bg=PAPER,
                       fg=colour if on else FADED_INK, cursor="hand2")
        box.pack(expand=True)
        box.bind("<Button-1>", lambda e: self.tick(note, which, box))

    def _wrap(self, label):
        """Wrap a note's text to the room it has. All notes are wrapped together in one pass
        once the page is laid out (_rewrap_all), not each on its own resize: that set off
        a chain of re-layouts which made the window take ~9 s to open. Until then, the
        width from the last pass is a close guess."""
        if label.cget("font") == str(self.f_note):
            guess = self._wrap_guess.get("note")
        else:
            guess = self._wrap_guess.get("todo")
        if guess:
            label.configure(wraplength=guess)
        self._wrapping.append(label)

    def _rewrap_soon(self, _=None):
        if self._rewrap_job:
            self.after_cancel(self._rewrap_job)
        self._rewrap_job = self.after(40, self._rewrap_all)

    def _rewrap_all(self):
        self._rewrap_job = None
        self.update_idletasks()  # so every note has its real width
        for label in self._wrapping:
            if not label.winfo_exists():
                continue
            width = max(label.winfo_width() - 12, 50)
            kind = "note" if label.cget("font") == str(self.f_note) else "todo"
            self._wrap_guess[kind] = width
            if abs(width - int(label.cget("wraplength") or 0)) > 3:
                label.configure(wraplength=width)

    def _size_tag(self, parent, note, pady=0):
        """Small / Medium / Big, once Organize has guessed this note's size."""
        if "size" not in note:
            return
        label = size_label(note["size"])
        colour = {"Small": WORK_GREEN, "Medium": FADED_INK, "Big": ACCENT}[label]
        tokens = sender.short_tokens(self._tokens(note))
        tk.Label(parent, text=f"{label} · {tokens}", font=self.f_small, bg=PAPER, fg=colour,
                 width=13, anchor="e").pack(side="right", padx=(10, 0), anchor="n", pady=pady)

    def _draw_history(self, note):
        done = note["status"] == "done"
        line = tk.Frame(self.notes_frame, bg=PAPER)
        line.pack(fill="x", pady=2)
        # ✓ finished, → on the list
        tk.Label(line, text="✓" if done else "→", font=self.f_todo, bg=PAPER,
                 fg=ACCENT if done else FADED_INK, width=2).pack(side="left", padx=(0, 6),
                                                                 anchor="n")
        if not done:
            self._tick_cell(line, note, "work")
            self._tick_cell(line, None, "send")
            self._size_tag(line, note)  # by the ticks, so the tags line up in a column
        if done:
            when = nice_date(note["done"]) if note.get("done") else ""
        elif note.get("worked"):
            when = f"Claude on it · {nice_date(note['worked'])}"
        else:
            when = nice_date(note["sent"]) if note.get("sent") else ""
        if when:
            tk.Label(line, text=when, font=self.f_small, bg=PAPER,
                     fg=WORK_GREEN if note.get("worked") and not done else FADED_INK
                     ).pack(side="right", padx=(10, 4), anchor="n")
        text = tk.Label(line, text=note["text"], font=self.f_todo, bg=PAPER,
                        fg=FADED_INK if done else INK, anchor="w", justify="left")
        text.pack(side="left", fill="x", expand=True)
        self._wrap(text)

    def _draw_done(self, done):
        """The Done list as one block of text, not a row of widgets per item: it can run to
        dozens of items, and rebuilding that many widgets made the window choppy."""
        indent = self.f_todo.measure("✓") + 14
        box = tk.Text(self.notes_frame, bg=PAPER, fg=FADED_INK, font=self.f_todo, wrap="word",
                      relief="flat", bd=0, highlightthickness=0, padx=0, pady=0, height=1,
                      cursor="arrow", spacing3=7)
        box.tag_configure("item", lmargin1=2, lmargin2=indent,
                          tabs=(indent,))
        box.tag_configure("tick", foreground=ACCENT)
        box.tag_configure("date", font=self.f_small, foreground=FADED_INK)
        for note in done:
            box.insert("end", "✓", ("item", "tick"), "\t" + note["text"], "item")
            if note.get("done"):
                box.insert("end", "   " + nice_date(note["done"]), ("item", "date"))
            box.insert("end", "\n", "item")
        box.delete("end-2c")  # no blank line after the last one
        box.configure(state="disabled")
        box.bindtags((str(box), "all"))  # no selecting or scrolling of its own
        box.pack(fill="x", pady=(2, 0))

        def fit(e=None):
            # Only when its width really changed: counting lines is slow, and every
            # height change sets off another round of layout
            if e is not None and abs(e.width - getattr(box, "_fit_w", 0)) < 4:
                return
            box._fit_w = e.width if e is not None else 0
            lines = box.count("1.0", "end", "displaylines")
            lines = lines[0] if isinstance(lines, tuple) else lines
            if lines and int(box.cget("height")) != lines:
                box.configure(height=lines)

        box.bind("<Configure>", fit)

    def _update_buttons(self):
        if self.sending is not None or self.current is None:
            return
        notes = self.store.get(self.current.slug)
        sent = self.store.get(self.current.slug, "sent")
        n = sum(x["send"] for x in notes)
        w = sum(x["work"] for x in notes + sent)
        self.send_btn.set(f"Send {n} ticked" if n else "Send", enabled=bool(n))

        total = sum(self._tokens(x) for x in notes + sent if x["work"])
        self.work_btn.set(f"Work on {w} · {sender.short_tokens(total)}  →" if w else "Work  →",
                          enabled=bool(w))

    def sync(self, results=None):
        """Bring the history in line with every project's to-do list. Returns whether it changed.
        results: what a background read found ({slug: (open, done)}); else read here."""
        if results is None:
            results = {p.slug: p.read() for p in self.projects}
        changed = False
        for p in self.projects:
            if p.slug in results:
                open_items, done = results[p.slug]
                changed |= self.store.sync(p.slug, open_items, done)
        return changed

    def _reread_todo(self):
        """Claude ticks things off the to-do lists while he works; keep up with it. The files
        (and, for a shared game, every git branch) are read on a side thread, so the window
        never stalls while that happens."""
        found = {}

        def read():
            for p in list(self.projects):
                found[p.slug] = p.read()

        reader = threading.Thread(target=read, daemon=True)
        reader.start()

        def apply():
            if reader.is_alive():
                self.after(100, apply)
                return
            f = self.focus_get()
            editing = isinstance(f, tk.Entry) and f is not self.entry
            if not editing and self.sending is None and self.sync(found):
                self.refresh(keep_scroll=True)
            self.after(10_000, self._reread_todo)

        self.after(100, apply)

    # --- tokens --------------------------------------------------------------

    def _read_usage(self):
        try:
            return json.loads(sender.USAGE.read_text())
        except (OSError, ValueError):
            return None

    def _tokens(self, note):
        """The learned guess for one note, at this hour."""
        size = note["size"] if "size" in note else size_score(note["text"])
        return self.guess.tokens(size, datetime.now().hour)

    def _relearn(self):
        """Every 5 minutes: learn again from Claude's chats (on a side thread: reading them
        takes a second or two), then update the sign and the guesses."""
        found = []
        reader = threading.Thread(target=lambda: found.append(sender.load_usage()),
                                  daemon=True)
        reader.start()

        def apply():
            if reader.is_alive():
                self.after(200, apply)
                return
            if found and found[0]:
                self.guess = sender.TokenGuess(found[0])
                if self.sending is None:
                    self.refresh(keep_scroll=True)
            self._show_sign()
            self.after(5 * 60_000, self._relearn)

        self.after(200, apply)

    def _show_sign(self):
        level, why = sender.good_time(self.guess)
        title, colour = {"good": ("● Good time for Claude", WORK_GREEN),
                         "ok": ("● OK time for Claude", INK),
                         "bad": ("● Not a great time for Claude", ACCENT)}[level]
        self.sign_title.configure(text=title, fg=colour)
        self.sign_why.configure(text=why)

    def say(self, text, colour=FADED_INK):
        self.status.configure(text=text, fg=colour)

    # --- actions ----------------------------------------------------------

    def pick(self, project):
        self.current = project
        self.say("")
        self.refresh()

    def add_note(self):
        text = self.entry.get()
        if text == self._placeholder and self.entry.cget("fg") == FADED_INK:
            return
        if self.current and self.store.add(self.current.slug, text):
            self.entry.delete(0, "end")
            self.refresh(keep_scroll=True)

    def tick(self, note, which, box):
        """Flip one tick. Only that box and the buttons change; the page is not rebuilt."""
        self.store.tick(self.current.slug, [note["id"]], which, not note[which])
        on = note[which]
        colour = ACCENT if which == "send" else WORK_GREEN
        box.configure(text="☑" if on else "☐", fg=colour if on else FADED_INK)
        self._update_buttons()

    def tick_all(self, notes, which):
        on = not all(n[which] for n in notes)
        self.store.tick(self.current.slug, [n["id"] for n in notes], which, on)
        self.refresh(keep_scroll=True)

    def organize(self):
        """Sort the waiting and sent notes smallest change first, each tagged with its size.
        VibeNote guesses from the words in each note: no Claude, no tokens."""
        p = self.current
        if p is None or not (self.store.get(p.slug) or self.store.get(p.slug, "sent")):
            self.say("Nothing to organize yet.")
            return
        self.store.organize(p.slug)
        self.say("Sorted smallest to biggest. It's a rough guess from the words, "
                 "no tokens used.", ACCENT)
        self.refresh()

    def delete_note(self, note):
        self.store.delete(self.current.slug, note["id"])
        self.refresh(keep_scroll=True)

    def edit_note(self, note, line, label):
        """Swap the note for a text box; Enter or clicking away saves it, Esc leaves it as it was."""
        label.pack_forget()
        box = tk.Entry(line, font=self.f_note, bg=FIELD, fg=INK, relief="flat",
                       insertbackground=INK, highlightthickness=1,
                       highlightbackground=RULE, highlightcolor=ACCENT)
        box.insert(0, note["text"])
        box.pack(side="left", fill="x", expand=True)
        box.focus_set()
        box.icursor("end")
        done = []

        def finish(save=True):
            if done:
                return
            done.append(True)
            if save:
                self.store.edit(self.current.slug, note["id"], box.get())
            self.refresh(keep_scroll=True)

        box.bind("<Return>", lambda e: finish())
        box.bind("<FocusOut>", lambda e: finish())
        box.bind("<Escape>", lambda e: finish(save=False))

    def move_menu(self, note, event):
        menu = tk.Menu(self, tearoff=0, bg=FIELD, fg=INK, activebackground=SIDEBAR_PICKED,
                       activeforeground=INK, font=self.f_side, relief="flat")
        menu.add_command(label="Move to…", state="disabled")
        for p in self.projects:
            if p is not self.current:
                menu.add_command(label=p.title, command=lambda to=p: self.move_note(note, to))
        menu.tk_popup(event.x_root, event.y_root)

    def move_note(self, note, to):
        self.store.move(self.current.slug, note["id"], to.slug)
        self.say(f"Moved to {to.title}")
        self.refresh(keep_scroll=True)

    def _send(self, p, notes):
        """Put these waiting notes on the project's to-do list. Returns the file, or None."""
        try:
            todo = sender.add_to_list(p, [n["text"] for n in notes])
        except OSError as err:
            self.say(f"Couldn't add them to the list: {err.strerror or err}. "
                     "Your notes are still here.", ACCENT)
            return None
        self.store.mark_sent(p.slug, [n["id"] for n in notes])
        return todo

    def send(self):
        """Send: the ticked waiting notes go on the bottom of the project's to-do list. No tokens."""
        p = self.current
        notes = [n for n in self.store.get(p.slug) if n["send"]] if p else []
        if not notes or self.sending is not None:
            return
        todo = self._send(p, notes)
        if todo:
            n = len(notes)
            self.say(f"✓ {n} note{'s' * (n != 1)} added to {todo.name}", ACCENT)
        self.refresh(keep_scroll=True)

    def work(self):
        """Work: the project's Claude starts on the Work-ticked items, once he agrees to use tokens."""
        p = self.current
        if p is None or self.sending is not None:
            return
        waiting = [n for n in self.store.get(p.slug) if n["work"]]
        sent = [n for n in self.store.get(p.slug, "sent") if n["work"]]
        chosen = sent + waiting
        if not chosen:
            return
        extra = (f", including {len(waiting)} note{'s' * (len(waiting) != 1)} not sent yet, "
                 "which get added to its list first" if waiting else "")
        if not TokenWarning(self, p.title, len(chosen), extra).agreed:
            self.say("Nothing sent to Claude.")
            return
        if waiting and not self._send(p, waiting):
            return
        self.store.mark_worked(p.slug, [n["id"] for n in chosen])
        items = [n["text"] for n in chosen]
        self.sending = "…"
        self.work_btn.set("Starting…", enabled=False)

        def go():
            try:
                self.sending = ("ok", sender.start_work(p, items))
            except OSError as err:
                self.sending = ("fail", f"Couldn't reach Claude: {err.strerror or err}")

        threading.Thread(target=go, daemon=True).start()
        self._wait_for_work()

    def _wait_for_work(self):
        if self.sending == "…":
            self.after(150, self._wait_for_work)
            return
        how, msg = self.sending
        self.sending = None
        self.say(f"✓ {msg}" if how == "ok" else msg, ACCENT)
        self.refresh(keep_scroll=True)


class Loading(tk.Canvas):
    """The VibeNote notepad (assets/icon.svg, in pixels), softly pulsing in the middle of the
    window while it opens. Its page is dimmed from the icon's: he is light sensitive."""

    PIXELS = [  # x, y, width, height, colour, on the 32 x 32 grid of the icon
        (7, 6, 18, 23, "#1d3b2a"), (8, 7, 16, 21, "#aac59d"), (8, 7, 16, 1, "#bcd6b0"),
        (8, 27, 16, 1, "#8fb083"), (23, 8, 1, 19, "#9bb98e"), (8, 8, 16, 3, "#4f9e66"),
        (8, 10, 16, 1, "#3a8653"),
        (10, 4, 2, 5, "#1d3b2a"), (10, 5, 1, 3, "#86c895"), (15, 4, 2, 5, "#1d3b2a"),
        (15, 5, 1, 3, "#86c895"), (20, 4, 2, 5, "#1d3b2a"), (20, 5, 1, 3, "#86c895"),
        (10, 14, 11, 1, "#3f8f58"), (10, 17, 12, 1, "#3f8f58"), (10, 20, 9, 1, "#3f8f58"),
        (10, 23, 6, 1, "#3f8f58"), (20, 23, 1, 1, "#d6ecd0"),
    ]
    GLOW = ["#2a2a1e", "#2f3523", "#334028", "#36492c", "#384f2f"]  # paper -> dim green

    def __init__(self, app, scale=5):
        super().__init__(app, bg=PAPER, highlightthickness=0)
        self.app, self.started, self.step = app, time.monotonic(), 0
        self.place(x=0, y=0, relwidth=1, relheight=1)
        self.glow = [self.create_rectangle(0, 0, 0, 0, outline="", fill=PAPER)
                     for _ in range(3)]
        self.icon = [self.create_rectangle(x * scale, y * scale, (x + w) * scale,
                                           (y + h) * scale, outline="", fill=c)
                     for x, y, w, h, c in self.PIXELS]
        self.scale = scale
        self.bind("<Configure>", self._centre)
        self._pulse()

    def _centre(self, e):
        s = self.scale
        dx, dy = e.width // 2 - 16 * s, e.height // 2 - 17 * s
        for item, (x, y, w, h, _) in zip(self.icon, self.PIXELS):
            self.coords(item, dx + x * s, dy + y * s, dx + (x + w) * s, dy + (y + h) * s)
        for i, item in enumerate(self.glow):  # three soft layers, widest first
            pad = (3 - i) * 4
            self.coords(item, dx + 6 * s - pad, dy + 5 * s - pad, dx + 26 * s + pad,
                        dy + 29 * s + pad)

    def _pulse(self):
        if not self.winfo_exists():
            return
        n = len(self.GLOW) - 1
        level = abs(self.step % (2 * n) - n)  # up and down
        for i, item in enumerate(self.glow):
            self.itemconfigure(item, fill=self.GLOW[max(level - (2 - i), 0)])
        self.step += 1
        self.after(90, self._pulse)

    def finish(self):
        """Gone once the page is ready, but shown for at least half a second so it never
        just flickers."""
        wait = int((0.5 - (time.monotonic() - self.started)) * 1000)
        self.after(max(wait, 0), self.destroy)


class Button(tk.Label):
    """A flat paper-style button. main: filled brick red; otherwise outlined."""

    def __init__(self, parent, font, command, main):
        self.main = main
        self.enabled = True
        super().__init__(parent, font=font, padx=16, pady=7, highlightthickness=1)
        self.bind("<Button-1>", lambda e: self.enabled and command())
        self.bind("<Enter>", lambda e: self._paint(hover=True))
        self.bind("<Leave>", lambda e: self._paint())
        self._paint()

    def set(self, text, enabled=True):
        self.enabled = enabled
        self.configure(text=text)
        self._paint()

    def _paint(self, hover=False):
        hover = hover and self.enabled
        if not self.enabled:
            bg, fg, edge = RULE, FADED_INK, RULE
        elif self.main:
            bg, fg, edge = (ACCENT_DARK if hover else ACCENT), PAPER, ACCENT
        else:
            bg, fg, edge = (SIDEBAR if hover else FIELD), ACCENT, ACCENT
        self.configure(bg=bg, fg=fg, highlightbackground=edge, highlightcolor=edge,
                       cursor="hand2" if self.enabled else "arrow")


class TokenWarning(tk.Toplevel):
    """Asks him to agree before Work uses his Claude tokens. .agreed says what he chose."""

    def __init__(self, app, title, total, extra):
        super().__init__(app, bg=PAPER, padx=28, pady=22)
        self.agreed = False
        self.title("This uses your tokens")
        self.transient(app)
        self.resizable(False, False)

        tk.Label(self, text="⚠  This will use your Claude tokens", font=app.f_side_picked,
                 bg=PAPER, fg=ACCENT, anchor="w").pack(fill="x")
        tk.Label(self, text=f"{title}'s Claude will start working on the {total} item"
                            f"{'s' * (total != 1)} you ticked for Work{extra}. It keeps going "
                            "until they are done or you stop it, using your tokens as it "
                            "works. If no Claude chat is open for it, a new terminal opens.",
                 font=app.f_todo, bg=PAPER, fg=INK, justify="left", wraplength=420,
                 anchor="w").pack(fill="x", pady=(10, 18))

        row = tk.Frame(self, bg=PAPER)
        row.pack(fill="x")
        agree = Button(row, app.f_button, self._agree, main=True)
        agree.set("I agree, start work")
        agree.pack(side="right")
        cancel = Button(row, app.f_button, self.destroy, main=False)
        cancel.set("Cancel")
        cancel.pack(side="right", padx=(0, 10))

        self.bind("<Escape>", lambda e: self.destroy())
        self.update_idletasks()
        x = app.winfo_rootx() + (app.winfo_width() - self.winfo_width()) // 2
        y = app.winfo_rooty() + (app.winfo_height() - self.winfo_height()) // 3
        self.geometry(f"+{max(x, 0)}+{max(y, 0)}")
        self.wait_visibility()
        self.grab_set()
        cancel.focus_set()
        app.wait_window(self)

    def _agree(self):
        self.agreed = True
        self.destroy()


if __name__ == "__main__":
    if "--collect-usage" in sys.argv:
        # Run as root (by Claude at the end of a Work batch): learn from Claude's chats
        sender.save_usage(sender.collect_usage())
        print(f"VibeNote: token use saved to {sender.USAGE}")
    else:
        VibeNote().mainloop()
