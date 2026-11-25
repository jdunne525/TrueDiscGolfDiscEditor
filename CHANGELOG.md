# Changelog

## 1.0.0 — 2026-11-25

First public release.

* Window and command line for disc wear: `wear`, plus `durability`, `paino` (weight) and
  `favourite`, written token-by-token so every other byte of the save is untouched.
* The risk of corrupting the save is stated where it cannot be missed: a notice when the
  window opens, `python tdg_cli.py disclaimer`, the `--help` epilog, the README and the
  license's warranty disclaimer.
* A backup of the save is written next to it before every write
  (`SaveFile.es3.bak-<date and time>`). There is no way to turn it off.
* Before applying changes the save is read again: if it changed since the tool read it, the
  write is refused and nothing is touched. The window says to reload the save
  (`Reload` / `F5`) and set the values again.
* Choosing another save file, or reloading, warns before staged edits that were never
  written are thrown away, and can be backed out of.
* Snapshot and compare are command line only. The window has no buttons for them;
  `tdg_cli.py snapshot`, `snapshots` and `diff` and `tdgedit.snapshots` still do the work.
