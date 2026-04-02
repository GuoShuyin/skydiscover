"""
Distributed cache protocol discovery task.

Design intent:
- Cached reads should remain linearizable without contacting storage on cache hits.
- A delayed write from an old owner must never be accepted after ownership changes.
- The cache/proxy protocol should minimize round trips and redundant control-plane
  work between the cache tier and the storage tier.

Your job is to generate P code that defines exactly these two machines:
- machine StorageProxy
- machine CacheNode

The evaluator hides the concrete checker harness and maps the generic names in
your candidate to the internal benchmark implementation before compiling.

Candidate-side interface available in the fixed environment:

Types:
- type tKeyRange = (low: int, high: int)
- type tOwnershipRecord = (range: tKeyRange, versionId: int, ownershipEpoch: int)
- type tStorageWriteReq = (caller: machine, key: int, value: int, versionId: int, rangeLow: int)
- type tAccessHandle = (opType: int, writeOverlap: bool, hasOwnershipRecord: bool, ownershipRecord: tOwnershipRecord, client: machine, value: int)
- type tCachedValue = (ownershipRecord: tOwnershipRecord, value: int)

Events:
- eClientRead: (client: machine, key: int)
- eClientWrite: (client: machine, key: int, value: int)
- eStorageRead: (caller: machine, key: int)
- eStorageWrite: tStorageWriteReq
- eSyncOwnership: (caller: machine, range: tKeyRange, versionId: int)
- eStorageReadResp: (key: int, value: int)
- eStorageWriteResp: (key: int, success: bool, value: int)
- eSyncOwnershipDone: (rangeLow: int, status: int)
- eReadResp: (key: int, value: int, fromCache: bool)
- eWriteResp: (key: int, success: bool)
- eOwnershipGrant: (range: tKeyRange, ownershipEpoch: int)
- eOwnershipRevoke: (range: tKeyRange, ownershipEpoch: int, ackTo: machine)
- eOwnershipRevokeAck: (range: tKeyRange, ownershipEpoch: int)
- eOwnershipTransferDone: (rangeLow: int, ownershipEpoch: int)
- eRequestOwnershipGrant: (pod: machine, range: tKeyRange, ownershipEpoch: int)
- eRequestOwnershipRevoke: (pod: machine, range: tKeyRange, ownershipEpoch: int, requester: machine)
- ePodRestart
- eStorageRestart
- eFetchShardLayout: (caller: machine, range: tKeyRange)
- eFetchShardLayoutResp: (subRanges: seq[tKeyRange])
- eStorageSplit: int
- eProxyTick

Scoring:
- Safety first: model checking must satisfy both LSI safety and no stale-write commit.
- Efficiency second: fewer storage/control-plane round trips and higher cache-hit rate score better.
"""

from evaluator_runtime import evaluate, evaluate_stage1, evaluate_stage2, main


if __name__ == "__main__":
    main()
