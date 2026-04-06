// Ownership-aware fixed harness for the look-aside cache benchmark.
// The evaluator injects the same world dynamically at scoring time; this
// checked-in file mirrors that world so the benchmark remains readable.

event eProxyTick;
event eHarnessTick;
event eClientDoRead: (key: int);
event eClientDoWrite: (key: int, value: int);
event eClientReadDone: (clientId: int, key: int, value: int, podId: int);
event eClientWriteDone: (clientId: int, key: int, success: bool, podId: int);
type tProxyWriteReq = (client: machine, key: int, value: int, podId: int);

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

machine NetworkProxy {
    var db: machine;
    var pendingWrites: seq[tProxyWriteReq];
    var tickArmed: bool;

    start state Ready {
        entry (p: (db: machine)) {
            db = p.db;
            pendingWrites = default(seq[tProxyWriteReq]);
            tickArmed = false;
        }

        on eRead do (req: (client: machine, key: int, podId: int)) {
            send db, eRead, req;
        }

        on eDbRead do (req: (lc: machine, key: int, podId: int)) {
            send db, eDbRead, req;
        }

        on eDbRefresh do (req: (lc: machine, key: int, podId: int)) {
            send db, eDbRefresh, req;
        }

        on eProxyControl do (req: tProxyControlReq) {
            send db, eProxyControl, req;
        }

        on eWrite do (req: (client: machine, key: int, value: int, podId: int)) {
            pendingWrites += (sizeof(pendingWrites), req);
            if (!tickArmed) {
                tickArmed = true;
                send this, eProxyTick;
            }
        }

        on eProxyTick do {
            var idx: int;
            var req: tProxyWriteReq;
            tickArmed = false;
            if (sizeof(pendingWrites) == 0) {
                return;
            }

            if ($) {
                idx = choose(sizeof(pendingWrites));
                req = pendingWrites[idx];
                pendingWrites -= (idx);
                send db, eWrite, req;
            }

            if (sizeof(pendingWrites) > 0 && !tickArmed) {
                tickArmed = true;
                send this, eProxyTick;
            }
        }
    }
}

machine ClientPod {
    var controller: machine;
    var system: machine;
    var podId: int;
    var clientId: int;

    start state Ready {
        entry (p: (controller: machine, system: machine, podId: int, clientId: int)) {
            controller = p.controller;
            system = p.system;
            podId = p.podId;
            clientId = p.clientId;
        }

        on eClientDoRead do (req: (key: int)) {
            send system, eRead, (client = this, key = req.key, podId = podId);
        }

        on eClientDoWrite do (req: (key: int, value: int)) {
            send system, eWrite, (client = this, key = req.key, value = req.value, podId = podId);
        }

        on eReadResp do (resp: (key: int, value: int, podId: int)) {
            send controller, eClientReadDone,
                (clientId = clientId, key = resp.key, value = resp.value, podId = resp.podId);
        }

        on eWriteResp do (resp: (key: int, success: bool, podId: int)) {
            send controller, eClientWriteDone,
                (clientId = clientId, key = resp.key, success = resp.success, podId = resp.podId);
        }
    }
}

machine CandidateWarmThenWriteDriver {
    var store: machine;
    var db: machine;
    var sharder: machine;
    var pod0: machine;
    var client0: machine;

    start state Init {
        entry {
            store = new SimpleTiDB();
            db = new NetworkProxy((db = store, ));
            sharder = new AutoSharder();
            pod0 = new LookasideCacheSystem((db = db, sharder = sharder, podId = 0));
            client0 = new ClientPod((controller = this, system = pod0, podId = 0, clientId = 0));
            send sharder, eRequestOwnershipGrant, (pod = pod0, range = (low = 40, high = 45), sliceHandle = 1);
            send client0, eClientDoRead, (key = 40, );
            goto AwaitWarmRead;
        }
    }

    state AwaitWarmRead {
        on eClientReadDone do (resp: (clientId: int, key: int, value: int, podId: int)) {
            send client0, eClientDoWrite, (key = 40, value = 11);
            goto AwaitWrite;
        }
    }

    state AwaitWrite {
        on eClientWriteDone do (resp: (clientId: int, key: int, success: bool, podId: int)) {
            send client0, eClientDoRead, (key = 40, );
            goto AwaitSecondRead;
        }
    }

    state AwaitSecondRead {
        on eClientReadDone do (resp: (clientId: int, key: int, value: int, podId: int)) {
            goto Done;
        }
    }

    state Done {
        ignore eClientReadDone, eClientWriteDone, eOwnershipTransferDone;
    }
}

machine CandidateMultiClientConflictDriver {
    var store: machine;
    var db: machine;
    var sharder: machine;
    var pod0: machine;
    var pod1: machine;
    var client0: machine;
    var client1: machine;
    var step: int;

    start state Init {
        entry {
            store = new SimpleTiDB();
            db = new NetworkProxy((db = store, ));
            sharder = new AutoSharder();
            pod0 = new LookasideCacheSystem((db = db, sharder = sharder, podId = 0));
            pod1 = new LookasideCacheSystem((db = db, sharder = sharder, podId = 1));
            client0 = new ClientPod((controller = this, system = pod0, podId = 0, clientId = 0));
            client1 = new ClientPod((controller = this, system = pod1, podId = 1, clientId = 1));
            step = 0;
            send sharder, eRequestOwnershipGrant, (pod = pod0, range = (low = 41, high = 45), sliceHandle = 1);
            send client0, eClientDoRead, (key = 41, );
            goto Running;
        }
    }

    state Running {
        on eClientReadDone do (resp: (clientId: int, key: int, value: int, podId: int)) {
            if (step == 0) {
                step = 1;
                send client0, eClientDoWrite, (key = 41, value = 21);
                return;
            }
            if (step == 2) {
                step = 3;
                send client1, eClientDoWrite, (key = 41, value = 22);
                return;
            }
            if (step == 4) {
                goto Done;
                return;
            }
            goto Done;
        }

        on eClientWriteDone do (resp: (clientId: int, key: int, success: bool, podId: int)) {
            if (step == 1) {
                step = 2;
                send client1, eClientDoRead, (key = 41, );
                return;
            }
            if (step == 3) {
                step = 4;
                send client0, eClientDoRead, (key = 41, );
                return;
            }
            goto Done;
        }
    }

    state Done {
        ignore eClientReadDone, eClientWriteDone, eOwnershipTransferDone;
    }
}

machine CandidateDelayedWriteAfterTransferDriver {
    var store: machine;
    var db: machine;
    var sharder: machine;
    var pod0: machine;
    var pod1: machine;
    var client0: machine;
    var client1: machine;
    var warmups: int;
    var postTransferReads: int;
    var activeSh: int;

    start state Init {
        entry {
            store = new SimpleTiDB();
            db = new NetworkProxy((db = store, ));
            sharder = new AutoSharder();
            pod0 = new LookasideCacheSystem((db = db, sharder = sharder, podId = 0));
            pod1 = new LookasideCacheSystem((db = db, sharder = sharder, podId = 1));
            client0 = new ClientPod((controller = this, system = pod0, podId = 0, clientId = 0));
            client1 = new ClientPod((controller = this, system = pod1, podId = 1, clientId = 1));
            warmups = 0;
            postTransferReads = 0;
            activeSh = 1;
            send sharder, eRequestOwnershipGrant, (pod = pod0, range = (low = 40, high = 45), sliceHandle = activeSh);
            send client0, eClientDoRead, (key = 40, );
            goto AwaitWarmRead;
        }
    }

    state AwaitWarmRead {
        on eClientReadDone do (resp: (clientId: int, key: int, value: int, podId: int)) {
            send client0, eClientDoWrite, (key = 40, value = 5000);
            send client0, eClientDoWrite, (key = 40, value = 5001);
            send client0, eClientDoWrite, (key = 40, value = 5002);
            send client0, eClientDoWrite, (key = 40, value = 5003);
            send this, eHarnessTick;
            goto Warmup;
        }
    }

    state Warmup {
        on eHarnessTick do {
            warmups = warmups + 1;
            if (warmups < 3) {
                send this, eHarnessTick;
                return;
            }
            send sharder, eRequestOwnershipRevoke,
                (pod = pod0, range = (low = 40, high = 45), sliceHandle = activeSh, requester = this);
            activeSh = 2;
            send sharder, eRequestOwnershipGrant, (pod = pod1, range = (low = 40, high = 45), sliceHandle = activeSh);
            goto WaitingTransfer;
        }

        on eClientWriteDone do (resp: (clientId: int, key: int, success: bool, podId: int)) {
            // Ignore write completions; the proxy may delay and reorder them.
        }
    }

    state WaitingTransfer {
        on eOwnershipTransferDone do (resp: (rangeLow: int, sliceHandle: int)) {
            send client1, eClientDoRead, (key = 40, );
            goto ReadingAfterTransfer;
        }

        on eClientWriteDone do (resp: (clientId: int, key: int, success: bool, podId: int)) {
            // Old-owner writes may still complete after revoke; this is intentional.
        }
    }

    state ReadingAfterTransfer {
        on eClientReadDone do (resp: (clientId: int, key: int, value: int, podId: int)) {
            postTransferReads = postTransferReads + 1;
            if (postTransferReads < 6) {
                send client1, eClientDoRead, (key = 40, );
                return;
            }
            goto Done;
        }

        on eClientWriteDone do (resp: (clientId: int, key: int, success: bool, podId: int)) {
            // Ignore late completions from the old owner.
        }
    }

    state Done {
        ignore eClientReadDone, eClientWriteDone, eOwnershipTransferDone;
    }
}
