# True Disc Golf disc wear editor

Edits the disc wear that True Disc Golf (Sportsmanlike Games) stores for each disc in your
bag, so each disc can be tuned by hand instead of grinding it in game.

Plan and the evidence behind the wear fields: [plans/disc-wear-editor-plan.md](plans/disc-wear-editor-plan.md).

## Run it

```
run_editor.bat            (or: python tdg_editor.py)
```

Windows, Python 3.10+, standard library only — the GUI is tkinter, no installs, no network.

Pick the save at the top (`True Disc Golf`, `True Disc Golf demo`, or `Browse…`), select a
disc, drag the wear slider or type a value, press **stage row**, then **Write save**.
Presets set wear to 0 / 25 / 50 / 75 / 100 % of the disc's durability. Tick *in bag only* or
filter by type to work on part of the bag; *set wear for every listed disc* applies a
percentage to everything the list is showing.

**Close the game first.** The game rewrites the save when it quits, and that overwrites
anything you wrote while it was running. The window shows a warning while the game is
running and asks before writing anyway. Every write leaves a `SaveFile.es3.bak-<timestamp>`
next to the save and re-reads the file to prove it still parses.

Keyboard: `F5` reload, `Ctrl+S` write.

## Command line

```
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
`index:N`. `--dry-run` stages without writing.

## Finding out what wear actually costs (the calibration loop)

The wear field is identified; what one hit adds to it is measured:

1. **Snapshot** the save (button, or `tdg_cli.py snapshot --tag before`) — copies go to `saves/`.
2. Play a round and rub one disc against a trunk or a pole landing on purpose, then quit.
3. **Compare snapshots…** in the GUI, or `tdg_cli.py diff <before> <after>`.
   The diff walks the whole save and prints every value that moved, so the fields that
   change when a disc gets worn are named by evidence, and the delta says what one hit costs.

## What gets written

`wear` is the point. `durability`, `paino` (weight, grams) and `favourite` are also editable
because they sit in the same record and matter when tuning a disc. The disc's identity —
`nimi`, `valmistaja`, `muovi`, `prefab` — decides which model and ratings the game loads, so
the tool leaves those alone.

Writes are token-level: only the number text behind the field is replaced inside the
`kiekot` block, and every other byte of the file stays as the game wrote it, which is what
keeps Easy Save 3 reading the file happily.

## Layout

| path | what it is |
| --- | --- |
| `tdg_editor.py`, `run_editor.bat` | GUI entry points |
| `tdg_cli.py` | command line entry point |
| `src/tdgedit/es3.py` | Easy Save 3 text reader/writer, token-level field edits |
| `src/tdgedit/savefile.py` | disc model, save paths, bag slots, staged edits |
| `src/tdgedit/snapshots.py` | snapshots and the before/after diff |
| `src/tdgedit/gui.py` | tkinter window |
| `src/tdgedit/cli.py` | argparse front end |
| `tests/` | `python -m unittest discover -s tests` |
| `tools/metadata_strings.py`, `tools/scan_assets.py` | read-only probes used to find the wear identifiers (need UnityPy for the asset scan) |
| `saves/` | the baseline snapshots taken before any edit, and later before/after pairs |

## Tests

```
python -m unittest discover -s tests
```

Covers: locating the disc records in the save, replacing only the value token, values
landing on the right disc, float and int formatting, unrelated keys staying byte-identical,
backup and re-read on write, refusing values that are not numbers, the diff naming a changed
wear path, the CLI commands, and the window's own behaviour (rows, selection, presets, bulk
apply, write, snapshot, compare). One test runs against the real baseline snapshot in `saves/`
and is skipped if that file is removed.

## Troubleshooting

* **The edit is gone after playing** — the game rewrites the save when it quits, so anything
  written while it was running is lost. Close the game, reload (`F5`), write again.
  Steam Cloud is not the culprit: neither install has cloud saves, so a vanished edit means
  the game wrote this file.
* **The disc still looks new in game** — the save was written, but the game may render wear from
  a value it also keeps elsewhere. Run the snapshot/diff loop after wearing a disc in game: the
  diff lists every field that moved, which is the list the editor has to cover.
* **The save will not open** — the file was edited by something else in the meantime. The write
  backups (`SaveFile.es3.bak-<timestamp>` next to the save) and the copies in `saves/` are the
  way back.
