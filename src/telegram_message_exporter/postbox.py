"""Postbox parsing helpers for Telegram Desktop databases."""

# pylint: disable=too-many-lines

from __future__ import annotations

import enum
import io
import sqlite3
import struct
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Iterable, Optional

from .hashing import murmur_hash, persistent_hash32
from .models import Attachment, ForwardInfo, Message
from .schema import (
    POSTBOX_FIELD_ALIASES,
    POSTBOX_MEDIA_HELPER_TYPES,
    POSTBOX_MEDIA_TYPES,
    POSTBOX_MESSAGE_ATTRIBUTE_TYPES,
    PostboxTable,
    TelegramMediaActionType,
)


class ByteReader:
    """Binary reader with configurable endianness."""

    def __init__(self, buffer: io.BytesIO, endian: str = "<") -> None:
        self.endian = endian
        self.buf = buffer

    def read_fmt(self, fmt: str) -> int:
        """Read and unpack a value for the given format."""
        fmt = self.endian + fmt
        data = self.buf.read(struct.calcsize(fmt))
        return struct.unpack(fmt, data)[0]

    def read_int8(self) -> int:
        """Read a signed 8-bit integer."""
        return self.read_fmt("b")

    def read_uint8(self) -> int:
        """Read an unsigned 8-bit integer."""
        return self.read_fmt("B")

    def read_int32(self) -> int:
        """Read a signed 32-bit integer."""
        return self.read_fmt("i")

    def read_uint32(self) -> int:
        """Read an unsigned 32-bit integer."""
        return self.read_fmt("I")

    def read_int64(self) -> int:
        """Read a signed 64-bit integer."""
        return self.read_fmt("q")

    def read_uint64(self) -> int:
        """Read an unsigned 64-bit integer."""
        return self.read_fmt("Q")

    def read_bytes(self) -> bytes:
        """Read a byte sequence prefixed by its length."""
        length = self.read_int32()
        return self.buf.read(length)

    def read_str(self) -> str:
        """Read a UTF-8 string prefixed by length."""
        return self.read_bytes().decode("utf-8")

    def read_short_bytes(self) -> bytes:
        """Read a byte sequence prefixed by uint8 length."""
        length = self.read_uint8()
        return self.buf.read(length)

    def read_short_str(self) -> str:
        """Read a short UTF-8 string prefixed by uint8 length."""
        return self.read_short_bytes().decode("utf-8")

    def read_double(self) -> float:
        """Read a double-precision float."""
        return self.read_fmt("d")


class MessageDataFlags(enum.IntFlag):
    """Bit flags describing message metadata fields."""

    GLOBALLY_UNIQUE_ID = 1 << 0
    GLOBAL_TAGS = 1 << 1
    GROUPING_KEY = 1 << 2
    GROUP_INFO = 1 << 3
    LOCAL_TAGS = 1 << 4
    THREAD_ID = 1 << 5


class FwdInfoFlags(enum.IntFlag):
    """Bit flags describing forward info fields."""

    SOURCE_ID = 1 << 1
    SOURCE_MESSAGE = 1 << 2
    SIGNATURE = 1 << 3
    PSA_TYPE = 1 << 4
    FLAGS = 1 << 5


class MessageForwardFlags(enum.IntFlag):
    """Flags stored inside decoded forward information."""

    IS_IMPORTED = 1 << 0


class MessageFlags(enum.IntFlag):
    """Bit flags describing message direction and state."""

    UNSENT = 1
    FAILED = 2
    INCOMING = 4
    TOP_INDEXABLE = 16
    SENDING = 32
    CAN_BE_GROUPED_INTO_FEED = 64
    WAS_SCHEDULED = 128
    COUNTED_AS_INCOMING = 256
    COPY_PROTECTED = 512
    IS_FORUM_TOPIC = 1024
    REACTIONS_ARE_POSSIBLE = 2048


class MessageTags(enum.IntFlag):
    """Message tag categories."""

    PHOTO_OR_VIDEO = 1 << 0
    FILE = 1 << 1
    MUSIC = 1 << 2
    WEB_PAGE = 1 << 3
    VOICE_OR_INSTANT_VIDEO = 1 << 4
    UNSEEN_PERSONAL_MESSAGE = 1 << 5
    LIVE_LOCATION = 1 << 6
    GIF = 1 << 7
    PHOTO = 1 << 8
    VIDEO = 1 << 9
    PINNED = 1 << 10
    UNSEEN_REACTION = 1 << 11
    VOICE = 1 << 12
    ROUND_VIDEO = 1 << 13
    POLLS = 1 << 14
    UNSEEN_POLL_VOTE = 1 << 15


class GlobalMessageTags(enum.IntFlag):
    """Global message tag categories."""

    CALLS = 1 << 0
    MISSED_CALLS = 1 << 1


class LocalMessageTags(enum.IntFlag):
    """Device-local message tag categories."""

    OUTGOING_LIVE_LOCATION = 1 << 0
    OUTGOING_DELIVERED_TO_SERVER = 1 << 1


@dataclass(frozen=True)
class MessageIndex:
    """Index for a Telegram Postbox message entry."""

    peer_id: int
    namespace: int
    message_id: int
    timestamp: int

    @classmethod
    def from_bytes(cls, payload: bytes) -> "MessageIndex":
        """Deserialize message index bytes into a structured index."""
        reader = ByteReader(io.BytesIO(payload), endian=">")
        peer_id = reader.read_int64()
        namespace = reader.read_int32()
        timestamp = reader.read_int32()
        message_id = reader.read_int32()
        return cls(peer_id, namespace, message_id, timestamp)

    def as_bytes(self) -> bytes:
        """Serialize the message index back to bytes."""
        return struct.pack(
            ">qiii", self.peer_id, self.namespace, self.timestamp, self.message_id
        )


class MediaEntryType(enum.IntEnum):
    """Storage mode used by entries in the Postbox message-media table."""

    DIRECT = 0
    MESSAGE_REFERENCE = 1


@dataclass(frozen=True)
class MediaEntry:
    """Decoded value from the Postbox message-media table."""

    entry_type: MediaEntryType
    media: Optional[Any] = None
    message_index: Optional[MessageIndex] = None
    reference_count: Optional[int] = None


class PostboxDecoder:
    """Decoder for Postbox key/value payloads."""

    registry: dict[int, Any] = {}

    @classmethod
    def register_decoder(cls, target: type) -> type:
        """Register a type hash decoder for Postbox objects."""
        cls.registry[murmur_hash(target.__name__.encode("utf-8"))] = target
        return target

    @classmethod
    def register_named_decoder(cls, type_name: str, target: Any) -> None:
        """Register a decoder under an explicit Swift type name."""
        cls.registry[murmur_hash(type_name.encode("utf-8"))] = target

    class ValueType(enum.Enum):
        """Postbox value encoding types."""

        INT32 = 0
        INT64 = 1
        BOOL = 2
        DOUBLE = 3
        STRING = 4
        OBJECT = 5
        INT32_ARRAY = 6
        INT64_ARRAY = 7
        OBJECT_ARRAY = 8
        OBJECT_DICTIONARY = 9
        BYTES = 10
        NIL = 11
        STRING_ARRAY = 12
        BYTES_ARRAY = 13

    def __init__(self, data: bytes) -> None:
        self.reader = ByteReader(io.BytesIO(data), endian="<")
        self.size = len(data)

    def decode_root_object(self) -> Optional[Any]:
        """Decode the root object for the payload."""
        _, value = self.get(self.ValueType.OBJECT, "_")
        return value

    def get(
        self, value_type: Optional["PostboxDecoder.ValueType"], key: str
    ) -> tuple[Any, Any]:
        """Fetch a typed value by key."""
        for entry_key, entry_type, entry_value in self.iter_kv():
            if entry_key != key:
                continue
            if value_type is None:
                return entry_type, entry_value
            if entry_type == value_type:
                return entry_type, entry_value
            if entry_type == self.ValueType.NIL:
                return entry_type, None
        return None, None

    def iter_kv(self) -> Iterable[tuple[str, "PostboxDecoder.ValueType", Any]]:
        """Iterate over key/value records in this payload."""
        self.reader.buf.seek(0, io.SEEK_SET)
        while self.reader.buf.tell() < self.size:
            key = self.reader.read_short_str()
            value_type, value = self.read_value()
            yield key, value_type, value

    def read_value(self) -> tuple["PostboxDecoder.ValueType", Any]:
        """Read a single value from the reader."""
        value_type = self.ValueType(self.reader.read_uint8())
        handler = {
            self.ValueType.INT32: self.reader.read_int32,
            self.ValueType.INT64: self.reader.read_int64,
            self.ValueType.BOOL: lambda: self.reader.read_uint8() != 0,
            self.ValueType.DOUBLE: self.reader.read_double,
            self.ValueType.STRING: self.reader.read_str,
            self.ValueType.OBJECT: self._read_object,
            self.ValueType.INT32_ARRAY: lambda: self._read_array(
                self.reader.read_int32
            ),
            self.ValueType.INT64_ARRAY: lambda: self._read_array(
                self.reader.read_int64
            ),
            self.ValueType.OBJECT_ARRAY: lambda: self._read_array(self._read_object),
            self.ValueType.OBJECT_DICTIONARY: self._read_object_dict,
            self.ValueType.BYTES: self.reader.read_bytes,
            self.ValueType.NIL: lambda: None,
            self.ValueType.STRING_ARRAY: lambda: self._read_array(self.reader.read_str),
            self.ValueType.BYTES_ARRAY: lambda: self._read_array(
                self.reader.read_bytes
            ),
        }[value_type]
        return value_type, handler()

    def _read_array(self, reader_fn):
        length = self.reader.read_int32()
        return [reader_fn() for _ in range(length)]

    def _read_object(self) -> Any:
        type_hash = self.reader.read_int32()
        data_len = self.reader.read_int32()
        data = self.reader.buf.read(data_len)
        if type_hash in self.registry:
            decoder = self.__class__(data)
            return self.registry[type_hash](decoder)
        decoder = self.__class__(data)
        payload = {key: val for key, _, val in decoder.iter_kv()}
        payload["@type"] = type_hash
        return payload

    def _read_object_dict(self) -> list[tuple[Any, Any]]:
        length = self.reader.read_int32()
        return [(self._read_object(), self._read_object()) for _ in range(length)]


@dataclass(frozen=True)
class PostboxObject:
    """Named Postbox object whose fields are retained without interpretation."""

    type_name: str
    payload: dict[str, Any]

    @property
    def fields(self) -> dict[str, Any]:
        """Return payload fields with current Telegram source names."""
        aliases = POSTBOX_FIELD_ALIASES.get(self.type_name, {})
        fields = {aliases.get(key, key): value for key, value in self.payload.items()}
        for field_name in (
            "document_id",
            "file_id",
            "game_id",
            "image_id",
            "photo_id",
            "webpage_id",
        ):
            value = fields.get(field_name)
            if isinstance(value, bytes) and len(value) == 12:
                fields[field_name] = struct.unpack("<iq", value)
        return fields

    def as_dict(self) -> dict[str, Any]:
        """Return a serializable representation."""
        return {
            "type": self.type_name,
            "payload": self.payload,
            "fields": self.fields,
        }


def _named_object_decoder(type_name: str):
    def decode(decoder: PostboxDecoder) -> PostboxObject:
        payload = {key: val for key, _, val in decoder.iter_kv()}
        return PostboxObject(type_name=type_name, payload=payload)

    return decode


@PostboxDecoder.register_decoder
class TelegramMediaAction:
    """Decoded Telegram service-message action."""

    def __init__(self, decoder: PostboxDecoder) -> None:
        raw = {key: val for key, _, val in decoder.iter_kv()}
        raw_type = raw.get("_rawValue", 0)
        if not isinstance(raw_type, int):
            raw_type = 0
        self.raw_type = raw_type
        self.type = TelegramMediaActionType.safe(raw_type)
        raw.pop("_rawValue", None)
        self.payload = raw

    def __repr__(self) -> str:
        return f"{self.type} {self.payload}"

    def as_dict(self) -> dict[str, Any]:
        """Return a serializable representation of the action."""
        return {
            "type": self.type.name,
            "raw_type": self.raw_type,
            "payload": self.payload,
        }


for _type_name in (
    *POSTBOX_MEDIA_TYPES,
    *POSTBOX_MEDIA_HELPER_TYPES,
    *POSTBOX_MESSAGE_ATTRIBUTE_TYPES,
):
    if _type_name != TelegramMediaAction.__name__:
        PostboxDecoder.register_named_decoder(
            _type_name, _named_object_decoder(_type_name)
        )


def _decode_root_object_safe(payload: bytes) -> Optional[Any]:
    try:
        return PostboxDecoder(payload).decode_root_object()
    except (LookupError, TypeError, UnicodeDecodeError, ValueError, struct.error):
        return None


def read_media_entry(payload: bytes) -> MediaEntry:
    """Decode a value from the Postbox message-media table."""
    reader = ByteReader(io.BytesIO(payload))
    entry_type = MediaEntryType(reader.read_int8())
    if entry_type == MediaEntryType.DIRECT:
        media = _decode_root_object_safe(reader.read_bytes())
        reference_count = reader.read_int32()
        return MediaEntry(
            entry_type=entry_type,
            media=media,
            reference_count=reference_count,
        )

    peer_id = reader.read_int64()
    namespace = reader.read_int32()
    message_id = reader.read_int32()
    timestamp = reader.read_int32()
    return MediaEntry(
        entry_type=entry_type,
        message_index=MessageIndex(peer_id, namespace, message_id, timestamp),
    )


def _media_id(media: Any) -> Optional[tuple[int, int]]:
    if not isinstance(media, PostboxObject):
        return None
    for field_name in ("file_id", "image_id", "webpage_id"):
        value = media.fields.get(field_name)
        if (
            isinstance(value, tuple)
            and len(value) == 2
            and all(isinstance(part, int) for part in value)
        ):
            return value
    return None


def _resource_id(value: Any) -> Any:
    """Return the concrete id from Telegram's optional (namespace, id) pairs."""
    if isinstance(value, tuple) and len(value) == 2:
        return value[1]
    return value


# pylint: disable=too-many-return-statements,too-many-branches
def _resource_cache_key(resource: Any) -> Optional[str]:
    if not isinstance(resource, PostboxObject):
        return None
    fields = resource.fields
    if resource.type_name == "CloudDocumentMediaResource":
        file_id = _resource_id(fields.get("file_id"))
        if fields.get("datacenter_id") is None or file_id is None:
            return None
        return f"telegram-cloud-document-{fields.get('datacenter_id')}-" f"{file_id}"
    if resource.type_name == "CloudPhotoSizeMediaResource":
        photo_id = _resource_id(fields.get("photo_id"))
        if (
            fields.get("datacenter_id") is None
            or photo_id is None
            or fields.get("size_spec") is None
        ):
            return None
        return (
            f"telegram-cloud-photo-size-{fields.get('datacenter_id')}-"
            f"{photo_id}-{fields.get('size_spec')}"
        )
    if resource.type_name == "CloudDocumentSizeMediaResource":
        document_id = _resource_id(fields.get("document_id"))
        if (
            fields.get("datacenter_id") is None
            or document_id is None
            or fields.get("size_spec") is None
        ):
            return None
        return (
            f"telegram-cloud-document-size-{fields.get('datacenter_id')}-"
            f"{document_id}-{fields.get('size_spec')}"
        )
    if resource.type_name == "CloudFileMediaResource":
        if any(
            fields.get(field_name) is None
            for field_name in ("datacenter_id", "volume_id", "local_id", "secret")
        ):
            return None
        return (
            f"telegram-cloud-file-{fields.get('datacenter_id')}-"
            f"{fields.get('volume_id')}-{fields.get('local_id')}-"
            f"{fields.get('secret')}"
        )
    if resource.type_name == "CloudPeerPhotoSizeMediaResource":
        datacenter_id = fields.get("datacenter_id")
        size_spec = fields.get("size_spec")
        if datacenter_id is None or size_spec is None:
            return None
        suffix = (
            f"{size_spec}-{fields.get('volume_id') or 0}-"
            f"{fields.get('local_id') or 0}"
        )
        photo_id = _resource_id(fields.get("photo_id"))
        if photo_id is not None:
            return f"telegram-peer-photo-size-{datacenter_id}-{photo_id}-{suffix}"
        return f"telegram-peer-photo-size-{datacenter_id}-{suffix}"
    if resource.type_name == "CloudStickerPackThumbnailMediaResource":
        datacenter_id = fields.get("datacenter_id")
        if datacenter_id is None:
            return None
        suffix = f"{fields.get('volume_id') or 0}-{fields.get('local_id') or 0}"
        thumb_version = fields.get("thumb_version")
        if thumb_version is not None:
            return (
                f"telegram-stickerpackthumbnail-{datacenter_id}-"
                f"{thumb_version}-{suffix}"
            )
        return f"telegram-stickerpackthumbnail-{datacenter_id}-{suffix}"
    if resource.type_name == "LocalFileMediaResource":
        file_id = _resource_id(fields.get("file_id"))
        return f"telegram-local-file-{file_id}" if file_id is not None else None
    if resource.type_name == "LocalFileReferenceMediaResource":
        random_id = fields.get("random_id")
        return f"local-file-{random_id}" if random_id is not None else None
    if resource.type_name == "HttpReferenceMediaResource":
        url = fields.get("url")
        return f"http-{persistent_hash32(url)}" if isinstance(url, str) else None
    if resource.type_name == "WebFileReferenceMediaResource":
        url = fields.get("url")
        size = fields.get("size") or fields.get("legacy_size")
        access_hash = fields.get("access_hash")
        if not isinstance(url, str) or size is None or access_hash is None:
            return None
        return f"proxy-{persistent_hash32(url)}-{size}-{access_hash}"
    if resource.type_name == "SecretFileMediaResource":
        file_id = _resource_id(fields.get("file_id"))
        datacenter_id = fields.get("datacenter_id")
        if file_id is None or datacenter_id is None:
            return None
        return f"secret-file-{file_id}-{datacenter_id}"
    if resource.type_name == "SecureFileMediaResource":
        file_id = _resource_id(fields.get("file_id"))
        return f"telegram-secure-file-{file_id}" if file_id is not None else None
    if resource.type_name == "WallpaperDataResource":
        slug = fields.get("slug")
        return f"wallpaper-{slug}" if isinstance(slug, str) else None
    return None


def _file_attribute_data(
    attributes: Any,
) -> tuple[Optional[str], bool, bool, Optional[int], Optional[int]]:
    filename = None
    is_voice = False
    is_sticker = False
    width = None
    height = None
    if not isinstance(attributes, list):
        return filename, is_voice, is_sticker, width, height
    for attribute in attributes:
        if not isinstance(attribute, PostboxObject):
            continue
        fields = attribute.payload
        attribute_type = fields.get("t")
        if attribute_type == 0 and isinstance(fields.get("fn"), str):
            filename = fields["fn"]
        elif attribute_type in (1, 10):
            is_sticker = True
        elif attribute_type == 4:
            width = fields.get("w")
            height = fields.get("h")
        elif attribute_type == 5:
            is_voice = bool(fields.get("iv"))
    return filename, is_voice, is_sticker, width, height


def _object_resources(value: Any) -> list[Any]:
    resources: list[Any] = []
    if isinstance(value, PostboxObject):
        resource = value.fields.get("resource")
        if isinstance(resource, PostboxObject):
            resources.append(resource)
    elif isinstance(value, list):
        for item in value:
            resources.extend(_object_resources(item))
    return resources


def _file_resources(fields: dict[str, Any]) -> list[Any]:
    resources = [fields.get("resource")]
    resources.extend(_object_resources(fields.get("preview_representations")))
    resources.extend(_object_resources(fields.get("video_thumbnails")))
    video_cover = fields.get("video_cover")
    if isinstance(video_cover, PostboxObject):
        resources.extend(_object_resources(video_cover.fields.get("representations")))
        resources.extend(
            _object_resources(video_cover.fields.get("video_representations"))
        )
    for alternative in fields.get("alternative_representations") or []:
        if isinstance(alternative, PostboxObject):
            alternative_fields = alternative.fields
            resources.append(alternative_fields.get("resource"))
            resources.extend(
                _object_resources(alternative_fields.get("preview_representations"))
            )
            resources.extend(
                _object_resources(alternative_fields.get("video_thumbnails"))
            )
    return resources


def _file_resource_keys(
    fields: dict[str, Any],
) -> tuple[Optional[str], tuple[str, ...], Optional[str]]:
    resources = _file_resources(fields)
    keys: list[str] = []
    source_path = None
    for resource in resources:
        key = _resource_cache_key(resource)
        if key and key not in keys:
            keys.append(key)
        if (
            source_path is None
            and isinstance(resource, PostboxObject)
            and isinstance(resource.fields.get("local_file_path"), str)
        ):
            source_path = resource.fields["local_file_path"]
    if not keys:
        return None, (), source_path
    return keys[0], tuple(keys[1:]), source_path


def media_attachments(  # pylint: disable=too-many-locals,too-many-return-statements,too-many-branches
    media: Any,
) -> list[Attachment]:
    """Convert a decoded Postbox media object to export attachments."""
    if isinstance(media, TelegramMediaAction):
        return [Attachment(kind="action", filename=media.type.name)]
    if not isinstance(media, PostboxObject):
        return []
    fields = media.fields
    if media.type_name == "TelegramMediaFile":
        resource = fields.get("resource")
        resource_fields = resource.fields if isinstance(resource, PostboxObject) else {}
        attr_filename, is_voice, is_sticker, width, height = _file_attribute_data(
            fields.get("attributes")
        )
        filename = resource_fields.get("file_name") or attr_filename
        mime_type = fields.get("mime_type")
        if is_sticker:
            kind = "sticker"
        elif is_voice:
            kind = "voice"
        elif isinstance(mime_type, str) and mime_type.startswith("video/"):
            kind = "video"
        elif isinstance(mime_type, str) and mime_type.startswith("audio/"):
            kind = "audio"
        elif isinstance(mime_type, str) and mime_type.startswith("image/"):
            kind = "image"
        else:
            kind = "file"
        cache_key, alternate_cache_keys, source_path = _file_resource_keys(fields)
        return [
            Attachment(
                kind=kind,
                filename=filename,
                mime_type=mime_type,
                cache_key=cache_key,
                alternate_cache_keys=alternate_cache_keys,
                source_path=source_path,
                width=width,
                height=height,
            )
        ]

    if media.type_name == "TelegramMediaImage":
        representations = fields.get("representations")
        candidates = [
            representation
            for representation in representations or []
            if isinstance(representation, PostboxObject)
        ]
        candidates.sort(
            key=lambda representation: (
                int(representation.fields.get("width") or 0)
                * int(representation.fields.get("height") or 0)
            ),
            reverse=True,
        )
        if not candidates:
            return [Attachment(kind="image")]
        representation = candidates[0]
        representation_fields = representation.fields
        cache_keys: list[str] = []
        for candidate in candidates:
            key = _resource_cache_key(candidate.fields.get("resource"))
            if key and key not in cache_keys:
                cache_keys.append(key)
        for video_representation in fields.get("video_representations") or []:
            if isinstance(video_representation, PostboxObject):
                key = _resource_cache_key(video_representation.fields.get("resource"))
                if key and key not in cache_keys:
                    cache_keys.append(key)
        return [
            Attachment(
                kind="image",
                cache_key=cache_keys[0] if cache_keys else None,
                alternate_cache_keys=tuple(cache_keys[1:]),
                width=representation_fields.get("width"),
                height=representation_fields.get("height"),
            )
        ]

    if media.type_name == "TelegramMediaWebpage":
        url = fields.get("url") or fields.get("pending_url")
        return [Attachment(kind="webpage", url=url)] if url else []

    return [Attachment(kind=media.type_name)]


class PostboxMediaResolver:  # pylint: disable=too-few-public-methods
    """Resolve referenced media entries from Postbox message-media storage."""

    def __init__(
        self, conn: sqlite3.Connection, media_table: str, message_table: str
    ) -> None:
        self.conn = conn
        self.media_table = media_table
        self.message_table = message_table
        self.cache: dict[tuple[int, int], Optional[Any]] = {}

    def resolve(  # pylint: disable=too-many-return-statements
        self, namespace: int, media_id: int
    ) -> Optional[Any]:
        """Resolve one media id to a decoded media object, if possible."""
        key = (namespace, media_id)
        if key in self.cache:
            return self.cache[key]
        raw_key = struct.pack(">iq", namespace, media_id)
        try:
            row = self.conn.execute(
                f"SELECT value FROM {self.media_table} WHERE key = ? LIMIT 1",
                (raw_key,),
            ).fetchone()
        except sqlite3.DatabaseError:
            self.cache[key] = None
            return None
        if row is None:
            self.cache[key] = None
            return None
        try:
            entry = read_media_entry(row[0])
        except (TypeError, ValueError, struct.error):
            self.cache[key] = None
            return None
        if entry.entry_type == MediaEntryType.DIRECT:
            self.cache[key] = entry.media
            return entry.media
        if entry.message_index is None:
            self.cache[key] = None
            return None
        try:
            message_row = self.conn.execute(
                f"SELECT value FROM {self.message_table} WHERE key = ? LIMIT 1",
                (entry.message_index.as_bytes(),),
            ).fetchone()
        except sqlite3.DatabaseError:
            self.cache[key] = None
            return None
        if message_row is None:
            self.cache[key] = None
            return None
        try:
            message = read_intermediate_message(message_row[0])
        except (LookupError, TypeError, UnicodeDecodeError, ValueError, struct.error):
            self.cache[key] = None
            return None
        if message:
            for media in message["embedded_media"]:
                if _media_id(media) == key:
                    self.cache[key] = media
                    return media
        self.cache[key] = None
        return None


def read_intermediate_fwd_info(reader: ByteReader) -> Optional[dict[str, Any]]:
    """Decode forward info section from a message payload."""
    info_flags = FwdInfoFlags(reader.read_int8())
    if info_flags == 0:
        return None

    author_id = reader.read_int64()
    date_value = reader.read_int32()

    source_id = reader.read_int64() if FwdInfoFlags.SOURCE_ID in info_flags else None

    src_peer = None
    src_namespace = None
    src_message_id = None
    if FwdInfoFlags.SOURCE_MESSAGE in info_flags:
        src_peer = reader.read_int64()
        src_namespace = reader.read_int32()
        src_message_id = reader.read_int32()

    signature = reader.read_str() if FwdInfoFlags.SIGNATURE in info_flags else None
    psa_type = reader.read_str() if FwdInfoFlags.PSA_TYPE in info_flags else None
    flags = (
        MessageForwardFlags(reader.read_int32())
        if FwdInfoFlags.FLAGS in info_flags
        else None
    )

    return {
        "author": author_id or None,
        "date": date_value,
        "src_id": source_id,
        "src_msg_peer": src_peer,
        "src_msg_ns": src_namespace,
        "src_msg_id": src_message_id,
        "signature": signature,
        "psa_type": psa_type,
        "flags": flags,
    }


def read_intermediate_message(  # pylint: disable=too-many-locals,too-many-branches,too-many-statements
    payload: bytes,
) -> Optional[dict[str, Any]]:
    """Decode a Postbox message payload to a structured dict."""
    reader = ByteReader(io.BytesIO(payload))
    message_type = reader.read_int8()
    if message_type != 0:
        return None

    stable_id = reader.read_uint32()
    stable_version = reader.read_uint32()

    data_flags = MessageDataFlags(reader.read_uint8())
    globally_unique_id = None
    if MessageDataFlags.GLOBALLY_UNIQUE_ID in data_flags:
        globally_unique_id = reader.read_int64()

    global_tags = GlobalMessageTags(0)
    if MessageDataFlags.GLOBAL_TAGS in data_flags:
        global_tags = GlobalMessageTags(reader.read_uint32())

    grouping_key = None
    if MessageDataFlags.GROUPING_KEY in data_flags:
        grouping_key = reader.read_int64()

    group_info_stable_id = None
    if MessageDataFlags.GROUP_INFO in data_flags:
        group_info_stable_id = reader.read_uint32()

    local_tags = LocalMessageTags(0)
    if MessageDataFlags.LOCAL_TAGS in data_flags:
        local_tags = LocalMessageTags(reader.read_uint32())

    thread_id = None
    if MessageDataFlags.THREAD_ID in data_flags:
        thread_id = reader.read_int64()

    flags = MessageFlags(reader.read_uint32())
    tags = MessageTags(reader.read_uint32())

    fwd_info = read_intermediate_fwd_info(reader)

    author_id = None
    if reader.read_int8() == 1:
        author_id = reader.read_int64()

    text = reader.read_str()

    attributes_count = reader.read_int32()
    attributes = []
    for _ in range(attributes_count):
        attribute = _decode_root_object_safe(reader.read_bytes())
        if attribute is not None:
            attributes.append(attribute)

    embedded_media_count = reader.read_int32()
    embedded_media = []
    for _ in range(embedded_media_count):
        media = _decode_root_object_safe(reader.read_bytes())
        if media is not None:
            embedded_media.append(media)

    referenced_media_ids = []
    for _ in range(reader.read_int32()):
        namespace = reader.read_int32()
        message_id = reader.read_int64()
        referenced_media_ids.append((namespace, message_id))

    custom_tags = []
    if reader.buf.tell() < len(payload):
        try:
            for _ in range(reader.read_int32()):
                custom_tags.append(reader.read_bytes())
        except struct.error:
            custom_tags = []

    return {
        "stable_id": stable_id,
        "stable_version": stable_version,
        "globally_unique_id": globally_unique_id,
        "global_tags": global_tags,
        "grouping_key": grouping_key,
        "group_info_stable_id": group_info_stable_id,
        "local_tags": local_tags,
        "thread_id": thread_id,
        "flags": flags,
        "tags": tags,
        "author_id": author_id,
        "fwd": fwd_info,
        "text": text,
        "attributes": attributes,
        "embedded_media": embedded_media,
        "referenced_media_ids": referenced_media_ids,
        "custom_tags": custom_tags,
    }


def iter_postbox_messages(  # pylint: disable=too-many-locals,too-many-branches,too-many-arguments,too-many-positional-arguments
    rows: Iterable[tuple[bytes, bytes]],
    peer_id: Optional[int] = None,
    start_ts: Optional[int] = None,
    end_ts: Optional[int] = None,
    limit: Optional[int] = None,
    media_resolver: Optional[PostboxMediaResolver] = None,
) -> list[Message]:
    """Iterate Postbox message rows and build normalized messages."""
    messages: list[Message] = []
    for key, value in rows:
        if not isinstance(key, (bytes, bytearray)) or not isinstance(
            value, (bytes, bytearray)
        ):
            continue
        idx = MessageIndex.from_bytes(key)
        if peer_id is not None and idx.peer_id != peer_id:
            continue
        if start_ts is not None and idx.timestamp < start_ts:
            continue
        if end_ts is not None and idx.timestamp > end_ts:
            continue

        try:
            msg = read_intermediate_message(value)
        except (LookupError, TypeError, UnicodeDecodeError, ValueError, struct.error):
            continue
        if not msg:
            continue
        text = msg.get("text") or ""
        media = list(msg.get("embedded_media") or [])
        if media_resolver is not None:
            for namespace, media_id in msg.get("referenced_media_ids") or []:
                referenced_media = media_resolver.resolve(namespace, media_id)
                if referenced_media is not None:
                    media.append(referenced_media)
        attachments = tuple(
            attachment for item in media for attachment in media_attachments(item)
        )
        if not text and not attachments:
            continue

        incoming = MessageFlags.INCOMING in msg["flags"]
        timestamp = datetime.fromtimestamp(idx.timestamp) if idx.timestamp else None
        raw_forward_info = msg.get("fwd")
        forward_info = None
        if raw_forward_info is not None:
            forward_timestamp = raw_forward_info.get("date")
            forward_flags = raw_forward_info.get("flags")
            forward_info = ForwardInfo(
                author_id=raw_forward_info.get("author"),
                source_id=raw_forward_info.get("src_id"),
                source_message_peer_id=raw_forward_info.get("src_msg_peer"),
                source_message_namespace=raw_forward_info.get("src_msg_ns"),
                source_message_id=raw_forward_info.get("src_msg_id"),
                date=(
                    datetime.fromtimestamp(forward_timestamp)
                    if forward_timestamp
                    else None
                ),
                author_signature=raw_forward_info.get("signature"),
                psa_type=raw_forward_info.get("psa_type"),
                is_imported=bool(
                    forward_flags and MessageForwardFlags.IS_IMPORTED in forward_flags
                ),
            )
        messages.append(
            Message(
                timestamp=timestamp,
                text=text,
                outgoing=None if incoming is None else not incoming,
                peer_id=idx.peer_id,
                author_id=msg.get("author_id"),
                attachments=attachments,
                forward_info=forward_info,
            )
        )
        if limit and len(messages) >= limit:
            break
    return messages


def parse_peer_key(raw_key: Any) -> Optional[int]:
    """Parse peer key into an integer peer id."""
    if isinstance(raw_key, int):
        return raw_key
    if isinstance(raw_key, (bytes, bytearray)) and len(raw_key) == 8:
        return struct.unpack(">q", raw_key)[0]
    return None


def peer_display(peer: Any) -> Optional[str]:
    """Build a display name from a peer payload."""
    if not isinstance(peer, dict):
        return None
    if "fn" in peer or "ln" in peer:
        return f"{peer.get('fn', '')} {peer.get('ln', '')}".strip()
    if "t" in peer:
        return str(peer.get("t"))
    if "un" in peer:
        return f"@{peer.get('un')}"
    return None


def list_peers_postbox(
    rows: Iterable[tuple[bytes, bytes]],
    term: Optional[str],
) -> list[tuple[str, int, str]]:
    """List peer ids and names from Postbox t2 rows."""
    results: list[tuple[str, int, str]] = []
    for key, value in rows:
        peer_id = parse_peer_key(key)
        if peer_id is None or not isinstance(value, (bytes, bytearray)):
            continue
        try:
            data = PostboxDecoder(value).decode_root_object()
        except (TypeError, UnicodeDecodeError, ValueError, struct.error):
            continue
        display = peer_display(data)
        if not display:
            continue
        if term and term.lower() not in display.lower():
            continue
        results.append((PostboxTable.PEER.sqlite_name, peer_id, display))
    return results


def load_peer_map(rows: Iterable[tuple[bytes, bytes]]) -> dict[int, str]:
    """Load peer mapping from Postbox t2 rows."""
    peer_map: dict[int, str] = {}
    for key, value in rows:
        peer_id = parse_peer_key(key)
        if peer_id is None or not isinstance(value, (bytes, bytearray)):
            continue
        try:
            data = PostboxDecoder(value).decode_root_object()
        except (TypeError, UnicodeDecodeError, ValueError, struct.error):
            continue
        display = peer_display(data)
        if display:
            peer_map[peer_id] = display
    return peer_map
