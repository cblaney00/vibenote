"""VibeNote: to-do lists on warm paper."""

import tkinter as tk
from tkinter import font as tkfont
from tkinter import messagebox

from store import Store

# Warm paper colours
PAPER = "#f6eedb"
SIDEBAR = "#ebdfc3"
SIDEBAR_PICKED = "#dccba3"
INK = "#3b2f22"
FADED_INK = "#a3937a"
RULE = "#e2d4b4"
ACCENT = "#b5552f"  # brick red, like a margin line
FIELD = "#fffaf0"

SERIF = "Georgia"


class VibeNote(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("VibeNote")
        self.geometry("900x620")
        self.minsize(600, 400)
        self.configure(bg=PAPER)

        self.store = Store()
        self.current_id = self.store.lists[0]["id"]

        self.f_brand = tkfont.Font(family=SERIF, size=20, weight="bold", slant="italic")
        self.f_side = tkfont.Font(family=SERIF, size=13)
        self.f_side_picked = tkfont.Font(family=SERIF, size=13, weight="bold")
        self.f_title = tkfont.Font(family=SERIF, size=24, weight="bold")
        self.f_task = tkfont.Font(family=SERIF, size=14)
        self.f_task_done = tkfont.Font(family=SERIF, size=14, overstrike=1)
        self.f_box = tkfont.Font(family="DejaVu Sans", size=16)
        self.f_small = tkfont.Font(family=SERIF, size=11, slant="italic")

        self._build_sidebar()
        self._build_page()
        self.refresh()

    # --- layout -----------------------------------------------------------

    def _build_sidebar(self):
        side = tk.Frame(self, bg=SIDEBAR, width=220)
        side.pack(side="left", fill="y")
        side.pack_propagate(False)

        tk.Label(side, text="VibeNote", font=self.f_brand, bg=SIDEBAR, fg=ACCENT,
                 anchor="w").pack(fill="x", padx=18, pady=(18, 14))

        self.list_box = tk.Frame(side, bg=SIDEBAR)
        self.list_box.pack(fill="both", expand=True)

        new_btn = tk.Label(side, text="+  New list", font=self.f_side, bg=SIDEBAR,
                           fg=ACCENT, anchor="w", cursor="hand2")
        new_btn.pack(fill="x", padx=18, pady=16)
        new_btn.bind("<Button-1>", lambda e: self.new_list())

    def _build_page(self):
        page = tk.Frame(self, bg=PAPER)
        page.pack(side="left", fill="both", expand=True)

        # Red margin line down the left of the page, like notebook paper
        tk.Frame(page, bg=ACCENT, width=2).pack(side="left", fill="y", padx=(36, 0))

        body = tk.Frame(page, bg=PAPER)
        body.pack(side="left", fill="both", expand=True, padx=(24, 36), pady=(22, 16))

        header = tk.Frame(body, bg=PAPER)
        header.pack(fill="x")
        self.title_label = tk.Label(header, font=self.f_title, bg=PAPER, fg=INK,
                                    anchor="w", cursor="xterm")
        self.title_label.pack(side="left", fill="x", expand=True)
        self.title_label.bind("<Button-1>", lambda e: self.rename_list())

        delete_list = tk.Label(header, text="Delete list", font=self.f_small, bg=PAPER,
                               fg=FADED_INK, cursor="hand2")
        delete_list.pack(side="right")
        delete_list.bind("<Button-1>", lambda e: self.delete_list())

        self.count_label = tk.Label(body, font=self.f_small, bg=PAPER, fg=FADED_INK,
                                    anchor="w")
        self.count_label.pack(fill="x", pady=(0, 14))

        # Box for typing a new task
        entry_row = tk.Frame(body, bg=FIELD, highlightthickness=1, highlightbackground=RULE)
        entry_row.pack(fill="x", pady=(0, 10))
        self.entry = tk.Entry(entry_row, font=self.f_task, bg=FIELD, fg=INK,
                              insertbackground=INK, relief="flat", highlightthickness=0)
        self.entry.pack(fill="x", ipady=8, padx=10)
        self.entry.bind("<Return>", lambda e: self.add_task())
        self._placeholder = "Add a task and press Enter…"
        self._show_placeholder()
        self.entry.bind("<FocusIn>", lambda e: self._hide_placeholder())
        self.entry.bind("<FocusOut>", lambda e: self._show_placeholder())

        # Scrolling area for the tasks
        holder = tk.Frame(body, bg=PAPER)
        holder.pack(fill="both", expand=True)
        self.canvas = tk.Canvas(holder, bg=PAPER, highlightthickness=0)
        self.canvas.pack(side="left", fill="both", expand=True)
        self.tasks_frame = tk.Frame(self.canvas, bg=PAPER)
        self._win = self.canvas.create_window(0, 0, window=self.tasks_frame, anchor="nw")
        self.tasks_frame.bind("<Configure>", lambda e: self.canvas.configure(
            scrollregion=self.canvas.bbox("all")))
        self.canvas.bind("<Configure>", lambda e: self.canvas.itemconfigure(
            self._win, width=e.width))
        self.bind_all("<Button-4>", lambda e: self._scroll(-1))
        self.bind_all("<Button-5>", lambda e: self._scroll(1))
        self.bind_all("<MouseWheel>", lambda e: self._scroll(-1 if e.delta > 0 else 1))

        self.clear_label = tk.Label(body, text="Clear ticked tasks", font=self.f_small,
                                    bg=PAPER, fg=FADED_INK, cursor="hand2", anchor="e")
        self.clear_label.pack(fill="x", pady=(8, 0))
        self.clear_label.bind("<Button-1>", lambda e: self.clear_done())

    def _scroll(self, steps):
        if self.tasks_frame.winfo_height() > self.canvas.winfo_height():
            self.canvas.yview_scroll(steps, "units")

    def _show_placeholder(self):
        if not self.entry.get():
            self.entry.insert(0, self._placeholder)
            self.entry.configure(fg=FADED_INK)

    def _hide_placeholder(self):
        if self.entry.get() == self._placeholder and self.entry.cget("fg") == FADED_INK:
            self.entry.delete(0, "end")
            self.entry.configure(fg=INK)

    # --- drawing ----------------------------------------------------------

    def refresh(self):
        self._draw_sidebar()
        self._draw_tasks()

    def _draw_sidebar(self):
        for w in self.list_box.winfo_children():
            w.destroy()
        for lst in self.store.lists:
            picked = lst["id"] == self.current_id
            left = sum(not t["done"] for t in lst["tasks"])
            bg = SIDEBAR_PICKED if picked else SIDEBAR
            row = tk.Frame(self.list_box, bg=bg, cursor="hand2")
            row.pack(fill="x")
            name = tk.Label(row, text=lst["name"], bg=bg, fg=INK, anchor="w",
                            font=self.f_side_picked if picked else self.f_side)
            name.pack(side="left", fill="x", expand=True, padx=(18, 4), pady=7)
            num = tk.Label(row, text=str(left) if left else "", bg=bg, fg=FADED_INK,
                           font=self.f_small)
            num.pack(side="right", padx=14)
            for w in (row, name, num):
                w.bind("<Button-1>", lambda e, i=lst["id"]: self.pick_list(i))

    def _draw_tasks(self):
        lst = self.store.get_list(self.current_id)
        self.title_label.configure(text=lst["name"])

        tasks = lst["tasks"]
        done = sum(t["done"] for t in tasks)
        if not tasks:
            self.count_label.configure(text="Nothing here yet")
        else:
            self.count_label.configure(text=f"{done} of {len(tasks)} done")

        for w in self.tasks_frame.winfo_children():
            w.destroy()

        # Unticked tasks first, ticked ones sink to the bottom
        for task in [t for t in tasks if not t["done"]] + [t for t in tasks if t["done"]]:
            self._draw_task(task)

        if done:
            self.clear_label.pack(fill="x", pady=(8, 0))
        else:
            self.clear_label.pack_forget()
        self.canvas.yview_moveto(0)

    def _draw_task(self, task):
        row = tk.Frame(self.tasks_frame, bg=PAPER)
        row.pack(fill="x")
        line = tk.Frame(row, bg=PAPER)
        line.pack(fill="x", pady=4)

        box = tk.Label(line, text="☑" if task["done"] else "☐", font=self.f_box,
                       bg=PAPER, fg=ACCENT if task["done"] else INK, cursor="hand2")
        box.pack(side="left", padx=(0, 10))

        text = tk.Label(line, text=task["text"], bg=PAPER, anchor="w", justify="left",
                        fg=FADED_INK if task["done"] else INK,
                        font=self.f_task_done if task["done"] else self.f_task,
                        cursor="hand2")
        text.pack(side="left", fill="x", expand=True)
        text.bind("<Configure>", lambda e: text.configure(wraplength=max(e.width, 50)))

        remove = tk.Label(line, text="×", font=self.f_task, bg=PAPER, fg=PAPER,
                          cursor="hand2")
        remove.pack(side="right", padx=(8, 4))

        # Ruled line under each task, like lined paper
        tk.Frame(row, bg=RULE, height=1).pack(fill="x")

        toggle = lambda e, i=task["id"]: self.toggle_task(i)  # noqa: E731
        box.bind("<Button-1>", toggle)
        text.bind("<Button-1>", toggle)
        remove.bind("<Button-1>", lambda e, i=task["id"]: self.delete_task(i))

        # The × only shows while the mouse is over the task
        def show(_):
            remove.configure(fg=FADED_INK)

        def hide(_):
            remove.configure(fg=PAPER)

        for w in (row, line, box, text, remove):
            w.bind("<Enter>", show, add="+")
            w.bind("<Leave>", hide, add="+")
        remove.bind("<Enter>", lambda e: remove.configure(fg=ACCENT), add="+")

    # --- actions ----------------------------------------------------------

    def pick_list(self, list_id):
        self.current_id = list_id
        self.refresh()

    def add_task(self):
        text = self.entry.get()
        if text == self._placeholder and self.entry.cget("fg") == FADED_INK:
            return
        if self.store.add_task(self.current_id, text):
            self.entry.delete(0, "end")
            self.refresh()

    def toggle_task(self, task_id):
        self.store.toggle_task(self.current_id, task_id)
        self.refresh()

    def delete_task(self, task_id):
        self.store.delete_task(self.current_id, task_id)
        self.refresh()

    def clear_done(self):
        self.store.clear_done(self.current_id)
        self.refresh()

    def new_list(self):
        lst = self.store.add_list("New list")
        self.current_id = lst["id"]
        self.refresh()
        self.rename_list(select_all=True)

    def rename_list(self, select_all=False):
        """Swap the title for a text box; Enter or clicking away saves it."""
        lst = self.store.get_list(self.current_id)
        header = self.title_label.master
        self.title_label.pack_forget()
        box = tk.Entry(header, font=self.f_title, bg=FIELD, fg=INK, relief="flat",
                       insertbackground=INK, highlightthickness=1,
                       highlightbackground=RULE, highlightcolor=ACCENT)
        box.insert(0, lst["name"])
        box.pack(side="left", fill="x", expand=True)
        box.focus_set()
        box.select_range(0, "end") if select_all else box.icursor("end")

        def finish(save=True):
            if not box.winfo_exists():
                return
            if save:
                self.store.rename_list(lst["id"], box.get())
            box.destroy()
            self.title_label.pack(side="left", fill="x", expand=True)
            self.refresh()
            self.entry.focus_set()

        box.bind("<Return>", lambda e: finish())
        box.bind("<FocusOut>", lambda e: finish())
        box.bind("<Escape>", lambda e: finish(save=False))

    def delete_list(self):
        lst = self.store.get_list(self.current_id)
        if not messagebox.askyesno("Delete list",
                                   f"Delete “{lst['name']}” and all its tasks?",
                                   parent=self):
            return
        self.store.delete_list(lst["id"])
        self.current_id = self.store.lists[0]["id"]
        self.refresh()


if __name__ == "__main__":
    VibeNote().mainloop()
