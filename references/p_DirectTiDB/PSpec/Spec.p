// PSpec/Spec.p  (p_DirectTiDB)
// Check that every value returned by TiDB matches the current storage state.
// Since announce in TiDB's eRead handler fires synchronously before the response
// is queued, storageState and dbStore are always in sync -> always passes.

spec LSISafety observes eMonitorDbWrite, eMonitorDirectRead {
    var storageState: map[int, int];

    start state Watching {
        on eMonitorDbWrite do (payload: (key: int, value: int)) {
            storageState[payload.key] = payload.value;
        }

        on eMonitorDirectRead do (payload: (key: int, value: int)) {
            var expected: int;
            expected = 0;
            if (payload.key in storageState) {
                expected = storageState[payload.key];
            }
            assert payload.value == expected,
                format("VIOLATION: direct read key={0} returned {1} but storage has {2}",
                       payload.key, payload.value, expected);
        }
    }
}
