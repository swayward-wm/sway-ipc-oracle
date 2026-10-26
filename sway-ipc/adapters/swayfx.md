# SwayFX adapter

`SwayFXAdapter` measures SwayFX 0.6 (`swayfx-0.6`, pinned in `pins.toml`).

## Run a first check

From a regular oracle clone, with the [pinned image](../../docs/reproducing.md) built:

```sh
OUT="${OUT:-$PWD/target/swayfx}"
mkdir -p "$OUT/tmp"
podman run --rm --memory 4g --memory-swap 4g --device /dev/dri/renderD128 \
  --security-opt label=disable -v "$PWD:/oracle:ro" -v "$OUT:/out" sway-ipc-oracle bash -c \
  'export TMPDIR=/out/tmp; ./contrib/sway-ipc-run command-fuzz --compositor swayfx \
    --binary "$SWAYFX_BINARY" --out /out/command-fuzz.toml' > "$OUT/run.log" 2>&1 &
PID=$!; wait "$PID"; echo "$?"
```

[Read exit codes](../../docs/ci.md#run-a-corpus) and
[run other corpora](../../docs/ci.md#pick-the-corpora), using
`SWAYFX_BINARY` inside the image. Each command needs its own 4 GiB, zero-swap
container and render device; see [why below](#build-and-renderer).

## Check what the adapter preserves

It subclasses `SwayAdapter` in `contrib/sway-ipc-run`, changing only the build
check. The headless backend, private `SWAYSOCK` and runtime directory, limits,
configs, clients and capabilities are the same as sway's.

Multi-output `fake-N` maps to `HEADLESS-(count-N)`. Clients are foot,
`xdg-toplevel-fixture` and `foreign-toplevel-request`; state and random runs
use sway's configs.

## Translations

None beyond sway's. SwayFX reads sway's config and command language, so the
adapter adds no rewrite of its own.

It inherits `SwayAdapter`'s mapping of `fake-N` output names in commands to
`HEADLESS-(count-N)`, as above. No row carries an `adapted` flag beyond those
that sway's own rows carry.

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

SwayFX has only scenefx's GLES2 renderer, with no pixman fallback. Software
rendering (`WLR_RENDERER_FORCE_SOFTWARE=1`, Mesa llvmpipe and `/dev/udmabuf`)
crashes in the pinned image at the oracle's 1270-pixel output width.

Pinned sway 1.12 crashes the same way with `WLR_RENDERER=gles2`; both start at
1272 or 1280 pixels. A 1270-pixel buffer's row stride is not 16-byte aligned;
wlroots does not pad it (`render/allocator/udmabuf.c:71`, `// TODO: align?`).

Snapshots therefore use the host's DRM render node, passed through with
`--device /dev/dri/renderD128`. Rendering does not change values read over IPC.

## Reproduce the published snapshot

Follow [snapshot reproduction](../../docs/reproducing.md), with the render
node mounted. The state generator runs full `scenarios.toml`; the committed
snapshot keeps sway 1.12's selection until release-candidate regeneration.

`contrib/validate` requires every state result to cover that same selection.
The state snapshot is `sway-ipc/results/swayfx-0.6.toml`.

SwayFX has no i3-derived result yet. The corpus has been
[recaptured](../../docs/reproducing.md#the-i3-derived-recapture); a SwayFX
replay has not been run or committed.
