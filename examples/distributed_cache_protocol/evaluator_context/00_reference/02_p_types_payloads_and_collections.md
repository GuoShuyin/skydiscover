P types, payloads, and collection patterns
==========================================

Use these patterns when constructing protocol state and responses.

Common types
------------

```p
type tKey = int;
type tValue = int;
type tReadReq = (key: int, requester: machine);
type tReadResp = (key: int, value: int, touchedStorage: bool);
type tWriteReq = (key: int, value: int, requester: machine);
```

Built-in families:

- primitive: `int`, `bool`, `float`, `string`, `event`, `machine`
- record:
  - tuple: `(int, bool, int)`
  - named tuple: `(key: int, value: int, touchedStorage: bool)`
- collections:
  - `map[K, V]`
  - `seq[T]`
  - `set[T]`

Named tuple rule
----------------

If a field type is a named tuple, construct it with field names.

Correct:

```p
var resp: (key: int, value: int, touchedStorage: bool);
resp = (key = k, value = v, touchedStorage = false);
```

Incorrect:

```p
resp = (k, v, false); // wrong type: plain tuple, not named tuple
```

Important: tuple and named tuple types are different in P.

Map, set, and sequence patterns
-------------------------------

```p
var kv: map[int, int];
var pending: set[int];
var log: seq[int];
var key: int;

kv[3] = 7;
kv += (4, 8);
kv -= (3);

pending += (10);
pending -= (10);

log += (0, 11);
log += (sizeof(log), 12);
log -= (0);

foreach(key in keys(kv)) {
    print format("key {0} -> {1}", key, kv[key]);
}
```

Useful operations
-----------------

- `sizeof(x)` for collection size
- `x in s` for membership
- `keys(m)` to iterate over map keys
- `values(m)` exists, but `keys(m)` is often clearer in protocol code
- `default(T)` to reset to type defaults

Default values
--------------

- `int` -> `0`
- `bool` -> `false`
- `machine` -> `null`
- `map`, `seq`, `set` -> empty collection
- tuple / named tuple -> each field gets its own default

Example:

```p
var cache: map[int, int];
var last: (key: int, value: int, touchedStorage: bool);

cache = default(map[int, int]);
last = default((key: int, value: int, touchedStorage: bool));
```

Constructor payload pattern
---------------------------

When using `new MachineName(payload)`, pass a single value. If the payload itself is a named tuple, wrap it as a single tuple literal.

Correct:

```p
new CacheNode((db = storage, peer = other));
```

Incorrect:

```p
new CacheNode(db = storage, peer = other); // parse error
```
