"""Tests for the snapshot/diff calibration loop and the command line front end.

Run with:  python -m unittest discover -s tests
"""

from __future__ import annotations

import contextlib
import io
import json
import os
import shutil
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from tdgedit import cli, es3, snapshots  # noqa: E402
from tdgedit.savefile import DiscSave  # noqa: E402

from test_es3 import FIXTURE  # noqa: E402  (tests/ is on sys.path when unittest discovers it)


class TempSaveCase(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.mkdtemp(prefix="tdg-tool-")
        self.path = os.path.join(self.tmp, "SaveFile.es3")
        with open(self.path, "w", encoding="utf-8", newline="") as fh:
            fh.write(FIXTURE)
        self.saves = os.path.join(self.tmp, "saves")

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def run_cli(self, *argv: str) -> tuple[int, str]:
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = cli.main(list(argv))
        return code, out.getvalue()


class TestSnapshots(TempSaveCase):
    def test_snapshot_copies_and_lists(self) -> None:
        dest = snapshots.snapshot(self.path, tag="before", dest_dir=self.saves)
        self.assertTrue(os.path.isfile(dest))
        self.assertIn("-before-", os.path.basename(dest))
        self.assertEqual(es3.read_text(dest), FIXTURE)
        self.assertEqual(snapshots.list_snapshots(self.saves), [dest])

    def test_diff_names_only_the_changed_wear(self) -> None:
        before = snapshots.snapshot(self.path, tag="before", dest_dir=self.saves)
        save = DiscSave(self.path)
        save.stage(1, "wear", 1500)
        save.save()
        after = snapshots.snapshot(self.path, tag="after", dest_dir=self.saves)
        changes = snapshots.diff_files(before, after)
        self.assertEqual([c[0] for c in changes], ["kiekot.value[1].wear"])
        self.assertEqual(changes[0][1], 0)
        self.assertEqual(changes[0][2], 1500)
        report = snapshots.format_diff(before, after)
        self.assertIn("wear fields that changed", report)
        self.assertIn("#7 Firebird™ beat up (driver slot 4)", report)
        self.assertIn("delta +1500", report)

    def test_diff_of_identical_says_so(self) -> None:
        a = snapshots.snapshot(self.path, tag="a", dest_dir=self.saves)
        b = snapshots.snapshot(self.path, tag="b", dest_dir=self.saves)
        self.assertEqual(snapshots.diff_files(a, b), [])
        self.assertIn("No differences", snapshots.format_diff(a, b))

    def test_diff_sees_changes_outside_the_disc_list_too(self) -> None:
        """If wear were tracked somewhere else as well, the diff would show that path."""
        before = snapshots.snapshot(self.path, tag="before", dest_dir=self.saves)
        data = json.loads(FIXTURE)
        data["asetukset"]["value"]["pelaaja"]["height"] = 180
        with open(self.path, "w", encoding="utf-8", newline="") as fh:
            fh.write(json.dumps(data, indent="\t"))
        after = snapshots.snapshot(self.path, tag="after", dest_dir=self.saves)
        paths = [c[0] for c in snapshots.diff_files(before, after)]
        self.assertIn("asetukset.value.pelaaja.height", paths)

    def test_tag_is_sanitised(self) -> None:
        dest = snapshots.snapshot(self.path, tag="before the round!", dest_dir=self.saves)
        self.assertNotIn("!", os.path.basename(dest))


class TestCli(TempSaveCase):
    def test_list_prints_the_bag_and_wear(self) -> None:
        code, out = self.run_cli("list", "--save", self.path)
        self.assertEqual(code, 0)
        self.assertIn("P2", out)
        self.assertIn("Firebird", out)
        self.assertIn("driver #4", out)
        self.assertIn("2 discs", out)

    def test_set_wear_by_number_writes_and_backs_up(self) -> None:
        code, out = self.run_cli("set", "--disc", "#7", "--wear", "3000", "--save", self.path)
        self.assertEqual(code, 0, out)
        self.assertIn("backup of the file", out)
        discs = es3.parse_file(self.path)["kiekot"]["value"]
        self.assertEqual(discs[1]["wear"], 3000)
        self.assertEqual(discs[0]["wear"], 0)
        backups = [n for n in os.listdir(self.tmp) if n.startswith("SaveFile.es3.bak-")]
        self.assertEqual(len(backups), 1)
        self.assertEqual(es3.read_text(os.path.join(self.tmp, backups[0])), FIXTURE)

    def test_a_file_written_after_the_read_is_not_edited(self) -> None:
        """The game saving while the command runs means the values go into a stale copy."""
        original = cli.DiscSave

        class RacingSave(original):
            def __init__(self, path: str) -> None:
                super().__init__(path)
                es3.write_text(self.path, self.text.replace('"playerstutorial"', '"playerstutorial2"'))

        cli.DiscSave = RacingSave
        self.addCleanup(setattr, cli, "DiscSave", original)
        code, out = self.run_cli("set", "--disc", "#7", "--wear", "3000", "--save", self.path)
        self.assertEqual(code, 2, out)
        self.assertIn("Nothing was written", out)
        self.assertIn("Run the command again", out)
        self.assertEqual(es3.read_text(self.path), FIXTURE.replace('"playerstutorial"', '"playerstutorial2"'))
        self.assertFalse([n for n in os.listdir(self.tmp) if ".bak-" in n])

    def test_disclaimer_is_printed(self) -> None:
        code, out = self.run_cli("disclaimer")
        self.assertEqual(code, 0)
        self.assertIn("no warranty", out.lower())
        self.assertIn("backup", out.lower())
        self.assertIn("SaveFile.es3.bak", out)

    def test_set_wear_pct_uses_durability(self) -> None:
        code, _ = self.run_cli("set", "--disc", "#3", "--wear-pct", "50", "--save", self.path)
        self.assertEqual(code, 0)
        self.assertEqual(es3.parse_file(self.path)["kiekot"]["value"][0]["wear"], 1000)

    def test_set_by_category(self) -> None:
        code, _ = self.run_cli("set", "--disc", "driver", "--wear-pct", "100", "--save", self.path)
        self.assertEqual(code, 0)
        discs = es3.parse_file(self.path)["kiekot"]["value"]
        self.assertEqual([d["wear"] for d in discs], [0, 5000])

    def test_dry_run_writes_nothing(self) -> None:
        code, out = self.run_cli("set", "--disc", "all", "--wear", "10", "--dry-run", "--save", self.path)
        self.assertEqual(code, 0)
        self.assertIn("not written", out)
        self.assertEqual(es3.read_text(self.path), FIXTURE)

    def test_nothing_to_change_is_reported(self) -> None:
        code, out = self.run_cli("set", "--disc", "#3", "--save", self.path)
        self.assertEqual(code, 1)
        self.assertIn("Nothing to change", out)

    def test_wear_and_wear_pct_together_are_refused(self) -> None:
        code, out = self.run_cli("set", "--disc", "#3", "--wear", "10", "--wear-pct", "50", "--save", self.path)
        self.assertEqual(code, 1)
        self.assertIn("not both", out)
        self.assertEqual(es3.read_text(self.path), FIXTURE)

    def test_wear_pct_out_of_range_is_refused(self) -> None:
        code, out = self.run_cli("set", "--disc", "#3", "--wear-pct", "150", "--save", self.path)
        self.assertEqual(code, 1)
        self.assertIn("0 to 100", out)
        self.assertEqual(es3.read_text(self.path), FIXTURE)

    def test_negative_wear_is_refused_without_a_traceback(self) -> None:
        code, out = self.run_cli("set", "--disc", "#3", "--wear", "-10", "--save", self.path)
        self.assertEqual(code, 1)
        self.assertIn("cannot be negative", out)
        self.assertEqual(es3.read_text(self.path), FIXTURE)

    def test_unknown_disc_fails(self) -> None:
        with self.assertRaises(SystemExit):
            self.run_cli("set", "--disc", "nope", "--wear", "1", "--save", self.path)

    def test_snapshot_and_diff_commands(self) -> None:
        code, out = self.run_cli("snapshot", "--tag", "before", "--dest", self.saves, "--save", self.path)
        self.assertEqual(code, 0)
        before = out.strip()
        save = DiscSave(self.path)
        save.stage(0, "wear", 400)
        save.save()
        self.run_cli("snapshot", "--tag", "after", "--dest", self.saves, "--save", self.path)
        after = next(p for p in snapshots.list_snapshots(self.saves) if "-after-" in os.path.basename(p))
        self.assertNotEqual(after, before)
        code, out = self.run_cli("diff", before, after)
        self.assertEqual(code, 0)
        self.assertIn("kiekot.value[0].wear: 0 -> 400", out)

    def test_snapshots_command_lists_the_default_folder(self) -> None:
        code, out = self.run_cli("snapshots")
        listed = [line for line in out.splitlines() if line.endswith(".es3")]
        if code == 0:
            self.assertTrue(listed)
        else:
            self.assertIn("No snapshots yet", out)


if __name__ == "__main__":
    unittest.main()
