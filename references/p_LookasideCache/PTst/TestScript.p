// PTst/TestScript.p  (p_LookasideCache)
// Expected: FAIL — writes bypass the cache, leaving stale entries until TTL expiry.

test tcLookasideLSI [main = TestDriver]:
    assert LSISafety in
    {TestDriver, SimpleTiDB, LookasideCache, Client};
