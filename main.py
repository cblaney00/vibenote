"""VibeNote: notes for each of his projects, on warm paper, sent to that project's Claude in batches.

Writing and sorting notes never needs Claude; only the Send button talks to it.
"""

import json
import os
from pathlib import Path
import sys
import subprocess
from datetime import date, datetime
import threading
import time
import tkinter as tk
from tkinter import font as tkfont

import projects
import sender
from store import Store, condense, group_notes, size_label, size_score, tokens_in

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
GLYPHS = "DejaVu Sans"      # has the grip (⠿) and flags (⚑ ⚐) Georgia lacks
WIDE, TALL = 1120, 780      # opening size (his ask, 2026-11-06: "make the app window bigger")


def nice_date(iso):
    """"2026-10-30" -> "30 Oct"."""
    try:
        return date.fromisoformat(iso).strftime("%-d %b")
    except ValueError:
        return iso


# Pop-ups carry VibeNote's window class: a bare Tk pop-up is "Toplevel", which his desktop
# couldn't place and showed as another app (Your Only Move Is HUSTLE, 2026-11-02)
POPUP_CLASS = "Vibenote"


class VibeNote(tk.Tk):
    def __init__(self, lando=False, view=None):
        super().__init__(className="vibenote")
        # Lando mode (his ask, 2026-11-09): Lando talks to Claude himself, so no Work
        self.lando = lando
        self.title("VibeNote")
        self.geometry(f"{WIDE}x{TALL}")
        self.minsize(760, 520)
        self.configure(bg=PAPER)

        self.store = Store()
        self.guess = sender.TokenGuess(self._read_usage())
        self.projects = projects.find_projects()
        waiting = [p for p in self.projects if self.store.get(p.slug)]
        self.current = (waiting or self.projects)[0] if self.projects else None
        self.sending = None  # the message from a send running in the background

        self.f_brand = tkfont.Font(family=SERIF, size=22, weight="bold", slant="italic")
        # Small text a bit bigger and upright (his pick, 2026-11-02: "less cluttery small text")
        self.f_head = tkfont.Font(family=SERIF, size=12)
        self.f_side = tkfont.Font(family=SERIF, size=15)
        self.f_side_picked = tkfont.Font(family=SERIF, size=15, weight="bold")
        self.f_title = tkfont.Font(family=SERIF, size=26, weight="bold")
        self.f_note = tkfont.Font(family=SERIF, size=15)
        self.f_todo = tkfont.Font(family=SERIF, size=14)
        self.f_box = tkfont.Font(family=GLYPHS, size=16)
        # Tick columns sized from the text itself: his screen draws text ~1/3 bigger than
        # a plain one, and fixed pixel sizes cut the ticks off there
        self.tick_w = max(self.f_head.measure("Work"), self.f_box.measure("☑")) + 20
        self.tick_h = self.f_box.metrics("linespace") + 4
        self.head_h = self.f_head.metrics("linespace") + 4
        self.f_small = tkfont.Font(family=SERIF, size=13)
        self.f_button = tkfont.Font(family=SERIF, size=14, weight="bold")
        self.f_section = tkfont.Font(family=SERIF, size=11, weight="bold")
        self.f_glyph = tkfont.Font(family=GLYPHS, size=13)
        self.side_w = 280

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
        self._show_live()
        self.after(10_000, self._reread_todo)
        self.after(1500, self._relearn)
        self._ahead_job = self.after(700, self._build_ahead)
        self.after(200, self._float)
        self._size = None
        self._redraw_soon = None
        # Only the window itself: a plain bind here also fires for every widget inside it,
        # tens of thousands of times while the page is first laid out
        self.bindtags(("vibenote-window",) + self.bindtags())
        self.bind_class("vibenote-window", "<Configure>", self._resized)
        self._rewrap_all()  # notes wrapped before the notepad goes
        loading.finish()
        if view == "usage":  # opened from the mini player (Lando mode)
            self.show("usage")
        elif view == "tips":
            self.show_tips()

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
        self._fit_sidebar()
        self.canvas.itemconfigure(self._win, state="hidden")
        self.update_idletasks()
        self.canvas.itemconfigure(self._win, state="normal")

    # --- the window floats freely (his pick) ------------------------------

    def _float(self):
        """On his desktop (Hyprland) windows snap into tiles; ask for this one to float instead."""
        if not os.environ.get("HYPRLAND_INSTANCE_SIGNATURE"):
            return
        me = f"pid:{os.getpid()}"
        for args in (["setfloating", me], ["resizewindowpixel", f"exact {WIDE} {TALL},{me}"],
                     ["centerwindow"]):
            try:
                subprocess.run(["hyprctl", "dispatch", *args], capture_output=True, timeout=3)
            except (OSError, subprocess.SubprocessError):
                return

    # --- layout -----------------------------------------------------------

    def _build_sidebar(self):
        side = tk.Frame(self, bg=SIDEBAR, width=self.side_w)
        side.pack(side="left", fill="y")
        side.pack_propagate(False)
        self.side = side
        self.margin_line = self.body = None  # made with the page, just after

        tk.Label(side, text="VibeNote", font=self.f_brand, bg=SIDEBAR, fg=ACCENT,
                 anchor="w").pack(fill="x", padx=20, pady=(20, 14))

        # "Is now a good time for Claude?" (his ask, 2026-11-01) and the live usage bars
        # (his ask, 2026-11-06: "a live usage bar from claude /usage"), at the bottom
        sign = tk.Frame(side, bg=SIDEBAR)
        sign.pack(side="bottom", fill="x", padx=20, pady=(0, 16))
        tk.Frame(side, bg=RULE, height=1).pack(side="bottom", fill="x", padx=20, pady=(0, 16))
        self.sign_title = tk.Label(sign, font=self.f_side, bg=SIDEBAR, anchor="w",
                                   justify="left")
        self.sign_title.pack(fill="x")
        self.sign_why = tk.Label(sign, font=self.f_small, bg=SIDEBAR, fg=FADED_INK, anchor="w",
                                 justify="left")
        self.sign_why.pack(fill="x")
        self.live_box = tk.Frame(sign, bg=SIDEBAR)
        self.live_box.pack(fill="x", pady=(10, 0))
        links = tk.Frame(sign, bg=SIDEBAR)
        links.pack(anchor="w", pady=(2, 0))
        self.sign_more = SmallButton(links, self.f_small, lambda: self.show("usage"), ACCENT,
                                     "Claude usage ›")
        self.sign_more.pack(side="left")
        SmallButton(links, self.f_small, self.show_tips, ACCENT, "Tips ›").pack(
            side="left", padx=(8, 0))
        for w in (sign, self.sign_title, self.sign_why):
            w.configure(cursor="hand2")
            w.bind("<Button-1>", lambda e: self.show("usage"))

        # The projects, in a list that scrolls when they don't all fit, so the sign and the
        # usage bars below always show
        self.side_canvas = tk.Canvas(side, bg=SIDEBAR, highlightthickness=0,
                                     yscrollincrement=6)
        self.side_canvas.pack(fill="both", expand=True, pady=(0, 8))
        self.list_box = tk.Frame(self.side_canvas, bg=SIDEBAR)
        self._side_win = self.side_canvas.create_window(0, 0, window=self.list_box, anchor="nw")
        self.list_box.bind("<Configure>", lambda e: self.side_canvas.configure(
            scrollregion=self.side_canvas.bbox("all")))
        self.side_canvas.bind("<Configure>", lambda e: self.side_canvas.itemconfigure(
            self._side_win, width=e.width))
        self._fit_sidebar(force=True)

    def _fit_sidebar(self, force=False):
        """The sidebar takes about a quarter of the window, between 220 and 310 px, and the
        page's margins narrow too, so a small window still has room for the notes."""
        wide = self.winfo_width()
        width = max(220, min(310, int(wide * 0.27))) if not force else self.side_w
        roomy = force or wide - width > 720
        if self.body is not None:
            self.margin_line.pack_configure(padx=(36 if roomy else 14, 0))
            self.body.pack_configure(padx=(32, 44) if roomy else (18, 18))
        if width == self.side_w and not force:
            return
        self.side_w = width
        self.side.configure(width=width)
        for label in (self.sign_title, self.sign_why):
            label.configure(wraplength=width - 40)
        self.sign_more.set("Claude usage ›" if width >= 250 else "Usage ›")  # Tips still fits
        if not force:
            self._show_live()
            self._draw_sidebar()

    def _show_live(self):
        """The two bars Claude's /usage shows: this 5-hour window and this week. Re-read
        every 30 s (the Glade's Claude hook refreshes the file after Claude's replies)."""
        if getattr(self, "_live_job", None):
            self.after_cancel(self._live_job)
        self._live_job = self.after(30_000, self._show_live)
        # Lando's VibeNote fetches his numbers itself (next time's bars)
        threading.Thread(target=sender.refresh_own_usage, daemon=True).start()
        for w in self.live_box.winfo_children():
            w.destroy()
        draw_live(self.live_box, self.f_small, self.f_section, self.side_w - 40, SIDEBAR)

    @staticmethod
    def _live_colour(pct):
        return live_colour(pct)

    def _build_page(self):
        page = tk.Frame(self, bg=PAPER)
        page.pack(side="left", fill="both", expand=True)

        # Red margin line down the left of the page, like notebook paper
        self.margin_line = tk.Frame(page, bg=MARGIN, width=2)
        self.margin_line.pack(side="left", fill="y", padx=(36, 0))

        body = tk.Frame(page, bg=PAPER)
        self.body = body
        body.pack(side="left", fill="both", expand=True, padx=(32, 44), pady=(26, 18))

        self.title_label = tk.Label(body, font=self.f_title, bg=PAPER, fg=INK, anchor="w")
        self.title_label.pack(fill="x")
        count_row = tk.Frame(body, bg=PAPER)
        count_row.pack(fill="x", pady=(2, 18))
        self.count_label = tk.Label(count_row, font=self.f_small, bg=PAPER, fg=FADED_INK,
                                    anchor="w")
        self.count_label.pack(side="left")
        # "Summary" on a project page, "← Back" on the others
        self.page_link = SmallButton(count_row, self.f_small, self._page_link, ACCENT)
        self.page_link.pack(side="left", padx=(14, 0))
        self.view = None  # None: the project's notes; else "usage", "find" or "summary"
        self.later_open = False  # the Later box starts folded (his pick, 2026-11-02)

        # Box for finding notes in every project (Ctrl+F, his ask), shown instead of the
        # note box while finding
        self.find_row = tk.Frame(body, bg=FIELD, highlightthickness=1, highlightbackground=ACCENT)
        self.find_entry = tk.Entry(self.find_row, font=self.f_note, bg=FIELD, fg=INK,
                                   insertbackground=INK, relief="flat", highlightthickness=0)
        self.find_entry.pack(fill="x", ipady=8, padx=10)
        self.find_entry.bind("<KeyRelease>", lambda e: e.keysym != "Escape" and self._draw_page())
        self.find_entry.bind("<Escape>", lambda e: self.show(None))
        self.bind_all("<Control-f>", lambda e: self.show("find"))
        self.bind_all("<Control-F>", lambda e: self.show("find"))

        # Box for typing a new note
        entry_row = tk.Frame(body, bg=FIELD, highlightthickness=1, highlightbackground=RULE)
        entry_row.pack(fill="x", pady=(0, 14))
        self.entry_row = entry_row
        # It grows as the note wraps, so a long one shows in full (his ask, 2026-11-09)
        self.entry = tk.Text(entry_row, font=self.f_note, bg=FIELD, fg=INK, height=1,
                             wrap="word", insertbackground=INK, relief="flat",
                             highlightthickness=0, padx=0, pady=10)
        self.entry.pack(fill="x", padx=12)
        self._growing(self.entry)
        self.entry.bind("<Return>", lambda e: self.add_note() or "break")
        self._placeholder = "Write a note and press Enter…"
        self._show_placeholder()
        self.entry.bind("<FocusIn>", lambda e: self._hide_placeholder())
        self.entry.bind("<FocusOut>", lambda e: self._show_placeholder())

        # The bottom bar: what happened, Send (onto the to-do list, no tokens) and Work
        # (Claude starts on the list, uses tokens: he has to agree first)
        bottom = tk.Frame(body, bg=PAPER)
        bottom.pack(side="bottom", fill="x", pady=(10, 0))
        self.bottom = bottom
        self.work_btn = Button(bottom, self.f_button, self.work, main=True)
        if not self.lando:
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
        self.holder = holder
        self.canvas = tk.Canvas(holder, bg=PAPER, highlightthickness=0, yscrollincrement=6)
        self.canvas.pack(side="left", fill="both", expand=True)
        # Each project's page is kept once built, so switching back to it is instant
        # (2026-11-06: "laggy when switching between projects"); the others' pages share one
        self._pages = {}  # project -> (frame, what it showed, its notes to wrap)
        self._snap_for = None  # the note whose snapshot is showing
        self._other_page = self.notes_frame = self._new_page()
        self._win = self.canvas.create_window(0, 0, window=self.notes_frame, anchor="nw")
        self._wrapping, self._wrap_guess, self._rewrap_job = [], {}, None

        def canvas_resized(e):
            self.canvas.itemconfigure(self._win, width=e.width)
            self._rewrap_soon()

        self.canvas.bind("<Configure>", canvas_resized)
        self.bind_all("<Button-4>", lambda e: self._scroll(-1))
        self.bind_all("<Button-5>", lambda e: self._scroll(1))
        self.bind_all("<MouseWheel>", lambda e: self._scroll(-1 if e.delta > 0 else 1))

    def _new_page(self):
        frame = tk.Frame(self.canvas, bg=PAPER)
        frame.bind("<Configure>", lambda e: frame is self.notes_frame and self.canvas.configure(
            scrollregion=(0, 0, e.width, e.height)))
        return frame

    def _page_key(self):
        """What a project's page shows: if none of it changed, the kept page is still right."""
        p = self.current
        return (json.dumps(self.store.all(p.slug), sort_keys=True), self.later_open,
                # its token numbers: these change only when the estimate for it does
                self.guess.tokens(1000, datetime.now().astimezone(), p.slug),
                # what worked-on notes really used, which changes as Claude works
                (self.guess.usage or {}).get("updated"))

    def _scroll(self, steps):
        """Smooth scrolling: each turn of the wheel glides 72 px over a few frames."""
        self._hide_snap()
        x, y = self.winfo_pointerxy()
        if self.side_canvas.winfo_containing(x, y) and str(
                self.side_canvas.winfo_containing(x, y)).startswith(str(self.side_canvas)):
            if self.list_box.winfo_height() > self.side_canvas.winfo_height():
                self.side_canvas.yview_scroll(steps * 8, "units")
            return
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
        if not self.entry.get("1.0", "end-1c"):
            self.entry.insert("1.0", self._placeholder)
            self.entry.configure(fg=FADED_INK)

    def _hide_placeholder(self):
        if (self.entry.get("1.0", "end-1c") == self._placeholder
                and self.entry.cget("fg") == FADED_INK):
            self.entry.delete("1.0", "end")
            self.entry.configure(fg=INK)

    def _growing(self, box, most=6):
        """A text box as tall as its wrapped text, up to `most` lines (then it scrolls), so a
        long note shows in full while he types it (his ask, 2026-11-09). Notes are one line:
        pasted line breaks become spaces."""
        def fit(_=None):
            text = box.get("1.0", "end-1c")
            if "\n" in text:
                at = box.index("insert")
                box.delete("1.0", "end")
                box.insert("1.0", " ".join(text.split("\n")))
                box.mark_set("insert", at)
            lines = box.count("1.0", "end-1c", "displaylines") or 0
            lines = (lines[0] if isinstance(lines, tuple) else lines) + 1
            if int(box.cget("height")) != min(lines, most):
                box.configure(height=min(lines, most))
            box.see("insert")

        for seq in ("<KeyRelease>", "<<Paste>>", "<Configure>"):
            box.bind(seq, lambda e: box.after_idle(fit), add="+")
        box.after_idle(fit)

    # --- drawing ----------------------------------------------------------

    def refresh(self, keep_scroll=False):
        """After a change: the sidebar and this page are built afresh (and later, out of
        sight, any other page the change touched)."""
        if self.current:
            self._pages.pop(self.current.slug, None)
        self._draw_sidebar()
        self._draw_page(keep_scroll)
        if getattr(self, "_ahead_job", None):
            self.after_cancel(self._ahead_job)
        if hasattr(self, "_ahead_job"):  # not before the window has finished opening
            self._ahead_job = self.after(700, self._build_ahead)

    def _sort(self):
        """His order (his ask, 2026-11-04: drag them, pin some): pinned on top, then where he
        dragged them; ones not placed yet at the bottom, longest lists first."""
        order = self.store.sidebar_order([p.slug for p in self.projects])
        self.projects.sort(key=lambda p: order.index(p.slug))

    def _draw_sidebar(self):
        """His sidebar (his pick, 2026-11-06): a Pinned box on top, then the rest. Each row
        has a grip to drag it and a flag to click: ⚑ pinned, ⚐ not. Dragging a project into
        or out of the Pinned box pins or unpins it; dragging inside a box orders it."""
        if getattr(self, "_drag", None):
            return  # not while he is dragging a project; the drop draws it again
        for w in self.list_box.winfo_children():
            w.destroy()
        self._sort()
        self._items = []  # (project or None, widget), top to bottom; None: a box's title
        self._row_of = {}  # project -> its row, so picking one only re-colours two rows
        pinned = [p for p in self.projects if p.slug in self.store.pinned]
        rest = [p for p in self.projects if p.slug not in self.store.pinned]
        self._section("PINNED", top=True)
        if not pinned:
            hint = tk.Label(self.list_box, text="Click ⚐ or drag a project here",
                            font=self.f_small, bg=SIDEBAR, fg=FADED_INK, anchor="w")
            hint.pack(fill="x", padx=20, pady=(0, 4))
            self._items.append((None, hint))
        for p in pinned:
            self._project_row(p)
        self._projects_head = self._section("PROJECTS")
        for p in rest:
            self._project_row(p)

    @staticmethod
    def _fit_name(title, font, room):
        """A long name ends in … rather than being cut off at the sidebar's edge."""
        if font.measure(title) <= room:
            return title
        while title and font.measure(title + "…") > room:
            title = title[:-1]
        return title.rstrip() + "…"

    def _mark_picked(self):
        """Light up the open project's row (and dim the last one) without rebuilding the
        sidebar: rebuilding it on every switch was a good part of the lag (2026-11-06)."""
        picked = self.current.slug if self.current and self.view is None else None
        for slug, row in getattr(self, "_row_of", {}).items():
            if not row.winfo_exists():
                continue
            bg = SIDEBAR_PICKED if slug == picked else SIDEBAR
            if row.cget("bg") == bg:
                continue
            row.configure(bg=bg)
            for w in row.winfo_children():
                w.configure(bg=bg)
                if w.cget("anchor") == "w":  # the name
                    w.configure(font=self.f_side_picked if slug == picked else self.f_side)

    def _section(self, text, top=False):
        head = tk.Label(self.list_box, text=text, font=self.f_section, bg=SIDEBAR,
                        fg=FADED_INK, anchor="w")
        head.pack(fill="x", padx=20, pady=(0 if top else 16, 4))
        self._items.append((None, head))
        return head

    def _project_row(self, p):
        picked = p is self.current and self.view is None
        waiting = len(self.store.get(p.slug))
        is_pinned = p.slug in self.store.pinned
        bg = SIDEBAR_PICKED if picked else SIDEBAR
        row = tk.Frame(self.list_box, bg=bg, cursor="hand2")
        row.pack(fill="x", padx=6)
        self._row_of[p.slug] = row
        grip = tk.Label(row, text="⠿", font=self.f_glyph, bg=bg, fg=RULE, cursor="fleur")
        grip.pack(side="left", padx=(4, 4))
        pin = tk.Label(row, text="⚑" if is_pinned else "⚐", font=self.f_glyph, bg=bg,
                       fg=ACCENT if is_pinned else RULE, cursor="hand2")
        pin.pack(side="right", padx=(2, 8))
        num = tk.Label(row, text=str(waiting) if waiting else "", bg=bg, fg=ACCENT,
                       font=self.f_side_picked)
        num.pack(side="right", padx=(4, 4))
        font = self.f_side_picked if picked else self.f_side
        room = self.side_w - 12 - 2 * self.f_glyph.measure("⚑") - 30 - font.measure("88")
        name = tk.Label(row, text=self._fit_name(p.title, font, room), bg=bg, fg=INK,
                        anchor="w", font=font)
        name.pack(side="left", fill="x", expand=True, pady=3)  # thin rows (his pick, 2026-11-06)
        for w in (row, grip, name, num):
            w.bind("<ButtonPress-1>", lambda e, proj=p, r=row: self._drag_start(e, proj, r))
            w.bind("<B1-Motion>", self._drag_move)
            w.bind("<ButtonRelease-1>", self._drag_end)
        for w in (row, grip, name, num, pin):
            w.bind("<Button-3>", lambda e, proj=p: self._project_menu(proj, e))
            # under the mouse the grip and an empty flag light up, so he can see they work
            w.bind("<Enter>", lambda e, g=grip, f=pin, on=is_pinned: (
                g.configure(fg=FADED_INK), on or f.configure(fg=FADED_INK)), add="+")
            w.bind("<Leave>", lambda e, g=grip, f=pin, on=is_pinned: (
                g.configure(fg=RULE), on or f.configure(fg=RULE)), add="+")
        pin.bind("<Button-1>", lambda e, proj=p: self._pin(proj))
        self._items.append((p, row))

    # Dragging a project (his ask, 2026-11-04; into and out of Pinned, 2026-11-06). The row
    # follows the mouse by being packed into its new place as it passes each neighbour; only
    # a drop saves. A plain click (no real move) still picks the project.
    def _drag_start(self, event, project, row):
        self._drag = {"p": project, "row": row, "y": event.y_root, "moved": False}

    def _drag_move(self, event):
        d = getattr(self, "_drag", None)
        if not d:
            return
        if not d["moved"]:
            if abs(event.y_root - d["y"]) < 6:
                return
            d["moved"] = True
            self.list_box.configure(cursor="fleur")
            for w in (d["row"], *d["row"].winfo_children()):
                w.configure(bg=RULE)
        y = event.y_root - self.list_box.winfo_rooty()
        others = [(p, w) for p, w in self._items if w is not d["row"]]
        # the first thing below the mouse; never above the Pinned title
        at = next((i for i, (p, w) in enumerate(others)
                   if y < w.winfo_y() + w.winfo_height() / 2), len(others))
        at = max(at, 1)
        now = self._items.index((d["p"], d["row"]))
        if at == now:
            return
        self._items = others[:at] + [(d["p"], d["row"])] + others[at:]
        if at < len(others):
            d["row"].pack_configure(before=others[at][1])
        else:
            d["row"].pack_configure(after=others[-1][1])

    def _drag_end(self, event):
        d, self._drag = getattr(self, "_drag", None), None
        if not d:
            return
        if not d["moved"]:
            self.pick(d["p"])
            return
        self.list_box.configure(cursor="")
        cut = next(i for i, (p, w) in enumerate(self._items) if w is self._projects_head)
        order = [p.slug for p, w in self._items if p]
        pinned = [p.slug for p, w in self._items[:cut] if p]
        self.store.set_order(order, pinned)
        self.refresh(keep_scroll=True)  # also catches up on anything held back while dragging

    def _project_menu(self, project, event):
        menu = tk.Menu(self, tearoff=0, bg=FIELD, fg=INK, activebackground=SIDEBAR_PICKED,
                       activeforeground=INK, font=self.f_side, relief="flat")
        pinned = project.slug in self.store.pinned
        menu.add_command(label="Unpin" if pinned else "Pin to the top",
                         command=lambda: self._pin(project))
        menu.tk_popup(event.x_root, event.y_root)

    def _pin(self, project):
        self.store.toggle_pin(project.slug, [p.slug for p in self.projects])
        self._draw_sidebar()

    def show(self, view):
        """Switch the main area: None (the project's notes), "usage", "find", "summary"."""
        same = getattr(self, "_shown", "unset") == view
        self.view = self._shown = view
        on_notes = view is None
        if not same:  # re-packing these each time made the page jump on every switch
            self.find_row.pack_forget()
            self.entry_row.pack_forget()
            self.bottom.pack_forget()
            self.holder.pack_forget()
            if view == "find":
                self.find_row.pack(fill="x", pady=(0, 10))
            if on_notes:
                self.entry_row.pack(fill="x", pady=(0, 14))
                self.bottom.pack(side="bottom", fill="x", pady=(10, 0))
            self.holder.pack(fill="both", expand=True)
        self.say("")
        self._mark_picked()
        self._draw_page()
        if view == "find":
            self.find_entry.focus_set()
            self.find_entry.select_range(0, "end")
        return "break"

    def _page_link(self):
        if self.view is None:
            self.show("summary")
        else:
            self.show(None)

    def _draw_page(self, keep_scroll=False):
        """Build the page out of sight and show it once its notes are wrapped: drawn in the
        open, it showed half-built and then the notes jumped as they re-wrapped (2026-11-06)."""
        slug = self.current.slug if self.current and self.view is None else None
        key = self._page_key() if slug else None
        kept = self._pages.get(slug)
        if kept and kept[1] == key:  # nothing on it changed: show it as it was
            self._show_page(kept[0])
            self._wrapping = kept[2]
            self._rewrap_all()  # in case the window changed width since
            self._fill_page(keep_scroll, body=False)
            if not keep_scroll:
                self.canvas.yview_moveto(0)
            return
        frame = kept[0] if kept else self._new_page() if slug else self._other_page
        self.canvas.itemconfigure(self._win, state="hidden")
        self._show_page(frame)
        try:
            self._fill_page(keep_scroll)
        finally:
            if self._rewrap_job:
                self.after_cancel(self._rewrap_job)
            self._rewrap_all()
            self.canvas.itemconfigure(self._win, state="normal")
            if slug:
                self._pages[slug] = (frame, key, self._wrapping)

    def _build_ahead(self):
        """Build the other projects' pages out of sight, one at a time, so even the first
        switch to one is instant. Waits while he is dragging or Claude is being started."""
        self._ahead_job = None
        if getattr(self, "_drag", None) or self.sending is not None or self.view is not None:
            self._ahead_job = self.after(1000, self._build_ahead)
            return
        here, page, wrapping = self.current, self.notes_frame, self._wrapping
        for p in self.projects:
            if p is here:
                continue
            self.current = p
            kept = self._pages.get(p.slug)
            fresh = kept and kept[1] == self._page_key()
            self.current = here
            if fresh:
                continue
            self.current = p
            self.notes_frame = kept[0] if kept else self._new_page()
            try:
                self._fill_page(keep_scroll=True)  # never scroll the page he is on
                self._rewrap_all()
                self._pages[p.slug] = (self.notes_frame, self._page_key(), self._wrapping)
            finally:
                self.current, self.notes_frame, self._wrapping = here, page, wrapping
                # the title, counts and buttons belong to the page he is looking at
                self._fill_page(keep_scroll=True, body=False)
            self._ahead_job = self.after(60, self._build_ahead)  # the next after a breath
            return

    def _show_page(self, frame):
        self._hide_snap()
        if frame is not self.notes_frame:
            self.notes_frame = frame
            self.canvas.itemconfigure(self._win, window=frame)
        self.canvas.configure(scrollregion=(0, 0, frame.winfo_reqwidth(),
                                            frame.winfo_reqheight()))

    def _fill_page(self, keep_scroll=False, body=True):
        """The page's title and counts, then (body) its notes."""
        if body:
            self._wrapping = []
            for w in self.notes_frame.winfo_children():
                w.destroy()
        back = f"← Back to {self.current.title}" if self.current else "← Back"
        if self.view:
            self.page_link.set(back)
            {"usage": self._draw_usage, "find": self._draw_find,
             "summary": self._draw_summary}[self.view]()
            if not keep_scroll:
                self.canvas.yview_moveto(0)
            return
        self.page_link.set("Summary ›" if self.current else "")
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
        later = self.store.get(p.slug, "later")
        review = self.store.get(p.slug, "review")
        review.sort(key=lambda n: n.get("review", ""), reverse=True)
        # Newest first: finished since VibeNote started watching, then the imported ones
        # in the order the to-do file had them (its newest are at the top)
        done = sorted((n for n in done if n.get("done")), key=lambda n: n["done"],
                      reverse=True) + [n for n in done if not n.get("done")]
        self.title_label.configure(text=p.title)
        self.count_label.configure(
            text=f"{len(notes)} waiting · {len(sent)} sent · "
                 + (f"{len(review)} with Lando · " if review else "") + f"{len(done)} done"
                 + (f" · {len(later)} later" if later else ""))
        if not body:
            self._update_buttons()
            return

        if notes or sent:
            self._tick_all_row(notes, sent)
        if not notes:
            tk.Label(self.notes_frame, text="No notes waiting. Write one above.",
                     font=self.f_small, bg=PAPER, fg=FADED_INK, anchor="w").pack(fill="x", pady=6)
        else:
            self._heading(f"Waiting to send ({len(notes)}) · {self._total(notes)}", notes,
                          send=True, top=True)
        group, totals = None, self._group_totals(notes)
        for note in notes:
            group = self._group_heading(note, group, totals)
            self._draw_note(note)

        # Sent, split (his ask, 2026-11-04): not started yet, and ones Claude has been on that
        # he hasn't signed off
        for title, part in (("Sent: on its to-do list", [n for n in sent if not n.get("worked")]),
                            ("Worked on, not finished", [n for n in sent if n.get("worked")])):
            if not part:
                continue
            self._heading(f"{title} ({len(part)}) · {self._total(part)}", part, send=False)
            group, totals = None, self._group_totals(part)
            for note in part:
                group = self._group_heading(note, group, totals)
                self._draw_history(note)
        if later:
            self._draw_later(later)
        if review:
            self._heading(f"Up for review by Lando ({len(review)})")
            for note in review:
                self._draw_history(note)
        if done:
            self._heading(f"Done ({len(done)})")
            self._draw_done(done)

        self._update_buttons()
        if not keep_scroll:
            self.canvas.yview_moveto(0)

    # --- the other pages: Claude usage, Find, Summary --------------------------

    def _line(self, text, font=None, fg=INK, pady=(0, 2), padx=0, wrap=True, link=None):
        label = tk.Label(self.notes_frame, text=text, font=font or self.f_todo, bg=PAPER, fg=fg,
                         anchor="w", justify="left")
        label.pack(fill="x", pady=pady, padx=padx)
        if wrap:
            self._wrap(label)
        if link:
            label.configure(cursor="hand2")
            label.bind("<Button-1>", lambda e: link())
        return label

    def _title_of(self, slug):
        if slug == "computer":
            return "Your computer (setup)"
        return next((p.title for p in self.projects if p.slug == slug), slug)

    def _report(self, extra=0):
        return sender.usage_report(self.guess.usage, sender.load_accounts(), extra=extra)

    def _usage_after(self, cost):
        """For the Work warning: what this request does to the account logged in now (his
        ask: "if the session will set me off track")."""
        report = self._report(extra=cost)
        acc = next((a for a in report["accounts"] if a["logged_in"]), None)
        if acc is None:
            return ""
        t = sender.short_tokens
        text = (f"{acc['name']} (logged in now) after this: {t(acc['used'])} used this week. "
                f"At your pace that is {t(acc['projected'])} by its refresh "
                f"({sender.refresh_text(acc)})")
        if acc["limit"]:
            if acc["on_track"]:
                text += f", within the {t(acc['limit'])} it can do. On track."
            else:
                text += (f", more than the {t(acc['limit'])} it can do: off track. Keep to "
                         f"{t(acc['daily_budget'])} a day.")
        else:
            text += "."
        if report["use_now"] and report["use_now"] != acc["name"]:
            text += f" Better to use {report['use_now']} first: its week ends sooner."
        return text

    def _draw_usage(self):
        """Claude usage, broken down, for both accounts (his ask, 2026-11-02)."""
        t = sender.short_tokens
        report = self._report()
        usage = self.guess.usage or {}
        self.title_label.configure(text="Claude usage")
        try:
            updated = datetime.fromisoformat(usage["updated"]).astimezone().strftime("%-d %b %H:%M")
        except (KeyError, ValueError):
            updated = "never"
        self.count_label.configure(text=f"Tokens Claude wrote, from your chats · updated {updated}")
        if not usage:
            self._line("No usage learned yet. It appears after Claude finishes a Work batch.",
                       fg=FADED_INK)
            self._draw_tips(usage)
            return
        logged = next((a for a in report["accounts"] if a["logged_in"]), None)
        if report["use_now"]:
            best = next(a for a in report["accounts"] if a["name"] == report["use_now"])
            why = (f"its week ends sooner ({sender.refresh_text(best)}), and what it doesn't "
                   "use is lost then")
            self._line(f"Use {best['name']} now: {why}.", font=self.f_note, fg=WORK_GREEN,
                       pady=(0, 2))
        if logged:
            self._line(f"Logged in to Claude now: {logged['name']} ({logged['email']})",
                       fg=FADED_INK, pady=(0, 6))
        last5 = usage.get("last5h", 0)
        if report["five_hour"]:
            self._line(f"Last 5 hours: {t(last5)} of the {t(report['five_hour'])} a 5-hour "
                       f"window holds (learned from the {len(usage.get('five_hour_fills', []))} "
                       "times you hit one).", fg=INK, pady=(0, 4))

        for a in report["accounts"]:
            self._heading(f"{a['name']} · {a['email']}" + (" · logged in now" if a["logged_in"]
                                                            else ""))
            left = a["end"] - datetime.now().astimezone()
            d, h = left.days, left.seconds // 3600
            refresh = tk.Frame(self.notes_frame, bg=PAPER)
            refresh.pack(fill="x", pady=(0, 2))
            tk.Label(refresh, text=f"Week refreshes {sender.refresh_text(a)}"
                     + (" (a guess)" if a.get("guess") else "") + f" · in {d} d {h} h",
                     font=self.f_todo, bg=PAPER, fg=FADED_INK).pack(side="left")
            SmallButton(refresh, self.f_small,
                        lambda acc=a, lab=refresh: self._edit_refresh(acc, lab), ACCENT,
                        "Change").pack(side="left", padx=(10, 0))
            self._line(f"Used this week: {t(a['used'])} · your pace: {t(a['pace'])} a day")
            if a["weekly_learned"]:
                limit_text = f"its weekly limit, {t(a['limit'])}"
            elif a["limit"]:
                limit_text = (f"at least {t(a['limit'])}: the most you've used in a week without "
                              "hitting the limit, so the real one is bigger")
            else:
                limit_text = None
            self._line(f"At this pace by the refresh: {t(a['projected'])}")
            if limit_text:
                self._line(f"A week can hold {limit_text}.", fg=FADED_INK)
                state = ("On track" if a["on_track"] else "Off track: you'll run out first")
                self._line(f"{state} · to last the week: {t(a['daily_budget'])} a day for "
                           f"the {max(a['days_left'], 0):.1f} days left",
                           fg=WORK_GREEN if a["on_track"] else ACCENT)
            if a["projects"]:
                parts = sorted(a["projects"].items(), key=lambda kv: -kv[1])
                self._line("By project: " + " · ".join(f"{self._title_of(k)} {t(v)}"
                                                       for k, v in parts), fg=FADED_INK)
            if a["days"]:
                self._line("By day: " + " · ".join(f"{k} {t(v)}" for k, v in a["days"].items()),
                           fg=FADED_INK)
        self._line("Which account was logged in is only known from 2 Nov; before that it "
                   "counts as Account 2. The numbers get better as VibeNote sees more.",
                   font=self.f_small, fg=FADED_INK, pady=(18, 0))
        self._draw_tips(usage)

    def _draw_tips(self, usage):
        """Tips for lighter tokens, at the bottom of the usage page (his pick, 2026-11-04)."""
        self._heading("Tips for lighter tokens · learned from your chats")
        for tip in sender.token_tips(usage, self.guess, self._title_of, direct=self.lando):
            self._line(f"•  {tip}", pady=(0, 6))

    def show_tips(self):
        self.show("usage")
        # after the notes have wrapped, so the bottom is the real bottom
        self.after(150, lambda: self.canvas.yview_moveto(1.0))

    def _edit_refresh(self, acc, label):
        box = tk.Entry(self.notes_frame, font=self.f_todo, bg=FIELD, fg=INK, relief="flat",
                       insertbackground=INK, highlightthickness=1, highlightbackground=RULE,
                       highlightcolor=ACCENT)
        box.insert(0, sender.refresh_text(acc))
        box.pack(after=label, fill="x", pady=(0, 4))
        box.focus_set()
        box.select_range(0, "end")
        self.say("Type the day and time, like \u201cThu 11pm\u201d, and press Enter.")

        def save(_=None):
            when = sender.parse_refresh(box.get())
            if when is None:
                self.say("Couldn't read that; try like \u201cThu 11pm\u201d.", ACCENT)
                return
            accounts = sender.load_accounts()
            for a in accounts:
                if a["email"] == acc["email"]:
                    a.update(when, guess=False)
            sender.save_accounts(accounts)
            self.say(f"✓ {acc['name']} refreshes {sender.refresh_text({**acc, **when})}", ACCENT)
            self.refresh(keep_scroll=True)

        box.bind("<Return>", save)
        box.bind("<Escape>", lambda e: self.refresh(keep_scroll=True))

    def _draw_find(self):
        """Every note in every project with these words (Ctrl+F, his ask)."""
        query = self.find_entry.get().strip().lower()
        self.title_label.configure(text="Find")
        if not query:
            self.count_label.configure(text="Type to find notes in every project · Esc to go back")
            return
        words = query.split()
        hits = []
        for p in self.projects:
            for n in self.store.all(p.slug):
                hay = (n["text"] + " " + sender.snapshot_line(n["snap"]) if n.get("snap")
                       else n["text"]).lower()
                if all(w in hay for w in words):
                    hits.append((p, n))
        self.count_label.configure(text=f"{len(hits)} found · click one to open its project")
        box = tk.Text(self.notes_frame, bg=PAPER, fg=INK, font=self.f_todo, wrap="word",
                      relief="flat", bd=0, highlightthickness=0, height=1, cursor="arrow",
                      spacing3=8)
        box.tag_configure("where", foreground=ACCENT, font=self.f_small)
        box.tag_configure("hit", background=SIDEBAR_PICKED, foreground=INK)
        box.tag_configure("when", foreground=FADED_INK, font=self.f_small)
        mark = {"waiting": "waiting", "sent": "on its list", "done": "done", "later": "in Later",
                "review": "with Lando"}
        for i, (p, n) in enumerate(hits[:200]):
            tag = f"go{i}"
            box.insert("end", f"{p.title} · {mark[n['status']]}\n", ("where", tag))
            start = box.index("end-1c")
            box.insert("end", n["text"], tag)
            for w in words:  # light up the words he looked for
                at = start
                while True:
                    at = box.search(w, at, stopindex="end", nocase=True)
                    if not at:
                        break
                    box.tag_add("hit", at, f"{at}+{len(w)}c")
                    at = f"{at}+{len(w)}c"
            if n.get("snap"):
                box.insert("end", "\n" + sender.snapshot_line(n["snap"]), ("when", tag))
            box.insert("end", "\n")
            box.tag_bind(tag, "<Button-1>", lambda e, proj=p: self.pick(proj))
            box.tag_bind(tag, "<Enter>", lambda e: box.configure(cursor="hand2"))
            box.tag_bind(tag, "<Leave>", lambda e: box.configure(cursor="arrow"))
        box.configure(state="disabled")
        box.bindtags((str(box), "all"))
        box.pack(fill="x")
        self._fit_text(box)

    def _fit_text(self, box):
        def fit(e=None):
            if e is not None and abs(e.width - getattr(box, "_fit_w", 0)) < 4:
                return
            box._fit_w = e.width if e is not None else 0
            lines = box.count("1.0", "end", "displaylines")
            lines = lines[0] if isinstance(lines, tuple) else lines
            if lines and int(box.cget("height")) != lines:
                box.configure(height=lines)
        box.bind("<Configure>", fit)

    def _draw_summary(self):
        """Everything ever noted for this project, condensed (his ask, 2026-11-02): grouped by
        what it is about, each said shorter, and the open ones ready to copy for Claude."""
        p = self.current
        self.title_label.configure(text=f"{p.title}: summary")
        notes = self.store.all(p.slug)
        open_notes = [n for n in notes if n["status"] in ("waiting", "sent")]  # not Later
        mine = " ".join(n["text"] for n in open_notes)
        short = "\n".join(f"- {condense(n['text'])}" for n in open_notes)
        self.count_label.configure(
            text=f"{len(notes)} notes · {len(open_notes)} open · for Claude: "
                 f"~{tokens_in(mine)} → ~{tokens_in(short)} tokens")
        if open_notes:
            copy = Button(self.notes_frame, self.f_button, lambda: self._copy(short), main=False)
            copy.set("Copy the open ones for Claude")
            copy.pack(anchor="w", pady=(0, 6))
        status = {"waiting": "•", "sent": "→", "done": "✓", "later": "◦", "review": "✓"}
        groups = group_notes([dict(n) for n in notes])
        groups.sort(key=lambda g: (g[0] == "On their own", -len(g[1])))
        box = tk.Text(self.notes_frame, bg=PAPER, fg=INK, font=self.f_todo, wrap="word",
                      relief="flat", bd=0, highlightthickness=0, height=1, cursor="arrow",
                      spacing3=5)
        box.tag_configure("head", foreground=ACCENT, font=self.f_small, spacing1=12)
        box.tag_configure("done", foreground=FADED_INK)
        box.tag_configure("item", lmargin1=8, lmargin2=26)
        for heading, members in groups:
            open_n = sum(m["status"] not in ("done", "review") for m in members)
            box.insert("end", f"{heading} · {len(members)} notes, {open_n} open\n", "head")
            for m in sorted(members, key=lambda m: m["status"] in ("done", "review")):
                tags = ("item", "done") if m["status"] in ("done", "review") else ("item",)
                box.insert("end", f"{status[m['status']]}  {condense(m['text'])}\n", tags)
        box.delete("end-2c")
        box.configure(state="disabled")
        box.bindtags((str(box), "all"))
        box.pack(fill="x")
        self._fit_text(box)

    def _copy(self, text):
        self.clipboard_clear()
        self.clipboard_append(text)
        self.say("✓ Copied: paste it into a Claude chat", ACCENT)

    def _draw_note(self, note):
        row = tk.Frame(self.notes_frame, bg=PAPER)
        row.pack(fill="x")
        line = tk.Frame(row, bg=PAPER)
        line.pack(fill="x", pady=8)

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
        later = tk.Label(line, text="Later", font=self.f_small, bg=PAPER, fg=PAPER,
                         cursor="hand2")
        later.pack(side="right", padx=(8, 0), anchor="n", pady=(3, 0))
        self._size_tag(line, note, pady=(3, 0))
        # The text goes in last, so it gets the room left over and never squeezes the ticks
        text.pack(side="left", fill="x", expand=True)
        self._wrap(text)

        # Ruled line under each note, like lined paper
        tk.Frame(row, bg=RULE, height=1).pack(fill="x")

        self._selectable(text, lambda: self.edit_note(note, line, text))
        remove.bind("<Button-1>", lambda e: self.delete_note(note))
        move.bind("<Button-1>", lambda e: self.move_menu(note, e))
        later.bind("<Button-1>", lambda e: self.later_note(note))
        for w in (row, line, dot, text):
            w.bind("<Button-3>", lambda e: self.move_menu(note, e))

        # The snapshot taken when he wrote it: a faint line, shown while the mouse is over the
        # note (his pick); click it for everything. It floats over the page (_show_snap):
        # pushing the notes below down made hovering jumpy (2026-11-06).
        snap = sender.snapshot_line(note["snap"]) if note.get("snap") else None
        hiding = []

        # "Move", × and the snapshot only show while the mouse is over the note
        def show(_):
            for job in hiding:
                self.after_cancel(job)
            hiding.clear()
            remove.configure(fg=FADED_INK)
            move.configure(fg=FADED_INK)
            later.configure(fg=FADED_INK)
            if snap:
                self._show_snap(row, snap, note, show, hide)

        def hide_now():
            hiding.clear()
            if not row.winfo_exists():
                return
            remove.configure(fg=PAPER)
            move.configure(fg=PAPER)
            later.configure(fg=PAPER)
            if snap and self._snap_for is row:
                self._hide_snap()

        def hide(_):
            # a moment's wait: moving between the parts of a note leaves one and enters
            # another, and the line should not flicker
            hiding.append(self.after(120, hide_now))

        for w in (row, line, dot, text, remove, move, later):
            w.bind("<Enter>", show, add="+")
            w.bind("<Leave>", hide, add="+")
        for w in (remove, move, later):
            w.bind("<Enter>", lambda e, w=w: w.configure(fg=ACCENT), add="+")

    # Picking part of a note to copy (his ask, 2026-11-06: "the notes should be
    # copy/paste-able ... i just want to be able to click and drag it"). A label can't hold
    # a selection, so once the mouse moves a plain-text copy of the note goes exactly over
    # it, wrapped the same, and the drag selects in that; Ctrl+C copies, Esc or clicking
    # away clears it. A click without moving still does what it did (edit a waiting note).
    def _selectable(self, label, click=None):
        label.bind("<ButtonPress-1>", lambda e: self._sel_start(e, label, click))
        label.bind("<B1-Motion>", self._sel_move)
        label.bind("<ButtonRelease-1>", self._sel_end)

    def _sel_start(self, event, label, click):
        old = getattr(self, "_sel", None)
        if old and old["label"] is not label:
            self._sel_clear()
            old = None
        self._sel = {"label": label, "click": click, "x": event.x_root, "y": event.y_root,
                     "moved": False, "box": old["box"] if old else None}

    def _sel_box(self, label):
        pad = int(label.cget("padx")) + int(label.cget("bd"))
        padv = int(label.cget("pady")) + int(label.cget("bd"))
        wrap = int(label.cget("wraplength") or 0)
        box = tk.Text(label, font=label.cget("font"), bg=PAPER, fg=label.cget("fg"),
                      wrap="word", relief="flat", bd=0, highlightthickness=0, padx=pad,
                      pady=padv, cursor="xterm", selectbackground=SIDEBAR_PICKED,
                      selectforeground=INK, inactiveselectbackground=SIDEBAR_PICKED,
                      insertwidth=0)
        box.insert("1.0", label.cget("text"))
        box.configure(state="disabled")
        box.bindtags((str(box), "all"))
        wide = min(label.winfo_width(), wrap + 2 * pad + 2) if wrap else label.winfo_width()
        box.place(x=0, y=0, width=wide, height=label.winfo_height())
        box.update_idletasks()
        for seq in ("<Enter>", "<Leave>", "<Button-3>"):  # hover and right-click as before
            if label.bind(seq):
                box.bind(seq, label.bind(seq))
        box.bind("<ButtonPress-1>", lambda e: self._sel_start(e, label, self._sel["click"]))
        box.bind("<B1-Motion>", self._sel_move)
        box.bind("<ButtonRelease-1>", self._sel_end)
        box.bind("<Control-c>", self._sel_copy)
        box.bind("<Control-C>", self._sel_copy)
        box.bind("<Escape>", lambda e: self._sel_clear())
        box.bind("<FocusOut>", lambda e: self._sel_clear())
        return box

    @staticmethod
    def _sel_at(box, x_root, y_root):
        return box.index(f"@{x_root - box.winfo_rootx()},{y_root - box.winfo_rooty()}")

    def _sel_move(self, event):
        s = getattr(self, "_sel", None)
        if not s:
            return
        if not s["moved"]:
            if abs(event.x_root - s["x"]) + abs(event.y_root - s["y"]) < 5:
                return
            s["moved"] = True
            if s["box"] is None or not s["box"].winfo_exists():
                s["box"] = self._sel_box(s["label"])
            s["from"] = self._sel_at(s["box"], s["x"], s["y"])
        box = s["box"]
        a, b = s["from"], self._sel_at(box, event.x_root, event.y_root)
        if box.compare(b, "<", a):
            a, b = b, a
        box.tag_remove("sel", "1.0", "end")
        box.tag_add("sel", a, b)

    def _sel_end(self, event):
        s = getattr(self, "_sel", None)
        if not s:
            return
        if not s["moved"]:
            click = s["click"]
            self._sel_clear()
            if click:
                click()
        elif s["box"].tag_ranges("sel"):
            s["box"].focus_set()
        else:
            self._sel_clear()

    def _sel_copy(self, _=None):
        s = getattr(self, "_sel", None)
        if s and s["box"] is not None and s["box"].tag_ranges("sel"):
            self.clipboard_clear()
            self.clipboard_append(s["box"].get("sel.first", "sel.last"))
            self.say("✓ Copied", ACCENT)
        return "break"

    def _sel_clear(self):
        s, self._sel = getattr(self, "_sel", None), None
        if s and s["box"] is not None and s["box"].winfo_exists():
            s["box"].destroy()

    def _show_snap(self, row, text, note, show, hide):
        """The snapshot line in a small box just under the note, over the notes below it."""
        tip = getattr(self, "_snap_tip", None)
        if tip is None:
            tip = self._snap_tip = tk.Label(self.holder, font=self.f_small, bg=FIELD,
                                            fg=FADED_INK, anchor="w", justify="left", padx=10,
                                            pady=4, highlightthickness=1,
                                            highlightbackground=RULE, cursor="hand2")
        if self._snap_for is row:
            return
        self._snap_for = row
        wide = max(min(row.winfo_width(), self.canvas.winfo_width()) - 28, 120)
        tip.configure(text=text, wraplength=wide - 24)
        tip.bind("<Button-1>", lambda e: SnapshotDetails(self, note))
        tip.bind("<Enter>", show)  # moving onto the box keeps it up
        tip.bind("<Leave>", hide)
        tip.place(in_=row, x=28, rely=1.0, y=-2, width=wide)
        tip.lift()

    def _hide_snap(self):
        self._snap_for = None
        if getattr(self, "_snap_tip", None) is not None:
            self._snap_tip.place_forget()

    def _heading(self, text, notes=None, send=False, top=False):
        """A section title; with notes, also the "Send"/"Work" column titles over the ticks.
        Clicking a column title ticks the whole column (or unticks it, if all are ticked)."""
        row = tk.Frame(self.notes_frame, bg=PAPER)
        row.pack(fill="x", pady=(8 if top else 38, 6))
        if notes:
            for which, colour, shown in (("work", WORK_GREEN, True), ("send", ACCENT, send)):
                if which == "work" and self.lando:
                    continue
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

    def _total(self, notes):
        """A section's token estimate: its notes' guesses added up (his ask, 2026-11-01)."""
        return f"{sender.short_tokens(sum(self._tokens(n) for n in notes))} tokens"

    def _group_totals(self, notes):
        totals = {}
        for n in notes:
            if n.get("group"):
                totals[n["group"]] = totals.get(n["group"], 0) + self._tokens(n)
        return totals

    def _group_heading(self, note, current, totals):
        """After Organize, a quiet heading over each group of related notes (his pick), with
        the group's token total. Returns the group now showing."""
        group = note.get("group")
        if group and group != current:
            text = f"{group} · {sender.short_tokens(totals[group])}"
            tk.Label(self.notes_frame, text=text, font=self.f_small, bg=PAPER, fg=ACCENT,
                     anchor="w").pack(fill="x", padx=(20, 0), pady=(16, 2))
        return group

    def _tick_cell(self, parent, note, which):
        """One tick box in the "send" or "work" column; None draws an empty cell."""
        if which == "work" and self.lando:
            return  # no Work column in Lando mode
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

    def _room(self, w, known):
        """How wide w will be, worked out from the layout (the canvas's width, then each
        frame's padding and the sizes its neighbours ask for), so the page can be wrapped
        before it is ever shown: Tk only measures what is on screen. known: a cache."""
        if w is self.notes_frame:
            return self.canvas.winfo_width()
        if w in known:
            return known[w]
        info = w.pack_info()
        room = self._room(w.master, known) - self._padx(info)
        if info["side"] in ("left", "right"):
            for other in w.master.pack_slaves():
                if other is not w:
                    o = other.pack_info()
                    if o["side"] in ("left", "right"):
                        room -= other.winfo_reqwidth() + self._padx(o)
        known[w] = room
        return room

    @staticmethod
    def _padx(info):
        pad = info.get("padx", 0)
        pad = sum(int(p) for p in pad) if isinstance(pad, (tuple, list)) else int(pad) * 2
        return pad + int(info.get("ipadx", 0)) * 2

    def _rewrap_all(self):
        self._rewrap_job = None
        known = {}
        for label in self._wrapping:
            if not label.winfo_exists():
                continue
            try:
                width = max(self._room(label, known) - 12, 50)
            except tk.TclError:  # not packed (yet)
                continue
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
        # the size is in the colour; the word went for less clutter (his ask, 2026-11-06)
        tk.Label(parent, text=tokens, font=self.f_small, bg=PAPER, fg=colour,
                 width=6, anchor="e").pack(side="right", padx=(10, 0), anchor="n", pady=pady)

    def _draw_history(self, note):
        review = note["status"] == "review"  # finished, waiting on lando: shown like done
        done = note["status"] == "done" or review
        line = tk.Frame(self.notes_frame, bg=PAPER)
        line.pack(fill="x", pady=5)
        # ✓ finished, → on the list
        tk.Label(line, text="✓" if done else "→", font=self.f_todo, bg=PAPER,
                 fg=WORK_GREEN if review else ACCENT if done else FADED_INK,
                 width=2).pack(side="left", padx=(0, 6), anchor="n")
        if review:
            tk.Label(line, text="with Lando", font=self.f_small, bg=PAPER,
                     fg=WORK_GREEN).pack(side="right", padx=(10, 4), anchor="n")
        if not done:
            self._tick_cell(line, note, "work")
            self._tick_cell(line, None, "send")
            self._size_tag(line, note)  # by the ticks, so the tags line up in a column
        if review:
            when = ""
        elif done:
            when = nice_date(note["done"]) if note.get("done") else ""
        elif note.get("worked"):
            when = nice_date(note["worked"])  # its section already says Claude was on it
        else:
            when = nice_date(note["sent"]) if note.get("sent") else ""
        if when:
            when += self._guessed_used(note)
        date = None
        if when:
            # shown only while the mouse is over the item (his pick, 2026-11-02: less clutter)
            colour = WORK_GREEN if note.get("worked") and not done else FADED_INK
            date = tk.Label(line, text=when, font=self.f_small, bg=PAPER, fg=PAPER)
            date.pack(side="right", padx=(10, 4), anchor="n")
        later = None
        words = []  # the words that show under the mouse
        if not done:
            later = tk.Label(line, text="Later", font=self.f_small, bg=PAPER, fg=PAPER,
                             cursor="hand2")
            later.pack(side="right", padx=(8, 0), anchor="n")
            later.bind("<Button-1>", lambda e: self.later_note(note))
            words.append(later)
        if not done and note.get("worked"):
            # He has checked it and it is done as far as he is going (his ask, 2026-11-04)
            finish = tk.Label(line, text="Finished", font=self.f_small, bg=PAPER, fg=PAPER,
                              cursor="hand2")
            finish.pack(side="right", padx=(8, 0), anchor="n")
            finish.bind("<Button-1>", lambda e: self.finish_note(note))
            words.append(finish)
        text = tk.Label(line, text=note["text"], font=self.f_todo, bg=PAPER,
                        fg=FADED_INK if done else INK, anchor="w", justify="left",
                        cursor="xterm")
        text.pack(side="left", fill="x", expand=True)
        self._wrap(text)
        self._selectable(text)
        if later is not None:
            for w in (line, text):
                w.bind("<Button-3>", lambda e: self.move_menu(note, e))
            for w in (line, text, *words):
                for word in words:
                    w.bind("<Enter>", lambda e, word=word: word.configure(fg=FADED_INK), add="+")
                    w.bind("<Leave>", lambda e, word=word: word.configure(fg=PAPER), add="+")
            for word in words:
                word.bind("<Enter>", lambda e, word=word: word.configure(fg=ACCENT), add="+")
        if date is not None:
            for w in (line, text, date):
                w.bind("<Enter>", lambda e: date.configure(fg=colour), add="+")
                w.bind("<Leave>", lambda e: date.configure(fg=PAPER), add="+")

    def _draw_later(self, later):
        """The Later box (his ask, 2026-11-02: "pin it in a box for getting it done later so it
        doesnt clutter up the rest"). His picks: above Done, folded to one line until clicked;
        "Now" (shown under the mouse, or right-click) brings a note back."""
        arrow = "▾" if self.later_open else "▸"
        head = tk.Label(self.notes_frame, text=f"{arrow} Later ({len(later)}) · "
                                               f"{self._total(later)}",
                        font=self.f_head, bg=PAPER, fg=FADED_INK, anchor="w", cursor="hand2")
        head.pack(fill="x", pady=(26, 4))
        head.bind("<Button-1>", lambda e: self.toggle_later())
        head.bind("<Enter>", lambda e: head.configure(fg=ACCENT))
        head.bind("<Leave>", lambda e: head.configure(fg=FADED_INK))
        if not self.later_open:
            return
        for note in later:
            line = tk.Frame(self.notes_frame, bg=PAPER)
            line.pack(fill="x", pady=2)
            tk.Label(line, text="◦", font=self.f_todo, bg=PAPER, fg=FADED_INK,
                     width=2).pack(side="left", padx=(0, 6), anchor="n")
            remove = tk.Label(line, text="×", font=self.f_todo, bg=PAPER, fg=PAPER,
                              cursor="hand2")
            remove.pack(side="right", padx=(8, 4), anchor="n")
            now = tk.Label(line, text="Now", font=self.f_small, bg=PAPER, fg=PAPER,
                           cursor="hand2")
            now.pack(side="right", padx=(8, 0), anchor="n")
            self._size_tag(line, note)
            text = tk.Label(line, text=note["text"], font=self.f_todo, bg=PAPER, fg=FADED_INK,
                            anchor="w", justify="left", cursor="xterm")
            text.pack(side="left", fill="x", expand=True)
            self._wrap(text)
            self._selectable(text)
            now.bind("<Button-1>", lambda e, n=note: self.now_note(n))
            remove.bind("<Button-1>", lambda e, n=note: self.delete_note(n))
            for w in (line, text):
                w.bind("<Button-3>", lambda e, n=note: self.move_menu(n, e))
            for w in (line, text, now, remove):
                w.bind("<Enter>", lambda e, a=(now, remove): [x.configure(fg=FADED_INK)
                                                             for x in a], add="+")
                w.bind("<Leave>", lambda e, a=(now, remove): [x.configure(fg=PAPER)
                                                             for x in a], add="+")
            for w in (now, remove):
                w.bind("<Enter>", lambda e, w=w: w.configure(fg=ACCENT), add="+")

    def toggle_later(self):
        self.later_open = not self.later_open
        self.refresh(keep_scroll=True)

    def _guessed_used(self, note) -> str:
        """" · guessed ~29k · used ~34k" for a note Claude worked on, beside its date (his
        ask, 2026-11-09): VibeNote's guess when he pressed Work, and what the batch used."""
        parts = []
        if note.get("expected"):
            parts.append(f"guessed {sender.short_tokens(note['expected'])}")
        if note.get("worked") or note.get("work_at") or note["status"] in ("done", "review"):
            used = sender.actual_tokens(note, self.current.slug, self.guess.usage)
            if used:
                parts.append(f"used {sender.short_tokens(used)}")
        return "".join(" · " + p for p in parts)

    def _draw_done(self, done):
        """The Done list as one block of text, not a row of widgets per item: it can run to
        dozens of items, and rebuilding that many widgets made the window choppy."""
        indent = self.f_todo.measure("✓") + 14
        box = tk.Text(self.notes_frame, bg=PAPER, fg=FADED_INK, font=self.f_todo, wrap="word",
                      relief="flat", bd=0, highlightthickness=0, padx=0, pady=0, height=1,
                      cursor="xterm", spacing3=7, selectbackground=SIDEBAR_PICKED,
                      selectforeground=INK, inactiveselectbackground=SIDEBAR_PICKED)
        box.tag_configure("item", lmargin1=2, lmargin2=indent,
                          tabs=(indent,))
        box.tag_configure("tick", foreground=ACCENT)
        box.tag_configure("date", font=self.f_small, foreground=FADED_INK)
        for note in done:
            box.insert("end", "✓", ("item", "tick"), "\t" + note["text"], "item")
            if note.get("done"):
                box.insert("end", "   " + nice_date(note["done"]) + self._guessed_used(note),
                           ("item", "date"))
            box.insert("end", "\n", "item")
        box.delete("end-2c")  # no blank line after the last one
        box.configure(state="disabled")
        # Drag to pick text, Ctrl+C to copy (his ask, 2026-11-06); no scrolling of its own
        box.bindtags((str(box), "Text", "all"))
        box.bind("<ButtonPress-1>", lambda e: box.focus_set(), add="+")
        for seq in ("<Button-4>", "<Button-5>", "<MouseWheel>"):
            box.bind(seq, lambda e: self._scroll(-1 if e.num == 4 or e.delta > 0 else 1)
                     or "break")
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
        results: what a background read found ({slug: (open, done, review)}); else read here."""
        if results is None:
            results = {p.slug: p.read() for p in self.projects}
        changed = False
        for p in self.projects:
            if p.slug in results:
                open_items, done, review = results[p.slug]
                changed |= self.store.sync(p.slug, open_items, done, review)
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
            editing = getattr(f, "editing", False) or isinstance(f, tk.Entry)
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
        project = self.current.slug if self.current else None
        return self.guess.tokens(size, datetime.now().astimezone(), project)

    def _relearn(self, again=True, then=None):
        """Every 5 minutes (and when he presses Organize): learn again from Claude's chats
        (on a side thread: reading them takes a second or two), then update the sign and the
        guesses. again: keep doing it every 5 minutes. then: run afterwards."""
        found = []
        def read():
            sender.refresh_own_usage(collect=True)  # Lando mode: learns from his own chats
            found.append(sender.load_usage())
        reader = threading.Thread(target=read, daemon=True)
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
            if then:
                then()
            if again:
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
        self.show(None)

    def add_note(self):
        text = self.entry.get("1.0", "end-1c")
        if text == self._placeholder and self.entry.cget("fg") == FADED_INK:
            return
        note = self.current and self.store.add(self.current.slug, text)
        if note:
            self.entry.delete("1.0", "end")
            self.entry.configure(height=1)
            self.refresh(keep_scroll=True)
            self._take_snapshot(self.current, note)

    def _take_snapshot(self, project, note):
        """Note down what the project was like right now (git and its Claude chat), on a side
        thread so typing never waits."""
        found = []
        taker = threading.Thread(target=lambda: found.append(sender.snapshot(project)),
                                 daemon=True)
        taker.start()

        def apply():
            if taker.is_alive():
                self.after(100, apply)
            elif found:
                self.store.set_snapshot(project.slug, note["id"], found[0])
                if self.view is None and self.current is project:
                    self.refresh(keep_scroll=True)
        self.after(100, apply)

    def tick(self, note, which, box):
        """Flip one tick. Only that box and the buttons change; the page is not rebuilt."""
        self.store.tick(self.current.slug, [note["id"]], which, not note[which])
        on = note[which]
        colour = ACCENT if which == "send" else WORK_GREEN
        box.configure(text="☑" if on else "☐", fg=colour if on else FADED_INK)
        self._update_buttons()
        kept = self._pages.get(self.current.slug)
        if kept:  # the kept page already shows the new tick
            self._pages[self.current.slug] = (kept[0], self._page_key(), kept[2])

    def _tick_all_row(self, notes, sent):
        """One place to tick everything (his ask, 2026-11-02): all waiting notes for Send,
        everything open (waiting and on the list) for Work, or untick it all."""
        if self.lando and not notes:
            return  # only Send ticks in Lando mode: nothing waiting, nothing to tick
        row = tk.Frame(self.notes_frame, bg=PAPER)
        row.pack(fill="x", pady=(0, 6))
        tk.Label(row, text="Tick all:", font=self.f_small, bg=PAPER, fg=FADED_INK).pack(
            side="left")
        everything = notes + sent
        links = [("Send", ACCENT, lambda: self.tick_every(notes, "send", True)),
                 ("Work", WORK_GREEN, lambda: self.tick_every(everything, "work", True)),
                 ("Untick all", FADED_INK, lambda: self.untick_every(everything))]
        if self.lando:
            links.pop(1)
        if not notes:
            links.pop(0)
        for text, colour, action in links:
            SmallButton(row, self.f_small, action, colour, text).pack(side="left", padx=(10, 0))

    def tick_every(self, notes, which, on):
        self.store.tick(self.current.slug, [n["id"] for n in notes], which, on)
        self.refresh(keep_scroll=True)

    def untick_every(self, notes):
        ids = [n["id"] for n in notes]
        self.store.tick(self.current.slug, ids, "send", False)
        self.store.tick(self.current.slug, ids, "work", False)
        self.refresh(keep_scroll=True)

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
        self.say("Organized · updating the estimates…")
        self.refresh()
        # His ask (2026-11-02): Organize also brings the token and usage guesses up to date
        # for this time of day and week: re-read what Claude has used, then redraw
        self._relearn(again=False, then=lambda: self.say("✓ Organized · estimates up to date",
                                                         ACCENT))

    def delete_note(self, note):
        self.store.delete(self.current.slug, note["id"])
        self.refresh(keep_scroll=True)

    def edit_note(self, note, line, label):
        """Swap the note for a text box; Enter or clicking away saves it, Esc leaves it as it was."""
        label.pack_forget()
        box = tk.Text(line, font=self.f_note, bg=FIELD, fg=INK, relief="flat", height=1,
                      wrap="word", insertbackground=INK, highlightthickness=1, padx=1, pady=1,
                      highlightbackground=RULE, highlightcolor=ACCENT)
        box.editing = True  # the 10 s to-do re-read waits while he edits
        box.insert("1.0", note["text"])
        box.pack(side="left", fill="x", expand=True)
        self._growing(box, most=20)  # the whole note, however long
        box.focus_set()
        box.mark_set("insert", "end-1c")
        done = []

        def finish(save=True):
            if done:
                return
            done.append(True)
            if save:
                self.store.edit(self.current.slug, note["id"], box.get("1.0", "end-1c"))
            self.refresh(keep_scroll=True)

        box.bind("<Return>", lambda e: finish() or "break")
        box.bind("<FocusOut>", lambda e: finish())
        box.bind("<Escape>", lambda e: finish(save=False))

    def move_menu(self, note, event):
        menu = tk.Menu(self, tearoff=0, bg=FIELD, fg=INK, activebackground=SIDEBAR_PICKED,
                       activeforeground=INK, font=self.f_side, relief="flat")
        if note["status"] == "later":
            menu.add_command(label="Now: bring it back", command=lambda: self.now_note(note))
            menu.add_separator()
        elif note["status"] in ("waiting", "sent"):
            menu.add_command(label="Later: put it aside", command=lambda: self.later_note(note))
            menu.add_separator()
        if note["status"] == "sent":  # on the list already: it stays in this project
            menu.tk_popup(event.x_root, event.y_root)
            return
        menu.add_command(label="Move to…", state="disabled")
        for p in self.projects:
            if p is not self.current:
                menu.add_command(label=p.title, command=lambda to=p: self.move_note(note, to))
        menu.tk_popup(event.x_root, event.y_root)

    def later_note(self, note):
        """Into the Later box; an item already on the to-do list comes off it (his pick)."""
        p = self.current
        if note["status"] == "sent":
            try:
                p.remove_from_todo(note["text"])
            except OSError as err:
                self.say(f"Couldn't take it off the list: {err.strerror or err}.", ACCENT)
                return
        self.store.later(p.slug, note["id"])
        self.say("Put aside in Later")
        self.refresh(keep_scroll=True)

    def finish_note(self, note):
        """He has checked it: ticked on its to-do list, so it turns done (or, in a game shared
        with lando, up for his review) when the list is next read."""
        p = self.current
        try:
            found = p.finish_in_todo(note["text"])
        except OSError as err:
            self.say(f"Couldn't tick it on the list: {err.strerror or err}.", ACCENT)
            return
        if not found:
            self.say("Couldn't find it on the list (it may be on another branch).", ACCENT)
            return
        self.sync({p.slug: p.read()})
        self.say("Ticked off as finished")
        self.refresh(keep_scroll=True)

    def now_note(self, note):
        self.store.now(self.current.slug, note["id"])
        self.say("Back in Waiting to send")
        self.refresh(keep_scroll=True)

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
        cost = sum(self._tokens(n) for n in chosen)
        usage_text = self._usage_after(cost)
        fresh, why = sender.work_plan(p, self.guess.usage)
        if fresh:
            usage_text = (f"VibeNote will start {p.title}'s Claude fresh first: {why}. Claude "
                          "reads the project's notes again, so nothing is lost.\n\n" + usage_text)
        if not TokenWarning(self, p.title, len(chosen), extra, cost, usage_text).agreed:
            self.say("Nothing sent to Claude.")
            return
        if waiting and not self._send(p, waiting):
            return
        self.store.mark_worked(p.slug, [n["id"] for n in chosen],
                               {n["id"]: self._tokens(n) for n in chosen})
        items = [n["text"] for n in chosen]
        self.sending = "…"
        self.work_btn.set("Starting…", enabled=False)

        def go():
            try:
                self.sending = ("ok", sender.start_work(p, items, self.guess.usage))
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


class SmallButton(tk.Label):
    """A small outlined button for the little things to click (his pick, 2026-11-02: "clearer
    places where you are able to click"); it lights up under the mouse. An empty text hides
    it."""

    def __init__(self, parent, font, command, colour, text=""):
        self.colour = colour
        super().__init__(parent, font=font, fg=colour, bg=FIELD, padx=10, pady=2,
                         highlightthickness=1, highlightbackground=RULE, highlightcolor=RULE,
                         cursor="hand2")
        self.bind("<Button-1>", lambda e: command())
        self.bind("<Enter>", lambda e: self.configure(bg=SIDEBAR_PICKED,
                                                      highlightbackground=colour))
        self.bind("<Leave>", lambda e: self.configure(bg=FIELD, highlightbackground=RULE))
        self._packed = None
        self.set(text)

    def pack(self, **kw):
        self._packed = kw
        if self.cget("text"):
            super().pack(**kw)

    def set(self, text):
        self.configure(text=text)
        if not text:
            self.pack_forget()
        elif self._packed is not None and not self.winfo_ismapped():
            super().pack(**self._packed)


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


class SnapshotDetails(tk.Toplevel):
    """Everything the snapshot saw when he wrote the note, so the moment can be looked up."""

    def __init__(self, app, note):
        super().__init__(app, class_=POPUP_CLASS, bg=PAPER, padx=28, pady=22)
        self.title("When this note was written")
        self.transient(app)
        snap = note["snap"]
        rows = [("Note", note["text"])]
        try:
            rows.append(("Written", datetime.fromisoformat(snap["at"]).strftime(
                "%A %-d %B %Y, %H:%M")))
        except (KeyError, ValueError):
            pass
        if snap.get("commit"):
            rows += [("Code", f"branch {snap.get('branch') or '?'}, last saved as "
                              f"{snap['commit']} \u201c{snap['subject']}\u201d ({snap['saved']})"),
                     ("Changes", f"{snap.get('changed', 0)} files changed since that save")]
        chat = snap.get("claude")
        if chat:
            rows += [("Claude", f"{'working on' if chat['working'] else 'was on'}: "
                                f"{chat['title']}" + (f" · now: {chat['now']}" if chat["now"]
                                                      else "")),
                     ("It said", chat["said"])]
        else:
            rows.append(("Claude", "no chat was open for this project"))
        for name, value in rows:
            line = tk.Frame(self, bg=PAPER)
            line.pack(fill="x", pady=2)
            tk.Label(line, text=name, font=app.f_small, bg=PAPER, fg=ACCENT, width=9,
                     anchor="nw").pack(side="left", anchor="n")
            tk.Label(line, text=value, font=app.f_todo, bg=PAPER, fg=INK, justify="left",
                     wraplength=440, anchor="w").pack(side="left", fill="x")
        if snap.get("commit"):
            tk.Label(self, text=f"Claude can look this moment up: ask it about save point "
                                f"{snap['commit']}.", font=app.f_small, bg=PAPER, fg=FADED_INK,
                     anchor="w").pack(fill="x", pady=(10, 0))
        close = Button(self, app.f_button, self.destroy, main=False)
        close.set("Close")
        close.pack(anchor="e", pady=(14, 0))
        self.bind("<Escape>", lambda e: self.destroy())
        centre_on(app, self)


class Mini(tk.Tk):
    """Lando mode's mini player (his pick, 2026-11-09: "minimized almost like a miniplayer
    ... not a lot of text by default"): the good-time dot, the two usage bars and one tip.
    Notes, Usage and Tips open the whole app (without Work). .next says which."""

    WIDTH = 340

    def __init__(self):
        super().__init__(className="vibenote")
        self.title("VibeNote")
        self.configure(bg=SIDEBAR)
        self.resizable(False, False)
        self.next = None
        self.f_small = tkfont.Font(family=SERIF, size=13)
        self.f_section = tkfont.Font(family=SERIF, size=11, weight="bold")
        self.f_side = tkfont.Font(family=SERIF, size=15)
        box = tk.Frame(self, bg=SIDEBAR)
        box.pack(fill="both", expand=True, padx=20, pady=16)
        self.sign = tk.Label(box, font=self.f_side, bg=SIDEBAR, anchor="w")
        self.sign.pack(fill="x")
        self.live = tk.Frame(box, bg=SIDEBAR)
        self.live.pack(fill="x", pady=(8, 0))
        self.tip = tk.Label(box, font=self.f_small, bg=SIDEBAR, fg=FADED_INK, anchor="w",
                            justify="left", wraplength=self.WIDTH - 40)
        self.tip.pack(fill="x", pady=(6, 12))
        links = tk.Frame(box, bg=SIDEBAR)
        links.pack(anchor="w")
        for text, view in (("Notes ›", "notes"), ("Usage ›", "usage"), ("Tips ›", "tips")):
            SmallButton(links, self.f_small, lambda v=view: self.open(v), ACCENT, text).pack(
                side="left", padx=(0, 8))
        self.bind("<Escape>", lambda e: self.destroy())
        self.show()
        self.after(200, self._float)

    def show(self):
        """Re-read every 30 s; his own numbers are fetched on a side thread for next time."""
        threading.Thread(target=sender.refresh_own_usage, daemon=True).start()
        guess = sender.TokenGuess(sender.load_usage())
        level, _ = sender.good_time(guess)
        self.sign.configure(text="● Good time for Claude" if level == "good"
                            else "● Busy hours for Claude",
                            fg=WORK_GREEN if level == "good" else ACCENT)
        for w in self.live.winfo_children():
            w.destroy()
        draw_live(self.live, self.f_small, self.f_section, self.WIDTH - 40, SIDEBAR)
        tips = sender.token_tips(guess.usage, guess, direct=True)
        self.tip.configure(text="Tip: " + tips[0] if tips else "")
        self.after(30_000, self.show)

    def open(self, view):
        self.next = view
        self.destroy()

    def _float(self):
        if not os.environ.get("HYPRLAND_INSTANCE_SIGNATURE"):
            return
        try:
            subprocess.run(["hyprctl", "dispatch", "setfloating", f"pid:{os.getpid()}"],
                           capture_output=True, timeout=3)
        except (OSError, subprocess.SubprocessError):
            pass


def live_colour(pct):
    return WORK_GREEN if pct < 50 else INK if pct < 80 else ACCENT


def draw_live(box, f_small, f_section, width, bg):
    """The two bars Claude's /usage shows, in box (the sidebar, or the mini player)."""
    live = sender.load_live_usage()
    if not live:
        tk.Label(box, text="Live usage shows after Claude's next reply.",
                 font=f_small, bg=bg, fg=FADED_INK, anchor="w", justify="left",
                 wraplength=width).pack(fill="x")
        return
    name = next((a["name"] for a in sender.load_accounts()
                 if a.get("email") and a["email"] == live.get("email")), "")
    try:
        age = (datetime.now().astimezone()
               - datetime.fromisoformat(live["at"])).total_seconds() / 60
    except (KeyError, ValueError):
        age = 0
    old = (f" · {round(age / 60)}h ago" if age >= 90 else f" · {round(age)} min ago"
           if age >= 15 else "")
    tk.Label(box, text=(name or "Claude") + " now" + old, font=f_section,
             bg=bg, fg=FADED_INK, anchor="w").pack(fill="x", pady=(0, 4))
    for key, title, when in (("five_hour", "5 hours", "%-I:%M%p"),
                             ("week", "This week", "%a %-I%p")):
        part = live.get(key)
        if not part:
            continue
        pct = max(0.0, min(100.0, part["percent"]))
        try:
            resets = datetime.fromisoformat(part["resets"]).astimezone().strftime(when)
            resets = "resets " + resets.replace("AM", "am").replace("PM", "pm")
        except (TypeError, ValueError, KeyError):
            resets = "starts fresh"
        top = tk.Frame(box, bg=bg)
        top.pack(fill="x")
        tk.Label(top, text=f"{round(pct)}%", font=f_small, bg=bg,
                 fg=live_colour(pct)).pack(side="right")
        tk.Label(top, text=title, font=f_small, bg=bg, fg=INK).pack(side="left")
        # the reset time beside the title when there is room, else under the bar
        beside = (f_small.measure(f"{title} · {resets} 100%") <= width)
        if beside:
            tk.Label(top, text=" · " + resets, font=f_small, bg=bg,
                     fg=FADED_INK).pack(side="left")
        bar_w, bar_h = width, 8
        bar = tk.Canvas(box, width=bar_w, height=bar_h, bg=bg,
                        highlightthickness=0)
        bar.pack(fill="x", pady=(3, 9 if beside else 1))
        bar.create_rectangle(0, 0, bar_w, bar_h, fill=RULE, width=0)
        if pct:
            bar.create_rectangle(0, 0, max(3, bar_w * pct / 100), bar_h,
                                 fill=live_colour(pct), width=0)
        if not beside:
            tk.Label(box, text=resets, font=f_small, bg=bg,
                     fg=FADED_INK, anchor="w").pack(fill="x", pady=(0, 6))


def close_older_copies() -> int:
    """One VibeNote at a time (2026-11-02): an older copy left open after an update kept the
    old code, so its token warning still came up in the screen's corner. Opening VibeNote
    closes any other copy he has running; notes are saved as he goes, so nothing is lost."""
    import signal
    me = os.getpid()
    closed = 0
    for proc in Path("/proc").iterdir():
        if not proc.name.isdigit() or int(proc.name) == me:
            continue
        try:
            if proc.stat().st_uid != os.getuid():
                continue
            args = (proc / "cmdline").read_bytes().split(b"\0")
        except OSError:
            continue
        if (any(a.endswith(b"vibenote/main.py") for a in args)
                and not {b"--collect-usage", b"--live-usage", b"--bar"} & set(args)):
            try:
                os.kill(int(proc.name), signal.SIGTERM)
                closed += 1
            except OSError:
                pass
    return closed


def centre_on(app, win):
    """Put a pop-up in the middle of VibeNote (his ask, 2026-11-02: the token warning came up
    in the corner of the screen, outside VibeNote). His desktop (Hyprland) decides where new
    windows go itself, so ask it to float the pop-up and move it there; elsewhere the
    window's own position is enough."""
    app.update_idletasks()
    x = app.winfo_rootx() + (app.winfo_width() - win.winfo_reqwidth()) // 2
    y = app.winfo_rooty() + (app.winfo_height() - win.winfo_reqheight()) // 3
    win.geometry(f"+{max(x, 0)}+{max(y, 0)}")
    win.wait_visibility()
    if not os.environ.get("HYPRLAND_INSTANCE_SIGNATURE"):
        return
    title = win.title()
    # The desktop may take a moment to list the new window, and places it itself once it
    # has: so move it, look again, and move it again until it stays put (up to ~1.5 s)
    for _ in range(30):
        try:
            out = subprocess.run(["hyprctl", "clients", "-j"], capture_output=True, text=True,
                                 timeout=2).stdout
            clients = [c for c in json.loads(out) if c.get("pid") == os.getpid()]
        except (OSError, ValueError, subprocess.SubprocessError):
            return
        main = next((c for c in clients if c.get("title") == "VibeNote"), None)
        pop = next((c for c in clients if c.get("title") == title), None)
        if main and pop:
            (mx, my), (mw, mh) = main["at"], main["size"]
            pw, ph = pop["size"]
            want = [mx + (mw - pw) // 2, my + (mh - ph) // 3]
            if pop["at"] == want:
                return
            where = f"address:{pop['address']}"
            if not pop.get("floating"):
                subprocess.run(["hyprctl", "dispatch", "setfloating", where],
                               capture_output=True, timeout=2)
            subprocess.run(["hyprctl", "dispatch", "movewindowpixel",
                            f"exact {want[0]} {want[1]},{where}"], capture_output=True, timeout=2)
        app.after(50)
        app.update()
    # Didn't stay put: note what the desktop said, so it can be fixed
    try:
        log = Path.home() / ".local/state/vibenote/centre.log"
        log.parent.mkdir(parents=True, exist_ok=True)
        with log.open("a") as f:
            f.write(f"{datetime.now().isoformat()} {title!r} pid {os.getpid()}: "
                    + json.dumps([{k: c.get(k) for k in ("title", "at", "size", "floating",
                                                         "workspace")} for c in clients])
                    + "\n")
    except (OSError, NameError):
        pass


class TokenWarning(tk.Toplevel):
    """Asks him to agree before Work uses his Claude tokens. .agreed says what he chose."""

    def __init__(self, app, title, total, extra, cost=0, usage_text=""):
        super().__init__(app, class_=POPUP_CLASS, bg=PAPER, padx=28, pady=22)
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
                 anchor="w").pack(fill="x", pady=(10, 10))
        if cost:
            tk.Label(self, text=f"VibeNote's guess: {sender.short_tokens(cost)} tokens.",
                     font=app.f_todo, bg=PAPER, fg=ACCENT, justify="left", wraplength=420,
                     anchor="w").pack(fill="x")
        if usage_text:
            tk.Label(self, text=usage_text, font=app.f_small, bg=PAPER, fg=INK, justify="left",
                     wraplength=420, anchor="w").pack(fill="x", pady=(4, 0))
        tk.Frame(self, bg=PAPER, height=14).pack()

        row = tk.Frame(self, bg=PAPER)
        row.pack(fill="x")
        agree = Button(row, app.f_button, self._agree, main=True)
        agree.set("I agree, start work")
        agree.pack(side="right")
        cancel = Button(row, app.f_button, self.destroy, main=False)
        cancel.set("Cancel")
        cancel.pack(side="right", padx=(0, 10))

        self.bind("<Escape>", lambda e: self.destroy())
        centre_on(app, self)
        self.grab_set()
        cancel.focus_set()
        app.wait_window(self)

    def _agree(self):
        self.agreed = True
        self.destroy()


if __name__ == "__main__":
    if "--live-usage" in sys.argv:
        # Run as root by the Glade's Claude hook: the numbers Claude's /usage shows
        sender.save_live_usage()
    elif "--collect-usage" in sys.argv:
        sender.save_live_usage(every=0)
        # Run as root (by Claude at the end of a Work batch): learn from Claude's chats
        previous = sender.load_saved_usage()
        if sender.save_if_better(sender.collect_usage(previous=previous), previous):
            print(f"VibeNote: token use saved to {sender.USAGE}")
        else:
            print("VibeNote: couldn't see Claude's chats from here, so the saved token use "
                  "was kept. Run it as root, outside any sandbox.")
    elif "--bar" in sys.argv:
        # Lando's top bar (Waybar) runs this every minute: the dial and the numbers
        sender.refresh_own_usage()
        print(sender.bar_json(), flush=True)
    else:
        # --toggle (the top bar's click): a second click closes the open VibeNote
        if close_older_copies() and "--toggle" in sys.argv:
            sys.exit()
        if "--lando" in sys.argv or sender.LANDO:
            mini = None
            if "--full" not in sys.argv:
                mini = Mini()
                mini.mainloop()
            if mini is None or mini.next:
                VibeNote(lando=True, view=mini and mini.next).mainloop()
        else:
            VibeNote().mainloop()
