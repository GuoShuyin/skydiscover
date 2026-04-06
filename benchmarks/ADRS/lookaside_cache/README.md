# Lookaside Cache Routing

This benchmark now evolves a readable P-style program instead of executable
Python. The evaluator scores the full `.p` implementation directly using real
`p compile`, ownership-aware fixed `p check` validation, and a client-perceived
read/write balance score.

The design space still starts from two familiar baseline ideas:

- look-aside reads backed by a fast shared tier
- direct reads and writes against the backing database

The baseline is adapted from the reference state-machine implementations in:

- `references/p_LookasideCache/PSrc/Machines.p`
- `references/p_DirectTiDB/PSrc/Machines.p`

There is no separate design DSL, no declaration-only scoring shortcut, and no
hidden parsed sidecar. The full `.p` file is the single source of truth.
SkyDiscover edits that full program with targeted SEARCH/REPLACE diffs, and
any performance or safety improvement must be reflected in the real P code.
The seed may contain both baseline systems, but evolved programs may keep only
one scored system. If both remain, the evaluator takes the higher-scoring one.
The fixed evaluator-owned world now injects:

- `AutoSharder`
- `NetworkProxy`
- `ClientPod`

`NetworkProxy` is intentionally open on the control plane as well as the data
plane. In addition to forwarding the standard read/write path, it exposes a
generic tunnel:

- `eProxyControl`
- `eProxyControlResp`

with payload type `tProxyControlReq`. Evolved protocols should keep ordinary
client data reads/writes on the normal `eRead` / `eWrite` path, but if they
invent extra DB-facing control operations such as guard installation, epoch
changes, split hints, or other metadata updates, they should route those
through `eProxyControl` rather than introducing a brand-new proxy event name
that the fixed harness cannot see.

The seed look-aside cache is the original eventual-consistency variant: writes
bypass the cache and periodic refresh can leave a stale window, so it may fail
the fixed LSI checks until the search evolves a stronger protocol. The fixed
tests can also revoke ownership from one pod, grant it to another, and expose
delayed writes from the old owner after transfer.

No particular device name or topology pattern is preferred. Labels such as
`cache`, `buffer`, `stage`, `replica`, `proxy`, `local`, `shared`, `remote`,
`hot`, or `warm` are only descriptive text. The search is free to use very
different names or structures if they score better.

Performance is now scored from the client angle on fixed benchmark scenarios:
the evaluator estimates average client read latency and average client write
latency from the real P request paths, including proxy-hop costs, and then
rewards balanced improvement rather than one-sided gains. Correctness is
enforced by fixed PChecker scenarios. If a client is served a value different
from the current database value for that key at that moment, that is an LSI
violation, and the stage2 score collapses toward zero. If both baseline systems
are present, the evaluator scores each and keeps the higher result.
Cache-like code only receives cache-side latency credit if the implementation
both warms local cached state and actually serves client reads from the
cache-hit branch. A "cache" that merely checks local metadata and then always
falls through to the DB is treated as a DB path, not as a fast hit.

## Files

- `initial_program.p`: P-style seed used by search
- `initial_program.py`: legacy Python reference seed from the earlier benchmark version
- `config.yaml`: SkyDiscover prompt and search config
- `OwnershipSafety.pproj`: fixed temporary P project template
- `PSpec/Spec.p`: fixed LSI oracle used by `p check`
- `PTst/TestDriver.p`: fixed direct/lookaside adversarial drivers
- `PTst/TestScript.p`: fixed P test suite
- `evaluator/evaluator.py`: compile/check scorer plus client read/write balance estimator

## Run

From the repo root:

```bash
uv run python -m skydiscover.cli \
  benchmarks/ADRS/lookaside_cache/initial_program.p \
  benchmarks/ADRS/lookaside_cache/evaluator/evaluator.py \
  -c benchmarks/ADRS/lookaside_cache/config.yaml \
  -s adaevolve
```

For a short supervised run:

```bash
./.venv/bin/python -m skydiscover.cli \
  benchmarks/ADRS/lookaside_cache/initial_program.p \
  benchmarks/ADRS/lookaside_cache/evaluator/evaluator.py \
  -c benchmarks/ADRS/lookaside_cache/config.yaml \
  -s adaevolve \
  --iterations 10
```
