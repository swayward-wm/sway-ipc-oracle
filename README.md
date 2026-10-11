# sway-ipc-oracle

A compatibility test suite for compositors that speak the i3/sway IPC protocol.
Point it at a compositor and it tells you, request by request, where that
compositor behaves like sway and where it does not. Every difference comes
with a reason and a source citation.

It is the most comprehensive public i3/sway IPC compatibility suite we know
of. Seven compositors are measured against it, and you can reproduce every
published figure from a pinned container.

**[See the results for each compositor →](docs/results.md)**

## What it is

Sway ships no conformance suite, and i3's test suite only targets i3 on X11.
The one earlier attempt, [swaywm/sway-tests](https://github.com/swaywm/sway-tests),
is archived. So anything that claims to be "sway-compatible" has had nothing
to check that claim against. The oracle fills that gap with two sources of
truth:

- **i3's own 242 test files (3,755 assertions)**, unchanged, run directly
  against each compositor through a small adapter. Michael Stapelberg and the
  i3 contributors wrote them; they are realistic command sequences from the
  people who defined the protocol.
- **Sway 1.12's recorded replies.** The oracle drives pinned sway through
  hundreds of scenarios, records every IPC reply and event, and compares other
  compositors against that recording field by field.

## Why it is useful

- **It is broad.** The sway IPC side covers 367 hand-written scenarios, 418
  window-tree states reached by i3's own tests, all nine event types, 1,500
  captured random command sequences, and malformed commands and broken IPC
  framing. It also tracks which of sway's top-level commands are covered.
- **Differences are explained.** A non-match is not left as a bare number.
  Each one is classified as a bug, a declared deviation, a design difference
  the project chose on purpose, or a harness issue, and it cites the source
  line that explains it. `contrib/validate` checks every classification
  against a measured non-match and prints how many are still unreviewed.
  The results page shows that count for each compositor.
- **It is reproducible.** Every compositor is pinned to an exact commit and
  built in one container. A snapshot is raw runner output; nobody edits it by
  hand. Each result records a hash of the inputs that produced it, so a stale
  result fails validation.
- **It treats every compositor the same.** One rule set and one comparison.
  An adapter may translate a config or start a compositor headless, but it can
  never change an assertion or a value read over IPC.
- **It finds real bugs.** Running it has turned up crashes in sway itself
  ([four distinct ones](docs/sway-crashes.md)) and in other compositors, along
  with hundreds of behaviour differences in
  [swayward](https://github.com/swayward-wm/swayward), the compositor it was
  built for.

## What is measured

Each compositor gets its own block on the [results page](docs/results.md):

- [i3 4.25](docs/results.md#i3-425-9be3249a): where the i3 suite and the protocol come from.
- [sway 1.12](docs/results.md#sway-112-88869399): the reference.
- [swayward](docs/results.md#swayward-ec03e0af): the compositor the oracle was built for.
- [SwayFX 0.6](docs/results.md#swayfx-06-fd71a6bd): sway with visual effects.
- [scroll 1.12.21](docs/results.md#scroll-11221-f80c5820): a sway fork with a scrolling layout.
- [miracle-wm 0.11.2](docs/results.md#miracle-wm-0112-2df22b0e): a Mir compositor with i3/sway IPC.
- [swirl](docs/results.md#swirl-dc6382f2): a rebrand of scroll 1.12.17.

## What it is not

- **Not a ranking.** The results page has one block per compositor and never
  compares them in one table. A fork that removes a command on purpose has
  made a design choice, not failed a test.
- **Not a test of looks or feel.** The oracle sees only what the IPC socket
  reports: the window tree, workspaces, outputs, replies and events. Rendering,
  animation, input latency and visual effects are out of scope.
- **Not an i3 X11 test.** Many i3 tests assume X11 window-manager behaviour.
  For Wayland compositors those rows are labelled as X11 premises and set
  apart, not counted as failures.
- **Not a statement about what sway should do.** Sway 1.12 is the reference
  because "sway-compatible" means "does what sway does". Where sway itself
  crashes or reports stale state, the oracle records that and says why.

## Try it

Run one i3 test file against your own sway build:

```sh
./contrib/i3-suite-run --compositor sway --binary /path/to/sway 001-tile.t
```

Run the sway IPC scenarios against a compositor and compare with sway:

```sh
./contrib/sway-ipc-run --compositor sway --binary /path/to/sway --out /tmp/mine.toml
```

## Documentation

- [Results](docs/results.md): every measured compositor, how to read the
  figures, and where the reviews live.
- [Running the oracle](docs/running.md): the i3 suite, the sway IPC
  scenarios, the fuzz and random corpora.
- [Reproducing the results](docs/reproducing.md): the pinned container and
  one command per snapshot.
- [Run the oracle in your compositor's CI](docs/ci.md): pin the oracle, keep
  a baseline, and fail a pull request only on new differences.
- [Adding a compositor](docs/adding-a-compositor.md): adapters, pins and
  classifications, plus the compositors the oracle cannot measure yet.
- [Pinned sway crashes](docs/sway-crashes.md): sway 1.12 crashes found by the
  corpora.
- [Contributing](CONTRIBUTING.md): the rules that keep snapshots
  reproducible and fair.

## Licence

BSD-3-Clause. The i3 tests in `i3/t/` keep their original notice in
[`i3/LICENSE`](i3/LICENSE); Michael Stapelberg and the i3 contributors wrote
them.
