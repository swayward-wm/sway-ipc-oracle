# Reproducing the results

Build the pinned toolchain and run every result generator from a clean checkout:

```sh
git clone https://github.com/swayward-wm/sway-ipc-oracle.git sway-ipc-oracle
cd sway-ipc-oracle
podman build -t sway-ipc-oracle -f Containerfile .
podman run --rm --memory 4g --memory-swap 4g \
  --security-opt label=disable -v "$PWD:/oracle" sway-ipc-oracle \
  ./contrib/validate reproduce i3 --snapshot i3-suite
```

The image builds the pinned i3, sway, wlroots, and swayward commits and installs
the Perl, X11, Wayland, and client dependencies. It does not use files from the
host home directory. Reproduction has six independent units: the i3-suite and
sway-ipc snapshots for each of i3, sway, and swayward. A unit is done when two
consecutive runs agree apart from assertions declared in `i3/flaky-runs.toml`,
no canary is flaky, and the regenerated result matches the committed result
apart from metadata. A completed unit does not need to be rerun when another
unit flakes.

Run the sway i3-suite unit as two serial `--shard 1/1` runs, one after the
other, and require them to agree. Parallel sway shards disagree on tens of
assertions, so a sharded sway result is not a measurement. Run a swayward
i3-suite unit as shards in parallel. Each command needs its own 4 GiB,
zero-swap container. Shards select files deterministically and write partial
TOML plus private diagnostics; `i3-suite-run --merge` is the only step that
writes the combined result:

```sh
mkdir -p target/reproduce/swayward
for k in 1 2 3 4; do
  podman run --rm --memory 4g --memory-swap 4g \
    --security-opt label=disable -v "$PWD:/oracle" sway-ipc-oracle \
    ./contrib/validate reproduce swayward --snapshot i3-suite --shard "$k/4" \
      --out "target/reproduce/swayward/$k.toml" &
done
wait
./contrib/i3-suite-run --merge target/reproduce/swayward/{1,2,3,4}.toml \
  --out "i3/results/$(python3 -c 'import tomllib; print(tomllib.load(open("pins.toml", "rb"))["snapshot"]["swayward"])').toml"
```

Use six swayward shards on a 16-core machine after confirming memory headroom.
Keep file execution serial inside each shard. `--files FILE` (repeatable)
selects specific files for investigation. The outer Podman command supplies the
4 GiB memory limit and disables swap by setting the memory-plus-swap limit to
the same value.

Record one evidence line per unit with the oracle commit, image digest, wall
time, and non-metadata diff line count. Poll long runs every five minutes.
Result metadata contains the run date; compare content while excluding it:

```sh
git diff --ignore-matching-lines='^date = ' -- \
  i3/results sway-ipc/results
```

An empty diff means the measured content matches the committed results.

## Release-candidate regeneration

`contrib/regenerate-rc` runs the whole regeneration for a frozen swayward
commit. Run it on the host from a clean oracle checkout:

```sh
./contrib/regenerate-rc <swayward-sha> --dry-run
./contrib/regenerate-rc <swayward-sha>
```

The dry run changes nothing. It checks that the commit is on swayward main in
a fresh clone, that the checkout is clean, that Podman enforces the 4 GiB and
zero-swap caps, and that no sweep holds `ORACLE_SWEEP_LOCK`. It then prints
every unit with its container commands.

The full run repins swayward and renames the swayward snapshot files, then
builds the image from `pins.toml`. It then runs one unit at a time, two runs
per unit:

1. `i3-derived-capture` records sway's commands from the i3 suite, recaptures
   `sway-ipc/i3-derived` from pinned sway, and requires both sway replays of
   the new corpus to match every row.
2. The i3-suite units, with sway as two serial `--shard 1/1` runs and swayward
   as two sharded runs.
3. One unit per sway IPC result: every result in `pending.toml`, every
   swayward result, and every i3-derived result, because the recapture
   changes their corpus.

An agreeing unit installs its first run and removes its `pending.toml` entry.
The first unit that does not agree stops the run and installs nothing. The
script appends one line per unit to `target/rc/<sha8>/evidence.log` with the
unit, oracle commit, image digest, run count, wall time, agreement, and
non-metadata diff line count. To resume after a failure, fix the cause and run
the same command again. The script skips units that already agreed with the
same oracle commit and image. At the end it regenerates the README i3-suite
blocks and runs `contrib/validate`. The script never commits or pushes. Review
the diff, triage the new swayward rows, and commit the results.

The i3-derived recapture is required because the committed corpus predates
the fake-N to `HEADLESS-(count-N)` mapping. Before the mapping change, the
multi-output fixtures put workspace 1 and the initial focus on different
outputs than the replay uses now. Under the current runner, pinned sway
matches its own captures on every single-output scenario. It mismatches on
all 189 multi-output scenarios: 3624/4180 rows match, in tree, workspaces and
outputs.

To rehearse only the capture unit on a few i3 test files, run a trial in a
scratch clone and discard the clone afterwards:

```sh
./contrib/regenerate-rc <swayward-sha> --trial 502-focus-output.t --trial 100-fullscreen.t
```

A trial runs the same capture, staging and two-replay checks. It installs no
result, leaves `pending.toml` unchanged, and writes its evidence to
`target/rc/<sha8>-trial/`. It still rewrites `sway-ipc/i3-derived`.
The capture unit fails when the recapture yields no scenarios, for example
when the i3 shim could not write its command logs.

