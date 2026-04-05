/*
P-style seed program for workload-adaptive storage systems.

This seed intentionally starts from only two baseline systems:
1. DirectReadWriteSystem
2. LookasideCacheSystem

These are only starting points for exploration.
Future evolved programs may keep them, delete them, merge them, or replace them.
The best design is allowed to have no cache at all.
But the full evolved P-style program should still contain an explicit client
role and an explicit database/backing-store role.

Future evolved programs should still look like complete P programs, even if
they contain syntax errors. The evaluator only scores the DESIGN block.

LSI violation rule:
- if a client is served a value for key K that is NOT equal to the database's
  current value for key K at that exact moment, that read is an LSI violation.
*/

// Shared client/storage events
event eRead:      (client: machine, key: int, podId: int);
event eReadResp:  (key: int, value: int, podId: int);
event eWrite:     (client: machine, key: int, value: int, podId: int);
event eWriteResp: (key: int, success: bool, podId: int);

// Lookaside-cache internal DB events
event eDbRead:        (lc: machine, key: int, podId: int);
event eDbReadResp:    (key: int, value: int, podId: int);
event eDbRefresh:     (lc: machine, key: int, podId: int);
event eDbRefreshResp: (key: int, value: int, podId: int);

// Monitor events
event eMonitorDbWrite:    (key: int, value: int);
event eMonitorDirectRead: (key: int, value: int, podId: int);
event eMonitorCacheHit:   (key: int, value: int, podId: int);

// ---------------------------------------------------------------------------
// Authoritative database used by both baseline systems.
// ---------------------------------------------------------------------------
machine SimpleTiDB {
    var dbStore: map[int, int];

    start state Ready {
        on eRead do (req: (client: machine, key: int, podId: int)) {
            var val: int;
            val = 0;
            if (req.key in dbStore) {
                val = dbStore[req.key];
            }
            announce eMonitorDirectRead, (key = req.key, value = val, podId = req.podId);
            send req.client, eReadResp, (key = req.key, value = val, podId = req.podId);
        }

        on eWrite do (req: (client: machine, key: int, value: int, podId: int)) {
            dbStore[req.key] = req.value;
            announce eMonitorDbWrite, (key = req.key, value = req.value);
            send req.client, eWriteResp, (key = req.key, success = true, podId = req.podId);
        }

        on eDbRead do (req: (lc: machine, key: int, podId: int)) {
            var val2: int;
            val2 = 0;
            if (req.key in dbStore) {
                val2 = dbStore[req.key];
            }
            send req.lc, eDbReadResp, (key = req.key, value = val2, podId = req.podId);
        }

        on eDbRefresh do (req: (lc: machine, key: int, podId: int)) {
            var val3: int;
            val3 = 0;
            if (req.key in dbStore) {
                val3 = dbStore[req.key];
            }
            send req.lc, eDbRefreshResp, (key = req.key, value = val3, podId = req.podId);
        }
    }
}

// ---------------------------------------------------------------------------
// Baseline system 1: direct reads and writes against TiDB.
// This follows references/p_DirectTiDB/PSrc/Machines.p.
// ---------------------------------------------------------------------------
machine DirectReadWriteSystem {
    var db: machine;

    start state Init {
        entry (p: (db: machine)) {
            db = p.db;
            goto Ready;
        }
    }

    state Ready {
        on eRead do (req: (client: machine, key: int, podId: int)) {
            send db, eRead, req;
        }

        on eWrite do (req: (client: machine, key: int, value: int, podId: int)) {
            send db, eWrite, req;
        }
    }
}

// ---------------------------------------------------------------------------
// Baseline system 2: shared look-aside cache.
// Reads go through the cache first; writes still go to the database.
// This follows references/p_LookasideCache/PSrc/Machines.p.
// ---------------------------------------------------------------------------
machine LookasideCacheSystem {
    var db: machine;
    var localCache: map[int, int];
    var pendingReadClients: map[int, seq[machine]];
    var pendingReadPods: map[int, int];
    var refreshingKeys: set[int];

    start state Init {
        entry (p: (db: machine)) {
            db = p.db;
            goto Ready;
        }
    }

    state Ready {
        on eRead do (req: (client: machine, key: int, podId: int)) {
            if (req.key in localCache) {
                announce eMonitorCacheHit, (key = req.key, value = localCache[req.key], podId = req.podId);
                send req.client, eReadResp, (key = req.key, value = localCache[req.key], podId = req.podId);
            } else if (req.key in pendingReadClients) {
                pendingReadClients[req.key] += (sizeof(pendingReadClients[req.key]), req.client);
            } else {
                pendingReadClients[req.key] = default(seq[machine]);
                pendingReadClients[req.key] += (0, req.client);
                pendingReadPods[req.key] = req.podId;
                send db, eDbRead, (lc = this, key = req.key, podId = req.podId);
            }
        }

        on eWrite do (req: (client: machine, key: int, value: int, podId: int)) {
            // Baseline lookaside behavior: writes go directly to TiDB.
            // If the key is cached, this can create a stale window until the
            // next refresh or coherence action.
            send db, eWrite, req;
        }

        on eDbReadResp do (resp: (key: int, value: int, podId: int)) {
            var i: int;
            var k: int;
            var cacheKeys: seq[int];
            localCache[resp.key] = resp.value;
            i = 0;
            while (i < sizeof(pendingReadClients[resp.key])) {
                send pendingReadClients[resp.key][i], eReadResp,
                    (key = resp.key, value = resp.value, podId = pendingReadPods[resp.key]);
                i = i + 1;
            }
            pendingReadClients -= (resp.key);
            pendingReadPods -= (resp.key);

            if ($) {
                cacheKeys = keys(localCache);
                foreach (k in cacheKeys) {
                    if (!(k in refreshingKeys)) {
                        refreshingKeys += (k);
                        send db, eDbRefresh, (lc = this, key = k, podId = 0);
                    }
                }
            }
        }

        on eDbRefreshResp do (resp: (key: int, value: int, podId: int)) {
            localCache[resp.key] = resp.value;
            refreshingKeys -= (resp.key);
        }
    }

    // DESIGN-START

    authoritative db : authoritative_db {
        doc = "authoritative TiDB backing store and source of truth";
        stores_values = true;
        serves_reads = true;
        capacity = INF;
    }

    device lookaside_cache : cache {
        doc = "shared look-aside cache for hot read keys";
        stores_values = true;
        serves_reads = true;
        capacity = cache_capacity;
    }

    param read_order = [lookaside_cache, db];
    param scan_window = 16;
    param hot_read_threshold = 2;
    param hot_write_threshold = 2;

    // Seed a safe baseline instead of the stale buggy variant:
    // writes update the cache if the key is already cached.
    // Future evolved designs may delete this cache entirely and use a very
    // different architecture if that performs better.
    param write_update_if_cached = [lookaside_cache];
    param write_update_targets = [];
    param write_update_min_score = 999;
    param write_update_max_scan_ratio = 0.85;

    param promote_target = lookaside_cache;
    param promote_min_reads = 2;
    param promote_min_writes = 0;
    param promote_max_scan_ratio = 0.85;

    param write_stage_target = "";
    param write_stage_min_writes = 999;
    param write_stage_max_scan_ratio = 0.95;

    param write_invalidate_on_scan = [];
    param write_invalidate_scan_cutoff = 1.0;
    param write_invalidate_cold_targets = [];
    param write_invalidate_cold_score = 0;

    // DESIGN-END
}

machine Main {
    start state Boot {
        entry {
            var db: machine;
            var directSystem: machine;
            var lookasideSystem: machine;

            db = new SimpleTiDB();
            directSystem = new DirectReadWriteSystem((db = db));
            lookasideSystem = new LookasideCacheSystem((db = db));

            // Future evolved programs may keep, delete, or replace these two
            // baselines. The search space is not restricted to cache-based
            // systems.
        }
    }
}
