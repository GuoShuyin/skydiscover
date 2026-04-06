# SkyDiscover P Setup

This setup now evolves raw `P_project/PSrc/Machines.p` source directly.

SkyDiscover mutates:
- `PSrc/Machines.p`

The evaluator owns and injects:
- `PSpec/Spec.p`
- `PTst/TestDriver.p`
- `PTst/TestScript.p`
- `OwnershipSafety.pproj`
- `PForeign/`

That keeps the LSI oracle and anomaly-focused workload fixed while still letting search redesign the implementation.

The current seed intentionally keeps `NetworkProxy` unchanged as a stable compatibility layer. The intended mutation surface is `CacheNode`, where cache semantics, ownership handling, and delayed-write behavior live.

## Scoring

The evaluator reports three score families:

- `LSI` correctness
  - runs `p check` against the fixed spec and fixed tests
  - dominant metric
  - in `stage2`, any LSI bug collapses the score toward zero
- logical request latency
  - static proxy over generated `PSrc/Machines.p`
  - penalizes excess sends, storage-like sends, and coordination sends
  - direct DB reads, direct DB writes, and extra round trips are treated as costly
- syntax / compile
  - requires non-empty generated `PSrc/Machines.p`
  - requires successful `p compile`

## Search Mode

The config is intentionally code-oriented now:

- `language: p`
- `file_suffix: ".p"`
- `diff_based_generation: true`

This is the key fix for the earlier failure mode where `language: text` caused AdaEvolve to optimize prompt text instead of P code.

Within that code-oriented setup, treat `CacheNode` as the main place where useful search mutations should happen. `NetworkProxy` remains in the topology because the fixed harness instantiates it, but it is not the intended focus of search.

## Profiles

- `stage1`
  - smoke-test mode
  - useful for the initial eventually consistent cache baseline
  - compile and latency proxy dominate
  - `LSI` is reported but lightly weighted
- `stage2`
  - research mode
  - target is a linearizable cache that explicitly satisfies `LSI`
  - `LSI` is the main gate

## Commands

From repo root:

```bash
export OPENAI_API_KEY="your-real-key"
```

Stage 1 sanity run:

```bash
P_SCORER_PROFILE=stage1 uv run skydiscover-run \
  P_project/PSrc/Machines.p \
  P_project/skydiscover/evaluator.py \
  -c P_project/skydiscover/config.yaml \
  -s adaevolve \
  -i 10
```

Stage 2 research run from the same seed:

```bash
P_SCORER_PROFILE=stage2 uv run skydiscover-run \
  P_project/PSrc/Machines.p \
  P_project/skydiscover/evaluator.py \
  -c P_project/skydiscover/config.yaml \
  -s adaevolve \
  -i 20
```

If you have a stronger evolved candidate, use that file path as the first argument instead of `P_project/PSrc/Machines.p`.

To increase checker effort in `stage2`:

```bash
export P_SCORER_LSI_SCHEDULES=20
export P_SCORER_CHECK_TIMEOUT=120
```

## Output

SkyDiscover now writes evolved `.p` programs directly in its output directory instead of emitting a wrapped text bundle.

Check this folder after a run:

- `outputs/adaevolve/<run-name>/`

The most useful generated result is:

- `outputs/adaevolve/<run-name>/best/best_program.p`

Useful companion metadata:

- `outputs/adaevolve/<run-name>/best/best_program_info.json`

Example from a recent run:

- `outputs/adaevolve/PSrc_0405_0824/best/best_program.p`

Logs and checkpoints are also written under the same run directory, but the main artifact to inspect or reuse as the next seed is `best/best_program.p`.
