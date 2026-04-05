machine StorageProxy {
  type tProxyReq = (opId: int, caller: machine, key: int, value: int, isWrite: bool, podId: int);

  var db: machine;
  var nextOpId: int;
  var pending: seq[int]; // queue of opIds
  var reqs: map[int, tProxyReq]; // opId -> request
  var inflightPerKey: map[int, seq[int]]; // key -> seq of opIds forwarded to storage and awaiting response

  event eProxyStep;

  start state Init {
    entry (p: (db: machine)) {
      db = p.db;
      nextOpId = 1;
      goto Ready;
    }
  }

  state Ready {
    on eStorageRead do (r: (caller: machine, key: int, podId: int)) {
      var opId: int;
      var rec: tProxyReq;
      var qsz: int;

      opId = nextOpId;
      nextOpId = nextOpId + 1;
      rec = (opId = opId, caller = r.caller, key = r.key, value = 0, isWrite = false, podId = r.podId);
      reqs[opId] = rec;

      // enqueue
      pending += (sizeof(pending), opId);
      qsz = sizeof(pending);
      announce eMonitorProxyEnqueue, (key = r.key, podId = r.podId, isWrite = false, pending = qsz);

      // drive the proxy pump
      send this, eProxyStep;
    }

    on eStorageWrite do (w: (caller: machine, key: int, value: int, podId: int)) {
      var opId: int;
      var rec: tProxyReq;
      var qsz: int;

      opId = nextOpId;
      nextOpId = nextOpId + 1;
      rec = (opId = opId, caller = w.caller, key = w.key, value = w.value, isWrite = true, podId = w.podId);
      reqs[opId] = rec;

      // enqueue
      pending += (sizeof(pending), opId);
      qsz = sizeof(pending);
      announce eMonitorProxyEnqueue, (key = w.key, podId = w.podId, isWrite = true, pending = qsz);

      // drive the proxy pump
      send this, eProxyStep;
    }

    on eProxyStep do {
      var qsz: int;
      var coin: int;
      var pick: int;
      var opId: int;
      var rec: tProxyReq;
      var s: seq[int];

      qsz = sizeof(pending);
      if (qsz == 0) {
        return;
      }

      // non-deterministically hold or forward one
      coin = choose(2);
      if (coin == 0) {
        announce eMonitorProxyHold, (pending = qsz);
        // maybe schedule another step
        if (sizeof(pending) > 0) {
          send this, eProxyStep;
        }
        return;
      }

      // forward a randomly chosen queued request
      pick = choose(qsz);
      opId = pending[pick];
      // remove from pending
      pending -= (pick);

      rec = reqs[opId];

      // register inflight per key
      if (!(rec.key in inflightPerKey)) {
        inflightPerKey[rec.key] = default(seq[int]);
      }
      s = inflightPerKey[rec.key];
      s += (sizeof(s), opId);
      inflightPerKey[rec.key] = s;

      announce eMonitorProxyForward, (key = rec.key, podId = rec.podId, isWrite = rec.isWrite, pending = sizeof(pending));

      if (rec.isWrite) {
        send db, eStorageWrite, (caller = this, key = rec.key, value = rec.value, podId = rec.podId);
      } else {
        send db, eStorageRead, (caller = this, key = rec.key, podId = rec.podId);
      }

      // schedule another step to potentially forward more
      if (sizeof(pending) > 0) {
        send this, eProxyStep;
      }
    }

    on eStorageReadResp do (resp: (key: int, value: int)) {
      var infl: seq[int];
      var opId: int;
      var rec: tProxyReq;

      // match to the oldest inflight for this key
      assert resp.key in inflightPerKey && sizeof(inflightPerKey[resp.key]) > 0, "Proxy received unmatched read response!";
      infl = inflightPerKey[resp.key];
      opId = infl[0];
      infl -= (0);
      inflightPerKey[resp.key] = infl;

      rec = reqs[opId];

      announce eMonitorProxyResponseDelivered, (key = resp.key, podId = rec.podId, isWrite = false);
      send rec.caller, eStorageReadResp, (key = resp.key, value = resp.value);

      // cleanup
      reqs -= (opId);

      // continue pumping if needed
      if (sizeof(pending) > 0) {
        send this, eProxyStep;
      }
    }

    on eStorageWriteResp do (resp: (key: int, success: bool, value: int)) {
      var infl: seq[int];
      var opId: int;
      var rec: tProxyReq;

      // match to the oldest inflight for this key
      assert resp.key in inflightPerKey && sizeof(inflightPerKey[resp.key]) > 0, "Proxy received unmatched write response!";
      infl = inflightPerKey[resp.key];
      opId = infl[0];
      infl -= (0);
      inflightPerKey[resp.key] = infl;

      rec = reqs[opId];

      announce eMonitorProxyResponseDelivered, (key = resp.key, podId = rec.podId, isWrite = true);
      send rec.caller, eStorageWriteResp, (key = resp.key, success = resp.success, value = resp.value);

      // cleanup
      reqs -= (opId);

      // continue pumping if needed
      if (sizeof(pending) > 0) {
        send this, eProxyStep;
      }
    }
  }
}

machine CacheNode {
  var proxy: machine;
  var podId: int;

  var nextOpId: int;

  // local cache (maintained but not used to serve reads for strict LSI)
  var cache: map[int, int];

  // per-key inflight opIds for reads and writes
  var readInflight: map[int, seq[int]];
  var writeInflight: map[int, seq[int]];
  // opId -> client
  var opClient: map[int, machine];

  start state Init {
    entry (p: (proxy: machine, podId: int)) {
      proxy = p.proxy;
      podId = p.podId;
      nextOpId = 1;
      goto Ready;
    }
  }

  state Ready {
    on eClientRead do (r: (client: machine, key: int)) {
      var opId: int;
      var s: seq[int];

      // allocate opId and track client
      opId = nextOpId;
      nextOpId = nextOpId + 1;
      opClient[opId] = r.client;

      // enqueue per-key inflight read
      if (!(r.key in readInflight)) {
        readInflight[r.key] = default(seq[int]);
      }
      s = readInflight[r.key];
      s += (sizeof(s), opId);
      readInflight[r.key] = s;

      // issue to storage via proxy (always touch storage to guarantee LSI)
      announce eMonitorProxyRequestIssued, (key = r.key, podId = podId, isWrite = false);
      send proxy, eStorageRead, (caller = this, key = r.key, podId = podId);
    }

    on eClientWrite do (w: (client: machine, key: int, value: int)) {
      var opId: int;
      var s: seq[int];

      // allocate opId and track client
      opId = nextOpId;
      nextOpId = nextOpId + 1;
      opClient[opId] = w.client;

      // enqueue per-key inflight write
      if (!(w.key in writeInflight)) {
        writeInflight[w.key] = default(seq[int]);
      }
      s = writeInflight[w.key];
      s += (sizeof(s), opId);
      writeInflight[w.key] = s;

      // issue to storage via proxy
      announce eMonitorProxyRequestIssued, (key = w.key, podId = podId, isWrite = true);
      send proxy, eStorageWrite, (caller = this, key = w.key, value = w.value, podId = podId);
    }

    on eStorageReadResp do (resp: (key: int, value: int)) {
      var s: seq[int];
      var opId: int;
      var client: machine;

      assert resp.key in readInflight && sizeof(readInflight[resp.key]) > 0, "CacheNode: unexpected read response!";
      s = readInflight[resp.key];
      opId = s[0];
      s -= (0);
      readInflight[resp.key] = s;

      client = opClient[opId];
      opClient -= (opId);

      // update local cache with latest committed value
      cache[resp.key] = resp.value;

      // serve client; we touched storage, so fromCache = false
      send client, eReadResp, (key = resp.key, value = resp.value, fromCache = false);
    }

    on eStorageWriteResp do (resp: (key: int, success: bool, value: int)) {
      var s: seq[int];
      var opId: int;
      var client: machine;

      assert resp.key in writeInflight && sizeof(writeInflight[resp.key]) > 0, "CacheNode: unexpected write response!";
      s = writeInflight[resp.key];
      opId = s[0];
      s -= (0);
      writeInflight[resp.key] = s;

      client = opClient[opId];
      opClient -= (opId);

      if (resp.success) {
        // update local cache to the committed value
        cache[resp.key] = resp.value;
      }

      send client, eWriteResp, (key = resp.key, success = resp.success);
    }
  }
}