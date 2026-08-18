"""Generic mysqldump `INSERT INTO` parsing, shared by every source-bot adapter.

No SQL-parsing dependency is used on purpose: mysqldump output is regular enough
(one INSERT INTO `table` (cols) VALUES (...),(...),...; statement per batch) that a
small hand-rolled, escape-aware tokenizer is enough and avoids pulling in a full SQL
grammar just to read backup files we generate a preview from.
"""

from __future__ import annotations

import re
from collections.abc import Iterator

_ESCAPE_MAP = {"n": "\n", "r": "\r", "t": "\t", "0": "\0", "b": "\b", "Z": "\x1a"}


def _split_columns(raw: str) -> list[str]:
    return [c.strip().strip("`") for c in raw.split(",")]


def _read_sql_tuple(text: str, pos: int) -> tuple[list[str], int]:
    """Read one `(...)` value tuple starting at text[pos] == '('.

    Returns (raw value strings — still quoted/escaped, index right after the closing ')').
    """
    n = len(text)
    i = pos + 1
    values: list[str] = []
    buf: list[str] = []
    in_string = False
    quote_char = ""
    while i < n:
        ch = text[i]
        if in_string:
            if ch == "\\" and i + 1 < n:
                buf.append(ch)
                buf.append(text[i + 1])
                i += 2
                continue
            if ch == quote_char:
                in_string = False
                buf.append(ch)
                i += 1
                continue
            buf.append(ch)
            i += 1
            continue
        if ch in ("'", '"'):
            in_string = True
            quote_char = ch
            buf.append(ch)
            i += 1
            continue
        if ch == ",":
            values.append("".join(buf).strip())
            buf = []
            i += 1
            continue
        if ch == ")":
            values.append("".join(buf).strip())
            return values, i + 1
        buf.append(ch)
        i += 1
    raise ValueError("Unterminated SQL value tuple in dump")


def _unescape_sql_value(raw: str) -> str | None:
    raw = raw.strip()
    if not raw or raw.upper() == "NULL":
        return None
    if len(raw) >= 2 and raw[0] == raw[-1] and raw[0] in ("'", '"'):
        quote = raw[0]
        inner = raw[1:-1]
        out: list[str] = []
        i = 0
        n = len(inner)
        while i < n:
            ch = inner[i]
            if ch == "\\" and i + 1 < n:
                nxt = inner[i + 1]
                out.append(_ESCAPE_MAP.get(nxt, nxt))
                i += 2
                continue
            if ch == quote and i + 1 < n and inner[i + 1] == quote:
                out.append(quote)
                i += 2
                continue
            out.append(ch)
            i += 1
        return "".join(out)
    return raw


def iter_insert_rows(sql_text: str, table_name: str) -> Iterator[dict[str, str | None]]:
    """Yield one dict[column_name, value] per row from every INSERT INTO `table_name` statement.

    Column mapping comes from the statement's own explicit column list, not positional
    guessing, so this stays correct even if a future dump reorders columns.
    """
    pattern = re.compile(
        r"INSERT INTO\s+`" + re.escape(table_name) + r"`\s*\((?P<columns>[^)]*)\)\s*VALUES\s*",
        re.IGNORECASE,
    )
    n = len(sql_text)
    for match in pattern.finditer(sql_text):
        columns = _split_columns(match.group("columns"))
        i = match.end()
        while i < n:
            while i < n and sql_text[i] in " \t\r\n,":
                i += 1
            if i >= n or sql_text[i] != "(":
                break
            raw_values, i = _read_sql_tuple(sql_text, i)
            yield {col: _unescape_sql_value(val) for col, val in zip(columns, raw_values, strict=False)}
