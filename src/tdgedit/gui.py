"""True Disc Golf disc wear editor.

Reads the game's Easy Save 3 file, shows the discs in the bag with their wear, and writes
new wear values back into the save without disturbing anything else in the file.
"""

from __future__ import annotations

import os
import time
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from . import snapshots
from .savefile import Disc, DiscSave, SaveLocation, discover_saves, process_is_running

COLUMNS = (
    ("num", "disc", 90),
    ("type", "type", 80),
    ("slot", "bag slot", 110),
    ("name", "name", 150),
    ("maker", "maker", 90),
    ("plastic", "plastic", 90),
    ("speed", "speed", 55),
    ("weight", "wt", 50),
    ("durability", "durability", 80),
    ("wear", "wear", 110),
    ("worn", "worn", 60),
    ("fav", "fav", 45),
)

PRESETS = (("new", 0.0), ("light", 0.25), ("medium", 0.5), ("heavy", 0.75), ("beat", 1.0))

BROWSE = "Browse…"


class App(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("True Disc Golf disc wear editor")
        self.geometry("1120x680")
        self.minsize(900, 520)

        self.save: DiscSave | None = None
        self.locations: list[SaveLocation] = []
        self.location_var = tk.StringVar()
        self.status_var = tk.StringVar(value="Pick a save file.")
        self.warning_var = tk.StringVar(value="")
        self.staged_var = tk.StringVar(value="staged changes: 0")
        self.bag_only = tk.BooleanVar(value=False)
        self.category_var = tk.StringVar(value="all")
        self.search_var = tk.StringVar(value="")
        self.selected_index: int | None = None
        self.custom_path: str | None = None

        self._build_widgets()
        self._bind_keys()
        self._find_saves()
        self._warn_job = self.after(6000, self._warn_loop)

    # -------------------------------------------------------------- widgets

    def _build_widgets(self) -> None:
        top = ttk.Frame(self, padding=(10, 8, 10, 4))
        top.pack(fill="x")
        ttk.Label(top, text="Save:").pack(side="left")
        self.save_menu = ttk.OptionMenu(top, self.location_var, BROWSE, BROWSE, command=self._on_save_choice)
        self.save_menu.pack(side="left", padx=(4, 8))
        ttk.Button(top, text="Reload", width=8, command=self.reload).pack(side="left")
        ttk.Label(top, textvariable=self.status_var).pack(side="left", padx=10)

        warn = ttk.Label(top, textvariable=self.warning_var, foreground="#b00020")
        warn.pack(side="right")

        filters = ttk.Frame(self, padding=(10, 2, 10, 2))
        filters.pack(fill="x")
        ttk.Checkbutton(filters, text="in bag only", variable=self.bag_only, command=self._refresh_rows).pack(side="left")
        ttk.Label(filters, text=" type:").pack(side="left")
        ttk.OptionMenu(filters, self.category_var, "all", "all", "putter", "midrange", "driver",
                       command=self._refresh_rows).pack(side="left", padx=(2, 8))
        ttk.Label(filters, text=" search:").pack(side="left")
        entry = ttk.Entry(filters, textvariable=self.search_var, width=18)
        entry.pack(side="left")
        entry.bind("<Return>", lambda _e: self._refresh_rows())
        entry.bind("<KeyRelease>", lambda _e: self._refresh_rows())
        ttk.Label(filters, textvariable=self.staged_var).pack(side="right")

        body = ttk.Frame(self, padding=(10, 4, 10, 4))
        body.pack(fill="both", expand=True)

        self.tree = ttk.Treeview(body, columns=[c for c, _, _ in COLUMNS], show="headings", height=18)
        for column, heading, width in COLUMNS:
            self.tree.heading(column, text=heading)
            self.tree.column(column, width=width, anchor="w", stretch=True)
        bar = ttk.Scrollbar(body, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=bar.set)
        self.tree.pack(side="left", fill="both", expand=True)
        bar.pack(side="left", fill="y")
        self.tree.bind("<<TreeviewSelect>>", self._on_select)

        detail = ttk.LabelFrame(self, text="Selected disc", padding=(10, 6))
        detail.pack(fill="x", padx=10, pady=(0, 4))
        self.detail_title = ttk.Label(detail, text="no disc selected", font=("Segoe UI", 11, "bold"))
        self.detail_title.grid(row=0, column=0, columnspan=8, sticky="w")

        ttk.Label(detail, text="wear").grid(row=1, column=0, sticky="w")
        self.wear_scale = ttk.Scale(detail, from_=0.0, to=100.0, orient="horizontal", command=self._on_slide)
        self.wear_scale.grid(row=1, column=1, columnspan=4, sticky="ew", padx=6)
        self.wear_entry = ttk.Entry(detail, width=10)
        self.wear_entry.grid(row=1, column=5, sticky="w")
        self.wear_pct_var = tk.StringVar(value="")
        ttk.Label(detail, textvariable=self.wear_pct_var, width=8).grid(row=1, column=6, sticky="w")
        detail.columnconfigure(2, weight=1)

        ttk.Label(detail, text="presets").grid(row=2, column=0, sticky="w", pady=(6, 0))
        preset_frame = ttk.Frame(detail)
        preset_frame.grid(row=2, column=1, columnspan=4, sticky="w", pady=(6, 0))
        for label, fraction in PRESETS:
            ttk.Button(preset_frame, text=f"{label} {fraction * 100:.0f}%", width=9,
                       command=lambda f=fraction: self._preset(f)).pack(side="left", padx=2)

        ttk.Label(detail, text="durability").grid(row=3, column=0, sticky="w", pady=(6, 0))
        self.durability_entry = ttk.Entry(detail, width=10)
        self.durability_entry.grid(row=3, column=1, sticky="w", pady=(6, 0))
        ttk.Label(detail, text="weight (g)").grid(row=3, column=2, sticky="w", pady=(6, 0))
        self.weight_entry = ttk.Entry(detail, width=10)
        self.weight_entry.grid(row=3, column=3, sticky="w", pady=(6, 0))
        self.favourite_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(detail, text="favourite", variable=self.favourite_var,
                        command=self._stage_selected).grid(row=3, column=4, sticky="w", pady=(6, 0))
        ttk.Button(detail, text="stage row", command=self._stage_selected).grid(row=3, column=5, padx=6, pady=(6, 0))
        ttk.Button(detail, text="revert row", command=self._revert_selected).grid(row=3, column=6, pady=(6, 0))

        bulk = ttk.Frame(self, padding=(10, 2, 10, 6))
        bulk.pack(fill="x")
        ttk.Label(bulk, text="set wear for every listed disc (% of durability):").pack(side="left")
        self.bulk_pct = ttk.Entry(bulk, width=7)
        self.bulk_pct.pack(side="left", padx=6)
        ttk.Button(bulk, text="Apply to listed", command=self._apply_bulk).pack(side="left")
        ttk.Button(bulk, text="Snapshot", command=self._snapshot).pack(side="right", padx=4)
        ttk.Button(bulk, text="Compare snapshots…", command=self._open_compare).pack(side="right", padx=4)

        bottom = ttk.Frame(self, padding=(10, 4, 10, 10))
        bottom.pack(fill="x")
        self.write_button = ttk.Button(bottom, text="Write save", command=self._write)
        self.write_button.pack(side="left")
        ttk.Button(bottom, text="Discard staged", command=self._discard).pack(side="left", padx=6)
        ttk.Label(bottom, foreground="#555555",
                  text="Close the game before writing: the game rewrites the save when it quits.").pack(side="left", padx=10)

    # -------------------------------------------------------------- saves

    def _find_saves(self) -> None:
        self.locations = discover_saves()
        labels = [loc.label for loc in self.locations] + [BROWSE]
        self.location_var.set(self.locations[0].label if self.locations else BROWSE)
        self.save_menu["menu"].delete(0, "end")
        for label in labels:
            self.save_menu["menu"].add_command(label=label, command=lambda l=label: self._on_save_choice(l))
        if self.locations:
            self.reload()

    def _on_save_choice(self, label: str) -> None:
        self.location_var.set(label)
        if label == BROWSE:
            path = filedialog.askopenfilename(
                title="Pick a SaveFile.es3",
                filetypes=[("Easy Save 3 files", "*.es3"), ("all files", "*.*")],
            )
            if not path:
                return
            self.custom_path = path
            self.save = None
            self._load_path(path)
            return
        loc = next((l for l in self.locations if l.label == label), None)
        if loc:
            self._load_path(loc.path)

    def _current_location(self) -> SaveLocation | None:
        return next((l for l in self.locations if l.label == self.location_var.get()), None)

    def reload(self) -> None:
        loc = self._current_location()
        if loc is not None:
            self._load_path(loc.path)
            return
        if self.custom_path and os.path.isfile(self.custom_path):
            self._load_path(self.custom_path)
            return
        path = filedialog.askopenfilename(title="Pick a SaveFile.es3",
                                          filetypes=[("Easy Save 3 files", "*.es3"), ("all files", "*.*")])
        if path:
            self.custom_path = path
            self._load_path(path)

    def _load_path(self, path: str) -> None:
        try:
            self.save = DiscSave(path)
        except Exception as exc:  # a broken or in-flight save should not crash the tool
            messagebox.showerror("Could not read the save", f"{path}\n\n{exc}")
            self.save = None
            self.status_var.set("could not read save")
            return
        self.status_var.set(f"{len(self.save.discs)} discs  ·  modified "
                            f"{time.strftime('%Y-%m-%d %H:%M', time.localtime(os.path.getmtime(path)))}")
        self._update_running_warning()
        self._refresh_rows()
        self._update_staged_label()

    def _update_running_warning(self) -> None:
        """Warn while the game is running: its quit-save would cover ours."""
        loc = self._current_location()
        exe = loc.exe_name if loc else "True Disc Golf.exe"
        if process_is_running(exe):
            self.warning_var.set(f"WARNING: {exe} is running — its own save on quit will overwrite edits")
        else:
            self.warning_var.set("")

    def _warn_loop(self) -> None:
        self._update_running_warning()
        self._warn_job = self.after(6000, self._warn_loop)

    # -------------------------------------------------------------- rows

    def _visible_discs(self) -> list[Disc]:
        if not self.save:
            return []
        out = []
        search = self.search_var.get().strip().lower()
        for d in self.save.discs:
            if self.bag_only.get() and not d.bag_category:
                continue
            if self.category_var.get() != "all" and d.disc_type != self.category_var.get():
                continue
            if search and search not in " ".join([d.name, d.maker, d.plastic, d.prefab]).lower():
                continue
            out.append(d)
        return out

    def _refresh_rows(self) -> None:
        if not self.save:
            return
        selected = self.selected_index
        visible = {d.index for d in self._visible_discs()}
        self.tree.delete(*self.tree.get_children())
        for d in self.save.discs:
            if d.index not in visible:
                continue
            staged = self.save.staged_for(d.index)
            wear_text = self.save.preview_wear(d.index)
            durability = staged.get("durability", d.durability)
            weight = staged.get("paino", d.weight)
            worn = f"{d.wear_percent:.0f}%" if "wear" not in staged else "will change"
            values = (
                f"#{d.numero}",
                d.disc_type,
                d.bag_text(),
                d.name,
                d.maker,
                d.plastic,
                str(d.speed),
                f"{weight:g}" if isinstance(weight, (int, float)) else str(weight),
                f"{durability:g}",
                wear_text,
                worn,
                "★" if d.favourite else "",
            )
            tag = "staged" if staged else ("bag" if d.bag_category else "box")
            self.tree.insert("", "end", iid=str(d.index), values=values, tags=(tag,))
        self.tree.tag_configure("staged", background="#fff3cd")
        self.tree.tag_configure("box", foreground="#777777")
        if selected is not None and self.tree.exists(str(selected)):
            self.tree.selection_set(str(selected))
        self._update_staged_label()

    def _update_staged_label(self) -> None:
        count = len(self.save.staged) if self.save else 0
        self.staged_var.set(f"staged changes: {count}")
        self.write_button.configure(state="normal" if count else "disabled")

    # -------------------------------------------------------------- detail

    def _on_select(self, _event=None) -> None:
        sel = self.tree.selection()
        if not sel:
            return
        self.selected_index = int(sel[0])
        disc = self.save.discs[self.selected_index]
        staged = self.save.staged_for(disc.index)
        self.detail_title.configure(text=disc.label)
        max_value = max(disc.durability, 1.0)
        self.wear_scale.configure(to=max_value)
        wear = staged.get("wear", disc.wear)
        self.wear_scale.set(min(max(wear, 0.0), max_value))
        self.wear_entry.delete(0, "end")
        self.wear_entry.insert(0, f"{wear:g}")
        self._update_wear_pct()
        self.durability_entry.delete(0, "end")
        self.durability_entry.insert(0, f"{staged.get('durability', disc.durability):g}")
        self.weight_entry.delete(0, "end")
        self.weight_entry.insert(0, f"{staged.get('paino', disc.weight):g}" if
                                 isinstance(staged.get("paino", disc.weight), (int, float)) else str(staged.get("paino", disc.weight)))
        self.favourite_var.set(staged.get("favourite", disc.favourite))

    def _update_wear_pct(self) -> None:
        disc = self._selected_disc()
        if disc is None or not disc.durability:
            self.wear_pct_var.set("")
            return
        try:
            wear = float(self.wear_entry.get())
        except ValueError:
            self.wear_pct_var.set("")
            return
        self.wear_pct_var.set(f"{100.0 * wear / disc.durability:.0f}%")

    def _selected_disc(self) -> Disc | None:
        if self.save is None or self.selected_index is None:
            return None
        return self.save.discs[self.selected_index]

    def _on_slide(self, value: str) -> None:
        if not self.wear_entry:
            return
        number = float(value)
        self.wear_entry.delete(0, "end")
        self.wear_entry.insert(0, f"{number:g}")
        self._update_wear_pct()

    def _preset(self, fraction: float) -> None:
        disc = self._selected_disc()
        if disc is None:
            return
        value = fraction * disc.durability
        self.wear_scale.set(min(value, float(self.wear_scale["to"])))
        self.wear_entry.delete(0, "end")
        self.wear_entry.insert(0, f"{value:g}")
        self._update_wear_pct()
        self._stage_selected()

    def _stage_selected(self) -> None:
        disc = self._selected_disc()
        if disc is None or self.save is None:
            return
        try:
            wear = float(self.wear_entry.get())
            durability = float(self.durability_entry.get())
            weight = float(self.weight_entry.get())
        except ValueError:
            messagebox.showwarning("Check the values", "wear, durability and weight must be numbers")
            return
        try:
            self.save.stage(disc.index, "wear", wear)
            self.save.stage(disc.index, "durability", durability)
            self.save.stage(disc.index, "paino", weight)
            self.save.stage(disc.index, "favourite", self.favourite_var.get())
        except ValueError as exc:
            messagebox.showwarning("Check the values", str(exc))
            return
        self._refresh_rows()
        self._update_staged_label()

    def _revert_selected(self) -> None:
        disc = self._selected_disc()
        if disc is None or self.save is None:
            return
        for field in list(self.save.staged):
            if field[0] == disc.index:
                self.save.staged.pop(field)
        self._on_select()
        self._refresh_rows()

    # -------------------------------------------------------------- bulk, write, snapshots

    def _apply_bulk(self) -> None:
        if self.save is None:
            return
        try:
            percent = float(self.bulk_pct.get())
        except ValueError:
            messagebox.showwarning("Check the value", "type a percentage of durability, e.g. 50")
            return
        if not 0 <= percent <= 100:
            messagebox.showwarning("Check the value", "use 0 to 100 percent")
            return
        discs = self._visible_discs()
        for d in discs:
            try:
                self.save.stage(d.index, "wear", percent / 100.0 * d.durability)
            except ValueError as exc:
                messagebox.showwarning("Check the value", str(exc))
                return
        self._refresh_rows()
        self._update_staged_label()

    def _discard(self) -> None:
        if self.save:
            self.save.clear_staged()
        self._refresh_rows()
        self._update_staged_label()

    def _write(self) -> None:
        if self.save is None or not self.save.has_changes:
            return
        loc = self._current_location()
        running = process_is_running(loc.exe_name) if loc else process_is_running("True Disc Golf.exe")
        if running:
            if not messagebox.askyesno(
                "The game is running",
                "The game is running. When it quits it rewrites the save and your edits are lost.\n\n"
                "Write anyway?",
            ):
                return
        try:
            backup = self.save.save(backup=True)
        except Exception as exc:
            messagebox.showerror("Write failed", str(exc))
            return
        self._refresh_rows()
        self._update_staged_label()
        self.status_var.set(f"wrote {self.save.path}")
        messagebox.showinfo("Saved", f"Wrote {self.save.path}\nBackup: {backup}")

    def _snapshot(self) -> None:
        if self.save is None:
            return
        tag = messagebox.askstring("Snapshot", "Name this snapshot (for example: before)") or ""
        try:
            dest = snapshots.snapshot(self.save.path, tag=tag)
        except OSError as exc:
            messagebox.showerror("Snapshot failed", str(exc))
            return
        messagebox.showinfo("Snapshot saved", dest)

    def _open_compare(self) -> None:
        CompareWindow(self)

    # -------------------------------------------------------------- keyboard

    def _bind_keys(self) -> None:
        self.bind("<F5>", lambda _e: self.reload())
        self.bind("<Control-s>", lambda _e: self._write())


class CompareWindow(tk.Toplevel):
    """Pick two snapshots and show every value that moved between them."""

    def __init__(self, app: App) -> None:
        super().__init__(app)
        self.title("Compare save snapshots")
        self.geometry("820x520")
        self.app = app
        self.found = snapshots.list_snapshots()
        frame = ttk.Frame(self, padding=8)
        frame.pack(fill="both", expand=True)
        ttk.Label(frame, text="before").grid(row=0, column=0, sticky="w")
        self.before_var = tk.StringVar(value=self.found[-2] if len(self.found) > 1 else (self.found[0] if self.found else ""))
        self.after_var = tk.StringVar(value=self.found[-1] if self.found else "")
        self.before_menu = ttk.OptionMenu(frame, self.before_var, self.before_var.get(), *self._labels())
        self.before_menu.grid(row=0, column=1, sticky="ew", pady=2)
        ttk.Label(frame, text="after").grid(row=1, column=0, sticky="w")
        self.after_menu = ttk.OptionMenu(frame, self.after_var, self.after_var.get(), *self._labels())
        self.after_menu.grid(row=1, column=1, sticky="ew", pady=2)
        ttk.Button(frame, text="Compare", command=self._compare).grid(row=2, column=0, sticky="w", pady=6)
        ttk.Button(frame, text="Snapshot current save", command=self._snapshot_current).grid(row=2, column=1, sticky="e", pady=6)
        frame.columnconfigure(1, weight=1)
        self.report = tk.Text(frame, wrap="none", font=("Consolas", 10))
        self.report.grid(row=3, column=0, columnspan=2, sticky="nsew")
        frame.rowconfigure(3, weight=1)
        self._compare()

    def _labels(self) -> list[str]:
        return self.found or ["(no snapshots in saves/)"]

    def _snapshot_current(self) -> None:
        if not self.app.save:
            return
        tag = messagebox.askstring("Snapshot", "Name this snapshot (for example: after)") or ""
        self.found = snapshots.list_snapshots(snapshots.snapshot_dir())
        newest = snapshots.snapshot(self.app.save.path, tag=tag)
        self.found = snapshots.list_snapshots(snapshots.snapshot_dir())
        names = tuple(self.found)
        self.after_menu["menu"].delete(0, "end")
        for name in names:
            self.after_menu["menu"].add_command(label=name, command=lambda n=name: self.after_var.set(n))
        self.after_var.set(newest)
        self._compare()

    def _compare(self) -> None:
        a, b = self.before_var.get(), self.after_var.get()
        if not (a and b and os.path.isfile(a) and os.path.isfile(b)):
            self.report.delete("1.0", "end")
            self.report.insert("1.0", "Pick two snapshot files. Snapshots live in the project's saves/ folder.")
            return
        self.report.delete("1.0", "end")
        self.report.insert("1.0", snapshots.format_diff(a, b))


def run() -> None:
    app = App()
    app.mainloop()
