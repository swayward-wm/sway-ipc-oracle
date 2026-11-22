# swirl adapter

`SwirlAdapter` measures swirl's pinned `main` commit (`swirl-dc6382f2`).
With no releases or tags, swirl rebrands scroll 1.12.17 (scroll commit `262b38c8`).
Its snapshot measures that version's sway IPC behaviour, not scroll 1.12.21's.

## Run a first check

From a regular oracle clone, with the [pinned image](../../docs/reproducing.md) built:

```sh
OUT="${OUT:-$PWD/target/swirl}"
mkdir -p "$OUT/tmp"
podman run --rm --memory 4g --memory-swap 4g --security-opt label=disable \
  -v "$PWD:/oracle:ro" -v "$OUT:/out" sway-ipc-oracle bash -c \
  'export TMPDIR=/out/tmp; ./contrib/sway-ipc-run command-fuzz --compositor swirl \
    --binary "$SWIRL_BINARY" --out /out/command-fuzz.toml' > "$OUT/run.log" 2>&1 &
PID=$!; wait "$PID"; echo "$?"
```

[Read exit codes](../../docs/ci.md#run-a-corpus) and
[run other corpora](../../docs/ci.md#pick-the-corpora), using
`SWIRL_BINARY` inside the image. Use one 4 GiB, zero-swap container per command.

## Check what the adapter preserves

`SwirlAdapter` subclasses [scroll's adapter](scroll.md#check-what-the-adapter-preserves)
in `contrib/sway-ipc-run`, changing only the build check. It inherits scroll's
config, clients, output mapping, limits and headless setup.

## Socket

The default socket is `sway-ipc.<uid>.<pid>.sock`; `SCROLLSOCK` still overrides
it and `SWAYSOCK` is ignored (`sway/ipc-server.c:100-101`, `143`). The inherited
scroll adapter sets `SCROLLSOCK` to the private path.

## Translations

The scroll translation, inherited unchanged:

| Rule | Translation | Why |
| --- | --- | --- |
| `scroll-animations-off` | The rendered config gains `animations enabled no`. | swirl keeps scroll's animations, on by default (`sway/scroll.5.scd:68-73`; the `animations` config command, `sway/commands.c:121`). |

Each swirl result records it once in its `[run]` table:
`adapted = ["scroll-animations-off"]`. As for scroll, the column layout and
its default width are not translated.

## Version and build check

GET_VERSION reports `human_readable` `1.13-dev` and `variant` `swirl`, with no
commit (`meson.build:170-172`, `sway/ipc-json.c:234-235`). `version_details`
reports the commit as unknown.

- The result's commit comes from the source checkout: it must be clean with
  `HEAD` at the pin before the run starts.
- Each started compositor must report variant `swirl` and version `1.13-dev`.
- The binary's content hash must stay the same throughout the run;
  a rebuild during the run is refused.

## Build and renderer

The image uses pinned swirl's in-tree wlroots 0.21-dev, `lua-devel`,
`readline-devel` and sway's meson options, as for scroll (`Containerfile`).
`SWIRL_BINARY` names the binary (`sway/meson.build:284-285`).

Pinned `meson.build:227-230` tries to install a missing `swirl.png` (the rebrand
removed `scroll.png`). The image creates an empty file for setup, then removes
it and `subprojects/.wraplock` before the cleanliness check. It is not compiled.

As for scroll, the renderer falls back to pixman with no render node
(`sway/server.c:280`), so no `--device` is needed.

## Reproduce the published snapshot

Follow [snapshot reproduction](../../docs/reproducing.md) to build the pinned
image. Run each command below inside its own oracle container with
`--memory 4g --memory-swap 4g` and a writable `-v "$PWD:/oracle"` mount,
not the first check's read-only mount. These commands regenerate files under
`sway-ipc/results/`:

```sh
./contrib/validate reproduce swirl --snapshot sway-ipc
./contrib/sway-ipc-run scenarios --corpus events --compositor swirl --binary "$SWIRL_BINARY"
./contrib/sway-ipc-run command-fuzz --compositor swirl --binary "$SWIRL_BINARY"
./contrib/sway-ipc-run wire-fuzz --compositor swirl --binary "$SWIRL_BINARY"
./contrib/sway-ipc-run random --compositor swirl --binary "$SWIRL_BINARY"
```

The first command runs full `scenarios.toml`; the committed result keeps sway 1.12's selected
scenarios until release-candidate regeneration, as [scroll does](scroll.md#reproduce-the-published-snapshot).

## Read the full-state observations

When measured, the full corpus had 4,777 rows over 545 captures: swirl matched
3,555 and mismatched 1,222, the same totals as scroll 1.12.21 on that tree.
Two rows differed, both outside the committed selection:

- `global_fullscreen_floating_workspace_switch.command` matches sway on swirl
  and fails on scroll in 3 of 3 runs each. It sends `workspace number 3`
  under a global fullscreen view that was then floated.
- scroll has `ded02434` (sway chase `7e8b4d36`), updating the global fullscreen
  pointer on reparenting; swirl lacks it (`sway/tree/container.c:1814-1822`).
  It likely explains the first difference, but that cause is not verified.
- `global_fullscreen_floated_split_px_resize_up.command` is [unstable](../../docs/results.md#how-to-read-a-block)
  on both: it mismatched in 2 of 3 scroll reruns and 1 of 3 swirl reruns.

## Known crash

Random seed 306 segfaults swirl at step 16, `resize shrink height 10 px`,
as it does [scroll](scroll.md#known-crash). The same code calls
`view_get_constraints(view=NULL)` (`sway/tree/view.c:270`).

The caller is `resize_adjust_tiled` (`sway/commands/resize.c:125`);
the random result records `verdict = "crash"`.

swirl has no i3-derived result yet. The corpus has been
[recaptured](../../docs/reproducing.md#the-i3-derived-recapture); a swirl replay
has not been run or committed.
