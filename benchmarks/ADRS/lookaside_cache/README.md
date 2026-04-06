# Lookaside Cache Routing

This benchmark now evolves a readable P-style program instead of executable
Python. The evaluator scores the full `.p` implementation directly using the
same overall pattern as the partner benchmark for compile/check, but the
performance term is now tied to client-perceived latency on fixed scenarios:
real `p compile`, fixed `p check` validation, and a read/write balance score.

The design space is still inspired by two familiar baseline ideas:

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
The seed look-aside cache is the original eventual-consistency variant: writes
bypass the cache and periodic refresh can leave a stale window, so it may fail
the fixed LSI checks until the search evolves a stronger protocol.

No particular device name or topology pattern is preferred. Labels such as
`cache`, `buffer`, `stage`, `replica`, `proxy`, `local`, `shared`, `remote`,
`hot`, or `warm` are only descriptive text. The search is free to use very
different names or structures if they score better.

Performance is now scored from the client angle on fixed benchmark scenarios:
the evaluator estimates average client read latency and average client write
latency from the real P request paths, then rewards balanced improvement rather
than one-sided gains. Correctness is enforced by fixed PChecker scenarios. If a
client is served a value different from the current database value for that key
at that moment, that is an LSI violation, and the stage2 score collapses toward
zero. If both baseline systems are present, the evaluator scores each and keeps
the higher result.

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
