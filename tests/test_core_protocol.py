"""Unit tests for the core IPC framing (no pipe needed)."""

from core.ipc import protocol


def test_encode_decode_roundtrip():
    msg = {"op": "open", "path": "x.belegtool", "n": 3, "nested": {"a": [1, 2]}}
    frame = protocol.encode(msg)
    out = protocol.read_message(protocol.reader_for_bytes(frame))
    assert out == msg


def test_two_messages_in_one_stream():
    a = protocol.encode({"op": "hello"})
    b = protocol.encode({"op": "open"})
    read = protocol.reader_for_bytes(a + b)
    assert protocol.read_message(read) == {"op": "hello"}
    assert protocol.read_message(read) == {"op": "open"}
    assert protocol.read_message(read) is None  # end of stream


def test_empty_stream_returns_none():
    assert protocol.read_message(protocol.reader_for_bytes(b"")) is None


def test_truncated_payload_returns_none():
    frame = protocol.encode({"op": "hello"})[:-2]  # cut the JSON short
    assert protocol.read_message(protocol.reader_for_bytes(frame)) is None


def test_unicode_survives():
    msg = {"name": "Ordner Ü/ä – Beleg"}
    out = protocol.read_message(protocol.reader_for_bytes(protocol.encode(msg)))
    assert out == msg
