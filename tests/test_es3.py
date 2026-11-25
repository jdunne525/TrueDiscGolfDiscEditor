"""Tests for the ES3 text editing that the editor relies on.

Run with:  python -m unittest discover -s tests
"""

from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from tdgedit import es3  # noqa: E402
from tdgedit.savefile import DiscSave, SaveChangedError  # noqa: E402

BASELINE = os.path.join(ROOT, "saves", "sample-save.es3")

FIXTURE = """{
\t"asetukset" : {
\t\t"__type" : "Peli+asetuksetArray,Assembly-CSharp",
\t\t"value" : {
\t\t\t"versio" : 0.92,
\t\t\t"pelaaja" : {
\t\t\t\t"height" : 0,
\t\t\t\t"righthand" : true
\t\t\t}
\t\t}
\t},
\t"kiekotbagissa" : {
\t\t"__type" : "Kiekot+kiekotbagissaArray,Assembly-CSharp",
\t\t"value" : {
\t\t\t"putterit" : [
\t\t\t\t{ "kiekkonumero" : 3, "bagnumero" : 0 }
\t\t\t],
\t\t\t"driverit" : [
\t\t\t\t{ "kiekkonumero" : 7, "bagnumero" : 4 }
\t\t\t]
\t\t}
\t},
\t"kiekot" : {
\t\t"__type" : "System.Collections.Generic.List`1[[Kiekot+kiekotArray, Assembly-CSharp, Version=0.0.0.0, Culture=neutral, PublicKeyToken=null]],mscorlib",
\t\t"value" : [
\t\t\t{
\t\t\t\t"numero" : 3,
\t\t\t\t"nopeus" : 2,
\t\t\t\t"tyyppi" : "putter",
\t\t\t\t"valmistaja" : "discmania",
\t\t\t\t"muovi" : "D-Line",
\t\t\t\t"nimi" : "P2",
\t\t\t\t"prefab" : "P2_d",
\t\t\t\t"paino" : 175,
\t\t\t\t"vari" : "F5AA06",
\t\t\t\t"wear" : 0,
\t\t\t\t"durability" : 2000,
\t\t\t\t"favourite" : false,
\t\t\t\t"custom" : null
\t\t\t},
\t\t\t{
\t\t\t\t"numero" : 7,
\t\t\t\t"nopeus" : 9,
\t\t\t\t"tyyppi" : "driver",
\t\t\t\t"valmistaja" : "innova",
\t\t\t\t"muovi" : "Champion",
\t\t\t\t"nimi" : "Firebird\\u2122 beat up",
\t\t\t\t"prefab" : "Firebird_champion",
\t\t\t\t"paino" : 175,
\t\t\t\t"vari" : "FF0000",
\t\t\t\t"wear" : 0,
\t\t\t\t"durability" : 5000,
\t\t\t\t"favourite" : false,
\t\t\t\t"custom" : null
\t\t\t}
\t\t]
\t},
\t"playerstutorial" : {
\t\t"__type" : "bool",
\t\t"value" : true
\t}
}
"""


class FixtureCase(unittest.TestCase):
    def setUp(self) -> None:
        self.text = FIXTURE


class TestSpans(FixtureCase):
    def test_disc_spans_are_the_disc_records(self) -> None:
        spans = es3.disc_spans(self.text)
        self.assertEqual(len(spans), 2)
        for span in spans:
            block = self.text[span.start:span.end]
            self.assertIn('"numero"', block)
            self.assertIn('"wear"', block)

    def test_top_level_key_span_covers_the_whole_block(self) -> None:
        _key, value = es3.find_top_level_key(self.text, "kiekot")
        self.assertTrue(self.text[value.start] == "{")
        self.assertTrue(self.text[value.end - 1] == "}")
        self.assertEqual(json.loads(self.text[value.start:value.end])["value"][0]["nimi"], "P2")

    def test_top_level_scalar_is_the_whole_object(self) -> None:
        key, value = es3.find_top_level_key(self.text, "playerstutorial")
        self.assertEqual(self.text[key.start : key.end], '"playerstutorial"')
        self.assertEqual(json.loads(self.text[value.start:value.end])["value"], True)

    def test_field_span_reads_a_scalar_field(self) -> None:
        block = self.text[es3.disc_spans(self.text)[0].start : es3.disc_spans(self.text)[0].end]
        local = es3.field_span(block, "favourite")
        self.assertEqual(block[local.start:local.end], "false")
        local = es3.field_span(block, "wear")
        self.assertEqual(block[local.start:local.end], "0")
        local = es3.field_span(block, "muovi")
        self.assertEqual(block[local.start:local.end], '"D-Line"')

    def test_missing_key_raises(self) -> None:
        with self.assertRaises(KeyError):
            es3.find_top_level_key(self.text, "nothere")


class TestEdits(FixtureCase):
    def test_only_the_number_moves(self) -> None:
        spans = es3.disc_spans(self.text)
        edits = es3.build_edits(self.text, spans, [(0, "wear", 1200)])
        self.assertEqual(len(edits), 1)
        new = es3.apply_edits(self.text, edits)
        self.assertEqual(new[: edits[0].start], self.text[: edits[0].start])
        self.assertEqual(new[edits[0].start + len("1200") :], self.text[edits[0].end :])
        self.assertEqual(new[edits[0].start : edits[0].start + len("1200")], "1200")
        self.assertEqual(len(new), len(self.text) + len("1200") - len("0"))

    def test_values_land_in_the_right_disc(self) -> None:
        spans = es3.disc_spans(self.text)
        new = es3.apply_edits(
            self.text,
            es3.build_edits(self.text, spans, [(0, "wear", 0), (1, "wear", 4300)]),
        )
        discs = es3.parse(new)["kiekot"]["value"]
        self.assertEqual(discs[0]["wear"], 0)
        self.assertEqual(discs[1]["wear"], 4300)
        self.assertEqual(discs[1]["durability"], 5000)

    def test_no_edit_when_the_value_is_already_right(self) -> None:
        spans = es3.disc_spans(self.text)
        self.assertEqual(es3.build_edits(self.text, spans, [(0, "wear", 0)]), [])

    def test_float_and_int_formats(self) -> None:
        self.assertEqual(es3.format_number(0), "0")
        self.assertEqual(es3.format_number(1200), "1200")
        self.assertEqual(es3.format_number(1200.0), "1200")
        self.assertEqual(es3.format_number(1250.5), "1250.5")
        self.assertEqual(es3.format_scalar(True), "true")
        self.assertEqual(es3.format_scalar(None), "null")

    def test_secondary_fields(self) -> None:
        spans = es3.disc_spans(self.text)
        new = es3.apply_edits(
            self.text,
            es3.build_edits(
                self.text,
                spans,
                [(1, "durability", 6000), (0, "paino", 172), (1, "favourite", True)],
            ),
        )
        discs = es3.parse(new)["kiekot"]["value"]
        self.assertEqual(discs[1]["durability"], 6000)
        self.assertEqual(discs[0]["paino"], 172)
        self.assertEqual(discs[1]["favourite"], True)
        self.assertEqual(discs[0]["favourite"], False)

    def test_change_field_values_over_every_record(self) -> None:
        new = es3.change_field_values(self.text, "kiekot", "wear", [100, 200])
        discs = es3.parse(new)["kiekot"]["value"]
        self.assertEqual([d["wear"] for d in discs], [100, 200])
        with self.assertRaises(ValueError):
            es3.change_field_values(self.text, "kiekot", "wear", [100])

    def test_unicode_names_survive(self) -> None:
        spans = es3.disc_spans(self.text)
        new = es3.apply_edits(self.text, es3.build_edits(self.text, spans, [(1, "wear", 500)]))
        self.assertEqual(es3.parse(new)["kiekot"]["value"][1]["nimi"], "Firebird™ beat up")
        self.assertIn("Firebird\\u2122", new)

    def test_other_keys_untouched(self) -> None:
        spans = es3.disc_spans(self.text)
        new = es3.apply_edits(self.text, es3.build_edits(self.text, spans, [(1, "wear", 900)]))
        before, after = es3.parse(self.text), es3.parse(new)
        for key in before:
            if key == "kiekot":
                continue
            self.assertEqual(before[key], after[key], key)


class TestDiscSave(FixtureCase):
    def setUp(self) -> None:
        super().setUp()
        self.tmp = tempfile.mkdtemp(prefix="tdg-test-")
        self.path = os.path.join(self.tmp, "SaveFile.es3")
        with open(self.path, "w", encoding="utf-8", newline="") as fh:
            fh.write(self.text)
        self.save = DiscSave(self.path)

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_reads_the_bag(self) -> None:
        self.assertEqual(len(self.save.discs), 2)
        putter, driver = self.save.discs
        self.assertEqual((putter.bag_category, putter.bag_slot), ("putter", 0))
        self.assertEqual((driver.bag_category, driver.bag_slot), ("driver", 4))
        self.assertEqual(driver.wear_percent, 0.0)

    def test_stage_then_save_writes_and_backs_up(self) -> None:
        self.save.stage(1, "wear", 2500)
        self.assertTrue(self.save.has_changes)
        backup = self.save.save()
        self.assertTrue(os.path.isfile(backup))
        with open(backup, encoding="utf-8", newline="") as fh:
            self.assertEqual(fh.read(), self.text)
        discs = es3.parse_file(self.path)["kiekot"]["value"]
        self.assertEqual(discs[1]["wear"], 2500)
        self.assertEqual(es3.read_text(backup), self.text)

    def test_stage_equal_value_stages_nothing(self) -> None:
        self.save.stage(0, "wear", 0)
        self.assertFalse(self.save.has_changes)

    def test_negative_wear_rejected(self) -> None:
        with self.assertRaises(ValueError):
            self.save.stage(0, "wear", -5)

    def test_text_that_is_not_a_number_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            self.save.stage(0, "wear", "lots")

    def test_two_writes_keep_their_own_backups(self) -> None:
        self.save.stage(0, "wear", 100)
        first = self.save.save()
        self.save.stage(1, "wear", 200)
        second = self.save.save()
        self.assertNotEqual(first, second)
        self.assertEqual(es3.read_text(first), self.text)
        discs = es3.parse_file(self.path)["kiekot"]["value"]
        self.assertEqual([d["wear"] for d in discs], [100, 200])

    def test_only_whitelisted_fields_are_editable(self) -> None:
        with self.assertRaises(ValueError):
            self.save.stage(0, "nimi", "something else")

    def test_a_file_written_after_reading_refuses_the_edit(self) -> None:
        """The game rewrote the save, so the staged edits belong to a file that is gone."""
        self.save.stage(0, "wear", 500)
        self.assertFalse(self.save.changed_on_disk())
        rewritten = self.text.replace('"playerstutorial"', '"playerstutorial2"')
        with open(self.path, "w", encoding="utf-8", newline="") as fh:
            fh.write(rewritten)
        self.assertTrue(self.save.changed_on_disk())
        with self.assertRaises(SaveChangedError):
            self.save.save()
        self.assertEqual(es3.read_text(self.path), rewritten)
        self.assertFalse([n for n in os.listdir(self.tmp) if ".bak-" in n])
        self.assertTrue(self.save.has_changes)

    def test_a_file_rewritten_to_the_same_bytes_still_writes(self) -> None:
        self.save.stage(0, "wear", 500)
        with open(self.path, "w", encoding="utf-8", newline="") as fh:
            fh.write(self.text)
        self.assertFalse(self.save.changed_on_disk())
        self.save.save()
        self.assertEqual(es3.parse_file(self.path)["kiekot"]["value"][0]["wear"], 500)

    def test_a_missing_file_refuses_the_edit(self) -> None:
        self.save.stage(0, "wear", 500)
        os.remove(self.path)
        with self.assertRaises(SaveChangedError):
            self.save.save()
        self.assertFalse([n for n in os.listdir(self.tmp) if ".bak-" in n])

    def test_every_edit_leaves_its_own_backup(self) -> None:
        self.save.stage(0, "wear", 100)
        first = self.save.save()
        self.save.stage(0, "wear", 200)
        second = self.save.save()
        self.assertEqual(es3.read_text(first), self.text)
        self.assertEqual(es3.read_text(second), self.text.replace('"wear" : 0', '"wear" : 100', 1))

    def test_reload_after_save_shows_new_wear(self) -> None:
        self.save.stage(0, "wear", 700)
        self.save.save()
        self.assertEqual(self.save.discs[0].wear, 700)
        self.assertEqual(self.save.discs[0].wear_percent, 35.0)
        self.assertFalse(self.save.has_changes)

    def test_preview_text_shows_pending_change(self) -> None:
        self.save.stage(0, "wear", 500)
        self.assertEqual(self.save.preview_wear(0), "0 -> 500")


class TestRealBaseline(unittest.TestCase):
    """The snapshot taken from the installed game, so the real file shape is covered."""

    @unittest.skipUnless(os.path.isfile(BASELINE), "baseline snapshot is not present")
    def test_reads_and_round_trips(self) -> None:
        text = es3.read_text(BASELINE)
        save = DiscSave(BASELINE)
        self.assertGreaterEqual(len(save.discs), 14)
        self.assertTrue(all(d.wear == 0 for d in save.discs))
        self.assertTrue(all(d.bag_category for d in save.discs))
        tmp = tempfile.mkdtemp(prefix="tdg-baseline-")
        try:
            copy = os.path.join(tmp, "SaveFile.es3")
            shutil.copyfile(BASELINE, copy)
            save = DiscSave(copy)
            save.stage(3, "wear", 1250.5)
            save.stage(5, "favourite", True)
            backup = save.save()
            written = es3.read_text(copy)
            self.assertEqual(es3.read_text(backup), text)
            # only the two tokens differ
            self.assertEqual(len(written) - len(text), len("1250.5") - len("0") + len("true") - len("false"))
            discs = es3.parse(written)["kiekot"]["value"]
            self.assertEqual(discs[3]["wear"], 1250.5)
            self.assertEqual(discs[5]["favourite"], True)
            self.assertEqual([d["wear"] for i, d in enumerate(discs) if i not in (3, 5)], [0] * (len(discs) - 2))
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
