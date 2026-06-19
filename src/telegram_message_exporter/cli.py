#!/usr/bin/env python3
"""Command-line interface for Telegram Message Exporter."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Optional

import sqlite3

from . import __version__, crypto
from .db import (
    FetchOptions,
    detect_message_table,
    fetch_messages,
    is_postbox_kv_table,
    iter_postbox_message_rows,
    iter_postbox_peer_rows,
    list_tables,
    preview_value,
    sample_rows,
    search_peers,
    table_columns,
)
from .exporters import (
    RenderOptions,
    copy_message_media,
    render_csv,
    render_html,
    render_markdown,
)
from .postbox import (
    PostboxMediaResolver,
    iter_postbox_messages,
    list_peers_postbox,
    load_peer_map,
)
from .schema import PostboxTable
from .utils import parse_date_input


def cmd_decrypt(args: argparse.Namespace) -> None:
    """Decrypt an encrypted Telegram DB."""
    key_path = Path(args.key).expanduser()
    db_path = Path(args.db).expanduser()
    out_path = Path(args.out).expanduser()

    if not key_path.exists():
        raise SystemExit(f"Key file not found: {key_path}")
    if not db_path.exists():
        raise SystemExit(f"Database file not found: {db_path}")

    passcodes = crypto.read_passcodes(args.passcode)
    result = crypto.decrypt_database(key_path, db_path, out_path, passcodes)

    if args.debug:
        if result.key_info.local_key is not None:
            print(f"Local key length: {len(result.key_info.local_key)} bytes")
        print(f"Tempkey parse: {'ok' if result.key_info.tempkey_ok else 'failed'}")
        print(
            f"Decryption profile succeeded: {result.match.profile.name} "
            f"(key={result.match.candidate.name})"
        )

    size_mb = out_path.stat().st_size / (1024 * 1024)
    print(f"Decrypted DB written to {out_path} ({size_mb:.2f} MB)")


def cmd_diagnose(args: argparse.Namespace) -> None:
    """Inspect a plaintext Telegram DB."""
    db_path = Path(args.db).expanduser()
    if not db_path.exists():
        raise SystemExit(f"Database file not found: {db_path}")

    conn = sqlite3.connect(str(db_path))
    tables = list_tables(conn)
    print("Tables:")
    for table in tables:
        print(f"  - {table}")

    message_table = PostboxTable.MESSAGE_HISTORY.sqlite_name
    table = args.table or (message_table if message_table in tables else None)
    if table:
        print("\nColumns:")
        for col in table_columns(conn, table):
            print(f"  {col[1]} ({col[2]})")

        print("\nSample rows:")
        for idx, row in enumerate(sample_rows(conn, table), start=1):
            print(f"Row {idx}:")
            for col_idx, value in enumerate(row):
                print(f"  [{col_idx}] {preview_value(value)}")
    conn.close()


def cmd_list_peers(args: argparse.Namespace) -> None:
    """List peer IDs from a plaintext DB."""
    db_path = Path(args.db).expanduser()
    if not db_path.exists():
        raise SystemExit(f"Database file not found: {db_path}")

    conn = sqlite3.connect(str(db_path))
    results = []
    peer_table = PostboxTable.PEER.sqlite_name
    if peer_table in list_tables(conn) and is_postbox_kv_table(conn, peer_table):
        rows = conn.execute(f"SELECT key, value FROM {peer_table}").fetchall()
        results = list_peers_postbox(rows, args.search)
    else:
        results = search_peers(conn, args.search)
    conn.close()

    if not results:
        print("No peer records found with the current heuristic.")
        return

    print("Possible peers:")
    for table_name, peer_id, display in results:
        print(f"  {peer_id}  {display}  (table={table_name})")


def cmd_export(args: argparse.Namespace) -> None:
    """Export messages to Markdown, HTML, or CSV."""
    db_path = Path(args.db).expanduser()
    if not db_path.exists():
        raise SystemExit(f"Database file not found: {db_path}")

    conn = sqlite3.connect(str(db_path))
    table = args.table or detect_message_table(conn)

    tables = list_tables(conn)
    peer_id = _resolve_peer_id(conn, args.contact, args.peer_id, tables)

    options = FetchOptions(
        peer_id=peer_id,
        limit=args.limit,
        start_ts=parse_date_input(args.start_date, end=False),
        end_ts=parse_date_input(args.end_date, end=True),
    )

    peer_map: Optional[dict[int, str]] = None
    if is_postbox_kv_table(conn, table):
        messages, peer_map = _load_postbox_export(conn, table, options, tables, args)
    else:
        messages = fetch_messages(conn, table, options)
    conn.close()

    if not messages:
        raise SystemExit("No messages found with the current filters.")

    title = args.contact or _title_from_peer(peer_map, peer_id)
    out_path = Path(args.out) if args.out else _default_out_path(args.format)
    media_dir = _resolve_media_dir(args.media_dir, db_path)
    if media_dir is not None:
        messages, copied_count = copy_message_media(messages, media_dir, out_path)
        if args.debug:
            print(
                f"[media] copied {copied_count} cached files from {media_dir}",
                file=sys.stderr,
            )

    if args.format == "md":
        render_markdown(
            messages,
            title,
            out_path,
            options=RenderOptions(
                peer_map=peer_map,
                me_name=args.me_name,
                show_direction=args.show_direction,
            ),
        )
    elif args.format == "csv":
        render_csv(messages, out_path, peer_map=peer_map, me_name=args.me_name)
    elif args.format == "html":
        render_html(messages, title, out_path, peer_map=peer_map, me_name=args.me_name)
    else:
        raise SystemExit(f"Unknown format: {args.format}")

    print(f"Exported {len(messages)} messages to {out_path}")


def _load_postbox_export(
    conn,
    table: str,
    options: FetchOptions,
    tables: list[str],
    args: argparse.Namespace,
):
    """Load Postbox messages plus the smallest useful peer map."""
    peer_table = PostboxTable.PEER.sqlite_name
    media_table = PostboxTable.MESSAGE_MEDIA.sqlite_name
    media_resolver = (
        PostboxMediaResolver(conn, media_table, table)
        if media_table in tables
        else None
    )
    rows = iter_postbox_message_rows(conn, table, options, debug=args.debug)
    messages = iter_postbox_messages(
        rows,
        peer_id=options.peer_id,
        start_ts=options.start_ts,
        end_ts=options.end_ts,
        limit=options.limit,
        media_resolver=media_resolver,
    )
    has_peer_table = peer_table in tables and is_postbox_kv_table(conn, peer_table)
    if not has_peer_table:
        return messages, {}
    if options.peer_id is None:
        peer_rows = conn.execute(f"SELECT key, value FROM {peer_table}")
    else:
        peer_rows = iter_postbox_peer_rows(
            conn,
            peer_table,
            _referenced_peer_ids(messages, options.peer_id),
            debug=args.debug,
        )
    return messages, load_peer_map(peer_rows)


def _title_from_peer(peer_map: Optional[dict[int, str]], peer_id: Optional[int]) -> str:
    if peer_map and peer_id and peer_id in peer_map:
        return peer_map[peer_id]
    if peer_id is not None:
        return f"peer {peer_id}"
    return "All Chats"


def _default_out_path(fmt: str) -> Path:
    suffix = {"md": "md", "csv": "csv", "html": "html"}.get(fmt, "md")
    return Path(f"chat_export.{suffix}")


def _resolve_media_dir(value: Optional[str], db_path: Path) -> Optional[Path]:
    if value:
        media_dir = Path(value).expanduser()
        if not media_dir.is_dir():
            raise SystemExit(f"Media directory not found: {media_dir}")
        return media_dir
    if db_path.parent.name == "db":
        candidate = db_path.parent.parent / "media"
        if candidate.is_dir():
            return candidate
    return None


def _referenced_peer_ids(messages, requested_peer_id: Optional[int]) -> set[int]:
    peer_ids = {requested_peer_id} if requested_peer_id is not None else set()
    for message in messages:
        for peer_id in (message.peer_id, message.author_id):
            if peer_id is not None:
                peer_ids.add(peer_id)
        if message.forward_info is None:
            continue
        for peer_id in (
            message.forward_info.author_id,
            message.forward_info.source_id,
            message.forward_info.source_message_peer_id,
        ):
            if peer_id is not None:
                peer_ids.add(peer_id)
    return peer_ids


def _resolve_peer_id(
    conn,
    contact: Optional[str],
    peer_id: Optional[int],
    tables: Optional[list[str]] = None,
) -> Optional[int]:
    if not contact or peer_id is not None:
        return peer_id

    matches = _search_contact_matches(conn, contact, tables)
    if matches:
        if len(matches) == 1:
            return matches[0][1]
        print("Multiple peer matches found. Use --peer-id to select one:")
        for table_name, candidate_id, display in matches:
            print(f"  {candidate_id}  {display}  (table={table_name})")
        raise SystemExit(2)
    raise SystemExit("Contact name not found. Use list-peers or provide --peer-id.")


def _search_contact_matches(
    conn,
    contact: str,
    tables: Optional[list[str]] = None,
) -> list[tuple[str, int, str]]:
    tables = tables or list_tables(conn)
    peer_table = PostboxTable.PEER.sqlite_name
    if peer_table in tables and is_postbox_kv_table(conn, peer_table):
        rows = conn.execute(f"SELECT key, value FROM {peer_table}").fetchall()
        return list_peers_postbox(rows, contact)
    return search_peers(conn, contact)


def build_parser() -> argparse.ArgumentParser:
    """Build the CLI argument parser."""
    parser = argparse.ArgumentParser(
        description="Telegram for macOS message recovery tools",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
        help="Show version and exit",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    decrypt = subparsers.add_parser("decrypt", help="Decrypt db_sqlite to plaintext DB")
    decrypt.add_argument("--key", required=True, help="Path to .tempkeyEncrypted")
    decrypt.add_argument("--db", required=True, help="Path to db_sqlite")
    decrypt.add_argument("--out", default="plaintext.db", help="Output plaintext DB")
    decrypt.add_argument(
        "--passcode", help="Telegram local passcode (or set TG_LOCAL_PASSCODE)"
    )
    decrypt.add_argument("--debug", action="store_true", help="Print extra diagnostics")
    decrypt.set_defaults(func=cmd_decrypt)

    diagnose = subparsers.add_parser("diagnose", help="Inspect plaintext DB")
    diagnose.add_argument("--db", required=True, help="Path to plaintext DB")
    diagnose.add_argument("--table", help="Table name to sample")
    diagnose.set_defaults(func=cmd_diagnose)

    list_peers = subparsers.add_parser("list-peers", help="Find peer IDs by name")
    list_peers.add_argument("--db", required=True, help="Path to plaintext DB")
    list_peers.add_argument("--search", help="Name fragment to search")
    list_peers.set_defaults(func=cmd_list_peers)

    export = subparsers.add_parser(
        "export", help="Export messages to Markdown/HTML/CSV"
    )
    export.add_argument("--db", required=True, help="Path to plaintext DB")
    export.add_argument("--contact", help="Contact name to match")
    export.add_argument("--peer-id", type=int, help="Peer ID to export")
    export.add_argument("--table", help="Override messages table")
    export.add_argument("--limit", type=int, help="Limit number of messages")
    export.add_argument("--start-date", help="Start date (YYYY-MM-DD or ISO datetime)")
    export.add_argument("--end-date", help="End date (YYYY-MM-DD or ISO datetime)")
    export.add_argument(
        "--format",
        default="md",
        choices=["md", "csv", "html"],
        help="Export format (md, csv, html)",
    )
    export.add_argument("--out", help="Output file path (defaults by format)")
    export.add_argument("--me-name", default="Me", help="Label for outgoing messages")
    export.add_argument(
        "--media-dir",
        help="Telegram postbox/media directory; copies referenced cached files",
    )
    export.add_argument(
        "--show-direction", action="store_true", help="Append (in)/(out) labels"
    )
    export.add_argument(
        "--debug",
        action="store_true",
        help="Print SQL key ranges and query plans",
    )
    export.set_defaults(func=cmd_export)

    return parser


def main() -> None:
    """Entry point for CLI usage."""
    parser = build_parser()
    if len(sys.argv) == 1:
        parser.print_help()
        return
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
