from __future__ import annotations

import json
import os
import random
import threading
import time
from datetime import datetime, timezone

import ulid


class TestNew:
    def test_with_entropy(self) -> None:
        uid = ulid.new(ulid.now(), os.urandom)
        assert not uid.is_zero()

    def test_with_none_entropy(self) -> None:
        ms = ulid.now()
        uid = ulid.new(ms, None)
        assert uid.time() == ms
        assert uid.entropy() == b"\x00" * 10

    def test_with_big_time(self) -> None:
        try:
            ulid.new(ulid.max_time() + 1, None)
            assert False, "expected ErrBigTime"
        except ulid.ErrBigTime:
            pass

    def test_with_max_time(self) -> None:
        uid = ulid.new(ulid.max_time(), None)
        assert uid.time() == ulid.max_time()


class TestMustNew:
    def test_success(self) -> None:
        uid = ulid.must_new(ulid.now(), os.urandom)
        assert not uid.is_zero()

    def test_panics_on_error(self) -> None:
        try:
            ulid.must_new(ulid.max_time() + 1, None)
            assert False, "expected exception"
        except ulid.ErrBigTime:
            pass


class TestMake:
    def test_basic(self) -> None:
        uid = ulid.make()
        assert not uid.is_zero()

        n = ulid.now()
        ts = uid.time()
        assert ts <= n
        assert ts >= n - 1000


class TestParse:
    def test_valid(self) -> None:
        orig = ulid.make()
        s = orig.string()
        parsed = ulid.parse(s)
        assert orig == parsed

    def test_case_insensitive(self) -> None:
        orig = ulid.make()
        s = orig.string()
        upper = ulid.parse(s.upper())
        assert orig == upper

    def test_wrong_length(self) -> None:
        try:
            ulid.parse("short")
            assert False, "expected ErrDataSize"
        except ulid.ErrDataSize:
            pass

    def test_overflow(self) -> None:
        try:
            ulid.parse("80000000000000000000000000")
            assert False, "expected ErrOverflow"
        except ulid.ErrOverflow:
            pass

    def test_max_valid(self) -> None:
        uid = ulid.parse("7ZZZZZZZZZZZZZZZZZZZZZZZZZ")
        assert uid.time() == ulid.max_time()


class TestParseStrict:
    def test_valid(self) -> None:
        orig = ulid.make()
        ulid.parse_strict(orig.string())

    def test_invalid_characters(self) -> None:
        try:
            ulid.parse_strict("0000000000000000000000000i")
            assert False, "expected ErrInvalidCharacters"
        except ulid.ErrInvalidCharacters:
            pass

    def test_uppercase_valid(self) -> None:
        orig = ulid.make()
        ulid.parse_strict(orig.string().upper())


class TestMustParse:
    def test_success(self) -> None:
        orig = ulid.make()
        parsed = ulid.must_parse(orig.string())
        assert orig == parsed

    def test_panics_on_error(self) -> None:
        try:
            ulid.must_parse("bad")
            assert False, "expected exception"
        except ulid.ErrDataSize:
            pass


class TestMustParseStrict:
    def test_panics_on_error(self) -> None:
        try:
            ulid.must_parse_strict("0000000000000000000000000i")
            assert False, "expected exception"
        except ulid.ErrInvalidCharacters:
            pass


class TestPrefixed:
    def test_basic_prefix(self) -> None:
        uid = ulid.make()
        s = uid.prefixed("user")
        assert s.startswith("user_")
        assert len(s) == len("user_") + ulid.ENCODED_SIZE

    def test_txn_prefix(self) -> None:
        uid = ulid.make()
        s = uid.prefixed("txn")
        assert s.startswith("txn_")

    def test_ulid_portion_is_lowercase(self) -> None:
        uid = ulid.make()
        s = uid.prefixed("evt")
        ulid_part = s[len("evt_") :]
        assert ulid_part == ulid_part.lower()

    def test_prefixed_round_trip(self) -> None:
        uid = ulid.make()
        s = uid.prefixed("user")
        prefix, parsed = ulid.parse_prefixed(s)
        assert prefix == "user"
        assert parsed == uid


class TestParsePrefixed:
    def test_valid(self) -> None:
        uid = ulid.make()
        s = uid.prefixed("user")
        prefix, parsed = ulid.parse_prefixed(s)
        assert prefix == "user"
        assert parsed == uid

    def test_no_underscore(self) -> None:
        try:
            ulid.parse_prefixed("nounderscore")
            assert False, "expected ErrInvalidPrefix"
        except ulid.ErrInvalidPrefix:
            pass

    def test_wrong_ulid_length(self) -> None:
        try:
            ulid.parse_prefixed("user_short")
            assert False, "expected ErrDataSize"
        except ulid.ErrDataSize:
            pass

    def test_single_char_prefix(self) -> None:
        uid = ulid.make()
        s = uid.prefixed("x")
        prefix, parsed = ulid.parse_prefixed(s)
        assert prefix == "x"
        assert parsed == uid


class TestLowercaseOutput:
    def test_string_lowercase(self) -> None:
        for _ in range(100):
            uid = ulid.make()
            s = uid.string()
            assert s == s.lower()

    def test_json_lowercase(self) -> None:
        uid = ulid.make()
        data = uid.marshal_json()
        inner = json.loads(data)
        assert inner == inner.lower()

    def test_marshal_text_lowercase(self) -> None:
        uid = ulid.make()
        data = uid.marshal_text()
        assert data.decode() == data.decode().lower()


class TestTimestamp:
    def test_timestamp(self) -> None:
        dt = datetime.now(tz=timezone.utc)
        ms = ulid.timestamp(dt)
        expected = int(dt.timestamp() * 1000)
        assert ms == expected

    def test_time(self) -> None:
        ms = 1609459200000  # 2021-01-01 00:00:00 UTC
        t = ulid.time(ms)
        assert int(t.timestamp()) == 1609459200

    def test_max_time(self) -> None:
        expected = (1 << 48) - 1
        assert ulid.max_time() == expected

    def test_timestamp_round_trip(self) -> None:
        dt = datetime.now(tz=timezone.utc)
        ms = ulid.timestamp(dt)
        recovered = ulid.time(ms)
        assert abs(dt.timestamp() - recovered.timestamp()) < 0.001


class TestULIDMethods:
    def test_string(self) -> None:
        uid = ulid.make()
        s = uid.string()
        assert len(s) == ulid.ENCODED_SIZE

    def test_bytes(self) -> None:
        uid = ulid.make()
        b = uid.bytes()
        assert len(b) == ulid.BINARY_SIZE

    def test_time(self) -> None:
        ms = 1234567890123
        uid = ulid.new(ms, None)
        assert uid.time() == ms

    def test_entropy(self) -> None:
        uid = ulid.new(ulid.now(), os.urandom)
        e = uid.entropy()
        assert len(e) == 10

    def test_is_zero(self) -> None:
        zero = ulid.ULID()
        assert zero.is_zero()

        uid = ulid.make()
        assert not uid.is_zero()

    def test_compare(self) -> None:
        a = ulid.new(1000, None)
        b = ulid.new(2000, None)
        assert a.compare(b) < 0
        assert b.compare(a) > 0
        assert a.compare(a) == 0


class TestSetTimeEntropy:
    def test_set_time(self) -> None:
        uid = ulid.ULID()
        uid = uid.set_time(12345)
        assert uid.time() == 12345

        try:
            uid.set_time(ulid.max_time() + 1)
            assert False, "expected ErrBigTime"
        except ulid.ErrBigTime:
            pass

    def test_set_entropy(self) -> None:
        uid = ulid.ULID()
        e = bytes(range(1, 11))
        uid = uid.set_entropy(e)
        assert uid.entropy() == e

        try:
            uid.set_entropy(b"\x00" * 5)
            assert False, "expected ErrDataSize"
        except ulid.ErrDataSize:
            pass


class TestMarshal:
    def test_marshal_binary_round_trip(self) -> None:
        uid = ulid.make()
        data = uid.marshal_binary()
        assert len(data) == ulid.BINARY_SIZE
        parsed = ulid.ULID.unmarshal_binary(data)
        assert uid == parsed

    def test_unmarshal_binary_wrong_size(self) -> None:
        try:
            ulid.ULID.unmarshal_binary(b"\x01\x02\x03")
            assert False, "expected ErrDataSize"
        except ulid.ErrDataSize:
            pass

    def test_marshal_text_round_trip(self) -> None:
        uid = ulid.make()
        data = uid.marshal_text()
        assert len(data) == ulid.ENCODED_SIZE
        assert data.decode() == uid.string()
        parsed = ulid.ULID.unmarshal_text(data)
        assert uid == parsed

    def test_json_round_trip(self) -> None:
        uid = ulid.make()
        data = uid.marshal_json()
        parsed = ulid.ULID.unmarshal_json(data)
        assert uid == parsed

    def test_json_unmarshal_errors(self) -> None:
        try:
            ulid.ULID.unmarshal_json(b"notquoted")
            assert False, "expected ErrDataSize"
        except ulid.ErrDataSize:
            pass
        try:
            ulid.ULID.unmarshal_json(b'""')
            assert False, "expected ErrDataSize"
        except ulid.ErrDataSize:
            pass


class TestEncodingRoundTrip:
    def test_stress(self) -> None:
        for i in range(1000):
            orig = ulid.make()
            s = orig.string()
            parsed = ulid.parse(s)
            assert orig == parsed, f"iteration {i}: text round-trip failed"

            data = orig.marshal_binary()
            bin_parsed = ulid.ULID.unmarshal_binary(data)
            assert orig == bin_parsed, f"iteration {i}: binary round-trip failed"


class TestSortOrder:
    def test_lexicographic(self) -> None:
        ids = [ulid.make() for _ in range(100)]
        strs = [uid.string() for uid in ids]
        sorted_ids = sorted(ids)
        sorted_strs = sorted(strs)
        for i, uid in enumerate(sorted_ids):
            assert uid.string() == sorted_strs[i]

    def test_monotonic(self) -> None:
        entropy = ulid.monotonic(os.urandom, 0)
        ms = ulid.now()
        prev = ulid.new(ms, entropy)
        for i in range(1000):
            nxt = ulid.new(ms, entropy)
            assert nxt.compare(prev) > 0, f"iteration {i}: monotonic order violated"
            prev = nxt

    def test_monotonic_new_millisecond(self) -> None:
        entropy = ulid.monotonic(os.urandom, 0)
        id1 = ulid.new(1000, entropy)
        id2 = ulid.new(2000, entropy)
        assert id1 != id2
        assert id2.compare(id1) > 0

    def test_monotonic_overflow(self) -> None:
        max_entropy_data = bytes([0xFF] * 10 + [0x00] * 7 + [0x01])
        idx = 0

        def fake_reader(n: int) -> bytes:
            nonlocal idx
            result = max_entropy_data[idx : idx + n]
            idx += n
            if len(result) < n:
                result = result + b"\x00" * (n - len(result))
            return result

        entropy = ulid.monotonic(fake_reader, 1)
        ms = ulid.now()
        ulid.new(ms, entropy)
        try:
            ulid.new(ms, entropy)
            assert False, "expected ErrMonotonicOverflow"
        except ulid.ErrMonotonicOverflow:
            pass


class TestConcurrency:
    def test_concurrent_make(self) -> None:
        ids: list[ulid.ULID] = [ulid.ULID() for _ in range(1000)]
        errors: list[Exception] = []

        def worker(idx: int) -> None:
            try:
                ids[idx] = ulid.make()
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(1000)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors
        seen: set[ulid.ULID] = set()
        for uid in ids:
            assert not uid.is_zero()
            assert uid not in seen, f"duplicate ULID: {uid.string()}"
            seen.add(uid)


class TestGenerator:
    def test_basic(self) -> None:
        gen = ulid.new_generator()
        uid = gen.make()
        assert not uid.is_zero()

    def test_with_node_id(self) -> None:
        gen = ulid.new_generator(ulid.with_node_id(42))
        uid = gen.make()
        nid, ok = gen.node_id()
        assert ok
        assert nid == 42
        b = uid.bytes()
        assert b[6] == 0
        assert b[7] == 42

    def test_with_prefix(self) -> None:
        gen = ulid.new_generator(ulid.with_prefix("txn"))
        s = gen.make_prefixed()
        assert s.startswith("txn_")

    def test_override_prefix(self) -> None:
        gen = ulid.new_generator(ulid.with_prefix("txn"))
        s = gen.make_prefixed("user")
        assert s.startswith("user_")

    def test_no_prefix_panics(self) -> None:
        gen = ulid.new_generator()
        try:
            gen.make_prefixed()
            assert False, "expected RuntimeError"
        except RuntimeError:
            pass

    def test_generator_new(self) -> None:
        gen = ulid.new_generator(ulid.with_node_id(100))
        ms = ulid.now()
        uid = gen.new(ms)
        assert uid.time() == ms
        b = uid.bytes()
        assert b[6] == 0
        assert b[7] == 100

    def test_distributed_uniqueness(self) -> None:
        num_nodes = 10
        ids_per_node = 1000
        all_ids: list[ulid.ULID] = [ulid.ULID() for _ in range(num_nodes * ids_per_node)]
        errors: list[Exception] = []

        def node_worker(node: int) -> None:
            try:
                gen = ulid.new_generator(ulid.with_node_id(node))
                offset = node * ids_per_node
                for i in range(ids_per_node):
                    all_ids[offset + i] = gen.make()
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=node_worker, args=(n,)) for n in range(num_nodes)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors
        seen: set[ulid.ULID] = set()
        for uid in all_ids:
            assert not uid.is_zero()
            assert uid not in seen, f"duplicate ULID across nodes: {uid.string()}"
            seen.add(uid)

    def test_generator_concurrent(self) -> None:
        gen = ulid.new_generator(ulid.with_node_id(1))
        ids: list[ulid.ULID] = [ulid.ULID() for _ in range(1000)]
        errors: list[Exception] = []

        def worker(idx: int) -> None:
            try:
                ids[idx] = gen.make()
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(1000)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors
        seen: set[ulid.ULID] = set()
        for uid in ids:
            assert uid not in seen, f"duplicate ULID: {uid.string()}"
            seen.add(uid)


class TestEdgeCases:
    def test_zero_ulid(self) -> None:
        s = ulid.ZERO.string()
        expected = "00000000000000000000000000"
        assert s == expected
        parsed = ulid.parse(expected)
        assert parsed == ulid.ZERO

    def test_known_values(self) -> None:
        uid = ulid.new(0, None)
        assert uid.string() == "00000000000000000000000000"
        max_id = ulid.parse("7zzzzzzzzzzzzzzzzzzzzzzzzz")
        assert max_id.time() == ulid.max_time()

    def test_default_entropy(self) -> None:
        e = ulid.default_entropy()
        assert e is not None
        uid = ulid.new(ulid.now(), e)
        assert not uid.is_zero()

    def test_timestamp_preservation(self) -> None:
        timestamps = [0, 1, 1000, int(time.time() * 1000), ulid.max_time() - 1, ulid.max_time()]
        for ms in timestamps:
            uid = ulid.new(ms, os.urandom)
            assert uid.time() == ms
            parsed = ulid.parse(uid.string())
            assert parsed.time() == ms

    def test_overflow_boundary(self) -> None:
        for c in "01234567":
            s = c + "0" * 25
            ulid.parse(s)

        overflow_cases = [
            "80000000000000000000000000",
            "90000000000000000000000000",
            "a0000000000000000000000000",
            "g0000000000000000000000000",
            "z0000000000000000000000000",
        ]
        for s in overflow_cases:
            try:
                ulid.parse(s)
                assert False, f"string {s!r} should overflow"
            except ulid.ErrOverflow:
                pass

    def test_monotonic_large_increment(self) -> None:
        entropy = ulid.monotonic(os.urandom, (1 << 64) - 1)
        ms = ulid.now()
        ulid.new(ms, entropy)
        try:
            ulid.new(ms, entropy)
        except ulid.ErrMonotonicOverflow:
            pass


class TestPythonSpecific:
    def test_rich_comparisons(self) -> None:
        a = ulid.new(1000, None)
        b = ulid.new(2000, None)
        assert a < b
        assert a <= b
        assert b > a
        assert b >= a
        assert a == a
        assert a != b

    def test_hash_and_set(self) -> None:
        uid = ulid.make()
        s: set[ulid.ULID] = {uid}
        assert uid in s
        parsed = ulid.parse(uid.string())
        assert parsed in s

    def test_int_conversion(self) -> None:
        uid = ulid.new(0, None)
        assert int(uid) == 0
        uid2 = ulid.make()
        assert int(uid2) > 0

    def test_bytes_conversion(self) -> None:
        uid = ulid.make()
        b = bytes(uid)
        assert len(b) == 16
        assert b == uid.bytes()

    def test_sorted(self) -> None:
        ids = [ulid.make() for _ in range(100)]
        sorted_ids = sorted(ids)
        for i in range(len(sorted_ids) - 1):
            assert sorted_ids[i] <= sorted_ids[i + 1]

    def test_locked_monotonic_reader(self) -> None:
        inner = ulid.monotonic(os.urandom, 0)
        locked = ulid.LockedMonotonicReader(inner)
        errors: list[Exception] = []

        ms = ulid.now()

        def worker() -> None:
            try:
                ulid.new(ms, locked)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker) for _ in range(100)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors

    def test_monotonic_with_random(self) -> None:
        rng = random.Random(42)

        def rng_reader(n: int) -> bytes:
            return bytes(rng.getrandbits(8) for _ in range(n))

        entropy = ulid.monotonic(rng_reader, 0)
        ms = ulid.now()
        prev = ulid.new(ms, entropy)
        for i in range(100):
            nxt = ulid.new(ms, entropy)
            assert nxt.compare(prev) > 0, f"monotonic order violated at iteration {i}"
            prev = nxt
