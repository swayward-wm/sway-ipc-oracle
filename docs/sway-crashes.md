# Pinned sway crashes

Pinned sway 1.12 (`88869399`, wlroots `c1d38536`) segfaults on some generated
command sequences. These are sway bugs, not swayward divergences: with no sway
reply there is nothing to compare, so no oracle row can come from them.

## How the runners classify them

- `differential` reports a seed that kills either compositor as
  `verdict = "crash"`, never as a mismatch. Each crash row includes `exits`
  (for example `sway: killed by SIGSEGV`), the step after which the death was
  observed, and the `commands` up to that step. A crash of `--a` (the reference,
  sway) carries `triage = "harness issue"`. A crash of `--b` stays `untriaged`.
- Sway segfaults inside a later transaction, often after it has already
  answered the command, so the runner checks liveness after a divergent step
  and after the last step. A divergence observed while sway is dying is a crash.
  Delta debugging discards candidates that crash a compositor.
- `scenarios` names the scenario and action that sway died on, for example
  `sway crashed (killed by SIGSEGV) in scenario X at action 'capture:X'`. A
  scenario that crashes pinned sway cannot be captured and is not added.

`contrib/tests/sway-ipc-crash` covers the classification.

## Distinct crashes

Each list below is minimal: removing any command stops the crash. `win` opens
one `foot` window. Each line is its own IPC `RUN_COMMAND` message; `A && B`
means separate messages sent back to back with no settle in between. Each was
reproduced 3/3 on a fresh headless sway with the oracle's differential config
(`font monospace 10`, `default_border normal 2`, one 1280x720 output). Frames
are resolved from the debug build's cores with `addr2line`.

### 1. Splitting a global-fullscreen view: `container_get_gaps`

```
win
layout tabbed            # or: floating enable
fullscreen enable global && split h
```

```
#0 container_get_gaps     sway/desktop/transaction.c:482
#1 arrange_fullscreen     sway/desktop/transaction.c:508
#2 arrange_root           sway/desktop/transaction.c:682
#3 transaction_progress   sway/desktop/transaction.c:765
#4 set_instruction_ready  sway/desktop/transaction.c:913
```

`split` wraps the fullscreen view in a new container. `container_replace`
moves `FULLSCREEN_GLOBAL` onto the wrapper (`sway/tree/container.c:1471-1505`),
which has no view. The next transaction's `arrange_fullscreen` then calls
`container_get_gaps(fs)` for it. That function dereferences
`con->current.workspace`, and a container created in the same transaction has
no committed `current` state yet (`transaction.c:474-483`).

The split must arrive before the fullscreen's transaction commits: sent back to
back without a settle it crashes, while a single `fullscreen enable global;
split h` message or separate messages with a settle between them survive
(reviewed 3-4/3-4 alive on 88869399). Random sequences hit it
through a wrapping command right after `fullscreen ... global`: `split`,
`splitt`, `layout` on a fresh tabbed or stacked workspace, `move container to
workspace`, `kill` after a split, or a new window opening. This one shape covers
172 of the 340 local cores. A variant reaches the same frame through
`arrange_output` (16 cores). All 39 "real crash" seeds in worker-3's recheck of
`sway-crash.txt` are this shape. The cheapest variant:

```
win
win
fullscreen enable global && splitv && move container to workspace 1
```

### 2. Moving a split, floated, fullscreen view: `workspace_focus_fullscreen`

```
win
win
fullscreen enable
floating toggle
split h
move container to workspace next
```

```
#0 seat_node_from_node        sway/input/seat.c:329
#1 seat_set_raw_focus         sway/input/seat.c:1117
#2 workspace_focus_fullscreen sway/commands/move.c:102
#3 container_move_to_container sway/commands/move.c:269
#4 cmd_move_container         sway/commands/move.c:578
```

Random-v3 seed 52. The destination workspace's `fullscreen` pointer names a
container that the float, split and move sequence has detached or destroyed.
`seat_set_raw_focus` then dereferences it.

### 3. `swap` with a scratchpad container: `container_swap`

```
win
mark m
win
focus next
split h
focus parent; split v
fullscreen toggle; move scratchpad
swap container with mark m
```

```
#0 container_swap  sway/tree/container.c:1844
#1 cmd_swap        sway/commands/swap.c:93
```

Random-v3 seed 31189. One side of the swap is in the scratchpad (hidden), so
`con->pending.workspace` is NULL. `container_swap` dereferences
`con->pending.workspace->output` before its `sway_assert(vis1 && vis2)` guard
can run.

### 4. `move container to mark` into the scratchpad: `workspace_add_floating`

```
win
move scratchpad
scratchpad show
win
floating toggle
splitv
mark m
move scratchpad
move container to mark m
```

```
#0 workspace_add_floating       sway/tree/workspace.c:966
#1 container_move_to_workspace  sway/commands/move.c:208
#2 container_move_to_container  sway/commands/move.c:249
#3 cmd_move_container           sway/commands/move.c:578
```

Random-v3 seed 40167, through the R8 and R7 recipes. The marked target is a
hidden scratchpad container with no workspace, and moving a floating container
to it reaches `workspace_add_floating` with a NULL workspace.

## Seen in cores, not minimised

These stacks appear in the local core dumps (`coredumpctl`, 340 cores of the
pinned binary), but no generated seed has been tied to them. A report needs a
reproducer first.

- `container_detach <- container_begin_destroy <- view_unmap` during
  `server_fini` (52 cores). Sway segfaults at shutdown while clients are torn
  down. It happens when the harness stops sway after a run and affects no
  result.
- `workspace_add_floating` or `seat_get_focus_inactive_tiling <-
  container_set_floating <- cmd_floating` (5 cores), and
  `arrange_workspace <- cmd_move_in_direction` (2 cores). These are probably
  relatives of crashes 2 and 4. Minimise them before reporting.
- `handle_seat_destroy`, `ipc_event_shutdown`, and the `wlr_backend_finish`
  assert. These are startup and shutdown failures from harness development
  (September 2026), not from command sequences.

Nothing here has been filed upstream.
