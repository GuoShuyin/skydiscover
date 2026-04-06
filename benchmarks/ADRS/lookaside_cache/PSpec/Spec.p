// Safety oracle for the ownership-aware direct/read and look-aside benchmark.
// LSI means any served read must match the current authoritative DB value.

spec LSISafety observes eMonitorDbWrite, eMonitorServedRead {
    var storageState: map[int, int];

    start state Watching {
        on eMonitorDbWrite do (payload: (key: int, value: int)) {
            storageState[payload.key] = payload.value;
        }

        on eMonitorServedRead do (payload: (key: int, value: int, podId: int)) {
            var expected: int;
            expected = 0;
            if (payload.key in storageState) {
                expected = storageState[payload.key];
            }
            assert payload.value == expected,
                format("LSI VIOLATION: served read pod={0} key={1} returned {2} but storage has {3}",
                       payload.podId, payload.key, payload.value, expected);
        }
    }
}
