# Sway IPC fixtures

These files record the JSON schema and values returned by sway's IPC. The query fixtures and sequence fixtures were last
captured from sway 1.12 on 2026-09-22. `schema-version.json` pins the target tag
and commit. The individual event fixtures and `inputs-libinput.json` remain
sway 1.11 captures as noted below.

## Capture environment

- sway: 1.12, tag commit `88869399f421d9180dd8b6ed0b5a1f4a3585d252`
- host: `linuxpc`, Fedora Linux 44.20260922.0 (Sway Atomic)
- backend: wlroots Wayland backend, nested inside the operator's sway session
- output: `WL-1`, 1270x1408, scale 1, normal transform
- config: solid-color output background, 2 px normal borders, monospace 10
- client: standalone foot terminals with unique `fixture-*` app IDs
- capture command: `contrib/sway-ipc-run --compositor sway --binary /path/to/sway --capture`
- scenario source: `sway-ipc/scenarios.toml`

Each captured scenario has the raw replies to `get_tree`, `get_workspaces`, and
`get_outputs`, formatted only with `jq -S .` for stable key order. Each also has
an `*.events.json` file captured after subscribing to all nine event families;
the ordered stream ends at a runner-generated `SEND_TICK` barrier. The
`two_floating` and `three_floating_*` scenarios show that `floating_nodes` uses
back-to-front stacking order, while the workspace `focus` array lists the
focused floating window first. `three_floating_after_raise` focuses
`fixture-1`, making the order change observable.

The `urgent_via_command` scenario records compositor-originated urgency set by
sway's `urgent enable` IPC command. It does not cover client-originated urgency:
foot emitting BEL and an xterm bell did not raise urgency in the nested sway
capture environment.

The named corner-case scenarios keep fixes from depending only on large random
or i3-derived sequences. They cover empty-workspace command errors and layout
lifecycle, fullscreen map and split-wrapper state, workspace focus recency,
singleton directional moves, scratchpad unfloat, moving a container tree onto
an empty workspace, and parser error replies. Each fixture was captured from
the pinned sway 1.12 build through the ordinary scenario runner.

`inputs.json` was recaptured with the query fixtures from the sway 1.12
Wayland-backend session. It records the backend-neutral pointer and keyboard
values. `inputs-libinput.json` was captured on 2026-09-20 from a capped sway
1.11 `WLR_BACKENDS=headless,libinput` session using the operator's Logitech G703.
It records the real USB IDs and every libinput property that device exposes.
Both files are raw `GET_INPUTS` replies formatted only with `jq`.

## i3-suite-derived fixtures

`sway-ipc/i3-derived/` contains states reached by i3's own unchanged tests and
captured from sway 1.12. The calibration recorder preserves each command's
`.t` file and line. `contrib/sway-ipc-run i3-derived --capture` replays those
logs against pinned sway, reduces every reply to a layout-shape hash for
deduplication, and stores one raw sway capture per distinct shape. The manifest
records X11-identity and process-lifecycle sequences that could not be replayed;
the runner does not invent Wayland substitutes for them.

## Random sequence corpus

`sway-ipc/random/` contains 500 deterministic 20-step command sequences. The
runner captured every command reply, `GET_TREE`, and `GET_WORKSPACES` reply from
pinned sway 1.12 after the state settled. `objects/` stores canonical JSON by
content hash, and `sequences.json` maps each seed and step to those objects.
Capture with `contrib/sway-ipc-run random --compositor sway --binary /path/to/sway
--capture --seeds 500 --steps 20`; replay by omitting `--capture`.

## Oracle policy

Never edit these fixtures by hand to make a compositor test pass. If a
compositor intentionally differs, record the difference outside the fixture.

Only replace fixtures with `contrib/sway-ipc-run --capture` against the pinned
sway binary. The runner starts a capped headless compositor with private IPC and
Wayland sockets; it never targets the ambient session.

Run `contrib/check-sway-fixture-schema /path/to/sway` with the sway checkout at
tag `1.12`. It reads the target from `schema-version.json`, extracts the output
and native-view field sets from `sway/ipc-json.c`, and compares them with
representative captures. The check fails if the checkout is not the pinned tag
or if a field changes. Update the target and recapture before accepting a later
sway release.

## Event fixtures

The `*.sequence.json` files in `events/` were recaptured from sway 1.12 on
2026-09-22. The individual mode, window-mutation, and workspace-mutation event
fixtures were recaptured from sway 1.12 with `contrib/sway-ipc-run
--capture-events`; event types that require input injection or exact map-time
subscription remain the original captures. Window events containing a native
view include sway 1.12's unconditional `tag` field. `binding.run.json` used
`bindsym Shift+Ctrl+t nop` and injected the chord through sway's
virtual-keyboard protocol.

The `*.sequence.json` files preserve complete ordered event lists from the sway
1.12 installation. Event-sequence capture has not yet moved into the Python
runner, so capture mode leaves these files unchanged. `workspace-switch-empty` captures a switch to
an empty workspace and back. `workspace-close-last` captures closing the final
window on an inactive workspace. `workspace-rename` captures a rename. The
`workspace-move-right-*` files capture a focused window moving across two
headless outputs into an empty workspace, into an occupied workspace, and away
from its source workspace's last window. Sway 1.12 emits one `window::move`
event and no workspace event in all three cases. A future scenario extension
must capture subscriptions through the same runner and use sway `SEND_TICK` as
the end-of-stream barrier.

The 27 existing event fixtures remain as focused examples of individual event
payloads and multi-event transitions. The per-scenario event corpus folds their
covered window, workspace, and mode changes into replayable whole-scenario
streams while preserving these fixtures for precise protocol checks.

`window-map-focused.sequence.json` and `window-map-unfocused.sequence.json`
were recaptured from the capped sway 1.12 Wayland-backend session. Mapping a
focused window emitted `new`, `title`, then `focus`. A window matched by
`no_focus` emitted only `new` and `title`. The `title` event comes from foot
setting its title after map; the focus distinction is independent of it.

The original capture produced all requested workspace changes: `init`, `empty`,
`focus`, `move`, `rename`, `urgent`, and `reload`. It also produced all requested
window changes: `new`, `close`, `focus`, `title`, `fullscreen_mode`, `move`,
`floating`, `urgent`, and `mark`. Mode fixtures cover `resize` and the return to
`default`. The binding fixture covers sway's complete `change: "run"` keyboard
payload.

The headless conformance test uses `workspace.reload.json`, `window.focus.json`,
and `mode.default.json` because those states match deterministic harness events.
The other files preserve real sway payloads for future event-specific tests.
Never derive or hand-edit an event fixture from the compositor under test.

## Fuzz fixtures

`sway-ipc/fuzz/command-fuzz.json` and `sway-ipc/fuzz/wire-fuzz.json` were
captured on 2026-09-26 from pinned sway 1.12 (`88869399`) with
`contrib/sway-ipc-run {command,wire}-fuzz --capture`, one fresh headless
compositor per case, in the environment above. Each entry records the input
(command text, or the raw frame as hex) and sway's observation. Only
`GET_VERSION` payloads are reduced to their key set, because they name the build
and the private config path. The same never-hand-edit rule applies.
