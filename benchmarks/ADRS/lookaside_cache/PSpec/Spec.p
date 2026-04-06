// Safety oracle for the direct-read and look-aside baseline benchmark.
// LSI means any served read must match the current authoritative DB value.

spec LSISafety observes eMonitorDbWrite, eMonitorDirectRead, eMonitorCacheHit {
    var storageState: map[int, int];

    start state Watching {
        on eMonitorDbWrite do (payload: (key: int, value: int)) {
            storageState[payload.key] = payload.value;
        }

        on eMonitorDirectRead do (payload: (key: int, value: int, podId: int)) {
            var expected: int;
            expected = 0;
            if (payload.key in storageState) {
                expected = storageState[payload.key];
            }
            assert payload.value == expected,
                format("LSI VIOLATION: direct read pod={0} key={1} returned {2} but storage has {3}",
                       payload.podId, payload.key, payload.value, expected);
        }

        on eMonitorCacheHit do (payload: (key: int, value: int, podId: int)) {
            var expected2: int;
            expected2 = 0;
            if (payload.key in storageState) {
                expected2 = storageState[payload.key];
            }
            assert payload.value == expected2,
                format("LSI VIOLATION: cache hit pod={0} key={1} returned {2} but storage has {3}",
                       payload.podId, payload.key, payload.value, expected2);
        }
    }
}
