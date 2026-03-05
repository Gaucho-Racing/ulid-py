from __future__ import annotations

import os

import ulid


def test_bench_new_crypto(benchmark) -> None:  # type: ignore[no-untyped-def]
    benchmark(ulid.new, ulid.now(), os.urandom)


def test_bench_new_monotonic_crypto(benchmark) -> None:  # type: ignore[no-untyped-def]
    entropy = ulid.monotonic(os.urandom, 0)
    benchmark(ulid.new, ulid.now(), entropy)


def test_bench_make(benchmark) -> None:  # type: ignore[no-untyped-def]
    benchmark(ulid.make)


def test_bench_parse(benchmark) -> None:  # type: ignore[no-untyped-def]
    s = ulid.make().string()
    benchmark(ulid.parse, s)


def test_bench_parse_strict(benchmark) -> None:  # type: ignore[no-untyped-def]
    s = ulid.make().string()
    benchmark(ulid.parse_strict, s)


def test_bench_parse_prefixed(benchmark) -> None:  # type: ignore[no-untyped-def]
    s = ulid.make().prefixed("user")
    benchmark(ulid.parse_prefixed, s)


def test_bench_string(benchmark) -> None:  # type: ignore[no-untyped-def]
    uid = ulid.make()
    benchmark(uid.string)


def test_bench_prefixed(benchmark) -> None:  # type: ignore[no-untyped-def]
    uid = ulid.make()
    benchmark(uid.prefixed, "user")


def test_bench_marshal_text(benchmark) -> None:  # type: ignore[no-untyped-def]
    uid = ulid.make()
    benchmark(uid.marshal_text)


def test_bench_marshal_binary(benchmark) -> None:  # type: ignore[no-untyped-def]
    uid = ulid.make()
    benchmark(uid.marshal_binary)


def test_bench_marshal_json(benchmark) -> None:  # type: ignore[no-untyped-def]
    uid = ulid.make()
    benchmark(uid.marshal_json)


def test_bench_compare(benchmark) -> None:  # type: ignore[no-untyped-def]
    a = ulid.make()
    b = ulid.make()
    benchmark(a.compare, b)


def test_bench_now(benchmark) -> None:  # type: ignore[no-untyped-def]
    benchmark(ulid.now)


def test_bench_time(benchmark) -> None:  # type: ignore[no-untyped-def]
    uid = ulid.make()
    benchmark(uid.time)


def test_bench_generator_make(benchmark) -> None:  # type: ignore[no-untyped-def]
    gen = ulid.new_generator()
    benchmark(gen.make)


def test_bench_generator_make_node_id(benchmark) -> None:  # type: ignore[no-untyped-def]
    gen = ulid.new_generator(ulid.with_node_id(42))
    benchmark(gen.make)


def test_bench_generator_make_prefixed(benchmark) -> None:  # type: ignore[no-untyped-def]
    gen = ulid.new_generator(ulid.with_node_id(1), ulid.with_prefix("txn"))
    benchmark(gen.make_prefixed)
