// Helper types for proxy-internal bookkeeping
type tPending = (isWrite: bool, key: int, value: int, podId: int, reqId: int, caller: machine);
type tInFlight = (isWrite: bool, key: int, podId: int, reqId: int, caller: machine);

// CacheNode <-> StorageProxy request/response events
event eProxyReadReq: (key: int, podId: int, reqId: int, caller: machine);
event eProxyWriteReq: (key: int, value: int, podId: int, reqId: int, caller: machine);
event eProxyReadResp: (reqId: int, key: int, value: int);
event eProxyWriteResp: (reqId: int, key: int, success: bool, value: int);

// Internal tick to drive proxy forwarding/holding
event eTick;

machine StorageProxy {
    var db: machine;
    var q: seq[tPending];
    var inflight: map[int, tInFlight];

    start state Init {
        entry (p: (db: machine)) {
            db = p.db;
            q = default(seq[tPending]);
            inflight = default(map[int, tInFlight]);
            goto Ready;
        }
    }

    state Ready {
        on eProxyReadReq do (r: (key: int, podId: int, reqId: int, caller: machine)) {
            var pend: tPending;
            pend = (isWrite = false, key = r.key, value = 0, podId = r.podId, reqId = r.reqId, caller = r.caller);
            q += (sizeof(q), pend);
            announce eMonitorProxyEnqueue, (key = r.key, podId = r.podId, isWrite = false, pending = sizeof(q));
            send this, eTick;
        }

        on eProxyWriteReq do (w: (key: int, value: int, podId: int, reqId: int, caller: machine)) {
            var pend: tPending;
            pend = (isWrite = true, key = w.key, value = w.value, podId = w.podId, reqId = w.reqId, caller = w.caller);
            q += (sizeof(q), pend);
            announce eMonitorProxyEnqueue, (key = w.key, podId = w.podId, isWrite = true, pending = sizeof(q));
            send this, eTick;
        }

        on eTick do {
            HandleTick();
        }

        on eStorageReadResp do (resp: (key: int, value: int)) {
            var f: tInFlight;
            assert resp.key in inflight, "StorageProxy received read resp for unknown key";
            f = inflight[resp.key];
            send f.caller, eProxyReadResp, (reqId = f.reqId, key = resp.key, value = resp.value);
            announce eMonitorProxyResponseDelivered, (key = f.key, podId = f.podId, isWrite = false);
            inflight -= (resp.key);
            if (sizeof(q) > 0) {
                send this, eTick;
            }
        }

        on eStorageWriteResp do (resp: (key: int, success: bool, value: int)) {
            var f: tInFlight;
            assert resp.key in inflight, "StorageProxy received write resp for unknown key";
            f = inflight[resp.key];
            send f.caller, eProxyWriteResp, (reqId = f.reqId, key = resp.key, success = resp.success, value = resp.value);
            announce eMonitorProxyResponseDelivered, (key = f.key, podId = f.podId, isWrite = true);
            inflight -= (resp.key);
            if (sizeof(q) > 0) {
                send this, eTick;
            }
        }
    }

    fun HandleTick() {
        var n: int;
        var idx: int;
        var tries: int;
        var found: bool;
        var item: tPending;
        var f: tInFlight;

        n = sizeof(q);
        if (n == 0) {
            return;
        }

        if ($) {
            tries = 0;
            found = false;
            while (tries < n) {
                idx = choose(n);
                if (!(q[idx].key in inflight)) {
                    found = true;
                    break;
                }
                tries = tries + 1;
            }

            if (!found) {
                announce eMonitorProxyHold, (pending = n);
                send this, eTick;
                return;
            }

            item = q[idx];
            q -= (idx);

            f = (isWrite = item.isWrite, key = item.key, podId = item.podId, reqId = item.reqId, caller = item.caller);
            inflight[item.key] = f;

            announce eMonitorProxyForward, (key = item.key, podId = item.podId, isWrite = item.isWrite, pending = sizeof(q));

            if (item.isWrite) {
                send db, eStorageWrite, (caller = this, key = item.key, value = item.value, podId = item.podId);
            } else {
                send db, eStorageRead, (caller = this, key = item.key, podId = item.podId);
            }
        } else {
            announce eMonitorProxyHold, (pending = n);
            send this, eTick;
        }
    }
}

machine CacheNode {
    var proxy: machine;
    var podId: int;
    var nextReqId: int;
    var clientByReq: map[int, machine];

    start state Init {
        entry (p: (proxy: machine, podId: int)) {
            proxy = p.proxy;
            podId = p.podId;
            nextReqId = 1;
            clientByReq = default(map[int, machine]);
            goto Ready;
        }
    }

    state Ready {
        on eClientRead do (r: (client: machine, key: int)) {
            var reqId: int;
            reqId = nextReqId;
            nextReqId = nextReqId + 1;
            clientByReq[reqId] = r.client;

            announce eMonitorProxyRequestIssued, (key = r.key, podId = podId, isWrite = false);
            send proxy, eProxyReadReq, (key = r.key, podId = podId, reqId = reqId, caller = this);
        }

        on eClientWrite do (w: (client: machine, key: int, value: int)) {
            var reqId: int;
            reqId = nextReqId;
            nextReqId = nextReqId + 1;
            clientByReq[reqId] = w.client;

            announce eMonitorProxyRequestIssued, (key = w.key, podId = podId, isWrite = true);
            send proxy, eProxyWriteReq, (key = w.key, value = w.value, podId = podId, reqId = reqId, caller = this);
        }

        on eProxyReadResp do (resp: (reqId: int, key: int, value: int)) {
            var c: machine;
            assert resp.reqId in clientByReq, "Unknown reqId in read response at CacheNode";
            c = clientByReq[resp.reqId];
            clientByReq -= (resp.reqId);
            send c, eReadResp, (key = resp.key, value = resp.value, fromCache = false);
        }

        on eProxyWriteResp do (resp: (reqId: int, key: int, success: bool, value: int)) {
            var c: machine;
            assert resp.reqId in clientByReq, "Unknown reqId in write response at CacheNode";
            c = clientByReq[resp.reqId];
            clientByReq -= (resp.reqId);
            send c, eWriteResp, (key = resp.key, success = resp.success);
        }
    }
}