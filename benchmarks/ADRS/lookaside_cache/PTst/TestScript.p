test tcDirectSafety [main = DirectSafetyDriver]:
    assert LSISafety in
    {DirectSafetyDriver, SimpleTiDB, DirectReadWriteSystem};

test tcLookasideWarmThenWrite [main = LookasideWarmThenWriteDriver]:
    assert LSISafety in
    {LookasideWarmThenWriteDriver, SimpleTiDB, LookasideCacheSystem};

test tcLookasideMultiClientConflict [main = LookasideMultiClientConflictDriver]:
    assert LSISafety in
    {LookasideMultiClientConflictDriver, SimpleTiDB, LookasideCacheSystem};
