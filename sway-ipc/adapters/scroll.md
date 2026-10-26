# scroll adapter

`ScrollAdapter` measures scroll 1.12.21 (`scroll-1.12.21`, pinned in `pins.toml`).

## Run a first check

From a regular oracle clone, with the [pinned image](../../docs/reproducing.md) built:

```sh
OUT="${OUT:-$PWD/target/scroll}"
mkdir -p "$OUT/tmp"
podman run --rm --memory 4g --memory-swap 4g --security-opt label=disable \
  -v "$PWD:/oracle:ro" -v "$OUT:/out" sway-ipc-oracle bash -c \
  'export TMPDIR=/out/tmp; ./contrib/sway-ipc-run command-fuzz --compositor scroll \
    --binary "$SCROLL_BINARY" --out /out/command-fuzz.toml' > "$OUT/run.log" 2>&1 &
PID=$!; wait "$PID"; echo "$?"
```

[Read exit codes](../../docs/ci.md#run-a-corpus) and
[run other corpora](../../docs/ci.md#pick-the-corpora), using
`SCROLL_BINARY` inside the image. Use one 4 GiB, zero-swap container per command.

## Check what the adapter preserves

`ScrollAdapter` subclasses `SwayAdapter` in `contrib/sway-ipc-run`:

- Same headless wlroots backend, private runtime directory and memory/time limits.
- Same state/random configs, capabilities and `fake-N` to `HEADLESS-(count-N)` mapping.
- Same foot, `xdg-toplevel-fixture` and `foreign-toplevel-request` clients.

## Socket

scroll reads `SCROLLSOCK`, ignoring `SWAYSOCK` (`sway/ipc-server.c:101-102`).
The adapter replaces any ambient `SCROLLSOCK` with the private socket path,
as `SWAYSOCK` does for sway.

## Translations

| Rule | Translation | Why |
| --- | --- | --- |
| `scroll-animations-off` | The rendered config gains `animations enabled no`. | scroll animates window moves and resizes by default (`sway/scroll.5.scd:68-73`, `sway/desktop/animation.c:187`). With animations on, a capture can read geometry mid-animation. sway has no animations, so the oracle's premise is a compositor that lays out immediately. |

The rule applies to every row, so each scroll result records it once in its
`[run]` table: `adapted = ["scroll-animations-off"]`. Apart from the
inherited `fake-N` output names, no command or reply is rewritten.

The column layout and default width (`layout_default_width 0.5`,
`sway/config.c:246`) are not translated: that would change the test's meaning.
`split`, `layout`, tabbed and stacked scenarios run as written and measure scroll's errors.

## Version

scroll reports `human_readable` as `1.13-dev-<commit> (<date>, branch '<branch>')`.
The 1.12.21 tag uses meson version `1.13-dev` (`meson.build:4,160-171`).
`version_details` reads the commit to check the pin, as SwayFX does.

## Build and renderer

The image builds pinned scroll with its in-tree wlroots 0.21-dev, not sway's
wlroots pin (`subprojects/wlroots`; `meson.build:42-49` requires `>=0.21.0,<0.22.0`).
It uses `lua-devel`, `readline-devel` and sway's meson options (`Containerfile`).

scroll creates its renderer with `wlr_renderer_autocreate`
(`sway/server.c:280`). In the oracle container, with no render node, wlroots
falls back to the pixman renderer, so scroll needs no `--device`.

## Reproduce the published snapshot

Follow [snapshot reproduction](../../docs/reproducing.md) to build the pinned
image. Run each command below inside its own oracle container with
`--memory 4g --memory-swap 4g` and a writable `-v "$PWD:/oracle"` mount,
not the first check's read-only mount. These commands regenerate files under
`sway-ipc/results/`:

```sh
./contrib/validate reproduce scroll --snapshot sway-ipc
./contrib/sway-ipc-run scenarios --corpus events --compositor scroll --binary "$SCROLL_BINARY"
./contrib/sway-ipc-run command-fuzz --compositor scroll --binary "$SCROLL_BINARY"
./contrib/sway-ipc-run wire-fuzz --compositor scroll --binary "$SCROLL_BINARY"
./contrib/sway-ipc-run random --compositor scroll --binary "$SCROLL_BINARY"
```

The first command runs full `scenarios.toml`; the committed snapshot keeps sway 1.12's selected
scenarios until release-candidate regeneration replaces all state results.

`contrib/validate` requires every state result to cover that same selection.
The state snapshot is `sway-ipc/results/scroll-1.12.21.toml`.

## Known crash

Random seed 306 segfaults scroll 1.12.21 in 3 of 3 fresh runs at step 16,
`resize shrink height 10 px`. Step 15 moved a tiled view to workspace 2;
the focused container is then a column, not a view.

`resize_adjust_tiled` (`sway/commands/resize.c:119`) calls
`view_get_constraints(view=NULL)` (`sway/tree/view.c:271`). The random result
records `verdict = "crash"`; pinned sway answers the same sequence.

scroll has no i3-derived result yet. The corpus has been
[recaptured](../../docs/reproducing.md#the-i3-derived-recapture); a scroll replay
has not been run or committed.
