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
            pod0    = new CLINKPod((db = db, sharder = sharder, podId = 0));
            pod1    = new CLINKPod((db = db, sharder = sharder, podId = 1));
            sliceCounter = 0;
            warmups = 0;

            sh = NextSlice();
            activeSh = sh;
            send sharder, eRequestOwnershipGrant, (pod = pod0, range = (low = 40, high = 45), sliceHandle = sh);

            // Give pod0 time to install guards, then keep old-owner writes flowing.
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
