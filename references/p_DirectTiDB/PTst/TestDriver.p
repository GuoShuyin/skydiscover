// PTst/TestDriver.p  (p_DirectTiDB)
// Client reads and writes go directly to TiDB — no caching layer at all.

machine DirectClient {
    var db:       machine;
    var clientId: int;
    var numOps:   int;
    var opsIssued: int;

    start state Init {
        entry (p: (db: machine, id: int, numOps: int)) {
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
                print format("DirectClient {0}: READ  key={1}", clientId, key);
                send db, eRead, (client = this, key = key);
            } else {
                print format("DirectClient {0}: WRITE key={1} val={2}",
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
    var client0: machine;
    var client1: machine;

    start state Init {
        entry {
            db      = new SimpleTiDB();
            client0 = new DirectClient((db = db, id = 0, numOps = 5));
            client1 = new DirectClient((db = db, id = 1, numOps = 5));
            goto Done;
        }
    }

    state Done { }
}
