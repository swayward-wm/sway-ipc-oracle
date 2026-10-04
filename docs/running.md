# Running the oracle

## The i3 suite

Build the pinned i3 and compositor revisions, then run one command per result:

```sh
./contrib/i3-suite-run --compositor i3
./contrib/i3-suite-run --compositor sway --binary /path/to/pinned/sway
./contrib/i3-suite-run --compositor swayward --binary /path/to/pinned/swayward
```

The i3 adapter delegates to upstream `complete-run.pl` on Xvfb. The sway and
swayward adapters run each unchanged test against a headless compositor with a
private IPC socket and private X11 socket directory. Sway owns Xwayland;
swayward uses xwayland-satellite. Every compositor run has a 2 GiB memory cap,
no swap, and a wall-time limit. See [`i3/adapters/`](../i3/adapters/) for the
adapter boundaries.

## The sway IPC scenarios

`contrib/sway-ipc-run` uses only Python's standard library. It starts sway or
swayward under a 2 GiB, zero-swap systemd scope with a wall-time limit and
private IPC and Wayland sockets. It opens standalone `foot` clients and never
uses the ambient `SWAYSOCK`, `I3SOCK`, `WAYLAND_DISPLAY`, or `DISPLAY`.

```sh
./contrib/sway-ipc-run --compositor sway --binary /path/to/sway \
  --out sway-ipc/results/sway-1.12.toml
./contrib/sway-ipc-run --compositor swayward --binary /path/to/swayward \
  --out sway-ipc/results/swayward-5f4ad1d8.toml
```

Recipes live in `sway-ipc/scenarios.toml`; comparison rules and their reasons
live in `sway-ipc/normalize.toml`. Size-hint scenarios lazily compile
`contrib/xdg-toplevel-fixture.c` and require a C compiler, `pkg-config`,
`wayland-scanner`, and the `wayland-client` and `wayland-protocols` development
packages. Without them, only those scenarios are reported as not applicable;
the pinned oracle container has them and treats a missing fixture as an error.
Foreign-toplevel scenarios likewise compile `contrib/foreign-toplevel-request.c`
against `contrib/protocols/wlr-foreign-toplevel-management-unstable-v1.xml`,
vendored from the pinned wlroots, and send one taskbar request per
`foreign_toplevel:APP_ID|REQUEST` action.
`sway-ipc/applicability.toml` limits i3
comparisons to the fields in i3's pinned IPC protocol and cites sway's source
for excluded sway extensions. Every sway field remains applicable to swayward.
Use repeated `--scenario NAME` arguments for a subset. The runner starts a
fresh compositor for each recipe so runtime commands cannot leak into later
measurements. The pinned swayward run records **440 match / 10 mismatch / 0 not
applicable** across 90 scenarios and five IPC requests. Use
`--no-fresh-per-scenario` only when investigating sequential state. `--capture` is
restricted to sway and replaces the selected query fixtures after running the
same comparisons. The i3 adapter runs i3 under private Xvfb and opens xterm
clients; both programs must be installed beside the runner.

## Fuzz corpora

Two seeded, deterministic corpora probe input that the scenarios never send.
`command-fuzz` reads the pinned sway runtime-command census from
`sway-ipc/fuzz/command-families.json` and generates boundary cases for every
family: missing, extra and invalid arguments; quotes and Unicode; numeric
negatives and overflow where the probe has a number; criteria edges where it
has criteria; and `px`/`ppt`/unknown units where it has a unit. It also sends a
small fixed set for command separators, NUL and a 64 KiB string. It records the
reply and whether `get_tree`, `get_workspaces` or `get_outputs` changed.
`wire-fuzz` sends broken framing: bad magic, truncated headers and payloads,
oversized lengths, unknown and event message types, invalid JSON for
`SUBSCRIBE` and `COMMAND`, and 32 simultaneous clients. It records a reply, a
disconnect or a 2-second timeout.

Each case runs on a fresh compositor. Afterwards the runner checks the process
and sends `GET_VERSION`. An exited compositor is `crash`, and an unresponsive one
is `hang`. Both are counted separately from `mismatch`.

```sh
# Capture (sway only): always records the larger local budget.
./contrib/sway-ipc-run command-fuzz --compositor sway --binary /path/to/sway --capture
./contrib/sway-ipc-run wire-fuzz --compositor sway --binary /path/to/sway --capture
# Replay: --budget ci (default, committed snapshots) or --budget local.
./contrib/sway-ipc-run command-fuzz --compositor swayward --binary /path/to/swayward
```

The CI command budget keeps two seeded variants per command family plus the
fixed cases; the local budget captures every generated variant. Wire budgets
are 10 and 16 cases. `--seed` changes the deterministic order of each family's
variants; the committed fixture uses seed 0. Fixtures live in `sway-ipc/fuzz/`,
and results in
`sway-ipc/results/<snapshot>-{command,wire}-fuzz.toml`.

## States derived from i3's test suite

The optional calibration recorder logs replayable IPC commands and ordinary
mapped windows while i3's unchanged `.t` files run against sway. It records the
source file and line for each operation. Capture mode replays those logs through
the same isolated sway adapter, hashes a normalized tree shape after every
operation, and keeps one scenario per distinct shape. The committed fixtures
are therefore states reached by i3's own tests, captured from sway 1.12; they
are not hand-authored approximations.

```sh
./contrib/i3-suite-run --compositor sway --record-commands \
  --binary /path/to/pinned/sway
./contrib/sway-ipc-run i3-derived --compositor sway \
  --binary /path/to/pinned/sway --command-logs target/i3-suite/sway --capture
./contrib/sway-ipc-run i3-derived --compositor swayward \
  --binary /path/to/swayward
```

`sway-ipc/i3-derived/scenarios.json` is the compact replay and provenance
manifest. Each hash-named JSON file contains sway's raw tree, workspace, and
output replies for one distinct normalized shape. Commands tied to X11 window
IDs, compositor process lifecycle, or spawned programs are stopped and listed
with a reason rather than translated silently. Capture remains restricted to
real sway.

## Random sequence corpora

`random` replays seeded command sequences captured from sway and compares the
command reply, `get_tree` and `get_workspaces` after every step. Each seed runs
on a fresh compositor. A mismatch that changes on an immediate fresh retry is
reported as unstable.

There are two corpora. Results of one are never compared with results of the
other.

- `random` (`--generator v1`, the default): 500 seeds of 20 steps from 31
  commands. Results are `sway-ipc/results/<snapshot>-random.toml`.
- `random-v2` (`--generator v2`): 1,000 seeds of 20 steps from
  `sway-ipc/random-v2/vocabulary.json`. Each family in the vocabulary cites the
  line of sway's `commands.c` handler table that dispatches it, and `validate`
  checks that line against the pinned sway source. Results are
  `sway-ipc/results/<snapshot>-random-v2.toml`. Seeds listed under `unstable`
  in `sway-ipc/random-v2/sequences.json` disagreed between repeated sway
  replays and are always reported as unstable.

```sh
./contrib/sway-ipc-run random --generator v2 --compositor swayward \
  --binary /path/to/swayward --out target/random-v2.toml
# Capture (sway only): replaces the captured sequences, keeps the vocabulary.
./contrib/sway-ipc-run random --generator v2 --capture --compositor sway \
  --binary /path/to/sway --seeds 1000 --steps 20
```

`differential --generator v2` drives two compositors with the same generator
and delta-debugs each divergence; pass `--out` outside the repository.
