"""The risk wording both front ends show, so nobody edits a save without knowing what it costs.

Kept in one place because the same text belongs in the window, in the command line help and in
the README: what the tool can do to a save, and what the way back is.
"""

from __future__ import annotations

TITLE = "This edits your game save"

# Shown when the window opens, before anything is read or written.
FULL = """True Disc Golf disc wear editor edits the save file the game keeps in
AppData\\LocalLow\\Sportsmanlike Games.

Risk: an edit can corrupt the save. If the game cannot read the file it usually starts a
new save, and the discs, rounds and settings the game had written are lost. The game also
keeps some things outside this file, and those are not edited here, so they can disagree
with what the save says. Nothing here is tested against every version of the game.

What the tool does to keep a way back:
  * before every write it makes a backup of the save next to it, as
    "SaveFile.es3.bak-<date and time>", and only then writes;
  * a write is refused if the file has changed since this window read it, because applying
    edits to a save the game has rewritten would undo the game's own save;
  * only the number behind the edited field is replaced, every other byte is left as the
    game wrote it, and the result is re-read and checked before it says it succeeded.

Still: close the game before editing, and copy the whole save folder somewhere else before
the first edit. Backups stay next to the save until you delete them. To undo an edit, close
the game and put the newest backup back over SaveFile.es3.

Unofficial tool, not affiliated with or endorsed by Sportsmanlike Games. It comes with no
warranty: use it on a save you can afford to lose.
"""

# One line for the bottom of the window.
SHORT = "an edit can corrupt the save - every write makes a backup first, no warranty"

# For the command line help.
CLI = (
    "Risk: an edit can corrupt the save. A save the game cannot read is usually replaced by a\n"
    "new one, and the discs, rounds and settings the game had written are gone.\n"
    "Each write first makes a backup next to the save, \"SaveFile.es3.bak-<date and\n"
    "time>\", and a write is refused if the file changed since it was read.\n"
    "Close the game before editing, and copy the save folder somewhere else before the\n"
    "first edit. Unofficial tool, no warranty; not affiliated with or endorsed by\n"
    "Sportsmanlike Games."
)
