// Helper types and events for internal bookkeeping
type tProxyReq = (key: int, isWrite: bool, podId: int, caller: machine, value: int, reqId: int);
type tWriteReqEntry = (client: machine, value: int);
event eProxyTick;

machine StorageProxy {
    var db: machine;
    var queue: seq[tProxyReq];
    var inflightByKey: map[int, tProxyReq];
    var nextReqId: int;

    start state Init {
        entry (p: (db: machine)) {
            db = p.db;
            queue = default(seq[tProxyReq]);
            inflightByKey = default(map[int, tProxyReq]);
            nextReqId = 1;
            goto Ready;
        }
    }

    state Ready {
        on eStorageRead do (req: (caller: machine, key: int, podId: int)) {
            var item: tProxyReq;
            var pending: int;
            item = (key = req.key, isWrite = false, podId = req.podId, caller = req.caller, value = 0, reqId = nextReqId);
            nextReqId = nextReqId + 1;
            announce eMonitorProxyRequestIssued, (key = req.key, podId = req.podId, isWrite = false);
            queue += (sizeof(queue), item);
            pending = sizeof(queue);
            announce eMonitorProxyEnqueue, (key = req.key, podId = req.podId, isWrite = false, pending = pending);
            send this, eProxyTick;
        }

        on eStorageWrite do (req: (caller: machine, key: int, value: int, podId: int)) {
            var item: tProxyReq;
            var pending: int;
            item = (key = req.key, isWrite = true, podId = req.podId, caller = req.caller, value = req.value, reqId = nextReqId);
            nextReqId = nextReqId + 1;
            announce eMonitorProxyRequestIssued, (key = req.key, podId = req.podId, isWrite = true);
            queue += (sizeof(queue), item);
            pending = sizeof(queue);
            announce eMonitorProxyEnqueue, (key = req.key, podId = req.podId, isWrite = true, pending = pending);
            send this, eProxyTick;
        }

        on eProxyTick do {
            var n: int;
            var c: int;
            var idx: int;
            var item: tProxyReq;
            n = sizeof(queue);
            if (n == 0) {
                return;
            }
            // Non-deterministically hold or forward one queued request
            c = choose(2);
            if (c == 0) {
                announce eMonitorProxyHold, (pending = n);
                // schedule another chance to forward later
                send this, eProxyTick;
                return;
            }

            // pick a queued request in a non-deterministic order
            idx = choose(n);
            item = queue[idx];
            queue -= (idx);

            // serialize per-key through the proxy
            assert !(item.key in inflightByKey), "Proxy should not have multiple inflight ops per key";
            inflightByKey[item.key] = item;

            announce eMonitorProxyForward, (key = item.key, podId = item.podId, isWrite = item.isWrite, pending = sizeof(queue));

            if (item.isWrite) {
                send db, eStorageWrite, (caller = this, key = item.key, value = item.value, podId = item.podId);
            } else {
                send db, eStorageRead, (caller = this, key = item.key, podId = item.podId);
            }
        }

        on eStorageReadResp do (resp: (key: int, value: int)) {
            var item: tProxyReq;
            assert resp.key in inflightByKey, "Read response for a key with no inflight request";
            item = inflightByKey[resp.key];
            inflightByKey -= (resp.key);
            // deliver back to original caller
            send item.caller, eStorageReadResp, (key = resp.key, value = resp.value);
            announce eMonitorProxyResponseDelivered, (key = resp.key, podId = item.podId, isWrite = false);
            // try to make progress on the queue
            send this, eProxyTick;
        }

        on eStorageWriteResp do (resp: (key: int, success: bool, value: int)) {
            var item: tProxyReq;
            assert resp.key in inflightByKey, "Write response for a key with no inflight request";
            item = inflightByKey[resp.key];
            inflightByKey -= (resp.key);
            // deliver back to original caller
            send item.caller, eStorageWriteResp, (key = resp.key, success = resp.success, value = resp.value);
            announce eMonitorProxyResponseDelivered, (key = resp.key, podId = item.podId, isWrite = true);
            // try to make progress on the queue
            send this, eProxyTick;
        }
    }
}

machine CacheNode {
    var proxy: machine;
    var podId: int;

    // Read single-flight and waiting sets
    var inflightReadKeys: set[int];
    var readsWait: map[int, seq[machine]];
    // Reads that await the completion of an inflight write for the same key
    var readsWaitingOnWrite: map[int, seq[machine]];

    // Write serialization per key
    var inflightWriteKeys: set[int];
    var inflightWriteClient: map[int, machine];
    var inflightWriteValue: map[int, int];
    var writesWait: map[int, seq[tWriteReqEntry]];

    start state Init {
        entry (p: (proxy: machine, podId: int)) {
            proxy = p.proxy;
            podId = p.podId;

            inflightReadKeys = default(set[int]);
            readsWait = default(map[int, seq[machine]]);
            readsWaitingOnWrite = default(map[int, seq[machine]]);

            inflightWriteKeys = default(set[int]);
            inflightWriteClient = default(map[int, machine]);
            inflightWriteValue = default(map[int, int]);
            writesWait = default(map[int, seq[tWriteReqEntry]]);
            goto Ready;
        }
    }

    state Ready {
        on eClientRead do (req: (client: machine, key: int)) { HandleClientRead(req); }
        on eClientWrite do (req: (client: machine, key: int, value: int)) { HandleClientWrite(req); }

        on eStorageReadResp do (resp: (key: int, value: int)) { OnStorageReadResp(resp); }
        on eStorageWriteResp do (resp: (key: int, success: bool, value: int)) { OnStorageWriteResp(resp); }
    }

    fun HandleClientRead(req: (client: machine, key: int)) {
        var lst: seq[machine];
        var lst2: seq[machine];

        // If a write to this key is inflight, piggyback the read on the write's completion to save a round trip.
        if (req.key in inflightWriteKeys) {
            if (req.key in readsWaitingOnWrite) {
                lst2 = readsWaitingOnWrite[req.key];
            } else {
                lst2 = default(seq[machine]);
            }
            lst2 += (sizeof(lst2), req.client);
            readsWaitingOnWrite[req.key] = lst2;
            return;
        }

        // If a read for this key is already inflight, just wait for it.
        if (req.key in inflightReadKeys) {
            lst = readsWait[req.key];
            lst += (sizeof(lst), req.client);
            readsWait[req.key] = lst;
            return;
        }

        // Start a new storage read via proxy.
        inflightReadKeys += (req.key);
        if (req.key in readsWait) {
            lst = readsWait[req.key];
        } else {
            lst = default(seq[machine]);
        }
        lst += (sizeof(lst), req.client);
        readsWait[req.key] = lst;

        send proxy, eStorageRead, (caller = this, key = req.key, podId = podId);
    }

    fun HandleClientWrite(req: (client: machine, key: int, value: int)) {
        var q: seq[tWriteReqEntry];
        var entry: tWriteReqEntry;

        entry = (client = req.client, value = req.value);

        if (req.key in writesWait) {
            q = writesWait[req.key];
        } else {
            q = default(seq[tWriteReqEntry]);
        }
        q += (sizeof(q), entry);
        writesWait[req.key] = q;

        // If no write is inflight for this key, issue the head-of-line write.
        if (!(req.key in inflightWriteKeys)) {
            IssueNextWrite(req.key);
        }
    }

    fun IssueNextWrite(key: int) {
        var q: seq[tWriteReqEntry];
        var head: tWriteReqEntry;

        if (!(key in writesWait)) {
            return;
        }
        q = writesWait[key];
        if (sizeof(q) == 0) {
            return;
        }

        head = q[0];
        q -= (0);
        writesWait[key] = q;

        inflightWriteKeys += (key);
        inflightWriteClient[key] = head.client;
        inflightWriteValue[key] = head.value;

        send proxy, eStorageWrite, (caller = this, key = key, value = head.value, podId = podId);
    }

    fun OnStorageReadResp(resp: (key: int, value: int)) {
        var lst: seq[machine];
        var i: int;

        assert resp.key in inflightReadKeys, "Unexpected read response with no inflight read";
        inflightReadKeys -= (resp.key);

        lst = readsWait[resp.key];
        i = 0;
        while (i < sizeof(lst)) {
            send lst[i], eReadResp, (key = resp.key, value = resp.value, fromCache = false);
            i = i + 1;
        }
        readsWait -= (resp.key);
    }

    fun OnStorageWriteResp(resp: (key: int, success: bool, value: int)) {
        var client: machine;
        var lst: seq[machine];
        var i: int;

        assert resp.key in inflightWriteKeys, "Unexpected write response with no inflight write";
        client = inflightWriteClient[resp.key];

        // Respond to the write client
        send client, eWriteResp, (key = resp.key, success = resp.success);

        // Any reads that were waiting on this write can be served now using the committed value.
        if (resp.key in readsWaitingOnWrite) {
            lst = readsWaitingOnWrite[resp.key];
            i = 0;
            while (i < sizeof(lst)) {
                send lst[i], eReadResp, (key = resp.key, value = resp.value, fromCache = false);
                i = i + 1;
            }
            readsWaitingOnWrite -= (resp.key);
        }

        inflightWriteKeys -= (resp.key);
        inflightWriteClient -= (resp.key);
        inflightWriteValue -= (resp.key);

        // Issue the next pending write for this key, if any.
        IssueNextWrite(resp.key);
    }
}