// Minimal seed for SkyDiscover: naive storage-backed cache with simple ownership handling.
// Machine names and event shapes are kept compatible with the fixed evaluator-owned harness.

type tKeyRange = (low: int, high: int);
type tDbWriteReq = (caller: machine, key: int, value: int, epochId: int, rangeLow: int);
type tPendingWrite = (client: machine);

event eClientRead: (client: machine, key: int);
event eClientWrite: (client: machine, key: int, value: int);
event eDbRead: (caller: machine, key: int);
event eDbWrite: tDbWriteReq;
event eSetEpoch: (caller: machine, range: tKeyRange, epochId: int);
event eDbReadResp: (key: int, value: int);
event eDbWriteResp: (key: int, success: bool, value: int);
event eSetEpochDone: (rangeLow: int, status: int);
event eReadResp: (key: int, value: int, fromCache: bool);
event eWriteResp: (key: int, success: bool);
event eOwnershipGrant: (range: tKeyRange, sliceHandle: int);
event eOwnershipRevoke: (range: tKeyRange, sliceHandle: int, ackTo: machine);
event eOwnershipRevokeAck: (range: tKeyRange, sliceHandle: int);
event eOwnershipTransferDone: (rangeLow: int, sliceHandle: int);
event eRequestOwnershipGrant: (pod: machine, range: tKeyRange, sliceHandle: int);
event eRequestOwnershipRevoke: (pod: machine, range: tKeyRange, sliceHandle: int, requester: machine);
event ePodRestart;
event eTabletRestart;
event eGetSplitPoints: (caller: machine, range: tKeyRange);
event eGetSplitPointsResp: (subRanges: seq[tKeyRange]);
event eTabletSplit: int;
event eMonitorDbWrite: (key: int, value: int);
event eMonitorCacheHit: (key: int, value: int, podId: int);

machine AutoSharder {
    var pendingRevokeRequesters: map[int, machine];

    start state Ready {
        entry {
            pendingRevokeRequesters = default(map[int, machine]);
        }

        on eRequestOwnershipGrant do (req: (pod: machine, range: tKeyRange, sliceHandle: int)) {
            send req.pod, eOwnershipGrant, (range = req.range, sliceHandle = req.sliceHandle);
        }

        on eRequestOwnershipRevoke do (req: (pod: machine, range: tKeyRange, sliceHandle: int, requester: machine)) {
            pendingRevokeRequesters[req.range.low] = req.requester;
            send req.pod, eOwnershipRevoke, (range = req.range, sliceHandle = req.sliceHandle, ackTo = this);
        }

        on eOwnershipRevokeAck do (resp: (range: tKeyRange, sliceHandle: int)) {
            var requester: machine;
            if (resp.range.low in pendingRevokeRequesters) {
                requester = pendingRevokeRequesters[resp.range.low];
                pendingRevokeRequesters -= (resp.range.low);
                send requester, eOwnershipTransferDone, (rangeLow = resp.range.low, sliceHandle = resp.sliceHandle);
            }
        }
    }
}

machine TiDB {
    var dbStore: map[int, int];

    start state Ready {
        on eDbRead do (req: (caller: machine, key: int)) {
            var val: int;
            val = 0;
            if (req.key in dbStore) {
                val = dbStore[req.key];
            }
            send req.caller, eDbReadResp, (key = req.key, value = val);
        }

        on eDbWrite do (req: tDbWriteReq) {
            dbStore[req.key] = req.value;
            announce eMonitorDbWrite, (key = req.key, value = req.value);
            send req.caller, eDbWriteResp, (key = req.key, success = true, value = req.value);
        }

        on eGetSplitPoints do (req: (caller: machine, range: tKeyRange)) {
            var subRanges: seq[tKeyRange];
            subRanges = default(seq[tKeyRange]);
            subRanges += (sizeof(subRanges), req.range);
            send req.caller, eGetSplitPointsResp, (subRanges = subRanges, );
        }

        on eSetEpoch do (req: (caller: machine, range: tKeyRange, epochId: int)) {
            send req.caller, eSetEpochDone, (rangeLow = req.range.low, status = 0);
        }

        on eTabletRestart do { }
        on eTabletSplit do (splitKey: int) { }
    }
}

machine NetworkProxy {
    var db: machine;

    start state Ready {
        entry (p: (db: machine)) {
            db = p.db;
        }

        on eDbRead do (req: (caller: machine, key: int)) {
            send db, eDbRead, req;
        }

        on eGetSplitPoints do (req: (caller: machine, range: tKeyRange)) {
            send db, eGetSplitPoints, req;
        }

        on eSetEpoch do (req: (caller: machine, range: tKeyRange, epochId: int)) {
            send db, eSetEpoch, req;
        }

        on eTabletRestart do {
            send db, eTabletRestart;
        }

        on eTabletSplit do (splitKey: int) {
            send db, eTabletSplit, splitKey;
        }

        on eDbWrite do (req: tDbWriteReq) {
            send db, eDbWrite, req;
        }
    }
}

machine CacheNode {
    var db: machine;
    var podId: int;
    var ownerEpoch: int;
    var cacheMap: map[int, int];
    var pendingReads: map[int, seq[machine]];
    var pendingWrites: map[int, seq[tPendingWrite]];

    start state Serving {
        entry (p: (db: machine, sharder: machine, podId: int)) {
            db = p.db;
            podId = p.podId;
            ownerEpoch = 0;
            cacheMap = default(map[int, int]);
            pendingReads = default(map[int, seq[machine]]);
            pendingWrites = default(map[int, seq[tPendingWrite]]);
        }

        on eOwnershipGrant do (req: (range: tKeyRange, sliceHandle: int)) {
            ownerEpoch = req.sliceHandle;
        }

        on eOwnershipRevoke do (req: (range: tKeyRange, sliceHandle: int, ackTo: machine)) {
            ownerEpoch = 0;
            send req.ackTo, eOwnershipRevokeAck, (range = req.range, sliceHandle = req.sliceHandle);
        }

        on eClientRead do (req: (client: machine, key: int)) {
            if (req.key in cacheMap) {
                announce eMonitorCacheHit, (key = req.key, value = cacheMap[req.key], podId = podId);
                send req.client, eReadResp, (key = req.key, value = cacheMap[req.key], fromCache = true);
                return;
            }
            if (!(req.key in pendingReads)) {
                pendingReads[req.key] = default(seq[machine]);
            }
            pendingReads[req.key] += (sizeof(pendingReads[req.key]), req.client);
            send db, eDbRead, (caller = this, key = req.key);
        }

        on eDbReadResp do (resp: (key: int, value: int)) {
            var clients: seq[machine];
            var client: machine;
            if (!(resp.key in pendingReads) || sizeof(pendingReads[resp.key]) == 0) {
                return;
            }
            clients = pendingReads[resp.key];
            client = clients[0];
            clients -= (0);
            if (sizeof(clients) == 0) {
                pendingReads -= (resp.key);
            } else {
                pendingReads[resp.key] = clients;
            }
            cacheMap[resp.key] = resp.value;
            send client, eReadResp, (key = resp.key, value = resp.value, fromCache = false);
        }

        on eClientWrite do (req: (client: machine, key: int, value: int)) {
            var writeReq: tPendingWrite;
            cacheMap[req.key] = req.value;
            if (!(req.key in pendingWrites)) {
                pendingWrites[req.key] = default(seq[tPendingWrite]);
            }
            writeReq = (client = req.client, );
            pendingWrites[req.key] += (sizeof(pendingWrites[req.key]), writeReq);
            send db, eDbWrite, (caller = this, key = req.key, value = req.value, epochId = ownerEpoch, rangeLow = 40);
        }

        on eDbWriteResp do (resp: (key: int, success: bool, value: int)) {
            var writes: seq[tPendingWrite];
            var writeReq: tPendingWrite;
            if (!(resp.key in pendingWrites) || sizeof(pendingWrites[resp.key]) == 0) {
                return;
            }
            writes = pendingWrites[resp.key];
            writeReq = writes[0];
            writes -= (0);
            if (sizeof(writes) == 0) {
                pendingWrites -= (resp.key);
            } else {
                pendingWrites[resp.key] = writes;
            }
            if (resp.success) {
                cacheMap[resp.key] = resp.value;
            }
            send writeReq.client, eWriteResp, (key = resp.key, success = resp.success);
        }

        on ePodRestart do {
            cacheMap = default(map[int, int]);
            pendingReads = default(map[int, seq[machine]]);
            pendingWrites = default(map[int, seq[tPendingWrite]]);
            ownerEpoch = 0;
        }

        ignore eSetEpochDone, eGetSplitPointsResp;
    }
}
