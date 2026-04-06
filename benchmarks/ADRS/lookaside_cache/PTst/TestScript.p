test tcCandidateWarmThenWrite [main = CandidateWarmThenWriteDriver]:
    assert LSISafety in
    {CandidateWarmThenWriteDriver, SimpleTiDB, NetworkProxy, AutoSharder, ClientPod, LookasideCacheSystem};

test tcCandidateMultiClientConflict [main = CandidateMultiClientConflictDriver]:
    assert LSISafety in
    {CandidateMultiClientConflictDriver, SimpleTiDB, NetworkProxy, AutoSharder, ClientPod, LookasideCacheSystem};

test tcCandidateDelayedWriteAfterTransfer [main = CandidateDelayedWriteAfterTransferDriver]:
    assert LSISafety in
    {CandidateDelayedWriteAfterTransferDriver, SimpleTiDB, NetworkProxy, AutoSharder, ClientPod, LookasideCacheSystem};
