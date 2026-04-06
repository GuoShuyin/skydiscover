// Fixed harness for the direct/read-write and look-aside cache baselines.
// Search may redesign internal machines, but keeping these baseline names and
// event signatures preserves compatibility with compile/check validation.

machine DirectSafetyDriver {
    var db: machine;
    var system: machine;

    start state Init {
        entry {
            db = new SimpleTiDB();
            system = new DirectReadWriteSystem((db = db, ));
            send system, eRead, (client = this, key = 40, podId = 0);
            goto AwaitWarmRead;
        }
    }

    state AwaitWarmRead {
        on eReadResp do (resp: (key: int, value: int, podId: int)) {
            send system, eWrite, (client = this, key = 40, value = 7, podId = 0);
            goto AwaitWrite;
        }
    }

    state AwaitWrite {
        on eWriteResp do (resp: (key: int, success: bool, podId: int)) {
            send system, eRead, (client = this, key = 40, podId = 1);
            goto AwaitFreshRead;
        }
    }

    state AwaitFreshRead {
        on eReadResp do (resp: (key: int, value: int, podId: int)) {
            goto Done;
        }
    }

    state Done {
        ignore eReadResp, eWriteResp;
    }
}

machine LookasideWarmThenWriteDriver {
    var db: machine;
    var system: machine;

    start state Init {
        entry {
            db = new SimpleTiDB();
            system = new LookasideCacheSystem((db = db, ));
            send system, eRead, (client = this, key = 40, podId = 0);
            goto AwaitWarmRead;
        }
    }

    state AwaitWarmRead {
        on eReadResp do (resp: (key: int, value: int, podId: int)) {
            send system, eWrite, (client = this, key = 40, value = 11, podId = 1);
            goto AwaitWrite;
        }
    }

    state AwaitWrite {
        on eWriteResp do (resp: (key: int, success: bool, podId: int)) {
            send system, eRead, (client = this, key = 40, podId = 2);
            goto AwaitSecondRead;
        }
    }

    state AwaitSecondRead {
        on eReadResp do (resp: (key: int, value: int, podId: int)) {
            goto Done;
        }
    }

    state Done {
        ignore eReadResp, eWriteResp;
    }
}

machine LookasideMultiClientConflictDriver {
    var db: machine;
    var system: machine;
    var step: int;

    start state Init {
        entry {
            db = new SimpleTiDB();
            system = new LookasideCacheSystem((db = db, ));
            step = 0;
            send system, eRead, (client = this, key = 41, podId = 0);
            goto Running;
        }
    }

    state Running {
        on eReadResp do (resp: (key: int, value: int, podId: int)) {
            if (step == 0) {
                step = 1;
                send system, eWrite, (client = this, key = 41, value = 21, podId = 1);
                return;
            }
            if (step == 2) {
                step = 3;
                send system, eWrite, (client = this, key = 41, value = 22, podId = 3);
                return;
            }
            if (step == 4) {
                goto Done;
                return;
            }
            goto Done;
        }

        on eWriteResp do (resp: (key: int, success: bool, podId: int)) {
            if (step == 1) {
                step = 2;
                send system, eRead, (client = this, key = 41, podId = 2);
                return;
            }
            if (step == 3) {
                step = 4;
                send system, eRead, (client = this, key = 41, podId = 4);
                return;
            }
            goto Done;
        }
    }

    state Done {
        ignore eReadResp, eWriteResp;
    }
}
