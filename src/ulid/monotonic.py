from __future__ import annotations

import random
import threading
from collections.abc import Callable

from ulid.ulid import ErrMonotonicOverflow

_MASK_U16 = 0xFFFF
_MASK_U64 = 0xFFFFFFFFFFFFFFFF
_MAX_U32 = 0xFFFFFFFF


class _UInt80:
    __slots__ = ("hi", "lo")

    def __init__(self) -> None:
        self.hi: int = 0
        self.lo: int = 0

    def add(self, n: int) -> bool:
        lo = self.lo
        self.lo = (self.lo + n) & _MASK_U64
        if self.lo < lo:
            hi = self.hi
            self.hi = (self.hi + 1) & _MASK_U16
            return self.hi < hi
        return False

    def is_zero(self) -> bool:
        return self.hi == 0 and self.lo == 0

    def read_from(self, p: bytes | bytearray) -> None:
        self.hi = (p[0] << 8) | p[1]
        self.lo = (
            (p[2] << 56) | (p[3] << 48) | (p[4] << 40) | (p[5] << 32) | (p[6] << 24) | (p[7] << 16) | (p[8] << 8) | p[9]
        )

    def write_to(self, p: bytearray) -> None:
        p[0] = (self.hi >> 8) & 0xFF
        p[1] = self.hi & 0xFF
        p[2] = (self.lo >> 56) & 0xFF
        p[3] = (self.lo >> 48) & 0xFF
        p[4] = (self.lo >> 40) & 0xFF
        p[5] = (self.lo >> 32) & 0xFF
        p[6] = (self.lo >> 24) & 0xFF
        p[7] = (self.lo >> 16) & 0xFF
        p[8] = (self.lo >> 8) & 0xFF
        p[9] = self.lo & 0xFF


class MonotonicEntropy:
    __slots__ = ("_reader", "_ms", "_inc", "_entropy", "_rng")

    def __init__(self, reader: Callable[[int], bytes], inc: int) -> None:
        self._reader = reader
        self._inc = inc if inc != 0 else _MAX_U32
        self._ms: int = 0
        self._entropy = _UInt80()
        self._rng: random.Random | None = None
        if isinstance(reader, random.Random):
            self._rng = reader

    def monotonic_read(self, ms: int) -> bytes:
        if not self._entropy.is_zero() and self._ms == ms:
            inc = self._increment()
            if self._entropy.add(inc):
                raise ErrMonotonicOverflow()
            buf = bytearray(10)
            self._entropy.write_to(buf)
            return bytes(buf)

        rand_bytes = self._reader(10)
        self._ms = ms
        self._entropy.read_from(rand_bytes)
        return rand_bytes[:10]

    def read(self, n: int) -> bytes:
        return self._reader(n)

    def _increment(self) -> int:
        if self._rng is not None:
            return 1 + self._rng.randrange(self._inc)
        rand_bytes = self._reader(8)
        val = (
            (rand_bytes[0] << 56)
            | (rand_bytes[1] << 48)
            | (rand_bytes[2] << 40)
            | (rand_bytes[3] << 32)
            | (rand_bytes[4] << 24)
            | (rand_bytes[5] << 16)
            | (rand_bytes[6] << 8)
            | rand_bytes[7]
        )
        return 1 + (val % self._inc)


class LockedMonotonicReader:
    __slots__ = ("_inner", "_lock")

    def __init__(self, inner: MonotonicEntropy) -> None:
        self._inner = inner
        self._lock = threading.Lock()

    def monotonic_read(self, ms: int) -> bytes:
        with self._lock:
            return self._inner.monotonic_read(ms)

    def read(self, n: int) -> bytes:
        with self._lock:
            return self._inner.read(n)

    def __call__(self, n: int) -> bytes:
        return self.read(n)


def Monotonic(entropy: Callable[[int], bytes], inc: int) -> MonotonicEntropy:
    return MonotonicEntropy(entropy, inc)
