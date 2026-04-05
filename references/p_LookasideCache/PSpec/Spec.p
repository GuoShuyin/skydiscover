// PSpec/Spec.p  (p_LookasideCache)
// LSI invariant: a value returned from cache must equal the current storage value.

spec LSISafety observes eMonitorDbWrite, eMonitorCacheHit {
    var storageState: map[int, int];

    start state Watching {
        on eMonitorDbWrite do (payload: (key: int, value: int)) {
            storageState[payload.key] = payload.value;
        }

        on eMonitorCacheHit do (payload: (key: int, value: int, podId: int)) {
            var expected: int;
            expected = 0;
            if (payload.key in storageState) {
                expected = storageState[payload.key];
            }
            assert payload.value == expected,
                format("LSI VIOLATION: cache {0} hit key={1} returned {2} but storage has {3}",
                       payload.podId, payload.key, payload.value, expected);
        }
    }
}
