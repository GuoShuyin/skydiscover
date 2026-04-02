spec LSIInvariant observes eMonitorStorageCommit, eMonitorClientReadIssued, eMonitorStorageReadIssued, eMonitorReadCompleted {
    var storageState: map[int, int];
    var pendingReadTouchedStorage: map[int, bool];

    start state Watching {
        on eMonitorStorageCommit do (payload: (key: int, value: int)) {
            storageState[payload.key] = payload.value;
        }

        on eMonitorClientReadIssued do (payload: (key: int, podId: int)) {
            pendingReadTouchedStorage[payload.podId] = false;
        }

        on eMonitorStorageReadIssued do (payload: (key: int, podId: int)) {
            if (payload.podId in pendingReadTouchedStorage) {
                pendingReadTouchedStorage[payload.podId] = true;
            }
        }

        on eMonitorReadCompleted do (payload: (key: int, value: int, podId: int, fromCache: bool)) {
            var expected: int;
            expected = 0;
            if (payload.key in storageState) {
                expected = storageState[payload.key];
            }

            if (payload.podId in pendingReadTouchedStorage && !pendingReadTouchedStorage[payload.podId]) {
                assert payload.value == expected,
                    format("LSI VIOLATION: pod {0} served key={1} value={2} without storage, but storage has {3}",
                           payload.podId, payload.key, payload.value, expected);
            }

            if (payload.podId in pendingReadTouchedStorage) {
                pendingReadTouchedStorage -= (payload.podId);
            }
        }
    }
}

spec ProxyQueueDiscipline observes eMonitorProxyEnqueue, eMonitorProxyForward, eMonitorProxyHold,
                                 eMonitorStorageReadIssued, eMonitorStorageWriteIssued, eMonitorScenarioDone {
    var queued: int;
    var forwardsAwaitingStorage: int;
    var sawEnqueue: bool;
    var sawForward: bool;
    var sawStorage: bool;

    start state Watching {
        on eMonitorProxyEnqueue do (payload: (key: int, podId: int, isWrite: bool, pending: int)) {
            queued = queued + 1;
            sawEnqueue = true;
        }

        on eMonitorProxyForward do (payload: (key: int, podId: int, isWrite: bool, pending: int)) {
            assert queued > 0,
                format("Proxy forwarded key={0} without a queued request", payload.key);
            queued = queued - 1;
            forwardsAwaitingStorage = forwardsAwaitingStorage + 1;
            sawForward = true;
        }

        on eMonitorProxyHold do (payload: (pending: int)) {
            assert payload.pending > 0,
                format("Proxy hold should only occur with pending requests, got pending={0}", payload.pending);
        }

        on eMonitorStorageReadIssued do (payload: (key: int, podId: int)) {
            assert forwardsAwaitingStorage > 0,
                format("Storage read for key={0} occurred without a preceding proxy forward", payload.key);
            forwardsAwaitingStorage = forwardsAwaitingStorage - 1;
            sawStorage = true;
        }

        on eMonitorStorageWriteIssued do (payload: (key: int, podId: int)) {
            assert forwardsAwaitingStorage > 0,
                format("Storage write for key={0} occurred without a preceding proxy forward", payload.key);
            forwardsAwaitingStorage = forwardsAwaitingStorage - 1;
            sawStorage = true;
        }

        on eMonitorScenarioDone do {
            assert sawEnqueue, "Proxy discipline scenario finished without any observed enqueue";
            assert sawForward, "Proxy discipline scenario finished without any observed forward";
            assert sawStorage, "Proxy discipline scenario finished without any storage-facing request";
        }
    }
}
