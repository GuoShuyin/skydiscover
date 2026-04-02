P syntax references for the distributed cache benchmark.

SkyDiscover automatically appends the contents of this `evaluator_context/`
directory to the visible task description when you run:

```bash
uv run python -m skydiscover examples/distributed_cache_protocol/evaluator.py ...
```

Use this folder for small, high-signal references such as:

- valid P syntax examples
- machine/state/entry/on-do patterns
- examples of maps, tuples, and local variable declarations
- tiny event-driven protocols that are unrelated to WriteGuards

The `00_reference/` folder contains distilled notes from the official P docs:

- `01_p_state_machine_cheatsheet.md`
- `02_p_types_payloads_and_collections.md`
- `03_p_common_compile_traps.md`
- `04_p_protocol_patterns.md`

Guidelines:

- Keep files short and readable.
- Prefer neutral examples that teach syntax and structure, not one fixed
  distributed-systems design.
- Avoid WriteGuard-specific concepts if you do not want to bias the search.
- `.p`, `.md`, and `.txt` files are good choices here.

The model should treat these files as syntax/style references, not as required
architecture.
