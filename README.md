# sway-ipc-oracle

Compatibility tests for compositors that speak the i3/sway IPC protocol.
It runs i3's unchanged tests and compares IPC replies with recordings from
pinned sway 1.12. Reviewed differences have reasons and source citations.

Seven compositors are measured. The runs found
[four distinct crashes in sway 1.12](docs/sway-crashes.md), the reference
compositor. These are measurements at pinned commits, not a ranking.

## Start with your task

| You want to… | Start here |
| --- | --- |
| Check a sway PR for new crashes | [Run pr-check](docs/start.md#check-a-sway-pr) |
| Measure your compositor or add it to CI | [Run a first corpus](docs/start.md#measure-your-compositor) |
| Write a tool using i3/sway IPC | [Read measured differences and their limits](docs/results.md#how-to-read-a-block) |
| See what the oracle found | [Results for each compositor](docs/results.md) or [sway crash reproducers](docs/sway-crashes.md) |

The quickstart assumes you have built your compositor. It links to the
requirements and the pinned container if you need a toolchain.

## What is tested

- **i3's own 242 test files (3,755 assertions)**, written by Michael
  Stapelberg and the i3 contributors, run through small compositor adapters.
- **Sway's recorded replies:** 371 hand-written scenarios, 416
  window-tree states reached by i3's tests, all nine event types, and 500
  captured random command sequences (a further 1,000 in a wider vocabulary
  are captured but not yet replayed).
- Malformed commands and broken IPC framing. The
  [command coverage record](sway-ipc/command-coverage.toml) lists which of
  sway's commands are exercised, and why each of the rest is not.

[Running the oracle](docs/running.md) describes the corpora and runners.

## How to read the evidence

Each compositor has its own [results block](docs/results.md) and raw snapshots.
A mismatch may be deliberate, an i3-only premise, or a harness issue, not a bug.
The page separates these causes and counts reviews still outstanding.

- **IPC only.** Tests run headless and observe trees, replies and events;
  they do not measure rendering, animation or input latency.
- **X11 limits are separate.** i3 tests with X11-only premises are labelled
  separately from comparable non-passes. Adapters translate configs, never
  assertions. To keep a test's premise, a few reply values are translated too,
  such as output names ([adapters](docs/glossary.md#sources-and-corpora)).
- **A match is not a guarantee.** It describes the scenarios tested at one
  commit, not every sequence a tool or user could send. Sway is the reference
  for sway compatibility, not a claim about what every compositor should do.
- **Reproducible snapshots.** Builds are pinned in [pins.toml](pins.toml).
  Input hashes detect stale results; pending measurements are marked on the
  results page. Snapshots are raw runner output, except i3's stated
  not-applicable random record. [Reproduce them](docs/reproducing.md).

## Project and reference

Sway ships no conformance suite, and i3's suite targets i3 on X11. The earlier
[swaywm/sway-tests](https://github.com/swaywm/sway-tests) is archived.

The oracle began in [swayward](https://github.com/swayward-wm/swayward), which
shares its maintainer and pins the oracle in CI. Nothing here depends on
swayward; every compositor gets the same rules.

The oracle was built with heavy AI assistance. A human maintains it and
reviews every change.

- [CI integration](docs/ci.md): pin the oracle and gate on new differences.
- [Adding a compositor](docs/adding-a-compositor.md): adapters and pins.
- [Contributing](CONTRIBUTING.md): reproducibility and classification rules.
- [pr-check reference](docs/pr-check.md): options, reports and test limits.

BSD-3-Clause. The i3 tests retain their original notice in
[`i3/LICENSE`](i3/LICENSE).
