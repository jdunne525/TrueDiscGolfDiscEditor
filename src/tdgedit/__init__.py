"""True Disc Golf disc wear editor engine.

``es3`` reads and writes the game's Easy Save 3 file, ``savefile`` models the disc
inventory, ``snapshots`` does the before/after comparison, ``disclaimer`` holds the risk
wording both front ends show, and ``gui`` and ``cli`` are the two front ends.
"""

from .disclaimer import FULL as DISCLAIMER, SHORT as SHORT_WARNING
from .es3 import apply_edits, build_edits, disc_spans, parse, parse_file, read_text, write_text
from .savefile import (
    Disc,
    DiscSave,
    SaveChangedError,
    SaveLocation,
    discover_saves,
    process_is_running,
)

__version__ = "1.0.0"

__all__ = [
    "DISCLAIMER",
    "SHORT_WARNING",
    "__version__",
    "Disc",
    "DiscSave",
    "SaveChangedError",
    "SaveLocation",
    "apply_edits",
    "build_edits",
    "disc_spans",
    "discover_saves",
    "parse",
    "parse_file",
    "process_is_running",
    "read_text",
    "write_text",
]
