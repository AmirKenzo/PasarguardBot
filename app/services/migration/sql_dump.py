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


def _split_top_level(body: str) -> list[str]:
    """Split a CREATE TABLE body on top-level commas (not inside parens/quotes)."""
    parts: list[str] = []
    buf: list[str] = []
    depth = 0
    in_string = False
    quote_char = ""
    i = 0
    n = len(body)
    while i < n:
        ch = body[i]
        if in_string:
            buf.append(ch)
            if ch == "\\" and i + 1 < n:
                buf.append(body[i + 1])
                i += 2
                continue
            if ch == quote_char:
                in_string = False
            i += 1
            continue
        if ch in ("'", '"'):
            in_string = True
            quote_char = ch
            buf.append(ch)
            i += 1
            continue
        if ch == "(":
            depth += 1
            buf.append(ch)
            i += 1
            continue
        if ch == ")":
            depth -= 1
            buf.append(ch)
            i += 1
            continue
        if ch == "," and depth == 0:
            parts.append("".join(buf))
            buf = []
            i += 1
            continue
        buf.append(ch)
        i += 1
    if buf:
        parts.append("".join(buf))
    return parts


def _columns_from_create_table(sql_text: str, table_name: str) -> list[str]:
    """Column order for a table, read from its CREATE TABLE statement.

    Needed for dumps (phpMyAdmin/mysqldump without --complete-insert) that write
    INSERT INTO `table` VALUES (...) with no explicit column list.
    """
    match = re.search(
        r"CREATE TABLE\s+`" + re.escape(table_name) + r"`\s*\((?P<body>.*?)\)\s*ENGINE",
        sql_text,
        re.IGNORECASE | re.DOTALL,
    )
    if not match:
        return []
    columns = []
    for raw_def in _split_top_level(match.group("body")):
        raw_def = raw_def.strip()
        if raw_def.startswith("`"):
            end = raw_def.index("`", 1)
            columns.append(raw_def[1:end])
    return columns


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

    Handles both dump styles: an explicit column list (INSERT INTO `t` (a,b) VALUES ...,
    used by wizwiz's mysqldump) and a bare one (INSERT INTO `t` VALUES ..., used by
    faoxima's phpMyAdmin export) — in the bare case, column order is read once from the
    table's own CREATE TABLE statement instead of guessed.
    """
    pattern = re.compile(
        r"INSERT INTO\s+`" + re.escape(table_name) + r"`\s*(?:\((?P<columns>[^)]*)\)\s*)?VALUES\s*",
        re.IGNORECASE,
    )
    n = len(sql_text)
    fallback_columns: list[str] | None = None
    for match in pattern.finditer(sql_text):
        col_group = match.group("columns")
        if col_group:
            columns = _split_columns(col_group)
        else:
            if fallback_columns is None:
                fallback_columns = _columns_from_create_table(sql_text, table_name)
            columns = fallback_columns
        i = match.end()
        while i < n:
            while i < n and sql_text[i] in " \t\r\n,":
                i += 1
            if i >= n or sql_text[i] != "(":
                break
            raw_values, i = _read_sql_tuple(sql_text, i)
            yield {col: _unescape_sql_value(val) for col, val in zip(columns, raw_values, strict=False)}
