from __future__ import annotations

import struct

from telegram_message_exporter.models import Attachment
from telegram_message_exporter.postbox import (
    MessageIndex,
    PostboxObject,
    _decode_root_object_safe,
    media_attachments,
)
from telegram_message_exporter.schema import TelegramMediaActionType


def test_message_index_round_trips_bytes() -> None:
    idx = MessageIndex(peer_id=123, namespace=0, message_id=456, timestamp=789)

    assert MessageIndex.from_bytes(idx.as_bytes()) == idx


def test_unknown_root_object_returns_none() -> None:
    assert _decode_root_object_safe(b"\x01") is None


def test_unknown_action_type_is_not_fatal() -> None:
    assert TelegramMediaActionType.safe(999) == TelegramMediaActionType.UNKNOWN


def test_media_attachments_for_image_uses_largest_representation() -> None:
    small_resource = PostboxObject(
        "CloudPhotoSizeMediaResource",
        {"d": 1, "i": struct.pack("<iq", 0, 111), "s": "s"},
    )
    large_resource = PostboxObject(
        "CloudPhotoSizeMediaResource",
        {"d": 1, "i": struct.pack("<iq", 0, 111), "s": "x"},
    )
    media = PostboxObject(
        "TelegramMediaImage",
        {
            "r": [
                PostboxObject(
                    "TelegramMediaImageRepresentation",
                    {"dx": 64, "dy": 64, "r": small_resource},
                ),
                PostboxObject(
                    "TelegramMediaImageRepresentation",
                    {"dx": 800, "dy": 600, "r": large_resource},
                ),
            ]
        },
    )

    attachments = media_attachments(media)

    assert attachments == (
        [
            Attachment(
                kind="image",
                cache_key="telegram-cloud-photo-size-1-111-x",
                alternate_cache_keys=("telegram-cloud-photo-size-1-111-s",),
                width=800,
                height=600,
            )
        ]
    )
