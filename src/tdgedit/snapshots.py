"""Snapshots and the before/after diff that names the fields that actually moved.

This is the calibration loop: snapshot the save, go wear a disc on purpose, snapshot
again, diff. The diff walks both files key by key and prints every value that changed,
so the wear fields are identified by evidence and the delta says what one hit costs.

``tdg_cli.py snapshot``, ``snapshots`` and ``diff`` are how this is reached now: the window
has no buttons for it.
"""

from __future__ import annotations

import json
import os
import shutil
import time
from typing import Any, Iterator

from . import es3
from .savefile import DiscSave


def snapshot_dir(project_root: str | None = None) -> str:
    root = project_root or os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    return os.path.join(root, "saves")


def snapshot(save_path: str, tag: str = "", dest_dir: str | None = None) -> str:
    """Copy the save into the project's ``saves`` folder with a timestamp name."""
    dest_dir = dest_dir or snapshot_dir()
    os.makedirs(dest_dir, exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    safe_tag = "".join(c if c.isalnum() or c in "-_" else "-" for c in tag).strip("-")
    base = os.path.basename(os.path.dirname(save_path)) or "save"
    safe_base = "".join(c if c.isalnum() or c in "-_." else "-" for c in base)
    name = f"snapshot-{stamp}" + (f"-{safe_tag}" if safe_tag else "") + f"-{safe_base}.es3"
    dest = os.path.join(dest_dir, name)
    # two snapshots taken in the same second must not overwrite each other
    stem = name[: -len(".es3")]
    suffix = 2
    while os.path.exists(dest):
        dest = os.path.join(dest_dir, f"{stem}-{suffix}.es3")
        suffix += 1
    shutil.copyfile(save_path, dest)
    return dest


def list_snapshots(dest_dir: str | None = None) -> list[str]:
    dest_dir = dest_dir or snapshot_dir()
    if not os.path.isdir(dest_dir):
        return []
    return sorted(
        os.path.join(dest_dir, n) for n in os.listdir(dest_dir) if n.endswith(".es3")
    )


def _walk(value: Any, path: str) -> Iterator[tuple[str, Any]]:
    """Leaf paths of a parsed save, e.g. ``kiekot.value[3].wear``."""
    if isinstance(value, dict):
        for key, sub in value.items():
            yield from _walk(sub, f"{path}.{key}" if path else str(key))
    elif isinstance(value, list):
        for i, sub in enumerate(value):
            yield from _walk(sub, f"{path}[{i}]")
    else:
        yield path, value


def diff_files(path_a: str, path_b: str) -> list[tuple[str, Any, Any]]:
    """Every leaf that differs between two saves, as ``(path, old, new)``."""
    a = es3.parse_file(path_a)
    b = es3.parse_file(path_b)
    old = dict(_walk(a, ""))
    new = dict(_walk(b, ""))
    out: list[tuple[str, Any, Any]] = []
    for path in sorted(set(old) | set(new)):
        if old.get(path, "<missing>") != new.get(path, "<missing>"):
            out.append((path, old.get(path, "<missing>"), new.get(path, "<missing>")))
    return out


def _disc_labels(save_path: str) -> dict[int, str]:
    """List position -> "#numero name (category slot)", so the diff says which disc."""
    try:
        save = DiscSave(save_path)
    except (OSError, ValueError, json.JSONDecodeError):
        return {}
    return {d.index: d.label for d in save.discs}


def _disc_index_in_diff(path: str) -> int | None:
    prefix = "kiekot.value["
    if not path.startswith(prefix):
        return None
    rest = path[len(prefix):]
    digits = ""
    for c in rest:
        if c.isdigit():
            digits += c
        else:
            break
    return int(digits) if digits else None


def format_diff(path_a: str, path_b: str, limit: int = 400) -> str:
    """Human-readable diff of two saves, wear changes first."""
    changes = diff_files(path_a, path_b)
    if not changes:
        return f"No differences between\n  {path_a}\n  {path_b}"
    lines = [
        f"Diff of two save snapshots",
        f"  before: {path_a}",
        f"  after:  {path_b}",
        f"{len(changes)} value(s) changed.",
        "",
    ]
    labels = _disc_labels(path_a)
    wear = [c for c in changes if c[0].endswith(".wear")]
    other = [c for c in changes if not c[0].endswith(".wear")]
    if wear:
        lines.append("wear fields that changed:")
        for path, old, new in wear:
            label = labels.get(_disc_index_in_diff(path), "")
            delta = ""
            if isinstance(old, (int, float)) and isinstance(new, (int, float)) and not isinstance(old, bool):
                delta = f"  (delta {new - old:+g})"
            lines.append(f"  {label + '  ' if label else ''}{path}: {old} -> {new}{delta}")
        lines.append("")
    if other:
        lines.append(f"everything else that changed ({len(other)}):")
        for path, old, new in other[:limit]:
            lines.append(f"  {path}: {old} -> {new}")
        if len(other) > limit:
            lines.append(f"  … {len(other) - limit} more")
    return "\n".join(lines)
