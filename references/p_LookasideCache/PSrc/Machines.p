// Bug: in the window between a direct write and the next TTL refresh, the
// shared cache serves a stale value -> LSI violation.

// Client <-> Cache (reads only)
event eRead:     (client: machine, key: int);
event eReadResp: (key: int, value: int);

// Client <-> TiDB (writes bypass the cache entirely)
event eWrite:     (client: machine, key: int, value: int);
event eWriteResp: (key: int, success: bool);

// Cache <-> TiDB: cache-miss fetch
event eDbRead:     (lc: machine, key: int);
event eDbReadResp: (key: int, value: int);

// Cache <-> TiDB: TTL-triggered proactive refresh
event eDbRefresh:     (lc: machine, key: int);
event eDbRefreshResp: (key: int, value: int);


// Monitor events (observed by LSISafety spec)
event eMonitorDbWrite:  (key: int, value: int);
event eMonitorCacheHit: (key: int, value: int, podId: int);

machine SimpleTiDB {
    var dbStore: map[int, int];

    start state Ready {
        on eWrite do (req: (client: machine, key: int, value: int)) {
            dbStore[req.key] = req.value;
            announce eMonitorDbWrite, (key = req.key, value = req.value);
            send req.client, eWriteResp, (key = req.key, success = true);
        }

        on eDbRead do (req: (lc: machine, key: int)) {
            var val: int;
            val = 0;
            if (req.key in dbStore) { val = dbStore[req.key]; }
            send req.lc, eDbReadResp, (key = req.key, value = val);
        }

        on eDbRefresh do (req: (lc: machine, key: int)) {
            var val: int;
            val = 0;
            if (req.key in dbStore) { val = dbStore[req.key]; }
            send req.lc, eDbRefreshResp, (key = req.key, value = val);
        }
    }
}

// Single shared lookaside cache used by all clients.
machine LookasideCache {
    var db: machine;

    var localCache:         map[int, int];
    var pendingReadClients: map[int, seq[machine]]; // key -> clients waiting on miss
    var refreshingKeys:     set[int];               // keys with TTL refresh in flight

    start state Init {
        entry (p: (db: machine)) {
            db = p.db;
            goto Ready;
        }
    }

    state Ready {
        on eRead do (req: (client: machine, key: int)) {
            if (req.key in localCache) {
                // Cache hit -- may be stale if a client wrote the key directly!
                announce eMonitorCacheHit,
                    (key = req.key, value = localCache[req.key], podId = 0);
                send req.client, eReadResp, (key = req.key, value = localCache[req.key]);
            } else if (req.key in pendingReadClients) {
                // Another client already triggered a miss for this key; queue up
                pendingReadClients[req.key] += (sizeof(pendingReadClients[req.key]), req.client);
            } else {
                // First miss: forward to TiDB
                pendingReadClients[req.key] = default(seq[machine]);
                pendingReadClients[req.key] += (0, req.client);
                send db, eDbRead, (lc = this, key = req.key);
            }
        }

        on eDbReadResp do (resp: (key: int, value: int)) {
            var i: int;
            var k: int;
            var cacheKeys: seq[int];
            localCache[resp.key] = resp.value;
            i = 0;
            while (i < sizeof(pendingReadClients[resp.key])) {
                send pendingReadClients[resp.key][i], eReadResp,
                    (key = resp.key, value = resp.value);
                i = i + 1;
            }
            pendingReadClients -= (resp.key);
            // Nondeterministically trigger TTL refresh inline so it runs in the
            // same scheduling step — self-send would queue the event and risk
            // being skipped if the schedule ends before LookasideCache runs again
            if ($) {
                cacheKeys = keys(localCache);
                foreach (k in cacheKeys) {
                    if (!(k in refreshingKeys)) {
                        refreshingKeys += (k);
                        send db, eDbRefresh, (lc = this, key = k);
                    }
                }
            }
        }

        // TTL refresh response: update the cached value in place
        on eDbRefreshResp do (resp: (key: int, value: int)) {
            localCache[resp.key] = resp.value;
            refreshingKeys -= (resp.key);
        }
    }
}
