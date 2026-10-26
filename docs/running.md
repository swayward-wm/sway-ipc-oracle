# Run the corpora

Each corpus has one command. Run them from the oracle checkout.
Terms such as bucket, mismatch and unstable are explained in
[how to read a block](results.md#how-to-read-a-block).

| You want to run | Command | Result file |
| --- | --- | --- |
| [i3's test suite](#the-i3-suite) | `i3-suite-run` | `i3/results/<snapshot>.toml` |
| [Scenarios](#sway-ipc-scenarios) (state, events) | `sway-ipc-run` | `sway-ipc/results/<snapshot>.toml` |
| [Fuzzing](#fuzz-corpora) | `sway-ipc-run command-fuzz`, `wire-fuzz` | `<snapshot>-{command,wire}-fuzz.toml` |
| [States from i3's tests](#states-derived-from-i3s-test-suite) | `sway-ipc-run i3-derived` | `<snapshot>-i3-derived.toml` |
| [Random sequences](#random-sequence-corpora) | `sway-ipc-run random` | `<snapshot>-random[-v2].toml` |

To measure your own build, start with [Run a first check](start.md).
To gate CI, see [CI integration](ci.md). To rebuild published results, see
[Reproducing the results](reproducing.md).

Always pass `--out` for your own runs. Without it the runner writes the
committed snapshot path.

## The i3 suite

Build the pinned i3 and compositor first. Then run one command per result:

```sh
./contrib/i3-suite-run --compositor i3
./contrib/i3-suite-run --compositor sway --binary /path/to/pinned/sway
./contrib/i3-suite-run --compositor swayward --binary /path/to/pinned/swayward
```

- i3 runs upstream `complete-run.pl` on Xvfb.
- Sway and swayward run each unchanged test against a headless compositor.
  Each has a private IPC socket and a private X11 socket directory.
- Sway owns Xwayland. Swayward uses xwayland-satellite.
- Every run has a 2 GiB memory cap, no swap and a wall-time limit.

Adapter boundaries are in [`i3/adapters/`](../i3/adapters/).

## Sway IPC scenarios

`contrib/sway-ipc-run` uses only Python's standard library. Each compositor
gets a private IPC socket. Wayland compositors also get a private Wayland
socket; i3 gets a private Xvfb display. The runner never uses the ambient
`SWAYSOCK`, `I3SOCK`, `WAYLAND_DISPLAY` or `DISPLAY`.

```sh
./contrib/sway-ipc-run --compositor sway --binary /path/to/sway \
  --out sway-ipc/results/sway-1.12.toml
./contrib/sway-ipc-run --compositor swayward --binary /path/to/swayward \
  --out sway-ipc/results/swayward-1fd3c25b.toml
```

Use repeated `--scenario NAME` arguments to run a subset.

### Compositor adapters

| `--compositor` | How it runs | Details |
| --- | --- | --- |
| `sway`, `swayward` | Under a 2 GiB, zero-swap systemd scope with a wall-time limit. Standalone `foot` clients. | This page |
| `i3` | Under private Xvfb, with xterm clients. Both programs must be installed beside the runner. | This page |
| `swayfx` | Subclass of the sway adapter, no translations. | [swayfx.md](../sway-ipc/adapters/swayfx.md): two reply extensions, renderer requirement |
| `scroll` | Subclass of the sway adapter. Sets `SCROLLSOCK`, turns animations off. | [scroll.md](../sway-ipc/adapters/scroll.md) |
| `swirl` | Subclass of the scroll adapter (a rebrand of scroll 1.12.17). `GET_VERSION` names no commit, so it checks the build another way. | [swirl.md](../sway-ipc/adapters/swirl.md) |
| `miracle-wm` | Mir compositor on Mir's virtual display and stub input. Translates config to YAML and outputs to `--virtual-output` sizes. Resets by closing fixture windows from the client, since it has no `kill`. | [miracle-wm.md](../sway-ipc/adapters/miracle-wm.md): translations and requests recorded as not applicable |

### What the runner does

- **Fresh compositor per scenario.** Runtime commands cannot leak into later
  measurements. `--no-fresh-per-scenario` is for investigating sequential state.
- **One retry.** A scenario with a mismatch or crash row reruns once on a
  fresh compositor. A row whose verdict or differences change is `unstable`,
  and `[run]` counts `unstable` beside the other verdicts.
- **No retry** in capture and `--no-fresh-per-scenario` runs. If the retry
  fails without a crash verdict, the runner warns and keeps the first rows.
- **Capture** (`--capture`) is restricted to sway. It replaces the selected
  query fixtures after running the same comparisons.
- **Unstable across runs.** `contrib/regenerate-rc` also compares its two runs
  row by row and marks differing rows unstable
  ([details](reproducing.md#release-candidate-regeneration)).

### Where the rules live

| File | Holds |
| --- | --- |
| `sway-ipc/scenarios.toml` | Scenario recipes |
| `sway-ipc/normalize.toml` | Comparison rules and their reasons |
| `sway-ipc/applicability.toml` | i3 comparisons limited to the fields in i3's pinned IPC protocol, with sway source citations for excluded sway extensions. Every sway field stays applicable to swayward. |

### Fixture clients

Two scenario kinds compile a small C client on first use.
They need a C compiler, `pkg-config`, `wayland-scanner`, and the
`wayland-client` and `wayland-protocols` development packages.

- **Size hints:** `contrib/xdg-toplevel-fixture.c`.
- **Foreign toplevel:** `contrib/foreign-toplevel-request.c`, built against
  `contrib/protocols/wlr-foreign-toplevel-management-unstable-v1.xml`
  (vendored from the pinned wlroots). It sends one taskbar request per
  `foreign_toplevel:APP_ID|REQUEST` action.

Without the packages, only those scenarios are reported as not applicable.
The pinned oracle container has them and treats a missing fixture as an error.

## Fuzz corpora

Two seeded, deterministic corpora probe input that scenarios never send.
Each case runs on a fresh compositor.

After each case the runner checks the process and sends `GET_VERSION`.
An exited compositor is `crash`; an unresponsive one is `hang`.
Both are counted apart from `mismatch`.

| Corpus | What it sends |
| --- | --- |
| `command-fuzz` | Boundary cases for every family in the pinned sway command census ([details below](#command-fuzz-cases)). Records the reply and whether `get_tree`, `get_workspaces` or `get_outputs` changed. |
| `wire-fuzz` | Broken framing: bad magic, truncated headers and payloads, oversized lengths, unknown and event message types, invalid JSON for `SUBSCRIBE` and `COMMAND`, 32 simultaneous clients. Records a reply, a disconnect or a 2-second timeout. |

```sh
# Capture (sway only): always records the larger local budget.
./contrib/sway-ipc-run command-fuzz --compositor sway --binary /path/to/sway --capture
./contrib/sway-ipc-run wire-fuzz --compositor sway --binary /path/to/sway --capture
# Replay: --budget ci (default, committed snapshots) or --budget local.
./contrib/sway-ipc-run command-fuzz --compositor swayward --binary /path/to/swayward
```

- **CI budget:** two seeded variants per command family plus the fixed cases.
  Wire fuzz has 10 cases.
- **Local budget:** every generated variant. Wire fuzz has 16 cases.
- `--seed` changes the order of each family's variants. The committed fixture
  uses seed 0.
- Fixtures are in `sway-ipc/fuzz/`. Results are
  `sway-ipc/results/<snapshot>-{command,wire}-fuzz.toml`.

### Command-fuzz cases

The census is `sway-ipc/fuzz/command-families.json`. For each family:

- missing, extra and invalid arguments, quotes and Unicode;
- numeric negatives and overflow, only where the probe has a number;
- criteria edges, only where it has criteria;
- `px`, `ppt` and unknown units, only where it has a unit.

The `exit` family gets three criteria cases instead. The corpus also sends
separators, NUL and a 64 KiB string.

## States derived from i3's test suite

An optional recorder logs the IPC commands and mapped windows of i3's
unchanged `.t` files while they run against sway, with source file and line.
Capture replays the logs and keeps one scenario per distinct tree shape.

The fixtures are states reached by i3's own tests, captured from sway 1.12.
They are not hand-written.

```sh
./contrib/i3-suite-run --compositor sway --record-commands \
  --binary /path/to/pinned/sway
./contrib/sway-ipc-run i3-derived --compositor sway \
  --binary /path/to/pinned/sway --command-logs target/i3-suite/sway --capture
./contrib/sway-ipc-run i3-derived --compositor swayward \
  --binary /path/to/swayward
```

- `sway-ipc/i3-derived/scenarios.json` is the replay and provenance manifest.
- Each hash-named JSON file holds sway's raw tree, workspace and output
  replies for one shape.
- Commands tied to X11 window IDs, compositor lifecycle or spawned programs
  are stopped and listed with a reason. They are never translated silently.
- Capture is restricted to real sway.

## Random sequence corpora

`random` replays seeded command sequences captured from sway. After every step
it compares the command reply, `get_tree` and `get_workspaces`.

- Each seed runs on a fresh compositor.
- A mismatch that changes on an immediate fresh retry is `unstable`.
- If the compositor dies, the seed is a `crash`. The row lists the commands up
  to the step after which the death was seen. Replay continues with the next
  seed.

Results of one corpus are never compared with results of another.

| Corpus | Generator | Size | Result file |
| --- | --- | --- | --- |
| `random` | `--generator v1` (default) | 500 seeds of 20 steps from 31 commands | `<snapshot>-random.toml` |
| `random-v2` | `--generator v2` | 1,000 seeds of 20 steps from `sway-ipc/random-v2/vocabulary.json` | `<snapshot>-random-v2.toml` |
| random-v3 | `--generator v3` | Differential and capture only | Written to `--out DIR` |

For v2, each vocabulary family cites the line of sway's `commands.c` handler
table that dispatches it, and `validate` checks that line against the pinned
sway source.

Seeds listed under `unstable` in `sway-ipc/random-v2/sequences.json`
disagreed between repeated sway replays. They are always reported as unstable.

```sh
./contrib/sway-ipc-run random --generator v2 --compositor swayward \
  --binary /path/to/swayward --out target/random-v2.toml
# Capture (sway only): replaces the captured sequences, keeps the vocabulary.
./contrib/sway-ipc-run random --generator v2 --capture --compositor sway \
  --binary /path/to/sway --seeds 1000 --steps 20
```

`differential --generator v2` drives two compositors with the same generator
and [delta-debugs](glossary.md#runs-and-the-harness) each divergence.
Pass `--out` outside the repository.

### random-v3: state-aware

`--generator v3` reads sway's settled `get_tree` and `get_workspaces` before
each command. It can build, on purpose, the states that sway's branches test.

Examples: floating, fullscreen, tabbed parents, marks, the scratchpad, several
workspaces. v3 has no committed corpus yet.

```sh
./contrib/sway-ipc-run differential --generator v3 --a-binary /path/to/sway \
  --b-binary /path/to/swayward --seed 0 --seeds 20 --out target/v3.toml
./contrib/sway-ipc-run random --generator v3 --capture --compositor sway \
  --binary /path/to/sway --seeds 200 --out target/random-v3
```

How it works:

- **Code and data.** The generator is `contrib/sway_ipc_v3.py`. Its data is
  `sway-ipc/random-v3/vocabulary.json` (base weights, state multipliers,
  preconditions) and `recipes.json` (precondition builders that end in trigger
  commands).
- **Determinism.** Each purpose has its own RNG, seeded from
  `random-v3:<seed>:<purpose>`. The generator reads only stable fields, so one
  seed against one sway gives one command list. `fuzz-self-test --binary <sway>`
  checks this on a live sway.
- **Length.** The default is 40 steps.
- **Recipes.** Seed `s` starts one-output recipe `s % 17` within its first
  five generated steps. It opens only the windows that recipe needs, then
  starts it before any random choice.
- **Two outputs.** `--outputs auto` gives 30% of seeds two outputs in an
  explicit layout, which both compositors check at step 0. A two-output seed
  starts recipe R14 first (windows on both outputs, then cross-output moves
  and focus), then recipe `s % 17`.
- **Extra recipes.** R18 (`output … disable`, sticky evacuation) runs only on
  two-output seeds. R19 (several urgent views, then `[urgent=latest|oldest]`)
  runs on any seed.
- **Setters.** About 5% of steps are a uniform pick from `setters` in
  `vocabulary.json`: random-v2's config-setter commands, without the declared
  `client.*` and `hide_edge_borders --i3` gaps.

What `differential` records:

- Every seed's command list, started recipes and trigger steps, in a
  `[[recorded]]` table.
- With any generator, a compositor that dies or stops answering during a seed
  becomes a `crash` row, never a mismatch. This includes a death just after a
  step that looked fine.
- A crash of the sway side is triaged `harness issue`.
  [Pinned sway crashes](sway-crashes.md) lists the known shapes.
- `--save-scenarios` writes a two-output reproducer with its `outputs` and
  `output_layout`, so the scenario replays on the same layout.
