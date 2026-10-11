# SwayFX adapter

`SwayFXAdapter` in `contrib/sway-ipc-run` measures SwayFX 0.6 (`swayfx-0.6`,
commit pinned in `pins.toml`) exactly as `SwayAdapter` measures sway 1.12. It is
a subclass that inherits everything but the build check:

- the same headless wlroots backend, private `SWAYSOCK`, private
  `XDG_RUNTIME_DIR`, memory cap and wall-time limit;
- the same sway config text, the same random-corpus config, and the same
  `fake-N` to `HEADLESS-(count-N)` output mapping for multi-output scenarios;
- the same foot, `xdg-toplevel-fixture` and `foreign-toplevel-request` clients,
  and the same capabilities.

## Translations

None. SwayFX reads sway's config and command language, so no config, command
or reply is rewritten, and no row carries an `adapted` flag beyond those that
sway's own rows carry.

The adapter differs from `SwayAdapter` only in how it reads the started build:
SwayFX reports `human_readable` as `0.6-<commit> (<date>, branch '<branch>')`,
and `version_details` takes the commit from it to check the pin.

## Documented extensions

SwayFX adds two keys to sway's replies. `sway-ipc/normalize.toml` removes them
before comparison for `swayfx` only (`[[extension_key]]`, with reasons and
source citations). Every key sway sends is still compared.

| Rule | Key | Source |
| --- | --- | --- |
| `swayfx-version-original-version` | `GET_VERSION.sway_original_version` | `sway/ipc-json.c:236`, `meson.build:15,182` |
| `swayfx-output-layer-shell-surfaces` | `layer_shell_surfaces` on each enabled output (`GET_OUTPUTS`, output nodes in `GET_TREE`) | `sway/ipc-json.c:369-445`, `sway/sway-ipc.7.scd:265` |

The wire-fuzz corpus records the key list of `GET_VERSION` replies; the same
`swayfx-version-original-version` rule removes the extra key from that list.

## Build and renderer

The oracle image builds SwayFX from the pinned commit with scenefx 0.5 and the
same wlroots commit as sway, as meson subprojects, with sway's meson options
(`Containerfile`). `$SWAYFX_BINARY` names the binary.

SwayFX renders only through scenefx's GLES2 renderer; it has no pixman
fallback. In the pinned image, software rendering
(`WLR_RENDERER_FORCE_SOFTWARE=1` with Mesa llvmpipe and `/dev/udmabuf`) crashes
at the oracle's 1270-pixel output width. Pinned sway 1.12 crashes the same way
with `WLR_RENDERER=gles2`, and both start at widths of 1272 or 1280 pixels. The
row stride of a 1270-pixel buffer is not 16-byte aligned, and wlroots'
udmabuf allocator does not pad it (`render/allocator/udmabuf.c:71`,
`// TODO: align?`). SwayFX snapshots are therefore measured with the host's
DRM render node passed into the container (`--device /dev/dri/renderD128`).
The renderer draws pixels and does not change any value read over IPC.

## Running the snapshots

Each command runs in its own oracle container with
`--memory 4g --memory-swap 4g --device /dev/dri/renderD128`:

```sh
./contrib/validate reproduce swayfx --snapshot sway-ipc
./contrib/sway-ipc-run scenarios --corpus events --compositor swayfx --binary "$SWAYFX_BINARY"
./contrib/sway-ipc-run command-fuzz --compositor swayfx --binary "$SWAYFX_BINARY"
./contrib/sway-ipc-run wire-fuzz --compositor swayfx --binary "$SWAYFX_BINARY"
./contrib/sway-ipc-run random --compositor swayfx --binary "$SWAYFX_BINARY"
```

The first command runs the full state corpus (`scenarios.toml`) and writes
`sway-ipc/results/swayfx-0.6.toml`. `contrib/validate` requires every state
result to cover the scenarios of the committed sway 1.12 state result, so the
committed SwayFX result keeps those rows until the release-candidate
regeneration replaces every state result.

SwayFX has no i3-derived result yet: the i3-derived corpus awaits its sway
recapture (`pending.toml`).
