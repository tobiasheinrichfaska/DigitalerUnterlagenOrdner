"""Message framing for the core IPC: 4-byte big-endian length + UTF-8 JSON.

Transport-agnostic: the read side takes a ``read_exact(n)`` callable (returns
exactly ``n`` bytes, or ``b""`` at end-of-stream), so the same code works over a
named pipe or an in-memory buffer in tests.
"""

import json
import struct
from typing import Any, Callable, Optional

_HEADER = struct.Struct(">I")  # unsigned 32-bit length prefix
MAX_MESSAGE_BYTES = 256 * 1024 * 1024  # 256 MiB hard cap (previews/PDF blobs)


def encode(obj: Any) -> bytes:
    """Serialize a JSON-able object to a length-prefixed frame."""
    payload = json.dumps(obj, ensure_ascii=False).encode("utf-8")
    return _HEADER.pack(len(payload)) + payload


def read_message(read_exact: Callable[[int], bytes]) -> Optional[Any]:
    """Read one framed message; returns ``None`` at end-of-stream."""
    header = read_exact(_HEADER.size)
    if not header or len(header) < _HEADER.size:
        return None
    (length,) = _HEADER.unpack(header)
    if length > MAX_MESSAGE_BYTES:
        raise ValueError(f"message too large: {length} bytes")
    if length == 0:
        return {}
    payload = read_exact(length)
    if len(payload) < length:
        return None  # truncated → treat as closed
    return json.loads(payload.decode("utf-8"))


def reader_for_bytes(data: bytes) -> Callable[[int], bytes]:
    """A ``read_exact`` over an in-memory buffer (for tests)."""
    pos = 0

    def read_exact(n: int) -> bytes:
        nonlocal pos
        chunk = data[pos:pos + n]
        pos += len(chunk)
        return chunk

    return read_exact
