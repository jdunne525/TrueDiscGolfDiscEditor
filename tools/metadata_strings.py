#!/usr/bin/env python3
r"""Look up an identifier in a Unity IL2CPP global-metadata.dat and show its neighbourhood.

global-metadata.dat holds every class, method and field name the game was compiled with as
null-separated strings, so grepping it tells you what the game calls the thing you are
after, and what the code around it is named.

    python tools/metadata_strings.py wear --metadata "<install>\True Disc Golf_Data\il2cpp_data\Metadata\global-metadata.dat"
    python tools/metadata_strings.py durability --window 2000

Default is whatever ``TDG_GAME_DIR`` points at (the game's install folder); pass
``--metadata`` to look at any build, including the demo's own.

The editor itself does not use this probe, and nothing here writes to the game.
"""

from __future__ import annotations

import argparse
import os
import re
import sys


def default_metadata() -> str | None:
    """``global-metadata.dat`` inside ``TDG_GAME_DIR``, when that environment variable is set."""
    game = os.environ.get("TDG_GAME_DIR")
    if not game:
        return None
    return os.path.join(game, "True Disc Golf_Data", "il2cpp_data", "Metadata", "global-metadata.dat")


def find_occurrences(blob: bytes, term: str) -> list[int]:
    needle = term.encode("utf-8")
    return [m.start() for m in re.finditer(re.escape(needle), blob)]


def identifiers_around(blob: bytes, offset: int, window: int) -> list[str]:
    start = max(0, offset - window)
    end = min(len(blob), offset + window)
    chunk = blob[start:end].decode("utf-8", "replace")
    return [part for part in chunk.split("\x00") if part]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("term")
    parser.add_argument("--metadata", default=default_metadata(),
                        help="path to global-metadata.dat (default: TDG_GAME_DIR)")
    parser.add_argument("--window", type=int, default=1200, help="bytes of context each side")
    parser.add_argument("--whole", action="store_true", help="print the whole heap slice, not split identifiers")
    args = parser.parse_args(argv)

    if args.metadata is None:
        print(
            "Say where the game is: --metadata <path to global-metadata.dat>, or set "
            "TDG_GAME_DIR to the install folder.",
            file=sys.stderr,
        )
        return 2
    if not os.path.isfile(args.metadata):
        print(f"no metadata file at {args.metadata}", file=sys.stderr)
        return 1

    blob = open(args.metadata, "rb").read()
    magic = int.from_bytes(blob[:4], "little")
    version = int.from_bytes(blob[4:8], "little")
    print(f"{args.metadata}\nmagic {magic:#x} metadata version {version}, {len(blob)} bytes")

    offsets = find_occurrences(blob, args.term)
    print(f"'{args.term}' appears {len(offsets)} time(s): {offsets[:20]}")
    for offset in offsets[:12]:
        print(f"\n=== offset {offset}")
        if args.whole:
            start = max(0, offset - args.window)
            end = min(len(blob), offset + args.window)
            print(repr(blob[start:end]))
        else:
            for name in identifiers_around(blob, offset, args.window):
                marker = "  <== " + args.term if args.term in name else ""
                print(f"  {name}{marker}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
