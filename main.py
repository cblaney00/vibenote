"""VibeNote: notes for each of his projects, on warm paper, sent to that project's Claude in batches.

Writing and sorting notes never needs Claude; only the Send button talks to it.
"""

import os
import subprocess
from datetime import date
import threading
import tkinter as tk
from tkinter import font as tkfont
from tkinter import messagebox

import projects
import sender
from store import Store

# Warm paper colours
PAPER = "#f6eedb"
SIDEBAR = "#ebdfc3"
SIDEBAR_PICKED = "#dccba3"
INK = "#3b2f22"
FADED_INK = "#a3937a"
RULE = "#e2d4b4"
ACCENT = "#b5552f"  # brick red, like a margin line
ACCENT_DARK = "#8f3f20"
FIELD = "#fffaf0"

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
        self.f_small = tkfont.Font(family=SERIF, size=11, slant="italic")
        self.f_button = tkfont.Font(family=SERIF, size=13, weight="bold")

        self._build_sidebar()
        self._build_page()
        self.sync()
        self._sort()
        waiting = [p for p in self.projects if self.store.get(p.slug)]
        self.current = (waiting or self.projects or [None])[0]
        self.refresh()
        self.after(10_000, self._reread_todo)
        self.after(200, self._float)

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

        self.list_box = tk.Frame(side, bg=SIDEBAR)
        self.list_box.pack(fill="both", expand=True)

    def _build_page(self):
        page = tk.Frame(self, bg=PAPER)
        page.pack(side="left", fill="both", expand=True)

        # Red margin line down the left of the page, like notebook paper
        tk.Frame(page, bg=ACCENT, width=2).pack(side="left", fill="y", padx=(36, 0))

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

        # The bottom bar: what happened, and the Send button
        bottom = tk.Frame(body, bg=PAPER)
        bottom.pack(side="bottom", fill="x", pady=(10, 0))
        self.send_btn = tk.Label(bottom, font=self.f_button, bg=ACCENT, fg=FIELD,
                                 padx=16, pady=8, cursor="hand2")
        self.send_btn.pack(side="right")
        self.send_btn.bind("<Button-1>", lambda e: self.send())
        self.send_btn.bind("<Enter>", lambda e: self.send_btn.configure(bg=ACCENT_DARK))
        self.send_btn.bind("<Leave>", lambda e: self.send_btn.configure(bg=ACCENT))
        self.status = tk.Label(bottom, font=self.f_small, bg=PAPER, fg=FADED_INK, anchor="w",
                               justify="left")
        self.status.pack(side="left", fill="x", expand=True)

        # Scrolling area for the notes and the project's to-do list
        holder = tk.Frame(body, bg=PAPER)
        holder.pack(fill="both", expand=True)
        self.canvas = tk.Canvas(holder, bg=PAPER, highlightthickness=0, yscrollincrement=24)
        self.canvas.pack(side="left", fill="both", expand=True)
        self.notes_frame = tk.Frame(self.canvas, bg=PAPER)
        self._win = self.canvas.create_window(0, 0, window=self.notes_frame, anchor="nw")
        self.notes_frame.bind("<Configure>", lambda e: self.canvas.configure(
            scrollregion=self.canvas.bbox("all")))
        self.canvas.bind("<Configure>", lambda e: self.canvas.itemconfigure(
            self._win, width=e.width))
        self.bind_all("<Button-4>", lambda e: self._scroll(-1))
        self.bind_all("<Button-5>", lambda e: self._scroll(1))
        self.bind_all("<MouseWheel>", lambda e: self._scroll(-1 if e.delta > 0 else 1))

    def _scroll(self, steps):
        if self.notes_frame.winfo_height() > self.canvas.winfo_height():
            self.canvas.yview_scroll(steps * 3, "units")

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
        for w in self.notes_frame.winfo_children():
            w.destroy()
        p = self.current
        if p is None:
            self.title_label.configure(text="No projects yet")
            self.count_label.configure(text="Start one with vibe, and it shows up here")
            self.send_btn.pack_forget()
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
        for note in notes:
            self._draw_note(note)

        if sent:
            self._heading(f"Sent: on its to-do list, waiting for Claude ({len(sent)})")
            for note in sent:
                self._draw_history(note)
        if done:
            self._heading(f"Done ({len(done)})")
            for note in done:
                self._draw_history(note)

        if self.sending is None:
            n = len(notes)
            self.send_btn.configure(text=f"Send {n} note{'s' * (n != 1)} to Claude  →"
                                    if n else "Send to Claude  →")
            self.send_btn.configure(bg=ACCENT if n else RULE, fg=FIELD if n else FADED_INK,
                                    cursor="hand2" if n else "arrow")
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
        text.pack(side="left", fill="x", expand=True)
        text.bind("<Configure>", lambda e: text.configure(wraplength=max(e.width - 12, 50)))

        remove = tk.Label(line, text="×", font=self.f_note, bg=PAPER, fg=PAPER, cursor="hand2")
        remove.pack(side="right", padx=(8, 4), anchor="n")
        move = tk.Label(line, text="Move", font=self.f_small, bg=PAPER, fg=PAPER, cursor="hand2")
        move.pack(side="right", padx=(8, 0), anchor="n", pady=(3, 0))

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

    def _heading(self, text):
        tk.Label(self.notes_frame, text=text, font=self.f_head, bg=PAPER, fg=FADED_INK,
                 anchor="w").pack(fill="x", pady=(26, 4))

    def _draw_history(self, note):
        done = note["status"] == "done"
        line = tk.Frame(self.notes_frame, bg=PAPER)
        line.pack(fill="x", pady=2)
        tk.Label(line, text="☑" if done else "☐", font=self.f_todo, bg=PAPER,
                 fg=ACCENT if done else FADED_INK).pack(side="left", padx=(2, 8), anchor="n")
        when = note.get("done") if done else note.get("sent")
        if when:
            tk.Label(line, text=nice_date(when), font=self.f_small, bg=PAPER,
                     fg=FADED_INK).pack(side="right", padx=(10, 4), anchor="n")
        text = tk.Label(line, text=note["text"], font=self.f_todo, bg=PAPER, fg=FADED_INK,
                        anchor="w", justify="left")
        text.pack(side="left", fill="x", expand=True)
        text.bind("<Configure>", lambda e: text.configure(wraplength=max(e.width - 12, 50)))

    def sync(self):
        """Bring the history in line with every project's to-do list. Returns whether it changed."""
        changed = False
        for p in self.projects:
            done = p.done_items() if p.slug not in self.store.imported else []
            changed |= self.store.sync(p.slug, p.todo_items(), done)
        return changed

    def _reread_todo(self):
        """Claude ticks things off the to-do lists while he works; keep up with it."""
        f = self.focus_get()
        editing = isinstance(f, tk.Entry) and f is not self.entry
        if not editing and self.sending is None and self.sync():
            self.refresh(keep_scroll=True)
        self.after(10_000, self._reread_todo)

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

    def send(self):
        p = self.current
        notes = self.store.get(p.slug) if p else []
        if not notes or self.sending is not None:
            return
        n = len(notes)
        if not messagebox.askyesno(
                "Send to Claude",
                f"Send {n} note{'s' * (n != 1)} to {p.title}'s Claude?\n\n"
                "They go on the bottom of its to-do list, and Claude starts on them. "
                "If no Claude is open for it, a new terminal opens.", parent=self):
            return
        texts = [note["text"] for note in notes]
        self.sending = "…"
        self.send_btn.configure(text="Sending…", bg=RULE, fg=FADED_INK)
        self.say("")

        def work():
            try:
                self.sending = ("ok", sender.send(p, texts))
            except OSError as err:
                self.sending = ("fail", f"Couldn't send: {err.strerror or err}")

        threading.Thread(target=work, daemon=True).start()
        self._wait_for_send(p, [note["id"] for note in notes])

    def _wait_for_send(self, project, ids):
        if self.sending == "…":
            self.after(150, self._wait_for_send, project, ids)
            return
        how, msg = self.sending
        self.sending = None
        if how == "ok":
            self.store.mark_sent(project.slug, ids)
            self.say(f"✓ {msg}", ACCENT)
        else:
            self.say(msg + " Your notes are still here.", ACCENT)
        self.refresh(keep_scroll=True)


if __name__ == "__main__":
    VibeNote().mainloop()
