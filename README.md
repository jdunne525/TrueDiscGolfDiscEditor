# True Disc Golf disc wear editor

Edits the disc wear that True Disc Golf (Sportsmanlike Games) stores for each disc in your
bag, so each disc can be tuned by hand instead of grinding it in game.

**Unofficial tool.** Not affiliated with, or endorsed by, Sportsmanlike Games.
Windows, Python 3.10+, standard library only — the GUI is tkinter, nothing to install, no
network.

## Read this first: the risk

Editing the save can **corrupt** it. If the game cannot read the file, it usually starts a
new save, and the discs, rounds and settings the game had written are gone. The game also
keeps some things outside this file, and this tool does not touch those, so they can
disagree with what the save says. Nothing here is tested against every version of the game.

* **Close the game before editing.** The game rewrites the save when it quits, and that
  overwrites anything written while it was running.
* **Copy the whole save folder somewhere else before the first edit.** That is the way back
  if the game refuses the file: close the game, put the copy back over `SaveFile.es3`.
* This tool comes with **no warranty** (see [LICENSE](LICENSE)). Use it on a save you can
  afford to lose.

What the tool does to keep a way back, on its own:

* **A backup before every write.** `SaveFile.es3.bak-<date and time>` appears next to the
  save, holding the file exactly as it was before that write. Backups are never deleted by
  the tool, and they are what you restore if the game will not load the save.
* **The file is re-read before anything is written.** If it changed since the tool read it —
  the game quit, another program wrote it, a backup was restored — the write is refused and
  nothing is touched. Reload the save (`Reload` button or `F5`) and apply the values again;
  reloading throws away the staged edits, so set them again afterwards.
* **Only the value token moves.** The rest of the file's bytes stay as the game wrote them,
  and the result is re-parsed and checked (right values on the right discs, every unrelated
  key unchanged) before the tool says it succeeded.

The window shows this notice when it opens, and `python tdg_cli.py disclaimer` prints it.

## Run it

```
run_editor.bat            (or: python tdg_editor.py)
```

Pick the save at the top (`True Disc Golf`, `True Disc Golf demo`, or `Browse…`), select a
disc, drag the wear slider or type a value, press **stage row**, then **Write save**.
Presets set wear to 0 / 25 / 50 / 75 / 100 % of the disc's durability. Tick *in bag only* or
filter by type to work on part of the bag; *set wear for every listed disc* applies a
percentage to everything the list is showing.

Choosing a different save, or pressing **Reload** / `F5`, warns you before it reads the file
over edits that have not been written yet, and you can back out of it.

Keyboard: `F5` reload, `Ctrl+S` write.

Snapshots and the before/after comparison are command line only (see below); the window has
no buttons for them.

## Command line

```
python tdg_cli.py disclaimer
python tdg_cli.py paths
python tdg_cli.py list
python tdg_cli.py set --disc "#11" --wear 1200
python tdg_cli.py set --disc driver --wear-pct 40
python tdg_cli.py set --disc Buzzz --wear 0 --save demo
python tdg_cli.py snapshot --tag before
python tdg_cli.py snapshot --tag after
python tdg_cli.py diff saves/snapshot-<before>.es3 saves/snapshot-<after>.es3
```

`--disc` takes `#numero`, a name fragment, `putter` / `midrange` / `driver`, `bag`, `all`, or
`index:N`. `--dry-run` stages without writing. `--force` writes even while the game is
running (it will overwrite the edit on quit). Every `set` that writes makes a backup first
and refuses a file that changed after it was read; exit status `2` means nothing was written
because the game is running or the file changed.

## Finding out what wear actually costs (the calibration loop)

The wear field is identified; what one hit adds to it is measured:

1. `python tdg_cli.py snapshot --tag before` — copies go to `saves/`.
2. Play a round, rub one disc against a trunk or a pole landing on purpose, then quit.
3. `python tdg_cli.py snapshot --tag after`, then
   `python tdg_cli.py diff saves/snapshot-<before>.es3 saves/snapshot-<after>.es3`.
   The diff walks the whole save and prints every value that moved, so the fields that
   change when a disc gets worn are named by evidence, and the delta says what one hit costs.

## What gets written

`wear` is the point. `durability`, `paino` (weight, grams) and `favourite` are also editable
because they sit in the same record and matter when tuning a disc. The disc's identity —
`nimi`, `valmistaja`, `muovi`, `prefab` — decides which model and ratings the game loads, so
the tool leaves those alone.

Plan and the evidence behind the wear fields:
[plans/disc-wear-editor-plan.md](plans/disc-wear-editor-plan.md).

## Layout

| path | what it is |
| --- | --- |
| `tdg_editor.py`, `run_editor.bat` | GUI entry points |
| `tdg_cli.py` | command line entry point |
| `src/tdgedit/es3.py` | Easy Save 3 text reader/writer, token-level field edits |
| `src/tdgedit/savefile.py` | disc model, save paths, bag slots, staged edits, the write itself |
| `src/tdgedit/disclaimer.py` | the risk notice shown by both front ends |
| `src/tdgedit/snapshots.py` | snapshots and the before/after diff |
| `src/tdgedit/gui.py` | tkinter window |
| `src/tdgedit/cli.py` | argparse front end |
| `tests/` | `python -m unittest discover -s tests` |
| `saves/sample-save.es3` | a save taken from a fresh install, so the tests cover the real file shape; it holds no personal data |
| `tools/metadata_strings.py`, `tools/scan_assets.py` | read-only probes used to find the wear identifiers (point them at your own install; the asset scan needs UnityPy) |
| `saves/` | snapshots you take with `tdg_cli.py snapshot`; write backups stay next to the save itself |

## Tests

```
python -m unittest discover -s tests
```

Covers: locating the disc records in the save, replacing only the value token, values
landing on the right disc, float and int formatting, unrelated keys staying byte-identical,
the backup made for every write, refusing a file that changed after it was read, refusing
values that are not numbers, the diff naming a changed wear path, the CLI commands
(including the disclaimer), and the window's own behaviour (rows, selection, presets, bulk
apply, write, the unwritten-changes warning, the risk notice, no snapshot buttons). One test
runs against `saves/sample-save.es3` and is skipped if that file is removed.

## Troubleshooting

* **"The save changed since it was read"** — the game (or something else) wrote the file
  after the tool read it, so the write was refused and nothing was touched. Reload the save
  and set the values again.
* **The edit is gone after playing** — the game rewrites the save when it quits, so anything
  written while it was running is lost. Close the game, reload (`F5`), write again.
  Steam Cloud is not the culprit: neither install has cloud saves, so a vanished edit means
  the game wrote this file.
* **The disc still looks new in game** — the save was written, but the game may render wear
  from a value it also keeps elsewhere. Run the snapshot/diff loop after wearing a disc in
  game: the diff lists every field that moved, which is the list the editor has to cover.
* **The game will not load the save** — close the game, delete `SaveFile.es3` and put the
  newest `SaveFile.es3.bak-<timestamp>` (or your own copy of the folder) in its place, then
  start the game to check.

## License and the game's files

Released under the MIT license — see [LICENSE](LICENSE). The save format belongs to Easy
Save 3 and True Disc Golf belongs to Sportsmanlike Games; this repository contains no files
from either, only the reading and writing code. `saves/sample-save.es3` is a save taken from
a fresh install (default player names, no progress worth anything) and is there so the tests
exercise the real file shape; delete it and the one test that needs it skips.
