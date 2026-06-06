"""Database helpers for Telegram plaintext SQLite exports."""

from __future__ import annotations

import sqlite3
import struct
import sys
import time
from dataclasses import dataclass
from typing import Iterable, Optional

from .models import Message
from .schema import PostboxTable
from .utils import parse_timestamp


def list_tables(conn: sqlite3.Connection) -> list[str]:
    """Return all table names in the database."""
    rows = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    return [row[0] for row in rows]


def table_columns(conn: sqlite3.Connection, table: str) -> list[tuple]:
    """Return PRAGMA column info for a table."""
    return conn.execute(f"PRAGMA table_info({table})").fetchall()


def detect_column(cols: list[tuple], names: Iterable[str]) -> Optional[str]:
    """Detect the first column matching any of the given names."""
    name_set = {name.lower() for name in names}
    for col in cols:
        if col[1].lower() in name_set:
            return col[1]
    return None


def detect_message_table(conn: sqlite3.Connection) -> str:
    """Best-effort detection of a messages table."""
    tables = list_tables(conn)
    message_table = PostboxTable.MESSAGE_HISTORY.sqlite_name
    if message_table in tables:
        return message_table
    if "messages" in tables:
        return "messages"

    candidates: list[tuple[str, int]] = []
    for table in tables:
        cols = table_columns(conn, table)
        col_names = {col[1].lower() for col in cols}
        has_message = any(name in col_names for name in ("message", "text", "data"))
        has_date = any(name in col_names for name in ("date", "timestamp", "time"))
        if not (has_message and has_date):
            continue
        try:
            count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        except sqlite3.DatabaseError:
            continue
        candidates.append((table, count))

    if candidates:
        candidates.sort(key=lambda item: item[1], reverse=True)
        return candidates[0][0]

    raise SystemExit("Could not identify a messages table. Run diagnose to inspect.")


def is_postbox_kv_table(conn: sqlite3.Connection, table: str) -> bool:
    """Return True if the table is a Postbox key/value pair table."""
    cols = table_columns(conn, table)
    if len(cols) != 2:
        return False
    names = [col[1].lower() for col in cols]
    return names == ["key", "value"]


def plausible_text(text: str) -> bool:
    """Heuristic to decide whether extracted text is meaningful."""
    if not text or len(text) < 2:
        return False
    printable = sum(1 for ch in text if ch.isprintable()) / max(len(text), 1)
    if printable < 0.9:
        return False
    return any(ch.isalpha() for ch in text) or " " in text


def score_text(text: str) -> float:
    """Score candidate text; higher is more likely a message."""
    score = len(text)
    score += 5 if " " in text else 0
    score += 5 if any(ch.isalpha() for ch in text) else 0
    if text.count("\n") > 20:
        score -= 10
    return score


def extract_tl_strings(blob: bytes) -> list[str]:
    """Extract possible TL-encoded strings from a blob."""
    strings: list[str] = []
    length = len(blob)
    for idx in range(length):
        if blob[idx] == 0:
            continue
        if blob[idx] == 254:
            if idx + 4 > length:
                continue
            str_len = blob[idx + 1] | (blob[idx + 2] << 8) | (blob[idx + 3] << 16)
            start = idx + 4
        else:
            str_len = blob[idx]
            start = idx + 1
        if str_len <= 0:
            continue
        end = start + str_len
        if end > length:
            continue
        try:
            candidate = blob[start:end].decode("utf-8")
        except UnicodeDecodeError:
            continue
        if plausible_text(candidate):
            strings.append(candidate)
    return strings


def extract_message_text(value: object) -> Optional[str]:
    """Extract likely message text from a DB value."""
    if value is None:
        return None
    if isinstance(value, str):
        return value.strip() or None
    if isinstance(value, bytes):
        candidates = extract_tl_strings(value)
        if not candidates:
            return None
        candidates.sort(key=score_text, reverse=True)
        return candidates[0].strip() or None
    return None


@dataclass(frozen=True)
class FetchOptions:
    """Filtering options when retrieving messages."""

    peer_id: Optional[int] = None
    limit: Optional[int] = None
    start_ts: Optional[int] = None
    end_ts: Optional[int] = None


def _prefix_successor(prefix: bytes) -> Optional[bytes]:
    """Return the smallest byte string greater than every key with this prefix."""
    successor = bytearray(prefix)
    for index in range(len(successor) - 1, -1, -1):
        if successor[index] != 0xFF:
            successor[index] += 1
            return bytes(successor[: index + 1])
    return None


def _postbox_key_prefix(peer_id: int) -> bytes:
    """Encode the peer-id prefix of a MessageHistoryTable key."""
    return struct.pack(">q", peer_id)


def _postbox_range_query(
    table: str,
    lower: bytes,
    upper: Optional[bytes],
) -> tuple[str, tuple[bytes, ...]]:
    query = f"SELECT key, value FROM {table} WHERE key >= ?"
    params = (lower,)
    if upper is not None:
        query += " AND key < ?"
        params += (upper,)
    return query + " ORDER BY key", params


def _debug_postbox_query(
    conn: sqlite3.Connection,
    label: str,
    query: str,
    params: tuple[object, ...] = (),
) -> None:
    """Print SQL and query-plan diagnostics for a Postbox lookup."""
    print(f"[query] {label}", file=sys.stderr)
    print(f"[query] SQL: {query}", file=sys.stderr)
    for index, param in enumerate(params, start=1):
        if isinstance(param, bytes):
            display = f"X'{param.hex()}'"
        else:
            display = repr(param)
        print(f"[query] param {index}: {display}", file=sys.stderr)
    for plan_row in conn.execute(f"EXPLAIN QUERY PLAN {query}", params):
        print(f"[query] plan: {plan_row[3]}", file=sys.stderr)


def _iter_query(
    conn: sqlite3.Connection,
    label: str,
    query: str,
    params: tuple[object, ...] = (),
    debug: bool = False,
) -> Iterable[tuple]:
    """Stream query rows and optionally report diagnostics."""
    if debug:
        _debug_postbox_query(conn, label, query, params)
    started_at = time.monotonic()
    row_count = 0
    try:
        for row in conn.execute(query, params):
            row_count += 1
            yield row
    finally:
        if debug:
            elapsed = time.monotonic() - started_at
            print(
                f"[query] consumed {row_count} rows in {elapsed:.3f}s: {label}",
                file=sys.stderr,
            )


def iter_postbox_message_rows(
    conn: sqlite3.Connection,
    table: str,
    options: FetchOptions,
    debug: bool = False,
) -> Iterable[tuple]:
    """Stream Postbox message rows using the BLOB key index when possible."""
    if options.peer_id is None:
        query = f"SELECT key, value FROM {table} ORDER BY key"
        yield from _iter_query(
            conn,
            "all peers (full ordered scan)",
            query,
            debug=debug,
        )
        return

    peer_prefix = _postbox_key_prefix(options.peer_id)
    query, params = _postbox_range_query(
        table,
        peer_prefix,
        _prefix_successor(peer_prefix),
    )
    yield from _iter_query(
        conn,
        f"peer {options.peer_id} (single key range)",
        query,
        params,
        debug,
    )


def iter_postbox_peer_rows(
    conn: sqlite3.Connection,
    table: str,
    peer_ids: Iterable[int],
    debug: bool = False,
) -> Iterable[tuple]:
    """Fetch selected Postbox peer rows through exact key lookups."""
    keys = tuple(struct.pack(">q", peer_id) for peer_id in sorted(set(peer_ids)))
    if not keys:
        return

    placeholders = ", ".join("?" for _ in keys)
    query = f"SELECT key, value FROM {table} WHERE key IN ({placeholders})"
    yield from _iter_query(
        conn,
        f"selected peers ({len(keys)} exact keys)",
        query,
        keys,
        debug,
    )


@dataclass(frozen=True)
class MessageColumns:
    """Resolved column names for a message table."""

    date: Optional[str]
    text: Optional[str]
    blob: Optional[str]
    peer: Optional[str]
    outgoing: Optional[str]
    all_columns: tuple[str, ...]


def detect_message_columns(cols: list[tuple]) -> MessageColumns:
    """Detect common message-related columns."""
    date_col = detect_column(cols, ("date", "date_", "timestamp", "time", "created_at"))
    text_col = detect_column(cols, ("message", "text"))
    blob_col = detect_column(cols, ("data", "blob", "raw", "payload"))
    peer_col = detect_column(cols, ("peer_id", "dialog_id", "chat_id", "channel_id"))
    out_col = detect_column(cols, ("out", "is_out", "outgoing"))
    all_cols = tuple(col[1] for col in cols)
    return MessageColumns(date_col, text_col, blob_col, peer_col, out_col, all_cols)


def build_message_query(
    table: str, columns: MessageColumns, options: FetchOptions
) -> tuple[str, list[object]]:
    """Build SQL for message selection."""
    select_cols = ["rowid", *columns.all_columns]
    query = f"SELECT {', '.join(select_cols)} FROM {table}"
    params: list[object] = []
    if options.peer_id is not None and columns.peer:
        query += f" WHERE {columns.peer} = ?"
        params.append(options.peer_id)
    if columns.date:
        query += f" ORDER BY {columns.date} ASC"
    else:
        query += " ORDER BY rowid ASC"
    if options.limit:
        query += " LIMIT ?"
        params.append(options.limit)
    return query, params


def row_to_map(row: tuple, columns: MessageColumns) -> dict[str, object]:
    """Build a dictionary mapping column names to values."""
    row_map = {"rowid": row[0]}
    for idx, name in enumerate(columns.all_columns, start=1):
        row_map[name] = row[idx]
    return row_map


def row_timestamp(row_map: dict[str, object], columns: MessageColumns):
    """Return parsed timestamp for a row."""
    return parse_timestamp(row_map.get(columns.date)) if columns.date else None


def row_in_range(ts, options: FetchOptions) -> bool:
    """Check whether a timestamp fits the requested range."""
    if options.start_ts is not None and (
        ts is None or int(ts.timestamp()) < options.start_ts
    ):
        return False
    if options.end_ts is not None and (
        ts is None or int(ts.timestamp()) > options.end_ts
    ):
        return False
    return True


def parse_outgoing(
    row_map: dict[str, object], columns: MessageColumns
) -> Optional[bool]:
    """Parse outgoing flag from a row."""
    if not columns.outgoing:
        return None
    value = row_map.get(columns.outgoing)
    if value is None:
        return None
    try:
        return bool(int(value))
    except (TypeError, ValueError):
        return None


def parse_peer_id(row_map: dict[str, object], columns: MessageColumns) -> Optional[int]:
    """Parse peer ID from a row."""
    if not columns.peer:
        return None
    value = row_map.get(columns.peer)
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def extract_text(row_map: dict[str, object], columns: MessageColumns) -> Optional[str]:
    """Extract message text from a row."""
    text = None
    if columns.text:
        text = extract_message_text(row_map.get(columns.text))
    if not text and columns.blob:
        text = extract_message_text(row_map.get(columns.blob))
    return text


def fetch_messages(
    conn: sqlite3.Connection,
    table: str,
    options: FetchOptions,
) -> list[Message]:
    """Fetch messages from a non-Postbox table."""
    cols = table_columns(conn, table)
    columns = detect_message_columns(cols)
    query, params = build_message_query(table, columns, options)
    rows = conn.execute(query, params).fetchall()
    messages: list[Message] = []
    for row in rows:
        row_map = row_to_map(row, columns)
        ts = row_timestamp(row_map, columns)
        if not row_in_range(ts, options):
            continue
        text = extract_text(row_map, columns)
        if not text:
            continue
        outgoing = parse_outgoing(row_map, columns)
        peer_val = parse_peer_id(row_map, columns)

        messages.append(
            Message(
                timestamp=ts,
                text=text,
                outgoing=outgoing,
                peer_id=peer_val,
                author_id=None,
            )
        )
    return messages


PEER_NAME_FIELDS = ("name", "title", "username", "first_name", "last_name")
PEER_ID_FIELDS = ("peer_id", "id", "user_id", "chat_id", "dialog_id")
PEER_QUERY_LIMIT = 200


@dataclass(frozen=True)
class PeerTableInfo:
    """Metadata for a table containing peer info."""

    table: str
    id_column: str
    name_columns: tuple[str, ...]


def detect_peer_tables(conn: sqlite3.Connection) -> list[PeerTableInfo]:
    """Detect tables that likely contain peer records."""
    infos: list[PeerTableInfo] = []
    for table in list_tables(conn):
        cols = table_columns(conn, table)
        col_names = [col[1] for col in cols]
        name_cols = [c for c in col_names if c.lower() in PEER_NAME_FIELDS]
        id_cols = [c for c in col_names if c.lower() in PEER_ID_FIELDS]
        if not name_cols or not id_cols:
            continue
        infos.append(PeerTableInfo(table, id_cols[0], tuple(name_cols)))
    return infos


def build_peer_query(info: PeerTableInfo, term: Optional[str]) -> tuple[str, list[str]]:
    """Build the SQL query for a peer search."""
    select_cols = [info.id_column, *info.name_columns]
    query = f"SELECT {', '.join(select_cols)} FROM {info.table}"
    params: list[str] = []
    if term:
        query += " WHERE " + " OR ".join([f"{col} LIKE ?" for col in info.name_columns])
        params = [f"%{term}%" for _ in info.name_columns]
    query += f" LIMIT {PEER_QUERY_LIMIT}"
    return query, params


def build_peer_display(values: Iterable[object]) -> Optional[str]:
    """Build a display name from row values."""
    name_parts = [str(value) for value in values if value]
    if not name_parts:
        return None
    return " ".join(name_parts).strip()


def query_peer_table(
    conn: sqlite3.Connection,
    info: PeerTableInfo,
    term: Optional[str],
) -> list[tuple[str, int, str]]:
    """Query a single table for peer matches."""
    query, params = build_peer_query(info, term)
    try:
        rows = conn.execute(query, params).fetchall()
    except sqlite3.DatabaseError:
        return []

    results: list[tuple[str, int, str]] = []
    for row in rows:
        peer_id = row[0]
        if peer_id is None:
            continue
        display = build_peer_display(row[1:])
        if not display:
            continue
        results.append((info.table, int(peer_id), display))
    return results


def search_peers(
    conn: sqlite3.Connection, term: Optional[str]
) -> list[tuple[str, int, str]]:
    """Search for peer names in non-Postbox tables."""
    results: list[tuple[str, int, str]] = []
    seen: set[tuple[str, int, str]] = set()
    for info in detect_peer_tables(conn):
        for record in query_peer_table(conn, info, term):
            if record in seen:
                continue
            seen.add(record)
            results.append(record)
    return results


def sample_rows(conn: sqlite3.Connection, table: str, limit: int = 3) -> list[tuple]:
    """Fetch sample rows for diagnostics."""
    return conn.execute(f"SELECT * FROM {table} LIMIT {limit}").fetchall()


def preview_value(value: object) -> str:
    """Return a short preview string for a database value."""
    if isinstance(value, bytes):
        preview = extract_message_text(value)
        if preview:
            return preview[:80] + ("..." if len(preview) > 80 else "")
        return f"<bytes {len(value)}>"
    return repr(value)
