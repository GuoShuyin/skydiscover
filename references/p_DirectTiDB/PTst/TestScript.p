// PTst/TestScript.p  (p_DirectTiDB)
// Expected: PASS — no cache, so eMonitorCacheHit never fires, LSI trivially holds.

test tcDirectTiDBLSI [main = TestDriver]:
    assert LSISafety in
    {TestDriver, SimpleTiDB, DirectClient};
