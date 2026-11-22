"""Easy Save 3 (.es3) text handling for True Disc Golf saves.

True Disc Golf writes its save with Easy Save 3 in plaintext: the file is JSON with
tab indentation and ``"key" : value`` separators, one top-level object per saved key,
each shaped ``{ "__type": "<C# type>", "value": <payload> }``.

Editing is done as token-level text replacement inside the exact span of the key being
edited, so every other byte of the file (indentation, key order, ``__type`` strings,
the other keys) is left exactly as the game wrote it. That keeps Easy Save 3 reading
the file the same way it read the one the game produced.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Iterable

# Open/pretty-print style the game uses; only used when a file has to be created whole.
INDENT = "\t"


def read_text(path: str) -> str:
    """Read the save as text without touching line endings."""
    with open(path, "r", encoding="utf-8", newline="") as fh:
        return fh.read()


def write_text(path: str, text: str) -> None:
    with open(path, "w", encoding="utf-8", newline="") as fh:
        fh.write(text)


def parse(text: str) -> dict[str, Any]:
    return json.loads(text)


def parse_file(path: str) -> dict[str, Any]:
    return parse(read_text(path))


@dataclass
class Span:
    start: int
    end: int  # exclusive


def _skip_string(text: str, i: int) -> int:
    """Return the index just past the string literal that starts at ``i``."""
    assert text[i] == '"'
    i += 1
    while i < len(text):
        c = text[i]
        if c == "\\":
            i += 2
            continue
        if c == '"':
            return i + 1
        i += 1
    raise ValueError("unterminated string in save file")


def match_container(text: str, start: int) -> int:
    """Return the index just past the container (``{``/``[``) that starts at ``start``.

    Braces, brackets and string literals are tracked so a brace inside a string does not
    throw the scan off.
    """
    open_char = text[start]
    if open_char not in "{[":
        raise ValueError(f"expected '{{' or '[' at {start}, found {open_char!r}")
    close_char = "}" if open_char == "{" else "]"
    depth = 0
    i = start
    while i < len(text):
        c = text[i]
        if c == '"':
            i = _skip_string(text, i)
            continue
        if c in "{[":
            depth += 1
        elif c in "}]":
            depth -= 1
            if depth == 0:
                if c != close_char:
                    raise ValueError(f"mismatched {c!r} at {i}")
                return i + 1
        i += 1
    raise ValueError("unbalanced container in save file")


def find_top_level_key(text: str, key: str) -> tuple[Span, Span]:
    """Return the span of ``"key"`` and the span of its value at the file's top level."""
    pattern = re.compile(r'^\t("' + re.escape(key) + r'")\s*:\s*', re.M)
    m = pattern.search(text)
    if m is None:
        raise KeyError(key)
    key_span = Span(m.start(1), m.start(1) + len(m.group(1)))
    value_start = m.end()
    if text[value_start] in "{[":
        value_end = match_container(text, value_start)
    else:
        value_end = _scalar_end(text, value_start)
    return key_span, Span(value_start, value_end)


def _scalar_end(text: str, start: int) -> int:
    """End of a bare scalar (number / true / false / null) starting at ``start``."""
    i = start
    while i < len(text) and text[i] not in ",\n\r}":
        i += 1
    return i


def iter_object_spans(text: str, array_start: int) -> list[Span]:
    """Spans of the objects inside the ``[`` array that starts at ``array_start``."""
    if text[array_start] != "[":
        raise ValueError("expected '['")
    end = match_container(text, array_start)
    spans: list[Span] = []
    i = array_start + 1
    while i < end - 1:
        c = text[i]
        if c == '"':
            i = _skip_string(text, i)
        elif c in "{[":
            stop = match_container(text, i)
            spans.append(Span(i, stop))
            i = stop
        else:
            i += 1
    return spans


def disc_spans(text: str, key: str = "kiekot") -> list[Span]:
    """Spans of the disc records inside the ``kiekot`` key's payload."""
    _, value_span = find_top_level_key(text, key)
    block = text[value_span.start:value_span.end]
    m = re.search(r'"value"\s*:\s*\[', block)
    if m is None:
        raise ValueError("kiekot payload has no 'value' array")
    array_start = value_span.start + m.end() - 1
    return iter_object_spans(text, array_start)


_NUMBER_RE = re.compile(r"-?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?")
_TRUE_LITERAL = "true"
_FALSE_LITERAL = "false"
_NULL_LITERAL = "null"


def field_span(block: str, field: str) -> Span:
    """Span of the value of ``"field"`` inside one object's text."""
    m = re.search(r'"' + re.escape(field) + r'"\s*:\s*', block)
    if m is None:
        raise KeyError(field)
    start = m.end()
    if block[start] == '"':
        end = _skip_string(block, start)
        return Span(start, end)
    end = _scalar_end(block, start)
    if block[start:end].strip() == "":
        raise ValueError(f"empty value for {field}")
    return Span(start, end)


def format_number(value: float | int) -> str:
    """Format a number the way the game writes it (``0``, ``1200``, ``0.5``)."""
    if isinstance(value, bool):
        raise ValueError("not a number")
    if isinstance(value, int):
        return str(value)
    float_value = float(value)
    if float_value.is_integer() and abs(float_value) < 1e15:
        return str(int(float_value))
    return repr(float_value)


def format_scalar(value: Any) -> str:
    if isinstance(value, bool):
        return _TRUE_LITERAL if value else _FALSE_LITERAL
    if value is None:
        return _NULL_LITERAL
    if isinstance(value, (int, float)):
        return format_number(value)
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=True)
    raise ValueError(f"cannot write value of type {type(value).__name__}")


@dataclass
class FieldEdit:
    """One field change inside one object span, as an absolute text range plus new text."""

    start: int
    end: int
    replacement: str

    @property
    def absolute(self) -> bool:
        return True


def build_edits(text: str, spans: list[Span], changes: Iterable[tuple[int, str, Any]]) -> list[FieldEdit]:
    """Turn ``(disc index, field, value)`` changes into absolute text edits.

    ``spans`` is the list of per-record spans from :func:`disc_spans`, in file order, so
    index ``i`` in ``changes`` is the same disc the JSON parse gives at position ``i``.
    """
    edits: list[FieldEdit] = []
    for index, field, value in changes:
        if index < 0 or index >= len(spans):
            raise IndexError(f"no disc at index {index}")
        span = spans[index]
        block = text[span.start:span.end]
        local = field_span(block, field)
        replacement = format_scalar(value)
        if block[local.start:local.end] == replacement:
            continue
        edits.append(FieldEdit(span.start + local.start, span.start + local.end, replacement))
    return edits


def apply_edits(text: str, edits: list[FieldEdit]) -> str:
    """Apply edits back-to-front so earlier replacements do not shift later offsets."""
    out = text
    for edit in sorted(edits, key=lambda e: e.start, reverse=True):
        out = out[:edit.start] + edit.replacement + out[edit.end:]
    return out


def change_field_values(text: str, key: str, field: str, values: list[Any]) -> str:
    """Convenience: set ``field`` on every record under ``key`` to ``values`` in order."""
    spans = disc_spans(text, key)
    if len(spans) != len(values):
        raise ValueError(f"{key} has {len(spans)} records but {len(values)} values were given")
    edits = build_edits(text, spans, [(i, field, v) for i, v in enumerate(values)])
    return apply_edits(text, edits)
