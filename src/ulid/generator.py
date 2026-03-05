from __future__ import annotations

import os
import threading
from collections.abc import Callable

from ulid.monotonic import Monotonic, MonotonicEntropy
from ulid.ulid import ULID, New, Now


class Generator:
    __slots__ = ("_mu", "_entropy", "_node_id", "_has_node", "_prefix")

    def __init__(self) -> None:
        self._mu = threading.Lock()
        self._entropy: MonotonicEntropy = Monotonic(os.urandom, 0)
        self._node_id: int = 0
        self._has_node: bool = False
        self._prefix: str = ""

    def make(self) -> ULID:
        with self._mu:
            uid = New(Now(), self._entropy)
            if self._has_node:
                buf = bytearray(uid._data)
                buf[6] = (self._node_id >> 8) & 0xFF
                buf[7] = self._node_id & 0xFF
                uid = ULID(bytes(buf))
        return uid

    def make_prefixed(self, prefix: str = "") -> str:
        uid = self.make()
        p = prefix if prefix else self._prefix
        if not p:
            raise RuntimeError("ulid: no prefix specified")
        return uid.prefixed(p)

    def new(self, ms: int) -> ULID:
        with self._mu:
            uid = New(ms, self._entropy)
            if self._has_node:
                buf = bytearray(uid._data)
                buf[6] = (self._node_id >> 8) & 0xFF
                buf[7] = self._node_id & 0xFF
                uid = ULID(bytes(buf))
        return uid

    def node_id(self) -> tuple[int, bool]:
        return self._node_id, self._has_node


GeneratorOption = Callable[[Generator], None]


def WithNodeID(node_id: int) -> GeneratorOption:
    def apply(g: Generator) -> None:
        g._node_id = node_id
        g._has_node = True

    return apply


def WithEntropy(reader: Callable[[int], bytes]) -> GeneratorOption:
    def apply(g: Generator) -> None:
        g._entropy = Monotonic(reader, 0)

    return apply


def WithPrefix(prefix: str) -> GeneratorOption:
    def apply(g: Generator) -> None:
        g._prefix = prefix

    return apply


def NewGenerator(*opts: GeneratorOption) -> Generator:
    g = Generator()
    for opt in opts:
        opt(g)
    return g
