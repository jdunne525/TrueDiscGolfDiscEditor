#!/usr/bin/env python3
r"""Read-only probe over a Unity build's .assets files: what is named what.

Used to find the disc wear UI: True Disc Golf's scenes and prefabs carry GameObjects named
after the rating lines the disc panel shows (speed, glide, fade, turn, wear), which is how
the wear line in the game's disc details panel was located.

Needs UnityPy (``pip install UnityPy``); the editor itself needs nothing but the standard
library. Script types in an IL2CPP build have stripped type trees, so this reports names
and hierarchy rather than script field values.

    python tools/scan_assets.py wear --dir "<install>\True Disc Golf_Data"
    python tools/scan_assets.py wear --dir "<install>\True Disc Golf_Data" --tree

Point it at your own install with ``--dir``, or set ``TDG_GAME_DIR`` to the install folder.
The editor itself does not use this probe, and nothing here writes to the game.
"""

from __future__ import annotations

import argparse
import os
import sys


def default_dir() -> str | None:
    """The ``*_Data`` folder inside ``TDG_GAME_DIR``, when that environment variable is set."""
    game = os.environ.get("TDG_GAME_DIR")
    if not game:
        return None
    for name in ("True Disc Golf_Data", "Data"):
        candidate = os.path.join(game, name)
        if os.path.isdir(candidate):
            return candidate
    return os.path.join(game, "True Disc Golf_Data")


def load(path):
    import UnityPy  # imported here so the editor never needs it

    return UnityPy.load(path)


def object_name(obj) -> str:
    try:
        data = obj.data
        return str(getattr(data, "name", "")) or str(obj.peek_name())
    except Exception:
        return "?"


def hierarchy(objs_by_path, path_id, depth=0, limit=40):
    """Names under a GameObject, so a label's siblings can be seen."""
    from UnityPy.enums import ClassIDType

    out: list[str] = []
    obj = objs_by_path.get(path_id)
    if obj is None or len(out) > limit:
        return out
    if obj.type != ClassIDType.GameObject:
        return out
    try:
        data = obj.data
    except Exception:
        data = None
    if data is None:
        out.append("  " * depth + object_name(obj) + "  (data not readable)")
        return out
    out.append("  " * depth + object_name(obj))
    try:
        components = list(data.m_Component)
    except Exception:
        return out
    for comp in components:
        child = objs_by_path.get(comp.path_id)
        if child is None or child.type != ClassIDType.Transform:
            continue
        try:
            children = list(child.data.m_Children)
        except Exception:
            continue
        for link in children:
            out.extend(hierarchy(objs_by_path, link.path_id, depth + 1, limit))
            if len(out) > limit:
                return out
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("term", help="substring to look for in object names")
    parser.add_argument("--dir", default=default_dir(),
                        help="folder of .assets files to scan (default: TDG_GAME_DIR)")
    parser.add_argument("--tree", action="store_true", help="also print the hierarchy under each hit")
    parser.add_argument("--files", nargs="*", help="specific .assets files instead of the whole folder")
    args = parser.parse_args(argv)

    try:
        from UnityPy.enums import ClassIDType
    except ImportError:
        print("UnityPy is not installed: pip install UnityPy", file=sys.stderr)
        return 2

    files = args.files
    if not files:
        if args.dir is None:
            print("Say where the game is: --dir <the game's *_Data folder>, or set TDG_GAME_DIR "
                  "to the install folder.", file=sys.stderr)
            return 2
        if not os.path.isdir(args.dir):
            print(f"no asset folder at {args.dir}", file=sys.stderr)
            return 1
        files = [
            os.path.join(args.dir, name)
            for name in sorted(os.listdir(args.dir))
            if name.endswith(".assets") and not name.endswith(".resS")
        ]

    hits = 0
    for path in files:
        try:
            env = load(path)
            objs = list(env.objects)
        except Exception as exc:
            print(f"{os.path.basename(path)}: could not parse ({exc})")
            continue
        by_path = {o.path_id: o for o in objs}
        for obj in objs:
            name = object_name(obj)
            if args.term.lower() not in name.lower():
                continue
            hits += 1
            type_name = obj.type.name if isinstance(obj.type, ClassIDType) else str(obj.type)
            print(f"{os.path.basename(path)}  {type_name:<16} {name}")
            if args.tree and obj.type == ClassIDType.GameObject:
                for line in hierarchy(by_path, obj.path_id):
                    print(f"    {line}")
        print(f"{os.path.basename(path)}: {len(objs)} objects scanned")
    print(f"{hits} object(s) matching {args.term!r}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
