from __future__ import annotations

import sqlite3

from telegram_message_exporter.cli import (
    _referenced_peer_ids,
    _resolve_media_dir,
    build_parser,
)
from telegram_message_exporter.db import FetchOptions
from telegram_message_exporter.models import ForwardInfo, Message


def test_export_parser_keeps_me_name_and_adds_media_debug() -> None:
    parser = build_parser()
    args = parser.parse_args(
        [
            "export",
            "--db",
            "plain.db",
            "--peer-id",
            "123",
            "--me-name",
            "Simon",
            "--media-dir",
            "media",
            "--debug",
        ]
    )

    assert args.me_name == "Simon"
    assert args.media_dir == "media"
    assert args.debug is True


def test_resolve_media_dir_autodetects_sibling_media(tmp_path) -> None:
    db_dir = tmp_path / "account-1" / "postbox" / "db"
    media_dir = tmp_path / "account-1" / "postbox" / "media"
    db_dir.mkdir(parents=True)
    media_dir.mkdir(parents=True)
    db_path = db_dir / "db_sqlite"
    db_path.write_bytes(b"")

    assert _resolve_media_dir(None, db_path) == media_dir


def test_referenced_peer_ids_includes_forward_sources() -> None:
    msg = Message(
        timestamp=None,
        text="forwarded",
        outgoing=False,
        peer_id=10,
        author_id=11,
        forward_info=ForwardInfo(
            author_id=12,
            source_id=13,
            source_message_peer_id=14,
            source_message_namespace=0,
            source_message_id=99,
            date=None,
            author_signature=None,
            psa_type=None,
        ),
    )

    assert _referenced_peer_ids([msg], 10) == {10, 11, 12, 13, 14}


def test_iter_postbox_message_rows_uses_peer_prefix_range() -> None:
    from telegram_message_exporter.db import iter_postbox_message_rows

    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE t7 (key BLOB PRIMARY KEY, value BLOB)")

    rows = list(
        iter_postbox_message_rows(
            conn,
            "t7",
            FetchOptions(peer_id=123, start_ts=1, end_ts=2),
        )
    )

    assert rows == []


def test_iter_postbox_peer_rows_encodes_blob_keys() -> None:
    import struct

    from telegram_message_exporter.db import iter_postbox_peer_rows

    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE t2 (key BLOB PRIMARY KEY, value BLOB)")
    conn.execute(
        "INSERT INTO t2 (key, value) VALUES (?, ?)", (struct.pack(">q", 123), b"peer")
    )

    rows = list(iter_postbox_peer_rows(conn, "t2", [123]))

    assert rows == [(struct.pack(">q", 123), b"peer")]
