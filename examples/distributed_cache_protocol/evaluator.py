"""
Distributed cache protocol discovery task.

Goal:
- Design a protocol for two pod-facing `CacheNode` machines in front of a shared storage system.
- A `CacheNode` may keep local cache state, forward to a shared or remote cache helper, or act as a thin frontend.
- satisfyLSI: A key may be served to a client without touching storage only if the returned value equals
  the latest committed value in storage.
- Under balanced and write-heavy workloads, minimize local pod/cache <-> proxy
  round trips.

Design context:
- An autosharder may assign key ranges to pods.
- Storage is implemented by tablet servers whose key-range layout may change dynamically.
- Ownership may transfer nondeterministically.
- Designs that rely on key ranges or ownership should remain coherent under range movement and transfer.
- Prefer scalable designs that keep authority metadata compact so cache/storage space is used primarily for data.

Hidden environment:
- Instantiates one storage machine and passes it to `StorageProxy` as `db`.
- Instantiates one `StorageProxy`.
- Instantiates two `CacheNode` pods.
- Generates concurrent reads and writes from two clients.
- Checks LSI with model checking.

Your candidate must define these machine types:
- machine StorageProxy
- machine CacheNode

You may also define helper events, helper functions, and helper machines.

Required constructor signatures:
- StorageProxy.entry(p: (db: machine))
- CacheNode.entry(p: (proxy: machine, podId: int))

Fixed events available to your candidate:
- eClientRead: (client: machine, key: int)
- eClientWrite: (client: machine, key: int, value: int)
- eStorageRead: (caller: machine, key: int, podId: int)
- eStorageWrite: (caller: machine, key: int, value: int, podId: int)
- eStorageReadResp: (key: int, value: int)
- eStorageWriteResp: (key: int, success: bool, value: int)
- eReadResp: (key: int, value: int, fromCache: bool)
- eWriteResp: (key: int, success: bool)
- eMonitorProxyRequestIssued: (key: int, podId: int, isWrite: bool)
- eMonitorProxyResponseDelivered: (key: int, podId: int, isWrite: bool)
- eMonitorProxyEnqueue: (key: int, podId: int, isWrite: bool, pending: int)
- eMonitorProxyForward: (key: int, podId: int, isWrite: bool, pending: int)
- eMonitorProxyHold: (pending: int)

Notes:
- All traffic from `CacheNode` machines or helper caches toward storage must go through `StorageProxy`.
- `StorageProxy` represents the interposed proxy/network layer between pods and storage.
- `StorageProxy` should behave like a network proxy: maintain a queue of storage-facing requests and
  nondeterministically either forward a queued request or keep requests queued to model congestion/delay.
- If it forwards, it may choose among queued requests in a nondeterministic order.
- Prefer explicit request IDs or operation IDs when multiple concurrent requests to the same key may be outstanding.
- When a `CacheNode` or helper cache sends a request to `StorageProxy`, announce `eMonitorProxyRequestIssued`.
- When `StorageProxy` returns a logical response back to a `CacheNode` or helper cache, announce `eMonitorProxyResponseDelivered`.
- When `StorageProxy` enqueues a storage-facing request, announce `eMonitorProxyEnqueue`.
- When `StorageProxy` forwards a queued storage-facing request to storage, announce `eMonitorProxyForward`
  before sending the storage event.
- When `StorageProxy` takes a congestion/no-op step while queued requests remain, announce `eMonitorProxyHold`.
- `StorageProxy` should stay focused on proxy/network behavior and avoid unrelated application-level functionality.
- Do not redeclare the fixed events listed above.
- You do not have to model ownership transfer.
- You do not have to model shard/tablet splits.
- Cache-based designs are allowed if they preserve LSI.

Scoring:
- Stage 1 is idea-first and uses static architectural signals instead of hard compilation.
- Stage 2 adds compilation/model-check evidence when available.
- If Stage 2 compilation fails, the candidate keeps most of its idea score and only receives a light penalty.
- Strong safety evidence and lower local pod/cache <-> proxy round trips still score best.
- Stage 1 also rewards visible support for request-ID matching, range/tablet/ownership awareness, and scalable metadata choices.
"""

from evaluator_runtime import evaluate, evaluate_stage1, evaluate_stage2, main


if __name__ == "__main__":
    main()
