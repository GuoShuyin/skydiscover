// PSrc/Machines.p  (p_DirectTiDB)
// Baseline: clients talk directly to TiDB with no caching layer.
// LSI trivially holds because every read returns the latest committed value.

// Client <-> TiDB events
event eRead:  (client: machine, key: int);
event eWrite: (client: machine, key: int, value: int);
event eReadResp:  (key: int, value: int);
event eWriteResp: (key: int, success: bool);

// Monitor events (observed by LSISafety spec)
event eMonitorDbWrite:    (key: int, value: int);
event eMonitorDirectRead: (key: int, value: int);

// Simple linearizable KV store — no guards, no slice handles
machine SimpleTiDB {
    var dbStore: map[int, int];

    start state Ready {
        on eRead do (req: (client: machine, key: int)) {
            var val: int;
            val = 0;
            if (req.key in dbStore) { val = dbStore[req.key]; }
            announce eMonitorDirectRead, (key = req.key, value = val);
            send req.client, eReadResp, (key = req.key, value = val);
        }

        on eWrite do (req: (client: machine, key: int, value: int)) {
            dbStore[req.key] = req.value;
            announce eMonitorDbWrite, (key = req.key, value = req.value);
            send req.client, eWriteResp, (key = req.key, success = true);
        }
    }
}
