machine BalancedWorkloadDriver {
    var db: machine;
    var pod0: machine;
    var pod1: machine;
    var client0: machine;
    var client1: machine;

    start state Init {
        entry {
            var store: machine;
            store = new StorageCluster();
            db = new StorageProxy((db = store, ));
            pod0 = new CacheNode((proxy = db, podId = 0));
            pod1 = new CacheNode((proxy = db, podId = 1));

            client0 = new BalancedClient((pod = pod0, id = 0, podId = 0, numOps = 24));
            client1 = new BalancedClient((pod = pod1, id = 1, podId = 1, numOps = 24));
            goto Done;
        }
    }

    state Done {
        ignore eReadResp, eWriteResp;
    }
}

machine WriteHeavyWorkloadDriver {
    var db: machine;
    var pod0: machine;
    var pod1: machine;
    var client0: machine;
    var client1: machine;

    start state Init {
        entry {
            var store: machine;
            store = new StorageCluster();
            db = new StorageProxy((db = store, ));
            pod0 = new CacheNode((proxy = db, podId = 0));
            pod1 = new CacheNode((proxy = db, podId = 1));

            client0 = new WriteBiasedClient((pod = pod0, id = 0, podId = 0, numOps = 24));
            client1 = new WriteBiasedClient((pod = pod1, id = 1, podId = 1, numOps = 24));
            goto Done;
        }
    }

    state Done {
        ignore eReadResp, eWriteResp;
    }
}

machine TargetedLSIDriver {
    var db: machine;
    var pod0: machine;
    var pod1: machine;
    var phase: int;

    start state Init {
        entry {
            var store: machine;
            store = new StorageCluster();
            db = new StorageProxy((db = store, ));
            pod0 = new CacheNode((proxy = db, podId = 0));
            pod1 = new CacheNode((proxy = db, podId = 1));
            phase = 0;
            goto WarmRead;
        }
    }

    state WarmRead {
        entry {
            announce eMonitorClientReadIssued, (key = 40, podId = 0);
            send pod0, eClientRead, (client = this, key = 40);
        }

        on eReadResp do (resp: (key: int, value: int, fromCache: bool)) {
            announce eMonitorReadCompleted,
                (key = resp.key, value = resp.value, podId = 0, fromCache = resp.fromCache);
            phase = 1;
            goto CrossWrite;
        }
    }

    state CrossWrite {
        entry {
            announce eMonitorClientWriteIssued, (key = 40, podId = 1);
            send pod1, eClientWrite, (client = this, key = 40, value = 999);
        }

        on eWriteResp do (resp: (key: int, success: bool)) {
            phase = 2;
            goto ProbeRead;
        }
    }

    state ProbeRead {
        entry {
            announce eMonitorClientReadIssued, (key = 40, podId = 0);
            send pod0, eClientRead, (client = this, key = 40);
        }

        on eReadResp do (resp: (key: int, value: int, fromCache: bool)) {
            announce eMonitorReadCompleted,
                (key = resp.key, value = resp.value, podId = 0, fromCache = resp.fromCache);
            goto Done;
        }
    }

    state Done {
        ignore eReadResp, eWriteResp;
    }
}

machine ProxyDisciplineDriver {
    var db: machine;
    var pod0: machine;
    var pod1: machine;
    var client0: machine;
    var client1: machine;
    var finishedClients: int;

    start state Init {
        entry {
            var store: machine;
            store = new StorageCluster();
            db = new StorageProxy((db = store, ));
            pod0 = new CacheNode((proxy = db, podId = 0));
            pod1 = new CacheNode((proxy = db, podId = 1));
            finishedClients = 0;

            client0 = new ProxyBurstDriverClient((pod = pod0, controller = this, podId = 0, targetOps = 8));
            client1 = new ProxyBurstDriverClient((pod = pod1, controller = this, podId = 1, targetOps = 8));
            goto WaitingForClients;
        }
    }

    state WaitingForClients {
        on eProxyBurstFinished do (payload: (podId: int)) {
            finishedClients = finishedClients + 1;
            if (finishedClients >= 2) {
                announce eMonitorScenarioDone;
                goto Done;
            }
        }
    }

    state Done {
        ignore eReadResp, eWriteResp;
    }
}
