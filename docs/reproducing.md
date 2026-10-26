# Reproduce the results

Rebuild a published snapshot in the pinned container and compare it with the
committed result. You need Podman and a clean, regular clone (not a git
worktree: provenance reads the clone's `.git`).

```sh
git clone https://github.com/swayward-wm/sway-ipc-oracle.git sway-ipc-oracle
cd sway-ipc-oracle
podman build -t sway-ipc-oracle -f Containerfile .
podman run --rm --memory 4g --memory-swap 4g \
  --security-opt label=disable -v "$PWD:/oracle" sway-ipc-oracle \
  ./contrib/validate reproduce i3 --snapshot i3-suite
```

The image builds the pinned i3, sway, wlroots and swayward commits and installs
the Perl, X11, Wayland and client dependencies. It uses no files from your
home directory. `--memory-swap` equal to `--memory` means no swap.

## Units and when one is done

Reproduction has ten independent units:

- the i3-suite and sway-ipc snapshots of i3, sway and swayward;
- the sway-ipc snapshots of SwayFX, scroll, miracle-wm and swirl, which have
  no i3-suite adapter ([other compositors](#other-compositors)).

A unit is done when:

- Two consecutive runs agree, apart from the files listed in `i3/flaky.toml`
  and the assertions listed in `i3/unstable.toml`. (`i3/flaky-runs.toml` only
  holds the raw outcomes behind those lists.)
- No [canary](glossary.md#runs-and-the-harness) is flaky.
- The regenerated result matches the committed result, apart from metadata.

A finished unit needs no rerun when another unit flakes.

Compare content without the run date:

```sh
git diff --ignore-matching-lines='^date = ' -- \
  i3/results sway-ipc/results
```

An empty diff means the measured content matches the committed results.
Record one evidence line per unit: oracle commit, image digest, wall time and
non-metadata diff line count. Poll long runs every five minutes.

## Sway i3 suite: serial only

Run it as two serial `--shard 1/1` runs, one after the other, and require them
to agree.

Parallel sway shards disagree on tens of assertions, so a sharded sway result
is not a measurement.

## Swayward i3 suite: parallel shards

Each shard needs its own 4 GiB, zero-swap container. Shards select files
deterministically and write partial TOML and private diagnostics.
`i3-suite-run --merge` is the only step that writes the combined result.

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

- Use six shards on a 16-core machine, after you confirm memory headroom.
- Keep file execution serial inside each shard.
- `--files FILE` (repeatable) selects specific files for investigation.

## Other compositors

Only i3, sway and swayward have an i3-suite adapter. The others have sway-IPC
snapshots only. Run their corpora with `contrib/sway-ipc-run` in the same
container, as in [Run the corpora](running.md).

| Compositor | Render node | Run with | Notes |
| --- | --- | --- | --- |
| SwayFX | `--device /dev/dri/renderD128` | `--binary "$SWAYFX_BINARY"` | [swayfx.md](../sway-ipc/adapters/swayfx.md) |
| scroll | none (pixman) | `--compositor scroll --binary "$SCROLL_BINARY"` | [scroll.md](../sway-ipc/adapters/scroll.md) |
| swirl | none (pixman) | `--compositor swirl --binary "$SWIRL_BINARY"` | [swirl.md](../sway-ipc/adapters/swirl.md) |
| miracle-wm | none (Mir uses software buffers) | `--compositor miracle-wm --binary "$MIRACLE_WM_BINARY"` | [miracle-wm.md](../sway-ipc/adapters/miracle-wm.md) |

SwayFX renders only through scenefx's GLES2 renderer, which crashes on
software rendering at the oracle's output size. Pass the host's render node
into each SwayFX container:

```sh
podman run --rm --memory 4g --memory-swap 4g --device /dev/dri/renderD128 \
  --security-opt label=disable -v "$PWD:/oracle" sway-ipc-oracle \
  ./contrib/validate reproduce swayfx --snapshot sway-ipc
```

`./contrib/validate reproduce all` (or `reproduce` with no mode) runs SwayFX
after i3, sway and swayward in the same container.

It needs the same `--device`. Without it, the SwayFX unit fails to start and
`reproduce all` exits non-zero.

## Release-candidate regeneration

`contrib/regenerate-rc` regenerates everything for one frozen swayward commit.
Run it on the host, from a clean oracle checkout:

```sh
./contrib/regenerate-rc <swayward-sha> --dry-run
./contrib/regenerate-rc <swayward-sha>
```

The dry run changes nothing. It prints every unit with its container commands.
It checks that:

- the commit is on swayward main in a fresh clone;
- the checkout is clean;
- Podman enforces the 4 GiB and zero-swap caps;
- no sweep holds `ORACLE_SWEEP_LOCK`;
- `/dev/dri/renderD128` exists, when a SwayFX unit is planned.

### What the full run does

The full run repins swayward, renames the swayward snapshot files and builds
the image from `pins.toml`. It then runs one unit at a time, two runs per unit:

1. **`i3-derived-capture`** records sway's commands from the i3 suite,
   recaptures `sway-ipc/i3-derived` from pinned sway, and requires both sway
   replays of the new corpus to match every row.
2. **The i3-suite units.** Sway runs as two serial `--shard 1/1` runs.
   Swayward runs as two sharded runs.
3. **One unit per sway IPC result:** every result in `pending.toml`, every
   swayward result and every i3-derived result (the recapture changes their
   corpus). The units cover every `pins.toml` snapshot compositor: i3, sway
   and swayward first, then SwayFX, scroll, miracle-wm and swirl in
   `pins.toml` order. SwayFX containers get `--device /dev/dri/renderD128`.

### When two runs agree

- An agreeing unit installs its first run and removes its `pending.toml`
  entry.
- The first unit that does not agree stops the run and installs nothing.
- The script appends one line per unit to `target/rc/<sha8>/evidence.log`:
  unit, oracle commit, image digest, run count, wall time, agreement and
  non-metadata diff line count.
- At the end it regenerates the generated regions of `docs/results.md` and runs
  `contrib/validate`.
- It never commits or pushes. Review the diff, triage the new swayward rows
  and commit the results.
- To resume after a failure, fix the cause and run the same command again.
  The script skips units that already agreed with the same oracle commit and
  image.

### How two runs are compared

For a sway IPC unit, two runs of an i3-derived or fuzz unit agree when they
are equal apart from the `date` line. State and events units pair rows by
scenario, request and occurrence.

Inside a run, a scenario with a mismatch or crash already reruns on a fresh
compositor. That retry cannot catch a row that matched in run 1 and
mismatches in run 2, so the unit compares the runs as well:

- Rows equal in verdict and differences are kept.
- A row that differs between the runs, or is unstable in either, is installed
  from run 1 with verdict `unstable` and run 1's differences.
- The `[run]` verdict counts are recounted. `evidence.log` lists each such row
  (`unstable_rows=N rows=...`).
- A row present in only one run counts the same way when its scenario crashed
  in either run.

The unit fails when:

- sway, the reference, disagrees on any row;
- more than 5% of the rows disagree;
- a row is missing from one run without a crash;
- a `[run]` key other than the verdict counts, `difference_fields` and `date`
  differs.

Random units use the seed as the key. A seed whose verdict or reproducer
differs between the runs installs as `unstable`, with run 1's reproducer
(run 2's when run 1 matched).

A seed that crashed in only one run, or crashed differently, fails the unit:
a crash has no reproducer to install as unstable. If such a crash is
nondeterministic, record it and rerun the unit.

### A row turned unstable

A row that turns unstable is no longer a measured mismatch. If a
classification names it, `contrib/validate` fails at the end of the run
("does not name a measured mismatch") and the script exits 3.

Check the evidence before you edit the classification:

- **The row varies between runs:** drop its key from the classification and
  keep the unstable verdict.
- **A real, stable mismatch that one run missed:** delete the unit's agreeing
  line from `evidence.log`, rerun the unit, and keep the classification.

## The i3-derived recapture

The recapture replaces `sway-ipc/i3-derived` with states captured from pinned
sway under the current runner.

Run it when the runner changes how it maps the i3 tests' fake outputs (fake-N)
to `HEADLESS-(count-N)`. That mapping decides which output holds workspace 1
and the initial focus in the multi-output fixtures.

The committed corpus has already been recaptured under the current mapping. It
holds 416 scenarios, 187 of them multi-output. Pinned sway matches all 4160
rows of its own replay (`sway-ipc/results/sway-1.12-i3-derived.toml`).

To rehearse only the capture unit on a few i3 test files, run a trial in a
scratch clone and discard the clone afterwards:

```sh
./contrib/regenerate-rc <swayward-sha> --trial 502-focus-output.t --trial 100-fullscreen.t
```

A trial:

- runs the same capture, staging and two-replay checks;
- installs no result and leaves `pending.toml` unchanged;
- writes its evidence to `target/rc/<sha8>-trial/`;
- still rewrites `sway-ipc/i3-derived`.

The capture unit fails when the recapture yields no scenarios, for example
when the i3 shim could not write its command logs. A trial runs only that
check.

The full run also compares the new corpus with the committed one
(`HEAD:sway-ipc/i3-derived/scenarios.json`) in three checks.

**Single-output digests.** The recapture changes only the mapping, which can
reshape only multi-output scenarios.

- The unit fails if a committed scenario with `outputs = 1` has no scenario
  with the same digest in the new corpus.
- `evidence.log` records `single_output_kept=K/N` and
  `multi_output_reshaped=R/M`. The reshaped digests, no longer present, are
  allowed.

**Per-test coverage.** The recapture keeps one scenario per state shape and
credits it to the first test that reaches it. Per-test counts and the total
can move while every state is still covered.

- A test file fails the unit when it has states in the committed corpus but
  none in the new corpus, and none of its committed digests are in the new
  corpus.
- `evidence.log` records `old`, `new`, `kept` (same digest, same test),
  `recredited` (same digest, other test), `reshaped` (committed digests no
  longer present) and `recredited_tests`, the files covered only through
  re-credited digests.

**Empty command logs.** An i3 test file with an empty command log fails the
unit if any of these holds:

- the file has states in the committed corpus;
- it auto-starts sway (no `use i3test i3_autostart => 0`), so the adapter
  writes a reset line;
- its source calls `->command`, `cmd`, `cmd_nosync`, `open_window`, or an
  `i3test.pm` helper that reaches one of them.

The helper list is derived when the check runs, from the image's
`/opt/i3-src/testcases/lib/i3test.pm.in`. At i3 9be3249a it is:

`cmp_tree`, `create_layout`, `fresh_workspace`, `input_focus`,
`kill_all_windows`, `net_wm_state_contains`, `open_floating_window`,
`sync_with_i3`, `wait_for_unmap`.

Tests such as `187-commands-parser.t` and `201-config-parser.t` do none of
this, so an empty log is correct for them. `evidence.log` lists the accepted
ones (`accepted_empty=...`).
