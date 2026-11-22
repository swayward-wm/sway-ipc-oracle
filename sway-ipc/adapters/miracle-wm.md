# miracle-wm adapter

`MiracleAdapter` measures miracle-wm 0.11.2 (`miracle-wm-0.11.2`, pinned in
`pins.toml`). It uses Mir, not wlroots, and implements i3/sway IPC plus a
subset of sway commands. Source paths below refer to pinned miracle-wm unless
explicitly labeled Mir 2.26.

## Run a first check

From a regular oracle clone, with the [pinned image](../../docs/reproducing.md) built:

```sh
OUT="${OUT:-$PWD/target/miracle-wm}"
mkdir -p "$OUT/tmp"
podman run --rm --memory 4g --memory-swap 4g --security-opt label=disable \
  -v "$PWD:/oracle:ro" -v "$OUT:/out" sway-ipc-oracle bash -c \
  'export TMPDIR=/out/tmp; ./contrib/sway-ipc-run command-fuzz --compositor miracle-wm \
    --binary "$MIRACLE_WM_BINARY" --out /out/command-fuzz.toml' > "$OUT/run.log" 2>&1 &
PID=$!; wait "$PID"; echo "$?"
```

[Read exit codes](../../docs/ci.md#run-a-corpus) and
[run other corpora](../../docs/ci.md#pick-the-corpora), using
`MIRACLE_WM_BINARY` inside the image. Use one 4 GiB, zero-swap container per
command. Mir falls back to software buffers in this container
([Mir 2.26 buffer allocator](https://github.com/canonical/mir/blob/v2.26.0/src/platforms/renderer-generic-egl/buffer_allocator.cpp#L215-L231));
no render node is needed.

## Check the headless setup

It shares foot, `xdg-toplevel-fixture` and memory/time limits with other
Wayland adapters. Virtual displays and stub input follow miracle-wm's end-to-end
harness (`e2e/conftest.py:59`).

| Setting | Reason or requirement |
| --- | --- |
| `--platform-display-libs=mir:virtual`, `--platform-input-lib=mir:stub-input` | Stub input needs Fedora's `mir-test-tools`, not just `mir-server-libs`. Without it, the process logs the socket, then exits 1 without an error. |
| `--enable-x11 false` | miracle-wm enables Xwayland by default (`src/main.cpp:268`); Mir aborts the child process if it cannot execute Xwayland ([Mir 2.26 `xwayland_server.cpp:115-118`](https://github.com/canonical/mir/blob/v2.26.0/src/server/frontend_xwayland/xwayland_server.cpp#L115-L118)). The oracle uses Wayland clients only. |
| `MIRACLESOCK` | Private `ipc.sock`, replacing the ambient value (`src/ipc_connection_manager.cpp:134-137`). Runtime and config-home directories are private too. |
| No session bus | GLib `G_IS_DBUS_CONNECTION` criticals at start and exit are harmless. |

## Check the translations

All rows record these three rules once in `[run].adapted`. They change setup
and cleanup only. Apart from `fake-N` output names (below), no scenario
command or IPC reply is rewritten.

| Rule | What changes |
| --- | --- |
| `miracle-config-yaml` | Sway config becomes miracle-wm YAML, shared by state, random and differential runs. |
| `miracle-outputs-virtual` | Output sizes become `--virtual-output=WxH`; positions go in display YAML. `fake-N` maps to `Virtual-(N+1)`. |
| `miracle-reset-client-close` | Cleanup closes fixture clients with SIGTERM instead of sending `kill`. |

### Match the config premise

miracle-wm reads only YAML (`miracle-wm-c/src/config-cpp.cpp:1322-1389`). The translated
config removes default gaps, rounding and animation and disables automatic
workspace back-and-forth, matching the oracle's sway config:

| YAML setting | miracle-wm default and source |
| --- | --- |
| `border: {size: 2, radius: 0}` | 8 px rounded corners (`wiki/docs/configuration/border.md`); 2 px matches sway's `default_border normal 2`. |
| `inner_gaps: {x: 0, y: 0}` | 10 px (`wiki/docs/configuration/inner_gaps.md`) |
| `outer_gaps: {x: 0, y: 0}` | 10 px (`wiki/docs/configuration/outer_gaps.md`) |
| `enable_animations: false` | On (`wiki/docs/configuration/enable_animations.md`); sway has no animations. |
| `workspace_back_and_forth: false` | On (`wiki/docs/configuration/workspace_back_and_forth.md`); sway's `workspace_auto_back_and_forth` is off. |

These are not translated:

- Title bars: miracle-wm always uses client-side decorations (`Decorations::always_csd()`,
  `src/main.cpp`), so it cannot express `default_border normal 2` with a title bar.
- `font monospace 10`: miracle-wm draws no title text.
- `mode resize` and `bindsym`: modes are fixed (`default`, `resize`, `dragging`,
  `moving`, `overview`), and key bindings are not observable over IPC.
- Unsupported scenario commands, including `splith`, `splitv`, `kill`,
  `output`, `urgent` and `default_border`: their replies are measured unchanged.

### Match output size and initial focus

miracle-wm has no `output` command (`src/ipc_command.cpp:92-152`), so sway's runtime
`output * mode --custom 1280x720@60Hz` cannot be sent. Outputs start at 1270x1408
for state, 1280x720 for random/differential, or the scenario's `output_layout` sizes.

The adapter checks those sizes over GET_OUTPUTS.

Mir names virtual outputs `Virtual-1` onwards in command-line order
([Mir 2.26 output naming](https://github.com/canonical/mir/blob/v2.26.0/src/server/graphics/multiplexing_display.cpp#L195-L235),
[`Virtual` type name](https://github.com/canonical/mir/blob/v2.26.0/src/common/output_type_names.cpp#L22-L49)).
In the measured headless miracle-wm starts, workspace 1 belongs to `Virtual-1`
and initial focus is on the last configured output. For multi-output scenarios,
the adapter sends `focus output` to match sway's initial fake-0 focus.

### Close fixtures and wait for windows

`[app_id=...] kill` replies `Unsupported command type: kill`
(`src/ipc_command.cpp:92-152`). Cleanup finds fixture PIDs in GET_TREE and this
run's `--app-id=fixture-` processes, sends SIGTERM, then waits for an empty tree.

It then switches to `workspace __fixture_reset` and `workspace 1`, as sway does.

The process check catches scratchpad clients omitted by GET_TREE: miracle-wm has no
`__i3_scratch` workspace. When opening a client, the adapter waits for its
`window::new` event and app_id, when miracle-wm adds it to the tree, rather than a count.

## Read unsupported requests and failed steps

| Request or client | What the adapter records |
| --- | --- |
| GET_INPUTS, GET_SEATS | Not sent; captures record `not applicable`. miracle-wm closes without replying: no case in `src/ipc_message_handler.cpp:65-260`. |
| GET_CONFIG, GET_BAR_CONFIG | Also absent, but the oracle does not capture them. |
| All other requests | Sent and measured, including SYNC and SEND_TICK (the events tick barrier). |
| `foreign-toplevel-request` | Mir serves `zwlr_foreign_toplevel_manager_v1` and resolves app_ids through its desktop-file manager ([Mir 2.26 `foreign_toplevel_manager_v1.cpp:400-412`](https://github.com/canonical/mir/blob/v2.26.0/src/server/frontend_wayland/foreign_toplevel_manager_v1.cpp#L400-L412)). In the measured miracle-wm run, both handles reported process name `foot`, not the fixture app_id. The client finds no `fixture-*` handle and exits 1. `commands` measures `{"success": false, "error": "client exited with 1"}`; the run does not abort. |

## Check the build identity

0.11.2 reports GET_VERSION `human_readable` `0.9.1` (major 0, minor 9, patch 1).
Tracked `src/version.h` from `3983c5f` shadows generated `build/src/version.h`
(`CMakeLists.txt:124-128`). Results keep the reported version.

GET_VERSION has no commit. `version_details` cannot read the pin;
`check_started_build` calls `require_clean_binary` on the source checkout
every time the compositor starts.

The image builds with CMake and Fedora 44 Mir 2.26 (`mir-devel`,
`mir-internal-devel`), disabling tests, error reporter and debug overlay
(`-DENABLE_TESTS=OFF -DBUILD_ERROR_REPORTER=OFF -DBUILD_DEBUG_OVERLAY=OFF`).

The build regenerates tracked `src/wlr-output-management-unstable-v1_wrapper.{cpp,h}`
(`protocols/CMakeLists.txt:5-11`). Changes are formatting only; the image
restores these files to keep the checkout clean (`Containerfile`).

## Reproduce the snapshot and inspect crashes

Follow [snapshot reproduction](../../docs/reproducing.md) to build the pinned
image. Run each command below inside its own oracle container with
`--memory 4g --memory-swap 4g` and a writable `-v "$PWD:/oracle"` mount,
not the first check's read-only mount. These commands regenerate files under
`sway-ipc/results/`:

```sh
./contrib/validate reproduce miracle-wm --snapshot sway-ipc
./contrib/sway-ipc-run scenarios --corpus events --compositor miracle-wm --binary "$MIRACLE_WM_BINARY"
./contrib/sway-ipc-run command-fuzz --compositor miracle-wm --binary "$MIRACLE_WM_BINARY"
./contrib/sway-ipc-run wire-fuzz --compositor miracle-wm --binary "$MIRACLE_WM_BINARY"
./contrib/sway-ipc-run random --compositor miracle-wm --binary "$MIRACLE_WM_BINARY"
```

The first command runs full `scenarios.toml`; committed results keep only sway 1.12's selected
scenarios, as required by `contrib/validate`.

Crashes mark each remaining capture row `verdict = "crash"`, with the scenario,
action and exit. The next scenario starts a fresh compositor. Wire-fuzz and
random record crashes the same way.

| Run | Observation |
| --- | --- |
| Committed state | 32 crash rows from two scenarios. `workspace_move_to_own_mark_wraps_children` contributes 8 rows, with SIGSEGV at `move container to mark m`. `scratchpad_split_view_close_keeps_group` contributes 24 rows: 8 each under that capture name and its `_hidden` and `_shown` names, with SIGSEGV at `move container to mark ssvc`. |
| Earlier full-state reruns | `workspace_move_to_own_mark_wraps_children` SIGSEGVs at `move container to mark m` in 3/3 fresh runs. `move_floating_split_to_own_child_mark` crashed at `move container to mark z` in one full run, but not in 3 later fresh runs; its committed rows are not crashes. Both scenarios are in the committed sway 1.12 selection. |
| Committed command fuzz | 3 crash rows: `[app_id=] exit`, `[oracle_field=value] exit`, and `gaps inner current set 2147483648` stop the process. |
| Committed wire fuzz | 2 crash rows: invalid JSON in SUBSCRIBE (uncaught `json::parse`, `src/ipc_message_handler.cpp:112`) and invalid UTF-8 in COMMAND stop the process. |

Count the committed state crash rows by capture name (the `_hidden` and
`_shown` captures belong to the same scratchpad scenario):

```sh
python3 - <<'PY'
from collections import Counter
import tomllib

with open("sway-ipc/results/miracle-wm-0.11.2.toml", "rb") as stream:
    result = tomllib.load(stream)
counts = Counter(row["scenario"] for row in result["result"]
                 if row["verdict"] == "crash")
print("crash rows:", sum(counts.values()))
for capture, count in sorted(counts.items()):
    print(capture, count)
PY
```

There is no [i3-derived](../../docs/results.md#how-to-read-a-block) result yet. The corpus has been
[recaptured](../../docs/reproducing.md#the-i3-derived-recapture); a miracle-wm replay
has not been run or committed.
