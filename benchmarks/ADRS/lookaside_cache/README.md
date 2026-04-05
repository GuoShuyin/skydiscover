# Lookaside Cache Routing

This benchmark now evolves a readable P-style program instead of executable
Python. The file does not need to compile as real P, but evolved best programs
should still look like full P programs with events, machines, and a coherent
architecture story. The evaluator only parses the declarative `DESIGN` block
for scoring and evaluates the resulting system design on fixed mixed workloads.

The design space is still inspired by two familiar baseline ideas:

- look-aside reads backed by a fast shared tier
- direct reads and writes against the backing database

The baseline is adapted from the reference state-machine implementations in:

- `references/p_LookasideCache/PSrc/Machines.p`
- `references/p_DirectTiDB/PSrc/Machines.p`

But the search target is now a constrained design DSL embedded inside a full
P-like program, not arbitrary runtime code. Only these declarations affect
score:

- `authoritative <name> : <role> { ... }`
- `device <name> : <role> { ... }`
- `param <name> = <value>;`

This keeps the benchmark readable and sharply reduces Python-level exploit
surface. You can still invent new devices, change the storage topology, and
alter routing policy through the declared parameters.

The evaluator simulates the workload with evaluator-controlled canonical
pricing. It keeps an ordered ladder of known device archetypes with fixed
read/write costs. Known roles map directly to those anchors, and newly invented
devices can be inserted between neighboring anchors by an evaluator-side device
judge. That judge looks at the declared role, doc string, and full raw device
block text. When a new device is inserted between two anchors, its charged read
and write costs are the midpoint of the two neighboring anchors.

The evaluator also enforces a total non-authoritative value-storage capacity
budget derived from `cache_capacity`, so adding extra devices changes how
capacity is split rather than creating free memory. The authoritative database
truth is maintained by the evaluator itself for LSI checking. This means the
candidate design cannot redefine correctness through custom code.

It also tracks explicit `LSI violation` events. If a client read is served with
a value different from the current database value for that key at that moment,
the evaluator records an LSI violation and applies an extra score penalty.
Several scenarios are multi-client and conflict-heavy to stress this behavior.
If `OPENAI_API_KEY` is set, the evaluator can use an LLM to place unknown
devices into the anchor ladder from their declared semantics; otherwise it
falls back to deterministic heuristics. The AI path is restricted by hard
semantic guardrails, so value-serving devices cannot be mispriced as pure
metadata planes.

## Files

- `initial_program.p`: P-style design seed used by search
- `initial_program.py`: legacy Python reference seed from the earlier benchmark version
- `config.yaml`: SkyDiscover prompt and search config
- `evaluator/evaluator.py`: deterministic design parser, workload generator, and scorer

## Run

From the repo root:

```bash
uv run python -m skydiscover.cli \
  benchmarks/ADRS/lookaside_cache/initial_program.p \
  benchmarks/ADRS/lookaside_cache/evaluator/evaluator.py \
  -c benchmarks/ADRS/lookaside_cache/config.yaml \
  -s adaevolve
```
