"""Telegram Postbox schema identifiers used by the exporter."""

from __future__ import annotations

import enum


class MessageNamespace(enum.IntEnum):
    """Known Telegram message-id namespaces."""

    CLOUD = 0
    LOCAL = 1
    SECRET_INCOMING = 2
    SCHEDULED_CLOUD = 3
    SCHEDULED_LOCAL = 4
    QUICK_REPLY_CLOUD = 5
    QUICK_REPLY_LOCAL = 6


class PostboxTable(enum.IntEnum):
    """Postbox SQLite table identifiers used by this project."""

    PEER = 2
    MESSAGE_MEDIA = 6
    MESSAGE_HISTORY = 7

    @property
    def sqlite_name(self) -> str:
        """Return the physical SQLite table name."""
        return f"t{int(self)}"


class TelegramMediaActionType(enum.IntEnum):
    """Known TelegramMediaActionType discriminators."""

    UNKNOWN = 0
    GROUP_CREATED = 1
    ADDED_MEMBERS = 2
    REMOVED_MEMBERS = 3
    PHOTO_UPDATED = 4
    TITLE_UPDATED = 5
    PINNED_MESSAGE_UPDATED = 6
    JOINED_BY_LINK = 7
    CHANNEL_MIGRATED_FROM_GROUP = 8
    GROUP_MIGRATED_TO_CHANNEL = 9
    HISTORY_CLEARED = 10
    HISTORY_SCREENSHOT = 11
    MESSAGE_AUTOREMOVE_TIMEOUT_UPDATED = 12
    GAME_SCORE = 13
    PHONE_CALL = 14
    PAYMENT_SENT = 15
    CUSTOM_TEXT = 16
    BOT_DOMAIN_ACCESS_GRANTED = 17
    BOT_SENT_SECURE_VALUES = 18
    PEER_JOINED = 19
    PHONE_NUMBER_REQUEST = 20
    GEO_PROXIMITY_REACHED = 21
    GROUP_PHONE_CALL = 22
    INVITE_TO_GROUP_PHONE_CALL = 23
    SET_CHAT_THEME = 24
    JOINED_BY_REQUEST = 25
    WEB_VIEW_DATA = 26
    GIFT_PREMIUM = 27
    TOPIC_CREATED = 28
    TOPIC_EDITED = 29
    SUGGESTED_PROFILE_PHOTO = 30
    ATTACH_MENU_BOT_ALLOWED = 31
    REQUESTED_PEER = 32
    SET_CHAT_WALLPAPER = 33
    SET_SAME_CHAT_WALLPAPER = 34
    BOT_APP_ACCESS_GRANTED = 35
    GIFT_CODE = 36
    GIVEAWAY_LAUNCHED = 37
    JOINED_CHANNEL = 38
    GIVEAWAY_RESULTS = 39
    BOOSTS_APPLIED = 40
    PAYMENT_REFUNDED = 41
    GIFT_STARS = 42
    PRIZE_STARS = 43
    STAR_GIFT = 44
    STAR_GIFT_UNIQUE = 45
    PAID_MESSAGES_REFUNDED = 46
    PAID_MESSAGES_PRICE_EDITED = 47
    CONFERENCE_CALL = 48
    TODO_COMPLETIONS = 49
    TODO_APPEND_TASKS = 50
    SUGGESTED_POST_APPROVAL_STATUS = 51
    GIFT_TON = 52
    SUGGESTED_POST_SUCCESS = 53
    SUGGESTED_POST_REFUND = 54
    SUGGESTED_BIRTHDAY = 55
    STAR_GIFT_PURCHASE_OFFER = 56
    STAR_GIFT_PURCHASE_OFFER_DECLINED = 57
    GROUP_CREATOR_CHANGE = 59
    COPY_PROTECTION_TOGGLE = 60
    COPY_PROTECTION_REQUEST = 61
    MANAGED_BOT_CREATED = 62
    POLL_OPTION_APPENDED = 63
    POLL_OPTION_DELETED = 64

    @classmethod
    def safe(cls, raw_value: int) -> "TelegramMediaActionType":
        """Return a known action type without failing on newer Telegram values."""
        try:
            return cls(raw_value)
        except ValueError:
            return cls.UNKNOWN


POSTBOX_MEDIA_TYPES = (
    "TelegramMediaAction",
    "TelegramMediaContact",
    "TelegramMediaDice",
    "TelegramMediaExpiredContent",
    "TelegramMediaFile",
    "TelegramMediaGame",
    "TelegramMediaGiveaway",
    "TelegramMediaGiveawayResults",
    "TelegramMediaImage",
    "TelegramMediaInvoice",
    "TelegramMediaLiveStream",
    "TelegramMediaMap",
    "TelegramMediaPaidContent",
    "TelegramMediaPoll",
    "TelegramMediaStory",
    "TelegramMediaTodo",
    "TelegramMediaUnsupported",
    "TelegramMediaWebpage",
)

POSTBOX_MEDIA_HELPER_TYPES = (
    "CloudDocumentMediaResource",
    "CloudDocumentSizeMediaResource",
    "CloudFileMediaResource",
    "CloudPeerPhotoSizeMediaResource",
    "CloudPhotoSizeMediaResource",
    "CloudStickerPackThumbnailMediaResource",
    "EmptyMediaResource",
    "HttpReferenceMediaResource",
    "LocalFileMediaResource",
    "LocalFileReferenceMediaResource",
    "SecretFileMediaResource",
    "SecureFileMediaResource",
    "TelegramMediaFileAttribute",
    "TelegramMediaImageRepresentation",
    "VideoRepresentation",
    "VideoThumbnail",
    "WebFileReferenceMediaResource",
    "WallpaperDataResource",
)

POSTBOX_MESSAGE_ATTRIBUTE_TYPES = (
    "AuthorSignatureMessageAttribute",
    "EditedMessageAttribute",
    "ForwardCountMessageAttribute",
    "ForwardOptionsMessageAttribute",
    "ForwardSourceInfoAttribute",
    "ForwardVideoTimestampAttribute",
    "ReplyMessageAttribute",
    "SourceAuthorInfoMessageAttribute",
    "SourceReferenceMessageAttribute",
    "TextEntitiesMessageAttribute",
    "ViewCountMessageAttribute",
)

POSTBOX_FIELD_ALIASES: dict[str, dict[str, str]] = {
    "CloudDocumentMediaResource": {
        "d": "datacenter_id",
        "f": "file_id",
        "a": "access_hash",
        "n64": "size",
        "n": "legacy_size",
        "fr": "file_reference",
        "fn": "file_name",
    },
    "CloudDocumentSizeMediaResource": {
        "d": "datacenter_id",
        "i": "document_id",
        "h": "access_hash",
        "s": "size_spec",
        "fr": "file_reference",
    },
    "CloudFileMediaResource": {
        "d": "datacenter_id",
        "v": "volume_id",
        "l": "local_id",
        "s": "secret",
        "n64": "size",
        "n": "legacy_size",
        "fr": "file_reference",
    },
    "CloudPeerPhotoSizeMediaResource": {
        "d": "datacenter_id",
        "p": "photo_id",
        "s": "size_spec",
        "v": "volume_id",
        "l": "local_id",
    },
    "CloudPhotoSizeMediaResource": {
        "d": "datacenter_id",
        "i": "photo_id",
        "h": "access_hash",
        "s": "size_spec",
        "n64": "size",
        "n": "legacy_size",
        "fr": "file_reference",
    },
    "CloudStickerPackThumbnailMediaResource": {
        "d": "datacenter_id",
        "t": "thumb_version",
        "v": "volume_id",
        "l": "local_id",
    },
    "HttpReferenceMediaResource": {
        "u": "url",
        "s64": "size",
        "s": "legacy_size",
    },
    "LocalFileMediaResource": {
        "f": "file_id",
        "sr": "is_secret_related",
        "s64": "size",
        "s": "legacy_size",
    },
    "LocalFileReferenceMediaResource": {
        "p": "local_file_path",
        "r": "random_id",
        "t": "is_uniquely_referenced_temporary_file",
        "s64": "size",
        "s": "legacy_size",
    },
    "SecretFileMediaResource": {
        "i": "file_id",
        "a": "access_hash",
        "s64": "container_size",
        "s": "legacy_container_size",
        "ds64": "decrypted_size",
        "ds": "legacy_decrypted_size",
        "d": "datacenter_id",
        "k": "key",
    },
    "SecureFileMediaResource": {
        "f": "file_id",
        "a": "access_hash",
        "n64": "size",
        "n": "legacy_size",
        "d": "datacenter_id",
        "t": "timestamp",
        "h": "file_hash",
        "s": "encrypted_secret",
    },
    "TelegramMediaFile": {
        "i": "file_id",
        "prf": "partial_reference",
        "r": "resource",
        "pr": "preview_representations",
        "vr": "video_thumbnails",
        "cv": "video_cover",
        "itd": "immediate_thumbnail_data",
        "mt": "mime_type",
        "s64": "size",
        "s": "legacy_size",
        "at": "attributes",
        "arep": "alternative_representations",
    },
    "TelegramMediaImage": {
        "i": "image_id",
        "r": "representations",
        "vr": "video_representations",
        "itd": "immediate_thumbnail_data",
        "em": "emoji_markup",
        "rf": "reference",
        "prf": "partial_reference",
        "fl": "flags",
        "vid": "video",
    },
    "TelegramMediaImageRepresentation": {
        "dx": "width",
        "dy": "height",
        "r": "resource",
        "ps": "progressive_sizes",
        "th": "immediate_thumbnail_data",
        "hv": "has_video",
        "ip": "is_personal",
    },
    "VideoRepresentation": {
        "w": "width",
        "h": "height",
        "r": "resource",
        "s": "start_timestamp",
    },
    "VideoThumbnail": {
        "w": "width",
        "h": "height",
        "r": "resource",
    },
    "WallpaperDataResource": {"s": "slug"},
    "WebFileReferenceMediaResource": {
        "u": "url",
        "s64": "size",
        "s": "legacy_size",
        "h": "access_hash",
    },
    "TelegramMediaWebpage": {
        "i": "webpage_id",
        "ct": "content_type",
        "pendingDate": "pending_date",
        "pendingUrl": "pending_url",
        "u": "url",
        "d": "display_url",
        "ti": "title",
        "tx": "text",
    },
}
