# True Disc Golf disc wear editor — plan

## What we are trying to do

True Disc Golf (Sportsmanlike Games, Steam appid `2721210`, plus the Steam demo appid
`3413550`) tracks wear on every disc in the player's bag. Wear is applied by the game as
you hit trees, poles, ground and concrete, and it changes how the disc flies (turn and
fade). We want to tune each disc by hand instead of grinding it in game, so:

1. Find where disc wear lives on disk.
2. Read the player's bag: which discs, and what wear each one has.
3. Build a GUI app that edits the wear of each disc and writes the save back in the exact
   format the game expects.
4. Keep a way to *prove* which fields are the wear fields: snapshot the save, play a round
   and wear a disc on purpose, snapshot again, diff. The diff names the fields that moved.

## Where the game data lives

| Item | Path |
| --- | --- |
| Full game install | `<steam library>\steamapps\common\True Disc Golf` (appid 2721210) |
| Demo install | `<steam library>\steamapps\common\True Disc Golf demo` (appid 3413550) |
| Full game save | `%USERPROFILE%\AppData\LocalLow\Sportsmanlike Games\True Disc Golf\SaveFile.es3` |
| Demo save | `%USERPROFILE%\AppData\LocalLow\Sportsmanlike Games\True Disc Golf demo\SaveFile.es3` |

Both saves are **Easy Save 3** files that are **not encrypted**: the file is plain JSON
(LF/TAB indented, `"key" : value`), one object per saved key, each shaped
`{ "__type": "<C# type>", "value": <payload> }`. The game's own type names are Finnish
(peli = game, kiekko = disc, pelaaja = player, muovi = plastic, paino = weight,
vari = colour, nopeus = speed).

Top-level keys in the full-game save: `asetukset`, `simulatorasetukset`, `kiekotbagissa`,
`kiekot`, `kierrokset`, `playerstutorial`, `screenasetukset`.

Steam Cloud is not used for either install: neither appid has a folder under Steam's
`userdata`, so a local edit is not quietly restored from the cloud — an edit that
disappears means the *game* wrote the file, not Steam.

## The wear variables (identified)

Discs are the list under key **`kiekot`** (`List<Kiekot+kiekotArray, Assembly-CSharp>`).
Each record is one disc:

```json
{ "numero": 11, "nopeus": 13, "tyyppi": "driver", "valmistaja": "discraft",
  "muovi": "Z", "nimi": "Crank", "prefab": "Crank_z", "paino": 175,
  "vari": "FDFDFD", "vari2": "", "vari3": "", "rim": "", "rim2": "", "rim3": "",
  "stamp": "0063FF", "stamp2": "", "stamp3": "",
  "wear": 0, "durability": 5000, "favourite": false, "custom": null }
```

* **`wear`** — the wear of this disc. This is the field to edit.
* **`durability`** — what the plastic can take before the disc is fully beaten. Observed
  values: `2000` (Discmania D-Line, Innova DX), `3000` (MVP Neutron Soft), `5000`
  (Innova Champion/Star, Discraft Z, MVP/Axiom Neutron/Proton, Latitude Opto).
  `wear` and `durability` travel together in the record, so `wear` is damage points on the
  `0 … durability` scale and `wear / durability` is the "how beaten is it" fraction.
* Which disc is where: key **`kiekotbagissa`** (`Kiekot+kiekotbagissaArray`) maps
  `kiekkonumero` (the disc's `numero`) to `bagnumero` (slot) per category —
  `putterit`, `midranget`, `driverit`.
* `favourite`, `paino` (weight), colours (`vari`/`rim`/`stamp`) live in the same record;
  `muovi` (plastic) and `prefab` decide the disc model, so the editor does not touch them.

Corroboration from the game binary, `True Disc Golf_Data/il2cpp_data/Metadata/global-metadata.dat`
(IL2CPP metadata v39), pulled with `tools/metadata_strings.py`:

* class `Kiekot` (the inventory) declares members `wear`, `Wear`, `UpdateWear`, `SaveDiscs`,
  `KiekonTiedot` (disc details UI), `BuyDisc`, `useDiscButtonClick`.
* the disc flight script (`kiekkoscript`) declares `discwear`, `discstability`, `discfade`,
  `discTurnKerroin`, `discFadeKerroin`, `discTurnValue`, `discFadeValue` — wear is fed into
  the turn/fade coefficients during flight, which is why tuning wear changes the disc.
* `KiekkoData` holds the per-model ratings (`discType`, `discSpeed`, `discGlide`,
  `discTurn`, `discFade`, `optimalThrowPower`, `hinta`, `muovi`, `durability`).
* the scene/prefab hierarchy has UI objects named `speed`, `glide`, `fade`, `turn`, `wear`
  next to `teksti` (text) components — the disc-details panel shows wear as a rating line.

Open question, kept honest: the binary is IL2CPP with metadata version 39 and Il2CppDumper
v6.7.46 rejects that version, so the exact arithmetic inside `UpdateWear` (how much wear one
hit adds, and how `discwear` is scaled into turn/fade) is not read from disassembly. What
the editor needs is the stored field, and that is confirmed. The scale is calibrated
empirically with the snapshot/diff feature described below.

## The bag in the sample save, as read on 2026-11-21

Full game (`True Disc Golf`), 14 discs, **all wear 0**, all in the bag. This is the bag in
`saves/sample-save.es3`, which is what the real-file test reads:

| numero | category / bag slot | disc | maker | plastic | speed | weight | durability | wear |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 3 | putter / slot 0 | P2 | Discmania | D-Line | 2 | 175 | 2000 | 0 |
| 4 | putter / slot 1 | Envy™ | Axiom | Neutron | 3 | 175 | 5000 | 0 |
| 5 | midrange / slot 1 | Buzzz | Discraft | Z | 5 | 175 | 5000 | 0 |
| 6 | midrange / slot 0 | Buzzz OS | Discraft | Z | 5 | 175 | 5000 | 0 |
| 7 | driver / slot 9 | Firebird | Innova | Champion | 9 | 175 | 5000 | 0 |
| 8 | driver / slot 10 | Wave™ | MVP | Neutron | 11 | 175 | 5000 | 0 |
| 9 | driver / slot 11 | Sidewinder | Innova | Champion | 9 | 175 | 5000 | 0 |
| 10 | driver / slot 4 | Wraith | Innova | Champion | 11 | 175 | 5000 | 0 |
| 11 | driver / slot 5 | Crank | Discraft | Z | 13 | 175 | 5000 | 0 |
| 12 | driver / slot 6 | Cigarra | Discraft | Z | 7 | 175 | 5000 | 0 |
| 13 | driver / slot 0 | Bolt | Latitude | Opto | 13 | 175 | 5000 | 0 |
| 14 | driver / slot 1 | Crave™ | Axiom | Proton | 6 | 175 | 5000 | 0 |
| 15 | driver / slot 2 | Rhythm™ | Axiom | Neutron | 7 | 175 | 5000 | 0 |
| 16 | midrange / slot 2 | Wasp | Discraft | Z | 5 | 175 | 5000 | 0 |

The demo save (`True Disc Golf demo`) holds 16 discs, numbers 0-15, also all `wear` 0; the
editor reads it the same way and its records have no `custom` field, which the reader
handles.

## How the editor writes the save

The write is surgical: the save is read as text, the `kiekot` key's text span is located by
matching braces (string-aware), every `"wear" : <number>` token in that span is found in
order and only the number text is replaced. Nothing else in the file — indentation, key
order, the `__type` strings, the other six keys — changes byte for byte, so Easy Save 3
loads the file exactly as it loaded the one the game wrote. The same token-level replace is
used for the secondary tunables (`durability`, `paino`) and for `favourite`. A backup
(`SaveFile.es3.bak-<timestamp>`) is written next to the save before every write, and the
result is re-parsed and re-checked before the tool says it succeeded; a failed check
restores the backup.

The tool shows a warning when `True Disc Golf.exe` / `True Disc Golf demo.exe` is running
and asks before writing anyway, and it re-reads the file before writing: if the file on disk
is no longer the text the staged edits were made against, the write is refused with
`SaveChangedError` and nothing is touched, because applying those edits would either fail or
undo whatever the game just saved. The window then tells the user to reload the save and set
the values again.

## Files

* `tdg_editor.py` — GUI entry point (`run_editor.bat` runs it).
* `tdg_cli.py` — same engine without a GUI: `disclaimer`, `list`, `set`, `snapshot`, `diff`.
* `src/tdgedit/es3.py` — ES3 text reader/writer, token-level field editing.
* `src/tdgedit/savefile.py` — disc model, save paths for both installs, bag slots, the write.
* `src/tdgedit/disclaimer.py` — the risk wording both front ends show.
* `src/tdgedit/snapshots.py` — snapshots and the before/after diff that names changed fields.
* `src/tdgedit/gui.py` — tkinter UI.
* `tools/metadata_strings.py`, `tools/scan_assets.py` — the read-only probes used to find
  the wear identifiers in the game binary and assets; point them at your own install with
  `--metadata` / `--dir` (or `TDG_GAME_DIR`).
* `saves/sample-save.es3` — a save taken from a fresh install before any edit, so the tests
  cover the real file shape and the comparison run has a starting point.

## Calibrating the wear scale (the part that needs a round of golf)

1. `python tdg_cli.py snapshot --tag before`.
2. Play a round, deliberately rub one disc on a trunk or a pole landing, quit the game.
3. `python tdg_cli.py snapshot --tag after` then `python tdg_cli.py diff saves/snapshot-*before*.es3 saves/snapshot-*after*.es3`.
   The diff prints every field that moved on every disc, so the wear fields are named by
   evidence rather than by name matching, and the delta says how much wear one hit costs.
4. Feed that into the editor: presets are fractions of `durability`, and the wear box takes
   any number, so whatever scale the game turns out to use can be set exactly.

## Decisions

* **Wear scale shown as a fraction of `durability`.** `wear` and `durability` sit together in
  the record and durability is per plastic (2000 / 3000 / 5000), so the editor treats
  `0 … durability` as the wear range and shows `wear / durability` as "worn %". Presets are
  0 / 25 / 50 / 75 / 100 % of durability. The wear box also takes any number, so if the
  calibration diff shows the game uses a different range, that range can be typed exactly.
* **Standard library only, tkinter GUI.** Nothing to install and no network needed to run the
  editor. UnityPy is used by the read-only asset probe, not by the editor.
* **Token-level writes rather than re-serialising the JSON.** The save is Easy Save 3 written
  by the game; leaving every byte except the value token as it was is the safest way to keep
  Easy Save 3 accepting the file.
* **Editable fields:** `wear`, and secondarily `durability`, `paino` (weight) and `favourite`.
  Name, maker, plastic and prefab decide the disc model the game loads, so changing them
  would desync the disc from its ratings; the editor refuses them.
* **Backups are not optional.** Every write leaves `SaveFile.es3.bak-<date and time>` next to
  the save holding the file exactly as it was, before anything is written, and there is no
  flag to skip it. An edit the game cannot read is only recoverable by putting that file back.
* **The save is read again before a write.** If the file on disk is no longer the text the
  staged edits were made against, the write is refused and nothing is touched, rather than
  merging edits into a file the tool has not seen. The user reloads and sets the values
  again; that is a visible step, and it never quietly undoes what the game just saved.
* **A load that would throw away unwritten edits asks first.** Reload and choosing another
  save file warn that the staged edits are not in the file yet and can be backed out of,
  because staged edits live only in this window.
* **Snapshot and compare are command line only.** The window has no buttons for them, so the
  everyday path is read, edit, backup, write; the diff loop is calibration work and
  `tdg_cli.py snapshot` / `snapshots` / `diff` still do it.
* **Both installs are supported.** The full game and the demo have separate saves and slightly
  different records (the demo has no `custom` field); the reader handles either.
* **Nothing was written to a real save.** The installed game's files were read only. The
  write path is tested against copies of a real save (`tests/test_es3.py` runs against the
  committed `saves/sample-save.es3`).
* **Il2CppDumper v6.7.46 rejects this build's metadata (version 39)**, so the arithmetic inside
  `UpdateWear` was not read from disassembly. The identifiers it declares are read instead
  (`tools/metadata_strings.py`), and the missing arithmetic is measured by the diff loop
  rather than guessed.

## Status

* Done: the wear field is identified and corroborated, both installs read, the editor written
  (window + CLI), tests covering the write and its guards.
* Open: the amount one hit adds to `wear`, and whether the game keeps a second wear value
  somewhere else (flight model, disc appearance). Both are answered by the calibration loop
  above: snapshot, wear one disc in game, snapshot, diff. The sample save has `wear: 0` on
  every disc, so any wear at all shows up in the diff.
