from __future__ import annotations

import builtins
import json
import os
import time as _time
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Union

if TYPE_CHECKING:
    from collections.abc import Callable

    from ulid.monotonic import LockedMonotonicReader, MonotonicEntropy


class ULIDError(Exception):
    pass


class ErrDataSize(ULIDError):
    def __init__(self) -> None:
        super().__init__("ulid: bad data size when unmarshaling")


class ErrInvalidCharacters(ULIDError):
    def __init__(self) -> None:
        super().__init__("ulid: bad data characters when unmarshaling")


class ErrBufferSize(ULIDError):
    def __init__(self) -> None:
        super().__init__("ulid: bad buffer size when marshaling")


class ErrBigTime(ULIDError):
    def __init__(self) -> None:
        super().__init__("ulid: timestamp too big")


class ErrOverflow(ULIDError):
    def __init__(self) -> None:
        super().__init__("ulid: overflow when unmarshaling")


class ErrMonotonicOverflow(ULIDError):
    def __init__(self) -> None:
        super().__init__("ulid: monotonic entropy overflow")


class ErrScanValue(ULIDError):
    def __init__(self) -> None:
        super().__init__("ulid: source value must be a string or byte slice")


class ErrInvalidPrefix(ULIDError):
    def __init__(self) -> None:
        super().__init__("ulid: invalid prefix format")


ENCODED_SIZE = 26
BINARY_SIZE = 16
MAX_TIME = (1 << 48) - 1

_ENCODING = "0123456789abcdefghjkmnpqrstvwxyz"

# 256-byte decode lookup table. 0xFF = invalid character.
_DEC = bytes(
    [
        0xFF,
        0xFF,
        0xFF,
        0xFF,
        0xFF,
        0xFF,
        0xFF,
        0xFF,  # 0x00
        0xFF,
        0xFF,
        0xFF,
        0xFF,
        0xFF,
        0xFF,
        0xFF,
        0xFF,  # 0x08
        0xFF,
        0xFF,
        0xFF,
        0xFF,
        0xFF,
        0xFF,
        0xFF,
        0xFF,  # 0x10
        0xFF,
        0xFF,
        0xFF,
        0xFF,
        0xFF,
        0xFF,
        0xFF,
        0xFF,  # 0x18
        0xFF,
        0xFF,
        0xFF,
        0xFF,
        0xFF,
        0xFF,
        0xFF,
        0xFF,  # 0x20
        0xFF,
        0xFF,
        0xFF,
        0xFF,
        0xFF,
        0xFF,
        0xFF,
        0xFF,  # 0x28
        0x00,
        0x01,
        0x02,
        0x03,
        0x04,
        0x05,
        0x06,
        0x07,  # '0'-'7'
        0x08,
        0x09,
        0xFF,
        0xFF,
        0xFF,
        0xFF,
        0xFF,
        0xFF,  # '8'-'9'
        0xFF,
        0x0A,
        0x0B,
        0x0C,
        0x0D,
        0x0E,
        0x0F,
        0x10,  # 'A'-'G'
        0x11,
        0xFF,
        0x12,
        0x13,
        0xFF,
        0x14,
        0x15,
        0xFF,  # 'H'-'O'
        0x16,
        0x17,
        0x18,
        0x19,
        0x1A,
        0xFF,
        0x1B,
        0x1C,  # 'P'-'W'
        0x1D,
        0x1E,
        0x1F,
        0xFF,
        0xFF,
        0xFF,
        0xFF,
        0xFF,  # 'X'-'Z'
        0xFF,
        0x0A,
        0x0B,
        0x0C,
        0x0D,
        0x0E,
        0x0F,
        0x10,  # 'a'-'g'
        0x11,
        0xFF,
        0x12,
        0x13,
        0xFF,
        0x14,
        0x15,
        0xFF,  # 'h'-'o'
        0x16,
        0x17,
        0x18,
        0x19,
        0x1A,
        0xFF,
        0x1B,
        0x1C,  # 'p'-'w'
        0x1D,
        0x1E,
        0x1F,
        0xFF,
        0xFF,
        0xFF,
        0xFF,
        0xFF,  # 'x'-'z'
        0xFF,
        0xFF,
        0xFF,
        0xFF,
        0xFF,
        0xFF,
        0xFF,
        0xFF,  # 0x80
        0xFF,
        0xFF,
        0xFF,
        0xFF,
        0xFF,
        0xFF,
        0xFF,
        0xFF,  # 0x88
        0xFF,
        0xFF,
        0xFF,
        0xFF,
        0xFF,
        0xFF,
        0xFF,
        0xFF,  # 0x90
        0xFF,
        0xFF,
        0xFF,
        0xFF,
        0xFF,
        0xFF,
        0xFF,
        0xFF,  # 0x98
        0xFF,
        0xFF,
        0xFF,
        0xFF,
        0xFF,
        0xFF,
        0xFF,
        0xFF,  # 0xA0
        0xFF,
        0xFF,
        0xFF,
        0xFF,
        0xFF,
        0xFF,
        0xFF,
        0xFF,  # 0xA8
        0xFF,
        0xFF,
        0xFF,
        0xFF,
        0xFF,
        0xFF,
        0xFF,
        0xFF,  # 0xB0
        0xFF,
        0xFF,
        0xFF,
        0xFF,
        0xFF,
        0xFF,
        0xFF,
        0xFF,  # 0xB8
        0xFF,
        0xFF,
        0xFF,
        0xFF,
        0xFF,
        0xFF,
        0xFF,
        0xFF,  # 0xC0
        0xFF,
        0xFF,
        0xFF,
        0xFF,
        0xFF,
        0xFF,
        0xFF,
        0xFF,  # 0xC8
        0xFF,
        0xFF,
        0xFF,
        0xFF,
        0xFF,
        0xFF,
        0xFF,
        0xFF,  # 0xD0
        0xFF,
        0xFF,
        0xFF,
        0xFF,
        0xFF,
        0xFF,
        0xFF,
        0xFF,  # 0xD8
        0xFF,
        0xFF,
        0xFF,
        0xFF,
        0xFF,
        0xFF,
        0xFF,
        0xFF,  # 0xE0
        0xFF,
        0xFF,
        0xFF,
        0xFF,
        0xFF,
        0xFF,
        0xFF,
        0xFF,  # 0xE8
        0xFF,
        0xFF,
        0xFF,
        0xFF,
        0xFF,
        0xFF,
        0xFF,
        0xFF,  # 0xF0
        0xFF,
        0xFF,
        0xFF,
        0xFF,
        0xFF,
        0xFF,
        0xFF,
        0xFF,  # 0xF8
    ]
)

EntropyReader = Union["Callable[[int], bytes]", "MonotonicEntropy", "LockedMonotonicReader", None]


class ULID:
    __slots__ = ("_data",)

    def __init__(self, data: builtins.bytes = b"\x00" * 16) -> None:
        if len(data) != BINARY_SIZE:
            raise ErrDataSize()
        self._data = bytes(data)

    def __str__(self) -> str:
        return self.string()

    def __repr__(self) -> str:
        return f"ULID({self.string()!r})"

    def __bytes__(self) -> builtins.bytes:
        return self._data

    def __int__(self) -> int:
        return int.from_bytes(self._data, "big")

    def __hash__(self) -> int:
        return hash(self._data)

    def __eq__(self, other: object) -> bool:
        if isinstance(other, ULID):
            return self._data == other._data
        return NotImplemented

    def __ne__(self, other: object) -> bool:
        if isinstance(other, ULID):
            return self._data != other._data
        return NotImplemented

    def __lt__(self, other: object) -> bool:
        if isinstance(other, ULID):
            return self._data < other._data
        return NotImplemented

    def __le__(self, other: object) -> bool:
        if isinstance(other, ULID):
            return self._data <= other._data
        return NotImplemented

    def __gt__(self, other: object) -> bool:
        if isinstance(other, ULID):
            return self._data > other._data
        return NotImplemented

    def __ge__(self, other: object) -> bool:
        if isinstance(other, ULID):
            return self._data >= other._data
        return NotImplemented

    def string(self) -> str:
        return _encode(self._data)

    def prefixed(self, prefix: str) -> str:
        return prefix + "_" + self.string()

    def bytes(self) -> builtins.bytes:
        return self._data

    def time(self) -> int:
        d = self._data
        return d[5] | (d[4] << 8) | (d[3] << 16) | (d[2] << 24) | (d[1] << 32) | (d[0] << 40)

    def timestamp(self) -> datetime:
        return time(self.time())

    def entropy(self) -> builtins.bytes:
        return self._data[6:]

    def is_zero(self) -> bool:
        return self._data == b"\x00" * 16

    def compare(self, other: ULID) -> int:
        if self._data < other._data:
            return -1
        if self._data > other._data:
            return 1
        return 0

    def set_time(self, ms: int) -> ULID:
        if ms > MAX_TIME:
            raise ErrBigTime()
        buf = bytearray(self._data)
        buf[0] = (ms >> 40) & 0xFF
        buf[1] = (ms >> 32) & 0xFF
        buf[2] = (ms >> 24) & 0xFF
        buf[3] = (ms >> 16) & 0xFF
        buf[4] = (ms >> 8) & 0xFF
        buf[5] = ms & 0xFF
        return ULID(bytes(buf))

    def set_entropy(self, e: builtins.bytes) -> ULID:
        if len(e) != 10:
            raise ErrDataSize()
        buf = bytearray(self._data)
        buf[6:] = e
        return ULID(bytes(buf))

    def marshal_binary(self) -> builtins.bytes:
        return self._data

    def marshal_text(self) -> builtins.bytes:
        return self.string().encode("ascii")

    def marshal_json(self) -> builtins.bytes:
        return json.dumps(self.string()).encode("ascii")

    @staticmethod
    def unmarshal_binary(data: builtins.bytes) -> ULID:
        if len(data) != BINARY_SIZE:
            raise ErrDataSize()
        return ULID(data)

    @staticmethod
    def unmarshal_text(data: builtins.bytes | str) -> ULID:
        if isinstance(data, str):
            return _parse(data, False)
        return _parse(data.decode("ascii"), False)

    @staticmethod
    def unmarshal_json(data: builtins.bytes | str) -> ULID:
        raw = data if isinstance(data, str) else data.decode("ascii")
        if len(raw) < 2 or raw[0] != '"' or raw[-1] != '"':
            raise ErrDataSize()
        return _parse(raw[1:-1], False)


def _encode(d: bytes) -> str:
    enc = _ENCODING
    # Timestamp (6 bytes -> 10 characters) - fully unrolled
    c0 = enc[(d[0] & 224) >> 5]
    c1 = enc[d[0] & 31]
    c2 = enc[(d[1] & 248) >> 3]
    c3 = enc[((d[1] & 7) << 2) | ((d[2] & 192) >> 6)]
    c4 = enc[(d[2] & 62) >> 1]
    c5 = enc[((d[2] & 1) << 4) | ((d[3] & 240) >> 4)]
    c6 = enc[((d[3] & 15) << 1) | ((d[4] & 128) >> 7)]
    c7 = enc[(d[4] & 124) >> 2]
    c8 = enc[((d[4] & 3) << 3) | ((d[5] & 224) >> 5)]
    c9 = enc[d[5] & 31]
    # Entropy (10 bytes -> 16 characters) - fully unrolled
    c10 = enc[(d[6] & 248) >> 3]
    c11 = enc[((d[6] & 7) << 2) | ((d[7] & 192) >> 6)]
    c12 = enc[(d[7] & 62) >> 1]
    c13 = enc[((d[7] & 1) << 4) | ((d[8] & 240) >> 4)]
    c14 = enc[((d[8] & 15) << 1) | ((d[9] & 128) >> 7)]
    c15 = enc[(d[9] & 124) >> 2]
    c16 = enc[((d[9] & 3) << 3) | ((d[10] & 224) >> 5)]
    c17 = enc[d[10] & 31]
    c18 = enc[(d[11] & 248) >> 3]
    c19 = enc[((d[11] & 7) << 2) | ((d[12] & 192) >> 6)]
    c20 = enc[(d[12] & 62) >> 1]
    c21 = enc[((d[12] & 1) << 4) | ((d[13] & 240) >> 4)]
    c22 = enc[((d[13] & 15) << 1) | ((d[14] & 128) >> 7)]
    c23 = enc[(d[14] & 124) >> 2]
    c24 = enc[((d[14] & 3) << 3) | ((d[15] & 224) >> 5)]
    c25 = enc[d[15] & 31]
    return (
        c0
        + c1
        + c2
        + c3
        + c4
        + c5
        + c6
        + c7
        + c8
        + c9
        + c10
        + c11
        + c12
        + c13
        + c14
        + c15
        + c16
        + c17
        + c18
        + c19
        + c20
        + c21
        + c22
        + c23
        + c24
        + c25
    )


def _parse(s: str, strict: bool) -> ULID:
    if len(s) != ENCODED_SIZE:
        raise ErrDataSize()

    v = s.encode("ascii") if isinstance(s, str) else s
    dec = _DEC

    if dec[v[0]] > 7:
        raise ErrOverflow()

    if strict:
        for i in range(ENCODED_SIZE):
            if dec[v[i]] == 0xFF:
                raise ErrInvalidCharacters()

    # Timestamp (10 characters -> 6 bytes) - fully unrolled
    b0 = (dec[v[0]] << 5) | dec[v[1]]
    b1 = (dec[v[2]] << 3) | (dec[v[3]] >> 2)
    b2 = (dec[v[3]] << 6) | (dec[v[4]] << 1) | (dec[v[5]] >> 4)
    b3 = (dec[v[5]] << 4) | (dec[v[6]] >> 1)
    b4 = (dec[v[6]] << 7) | (dec[v[7]] << 2) | (dec[v[8]] >> 3)
    b5 = (dec[v[8]] << 5) | dec[v[9]]
    # Entropy (16 characters -> 10 bytes) - fully unrolled
    b6 = (dec[v[10]] << 3) | (dec[v[11]] >> 2)
    b7 = (dec[v[11]] << 6) | (dec[v[12]] << 1) | (dec[v[13]] >> 4)
    b8 = (dec[v[13]] << 4) | (dec[v[14]] >> 1)
    b9 = (dec[v[14]] << 7) | (dec[v[15]] << 2) | (dec[v[16]] >> 3)
    b10 = (dec[v[16]] << 5) | dec[v[17]]
    b11 = (dec[v[18]] << 3) | (dec[v[19]] >> 2)
    b12 = (dec[v[19]] << 6) | (dec[v[20]] << 1) | (dec[v[21]] >> 4)
    b13 = (dec[v[21]] << 4) | (dec[v[22]] >> 1)
    b14 = (dec[v[22]] << 7) | (dec[v[23]] << 2) | (dec[v[24]] >> 3)
    b15 = (dec[v[24]] << 5) | dec[v[25]]

    data = bytes(
        [
            b0 & 0xFF,
            b1 & 0xFF,
            b2 & 0xFF,
            b3 & 0xFF,
            b4 & 0xFF,
            b5 & 0xFF,
            b6 & 0xFF,
            b7 & 0xFF,
            b8 & 0xFF,
            b9 & 0xFF,
            b10 & 0xFF,
            b11 & 0xFF,
            b12 & 0xFF,
            b13 & 0xFF,
            b14 & 0xFF,
            b15 & 0xFF,
        ]
    )
    return ULID(data)


def new(ms: int, entropy: EntropyReader = None) -> ULID:
    if ms > MAX_TIME:
        raise ErrBigTime()
    buf = bytearray(16)
    buf[0] = (ms >> 40) & 0xFF
    buf[1] = (ms >> 32) & 0xFF
    buf[2] = (ms >> 24) & 0xFF
    buf[3] = (ms >> 16) & 0xFF
    buf[4] = (ms >> 8) & 0xFF
    buf[5] = ms & 0xFF

    if entropy is not None:
        if hasattr(entropy, "monotonic_read"):
            rand_bytes = entropy.monotonic_read(ms)
            buf[6:] = rand_bytes[:10]
        elif callable(entropy):
            rand_bytes = entropy(10)
            buf[6:] = rand_bytes[:10]
        else:
            raise TypeError(f"unsupported entropy type: {type(entropy)}")

    return ULID(bytes(buf))


def must_new(ms: int, entropy: EntropyReader = None) -> ULID:
    return new(ms, entropy)


_default_entropy: EntropyReader = None
_default_entropy_initialized = False


def _get_default_entropy() -> EntropyReader:
    global _default_entropy, _default_entropy_initialized
    if not _default_entropy_initialized:
        from ulid.monotonic import LockedMonotonicReader, monotonic

        _default_entropy = LockedMonotonicReader(monotonic(os.urandom, 0))
        _default_entropy_initialized = True
    return _default_entropy


def make() -> ULID:
    return must_new(now(), _get_default_entropy())


def parse(s: str) -> ULID:
    return _parse(s, False)


def parse_strict(s: str) -> ULID:
    return _parse(s, True)


def parse_prefixed(s: str) -> tuple[str, ULID]:
    idx = s.find("_")
    if idx == -1:
        raise ErrInvalidPrefix()
    prefix = s[:idx]
    ulid_part = s[idx + 1 :]
    if len(ulid_part) != ENCODED_SIZE:
        raise ErrDataSize()
    return prefix, _parse(ulid_part, False)


def must_parse(s: str) -> ULID:
    return parse(s)


def must_parse_strict(s: str) -> ULID:
    return parse_strict(s)


def now() -> int:
    return int(_time.time() * 1000)


def timestamp(dt: datetime) -> int:
    return int(dt.timestamp() * 1000)


def time(ms: int) -> datetime:
    return datetime.fromtimestamp(ms / 1000.0, tz=timezone.utc)


def max_time() -> int:
    return MAX_TIME


def default_entropy() -> EntropyReader:
    return _get_default_entropy()


ZERO = ULID()
