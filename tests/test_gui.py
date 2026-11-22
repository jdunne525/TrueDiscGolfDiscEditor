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

        # no popups, no file dialogs, no game-process probe
        self.gui.messagebox = type(
            "SilentBox",
            (),
            {
                "showerror": staticmethod(lambda *a, **k: None),
                "showwarning": staticmethod(lambda *a, **k: None),
                "showinfo": staticmethod(lambda *a, **k: None),
                "askyesno": staticmethod(lambda *a, **k: True),
                "askstring": staticmethod(lambda *a, **k: "tag"),
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

    def test_snapshot_button_copies_the_save(self) -> None:
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
