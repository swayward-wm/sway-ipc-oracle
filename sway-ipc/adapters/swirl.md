# swirl adapter

`SwirlAdapter` in `contrib/sway-ipc-run` measures swirl at its `main` commit
(`swirl-dc6382f2`, commit pinned in `pins.toml`). swirl has no releases or
tags. It is a rebrand of scroll 1.12.17 (scroll `262b38c8`), so it is measured
as scroll is: `SwirlAdapter` subclasses `ScrollAdapter`
([`scroll.md`](scroll.md)) and changes only the build check. A swirl snapshot
is therefore a measurement of scroll 1.12.17's sway-IPC behaviour, not of
scroll 1.12.21's.

## Socket

swirl renamed its default socket to `sway-ipc.<uid>.<pid>.sock`, but the
override variable is still `SCROLLSOCK` (`sway/ipc-server.c:100-101`, `143`),
and `SWAYSOCK` is ignored. The inherited scroll adapter sets `SCROLLSOCK` to
the private socket path.

## Translations

The scroll translation, inherited unchanged:

| Rule | Translation | Why |
| --- | --- | --- |
| `scroll-animations-off` | The rendered config gains `animations enabled no`. | swirl keeps scroll's animations, on by default (`sway/scroll.5.scd:68-73`; the `animations` config command, `sway/commands.c:121`). |

Each swirl result records it once in its `[run]` table:
`adapted = ["scroll-animations-off"]`. As for scroll, the column layout and
its default width are not translated.

## Version and build check

swirl's `meson.build:170-172` removed the git suffix from the version, so
`human_readable` is only `1.13-dev` and `variant` is `swirl`
(`sway/ipc-json.c:234-235`). GET_VERSION names no commit, so it cannot check the
pin, and `version_details` reports the commit as unknown. The commit recorded
in each result comes from the source checkout, which every run checks before it
starts: `HEAD` must be the pin and the checkout must be clean. Instead of a
commit, each started compositor must report `variant` `swirl` and
`human_readable` `1.13-dev`, and the binary must have the same content hash
for the whole run, so a rebuild during the run is refused.

## Build and renderer

The oracle image builds swirl from the pinned commit with its in-tree wlroots
0.21-dev (`subprojects/wlroots`), `lua-devel` and `readline-devel`, and sway's
meson options, as for scroll (`Containerfile`). `$SWIRL_BINARY` names the
binary (`sway/meson.build:284-285`). The pinned `meson.build:227-230` installs
`swirl.png`, which the tree does not contain (the rebrand removed
`scroll.png`), so `meson setup` fails. The image creates an empty `swirl.png`
for setup only and removes it, with meson's `subprojects/.wraplock`, before the
checkout is checked for cleanliness. The file is install data and is not
compiled into the binary.

As for scroll, the renderer falls back to pixman with no render node
(`sway/server.c:280`), so no `--device` is needed.

## Running the snapshots

Each command runs in its own oracle container with
`--memory 4g --memory-swap 4g`:

```sh
./contrib/validate reproduce swirl --snapshot sway-ipc
./contrib/sway-ipc-run scenarios --corpus events --compositor swirl --binary "$SWIRL_BINARY"
./contrib/sway-ipc-run command-fuzz --compositor swirl --binary "$SWIRL_BINARY"
./contrib/sway-ipc-run wire-fuzz --compositor swirl --binary "$SWIRL_BINARY"
./contrib/sway-ipc-run random --compositor swirl --binary "$SWIRL_BINARY"
```

The first command runs the full state corpus (`scenarios.toml`). As for scroll,
the committed state result keeps the rows of the scenarios in the committed
sway 1.12 state result until the release-candidate regeneration.

On the full state corpus (4,777 rows over 545 captures when measured), swirl
has 3,555 match and 1,222 mismatch, the same totals as scroll 1.12.21 measured
on the same tree. Two rows differ, both outside the committed rows.
`global_fullscreen_floating_workspace_switch.command` (`workspace number 3`
under a global fullscreen view that was then floated) matches sway on swirl and
fails on scroll in 3 of 3 runs each. scroll 1.12.21 has `ded02434` (sway chase
7e8b4d36, which updates the global fullscreen pointer when a container is
reparented) and swirl does not (`sway/tree/container.c:1814-1822`). That this
commit causes the difference is likely but not verified.
`global_fullscreen_floated_split_px_resize_up.command` is unstable on both
compositors: it mismatched in 2 of 3 scroll reruns and in 1 of 3 swirl reruns.

## Known crash

Random seed 306 segfaults swirl at step 16, `resize shrink height 10 px`, as
it segfaults scroll 1.12.21 (see [`scroll.md`](scroll.md)): the code is the
same, `view_get_constraints(view=NULL)` (`sway/tree/view.c:270`) from
`resize_adjust_tiled` (`sway/commands/resize.c:125`). The random result records
it as `verdict = "crash"`.

swirl has no i3-derived result: the i3-derived corpus awaits its sway
recapture (`pending.toml`).
