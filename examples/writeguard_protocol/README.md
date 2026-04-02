Distributed cache protocol benchmark for SkyDiscover.

This example turns the local `p_WriteGuard/` project into a safety-first
discovery task. SkyDiscover only evolves the mutable cache/proxy protocol slice
(`StorageProxy` and `CacheNode`), while the evaluator reconstructs the full P
project, compiles it, runs model checking, and extracts efficiency metrics from
verbose traces.

`StorageProxy` and `CacheNode` are neutral candidate-side names. The evaluator
maps them to the fixed harness names internally before compiling the full P
project.

What the evaluator optimizes:

- Safety first: no `LSISafety` violations and no `NoStaleWriteCommitted`
  violations.
- Your target check is enforced directly: `tcProxyLSI` is validated with
  `p check ... -tc tcProxyLSI -s 10000 --sch-pct 3`.
- Efficiency next: fewer cache<->DB/control-plane round trips, better cache hit
  rate, and lower ownership-transfer overhead.

Recommended run: start from scratch, with no baseline:

```bash
uv run python -m skydiscover examples/writeguard_protocol/evaluator.py \
  --config examples/writeguard_protocol/config.yaml \
  --search adaevolve \
  --iterations 20
```

If you want to seed search with a scaffold anyway, you can still pass the optional baseline:

```bash
uv run python -m skydiscover examples/writeguard_protocol/initial_program.p \
  examples/writeguard_protocol/evaluator.py \
  --config examples/writeguard_protocol/config.yaml \
  --search adaevolve \
  --iterations 20
```

In from-scratch mode, the candidate still has to define both machines with the
same public interface:

- `machine StorageProxy`
- `machine CacheNode`

If your WriteGuard project lives somewhere other than `p_WriteGuard/`, update
`WRITEGUARD_ROOT` in [evaluator_runtime.py](/Users/apple/Documents/GitHub/skydiscover/examples/writeguard_protocol/evaluator_runtime.py).
