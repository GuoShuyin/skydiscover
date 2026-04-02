P quick rules for writing valid state-machine code
==================================================

This file condenses the P docs into the syntax patterns most useful for protocol synthesis.
Prefer copying these patterns exactly, then adapting names and logic.

Top-level structure
-------------------

- A P program is built from top-level declarations such as `event`, `type`, `enum`, `fun`, `machine`, `spec`, and `test`.
- In this benchmark, do not redeclare top-level events or types that are already provided by the hidden environment.
- Candidate code should mainly define the required machines and their local helpers.

Machine structure
-----------------

```p
machine ExampleMachine {
    var peer: machine;
    var cache: map[int, int];

    start state Init {
        entry (payload: machine) {
            peer = payload;
            goto Ready;
        }
    }

    state Ready {
        on eRequest do (req: (key: int, value: int)) {
            send peer, eForward, req;
        }

        on eReset goto Init;
    }
}
```

Key syntax rules
----------------

- A machine body contains only:
  - local `var` declarations
  - local `fun` declarations
  - `state` declarations
- A state body may contain:
  - `entry { ... }` or `entry (payload: T) { ... }`
  - `exit { ... }`
  - `on eX do { ... }`
  - `on eX do (payload: T) { ... }`
  - `on eX goto SomeState;`
  - `on eX goto SomeState with { ... }`
  - `ignore eX;`
  - `defer eX;`
- Event sends are asynchronous:
  - `send target, eEvent;`
  - `send target, eEvent, payload;`
- Internal control transfer uses:
  - `goto NextState;`
  - `goto NextState, payload;`
  - `raise eInternal;`
  - `raise eInternal, payload;`

Start states and handlers
-------------------------

- Each machine needs one `start state`.
- The `entry` of the start state receives the constructor payload from `new MachineName(payload)`.
- Event handlers belong inside a state, not at top level.
- Helper logic should usually live in local `fun` declarations.

Function-body rule that causes many parse errors
------------------------------------------------

Inside any function or entry block, all local variables must be declared before statements.

Correct:

```p
fun Compute(x: int) : int {
    var y: int;
    y = x + 1;
    return y;
}
```

Incorrect:

```p
fun Compute(x: int) : int {
    x = x + 1;
    var y: int; // invalid in P
    return x;
}
```

Safe mental model
-----------------

- Think "actors with states and FIFO inboxes".
- `send` enqueues a message at another machine.
- `goto` changes local control state.
- `raise` immediately dispatches an internal event in the same machine.
