from __future__ import annotations

import csv
import json
from datetime import datetime

from telegram_message_exporter.exporters import (
    copy_message_media,
    render_csv,
    render_html,
    render_markdown,
    resolve_speaker,
)
from telegram_message_exporter.models import Attachment, ForwardInfo, Message


def sample_message() -> Message:
    return Message(
        timestamp=datetime(2026, 2, 4, 14, 13, 9),
        text="hello https://example.com",
        outgoing=True,
        peer_id=100,
        author_id=200,
        attachments=(
            Attachment(
                kind="image",
                filename="photo.jpg",
                cache_key="telegram-cloud-photo-size-1-2-y",
                mime_type="image/jpeg",
            ),
        ),
        forward_info=ForwardInfo(
            author_id=300,
            source_id=400,
            source_message_peer_id=500,
            source_message_namespace=0,
            source_message_id=42,
            date=datetime(2025, 1, 1, 1, 2, 3),
            author_signature="Forwarder",
            psa_type=None,
            is_imported=True,
        ),
    )


def test_resolve_speaker_keeps_custom_me_name() -> None:
    msg = Message(None, "hello", True, 1, None)

    assert resolve_speaker(msg, {}, "Simon") == "Simon"


def test_copy_message_media_copies_cached_attachment(tmp_path) -> None:
    media_dir = tmp_path / "media"
    media_dir.mkdir()
    cache_key = "telegram-cloud-photo-size-1-2-y"
    (media_dir / cache_key).write_bytes(b"image")
    out_path = tmp_path / "exports" / "chat.html"

    messages, copied_count = copy_message_media([sample_message()], media_dir, out_path)

    assert copied_count == 1
    assert messages[0].attachments[0].exported_path == f"chat_media/{cache_key}"
    assert (tmp_path / "exports" / "chat_media" / cache_key).read_bytes() == b"image"


def test_render_markdown_includes_forward_and_attachment(tmp_path) -> None:
    out_path = tmp_path / "chat.md"
    message = sample_message()
    message = Message(
        **{
            **message.__dict__,
            "attachments": (
                Attachment(kind="image", filename="photo.jpg", exported_path="m/p.jpg"),
            ),
        }
    )

    render_markdown([message], "Chat", out_path)

    output = out_path.read_text(encoding="utf-8")

    assert "Forwarded from Forwarder" in output
    assert "![photo.jpg](m/p.jpg)" in output
    assert "<https://example.com>" in output


def test_render_csv_appends_json_metadata(tmp_path) -> None:
    out_path = tmp_path / "chat.csv"

    render_csv([sample_message()], out_path, me_name="Simon")

    rows = list(csv.DictReader(out_path.open(encoding="utf-8")))

    assert rows[0]["speaker"] == "Simon"
    assert json.loads(rows[0]["attachments"])[0]["filename"] == "photo.jpg"
    assert json.loads(rows[0]["forward_info"])["author_signature"] == "Forwarder"


def test_render_html_embeds_media_and_forward_info(tmp_path) -> None:
    out_path = tmp_path / "chat.html"
    message = Message(
        **{
            **sample_message().__dict__,
            "attachments": (
                Attachment(
                    kind="image",
                    filename="photo.jpg",
                    exported_path="chat_media/photo.jpg",
                    mime_type="image/jpeg",
                ),
            ),
        }
    )

    render_html([message], "Chat", out_path, me_name="Simon")
    output = out_path.read_text(encoding="utf-8")

    assert "Forwarded from Forwarder" in output
    assert 'img src="chat_media/photo.jpg"' in output
