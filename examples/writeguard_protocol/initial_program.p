// Mutable protocol slice for the distributed cache benchmark.
// The evaluator splices this snippet after the fixed type/event/controller/backend
// definitions from the fixed source model.
// Preserve the machine names and external event interface expected by the tests.
# EVOLVE-BLOCK-START
machine StorageProxy {
    var db: machine;
    var pendingWrites: seq[tStorageWriteReq];

    start state Ready {
        entry (p: (db: machine)) {
            db = p.db;
            pendingWrites = default(seq[tStorageWriteReq]);
        }

        on eStorageRead do (req: (caller: machine, key: int)) {
            send db, eStorageRead, req;
        }

        on eFetchShardLayout do (req: (caller: machine, range: tKeyRange)) {
            send db, eFetchShardLayout, req;
        }

        on eSyncOwnership do (req: (caller: machine, range: tKeyRange, versionId: int)) {
            send db, eSyncOwnership, req;
        }

        on eStorageRestart do {
            send db, eStorageRestart;
        }

        on eStorageSplit do (splitKey: int) {
            send db, eStorageSplit, splitKey;
        }

        on eStorageWrite do (req: tStorageWriteReq) {
            if ($) {
                print format("Proxy: forwarding WRITE key={0} ownership_record={1} immediately", req.key, req.versionId);
                send db, eStorageWrite, req;
            } else {
                pendingWrites += (sizeof(pendingWrites), req);
                print format("Proxy: delaying WRITE key={0} ownership_record={1}; pending={2}",
                             req.key, req.versionId, sizeof(pendingWrites));
                send this, eProxyTick;
            }
        }

        on eProxyTick do {
            var idx: int;
            var req: tStorageWriteReq;
            if (sizeof(pendingWrites) == 0) {
                return;
            }

            if ($) {
                idx = choose(sizeof(pendingWrites));
                req = pendingWrites[idx];
                pendingWrites -= (idx);
                print format("Proxy: releasing delayed WRITE key={0} ownership_record={1}; remaining={2}",
                             req.key, req.versionId, sizeof(pendingWrites));
                send db, eStorageWrite, req;
            } else {
                print format("Proxy: keeping delayed WRITE pending={0}", sizeof(pendingWrites));
            }

            if (sizeof(pendingWrites) > 0 && $) {
                send this, eProxyTick;
            }
        }
    }
}

// ---- CacheNode ----
// Faithful to Algorithms 1-4
machine CacheNode {
    var db:      machine;
    var sharder: machine;
    var podId:   int;
    var localVersionCounter: int;
    var ownershipRecordMap: map[int, tOwnershipRecord];//key represents lower bound of the range
    var cacheMap: map[int, tCachedValue];
    var opMap:    map[int, seq[tAccessHandle]];

    var pendingRange:       tKeyRange;
    var pendingVersionId:     int;
    var pendingOwnershipEpoch: int;

    var validOwnershipEpochs: set[int];
    // Write retry (Algorithm 2, lines 19-24)
    var isRetryWrite: bool;
    var retryKey:     int;
    var retryValue:   int;
    var retryClient:  machine;
    // Storage split point modeling (Algorithm 1, lines 8-16)
    var pendingOwnedRange: tKeyRange;       // full slice range from ownership grant
    var pendingSubranges:  seq[tKeyRange];  // sub-ranges from split points
    var pendingSubrangeIdx:     int;             // current sub-range index being installed

    start state Init {
        entry (p: (db: machine, sharder: machine, podId: int)) {
            db      = p.db;
            sharder = p.sharder;
            podId   = p.podId;
            localVersionCounter = podId * 1000 + 1;
            isRetryWrite = false;
            pendingSubranges = default(seq[tKeyRange]);
            pendingSubrangeIdx = 0;
            goto Serving;
        }
    }

    fun IsStillAssigned(sh: int): bool {
        return sh in validOwnershipEpochs;
    }

    fun FindOwnershipRecord(key: int): tAccessHandle {
        var r: int;
        foreach (r in keys(ownershipRecordMap)) {
            if (key >= r && key < ownershipRecordMap[r].range.high) {
                return (opType = 0, writeOverlap = false,
                        hasOwnershipRecord = true, ownershipRecord = ownershipRecordMap[r],
                        client = this, value = 0);
            }
        }
        return (opType = 0, writeOverlap = false,
                hasOwnershipRecord = false,
                ownershipRecord = (range = (low = 0, high = 0), versionId = 0, ownershipEpoch = 0),
                client = this, value = 0);
    }

    // Algorithm 4: SatisfiesLSI
    fun SatisfiesLSI(op: tAccessHandle): bool {
        // Cond 1: previous owner protection -- must have an ownershipRecord
        if (!op.hasOwnershipRecord) {
            print format("CacheNode {0}: LSI FAIL cond1: no ownershipRecord", podId);
            return false;
        }
        // Cond 2: current owner protection -- no concurrent write overlap
        if (op.writeOverlap) {
            print format("CacheNode {0}: LSI FAIL cond2: writeOverlap", podId);
            return false;
        }
        // Cond 3: future owner protection -- IsStillAssigned(ownershipEpoch)
        if (!IsStillAssigned(op.ownershipRecord.ownershipEpoch)) {
            print format("CacheNode {0}: LSI FAIL cond3: not still assigned (sh={1})", podId, op.ownershipRecord.ownershipEpoch);
            return false;
        }
        return true;
    }

    // Clear ownershipRecords for sub-ranges already installed during current round
    fun ClearPartialOwnershipRecords() {
        var i: int;
        var rLow: int;
        i = 0;
        while (i < pendingSubrangeIdx) {
            rLow = pendingSubranges[i].low;
            if (rLow in ownershipRecordMap) {
                ownershipRecordMap -= (rLow);
            }
            i = i + 1;
        }
    }

    state Serving {
        // Ignore stale SyncOwnershipDone and FetchShardLayoutResp from previous transitions
        ignore eSyncOwnershipDone, eFetchShardLayoutResp;

        on eOwnershipGrant do (req: (range: tKeyRange, ownershipEpoch: int)) {
            if (req.range.low in ownershipRecordMap) { ownershipRecordMap -= (req.range.low); }
            // Update IsStillAssigned
            validOwnershipEpochs += (req.ownershipEpoch);
            pendingOwnedRange  = req.range;
            pendingOwnershipEpoch = req.ownershipEpoch;
            isRetryWrite       = false;
            print format("CacheNode {0}: HANDLE_NEW_RANGE range=[{1},{2}) sh={3}",
                         podId, req.range.low, req.range.high, req.ownershipEpoch);
            send db, eFetchShardLayout, (caller = this, range = req.range);
            goto FetchingLayout;
        }

        on eOwnershipRevoke do (req: (range: tKeyRange, ownershipEpoch: int, ackTo: machine)) {
            if (req.range.low in ownershipRecordMap) { ownershipRecordMap -= (req.range.low); }
            // Update IsStillAssigned
            if (req.ownershipEpoch in validOwnershipEpochs) {
                validOwnershipEpochs -= (req.ownershipEpoch);
            }
            send req.ackTo, eOwnershipRevokeAck, (range = req.range, ownershipEpoch = req.ownershipEpoch);
            print format("CacheNode {0}: revoked range=[{1},{2}) sh={3}", podId, req.range.low, req.range.high, req.ownershipEpoch);
        }

        // Algorithm 3: Read path
        on eClientRead do (req: (client: machine, key: int)) {
            var cEntry: tCachedValue;
            var writeOverlap: bool;
            var ops: seq[tAccessHandle];
            var j: int;
            var gh: tAccessHandle;
            var opHandle: tAccessHandle;
            // Cache hit check: Algorithm 3, lines 2-5
            if (req.key in cacheMap) {
                cEntry = cacheMap[req.key];
                if (IsStillAssigned(cEntry.ownershipRecord.ownershipEpoch)) {
                    announce eMonitorCacheHit, (key = req.key, value = cEntry.value, podId = podId);
                    print format("CacheNode {0}: CACHE HIT key={1} value={2}",
                                 podId, req.key, cEntry.value);
                    send req.client, eReadResp, (key = req.key, value = cEntry.value, fromCache = true);
                    return;
                }
                cacheMap -= (req.key);
                print format("CacheNode {0}: evicted stale cache key={1}", podId, req.key);
            }
            // Cache miss: go to storage backend
            writeOverlap = false;
            if (req.key in opMap) {
                ops = opMap[req.key];
                j = 0;
                while (j < sizeof(ops)) {
                    if (ops[j].opType == 1) { writeOverlap = true; }
                    j = j + 1;
                }
            }
            gh = FindOwnershipRecord(req.key);
            opHandle = (opType = 0, writeOverlap = writeOverlap,
                        hasOwnershipRecord = gh.hasOwnershipRecord, ownershipRecord = gh.ownershipRecord,
                        client = req.client, value = 0);
            if (!(req.key in opMap)) { opMap[req.key] = default(seq[tAccessHandle]); }
            opMap[req.key] += (sizeof(opMap[req.key]), opHandle);
            print format("CacheNode {0}: CACHE MISS key={1} -> storage backend (writeOverlap={2})",
                         podId, req.key, writeOverlap);
            send db, eStorageRead, (caller = this, key = req.key);
        }

        on eStorageReadResp do (resp: (key: int, value: int)) {
            var opHandle: tAccessHandle;
            var cEntry: tCachedValue;
            var ops: seq[tAccessHandle];
            // Guard against stale response after crash/restart
            if (!(resp.key in opMap)) {
                print format("CacheNode {0}: stale DbReadResp key={1} after crash, ignoring", podId, resp.key);
                return;
            }
            ops = opMap[resp.key];
            opHandle = ops[0];
            ops -= (0);
            if (sizeof(ops) == 0) {
                opMap -= (resp.key);
            } else {
                opMap[resp.key] = ops;
            }
            cEntry = (ownershipRecord = opHandle.ownershipRecord, value = resp.value);
            cacheMap[resp.key] = cEntry;
            if (!SatisfiesLSI(opHandle)) {
                cacheMap -= (resp.key);
                print format("CacheNode {0}: read key={1} NOT cacheable (LSI failed)", podId, resp.key);
            } else {
                print format("CacheNode {0}: read key={1} cached value={2}", podId, resp.key, resp.value);
            }
            send opHandle.client, eReadResp, (key = resp.key, value = resp.value, fromCache = false);
        }

        // Algorithm 2: Write path
        on eClientWrite do (req: (client: machine, key: int, value: int)) {
            var gh: tAccessHandle;
            var ops: seq[tAccessHandle];
            var newOps: seq[tAccessHandle];
            var opItem: tAccessHandle;
            var j: int;
            var ops2: seq[tAccessHandle];
            var j2: int;
            var writeOverlap: bool;
            var opHandle: tAccessHandle;
            gh = FindOwnershipRecord(req.key);

            writeOverlap = false;
            // Algorithm 2, line 5: must have ownershipRecord AND IsStillAssigned
            if (!gh.hasOwnershipRecord || !IsStillAssigned(gh.ownershipRecord.ownershipEpoch)) {
                print format("CacheNode {0}: WRITE REJECTED key={1} no fencing token or not assigned", podId, req.key);
                send req.client, eWriteResp, (key = req.key, success = false);
                return;
            }
            if (req.key in cacheMap) { cacheMap -= (req.key); }
            // Mark write overlap on existing ops for this key
            if (req.key in opMap) {
                ops = opMap[req.key];
                newOps = default(seq[tAccessHandle]);
                j = 0;
                while (j < sizeof(ops)) {
                    opItem = ops[j];
                    opItem.writeOverlap = true;
                    newOps += (sizeof(newOps), opItem);
                    j = j + 1;
                }
                opMap[req.key] = newOps;

                //write path algorithm2 line 10 concurrent write request
                ops2 = opMap[req.key];
                j2 = 0;
                while (j2 < sizeof(ops2)) {
                    if (ops2[j2].opType == 1) { writeOverlap = true; }
                    j2 = j2 + 1;
                }
            }

            opHandle = (opType = 1, writeOverlap = writeOverlap,
                        hasOwnershipRecord = gh.hasOwnershipRecord, ownershipRecord = gh.ownershipRecord,
                        client = req.client, value = req.value);
            if (!(req.key in opMap)) { opMap[req.key] = default(seq[tAccessHandle]); }
            opMap[req.key] += (sizeof(opMap[req.key]), opHandle);
            print format("CacheNode {0}: WRITE key={1} value={2} versionId={3}",
                         podId, req.key, req.value, gh.ownershipRecord.versionId);
            send db, eStorageWrite, (caller = this, key = req.key, value = req.value,
                                 versionId = gh.ownershipRecord.versionId, rangeLow = gh.ownershipRecord.range.low);
        }

        // Algorithm 2: Write response
        on eStorageWriteResp do (resp: (key: int, success: bool, value: int)) {
            var opHandle: tAccessHandle;
            var cEntry: tCachedValue;
            var r: int;
            var foundRange: bool;
            var ops: seq[tAccessHandle];
            // Guard against stale response after crash/restart
            if (!(resp.key in opMap)) {
                print format("CacheNode {0}: stale DbWriteResp key={1} after crash, ignoring", podId, resp.key);
                return;
            }
            ops = opMap[resp.key];
            opHandle = ops[0];
            ops -= (0);
            if (sizeof(ops) == 0) {
                opMap -= (resp.key);
            } else {
                opMap[resp.key] = ops;
            }
            if (resp.success) {
                cEntry = (ownershipRecord = opHandle.ownershipRecord, value = resp.value);
                cacheMap[resp.key] = cEntry;
                if (!SatisfiesLSI(opHandle)) {
                    cacheMap -= (resp.key);
                    print format("CacheNode {0}: write key={1} LSI failed, evicted", podId, resp.key);
                } else {
                    print format("CacheNode {0}: write key={1} SUCCESS cached", podId, resp.key);
                }
                send opHandle.client, eWriteResp, (key = resp.key, success = true);
            } else {
                // Algorithm 2, lines 19-24: ownershipRecord mismatch -> refetch split points and retry
                foundRange = false;
                pendingOwnedRange = (low = 0, high = 0);
                pendingOwnershipEpoch = 0;
                // Find the fence's range for this key
                foreach (r in keys(ownershipRecordMap)) {
                    if (resp.key >= r && resp.key < ownershipRecordMap[r].range.high) {
                        pendingOwnedRange  = ownershipRecordMap[r].range;
                        pendingOwnershipEpoch = ownershipRecordMap[r].ownershipEpoch;
                        ownershipRecordMap -= (r);
                        foundRange = true;
                    }
                }
                if (!foundRange) {
                    // Lost ownershipRecord context: cannot safely retry.
                    isRetryWrite = false;
                    print format("CacheNode {0}: VersionMismatch key={1}, no matching ownershipRecord range, returning error",
                                 podId, resp.key);
                    send opHandle.client, eWriteResp, (key = resp.key, success = false);
                } else if (IsStillAssigned(pendingOwnershipEpoch)) {
                    // Still assigned: save retry info, refetch split points, reinstall fences
                    isRetryWrite = true;
                    retryKey     = resp.key;
                    retryValue   = opHandle.value;
                    retryClient  = opHandle.client;
                    print format("CacheNode {0}: VersionMismatch key={1}, refetching split points",
                                 podId, resp.key);
                    send db, eFetchShardLayout, (caller = this, range = pendingOwnedRange);
                    goto FetchingLayout;
                } else {
                    // No longer assigned: return error
                    isRetryWrite = false;
                    print format("CacheNode {0}: VersionMismatch key={1}, not assigned, returning error",
                                 podId, resp.key);
                    send opHandle.client, eWriteResp, (key = resp.key, success = false);
                }
            }
        }

        on ePodRestart do {
            print format("CacheNode {0}: RESTARTING", podId);
            goto Crashed;
        }
    }

    // New state: fetching split points from storage backend before installing fences
    state FetchingLayout {
        defer eClientRead, eClientWrite;
        ignore eSyncOwnershipDone;  // stale from previous round

        // Handle in-flight DB responses (stale)
        on eStorageReadResp do (resp: (key: int, value: int)) {
            var opHandle: tAccessHandle;
            var ops: seq[tAccessHandle];
            if (!(resp.key in opMap)) {
                print format("CacheNode {0}: stale DbReadResp key={1} during FetchingLayout", podId, resp.key);
                return;
            }
            ops = opMap[resp.key];
            opHandle = ops[0];
            ops -= (0);
            if (sizeof(ops) == 0) {
                opMap -= (resp.key);
            } else {
                opMap[resp.key] = ops;
            }
            send opHandle.client, eReadResp, (key = resp.key, value = resp.value, fromCache = false);
            print format("CacheNode {0}: in-flight DbReadResp key={1} during FetchingLayout (not cached)", podId, resp.key);
        }

        on eStorageWriteResp do (resp: (key: int, success: bool, value: int)) {
            var opHandle: tAccessHandle;
            var ops: seq[tAccessHandle];
            if (!(resp.key in opMap)) {
                print format("CacheNode {0}: stale DbWriteResp key={1} during FetchingLayout", podId, resp.key);
                return;
            }
            ops = opMap[resp.key];
            opHandle = ops[0];
            ops -= (0);
            if (sizeof(ops) == 0) {
                opMap -= (resp.key);
            } else {
                opMap[resp.key] = ops;
            }
            send opHandle.client, eWriteResp, (key = resp.key, success = resp.success);
            print format("CacheNode {0}: in-flight DbWriteResp key={1} during FetchingLayout", podId, resp.key);
        }

        on eFetchShardLayoutResp do (resp: (subRanges: seq[tKeyRange])) {
            pendingSubranges  = resp.subRanges;
            pendingSubrangeIdx     = 0;
            pendingRange      = pendingSubranges[0];
            pendingVersionId    = localVersionCounter;
            localVersionCounter = localVersionCounter + 1;
            print format("CacheNode {0}: got {1} sub-ranges, installing ownershipRecord for sub-range[0]=[{2},{3}) versionId={4}",
                         podId, sizeof(pendingSubranges), pendingRange.low, pendingRange.high, pendingVersionId);
            send db, eSyncOwnership, (caller = this, range = pendingRange, versionId = pendingVersionId);
            goto InstallingFences;
        }

        on eOwnershipRevoke do (req: (range: tKeyRange, ownershipEpoch: int, ackTo: machine)) {
            if (req.range.low in ownershipRecordMap) { ownershipRecordMap -= (req.range.low); }
            if (req.ownershipEpoch in validOwnershipEpochs) {
                validOwnershipEpochs -= (req.ownershipEpoch);
            }
            send req.ackTo, eOwnershipRevokeAck, (range = req.range, ownershipEpoch = req.ownershipEpoch);
            if (isRetryWrite) {
                send retryClient, eWriteResp, (key = retryKey, success = false);
                isRetryWrite = false;
            }
            print format("CacheNode {0}: revoked during FetchingLayout sh={1}", podId, req.ownershipEpoch);
            goto Serving;
        }

        on eOwnershipGrant do (req: (range: tKeyRange, ownershipEpoch: int)) {
            validOwnershipEpochs += (req.ownershipEpoch);
            // New grant supersedes: restart with new range
            isRetryWrite       = false;
            pendingOwnedRange  = req.range;
            pendingOwnershipEpoch = req.ownershipEpoch;
            print format("CacheNode {0}: new grant during FetchingLayout, sh={1}, re-fetching",
                         podId, req.ownershipEpoch);
            send db, eFetchShardLayout, (caller = this, range = req.range);
        }

        on ePodRestart do {
            if (isRetryWrite) {
                send retryClient, eWriteResp, (key = retryKey, success = false);
                isRetryWrite = false;
            }
            print format("CacheNode {0}: RESTARTING during FetchingLayout", podId);
            goto Crashed;
        }
    }

    // Renamed from WaitingForGuard: installing fences for each sub-range
    state InstallingFences {
        defer eClientRead, eClientWrite;
        ignore eFetchShardLayoutResp;  // stale from previous FetchingLayout

        // Handle in-flight DB responses that were sent before we entered InstallingFences
        on eStorageReadResp do (resp: (key: int, value: int)) {
            var opHandle: tAccessHandle;
            var ops: seq[tAccessHandle];
            // Guard is being reinstalled; don't cache, just respond to client
            if (!(resp.key in opMap)) {
                print format("CacheNode {0}: stale DbReadResp key={1} during ownershipRecord install", podId, resp.key);
                return;
            }
            ops = opMap[resp.key];
            opHandle = ops[0];
            ops -= (0);
            if (sizeof(ops) == 0) {
                opMap -= (resp.key);
            } else {
                opMap[resp.key] = ops;
            }
            send opHandle.client, eReadResp, (key = resp.key, value = resp.value, fromCache = false);
            print format("CacheNode {0}: in-flight DbReadResp key={1} during ownershipRecord install (not cached)", podId, resp.key);
        }

        on eStorageWriteResp do (resp: (key: int, success: bool, value: int)) {
            var opHandle: tAccessHandle;
            var ops: seq[tAccessHandle];
            // Guard is being reinstalled; don't cache, respond to client
            if (!(resp.key in opMap)) {
                print format("CacheNode {0}: stale DbWriteResp key={1} during ownershipRecord install", podId, resp.key);
                return;
            }
            ops = opMap[resp.key];
            opHandle = ops[0];
            ops -= (0);
            if (sizeof(ops) == 0) {
                opMap -= (resp.key);
            } else {
                opMap[resp.key] = ops;
            }
            send opHandle.client, eWriteResp, (key = resp.key, success = resp.success);
            print format("CacheNode {0}: in-flight DbWriteResp key={1} during ownershipRecord install", podId, resp.key);
        }

        // Algorithm 1: 3-way SyncOwnership response
        on eSyncOwnershipDone do (resp: (rangeLow: int, status: int)) {
            var gh: tOwnershipRecord;
            if (resp.status == 0) {
                // Success: install ownershipRecord for current sub-range
                if (!IsStillAssigned(pendingOwnershipEpoch)) {
                    // No longer assigned: abandon
                    print format("CacheNode {0}: SyncOwnership succeeded but no longer assigned sh={1}, abandoning",
                                 podId, pendingOwnershipEpoch);
                    ClearPartialOwnershipRecords();
                    if (isRetryWrite) {
                        send retryClient, eWriteResp, (key = retryKey, success = false);
                        isRetryWrite = false;
                    }
                    goto Serving;
                }
                gh = (range = pendingRange, versionId = pendingVersionId, ownershipEpoch = pendingOwnershipEpoch);
                ownershipRecordMap[pendingRange.low] = gh;
                print format("CacheNode {0}: FenceMap[{1},{2}) = versionId={3} sh={4}",
                             podId, pendingRange.low, pendingRange.high, pendingVersionId, pendingOwnershipEpoch);
                // Advance to next sub-range
                pendingSubrangeIdx = pendingSubrangeIdx + 1;
                if (pendingSubrangeIdx < sizeof(pendingSubranges)) {
                    // More sub-ranges to install
                    pendingRange      = pendingSubranges[pendingSubrangeIdx];
                    pendingVersionId    = localVersionCounter;
                    localVersionCounter = localVersionCounter + 1;
                    print format("CacheNode {0}: installing ownershipRecord for sub-range[{1}]=[{2},{3}) versionId={4}",
                                 podId, pendingSubrangeIdx, pendingRange.low, pendingRange.high, pendingVersionId);
                    send db, eSyncOwnership, (caller = this, range = pendingRange, versionId = pendingVersionId);
                } else {
                    // All sub-ranges done
                    print format("CacheNode {0}: all {1} sub-range fences installed", podId, sizeof(pendingSubranges));
                    if (isRetryWrite) {
                        isRetryWrite = false;
                        send this, eClientWrite, (client = retryClient, key = retryKey, value = retryValue);
                    }
                    goto Serving;
                }
            } else if (resp.status == 1) {
                // LayoutChanged: refetch split points and restart
                if (!IsStillAssigned(pendingOwnershipEpoch)) {
                    print format("CacheNode {0}: LayoutChanged but no longer assigned, abandoning", podId);
                    ClearPartialOwnershipRecords();
                    if (isRetryWrite) {
                        send retryClient, eWriteResp, (key = retryKey, success = false);
                        isRetryWrite = false;
                    }
                    goto Serving;
                }
                // Clear any partially installed fences
                ClearPartialOwnershipRecords();
                print format("CacheNode {0}: LayoutChanged, refetching split points for [{1},{2})",
                             podId, pendingOwnedRange.low, pendingOwnedRange.high);
                send db, eFetchShardLayout, (caller = this, range = pendingOwnedRange);
                goto FetchingLayout;
            } else {
                // Timeout (status == 2): retry same sub-range with fresh versionId
                if (!IsStillAssigned(pendingOwnershipEpoch)) {
                    print format("CacheNode {0}: SyncOwnership timeout but no longer assigned, abandoning", podId);
                    ClearPartialOwnershipRecords();
                    if (isRetryWrite) {
                        send retryClient, eWriteResp, (key = retryKey, success = false);
                        isRetryWrite = false;
                    }
                    goto Serving;
                }
                pendingVersionId    = localVersionCounter;
                localVersionCounter = localVersionCounter + 1;
                print format("CacheNode {0}: SyncOwnership TIMEOUT, retrying sub-range[{1}] with versionId={2}",
                             podId, pendingSubrangeIdx, pendingVersionId);
                send db, eSyncOwnership, (caller = this, range = pendingRange, versionId = pendingVersionId);
            }
        }

        on eOwnershipRevoke do (req: (range: tKeyRange, ownershipEpoch: int, ackTo: machine)) {
            if (req.range.low in ownershipRecordMap) { ownershipRecordMap -= (req.range.low); }
            if (req.ownershipEpoch in validOwnershipEpochs) {
                validOwnershipEpochs -= (req.ownershipEpoch);
            }
            send req.ackTo, eOwnershipRevokeAck, (range = req.range, ownershipEpoch = req.ownershipEpoch);
            // If we were retrying a write for this range, fail it
            if (isRetryWrite) {
                send retryClient, eWriteResp, (key = retryKey, success = false);
                isRetryWrite = false;
            }
            print format("CacheNode {0}: revoked during ownershipRecord install sh={1}", podId, req.ownershipEpoch);
            goto Serving;
        }

        on eOwnershipGrant do (req: (range: tKeyRange, ownershipEpoch: int)) {
            validOwnershipEpochs += (req.ownershipEpoch);
            // Reset retry state: new grant supersedes old pending
            isRetryWrite       = false;
            pendingOwnedRange  = req.range;
            pendingOwnershipEpoch = req.ownershipEpoch;
            print format("CacheNode {0}: new grant during InstallingFences, sh={1}, re-fetching split points",
                         podId, req.ownershipEpoch);
            send db, eFetchShardLayout, (caller = this, range = req.range);
            goto FetchingLayout;
        }

        on ePodRestart do {
            if (isRetryWrite) {
                send retryClient, eWriteResp, (key = retryKey, success = false);
                isRetryWrite = false;
            }
            print format("CacheNode {0}: RESTARTING during ownershipRecord install", podId);
            goto Crashed;
        }
    }

    state Crashed {
        entry {
            ownershipRecordMap          = default(map[int, tOwnershipRecord]);
            cacheMap          = default(map[int, tCachedValue]);
            opMap             = default(map[int, seq[tAccessHandle]]);
            validOwnershipEpochs = default(set[int]);
            isRetryWrite      = false;
            pendingSubranges  = default(seq[tKeyRange]);
            pendingSubrangeIdx     = 0;
            print format("CacheNode {0}: memory cleared", podId);
            goto Serving;
        }
    }
}
# EVOLVE-BLOCK-END
