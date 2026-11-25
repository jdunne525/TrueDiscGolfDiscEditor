"""Tests for the tkinter window's behaviour without showing a window.

Run with:  python -m unittest discover -s tests
"""

from __future__ import annotations

import os
import shutil
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from tdgedit import es3  # noqa: E402
from tdgedit.savefile import SaveLocation  # noqa: E402

from test_es3 import FIXTURE  # noqa: E402


class GuiCase(unittest.TestCase):
    def setUp(self) -> None:
        import tkinter as tk

        import tdgedit.gui as gui
        import tdgedit.savefile as savefile

        self.gui = gui
        self.tmp = tempfile.mkdtemp(prefix="tdg-gui-")
        self.path = os.path.join(self.tmp, "SaveFile.es3")
        with open(self.path, "w", encoding="utf-8", newline="") as fh:
            fh.write(FIXTURE)
        self.location = SaveLocation(label="Test save", path=self.path, exe_name="Not Running.exe")

        # no popups, no file dialogs, no game-process probe; popups are recorded so a test
        # can see what was said to the user, and their answers are set per test
        self.answers = {"askyesno": True, "askstring": "tag"}
        self.shown: list[tuple[str, tuple]] = []
        answers, shown = self.answers, self.shown
        self.gui.messagebox = type(
            "SilentBox",
            (),
            {
                "showerror": staticmethod(lambda *a, **k: shown.append(("showerror", a))),
                "showwarning": staticmethod(lambda *a, **k: shown.append(("showwarning", a))),
                "showinfo": staticmethod(lambda *a, **k: shown.append(("showinfo", a))),
                "askyesno": staticmethod(lambda *a, **k: shown.append(("askyesno", a)) or bool(answers["askyesno"])),
                "askstring": staticmethod(lambda *a, **k: shown.append(("askstring", a)) or answers["askstring"]),
            },
        )
        self.gui.filedialog = type("SilentDialog", (), {"askopenfilename": staticmethod(lambda **k: "")})
        self.gui.process_is_running = lambda name: False
        savefile.discover_saves = lambda: [self.location]
        gui.discover_saves = lambda: [self.location]
        self.gui.snapshots.snapshot_dir = lambda: self.tmp

        try:
            self.app = gui.App()
        except tk.TclError as exc:  # a machine with no display
            shutil.rmtree(self.tmp, ignore_errors=True)
            self.skipTest(f"no display available: {exc}")
        self.app.withdraw()

    def tearDown(self) -> None:
        if getattr(self, "app", None) is not None:
            self.app.destroy()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def pump(self) -> None:
        self.app.update()

    def select(self, row: int = 0) -> None:
        """Select a tree row the way a click does."""
        self.app.tree.selection_set(self.app.tree.get_children()[row])
        self.app._on_select()
        self.pump()

    def said(self, kind: str, needle: str) -> bool:
        return any(k == kind and needle.lower() in " ".join(str(x) for x in args).lower() for k, args in self.shown)

    def test_the_window_opens_with_the_risk_of_a_corrupt_save(self) -> None:
        self.assertTrue(self.said("showwarning", "corrupt") or self.said("showwarning", "unusable"))
        self.assertTrue(self.said("showwarning", "backup"))
        self.assertIn("backup", self.app.risk_label.cget("text").lower())

    def test_snapshot_and_compare_buttons_are_not_in_the_window(self) -> None:
        wanted = {"Snapshot", "Compare snapshots…"}
        buttons: list[str] = []

        def walk(widget: object) -> None:
            for child in widget.winfo_children():
                if child.winfo_class() == "TButton":
                    buttons.append(str(child.cget("text")))
                walk(child)

        walk(self.app)
        self.assertIn("Write save", buttons)
        self.assertIn("Apply to listed", buttons)
        self.assertEqual([t for t in buttons if t in wanted], [])
        # the functionality is kept, for the command line and for scripts
        self.assertTrue(callable(self.app._snapshot))
        self.assertTrue(callable(self.gui.CompareWindow))

    def test_loads_the_discs_into_the_tree(self) -> None:
        self.pump()
        rows = self.app.tree.get_children()
        self.assertEqual(len(rows), 2)
        values = self.app.tree.item(rows[0], "values")
        self.assertEqual(values[0], "#3")
        self.assertEqual(values[3], "P2")
        self.assertEqual(values[9], "0")          # wear
        self.assertEqual(values[10], "0%")        # worn
        self.assertEqual(str(self.app.write_button["state"]), "disabled")

    def test_selecting_a_disc_fills_the_detail_panel(self) -> None:
        self.pump()
        self.app.tree.selection_set(self.app.tree.get_children()[1])
        self.app._on_select()
        self.pump()
        self.assertEqual(self.app.selected_index, 1)
        self.assertIn("Firebird", self.app.detail_title.cget("text"))
        self.assertEqual(self.app.wear_entry.get(), "0")
        self.assertEqual(float(self.app.wear_scale["to"]), 5000.0)
        self.assertEqual(self.app.durability_entry.get(), "5000")
        self.assertEqual(self.app.weight_entry.get(), "175")

    def test_preset_stages_wear_and_marks_the_row(self) -> None:
        self.pump()
        self.app.tree.selection_set(self.app.tree.get_children()[1])
        self.app._on_select()
        self.app._preset(0.5)
        self.pump()
        self.assertEqual(self.app.wear_entry.get(), "2500")
        self.assertEqual(self.app.save.staged_for(1)["wear"], 2500)
        self.assertEqual(self.app.tree.item("1", "values")[9], "0 -> 2500")
        self.assertEqual(self.app.staged_var.get(), "staged changes: 1")
        self.assertEqual(str(self.app.write_button["state"]), "normal")

    def test_typing_a_wear_value_stages_it(self) -> None:
        self.pump()
        self.app.tree.selection_set(self.app.tree.get_children()[0])
        self.app._on_select()
        self.app.wear_entry.delete(0, "end")
        self.app.wear_entry.insert(0, "640")
        self.app._stage_selected()
        self.pump()
        self.assertEqual(self.app.save.staged_for(0)["wear"], 640)
        self.assertEqual(self.app.wear_pct_var.get(), "32%")

    def test_writing_from_the_window_changes_only_wear(self) -> None:
        self.pump()
        self.app.tree.selection_set(self.app.tree.get_children()[1])
        self.app._on_select()
        self.app._preset(0.75)
        before = es3.read_text(self.path)
        self.app._write()
        self.pump()
        after = es3.read_text(self.path)
        self.assertEqual(len(after) - len(before), len("3750") - len("0"))
        discs = es3.parse(after)["kiekot"]["value"]
        self.assertEqual(discs[1]["wear"], 3750)
        self.assertEqual(discs[0]["wear"], 0)
        self.assertFalse(self.app.save.has_changes)
        self.assertEqual(self.app.tree.item("1", "values")[9], "3750")
        self.assertEqual(self.app.tree.item("1", "values")[10], "75%")

    def test_a_value_that_is_not_a_number_is_refused(self) -> None:
        self.pump()
        self.app.tree.selection_set(self.app.tree.get_children()[0])
        self.app._on_select()
        self.app.wear_entry.delete(0, "end")
        self.app.wear_entry.insert(0, "lots")
        self.app._stage_selected()
        self.pump()
        self.assertFalse(self.app.save.has_changes)
        self.assertEqual(str(self.app.write_button["state"]), "disabled")

    def test_bulk_apply_covers_the_filtered_list(self) -> None:
        self.pump()
        self.app.category_var.set("driver")
        self.app._refresh_rows()
        self.pump()
        self.assertEqual(len(self.app.tree.get_children()), 1)
        self.app.bulk_pct.insert(0, "50")
        self.app._apply_bulk()
        self.pump()
        self.assertEqual(self.app.save.staged_for(1)["wear"], 2500)

    def test_bag_filter_hides_nothing_here_and_search_filters(self) -> None:
        self.pump()
        self.app.bag_only.set(True)
        self.app._refresh_rows()
        self.assertEqual(len(self.app.tree.get_children()), 2)
        self.app.search_var.set("P2")
        self.app._refresh_rows()
        self.pump()
        self.assertEqual(len(self.app.tree.get_children()), 1)

    def test_discard_clears_staged_changes(self) -> None:
        self.pump()
        self.app.tree.selection_set(self.app.tree.get_children()[0])
        self.app._on_select()
        self.app._preset(1.0)
        self.assertTrue(self.app.save.has_changes)
        self.app._discard()
        self.pump()
        self.assertFalse(self.app.save.has_changes)
        self.assertEqual(self.app.tree.item("0", "values")[9], "0")

    def test_reload_asks_when_staged_edits_would_be_lost(self) -> None:
        self.pump()
        self.select(1)
        self.app._preset(0.5)
        self.pump()
        self.assertTrue(self.app.save.has_changes)
        self.answers["askyesno"] = False
        self.app.reload()
        self.pump()
        self.assertTrue(self.said("askyesno", "not been written"))
        self.assertTrue(self.app.save.has_changes)          # refused: nothing is thrown away
        self.assertEqual(self.app.tree.item("1", "values")[9], "0 -> 2500")

    def test_reload_proceeds_when_the_user_accepts_losing_them(self) -> None:
        self.pump()
        self.select(1)
        self.app._preset(0.5)
        self.answers["askyesno"] = True
        self.app.reload()
        self.pump()
        self.assertFalse(self.app.save.has_changes)
        self.assertEqual(self.app.tree.item("1", "values")[9], "0")

    def test_changing_the_save_file_prompted_the_same_way(self) -> None:
        self.pump()
        self.select(0)
        self.app._preset(1.0)
        self.answers["askyesno"] = False
        self.app._on_save_choice("Test save")
        self.pump()
        self.assertTrue(self.said("askyesno", "Opening Test save"))
        self.assertTrue(self.app.save.has_changes)
        self.assertEqual(self.app.location_var.get(), "Test save")

    def test_no_prompt_when_there_is_nothing_unwritten(self) -> None:
        self.pump()
        self.app.reload()
        self.pump()
        self.assertEqual([k for k, _ in self.shown if k == "askyesno"], [])

    def test_browsing_then_cancelling_keeps_the_shown_save(self) -> None:
        self.pump()
        self.select(0)
        self.app._preset(0.5)
        self.app._on_save_choice(self.gui.BROWSE)   # the stubbed dialog picks nothing
        self.pump()
        self.assertEqual(self.app.location_var.get(), "Test save")
        self.assertTrue(self.app.save.has_changes)
        self.assertEqual(len(self.app.tree.get_children()), 2)

    def test_browsing_to_a_picked_file_loads_it_and_drops_staged_edits(self) -> None:
        self.pump()
        self.select(0)
        self.app._preset(0.5)
        picked = self.path
        self.gui.filedialog = type("PickedDialog", (),
                                   {"askopenfilename": staticmethod(lambda **k: picked)})
        self.app._on_save_choice(self.gui.BROWSE)
        self.pump()
        self.assertEqual(self.app.custom_path, picked)
        self.assertEqual(len(self.app.tree.get_children()), 2)
        self.assertFalse(self.app.save.has_changes)

    def test_writing_after_the_file_changed_on_disk_writes_nothing(self) -> None:
        self.pump()
        self.select(1)
        self.app._preset(0.75)
        rewritten = FIXTURE.replace('"playerstutorial" : {', '"playerstutorial2" : {')
        with open(self.path, "w", encoding="utf-8", newline="") as fh:
            fh.write(rewritten)
        self.app._write()
        self.pump()
        self.assertEqual(es3.read_text(self.path), rewritten)   # the game's file is untouched
        self.assertFalse([n for n in os.listdir(self.tmp) if ".bak-" in n])
        self.assertTrue(self.said("showwarning", "changed since"))
        self.assertTrue(self.said("showwarning", "Reload"))
        self.assertEqual(self.app.status_var.get(), "not written: the save changed since it was read")
        self.assertTrue(self.app.save.has_changes)              # still listed, not applied
        self.assertEqual(str(self.app.write_button["state"]), "normal")

    def test_writing_tells_the_user_where_the_backup_went(self) -> None:
        self.pump()
        self.select(1)
        self.app._preset(0.5)
        self.app._write()
        self.pump()
        backups = [n for n in os.listdir(self.tmp) if ".bak-" in n]
        self.assertEqual(len(backups), 1)
        self.assertTrue(self.said("showinfo", "Backup"))
        self.assertEqual(es3.read_text(os.path.join(self.tmp, backups[0])), FIXTURE)

    def test_snapshot_still_copies_the_save(self) -> None:
        self.pump()
        self.app._snapshot()
        self.pump()
        found = [n for n in os.listdir(self.tmp) if n.endswith(".es3") and n.startswith("snapshot-")]
        self.assertEqual(len(found), 1)
        self.assertEqual(es3.read_text(os.path.join(self.tmp, found[0])), FIXTURE)

    def test_compare_window_reports_the_wear_difference(self) -> None:
        self.pump()
        before = self.gui.snapshots.snapshot(self.path, tag="before", dest_dir=self.tmp)
        save = self.gui.DiscSave(self.path)
        save.stage(0, "wear", 300)
        save.save()
        after = self.gui.snapshots.snapshot(self.path, tag="after", dest_dir=self.tmp)
        window = self.gui.CompareWindow(self.app)
        window.before_var.set(before)
        window.after_var.set(after)
        window._compare()
        text = window.report.get("1.0", "end")
        self.assertIn("kiekot.value[0].wear: 0 -> 300", text)
        self.assertIn("wear fields that changed", text)
        window.destroy()


if __name__ == "__main__":
    unittest.main()
