Distributed cache protocol benchmark for SkyDiscover.

This benchmark is intentionally from-scratch: you do not provide an
`initial_program.p`. SkyDiscover only sees a high-level task description plus a
candidate-side P interface. The hidden evaluator supplies the clients, the
shared storage system, the fixed workloads, and the LSI checker.

The hidden environment instantiates:

- one `StorageProxy`
- two `CacheNode` pods

Your candidate defines the `StorageProxy` and `CacheNode` machine types. A
valid solution may choose to use a cache, or may forward everything to storage.

What evaluation means in this benchmark:

1. SkyDiscover writes the candidate P code to a temporary file.
2. `evaluator_runtime.py` creates a temporary P project by combining:
   - the hidden fixed environment,
   - the hidden LSI spec and workload drivers,
   - your candidate file.
3. It runs `p compile`.
4. Stage 1 runs small smoke checks.
5. Stage 2 runs larger `p check` workloads, including a targeted cross-pod
   stale-cache scenario plus balanced and write-heavy workloads.
6. A verbose run is replayed to extract efficiency metrics such as storage round
   trips per client operation.

The evaluator returns a metrics dictionary to SkyDiscover. The important fields
are:

- `safety_score`: fraction of required model-checking tests that passed.
- `round_trip_efficiency`: higher is better; derived from storage round trips per
  client operation.
- `cache_hit_rate`: fraction of reads served without touching storage.
- `combined_score`: zero unless all full LSI checks pass.

Optional syntax-reference folder:

- Put neutral P examples in
  [evaluator_context/](/Users/apple/Documents/GitHub/skydiscover/examples/distributed_cache_protocol/evaluator_context).
- When this benchmark runs, SkyDiscover automatically appends those files to
  the visible task description for the model.
- This is useful when you want to teach P syntax without committing to a
  specific distributed-systems design.

Recommended run:

```bash
uv run python -m skydiscover examples/distributed_cache_protocol/evaluator.py \
  --config examples/distributed_cache_protocol/config.yaml \
  --search adaevolve \
  --iterations 20
```

If you want to inspect the evaluator directly, these files matter most:

- [evaluator.py](/Users/apple/Documents/GitHub/skydiscover/examples/distributed_cache_protocol/evaluator.py)
- [evaluator_runtime.py](/Users/apple/Documents/GitHub/skydiscover/examples/distributed_cache_protocol/evaluator_runtime.py)
- [config.yaml](/Users/apple/Documents/GitHub/skydiscover/examples/distributed_cache_protocol/config.yaml)
