"""Command line front end: read the bag, set wear, snapshot, diff.

Same engine as the GUI, so the two can be used side by side.
"""

from __future__ import annotations

import argparse
import os
import sys
from typing import Any

from . import snapshots
from .savefile import Disc, DiscSave, discover_saves, process_is_running


def resolve_save(value: str | None) -> str:
    """A --save value is either a label ("True Disc Golf", "demo") or a file path."""
    locations = discover_saves()
    if value is None:
        if not locations:
            raise SystemExit("No True Disc Golf save found under AppData\\LocalLow\\Sportsmanlike Games")
        return locations[0].path
    if os.path.isfile(value):
        return value
    lowered = value.lower()
    for loc in locations:
        if loc.label.lower() == lowered or lowered in loc.label.lower():
            return loc.path
    raise SystemExit(f"No save matched {value!r}; found: {', '.join(l.label for l in locations)}")


def select_discs(save: DiscSave, selector: str) -> list[Disc]:
    selector = selector.strip()
    if selector.lower() in ("all", "*"):
        return list(save.discs)
    if selector.lower() in ("bag", "in-bag"):
        return [d for d in save.discs if d.bag_category]
    for category in ("putter", "midrange", "driver"):
        if selector.lower() == category:
            return [d for d in save.discs if d.disc_type == category]
    if selector.lower().startswith("index:"):
        return [save.discs[int(selector.split(":", 1)[1])]]
    text = selector.lstrip("#")
    if text.isdigit():
        numero = int(text)
        hits = [d for d in save.discs if d.numero == numero]
        if hits:
            return hits
    hits = [d for d in save.discs if selector.lower() in d.name.lower()]
    if not hits:
        raise SystemExit(f"No disc matched {selector!r}")
    return hits


def cmd_paths(_: argparse.Namespace) -> int:
    locations = discover_saves()
    if not locations:
        print("No True Disc Golf save found.")
        return 1
    for loc in locations:
        running = " (game is RUNNING - it will overwrite the save when it quits)" if process_is_running(loc.exe_name) else ""
        print(f"{loc.label}: {loc.path}{running}")
    return 0


def cmd_list(args: argparse.Namespace) -> int:
    save = DiscSave(resolve_save(args.save))
    print(f"{save.path}  ({len(save.discs)} discs)")
    print(f"{'num':>4}  {'type':<9} {'slot':<14} {'name':<18} {'maker':<11} {'plastic':<12} "
          f"{'spd':>3} {'wt':>4} {'dur':>5} {'wear':>8} {'worn%':>6}")
    for d in save.discs:
        print(f"{d.numero:>4}  {d.disc_type:<9} {d.bag_text():<14} {d.name:<18} {d.maker:<11} "
              f"{d.plastic:<12} {str(d.speed):>3} {str(d.weight):>4} {d.durability:>5.0f} "
              f"{d.wear:>8.4g} {d.wear_percent:>5.1f}%")
    return 0


def cmd_set(args: argparse.Namespace) -> int:
    path = resolve_save(args.save)
    save = DiscSave(path)
    discs = select_discs(save, args.disc)
    values: dict[str, Any] = {}
    if args.wear is not None:
        values["wear"] = args.wear
    if args.wear_pct is not None:
        values["wear_pct"] = args.wear_pct
    if args.durability is not None:
        values["durability"] = args.durability
    if args.weight is not None:
        values["paino"] = args.weight
    if args.favourite is not None:
        values["favourite"] = args.favourite
    if args.wear is not None and args.wear_pct is not None:
        print("Give either --wear or --wear-pct, not both.")
        return 1
    if args.wear_pct is not None and not 0 <= args.wear_pct <= 100:
        print("--wear-pct is a percentage of durability: use 0 to 100.")
        return 1
    if not values:
        print("Nothing to change; give --wear, --wear-pct, --durability, --weight or --favourite.")
        return 1
    for d in discs:
        pending = dict(values)
        if "wear_pct" in pending:
            pending["wear"] = pending.pop("wear_pct") / 100.0 * d.durability
        try:
            for field, value in pending.items():
                save.stage(d.index, field, value)
        except ValueError as exc:
            print(f"  {d.label}: {exc}")
            return 1
        parts = []
        for field, value in pending.items():
            if field == "favourite":
                before = "yes" if d.favourite else "no"
                after = "yes" if value else "no"
            else:
                current = getattr(d, _ATTR[field])
                before, after = f"{current:g}", f"{value:g}"
            parts.append(f"{field} {before} -> {after}")
        print(f"  {d.label}: " + ", ".join(parts))
    if args.dry_run:
        print(f"staged {len(save.staged)} change(s), not written (--dry-run)")
        return 0
    if not args.force and process_is_running(_exe_name_for(path)):
        print("The game is running, so it will overwrite this save when it quits. Use --force to write anyway.")
        return 2
    backup = save.save(backup=not args.no_backup)
    print(f"wrote {path}" + (f" (backup: {backup})" if backup else " (no backup)"))
    return 0


_ATTR = {"wear": "wear", "durability": "durability", "paino": "weight", "favourite": "favourite"}


def _exe_name_for(path: str) -> str:
    """The exe that owns this save, so the running check looks for the right process."""
    for loc in discover_saves():
        if os.path.normcase(loc.path) == os.path.normcase(path):
            return loc.exe_name
    return "True Disc Golf.exe"


def cmd_snapshot(args: argparse.Namespace) -> int:
    path = resolve_save(args.save)
    dest = snapshots.snapshot(path, tag=args.tag or "", dest_dir=args.dest)
    print(dest)
    return 0


def cmd_snapshots(_: argparse.Namespace) -> int:
    found = snapshots.list_snapshots()
    if not found:
        print("No snapshots yet. Use: python tdg_cli.py snapshot --tag before")
        return 1
    for path in found:
        print(path)
    return 0


def cmd_diff(args: argparse.Namespace) -> int:
    print(snapshots.format_diff(args.a, args.b))
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Read and tune disc wear in True Disc Golf saves.")
    sub = p.add_subparsers(dest="command", required=True)

    sp = sub.add_parser("paths", help="show the detected save files and whether the game is running")
    sp.set_defaults(func=cmd_paths)

    sp = sub.add_parser("list", help="list the discs in the bag and their wear")
    sp.add_argument("--save", help="save label (True Disc Golf, demo) or a path to a .es3 file")
    sp.set_defaults(func=cmd_list)

    sp = sub.add_parser("set", help="set wear (and optional secondary fields) on discs")
    sp.add_argument("--disc", default="all", help="#numero | name text | putter|midrange|driver | bag | all")
    sp.add_argument("--wear", type=float, help="wear value, on the same scale the save uses")
    sp.add_argument("--wear-pct", type=float, help="wear as a percentage of the disc's durability")
    sp.add_argument("--durability", type=float)
    sp.add_argument("--weight", type=float, help="paino, grams")
    sp.add_argument("--favourite", type=lambda s: s.lower() in ("1", "true", "yes", "on"), default=None)
    sp.add_argument("--save", help="save label or path")
    sp.add_argument("--dry-run", action="store_true")
    sp.add_argument("--no-backup", action="store_true")
    sp.add_argument("--force", action="store_true", help="write even if the game is running")
    sp.set_defaults(func=cmd_set)

    sp = sub.add_parser("snapshot", help="copy a save into saves/ for a before/after comparison")
    sp.add_argument("--tag", default="", help="e.g. before or after")
    sp.add_argument("--dest", help="folder to write the snapshot to (default: the project's saves/)")
    sp.add_argument("--save", help="save label or path")
    sp.set_defaults(func=cmd_snapshot)

    sp = sub.add_parser("snapshots", help="list saved snapshots")
    sp.set_defaults(func=cmd_snapshots)

    sp = sub.add_parser("diff", help="print every value that changed between two snapshots")
    sp.add_argument("a")
    sp.add_argument("b")
    sp.set_defaults(func=cmd_diff)
    return p


def main(argv: list[str] | None = None) -> int:
    try:
        # disc names carry characters like ™ that some Windows consoles cannot encode
        sys.stdout.reconfigure(errors="replace")
    except (AttributeError, ValueError):
        pass
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
