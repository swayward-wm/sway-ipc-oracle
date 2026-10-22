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

SwayFX renders only through scenefx's GLES2 renderer, which crashes on
software rendering at the oracle's output size (see
[`sway-ipc/adapters/swayfx.md`](../sway-ipc/adapters/swayfx.md)). Pass the
host's render node into each SwayFX container:

```sh
podman run --rm --memory 4g --memory-swap 4g --device /dev/dri/renderD128 \
  --security-opt label=disable -v "$PWD:/oracle" sway-ipc-oracle \
  ./contrib/validate reproduce swayfx --snapshot sway-ipc
```

`./contrib/validate reproduce all` (or `reproduce` with no mode) runs SwayFX
after i3, sway and swayward in the same container, so it needs the same
`--device /dev/dri/renderD128`. Without it, the SwayFX unit fails to start
and `reproduce all` exits non-zero.

SwayFX has no i3-suite adapter, so it has sway-IPC snapshots only. Run its
other corpora with `contrib/sway-ipc-run` and `--binary "$SWAYFX_BINARY"`, in
the same container.

scroll likewise has sway-IPC snapshots only. It renders with pixman in the
container and needs no render node; run its corpora with `--compositor scroll`
and `--binary "$SCROLL_BINARY"`
([`sway-ipc/adapters/scroll.md`](../sway-ipc/adapters/scroll.md)).
swirl is the same, with `--compositor swirl` and `--binary "$SWIRL_BINARY"`
([`sway-ipc/adapters/swirl.md`](../sway-ipc/adapters/swirl.md)).

miracle-wm also has sway-IPC snapshots only. Mir falls back to software
buffers in the container, so it needs no render node; run its corpora with
`--compositor miracle-wm` and `--binary "$MIRACLE_WM_BINARY"`
([`sway-ipc/adapters/miracle-wm.md`](../sway-ipc/adapters/miracle-wm.md)).

## Release-candidate regeneration

`contrib/regenerate-rc` runs the whole regeneration for a frozen swayward
commit. Run it on the host from a clean oracle checkout:

```sh
./contrib/regenerate-rc <swayward-sha> --dry-run
./contrib/regenerate-rc <swayward-sha>
```

The dry run changes nothing. It checks that the commit is on swayward main in
a fresh clone, that the checkout is clean, that Podman enforces the 4 GiB and
zero-swap caps, that no sweep holds `ORACLE_SWEEP_LOCK`, and, when a SwayFX
unit is planned, that `/dev/dri/renderD128` exists. It then prints
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
   changes their corpus. The units cover every `pins.toml` snapshot
   compositor: i3, sway and swayward first, then SwayFX, scroll, miracle-wm
   and swirl in `pins.toml` order. Two runs of an i3-derived or fuzz unit
   agree when they are equal apart from the `date` line. State and
   events units pair the rows of the two runs by scenario, request and
   occurrence. Within a run, a scenario with a mismatch or crash already
   reruns on a fresh compositor and reports rows that change as unstable.
   That retry cannot catch a row that matched in run 1 and mismatches in
   run 2, so the unit compares the runs as well. Rows equal in verdict and
   differences are kept. A row that differs between the runs, or that is
   unstable in either run, is installed from run 1 with verdict `unstable`
   and run 1's differences. The `[run]` verdict counts are recounted, and
   `evidence.log` lists each such row (`unstable_rows=N rows=...`). A row
   present in only one run counts the same way when its scenario crashed in
   either run. The unit fails when sway, the reference, disagrees on any
   row, when more than 5% of the rows disagree, when a row is missing from
   one run without a crash, or when a `[run]` key other than the verdict
   counts, `difference_fields` and `date` differs. Random units follow the
   same rule with the seed as the key: a seed whose verdict or reproducer
   differs between the runs installs as `unstable`, with run 1's reproducer
   (run 2's when run 1 matched). A seed that crashed in only one run, or
   crashed differently, fails the unit: a crash has no reproducer to install
   as unstable. If such a crash is nondeterministic, record it and rerun
   the unit. SwayFX containers get
   `--device /dev/dri/renderD128`, as in the SwayFX section above.

An agreeing unit installs its first run and removes its `pending.toml` entry.
The first unit that does not agree stops the run and installs nothing. The
script appends one line per unit to `target/rc/<sha8>/evidence.log` with the
unit, oracle commit, image digest, run count, wall time, agreement, and
non-metadata diff line count. To resume after a failure, fix the cause and run
the same command again. The script skips units that already agreed with the
same oracle commit and image. At the end it regenerates the `docs/results.md` i3-suite
blocks and runs `contrib/validate`. The script never commits or pushes. Review
the diff, triage the new swayward rows, and commit the results.

A row that turns unstable is no longer a measured mismatch. If a
classification names it, `contrib/validate` fails at the end of the run
("does not name a measured mismatch") and the script exits 3. Check the
evidence before you edit the classification. If the row varies between runs,
drop its key from the classification and keep the unstable verdict. If the
evidence shows a real, stable mismatch that one run missed, rerun the unit
by deleting its agreeing line from `evidence.log`, then keep the
classification.

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
when the i3 shim could not write its command logs. A trial runs only that
check. The full run also compares the new corpus with the committed one
(`HEAD:sway-ipc/i3-derived/scenarios.json`) in three checks:

- Single-output digests. The recapture changes only the fake-N to
  `HEADLESS-(count-N)` mapping, which can reshape only multi-output
  scenarios. The unit fails if any committed scenario with `outputs = 1` has
  no scenario with the same digest in the new corpus. `evidence.log` records
  `single_output_kept=K/N` and `multi_output_reshaped=R/M`, the committed
  multi-output digests no longer present, which are allowed.
- Per-test coverage. The recapture keeps one scenario per state shape and
  credits it to the first test that reaches it, so per-test counts and the
  total can move while every state is still covered. A test file fails the
  unit when it has states in the committed corpus but none in the new
  corpus, and none of its committed digests are in the new corpus.
  `evidence.log` records `old`, `new`, `kept` (same digest, same test),
  `recredited` (same digest, other test), `reshaped` (committed digests no
  longer present) and `recredited_tests`, the files covered only through
  re-credited digests.
- Empty command logs. An i3 test file whose command log is empty fails the
  unit if any of these holds: the file has states in the committed corpus;
  it auto-starts sway (no `use i3test i3_autostart => 0`), so the adapter
  writes a reset line; or its source calls `->command`, `cmd`, `cmd_nosync`,
  `open_window`, or an `i3test.pm` helper that reaches one of them. The
  helper list is derived when the check runs, from the image's
  `/opt/i3-src/testcases/lib/i3test.pm.in` (at i3 9be3249a: `cmp_tree`,
  `create_layout`, `fresh_workspace`, `input_focus`, `kill_all_windows`,
  `net_wm_state_contains`, `open_floating_window`, `sync_with_i3`,
  `wait_for_unmap`). Tests such as `187-commands-parser.t` and
  `201-config-parser.t` do none of this, so an empty log is correct for
  them. `evidence.log` lists the accepted ones (`accepted_empty=...`).

