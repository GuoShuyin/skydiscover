event eProxyStep;
event eAcquireLease: (requester: machine, key: int, podId: int);
event eLeaseGranted: (key: int);
event eRevokeLease: (key: int);
event eReleaseLease: (requester: machine, key: int, podId: int);

machine StorageProxy {
  var db: machine;

  // Queue of storage-facing requests waiting to be forwarded to storage.
  // Each element: (caller: original requester CacheNode, key, value (for writes), isWrite, podId)
  var reqQueue: seq[(caller: machine, key: int, value: int, isWrite: bool, podId: int)];
  var inflight: bool;
  var inflightReq: (caller: machine, key: int, value: int, isWrite: bool, podId: int);

  // Simple per-key exclusive lease coordination embedded in the proxy.
  var leaseHolder: map[int, machine];
  var leaseHolderPod: map[int, int];
  var leaseWaiters: map[int, seq[(requester: machine, podId: int)]];

  start state Init {
    entry (p: (db: machine)) {
      db = p.db;
      reqQueue = default(seq[(caller: machine, key: int, value: int, isWrite: bool, podId: int)]);
      inflight = false;
      inflightReq = default((caller: machine, key: int, value: int, isWrite: bool, podId: int));
      leaseHolder = default(map[int, machine]);
      leaseHolderPod = default(map[int, int]);
      leaseWaiters = default(map[int, seq[(requester: machine, podId: int)]]);
      send this, eProxyStep;
      goto Ready;
    }
  }

  state Ready {
    // CacheNode -> Proxy requests for storage; enqueue and announce enqueue
    on eStorageRead do (r: (caller: machine, key: int, podId: int)) {
      var rec: (caller: machine, key: int, value: int, isWrite: bool, podId: int);
      var pending: int;
      rec = (caller = r.caller, key = r.key, value = 0, isWrite = false, podId = r.podId);
      reqQueue += (sizeof(reqQueue), rec);
      pending = sizeof(reqQueue);
      send this, eMonitorProxyEnqueue, (key = r.key, podId = r.podId, isWrite = false, pending = pending);
    }

    on eStorageWrite do (w: (caller: machine, key: int, value: int, podId: int)) {
      var rec: (caller: machine, key: int, value: int, isWrite: bool, podId: int);
      var pending: int;
      rec = (caller = w.caller, key = w.key, value = w.value, isWrite = true, podId = w.podId);
      reqQueue += (sizeof(reqQueue), rec);
      pending = sizeof(reqQueue);
      send this, eMonitorProxyEnqueue, (key = w.key, podId = w.podId, isWrite = true, pending = pending);
    }

    // Proxy scheduling step: nondeterministically forward or hold when there are pending requests
    on eProxyStep do {
      var c: int;
      var pending: int;
      pending = sizeof(reqQueue);
      if (!inflight && pending > 0) {
        c = choose(2);
        if (c == 0) {
          // Congestion/no-op step
          send this, eMonitorProxyHold, (pending = pending);
        } else {
          // Forward one queued request (take the head of the queue)
          inflightReq = reqQueue[0];
          reqQueue -= (0);
          send this, eMonitorProxyForward, (key = inflightReq.key, podId = inflightReq.podId, isWrite = inflightReq.isWrite, pending = sizeof(reqQueue));
          if (inflightReq.isWrite) {
            send db, eStorageWrite, (caller = this, key = inflightReq.key, value = inflightReq.value, podId = inflightReq.podId);
          } else {
            send db, eStorageRead, (caller = this, key = inflightReq.key, podId = inflightReq.podId);
          }
          inflight = true;
        }
      } else {
        if (pending > 0) {
          send this, eMonitorProxyHold, (pending = pending);
        }
      }
      // keep stepping
      send this, eProxyStep;
    }

    // Responses from storage; deliver back to original requester and announce delivery
    on eStorageReadResp do (resp: (key: int, value: int)) {
      var k: int;
      var v: int;
      k = resp.key;
      v = resp.value;
      if (inflight && !inflightReq.isWrite) {
        send inflightReq.caller, eStorageReadResp, (key = k, value = v);
        send this, eMonitorProxyResponseDelivered, (key = k, podId = inflightReq.podId, isWrite = false);
        inflight = false;
        inflightReq = default((caller: machine, key: int, value: int, isWrite: bool, podId: int));
      }
    }

    on eStorageWriteResp do (resp: (key: int, success: bool, value: int)) {
      var k: int;
      var ok: bool;
      var v: int;
      k = resp.key;
      ok = resp.success;
      v = resp.value;
      if (inflight && inflightReq.isWrite) {
        send inflightReq.caller, eStorageWriteResp, (key = k, success = ok, value = v);
        send this, eMonitorProxyResponseDelivered, (key = k, podId = inflightReq.podId, isWrite = true);
        inflight = false;
        inflightReq = default((caller: machine, key: int, value: int, isWrite: bool, podId: int));
      }
    }

    // Simple exclusive lease management (not storage-facing)
    on eAcquireLease do (a: (requester: machine, key: int, podId: int)) {
      var k: int;
      var r: machine;
      var p: int;
      var waitQ: seq[(requester: machine, podId: int)];
      k = a.key;
      r = a.requester;
      p = a.podId;

      if (k in leaseHolder) {
        if (leaseHolder[k] == r) {
          // already holder, re-grant
          send r, eLeaseGranted, (key = k);
        } else {
          // request revoke from current holder and enqueue requester
          send leaseHolder[k], eRevokeLease, (key = k);
          if (!(k in leaseWaiters)) {
            leaseWaiters[k] = default(seq[(requester: machine, podId: int)]);
          }
          waitQ = leaseWaiters[k];
          waitQ += (sizeof(waitQ), (requester = r, podId = p));
          leaseWaiters[k] = waitQ;
        }
      } else {
        // free, grant to requester
        leaseHolder[k] = r;
        leaseHolderPod[k] = p;
        send r, eLeaseGranted, (key = k);
      }
    }

    on eReleaseLease do (rel: (requester: machine, key: int, podId: int)) {
      var k: int;
      var r: machine;
      var waitQ: seq[(requester: machine, podId: int)];
      var nextReq: (requester: machine, podId: int);
      k = rel.key;
      r = rel.requester;

      if (k in leaseHolder && leaseHolder[k] == r) {
        leaseHolder -= (k);
        leaseHolderPod -= (k);
        if (k in leaseWaiters) {
          waitQ = leaseWaiters[k];
          if (sizeof(waitQ) > 0) {
            nextReq = waitQ[0];
            waitQ -= (0);
            leaseWaiters[k] = waitQ;
            leaseHolder[k] = nextReq.requester;
            leaseHolderPod[k] = nextReq.podId;
            send nextReq.requester, eLeaseGranted, (key = k);
            if (sizeof(waitQ) == 0) {
              leaseWaiters -= (k);
            }
          } else {
            leaseWaiters -= (k);
          }
        }
      }
    }
  }
}

machine CacheNode {
  var proxy: machine;
  var podId: int;

  // Local cache and lease tracking
  var cache: map[int, int];
  var leaseHeld: set[int];
  var leasePending: set[int];
  var revokePending: set[int];

  // Pending client reads per key
  var pendingReads: map[int, set[machine]];

  // Pending client writes per key (queue) and current inflight write per key
  var writeQueues: map[int, seq[(client: machine, value: int)]];
  var writingKeys: set[int];
  var inflightWriteClient: map[int, machine];
  var inflightWriteValue: map[int, int];

  start state Init {
    entry (p: (proxy: machine, podId: int)) {
      proxy = p.proxy;
      podId = p.podId;
      cache = default(map[int, int]);
      leaseHeld = default(set[int]);
      leasePending = default(set[int]);
      revokePending = default(set[int]);
      pendingReads = default(map[int, set[machine]]);
      writeQueues = default(map[int, seq[(client: machine, value: int)]]);
      writingKeys = default(set[int]);
      inflightWriteClient = default(map[int, machine]);
      inflightWriteValue = default(map[int, int]);
      goto Ready;
    }
  }

  state Ready {
    on eClientRead do (req: (client: machine, key: int)) {
      var k: int;
      var c: machine;
      var waiters: set[machine];
      k = req.key;
      c = req.client;

      if ((k in leaseHeld) && (k in cache)) {
        // Serve from cache safely under exclusive lease
        send c, eReadResp, (key = k, value = cache[k], fromCache = true);
        return;
      }

      // Track pending reader
      if (!(k in pendingReads)) {
        pendingReads[k] = default(set[machine]);
      }
      waiters = pendingReads[k];
      waiters += (c);
      pendingReads[k] = waiters;

      // Ensure we hold a lease; if not, acquire
      if (!(k in leaseHeld) && !(k in leasePending)) {
        leasePending += (k);
        send proxy, eAcquireLease, (requester = this, key = k, podId = podId);
      } else if ((k in leaseHeld) && !(k in cache)) {
        // We hold lease but need initial value; fetch from storage
        send this, eMonitorProxyRequestIssued, (key = k, podId = podId, isWrite = false);
        send proxy, eStorageRead, (caller = this, key = k, podId = podId);
      }
    }

    on eClientWrite do (req: (client: machine, key: int, value: int)) {
      var k: int;
      var q: seq[(client: machine, value: int)];
      var cur: (client: machine, value: int);
      k = req.key;

      if (!(k in writeQueues)) {
        writeQueues[k] = default(seq[(client: machine, value: int)]);
      }
      q = writeQueues[k];
      q += (sizeof(q), (client = req.client, value = req.value));
      writeQueues[k] = q;

      // Ensure we hold lease or start acquiring
      if (!(k in leaseHeld) && !(k in leasePending)) {
        leasePending += (k);
        send proxy, eAcquireLease, (requester = this, key = k, podId = podId);
      }

      // If we already hold lease and not currently writing this key, issue write
      if ((k in leaseHeld) && !(k in writingKeys)) {
        // Dequeue head
        cur = writeQueues[k][0];
        writeQueues[k] -= (0);
        writingKeys += (k);
        inflightWriteClient[k] = cur.client;
        inflightWriteValue[k] = cur.value;
        send this, eMonitorProxyRequestIssued, (key = k, podId = podId, isWrite = true);
        send proxy, eStorageWrite, (caller = this, key = k, value = cur.value, podId = podId);
      }
    }

    // Lease granted: initialize cache by reading storage if needed and/or issue pending writes
    on eLeaseGranted do (g: (key: int)) {
      var k: int;
      var q: seq[(client: machine, value: int)];
      var cur: (client: machine, value: int);
      k = g.key;

      leaseHeld += (k);
      if (k in leasePending) {
        leasePending -= (k);
      }

      // If there are pending writes, issue first write
      if ((k in writeQueues) && (sizeof(writeQueues[k]) > 0) && !(k in writingKeys)) {
        q = writeQueues[k];
        cur = q[0];
        q -= (0);
        writeQueues[k] = q;
        writingKeys += (k);
        inflightWriteClient[k] = cur.client;
        inflightWriteValue[k] = cur.value;
        send this, eMonitorProxyRequestIssued, (key = k, podId = podId, isWrite = true);
        send proxy, eStorageWrite, (caller = this, key = k, value = cur.value, podId = podId);
      } else {
        // No pending writes: if we have pending readers or cache miss, fetch latest from storage once
        if ((k in pendingReads) || !(k in cache)) {
          send this, eMonitorProxyRequestIssued, (key = k, podId = podId, isWrite = false);
          send proxy, eStorageRead, (caller = this, key = k, podId = podId);
        }
      }
    }

    // Lease revoke: stop serving from cache, and release when safe
    on eRevokeLease do (r: (key: int)) {
      var k: int;
      k = r.key;
      revokePending += (k);
      if (k in leaseHeld) {
        leaseHeld -= (k);
      }
      // Clear local cached value to be conservative
      if (k in cache) {
        cache -= (k);
      }
      // If no write in-flight, ack release immediately
      if (!(k in writingKeys)) {
        send proxy, eReleaseLease, (requester = this, key = k, podId = podId);
        if (k in revokePending) {
          revokePending -= (k);
        }
      }
    }

    // Storage read response routed via proxy
    on eStorageReadResp do (resp: (key: int, value: int)) {
      var k: int;
      var v: int;
      var waiters: set[machine];
      var cli: machine;
      k = resp.key;
      v = resp.value;

      cache[k] = v;

      if (k in pendingReads) {
        waiters = pendingReads[k];
        foreach (cli in waiters) {
          send cli, eReadResp, (key = k, value = v, fromCache = false);
        }
        pendingReads -= (k);
      }
    }

    // Storage write response routed via proxy
    on eStorageWriteResp do (resp: (key: int, success: bool, value: int)) {
      var k: int;
      var ok: bool;
      var v: int;
      var nextQ: seq[(client: machine, value: int)];
      var cur: (client: machine, value: int);
      var cli: machine;
      k = resp.key;
      ok = resp.success;
      v = resp.value;

      // Update cache with committed value
      cache[k] = v;

      if (k in inflightWriteClient) {
        cli = inflightWriteClient[k];
        send cli, eWriteResp, (key = k, success = ok);
        inflightWriteClient -= (k);
      }
      if (k in inflightWriteValue) {
        inflightWriteValue -= (k);
      }
      if (k in writingKeys) {
        writingKeys -= (k);
      }

      // Serve any pending readers from cache (we still have/need lease)
      if (k in pendingReads) {
        var waiters: set[machine];
        var rc: machine;
        waiters = pendingReads[k];
        foreach (rc in waiters) {
          // From cache because we hold the lease and just updated to committed value
          send rc, eReadResp, (key = k, value = cache[k], fromCache = true);
        }
        pendingReads -= (k);
      }

      // Issue next write if queued
      if ((k in writeQueues) && (sizeof(writeQueues[k]) > 0)) {
        nextQ = writeQueues[k];
        cur = nextQ[0];
        nextQ -= (0);
        writeQueues[k] = nextQ;
        writingKeys += (k);
        inflightWriteClient[k] = cur.client;
        inflightWriteValue[k] = cur.value;
        send this, eMonitorProxyRequestIssued, (key = k, podId = podId, isWrite = true);
        send proxy, eStorageWrite, (caller = this, key = k, value = cur.value, podId = podId);
      } else {
        // If a revoke is pending and no more writes, release lease now
        if (k in revokePending) {
          send proxy, eReleaseLease, (requester = this, key = k, podId = podId);
          revokePending -= (k);
        }
      }
    }
  }
}