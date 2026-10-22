# miracle-wm adapter

`MiracleAdapter` in `contrib/sway-ipc-run` measures miracle-wm 0.11.2
(`miracle-wm-0.11.2`, commit pinned in `pins.toml`). miracle-wm is a Mir
compositor, not a wlroots one. It speaks i3/sway IPC and a subset of sway's
command language. The adapter shares the foot and `xdg-toplevel-fixture`
clients, the memory cap and the wall-time limit with the other Wayland
adapters. Everything else below is specific to miracle-wm.

## Headless start

These flags start miracle-wm headless, the same way its own end-to-end harness
does (`e2e/conftest.py:59`):

```sh
miracle-wm --config RUN/config.yaml --display-config-path RUN/display.yaml \
  --platform-display-libs=mir:virtual --platform-input-lib=mir:stub-input \
  --enable-x11 false --virtual-output=WxH [--virtual-output=WxH ...]
```

- `mir:stub-input` ships in Fedora's `mir-test-tools` package, not in
  `mir-server-libs`. Without it, miracle-wm logs its IPC socket path, then
  exits with status 1 and prints no error.
- `--enable-x11 false` turns off Xwayland. It is on by default
  (`src/main.cpp:268`), and Mir aborts with "Cannot execute Xwayland" if
  `/usr/bin/Xwayland` is missing. The oracle opens only Wayland clients.
- The IPC socket path comes from `MIRACLESOCK`
  (`src/ipc_connection_manager.cpp:134-137`). The adapter sets it to the
  run's private `ipc.sock` and removes any ambient `MIRACLESOCK`.
  `XDG_RUNTIME_DIR` and `XDG_CONFIG_HOME` point into the run directory.
- miracle-wm prints GLib "G_IS_DBUS_CONNECTION" criticals on start and exit
  because the container has no session bus. They are harmless.

## Translations

Each rule applies to every row, so each miracle-wm result records all three
once in its `[run]` table:
`adapted = ["miracle-config-yaml", "miracle-outputs-virtual", "miracle-reset-client-close"]`.
No command or reply is rewritten.

| Rule | Translation | Why |
| --- | --- | --- |
| `miracle-config-yaml` | The oracle's sway config becomes miracle's YAML config: `border: {size: 2, radius: 0}`, `inner_gaps: {x: 0, y: 0}`, `outer_gaps: {x: 0, y: 0}`, `enable_animations: false` and `workspace_back_and_forth: false`. The random and differential config is the same file. | miracle-wm reads only YAML (`miracle-wm-c/src/config-cpp.cpp:1322-1389`). Its defaults differ from sway's, and those differences would move every rectangle or change command meaning: 10 px inner and outer gaps (`wiki/docs/configuration/inner_gaps.md`, `outer_gaps.md`), 8 px rounded corners (`border.md`), animations on (`enable_animations.md`), and `workspace_back_and_forth` on (`workspace_back_and_forth.md`). sway has no gaps, square corners and no animations, and `workspace_auto_back_and_forth` is off. The 2 px border matches sway's `default_border normal 2` width. |
| `miracle-outputs-virtual` | Each headless output becomes a `--virtual-output=WxH` (1270x1408 for the state corpus, 1280x720 for random and differential runs, or the scenario's `output_layout` sizes), and their positions go into a display YAML. i3's `fake-N` maps to `Virtual-(N+1)`. With more than one output, the adapter sends `focus output` for the scenario's initial output after start. | miracle-wm has no `output` command (`src/ipc_command.cpp:92-152`), so the sway adapter's runtime `output * mode --custom 1280x720@60Hz` cannot be sent. The outputs start at that size instead, and the adapter checks the size over GET_OUTPUTS. Mir names virtual outputs `Virtual-1` onwards in command-line order and gives workspace 1 to `Virtual-1`. Mir focuses the last output it configures, while sway starts on fake-0's output. |
| `miracle-reset-client-close` | Between scenarios, `reset()` sends SIGTERM to each fixture window's client (its `pid` from GET_TREE, plus every process of the run whose command line carries `--app-id=fixture-`, since GET_TREE omits scratchpad windows) and waits until GET_TREE shows no fixture window. It then switches to `workspace __fixture_reset` and `workspace 1`, as the sway adapter does. | miracle-wm has no `kill` command (`src/ipc_command.cpp:92-152`; `[app_id=...] kill` replies `Unsupported command type: kill`). The windows close from the client side instead. This is a harness translation of the reset step only. Scenario actions that send `kill` go to miracle-wm unchanged and are measured. |

Not translated, on purpose:

- `default_border normal 2` with a title bar. miracle-wm always uses
  client-side decorations (`Decorations::always_csd()`, `src/main.cpp`), so it
  has no server-side title bar to configure.
- `font monospace 10`. miracle-wm draws no title text.
- `mode resize { ... }` and the `bindsym` lines. miracle-wm's binding modes are
  fixed (`default`, `resize`, `dragging`, `moving`, `overview`), and key
  bindings are not observable over IPC.
- Commands miracle-wm does not know, such as `splith`, `splitv`, `kill`,
  `output`, `urgent` and `default_border`. They go to miracle-wm unchanged,
  and its replies are measured.

## Requests it does not implement

GET_INPUTS and GET_SEATS have no `case` in `src/ipc_message_handler.cpp`
(65-260). miracle-wm closes the connection without replying. The adapter does
not send them, and each capture records `inputs` and `seats` as
`not applicable`, citing that source. GET_CONFIG and GET_BAR_CONFIG are absent
too, but the oracle does not capture them. Every other request is sent and
measured, including SYNC and SEND_TICK, the tick barrier of the events corpus.

## Window synchronisation

miracle-wm has no `__i3_scratch` workspace, so GET_TREE omits scratchpad
windows. The other adapters open a window and wait until GET_TREE shows one
more fixture window. A window that a `for_window` rule sends to the
scratchpad would never show up that way. This adapter therefore waits for the
`window` event with change `new` and the window's app_id. That is the same
point at which miracle-wm adds the window to its tree.

## Foreign toplevel

Mir serves `zwlr_foreign_toplevel_manager_v1`, but its toplevel handles carry
the client's process name (`foot`) as the app_id, not the xdg-toplevel app_id
(observed: both fixture windows reported `foot`). `foreign-toplevel-request`
therefore finds no `fixture-*` toplevel and exits with status 1. The adapter
records that as a failed step reply
(`{"success": false, "error": "client exited with 1"}`), which the scenario's
`commands` row measures. It does not abort the run.

## Version

miracle-wm 0.11.2 reports `human_readable` `"0.9.1"`, with major 0, minor 9
and patch 1. The repository tracks a stale `src/version.h` (from the 0.9.1
bump, `3983c5f`). It sits beside the generated `build/src/version.h` and
shadows it (`CMakeLists.txt:124-128`). GET_VERSION carries no commit, so
`version_details` cannot read the pin from it. `check_started_build` instead
re-checks the checkout behind the started binary (`require_clean_binary`) each
time a compositor starts. The results record the version as reported.

## Build

The oracle image builds miracle-wm from the pinned commit with CMake, against
Fedora 44's Mir 2.26 packages (`mir-devel`, `mir-internal-devel`), with
`-DENABLE_TESTS=OFF -DBUILD_ERROR_REPORTER=OFF -DBUILD_DEBUG_OVERLAY=OFF`
(`Containerfile`). The build regenerates
`src/wlr-output-management-unstable-v1_wrapper.{cpp,h}`, which are tracked
(`protocols/CMakeLists.txt:5-11`). The regenerated files differ only in
formatting, so the image restores them afterwards to keep the checkout clean.
`$MIRACLE_WM_BINARY` names the binary. Mir falls back to software buffers in
the container, so no render node is needed.

## Running the snapshots

Each command runs in its own oracle container with
`--memory 4g --memory-swap 4g`:

```sh
./contrib/validate reproduce miracle-wm --snapshot sway-ipc
./contrib/sway-ipc-run scenarios --corpus events --compositor miracle-wm --binary "$MIRACLE_WM_BINARY"
./contrib/sway-ipc-run command-fuzz --compositor miracle-wm --binary "$MIRACLE_WM_BINARY"
./contrib/sway-ipc-run wire-fuzz --compositor miracle-wm --binary "$MIRACLE_WM_BINARY"
./contrib/sway-ipc-run random --compositor miracle-wm --binary "$MIRACLE_WM_BINARY"
```

The first command runs the full state corpus (`scenarios.toml`). The committed
state result keeps only the scenarios of the committed sway 1.12 state result,
because `contrib/validate` requires every state result to cover them.

## Crashes

A scenario that kills miracle-wm records `verdict = "crash"` for each capture
row it had left, with the scenario, the action and the exit. The run then
continues with the next scenario on a fresh compositor. Wire-fuzz and random
crashes are recorded the same way.

Observed:

- State, in the full `scenarios.toml` run only: the committed state result
  has no crash rows, because neither scenario below is in the sway 1.12
  selection. `workspace_move_to_own_mark_wraps_children` SIGSEGVs miracle-wm
  at `move container to mark m` (3 of 3 fresh runs), so its 8 capture rows
  are `crash`. In one full run, `move_floating_split_to_own_child_mark` also
  crashed at `move container to mark z`, but it did not crash in 3 later
  fresh runs.
- Command fuzz (committed result, 3 crash rows): `[app_id=] exit` and `[oracle_field=value] exit` stop the
  compositor, and so does `gaps inner current set 2147483648`.
- Wire fuzz (committed result, 2 crash rows): a SUBSCRIBE with invalid JSON and a COMMAND with invalid UTF-8
  end the process. The first is an uncaught `json::parse` in
  `src/ipc_message_handler.cpp:112`.

miracle-wm has no i3-derived result yet: the i3-derived corpus awaits its sway
recapture (`pending.toml`).
