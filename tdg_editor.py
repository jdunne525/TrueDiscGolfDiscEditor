#!/usr/bin/env python3
"""GUI entry point for the True Disc Golf disc wear editor."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))

from tdgedit.gui import run  # noqa: E402  (path set up above)

if __name__ == "__main__":
    run()
