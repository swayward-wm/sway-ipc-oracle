# Pinned sway crashes

Pinned sway 1.12 (`88869399`, wlroots `c1d38536`) segfaults on some command
sequences. These are sway bugs, not swayward divergences.

They were found by live random exploration (the `differential` runner and
[random-v3](running.md#random-v3-state-aware)), not by the committed corpora.

The oracle's reference rows are replies recorded from sway. A sequence that
crashes sway has no reply to record, so it cannot become a row.

A crash of another compositor is recorded as a `crash` row
([how the runners record them](#how-the-runners-record-them)).

Nothing here has been filed upstream. Source paths below are in sway at
[`88869399`](https://github.com/swaywm/sway/tree/88869399f421d9180dd8b6ed0b5a1f4a3585d252).

## Reproduce a crash

[Build the pinned image](reproducing.md) and start a shell in it from your
oracle clone. Inside, `$SWAY_BINARY` is the pinned sway
(`/opt/sway-src/build/sway/sway`):

```sh
podman run --rm -it --memory 4g --memory-swap 4g --security-opt label=disable \
  -v "$PWD:/oracle" sway-ipc-oracle bash
```

This replays crash 2 on a fresh headless sway:

```sh
mkdir -p target/crashes
W="exec foot --app-id=fixture-diff-%s --title=fixture-diff-%s sh -c 'sleep 300'"
python3 - "$W" > target/crashes/2.json <<'PY'
import json, sys
win = sys.argv[1]
print(json.dumps({"outputs": 1, "commands": [win % (1, 1), win % (2, 2),
    "fullscreen enable", "floating toggle", "split h",
    "move container to workspace next"]}))
PY
./contrib/pr-check --replay target/crashes/2.json --binary "$SWAY_BINARY"
echo "$?"
```

It prints `crashed; step 6; key signal:SIGSEGV; ...` and exit code 1.
Exit 0 means sway survived, 2 a harness problem.

For crashes 3 and 4, put their lists below into `commands`, one `win` line
per `win`.

Crash 1 needs two commands sent back to back. `--replay` cannot do that: it
lets sway settle after every command ([limits](pr-check.md#what-it-does-not-test)).

This script sends them on one IPC connection without waiting, in the same
container shell. It prints `sway crashed`, and bash reports the segfault:

```sh
d=$(mktemp -d)
printf 'font monospace 10\ndefault_border normal 2\noutput * mode 1280x720\n' > "$d/config"
export XDG_RUNTIME_DIR="$d" SWAYSOCK="$d/ipc.sock" WLR_BACKENDS=headless WLR_HEADLESS_OUTPUTS=1
"$SWAY_BINARY" -c "$d/config" > "$d/log" 2>&1 &
python3 - <<'PY'
import os, socket, struct, time
while not os.path.exists(os.environ["SWAYSOCK"]): time.sleep(0.1)
s = socket.socket(socket.AF_UNIX); s.connect(os.environ["SWAYSOCK"])
def send(text, kind=0):  # kind 0 is RUN_COMMAND, 4 GET_TREE, 7 GET_VERSION
    s.sendall(b"i3-ipc" + struct.pack("=II", len(text), kind) + text.encode())
def reply():
    size = struct.unpack("=I", s.recv(14, socket.MSG_WAITALL)[6:10])[0]
    return s.recv(size, socket.MSG_WAITALL)
send("exec foot"); reply()
while send("", 4) or b'"app_id": "foot"' not in reply(): time.sleep(0.1)  # win
send("layout tabbed"); reply(); time.sleep(0.2)
send("fullscreen enable global"); send("split h")  # back to back
reply(); reply(); time.sleep(1)
try:
    send("", 7); reply(); print("sway survived")
except (OSError, struct.error):
    print("sway crashed")
PY
```

Sway segfaults in the next transaction, so the script sends `GET_VERSION`
after a second to see whether it is still alive.

## Distinct crashes

| # | Crash frame | Trigger |
| --- | --- | --- |
| 1 | `container_get_gaps` | split a global-fullscreen view before its transaction commits |
| 2 | `workspace_focus_fullscreen` | move a split, floated, fullscreen view |
| 3 | `container_swap` | swap with a container in the scratchpad |
| 4 | `workspace_add_floating` | `move container to mark` with a scratchpad target |

How to read a list:

- Each list is minimal: removing any command stops the crash.
- `win` opens one `foot` window. Each line is its own IPC `RUN_COMMAND`
  message.
- `A && B` means separate messages sent back to back, with no settle between
  them.

Each was reproduced 3/3 on a fresh headless sway with the oracle's
differential config: `font monospace 10`, `default_border normal 2`, one
1280x720 output. Frames come from the debug build's cores via `addr2line`.

Rechecked 2026-10-26 in image `rc-1fd3c25b`: every list and the cheapest
variant of crash 1 still crash 3/3.

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

Why it crashes:

1. `split` wraps the fullscreen view in a new container.
2. `container_replace` moves `FULLSCREEN_GLOBAL` onto the wrapper, which has
   no view (`sway/tree/container.c:1471-1505`).
3. The next transaction's `arrange_fullscreen` calls `container_get_gaps(fs)`
   for the wrapper. That reads `con->current.workspace`, which a container
   created in this transaction does not have yet (`transaction.c:474-483`).

The split must arrive before the fullscreen's transaction commits, so back to
back it crashes. One `fullscreen enable global; split h` message survives, and
so do separate messages with a settle between.

On `88869399` both variants stayed alive in every rerun (3 or 4 runs each).

Random sequences hit it through a wrapping command right after
`fullscreen ... global`:

- `split`, `splitt`, or `layout` on a fresh tabbed or stacked workspace;
- `move container to workspace`, or `kill` after a split;
- a new window opening.

This one shape covers 172 of the 340 local cores. A variant reaches the same
frame through `arrange_output` (16 cores).

All 39 seeds that still crashed when the earlier random crash list was
rechecked are this shape. The cheapest variant:

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

Found by random-v3 seed 52. The destination workspace's `fullscreen` pointer
names a container that the float, split and move sequence has detached or
destroyed. `seat_set_raw_focus` then dereferences it.

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

Found by random-v3 seed 31189. One side of the swap is hidden in the
scratchpad, so `con->pending.workspace` is NULL. `container_swap` reads its
`->output` before the `sway_assert(vis1 && vis2)` guard can run.

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

Found by random-v3 seed 40167, through the R8 (scratchpad cycle) and R7
(mark targets) [recipes](running.md#random-v3-state-aware).

The marked target is a hidden scratchpad container with no workspace. Moving
a floating container to it reaches `workspace_add_floating` with a NULL
workspace.

The seed numbers name where each crash was found. The v3 generator has
changed since, so a seed no longer replays the same commands; the lists
above do.

## Seen in cores, not minimised

These stacks appear in the local core dumps (`coredumpctl`, 340 cores of the
pinned binary). No generated seed has been tied to them, so a report needs a
reproducer first.

| Stack | Cores | Status |
| --- | ---: | --- |
| `container_detach <- container_begin_destroy <- view_unmap` during `server_fini` | 52 | Segfault at shutdown, when the harness stops sway after a run. Affects no result. |
| `workspace_add_floating` or `seat_get_focus_inactive_tiling <- container_set_floating <- cmd_floating` | 5 | Probably related to crashes 2 and 4. Minimise before reporting. |
| `arrange_workspace <- cmd_move_in_direction` | 2 | As above. |
| `handle_seat_destroy`, `ipc_event_shutdown`, the `wlr_backend_finish` assert | — | Startup and shutdown failures from harness development (September 2026), not from command sequences. |

## How the runners record them

A sway death is a `crash` row, never a mismatch.

| Runner | What a crash row records |
| --- | --- |
| `differential` | `verdict = "crash"`, `exits` (for example `sway: killed by SIGSEGV`), the step after which the death was seen, and the `commands` up to it. A crash of `--a` (the reference, sway) is triaged `harness issue`; a crash of `--b` stays `untriaged`. |
| `scenarios` | The scenario and action sway died on, for example `sway crashed (killed by SIGSEGV) in scenario X at action 'capture:X'`. A scenario that crashes pinned sway cannot be captured and is not added. |

Sway often segfaults in a later transaction, after it has answered the
command. So the runner checks liveness after a divergent step and after the
last step; a divergence seen while sway is dying is a crash.

Delta debugging discards candidates that crash a compositor.
`contrib/tests/sway-ipc-crash` covers this classification.
