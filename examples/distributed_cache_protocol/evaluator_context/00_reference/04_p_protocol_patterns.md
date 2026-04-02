Minimal protocol-writing patterns in P
======================================

The examples below are illustrative syntax patterns, not benchmark-specific declarations.

Pattern 1: request-response via async send
------------------------------------------

```p
machine ClientLike {
    var server: machine;

    start state Init {
        entry (s: machine) {
            server = s;
            send server, eReadReq, (key = 1, requester = this);
            goto Waiting;
        }
    }

    state Waiting {
        on eReadResp do (resp: (key: int, value: int, touchedStorage: bool)) {
            goto Done;
        }
    }

    state Done { }
}
```

Pattern 2: helper function updates a map
----------------------------------------

```p
fun Remember(key: int, value: int) {
    cache[key] = value;
}
```

Pattern 3: branch between cache hit and storage access
------------------------------------------------------

```p
fun HandleRead(req: tReadReq) {
    var resp: tReadResp;

    if (req.key in cache) {
        resp = (key = req.key, value = cache[req.key], touchedStorage = false);
        send req.requester, eReadResp, resp;
        return;
    }

    send storage, eStorageRead, req;
}
```

Pattern 4: state transition after an event
------------------------------------------

```p
state Idle {
    on eNeedRefresh goto Refreshing;
}

state Refreshing {
    entry {
        send storage, eRefreshReq;
    }

    on eRefreshDone goto Idle;
}
```

Pattern 5: use a helper instead of oversized inline logic
---------------------------------------------------------

```p
state Ready {
    on eWriteReq do HandleWrite;
}

fun HandleWrite(req: tWriteReq) {
    send storage, eStorageWrite, req;
}
```

High-level advice
-----------------

- Start from a tiny, obviously valid machine shape.
- Use named helper functions to keep handlers short.
- Prefer named tuples for protocol payloads.
- Only optimize after a simple direct-to-storage design compiles and passes safety.
