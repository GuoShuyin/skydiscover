event eClientRead: (client: machine, key: int);
event eClientWrite: (client: machine, key: int, value: int);
event eStorageRead: (caller: machine, key: int, podId: int);
event eStorageWrite: (caller: machine, key: int, value: int, podId: int);
event eStorageReadResp: (key: int, value: int);
event eStorageWriteResp: (key: int, success: bool, value: int);
event eReadResp: (key: int, value: int, fromCache: bool);
event eWriteResp: (key: int, success: bool);

event eMonitorStorageCommit: (key: int, value: int);
event eMonitorClientReadIssued: (key: int, podId: int);
event eMonitorClientWriteIssued: (key: int, podId: int);
event eMonitorStorageReadIssued: (key: int, podId: int);
event eMonitorStorageWriteIssued: (key: int, podId: int);
event eMonitorReadCompleted: (key: int, value: int, podId: int, fromCache: bool);
event eMonitorProxyRequestIssued: (key: int, podId: int, isWrite: bool);
event eMonitorProxyResponseDelivered: (key: int, podId: int, isWrite: bool);
event eMonitorProxyEnqueue: (key: int, podId: int, isWrite: bool, pending: int);
event eMonitorProxyForward: (key: int, podId: int, isWrite: bool, pending: int);
event eMonitorProxyHold: (pending: int);
event eMonitorScenarioDone;
event eProxyBurstStep;
event eProxyBurstFinished: (podId: int);

machine StorageCluster {
    var dataStore: map[int, int];

    start state Ready {
        entry {
            dataStore = default(map[int, int]);
        }

        on eStorageRead do (req: (caller: machine, key: int, podId: int)) {
            var val: int;
            announce eMonitorStorageReadIssued, (key = req.key, podId = req.podId);
            val = 0;
            if (req.key in dataStore) {
                val = dataStore[req.key];
            }
            send req.caller, eStorageReadResp, (key = req.key, value = val);
            print format("StorageCluster: Read key={0} -> {1}", req.key, val);
        }

        on eStorageWrite do (req: (caller: machine, key: int, value: int, podId: int)) {
            announce eMonitorStorageWriteIssued, (key = req.key, podId = req.podId);
            dataStore[req.key] = req.value;
            announce eMonitorStorageCommit, (key = req.key, value = req.value);
            send req.caller, eStorageWriteResp, (key = req.key, success = true, value = req.value);
            print format("StorageCluster: Write key={0} value={1}", req.key, req.value);
        }
    }
}

machine BalancedClient {
    var pod: machine;
    var clientId: int;
    var podId: int;
    var numOps: int;
    var opsIssued: int;

    start state Init {
        entry (p: (pod: machine, id: int, podId: int, numOps: int)) {
            pod = p.pod;
            clientId = p.id;
            podId = p.podId;
            numOps = p.numOps;
            opsIssued = 0;
            goto Issuing;
        }
    }

    state Issuing {
        entry {
            var key: int;
            var value: int;
            if (opsIssued >= numOps) {
                goto Done;
                return;
            }

            key = 40 + choose(3);
            if ($) {
                announce eMonitorClientReadIssued, (key = key, podId = podId);
                print format("BalancedClient {0}: READ key={1}", clientId, key);
                send pod, eClientRead, (client = this, key = key);
            } else {
                value = clientId * 100 + opsIssued;
                announce eMonitorClientWriteIssued, (key = key, podId = podId);
                print format("BalancedClient {0}: WRITE key={1} value={2}", clientId, key, value);
                send pod, eClientWrite, (client = this, key = key, value = value);
            }
            opsIssued = opsIssued + 1;
        }

        on eReadResp do (resp: (key: int, value: int, fromCache: bool)) {
            announce eMonitorReadCompleted,
                (key = resp.key, value = resp.value, podId = podId, fromCache = resp.fromCache);
            print format("BalancedClient {0}: got ReadResp key={1} value={2} fromCache={3}",
                         clientId, resp.key, resp.value, resp.fromCache);
            goto Issuing;
        }

        on eWriteResp do (resp: (key: int, success: bool)) {
            print format("BalancedClient {0}: got WriteResp key={1} success={2}",
                         clientId, resp.key, resp.success);
            goto Issuing;
        }
    }

    state Done {
        ignore eReadResp, eWriteResp;
    }
}

machine WriteBiasedClient {
    var pod: machine;
    var clientId: int;
    var podId: int;
    var numOps: int;
    var opsIssued: int;

    start state Init {
        entry (p: (pod: machine, id: int, podId: int, numOps: int)) {
            pod = p.pod;
            clientId = p.id;
            podId = p.podId;
            numOps = p.numOps;
            opsIssued = 0;
            goto Issuing;
        }
    }

    state Issuing {
        entry {
            var key: int;
            var value: int;
            if (opsIssued >= numOps) {
                goto Done;
                return;
            }

            key = 40 + choose(3);
            if (choose(4) == 0) {
                announce eMonitorClientReadIssued, (key = key, podId = podId);
                print format("WriteBiasedClient {0}: READ key={1}", clientId, key);
                send pod, eClientRead, (client = this, key = key);
            } else {
                value = clientId * 1000 + opsIssued;
                announce eMonitorClientWriteIssued, (key = key, podId = podId);
                print format("WriteBiasedClient {0}: WRITE key={1} value={2}", clientId, key, value);
                send pod, eClientWrite, (client = this, key = key, value = value);
            }
            opsIssued = opsIssued + 1;
        }

        on eReadResp do (resp: (key: int, value: int, fromCache: bool)) {
            announce eMonitorReadCompleted,
                (key = resp.key, value = resp.value, podId = podId, fromCache = resp.fromCache);
            print format("WriteBiasedClient {0}: got ReadResp key={1} value={2} fromCache={3}",
                         clientId, resp.key, resp.value, resp.fromCache);
            goto Issuing;
        }

        on eWriteResp do (resp: (key: int, success: bool)) {
            print format("WriteBiasedClient {0}: got WriteResp key={1} success={2}",
                         clientId, resp.key, resp.success);
            goto Issuing;
        }
    }

    state Done {
        ignore eReadResp, eWriteResp;
    }
}

machine ProxyBurstDriverClient {
    var pod: machine;
    var controller: machine;
    var podId: int;
    var opsIssued: int;
    var responsesSeen: int;
    var targetOps: int;

    start state Init {
        entry (p: (pod: machine, controller: machine, podId: int, targetOps: int)) {
            pod = p.pod;
            controller = p.controller;
            podId = p.podId;
            targetOps = p.targetOps;
            opsIssued = 0;
            responsesSeen = 0;
            goto Active;
        }
    }

    state Active {
        entry {
            send this, eProxyBurstStep;
        }

        on eProxyBurstStep do {
            var baseValue: int;
            var key: int;

            if (opsIssued >= targetOps) {
                return;
            }

            key = 40 + choose(2);
            baseValue = podId * 1000 + opsIssued;

            announce eMonitorClientWriteIssued, (key = key, podId = podId);
            send pod, eClientWrite, (client = this, key = key, value = baseValue);
            opsIssued = opsIssued + 1;

            if (opsIssued < targetOps) {
                announce eMonitorClientReadIssued, (key = key, podId = podId);
                send pod, eClientRead, (client = this, key = key);
                opsIssued = opsIssued + 1;
            }

            if (opsIssued < targetOps) {
                announce eMonitorClientWriteIssued, (key = 41, podId = podId);
                send pod, eClientWrite, (client = this, key = 41, value = baseValue + 100);
                opsIssued = opsIssued + 1;
            }

            if (opsIssued < targetOps) {
                announce eMonitorClientReadIssued, (key = 41, podId = podId);
                send pod, eClientRead, (client = this, key = 41);
                opsIssued = opsIssued + 1;
            }

            if (opsIssued < targetOps) {
                send this, eProxyBurstStep;
            }
        }

        on eReadResp do (resp: (key: int, value: int, fromCache: bool)) {
            announce eMonitorReadCompleted,
                (key = resp.key, value = resp.value, podId = podId, fromCache = resp.fromCache);
            responsesSeen = responsesSeen + 1;
            if (responsesSeen >= targetOps && opsIssued >= targetOps) {
                send controller, eProxyBurstFinished, (podId = podId, );
                goto Done;
            }
        }

        on eWriteResp do (resp: (key: int, success: bool)) {
            responsesSeen = responsesSeen + 1;
            if (responsesSeen >= targetOps && opsIssued >= targetOps) {
                send controller, eProxyBurstFinished, (podId = podId, );
                goto Done;
            }
        }
    }

    state Done {
        ignore eReadResp, eWriteResp, eProxyBurstStep;
    }
}
