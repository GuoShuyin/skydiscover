// PTst/TestDriver.p
// Nondeterministic test driver for PChecker exploration

// Client machine: issues random read/write ops to its assigned pod
machine Client {
    var pod: machine;
    var clientId: int;
    var numOps: int;
    var opsIssued: int;

    start state Init {
        entry (p: (pod: machine, id: int, numOps: int)) {
            pod      = p.pod;
            clientId = p.id;
            numOps   = p.numOps;
            opsIssued = 0;
            goto Issuing;
        }
    }

    state Issuing {
        entry {
            var key: int;
            if (opsIssued >= numOps) {
                goto Done;
                return;
            }
            // Pick key in [40, 44]
            key = 40 + choose(2);
            if ($) {
                // Read
                print format("Client {0}: READ key={1}", clientId, key);
                send pod, eClientRead, (client = this, key = key);
            } else {
                // Write with value = clientId * 100 + opsIssued
                print format("Client {0}: WRITE key={1} value={2}", clientId, key, clientId * 100 + opsIssued);
                send pod, eClientWrite, (client = this, key = key, value = clientId * 100 + opsIssued);
            }
            opsIssued = opsIssued + 1;
        }

        on eReadResp do (resp: (key: int, value: int, fromCache: bool)) {
            print format("Client {0}: got ReadResp key={1} value={2} fromCache={3}",
                         clientId, resp.key, resp.value, resp.fromCache);
            goto Issuing;
        }

        on eWriteResp do (resp: (key: int, success: bool)) {
            print format("Client {0}: got WriteResp key={1} success={2}",
                         clientId, resp.key, resp.success);
            goto Issuing;
        }
    }

    state Done {
        ignore eReadResp, eWriteResp;
    }
}

// Focused client: continuously writes one key to maximize stale-write opportunities.
machine WriteHammerClient {
    var pod: machine;
    var clientId: int;
    var key: int;
    var startValue: int;
    var numWrites: int;
    var writesIssued: int;
    var writesAcked: int;

    start state Init {
        entry (p: (pod: machine, id: int, key: int, startValue: int, numWrites: int)) {
            pod = p.pod;
            clientId = p.id;
            key = p.key;
            startValue = p.startValue;
            numWrites = p.numWrites;
            writesIssued = 0;
            writesAcked = 0;
            goto Writing;
        }
    }

    state Writing {
        entry {
            var value: int;
            // Keep a small pipeline of in-flight writes to increase reorder opportunities.
            while (writesIssued < numWrites && (writesIssued - writesAcked) < 3) {
                value = startValue + writesIssued;
                print format("HammerClient {0}: WRITE key={1} value={2}",
                             clientId, key, value);
                send pod, eClientWrite, (client = this, key = key, value = value);
                writesIssued = writesIssued + 1;
            }

            if (writesAcked >= numWrites) {
                goto Done;
                return;
            }
        }

        on eWriteResp do (resp: (key: int, success: bool)) {
            print format("HammerClient {0}: got WriteResp key={1} success={2}",
                         clientId, resp.key, resp.success);
            writesAcked = writesAcked + 1;
            goto Writing;
        }

        on eReadResp do (resp: (key: int, value: int, fromCache: bool)) {
            // This client only sends writes; ignore unexpected reads.
            print format("HammerClient {0}: unexpected ReadResp key={1} value={2}",
                         clientId, resp.key, resp.value);
            goto Writing;
        }
    }

    state Done {
        ignore eReadResp, eWriteResp;
    }
}

machine ReadHammerClient {
    var pod: machine;
    var clientId: int;
    var key: int;
    var numReads: int;
    var readsIssued: int;

    start state Init {
        entry (p: (pod: machine, id: int, key: int, numReads: int)) {
            pod = p.pod;
            clientId = p.id;
            key = p.key;
            numReads = p.numReads;
            readsIssued = 0;
            goto Reading;
        }
    }

    state Reading {
        entry {
            if (readsIssued >= numReads) {
                goto Done;
                return;
            }

            print format("ReadHammer {0}: READ key={1}", clientId, key);
            send pod, eClientRead, (client = this, key = key);
            readsIssued = readsIssued + 1;
        }

        on eReadResp do (resp: (key: int, value: int, fromCache: bool)) {
            print format("ReadHammer {0}: got ReadResp key={1} value={2} fromCache={3}",
                         clientId, resp.key, resp.value, resp.fromCache);
            goto Reading;
        }

        on eWriteResp do (resp: (key: int, success: bool)) {
            print format("ReadHammer {0}: unexpected WriteResp key={1} success={2}",
                         clientId, resp.key, resp.success);
            goto Reading;
        }
    }

    state Done {
        ignore eReadResp, eWriteResp;
    }
}

// TestDriver: nondeterministic environment
machine TestDriver {
    var db:           machine;
    var sharder:      machine;
    var pod0:         machine;
    var pod1:         machine;
    var client0:      machine;
    var client1:      machine;
    var sliceCounter: int;
    var currentOwner: int;
    var loopCount:    int;
    var activeSh:     int;  // slice handle currently held by the owner of [40,45)


    fun NextSlice(): int {
        sliceCounter = sliceCounter + 1;
        return sliceCounter;
    }

    start state Init {
        entry {
            var store: machine;
            var sh: int;
            store   = new TiDB();
            db      = new NetworkProxy((db = store, ));
            sharder = new AutoSharder();
            pod0    = new CacheNode((db = db, sharder = sharder, podId = 0));
            pod1    = new CacheNode((db = db, sharder = sharder, podId = 1));
            sliceCounter = 0;
            currentOwner = 0;
            loopCount    = 0;

            // Initial ownership grant to pod0
            sh = NextSlice();
            activeSh = sh;
            send sharder, eRequestOwnershipGrant, (pod = pod0, range = (low = 40, high = 45), sliceHandle = sh);

            // Create clients (bounded ops to limit state space)
            client0 = new Client((pod = pod0, id = 0, numOps = 20));
            client1 = new Client((pod = pod1, id = 1, numOps = 20));

            goto EnvironmentLoop;
        }
    }

    state EnvironmentLoop {
        entry {
            var action: int;
            var sh: int;
            var currPod: machine;
            var otherOwner: int;

            if (loopCount >= 20) {
                goto Done;
                return;
            }
            loopCount = loopCount + 1;

            action = choose(5);
            if (action == 0) {
                // Ownership transfer: revoke old owner first, then grant new owner.
                sh = NextSlice();
                if (currentOwner == 0) {
                    currPod = pod0;
                    otherOwner = 1;
                    send sharder, eRequestOwnershipRevoke, (pod = currPod, range = (low = 40, high = 45), sliceHandle = activeSh, requester = this);
                    send sharder, eRequestOwnershipGrant, (pod = pod1, range = (low = 40, high = 45), sliceHandle = sh);
                } else {
                    currPod = pod1;
                    otherOwner = 0;
                    send sharder, eRequestOwnershipRevoke, (pod = currPod, range = (low = 40, high = 45), sliceHandle = activeSh, requester = this);
                    send sharder, eRequestOwnershipGrant, (pod = pod0, range = (low = 40, high = 45), sliceHandle = sh);
                }
                activeSh = sh;
                currentOwner = otherOwner;
                print format("ENV: ownership transfer to pod{0} sh={1}", otherOwner, sh);
                goto WaitingTransfer;
                return;
            } else if (action == 1) {
                // Pod restart
                if ($) {
                    send pod0, ePodRestart;
                    print "ENV: pod0 restart";
                } else {
                    send pod1, ePodRestart;
                    print "ENV: pod1 restart";
                }
            } else if (action == 2) {
                // Tablet restart: clear TiDB epochs
                send db, eTabletRestart;
                print "ENV: tablet restart";
            } else if (action == 3) {
                // Tablet split: nondeterministic split key in (40, 45)
                send db, eTabletSplit, 41 + choose(3);
                print "ENV: tablet split";
            } else {
                // No-op
                print "ENV: no-op";
            }

            // Nondeterministically decide whether to continue looping
            if ($) {
                goto EnvironmentLoop;
            } else {
                goto Done;
            }
        }
    }

    state WaitingTransfer {
        on eOwnershipTransferDone do (resp: (rangeLow: int, sliceHandle: int)) {
            print format("ENV: ownership transfer revoke-ack rangeLow={0} sh={1}",
                         resp.rangeLow, resp.sliceHandle);
            // Nondeterministically decide whether to continue looping
            if ($) {
                goto EnvironmentLoop;
            } else {
                goto Done;
            }
        }
    }

    state Done {
        ignore eReadResp, eWriteResp, eOwnershipTransferDone;
    }
}

// Focused test driver for delayed-write interleavings with a write proxy.
machine DelayWriteFocusedDriver {
    var db:           machine;
    var sharder:      machine;
    var pod0:         machine;
    var pod1:         machine;
    var writer0:      machine;
    var writer1:      machine;
    var sliceCounter: int;
    var currentOwner: int;
    var activeSh:     int;
    var rounds:       int;

    fun NextSlice(): int {
        sliceCounter = sliceCounter + 1;
        return sliceCounter;
    }

    start state Init {
        entry {
            var store: machine;
            var sh: int;
            store   = new TiDB();
            db      = new NetworkProxy((db = store, ));
            sharder = new AutoSharder();
            pod0    = new CacheNode((db = db, sharder = sharder, podId = 0));
            pod1    = new CacheNode((db = db, sharder = sharder, podId = 1));
            sliceCounter = 0;
            currentOwner = 0;
            rounds       = 0;

            // Initial owner is pod0.
            sh = NextSlice();
            activeSh = sh;
            send sharder, eRequestOwnershipGrant, (pod = pod0, range = (low = 40, high = 45), sliceHandle = sh);

            // Two write hammers on the same key to keep writes in-flight while env mutates epochs.
            writer0 = new WriteHammerClient((pod = pod0, id = 0, key = 40, startValue = 1000, numWrites = 8));
            writer1 = new WriteHammerClient((pod = pod1, id = 1, key = 40, startValue = 2000, numWrites = 8));

            goto ChaosLoop;
        }
    }

    state ChaosLoop {
        entry {
            var action: int;
            var sh: int;
            var currPod: machine;
            var nextPod: machine;
            var nextOwner: int;

            if (rounds >= 12) {
                goto Done;
                return;
            }
            rounds = rounds + 1;

            // Focus on ownership epochs only (no tablet restart/split), so stale writes
            // are observed as old-epoch-vs-new-epoch races instead of expectedEpoch=0 cases.
            action = choose(4);
            if (action <= 2) {
                sh = NextSlice();
                if (currentOwner == 0) {
                    currPod = pod0;
                    nextPod = pod1;
                    nextOwner = 1;
                } else {
                    currPod = pod1;
                    nextPod = pod0;
                    nextOwner = 0;
                }
                // Keep same range, rotate slice handles aggressively. Revoke then grant.
                send sharder, eRequestOwnershipRevoke, (pod = currPod, range = (low = 40, high = 45), sliceHandle = activeSh, requester = this);
                send sharder, eRequestOwnershipGrant, (pod = nextPod, range = (low = 40, high = 45), sliceHandle = sh);
                activeSh = sh;
                currentOwner = nextOwner;
                print format("FOCUSED ENV: ownership transfer to pod{0} sh={1}", nextOwner, sh);
                goto WaitingTransfer;
                return;
            } else {
                print "FOCUSED ENV: no-op";
            }

            goto ChaosLoop;
        }
    }

    state WaitingTransfer {
        on eOwnershipTransferDone do (resp: (rangeLow: int, sliceHandle: int)) {
            print format("FOCUSED ENV: ownership transfer revoke-ack rangeLow={0} sh={1}",
                         resp.rangeLow, resp.sliceHandle);
            goto ChaosLoop;
        }
    }

    state Done {
        ignore eReadResp, eWriteResp, eOwnershipTransferDone;
    }
}

machine ProxyLSIDriver {
    var db:           machine;
    var sharder:      machine;
    var pod0:         machine;
    var pod1:         machine;
    var writer0:      machine;
    var reader1:      machine;
    var sliceCounter: int;
    var activeSh:     int;
    var warmups:      int;

    fun NextSlice(): int {
        sliceCounter = sliceCounter + 1;
        return sliceCounter;
    }

    start state Init {
        entry {
            var store: machine;
            var sh: int;
            store   = new TiDB();
            db      = new NetworkProxy((db = store, ));
            sharder = new AutoSharder();
            pod0    = new CacheNode((db = db, sharder = sharder, podId = 0));
            pod1    = new CacheNode((db = db, sharder = sharder, podId = 1));
            sliceCounter = 0;
            warmups = 0;

            sh = NextSlice();
            activeSh = sh;
            send sharder, eRequestOwnershipGrant, (pod = pod0, range = (low = 40, high = 45), sliceHandle = sh);

            // Give pod0 time to install epochs, then keep old-owner writes flowing.
            writer0 = new WriteHammerClient((pod = pod0, id = 0, key = 40, startValue = 5000, numWrites = 12));
            goto Warmup;
        }
    }

    state Warmup {
        entry {
            var sh: int;
            warmups = warmups + 1;
            if (warmups < 4) {
                goto Warmup;
                return;
            }

            sh = NextSlice();
            send sharder, eRequestOwnershipRevoke, (pod = pod0, range = (low = 40, high = 45), sliceHandle = activeSh, requester = this);
            send sharder, eRequestOwnershipGrant, (pod = pod1, range = (low = 40, high = 45), sliceHandle = sh);
            activeSh = sh;
            print format("PROXY LSI: transfer to pod1 sh={0}", sh);
            goto WaitingTransfer;
        }
    }

    state WaitingTransfer {
        on eOwnershipTransferDone do (resp: (rangeLow: int, sliceHandle: int)) {
            print format("PROXY LSI: transfer revoke-ack rangeLow={0} sh={1}",
                         resp.rangeLow, resp.sliceHandle);
            // New owner repeatedly reads the same key, so one read can cache an old value
            // and a later cache hit can expose the delayed write.
            reader1 = new ReadHammerClient((pod = pod1, id = 1, key = 40, numReads = 12));
            goto Done;
        }
    }

    state Done {
        ignore eReadResp, eWriteResp, eOwnershipTransferDone;
    }
}
