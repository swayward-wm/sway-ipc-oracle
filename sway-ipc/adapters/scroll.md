# scroll adapter

`ScrollAdapter` in `contrib/sway-ipc-run` measures scroll 1.12.21
(`scroll-1.12.21`, commit pinned in `pins.toml`) the way `SwayAdapter` measures
sway 1.12. It is a subclass that inherits:

- the headless wlroots backend, private `XDG_RUNTIME_DIR`, memory cap and
  wall-time limit;
- the sway config text, the random-corpus config, and the `fake-N` to
  `HEADLESS-(count-N)` output mapping for multi-output scenarios;
- the foot, `xdg-toplevel-fixture` and `foreign-toplevel-request` clients, and
  the capabilities.

## Socket

scroll takes its IPC socket path from `SCROLLSOCK` and ignores `SWAYSOCK`
(`sway/ipc-server.c:101-102`). The adapter sets `SCROLLSOCK` to the same private
socket path that `SWAYSOCK` names for sway, and removes any ambient
`SCROLLSOCK` from the environment.

## Translations

| Rule | Translation | Why |
| --- | --- | --- |
| `scroll-animations-off` | The rendered config gains `animations enabled no`. | scroll animates window moves and resizes by default (`sway/scroll.5.scd:68-73`, `sway/desktop/animation.c:187`). With animations on, a capture can read geometry mid-animation. sway has no animations, so the oracle's premise is a compositor that lays out immediately. |

The rule applies to every row, so each scroll result records it once in its
`[run]` table: `adapted = ["scroll-animations-off"]`. No command or reply is
rewritten.

Not translated, on purpose: scroll's column layout and its default column width
(`layout_default_width 0.5`, `sway/config.c:246`). Changing them would change
what a scenario means. Scenarios that use `split`, `layout`, tabbed or stacked
layouts run as written; scroll answers those commands with its own errors.

## Version

scroll reports `human_readable` as `1.13-dev-<commit> (<date>, branch
'<branch>')` (`meson.build:4,160-171`; the 1.12.21 tag carries meson version
`1.13-dev`). `version_details` takes the commit from it to check the pin, as the
SwayFX adapter does.

## Build and renderer

The oracle image builds scroll from the pinned commit with its own in-tree
wlroots 0.21-dev (`subprojects/wlroots`; `meson.build:42-49` requires
`>=0.21.0,<0.22.0`), not the wlroots pin that sway uses. It needs `lua-devel`
and `readline-devel`, and it uses sway's meson options (`Containerfile`).
`$SCROLL_BINARY` names the binary.

scroll creates its renderer with `wlr_renderer_autocreate`
(`sway/server.c:280`). In the oracle container, with no render node, wlroots
falls back to the pixman renderer, so scroll needs no `--device`.

## Running the snapshots

Each command runs in its own oracle container with
`--memory 4g --memory-swap 4g`:

```sh
./contrib/validate reproduce scroll --snapshot sway-ipc
./contrib/sway-ipc-run scenarios --corpus events --compositor scroll --binary "$SCROLL_BINARY"
./contrib/sway-ipc-run command-fuzz --compositor scroll --binary "$SCROLL_BINARY"
./contrib/sway-ipc-run wire-fuzz --compositor scroll --binary "$SCROLL_BINARY"
./contrib/sway-ipc-run random --compositor scroll --binary "$SCROLL_BINARY"
```

The first command runs the full state corpus (`scenarios.toml`) and writes
`sway-ipc/results/scroll-1.12.21.toml`. `contrib/validate` requires every state
result to cover the scenarios of the committed sway 1.12 state result, so the
committed scroll result keeps those rows until the release-candidate
regeneration replaces every state result.

## Known crash

Random seed 306 segfaults scroll 1.12.21 (3 of 3 fresh runs) at step 16,
`resize shrink height 10 px`, when the focused container is a column
container rather than a view (step 15 moved a tiled view to workspace 2):
`view_get_constraints(view=NULL)`
(`sway/tree/view.c:271`) from `resize_adjust_tiled`
(`sway/commands/resize.c:119`). The random result records it as
`verdict = "crash"`. Pinned sway answers the same sequence.

scroll has no i3-derived result yet: the i3-derived corpus awaits its sway
recapture (`pending.toml`).
