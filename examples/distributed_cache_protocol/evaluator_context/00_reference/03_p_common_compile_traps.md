Common P compile traps seen in synthesis
========================================

These mistakes repeatedly cause parser or type-checker failures.
Avoid them exactly.

1. Do not invent new statement forms
------------------------------------

Do not use unsupported constructs such as:

- `action ...`
- `const ...`
- ad-hoc syntax copied from another language

Stay inside the normal P forms:

- `var`
- `fun`
- `state`
- `entry`
- `exit`
- `on ... do`
- `on ... goto`
- `send`
- `raise`
- `goto`
- `if`
- `while`
- `foreach`
- `assert`
- `return`

2. Local `var` declarations must come first
-------------------------------------------

Inside `fun`, `entry`, `exit`, and anonymous handlers, declare all locals before statements.

Correct:

```p
entry {
    var hit: bool;
    hit = false;
}
```

Incorrect:

```p
entry {
    hit = false;
    var hit: bool; // invalid
}
```

3. Do not redeclare fixed benchmark symbols
-------------------------------------------

If the environment already defines an `event` or `type`, do not define it again in the candidate.

Bad:

```p
event eClientRead; // duplicates hidden declaration
```

4. Match named-tuple field names exactly
----------------------------------------

If the expected type is:

```p
(key: int, value: int, touchedStorage: bool)
```

then return:

```p
(key = k, value = v, touchedStorage = true)
```

not:

```p
(k, v, true)
```

5. Constructor calls take one payload value
-------------------------------------------

If a machine constructor needs multiple pieces of data, package them into one tuple.

Correct:

```p
new StorageProxy((db = dbRef, peer = cacheRef));
```

Incorrect:

```p
new StorageProxy(db = dbRef, peer = cacheRef);
```

6. Prefer small handlers plus helper functions
----------------------------------------------

Large anonymous handlers tend to drift into syntax errors.
Safer style:

```p
on eRead do HandleRead;

fun HandleRead(req: tReadReq) {
    var resp: tReadResp;
    ...
}
```

7. Keep the protocol simple before optimizing
---------------------------------------------

First goal:

- compile
- satisfy safety

Only after that, optimize:

- cache hits
- fewer storage round trips
- fewer control messages
