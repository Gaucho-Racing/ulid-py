from __future__ import annotations

import os

import ulid


def test_bench_new_crypto(benchmark) -> None:  # type: ignore[no-untyped-def]
    benchmark(ulid.New, ulid.Now(), os.urandom)


def test_bench_new_monotonic_crypto(benchmark) -> None:  # type: ignore[no-untyped-def]
    entropy = ulid.Monotonic(os.urandom, 0)
    benchmark(ulid.New, ulid.Now(), entropy)


def test_bench_make(benchmark) -> None:  # type: ignore[no-untyped-def]
    benchmark(ulid.Make)


def test_bench_parse(benchmark) -> None:  # type: ignore[no-untyped-def]
    s = ulid.Make().string()
    benchmark(ulid.Parse, s)


def test_bench_parse_strict(benchmark) -> None:  # type: ignore[no-untyped-def]
    s = ulid.Make().string()
    benchmark(ulid.ParseStrict, s)


def test_bench_parse_prefixed(benchmark) -> None:  # type: ignore[no-untyped-def]
    s = ulid.Make().prefixed("user")
    benchmark(ulid.ParsePrefixed, s)


def test_bench_string(benchmark) -> None:  # type: ignore[no-untyped-def]
    uid = ulid.Make()
    benchmark(uid.string)


def test_bench_prefixed(benchmark) -> None:  # type: ignore[no-untyped-def]
    uid = ulid.Make()
    benchmark(uid.prefixed, "user")


def test_bench_marshal_text(benchmark) -> None:  # type: ignore[no-untyped-def]
    uid = ulid.Make()
    benchmark(uid.marshal_text)


def test_bench_marshal_binary(benchmark) -> None:  # type: ignore[no-untyped-def]
    uid = ulid.Make()
    benchmark(uid.marshal_binary)


def test_bench_marshal_json(benchmark) -> None:  # type: ignore[no-untyped-def]
    uid = ulid.Make()
    benchmark(uid.marshal_json)


def test_bench_compare(benchmark) -> None:  # type: ignore[no-untyped-def]
    a = ulid.Make()
    b = ulid.Make()
    benchmark(a.compare, b)


def test_bench_now(benchmark) -> None:  # type: ignore[no-untyped-def]
    benchmark(ulid.Now)


def test_bench_time(benchmark) -> None:  # type: ignore[no-untyped-def]
    uid = ulid.Make()
    benchmark(uid.time)


def test_bench_generator_make(benchmark) -> None:  # type: ignore[no-untyped-def]
    gen = ulid.NewGenerator()
    benchmark(gen.make)


def test_bench_generator_make_node_id(benchmark) -> None:  # type: ignore[no-untyped-def]
    gen = ulid.NewGenerator(ulid.WithNodeID(42))
    benchmark(gen.make)


def test_bench_generator_make_prefixed(benchmark) -> None:  # type: ignore[no-untyped-def]
    gen = ulid.NewGenerator(ulid.WithNodeID(1), ulid.WithPrefix("txn"))
    benchmark(gen.make_prefixed)
