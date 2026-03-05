# ulid-py

[![CI](https://github.com/gaucho-racing/ulid-py/actions/workflows/ci.yml/badge.svg)](https://github.com/gaucho-racing/ulid-py/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/gaucho-ulid.svg)](https://pypi.org/project/gaucho-ulid/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A blazing fast, production-grade [ULID](https://github.com/ulid/spec) implementation in Python. Designed to provide a consistent, ergonomic identifier format, ulid-py is currently used across many of Gaucho Racing's services and projects.

- **Lowercase by default** — all string output uses lowercase Crockford Base32
- **Prefix support** — generate entity-scoped IDs like `user_01arz3ndek...` or `txn_01arz3ndek...`
- **Distributed uniqueness** — `Generator` with node ID partitioning guarantees collision-free IDs across up to 65,536 nodes without coordination
- **Monotonic sorting** — IDs generated within the same millisecond are strictly ordered
- **Fully unrolled encoding** — Crockford Base32 encode/decode with no loops
- **Thread-safe** — `make()`, `Generator`, and `default_entropy()` are safe for concurrent use
- **128-bit UUID compatible** — drop-in replacement for UUID columns in databases
- **Fully typed** — PEP 561 compliant with `py.typed` marker, passes `mypy --strict`
- **Zero runtime dependencies** — only stdlib

## Getting Started

### Installing

```sh
pip install gaucho-ulid
```

### Usage

```python
import ulid

# Generate a ULID
id = ulid.make()
print(id)  # 01jgy5fz7rqv8s3n0x4m6k2w1h

# With a prefix
print(id.prefixed("user"))  # user_01jgy5fz7rqv8s3n0x4m6k2w1h

# Parse it back
parsed = ulid.parse("01jgy5fz7rqv8s3n0x4m6k2w1h")
print(parsed.time())       # Unix millisecond timestamp
print(parsed.timestamp())  # datetime

# Parse prefixed IDs
prefix, parsed = ulid.parse_prefixed("user_01jgy5fz7rqv8s3n0x4m6k2w1h")
print(prefix)  # "user"

# Use a Generator for distributed systems
gen = ulid.new_generator(
    ulid.with_node_id(1),
    ulid.with_prefix("evt"),
)
print(gen.make_prefixed())  # evt_01jgy5fz7r...
```

## Specification

This library implements the [ULID spec](https://github.com/ulid/spec) with several opinionated extensions. This section covers the binary format, encoding, monotonicity behavior, distributed uniqueness strategy, and every deviation from the official spec.

### Binary Layout

A ULID is 128 bits (16 bytes), stored in big-endian (network byte order) as an immutable `bytes` object:

```
 0                   1                   2                   3
  0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
 +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
 |                      32_bit_uint_time_high                    |
 +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
 |     16_bit_uint_time_low      |       16_bit_uint_random      |
 +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
 |                       32_bit_uint_random                      |
 +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
 |                       32_bit_uint_random                      |
 +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
```

| Component | Bytes | Bits | Description |
|---|---|---|---|
| Timestamp | `[0:6]` | 48 | Unix milliseconds, big-endian. Valid until year 10889 AD. |
| Entropy | `[6:16]` | 80 | Cryptographic randomness (or node-partitioned randomness). |

Using immutable `bytes` as the underlying type means ULIDs are **hashable**: they can be used as dictionary keys and set members. Byte comparison ordering is consistent with chronological and lexicographic string ordering because the timestamp occupies the most significant bytes.

### Crockford Base32 Encoding

The string representation is 26 characters using the Crockford Base32 alphabet:

```
0123456789abcdefghjkmnpqrstvwxyz
```

The first 10 characters encode the 48-bit timestamp, the remaining 16 encode the 80-bit entropy:

```
ttttttttttrrrrrrrrrrrrrrrr
```

The encoding and decoding are **fully unrolled**: every bit extraction/insertion is a single explicit line with no loops. Decoding uses a 256-byte lookup table for O(1) character-to-value conversion, and both upper and lowercase map to the same values, making parsing inherently case-insensitive.

**Overflow check**: 26 Base32 characters technically encode 130 bits, but a ULID only uses 128. The first character is restricted to values `0`–`7` (3 bits). Any ULID string starting with `8` or higher is rejected with `ErrOverflow`. The largest valid ULID is `7zzzzzzzzzzzzzzzzzzzzzzzzz`.

#### `parse` vs `parse_strict`

`parse` skips character validation for speed. Invalid characters (like `I`, `L`, `O`, `U`) will silently produce wrong bits rather than returning an error. Use `parse_strict` when accepting untrusted input. Use `parse` when you control the input (e.g., reading from your own database).

### Monotonicity

When multiple ULIDs are generated within the same millisecond, the spec requires monotonic ordering. This library implements monotonicity through `MonotonicEntropy`:

```python
import os
import ulid

entropy = ulid.monotonic(os.urandom, 0)
ms = ulid.now()

# All three share the same millisecond: entropy is incremented, not re-randomized
id1 = ulid.new(ms, entropy)  # random entropy R
id2 = ulid.new(ms, entropy)  # R + random_increment
id3 = ulid.new(ms, entropy)  # R + random_increment + random_increment
# id1 < id2 < id3 guaranteed
```

**Overflow behavior**: The 80-bit entropy space is tracked using a custom `_UInt80` type (`uint16` high + `uint64` low) with explicit masking (since Python integers are arbitrary precision). When incrementing would overflow, `ErrMonotonicOverflow` is raised. The library **never** silently wraps around or advances the timestamp.

**Thread safety**: `MonotonicEntropy` itself is **not** thread-safe. For concurrent use, wrap it with `LockedMonotonicReader` (which adds a `threading.Lock`), or use `default_entropy()` / `make()` which do this automatically. The `Generator` class also handles its own locking internally.

### Entropy Sources

The library accepts any `Callable[[int], bytes]` as an entropy source:

| Source | Security | Notes |
|---|---|---|
| `os.urandom` | Cryptographic | Default. Uses OS entropy pool. |
| Custom callable | Varies | Any function `(int) -> bytes`. |
| `monotonic(r, inc)` | Inherits from `r` | Increments within same ms instead of re-reading. |
| `None` | None | Zero entropy. Useful for timestamp-only IDs. |

### Distributed Uniqueness

For multi-node deployments, the `Generator` class supports embedding a **16-bit node ID** in the first 2 bytes of the entropy field:

```python
gen = ulid.new_generator(ulid.with_node_id(42))
id = gen.make()
```

This partitions the entropy layout as follows:

```
 Bytes [0:6]  - 48-bit timestamp (unchanged)
 Bytes [6:8]  - 16-bit node ID (0–65535)
 Bytes [8:16] - 64-bit monotonic random entropy
```

Two generators with different node IDs **cannot** produce the same ULID, even within the same millisecond.

### Prefixed IDs

Prefixed IDs are a library extension for entity-scoped identifiers:

```python
id = ulid.make()
id.prefixed("user")  # "user_01arz3ndektsv4rrffq69g5fav"
id.prefixed("txn")   # "txn_01arz3ndektsv4rrffq69g5fav"
```

The prefix is **not** part of the ULID itself. `parse_prefixed` splits on the first `_` and parses the ULID portion:

```python
prefix, id = ulid.parse_prefixed("user_01arz3ndektsv4rrffq69g5fav")
# prefix = "user", id = the parsed ULID
```

### Deviations from the Official Spec

| Behavior | Official Spec | This Library |
|---|---|---|
| **String case** | Uppercase (`01ARZ3NDEK...`) | Lowercase (`01arz3ndek...`). Parsing remains case-insensitive. |
| **Prefixed IDs** | Not specified | Supported via `prefixed()` and `parse_prefixed()`. |
| **Node ID partitioning** | Not specified | Supported via `Generator` with `with_node_id()`. |
| **Excluded letter handling** | Crockford spec maps `I`→`1`, `L`→`1`, `O`→`0` during decoding | Not mapped. `I`, `L`, `O`, `U` are treated as invalid in strict mode and produce undefined results in non-strict mode. |

### Footguns

- **`parse` does not validate characters.** Use `parse_strict` for untrusted input.
- **`MonotonicEntropy` is not thread-safe.** Using it from multiple threads without `LockedMonotonicReader` will corrupt state. `make()` and `Generator` handle this for you.
- **`bytes()` and `entropy()` return the underlying immutable bytes.** Since `_data` is immutable `bytes`, no copy is needed.
- **`Generator` with node ID clobbers monotonic high bits.** If intra-millisecond ordering matters more than distributed uniqueness, use `make()` instead.
- **Monotonic overflow is an error, not a retry.** When `ErrMonotonicOverflow` is raised, the caller is responsible for handling it.

## API

### Constructors

| Function | Description |
|---|---|
| `make()` | Generate a ULID with current time and default entropy. Thread-safe. |
| `new(ms, entropy)` | Generate with explicit timestamp and entropy source. |
| `must_new(ms, entropy)` | Like `new` (raises on error in Python). |
| `parse(s)` | Decode a 26-char Base32 string. Case-insensitive. |
| `parse_strict(s)` | Like `parse` with character validation. |
| `parse_prefixed(s)` | Parse a `prefix_ulid` string, returning `(prefix, ULID)`. |
| `must_parse(s)` | Like `parse` (raises on error in Python). |
| `must_parse_strict(s)` | Like `parse_strict` (raises on error in Python). |

### ULID Methods

| Method | Description |
|---|---|
| `string()` | 26-char lowercase Crockford Base32 string. |
| `prefixed(p)` | Prefixed string: `p_<ulid>`. |
| `bytes()` | Raw 16-byte data. |
| `time()` | Unix millisecond timestamp. |
| `timestamp()` | Timestamp as `datetime`. |
| `entropy()` | 10-byte entropy. |
| `is_zero()` | True if zero value. |
| `compare(other)` | Lexicographic comparison (-1, 0, +1). |
| `set_time(ms)` | Return new ULID with updated timestamp. |
| `set_entropy(e)` | Return new ULID with updated entropy (10 bytes). |

### Python Special Methods

| Method | Description |
|---|---|
| `__str__` | Same as `string()`. |
| `__bytes__` | Same as `bytes()`. |
| `__int__` | 128-bit integer value. |
| `__hash__` | Hashable (usable as dict key / set member). |
| `__eq__`, `__lt__`, etc. | Full rich comparison support. |

### Serialization

| Method | Description |
|---|---|
| `marshal_binary()` | Raw 16-byte data. |
| `marshal_text()` | 26-byte ASCII encoded string. |
| `marshal_json()` | JSON-encoded quoted string. |
| `ULID.unmarshal_binary(data)` | Parse from 16 bytes. |
| `ULID.unmarshal_text(data)` | Parse from 26-char string/bytes. |
| `ULID.unmarshal_json(data)` | Parse from JSON string. |

### Time Helpers

| Function | Description |
|---|---|
| `now()` | Current UTC Unix milliseconds. |
| `timestamp(dt)` | Convert `datetime` to Unix ms. |
| `time(ms)` | Convert Unix ms to `datetime`. |
| `max_time()` | Maximum encodable timestamp (year 10889). |

### Entropy

| Function | Description |
|---|---|
| `default_entropy()` | Process-global thread-safe monotonic entropy (`os.urandom`). |
| `monotonic(r, inc)` | Create a monotonic entropy source wrapping any callable. |

### Generator

| Function/Method | Description |
|---|---|
| `new_generator(*opts)` | Create a generator with options. |
| `with_node_id(id)` | Embed a 16-bit node ID for distributed uniqueness. |
| `with_entropy(r)` | Use a custom entropy source. |
| `with_prefix(p)` | Set a default prefix. |
| `gen.make()` | Generate a ULID. Thread-safe. |
| `gen.make_prefixed(p)` | Generate a prefixed ULID string. |
| `gen.new(ms)` | Generate with explicit timestamp. |
| `gen.node_id()` | Get `(node_id, has_node)`. |

## Benchmarks

Measured with `pytest-benchmark` on Python 3.14 (GitHub Actions runner). Pure Python, no C extensions.

| Operation | Median | Throughput |
|---|---|---|
| `marshal_binary()` | 93 ns | 10.7M ops/sec |
| `compare()` | 122 ns | 8.1M ops/sec |
| `now()` | 201 ns | 4.9M ops/sec |
| `new()` (crypto entropy) | 2.6 µs | 372K ops/sec |
| `string()` | 3.1 µs | 320K ops/sec |
| `parse()` | 3.7 µs | 260K ops/sec |
| `parse_strict()` | 5.0 µs | 198K ops/sec |
| `make()` | 5.5 µs | 180K ops/sec |
| `new_generator().make()` | 5.5 µs | 180K ops/sec |
| `new_generator().make_prefixed()` | 9.3 µs | 106K ops/sec |

Run benchmarks locally:

```sh
hatch run bench
```

## Contributing

If you have a suggestion that would make this better, please fork the repo and create a pull request. You can also simply open an issue with the tag "enhancement".
Don't forget to give the project a star! Thanks again!

1. Fork the Project
2. Create your Feature Branch (`git checkout -b gh-username/my-amazing-feature`)
3. Commit your Changes (`git commit -m 'Add my amazing feature'`)
4. Push to the Branch (`git push origin gh-username/my-amazing-feature`)
5. Open a Pull Request

## License

MIT. See [LICENSE](LICENSE).
