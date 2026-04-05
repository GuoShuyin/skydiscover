event eProxyReadResp: (key: int, value: int, fromCache: bool);
event eProxyWriteResp: (key: int, success: bool, value: int);
event eDoProxyStep;

type tQueued = (isWrite: bool, key: int, value: int, caller: machine, podId: int);
type tWaiter = (caller: machine, podId: int);

machine StorageProxy {
  var db: machine;

  var requestQueue: seq[tQueued];
  var latestCommitted: map[int, int];
  var pendingWrites: map[int, int];

  var readWaiters: map[int, seq[tWaiter]];
  var writeWaiters: map[int, seq[tWaiter]];

  start state Init {
    entry (p: (db: machine)) {
      db = p.db;
      requestQueue = default(seq[tQueued]);
      latestCommitted = default(map[int, int]);
      pendingWrites = default(map[int, int]);
      readWaiters = default(map[int, seq[tWaiter]]);
      writeWaiters = default(map[int, seq[tWaiter]]);
      goto Ready;
    }
  }

  state Ready {
    on eStorageRead do (req: (caller: machine, key: int, podId: int)) {
      HandleReadReq(req);
      raise eDoProxyStep;
    }

    on eStorageWrite do (req: (caller: machine, key: int, value: int, podId: int)) {
      HandleWriteReq(req);
      raise eDoProxyStep;
    }

    on eStorageReadResp do (resp: (key: int, value: int)) {
      HandleReadResp(resp);
      raise eDoProxyStep;
    }

    on eStorageWriteResp do (resp: (key: int, success: bool, value: int)) {
      HandleWriteResp(resp);
      raise eDoProxyStep;
    }

    on eDoProxyStep do {
      TryForwardOrHold();
    }
  }

  fun HandleReadReq(req: (caller: machine, key: int, podId: int)) {
    var canServe: bool;
    var cnt: int;
    var ws: seq[tWaiter];
    var qItem: tQueued;
    var n: int;
    var w: tWaiter;

    // Determine if any writes are pending for this key
    cnt = 0;
    if (req.key in pendingWrites) {
      cnt = pendingWrites[req.key];
    }

    canServe = (req.key in latestCommitted) && (cnt == 0);

    // Announce request issued from cache node to proxy
    announce eMonitorProxyRequestIssued, (key = req.key, podId = req.podId, isWrite = false);

    if (canServe) {
      // Serve from proxy cache without touching storage
      announce eMonitorProxyResponseDelivered, (key = req.key, podId = req.podId, isWrite = false);
      send req.caller, eProxyReadResp, (key = req.key, value = latestCommitted[req.key], fromCache = true);
      return;
    }

    // Otherwise, coalesce reads: enqueue one storage read if none in flight/queued for this key.
    if (req.key in readWaiters) {
      ws = readWaiters[req.key];
    } else {
      ws = default(seq[tWaiter]);
    }

    w = (caller = req.caller, podId = req.podId);
    ws += (sizeof(ws), w);
    readWaiters[req.key] = ws;

    // If this is the first waiter, enqueue a storage read
    if (sizeof(ws) == 1) {
      qItem = (isWrite = false, key = req.key, value = 0, caller = this, podId = req.podId);
      n = sizeof(requestQueue) + 1;
      requestQueue += (sizeof(requestQueue), qItem);
      announce eMonitorProxyEnqueue, (key = req.key, podId = req.podId, isWrite = false, pending = n);
    }
  }

  fun HandleWriteReq(req: (caller: machine, key: int, value: int, podId: int)) {
    var ws: seq[tWaiter];
    var w: tWaiter;
    var cnt: int;
    var qItem: tQueued;
    var n: int;

    // Announce request issued
    announce eMonitorProxyRequestIssued, (key = req.key, podId = req.podId, isWrite = true);

    // Track write waiter to route response back
    if (req.key in writeWaiters) {
      ws = writeWaiters[req.key];
    } else {
      ws = default(seq[tWaiter]);
    }
    w = (caller = req.caller, podId = req.podId);
    ws += (sizeof(ws), w);
    writeWaiters[req.key] = ws;

    // Track pending writes count
    cnt = 0;
    if (req.key in pendingWrites) {
      cnt = pendingWrites[req.key];
    }
    cnt = cnt + 1;
    pendingWrites[req.key] = cnt;

    // Enqueue storage write
    qItem = (isWrite = true, key = req.key, value = req.value, caller = this, podId = req.podId);
    n = sizeof(requestQueue) + 1;
    requestQueue += (sizeof(requestQueue), qItem);
    announce eMonitorProxyEnqueue, (key = req.key, podId = req.podId, isWrite = true, pending = n);
  }

  fun HandleReadResp(resp: (key: int, value: int)) {
    var ws: seq[tWaiter];
    var i: int;
    var w: tWaiter;

    latestCommitted[resp.key] = resp.value;

    if (resp.key in readWaiters) {
      ws = readWaiters[resp.key];
    } else {
      ws = default(seq[tWaiter]);
    }

    i = 0;
    while (i < sizeof(ws)) {
      w = ws[i];
      announce eMonitorProxyResponseDelivered, (key = resp.key, podId = w.podId, isWrite = false);
      send w.caller, eProxyReadResp, (key = resp.key, value = resp.value, fromCache = false);
      i = i + 1;
    }

    // Clear read waiters for this key
    readWaiters[resp.key] = default(seq[tWaiter]);
  }

  fun HandleWriteResp(resp: (key: int, success: bool, value: int)) {
    var ws: seq[tWaiter];
    var w: tWaiter;
    var cnt: int;

    latestCommitted[resp.key] = resp.value;

    // Route to the earliest writer
    ws = writeWaiters[resp.key];
    assert sizeof(ws) > 0, "Write response received with no waiter";
    w = ws[0];
    ws -= (0);
    writeWaiters[resp.key] = ws;

    // Decrement pending writes
    cnt = 0;
    if (resp.key in pendingWrites) {
      cnt = pendingWrites[resp.key];
    }
    cnt = cnt - 1;
    if (cnt <= 0) {
      if (resp.key in pendingWrites) {
        pendingWrites -= (resp.key);
      }
    } else {
      pendingWrites[resp.key] = cnt;
    }

    announce eMonitorProxyResponseDelivered, (key = resp.key, podId = w.podId, isWrite = true);
    send w.caller, eProxyWriteResp, (key = resp.key, success = resp.success, value = resp.value);
  }

  fun TryForwardOrHold() {
    var n: int;
    var idx: int;
    var item: tQueued;

    n = sizeof(requestQueue);
    if (n == 0) {
      return;
    }

    if ($) {
      // Hold step while requests remain queued
      announce eMonitorProxyHold, (pending = n);
      return;
    }

    // Forward a nondeterministically chosen queued request
    idx = choose(n);
    item = requestQueue[idx];

    // Announce forward before sending to storage
    announce eMonitorProxyForward, (key = item.key, podId = item.podId, isWrite = item.isWrite, pending = n);

    // Remove from queue
    requestQueue -= (idx);

    if (item.isWrite) {
      send db, eStorageWrite, (caller = this, key = item.key, value = item.value, podId = item.podId);
    } else {
      send db, eStorageRead, (caller = this, key = item.key, podId = item.podId);
    }
  }
}

machine CacheNode {
  var proxy: machine;
  var podId: int;

  var pendingReads: map[int, seq[machine]];
  var pendingWrites: map[int, seq[machine]];

  start state Init {
    entry (p: (proxy: machine, podId: int)) {
      proxy = p.proxy;
      podId = p.podId;
      pendingReads = default(map[int, seq[machine]]);
      pendingWrites = default(map[int, seq[machine]]);
      goto Ready;
    }
  }

  state Ready {
    on eClientRead do (req: (client: machine, key: int)) {
      var q: seq[machine];

      if (req.key in pendingReads) {
        q = pendingReads[req.key];
      } else {
        q = default(seq[machine]);
      }
      q += (sizeof(q), req.client);
      pendingReads[req.key] = q;

      announce eMonitorProxyRequestIssued, (key = req.key, podId = podId, isWrite = false);
      send proxy, eStorageRead, (caller = this, key = req.key, podId = podId);
    }

    on eClientWrite do (req: (client: machine, key: int, value: int)) {
      var q: seq[machine];

      if (req.key in pendingWrites) {
        q = pendingWrites[req.key];
      } else {
        q = default(seq[machine]);
      }
      q += (sizeof(q), req.client);
      pendingWrites[req.key] = q;

      announce eMonitorProxyRequestIssued, (key = req.key, podId = podId, isWrite = true);
      send proxy, eStorageWrite, (caller = this, key = req.key, value = req.value, podId = podId);
    }

    on eProxyReadResp do (resp: (key: int, value: int, fromCache: bool)) {
      var q: seq[machine];
      var c: machine;

      q = pendingReads[resp.key];
      assert sizeof(q) > 0, "Unexpected read response with no pending client";
      c = q[0];
      q -= (0);
      pendingReads[resp.key] = q;

      send c, eReadResp, (key = resp.key, value = resp.value, fromCache = resp.fromCache);
    }

    on eProxyWriteResp do (resp: (key: int, success: bool, value: int)) {
      var q: seq[machine];
      var c: machine;

      q = pendingWrites[resp.key];
      assert sizeof(q) > 0, "Unexpected write response with no pending client";
      c = q[0];
      q -= (0);
      pendingWrites[resp.key] = q;

      send c, eWriteResp, (key = resp.key, success = resp.success);
    }
  }
}