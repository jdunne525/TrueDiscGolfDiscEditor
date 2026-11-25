"""The disc inventory as True Disc Golf stores it, plus where the saves live."""

from __future__ import annotations

import os
import subprocess
import time
from dataclasses import dataclass, field
from typing import Any

from . import es3

KIEKOT_KEY = "kiekot"
BAG_KEY = "kiekotbagissa"

# Categories in the bag key, in the order the game lists them.
BAG_CATEGORIES = (("putterit", "putter"), ("midranget", "midrange"), ("driverit", "driver"))

# Fields the editor is allowed to write. Everything else in the record is either the
# disc's identity (nimi/valmistaja/muovi/prefab decide the model the game loads) or a
# colour, which is not what this tool is for.
WRITABLE_FIELDS = {
    "wear": "number",
    "durability": "number",
    "paino": "number",
    "favourite": "bool",
}

# The two installs that write a save on this machine.
GAME_NAMES = ("True Disc Golf", "True Disc Golf demo")


def local_low_root() -> str:
    return os.path.join(os.environ.get("USERPROFILE", os.path.expanduser("~")), "AppData", "LocalLow")


def sportsmanlike_dir() -> str:
    return os.path.join(local_low_root(), "Sportsmanlike Games")


@dataclass
class SaveLocation:
    label: str
    path: str
    exe_name: str

    @property
    def exists(self) -> bool:
        return os.path.isfile(self.path)

    @property
    def mtime(self) -> float | None:
        try:
            return os.path.getmtime(self.path)
        except OSError:
            return None


def discover_saves() -> list[SaveLocation]:
    """Every ``SaveFile.es3`` under Sportsmanlike Games in LocalLow, game first, demo second."""
    root = sportsmanlike_dir()
    found: list[SaveLocation] = []
    for name in GAME_NAMES:
        path = os.path.join(root, name, "SaveFile.es3")
        if os.path.isfile(path):
            found.append(SaveLocation(label=name, path=path, exe_name=name + ".exe"))
    if os.path.isdir(root):  # anything else the same publisher leaves behind
        for entry in sorted(os.listdir(root)):
            path = os.path.join(root, entry, "SaveFile.es3")
            if os.path.isfile(path) and all(f.path != path for f in found):
                found.append(SaveLocation(label=entry, path=path, exe_name=entry + ".exe"))
    return found


class SaveChangedError(RuntimeError):
    """The file on disk is no longer the file the staged edits were made against.

    Raised instead of writing: applying edits to a save the game (or anything else) has
    rewritten in the meantime would either fail or quietly undo what was just written.
    """


def process_is_running(exe_name: str) -> bool:
    """True when the game is running, so a write would be thrown away when it quits."""
    try:
        out = subprocess.run(
            ["tasklist", "/NH", "/FI", f"IMAGENAME eq {exe_name}"],
            capture_output=True,
            text=True,
            timeout=10,
        ).stdout
    except (OSError, subprocess.SubprocessError):
        return False
    return exe_name.lower() in out.lower()


@dataclass
class Disc:
    index: int  # position in the kiekot list, which is also file order
    numero: int
    name: str
    maker: str
    plastic: str
    disc_type: str
    speed: Any
    weight: Any
    prefab: str
    wear: float
    durability: float
    favourite: bool
    colors: dict[str, str] = field(default_factory=dict)
    custom: Any = None
    raw: dict[str, Any] = field(default_factory=dict)
    bag_category: str | None = None
    bag_slot: int | None = None

    @property
    def wear_percent(self) -> float:
        """How beaten the disc is, on the durability scale the record carries."""
        if not self.durability:
            return 0.0
        return 100.0 * self.wear / self.durability

    @property
    def label(self) -> str:
        where = ""
        if self.bag_category:
            where = f" ({self.bag_category} slot {self.bag_slot})"
        return f"#{self.numero} {self.name}{where}"

    def bag_text(self) -> str:
        if self.bag_category is None:
            return "in box, not in bag"
        return f"{self.bag_category} #{self.bag_slot}"


def _as_number(value: Any, default: float = 0.0) -> float:
    if isinstance(value, bool):
        return default
    if isinstance(value, (int, float)):
        return value
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _to_number(value: Any, what: str) -> float:
    """Number for a staged edit: text that is not a number is an error, not a zero."""
    if isinstance(value, bool):
        raise ValueError(f"{what} must be a number")
    if isinstance(value, (int, float)):
        return value
    try:
        return float(str(value).strip())
    except (TypeError, ValueError):
        raise ValueError(f"{what} must be a number, got {value!r}") from None


def bag_map(payload: dict[str, Any]) -> dict[int, tuple[str, int]]:
    """numero -> (category, slot) from the ``kiekotbagissa`` payload."""
    out: dict[int, tuple[str, int]] = {}
    value = payload.get("value") or {}
    for key, category in BAG_CATEGORIES:
        for entry in value.get(key) or []:
            numero = entry.get("kiekkonumero")
            slot = entry.get("bagnumero")
            if isinstance(numero, int) and isinstance(slot, int):
                out[numero] = (category, slot)
    return out


class DiscSave:
    """One save file: discs read out of it, edits staged, written back surgically."""

    def __init__(self, path: str):
        self.path = path
        self.reload()

    def reload(self) -> None:
        self.text = es3.read_text(self.path)
        self.data = es3.parse(self.text)
        self.spans = es3.disc_spans(self.text, KIEKOT_KEY)
        records = (self.data.get(KIEKOT_KEY) or {}).get("value") or []
        if len(records) != len(self.spans):
            raise ValueError(
                f"{self.path}: parsed {len(records)} discs but located {len(self.spans)} records; "
                "the save is not the shape this tool expects"
            )
        bags = bag_map(self.data.get(BAG_KEY) or {})
        self.discs: list[Disc] = []
        for i, record in enumerate(records):
            colors = {
                k: str(record.get(k, ""))
                for k in ("vari", "vari2", "vari3", "rim", "rim2", "rim3", "stamp", "stamp2", "stamp3")
            }
            numero = record.get("numero", i)
            numero_int = int(numero) if isinstance(numero, int) else i
            where = bags.get(numero_int)
            disc = Disc(
                index=i,
                numero=numero_int,
                name=str(record.get("nimi", "")),
                maker=str(record.get("valmistaja", "")),
                plastic=str(record.get("muovi", "")),
                disc_type=str(record.get("tyyppi", "")),
                speed=record.get("nopeus", ""),
                weight=record.get("paino", ""),
                prefab=str(record.get("prefab", "")),
                wear=_as_number(record.get("wear")),
                durability=_as_number(record.get("durability")),
                favourite=bool(record.get("favourite")),
                colors=colors,
                custom=record.get("custom"),
                raw=dict(record),
                bag_category=where[0] if where else None,
                bag_slot=where[1] if where else None,
            )
            self.discs.append(disc)
        self.staged: dict[tuple[int, str], Any] = {}

    # -- staging ---------------------------------------------------------------

    def stage(self, index: int, field_name: str, value: Any) -> None:
        if field_name not in WRITABLE_FIELDS:
            raise ValueError(f"{field_name} is not an editable field")
        disc = self.discs[index]
        current = getattr(disc, _FIELD_ATTRS[field_name])
        if field_name == "favourite":
            value = bool(value)
        else:
            value = _to_number(value, field_name)
            if value < 0:
                raise ValueError("wear, durability and weight cannot be negative")
        if value == current:
            self.staged.pop((index, field_name), None)
            return
        self.staged[(index, field_name)] = value

    def staged_for(self, index: int) -> dict[str, Any]:
        return {f: v for (i, f), v in self.staged.items() if i == index}

    def clear_staged(self) -> None:
        self.staged.clear()

    @property
    def has_changes(self) -> bool:
        return bool(self.staged)

    # -- writing ---------------------------------------------------------------

    def changed_on_disk(self) -> bool:
        """True when the file is no longer the text these edits were made against.

        The whole text is compared, not the modification time: a rewrite that left every
        byte the same is not worth refusing, and a changed file is refused whatever the
        timestamp says.
        """
        try:
            current = es3.read_text(self.path)
        except OSError:
            return True
        return current != self.text

    def save(self) -> str:
        """Write the staged changes, after the file has been backed up.

        Refuses the write with :class:`SaveChangedError` when the file on disk has changed
        since it was read, and always leaves a ``<save>.bak-<timestamp>`` next to the save
        before anything is written. Returns the backup path (``""`` when there was nothing
        to write).
        """
        if not self.staged:
            return ""
        if self.changed_on_disk():
            raise SaveChangedError(
                f"{self.path} has been written since it was read here, so these staged edits "
                "belong to a copy of the save that no longer matches the file. Nothing was "
                "written."
            )
        changes = [(i, f, v) for (i, f), v in self.staged.items()]
        new_text = es3.apply_edits(self.text, es3.build_edits(self.text, self.spans, changes))
        # Prove the file we are about to leave behind still reads as a save with the
        # values we asked for, and that nothing else in it moved.
        check = es3.parse(new_text)
        records = (check.get(KIEKOT_KEY) or {}).get("value") or []
        for index, field_name, value in changes:
            got = records[index].get(field_name)
            if field_name == "favourite":
                ok = bool(got) == value
            else:
                ok = _as_number(got) == value
            if not ok:
                raise AssertionError(
                    f"write check failed for disc {index} field {field_name}: file holds {got!r}, expected {value!r}"
                )
        for key in self.data:
            if key == KIEKOT_KEY:
                continue
            if check.get(key) != self.data[key]:
                raise AssertionError(f"unrelated key {key} changed during the write")
        # The backup is not optional: an edit that the game cannot read is only recoverable
        # by putting the file back, and the user has to be able to find it.
        stamp = time.strftime("%Y%m%d-%H%M%S")
        backup_path = f"{self.path}.bak-{stamp}"
        suffix = 2
        while os.path.exists(backup_path):
            backup_path = f"{self.path}.bak-{stamp}-{suffix}"
            suffix += 1
        with open(backup_path, "w", encoding="utf-8", newline="") as fh:
            fh.write(self.text)
        try:
            es3.write_text(self.path, new_text)
        except OSError:
            if backup_path:
                es3.write_text(self.path, self.text)
            raise
        self.text = new_text
        self.data = check
        self.spans = es3.disc_spans(new_text, KIEKOT_KEY)
        self.reload()
        return backup_path

    def preview_wear(self, index: int) -> str:
        disc = self.discs[index]
        pending = self.staged_for(index).get("wear")
        if pending is None:
            return f"{disc.wear:g}"
        return f"{disc.wear:g} -> {pending:g}"


_FIELD_ATTRS = {"wear": "wear", "durability": "durability", "paino": "weight", "favourite": "favourite"}
