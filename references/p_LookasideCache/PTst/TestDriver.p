machine Client {
    var cache:    machine;  // shared cache, for reads
    var db:       machine;  // TiDB, for writes (direct, bypass cache)
    var clientId: int;
    var numOps:   int;
    var opsIssued: int;

    start state Init {
        entry (p: (cache: machine, db: machine, id: int, numOps: int)) {
            cache     = p.cache;
            db        = p.db;
            clientId  = p.id;
            numOps    = p.numOps;
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
            key = 40 + choose(3);
            if ($) {
                // Read via shared lookaside cache
                print format("Client {0}: READ  key={1}", clientId, key);
                send cache, eRead, (client = this, key = key);
            } else {
                // Write directly to TiDB — shared cache is NOT invalidated!
                print format("Client {0}: WRITE key={1} val={2}",
                             clientId, key, clientId * 100 + opsIssued);
                send db, eWrite, (client = this, key = key, value = clientId * 100 + opsIssued);
            }
            opsIssued = opsIssued + 1;
        }

        on eReadResp  do (resp: (key: int, value: int))    { goto Issuing; }
        on eWriteResp do (resp: (key: int, success: bool)) { goto Issuing; }
    }

    state Done {
        ignore eReadResp, eWriteResp;
    }
}

machine TestDriver {
    var db:      machine;
    var cache:   machine;
    var client0: machine;
    var client1: machine;

    start state Init {
        entry {
            db      = new SimpleTiDB();
            cache   = new LookasideCache((db = db,));
            client0 = new Client((cache = cache, db = db, id = 0, numOps = 20));
            client1 = new Client((cache = cache, db = db, id = 1, numOps = 20));
            goto Done;
        }
    }

    state Done { }
}
