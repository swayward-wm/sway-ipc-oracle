# sway-ipc-oracle

A conformance oracle for compositors that speak the i3/sway IPC protocol. It
runs i3's own test suite, unchanged, and replays IPC replies captured from real
sway, then records what each compositor did.

It is for people who build or change a sway-compatible compositor and want to
know where it behaves like sway and i3, and where it does not.

## What's in it

- **The i3 suite.** `i3/t/` holds 242 test files from i3, unchanged, at commit
  `9be3249a`. Michael Stapelberg and the i3 contributors wrote them; their
  BSD-3-Clause notice is in [`i3/LICENSE`](i3/LICENSE).
- **Sway's replies.** `sway-ipc/fixtures/` and `sway-ipc/i3-derived/` hold IPC
  replies and events captured from sway 1.12, including 360 tree states reached
  by i3's own tests.
- **Snapshots.** One result file per compositor and version, written only by the
  runners, with review notes kept beside them in `classifications/`.

The oracle came out of [swayward](https://github.com/swayward-wm/swayward),
its first user. Nothing here depends on swayward.

## Snapshots

Each pinned compositor has its own block below, and every block has the same
layout: the measured commit, one table of that compositor's results with a link
to each raw result file, and for the i3 suite two partitions of the same 3,755
assertions, the compositor's comparable view, and that view's asymmetries. No
table holds figures for more than one compositor. These are measurements, not
scores.

Figures marked † come from results listed in [`pending.toml`](pending.toml):
an input changed after they were measured, and they await regeneration in the
pinned container (the i3-suite and i3-derived results since 2026-10-03, the
other sway IPC results since 2026-10-04). They are the last measured values.

Compositors that speak i3/sway IPC but have no snapshot yet are listed in the
inventory below.

### How to read a block

- **i3 suite.** Every one of the 3,755 assertions in the 242 test files lands
  in exactly one outcome. Fail and unreached are counted apart; unreached
  assertions come after the point where a test file aborted. Unstable counts
  assertions, outside flaky files, whose outcome changed between harness runs
  (`i3/unstable.toml`); flaky counts every assertion of a file whose TAP plan
  or abort point changed between runs (`i3/flaky.toml`). Both are
  harness-timing measures, not compositor verdicts.
- **Sway IPC state** replays hand-picked scenarios and compares each IPC reply
  with sway 1.12's capture. i3 reports differs instead of mismatch, because its
  protocol lacks sway's extensions.
- **Events** replays 38 scenarios with a subscription to all nine sway event
  families and compares the ordered event stream.
  `sway-ipc/command-coverage.toml` records which of sway 1.12's 90 top-level
  commands the scenarios exercise, and why the rest cannot run headless.
- **i3-derived** replays 401 distinct states reached by i3's unchanged test
  suite. A mismatch that changes on an immediate fresh retry is unstable rather
  than a compositor verdict.
- **Random** replays 500 captured 20-step sequences, one verdict per seed.
- **Command fuzz** (malformed commands) and **wire fuzz** (broken IPC framing)
  replay sway 1.12 captures at the fixed CI budget. Crash and hang record
  compositor health, separately from mismatch. Human review of fuzz mismatches
  lives in `sway-ipc/classifications/`, keyed by snapshot and case.
  `contrib/validate` checks that each classification names a measured mismatch
  and includes its triage, finding, reason, and source.

Buckets sort the same 3,755 i3-suite assertions by interpretation, using the
classifications in `i3/classifications/`:

- **P** pass; **S** upstream skip.
- **N-i3**: the assertion tests an i3-only premise, so only i3 can pass it.
- **N-x11-all**: an X11 premise that neither measured Wayland stack meets
  (sway 1.12's wlroots XWM, swayward's xwayland-satellite). This is a statement
  about these two stacks, not about what an XWM could implement.
- **N-x11-sway**: X11 metadata that swayward cannot receive through
  xwayland-satellite, while sway's in-process XWM sees it.
- **N-harness**: a measurement artefact: flaky files, unstable assertions, and
  unreached assertions whose abort cause the source does not show.
- **N-gap**: a comparable non-pass: reviewed findings, unreviewed fails, and
  declared deviations.

A compositor's comparable view is the set of assertions whose bucket, for that
compositor, is not N-i3, N-x11-all or N-harness. Each view is shown only in
its own block, with its asymmetries: it excludes rows by that compositor's own
labels, so the views have different denominators. No view is the fair one.

Most of sway's non-passes against i3's tests are deliberate: sway is a Wayland
compositor, and many i3 tests assume X11. Every non-pass carries a reviewed
classification with a source citation, in `i3/classifications/`.

### i3 4.25 (`9be3249a`)

| Corpus | Outcome | Raw result |
| --- | --- | --- |
| i3 suite | 3,754 pass / 1 skip / 0 fail / 0 unreached / 0 unstable / 0 flaky | [i3 suite](i3/results/i3-4.25.toml) |
| sway IPC state | 242 match / 246 differs / 540 not applicable† | [sway IPC state](sway-ipc/results/i3-4.25.toml) |
| events | 1 match / 41 differs / 30 not applicable† | [events](sway-ipc/results/i3-4.25-events.toml) |
| i3-derived | 1,096 match / 2,248 differs / 0 unstable / 2,227 not applicable† | [i3-derived](sway-ipc/results/i3-4.25-i3-derived.toml) |
| random | not yet measured | — |
| command fuzz | 33 match / 159 differs / 3 not applicable / 0 crash / 0 hang† | [command fuzz](sway-ipc/results/i3-4.25-command-fuzz.toml) |
| wire fuzz | 3 match / 7 differs / 0 not applicable / 0 crash / 0 hang† | [wire fuzz](sway-ipc/results/i3-4.25-wire-fuzz.toml) |

| P | S | N-i3 | N-x11-all | N-x11-sway | N-harness | N-gap |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 3,754 | 1 | 0 | 0 | 0 | 0 | 0 |

Comparable view of i3 4.25 (3,755 rows):

| P | S | N-x11-sway | N-gap | pass | skip | fail | unreached | unstable | flaky |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 3,754 | 1 | 0 | 0 | 3,754 | 1 | 0 | 0 | 0 | 0 |

Asymmetries: i3's view excludes no rows, because i3 reaches every assertion.
The i3 suite was written for i3, so this view is the suite's own baseline, not
a measure of sway compatibility.

### sway 1.12 (`88869399`)

| Corpus | Outcome | Raw result |
| --- | --- | --- |
| i3 suite | 1,461 pass / 20 skip / 716 fail / 1,401 unreached / 135 unstable / 22 flaky† | [i3 suite](i3/results/sway-1.12.toml) |
| sway IPC state | 740 match / 0 mismatch / 40 not applicable† | [sway IPC state](sway-ipc/results/sway-1.12.toml) |
| events | 45 match / 0 mismatch / 0 not applicable† | [events](sway-ipc/results/sway-1.12-events.toml) |
| i3-derived | 4,180 match / 0 mismatch / 0 unstable / 0 not applicable† | [i3-derived](sway-ipc/results/sway-1.12-i3-derived.toml) |
| random | 500 match / 0 mismatch / 0 unstable / 0 not applicable† | [random](sway-ipc/results/sway-1.12-random.toml) |
| command fuzz | 195 match / 0 mismatch / 0 not applicable / 0 crash / 0 hang† | [command fuzz](sway-ipc/results/sway-1.12-command-fuzz.toml) |
| wire fuzz | 10 match / 0 mismatch / 0 not applicable / 0 crash / 0 hang† | [wire fuzz](sway-ipc/results/sway-1.12-wire-fuzz.toml) |

| P | S | N-i3 | N-x11-all | N-x11-sway | N-harness | N-gap |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1,461† | 20† | 360† | 276† | 0† | 848† (539 inferred X11 cause, unverified) | 790† (233 not yet reviewed) |

Comparable view of sway 1.12 (2,271 rows):

| P | S | N-x11-sway | N-gap | pass | skip | fail | unreached | unstable | flaky |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1,461† | 20† | 0† | 790† | 1,461† | 20† | 619† | 171† | 0† | 0† |

Asymmetries: sway's view and swayward's view share 2,146 rows. 125 rows are
in sway's view only, excluded by swayward's labels; sway passes 20 of them: 86
kill, 20 swayward flaky file, 9 `sway_no_append_layout`, 5 XTEST, and 5 i3
output or rename semantics. Measured on sway's view, swayward has 1,304 P.
Sway-sourced `*_finding` families describe where sway differs from i3, and
each names its test file.

### swayward (`ec03e0af`)

| Corpus | Outcome | Raw result |
| --- | --- | --- |
| i3 suite | 1,453 pass / 11 skip / 800 fail / 1,469 unreached / 0 unstable / 22 flaky† | [i3 suite](i3/results/swayward-ec03e0af.toml) |
| sway IPC state | 749 match / 31 mismatch / 0 not applicable† | [sway IPC state](sway-ipc/results/swayward-ec03e0af.toml) |
| events | 44 match / 1 mismatch / 0 not applicable† | [events](sway-ipc/results/swayward-ec03e0af-events.toml) |
| i3-derived | 4,118 match / 62 mismatch / 0 unstable / 0 not applicable† | [i3-derived](sway-ipc/results/swayward-ec03e0af-i3-derived.toml) |
| random | 329 match / 171 mismatch / 0 unstable / 0 not applicable† | [random](sway-ipc/results/swayward-ec03e0af-random.toml) |
| command fuzz | 195 match / 0 mismatch / 0 not applicable / 0 crash / 0 hang† | [command fuzz](sway-ipc/results/swayward-ec03e0af-command-fuzz.toml) |
| wire fuzz | 6 match / 4 mismatch / 0 not applicable / 0 crash / 0 hang† | [wire fuzz](sway-ipc/results/swayward-ec03e0af-wire-fuzz.toml) |

| P | S | N-i3 | N-x11-all | N-x11-sway | N-harness | N-gap |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1,453† | 11† | 327† | 836† | 349† | 118† | 661† (81 not yet reviewed) |

Comparable view of swayward `ec03e0af` (2,474 rows):

| P | S | N-x11-sway | N-gap | pass | skip | fail | unreached | unstable | flaky |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1,453† | 11† | 349† | 661† | 1,453† | 11† | 715† | 295† | 0† | 0† |

Asymmetries: swayward's view and sway's view share 2,146 rows. 328 rows are
in swayward's view only, excluded by sway's labels; swayward passes 149 of
them: 121 sway unstable, 65 unreached with undetermined cause, 49 sway-only
kill overrides, 25 `i3_open_command`, 22 sway flaky file, 23 EWMH or XTEST rows
where swayward keeps a reviewed label, and 23 in smaller families. Measured on
swayward's view, sway has 1,441 P.

## Try it

Run one test file against your own sway build:

```sh
./contrib/i3-suite-run --compositor sway --binary /path/to/sway 001-tile.t
```

- [Running the oracle](docs/running.md): the i3 suite and the sway IPC scenarios.
- [Reproducing the snapshots](docs/reproducing.md): the pinned container, and one command per snapshot.
- [Adding a compositor](docs/adding-a-compositor.md).

## Compositor inventory

Compositors that speak i3/sway IPC, and whether they have a snapshot.

| Project | IPC | Snapshot |
| --- | --- | --- |
| [i3](https://i3wm.org/docs/ipc.html) | i3 IPC | Yes |
| [sway](https://github.com/swaywm/sway/blob/master/sway/sway-ipc.7.scd) | sway IPC | Yes |
| [swayward](https://github.com/swayward-wm/swayward) | sway IPC | Yes |
| [SwayFX](https://github.com/wlrfx/swayfx) | sway IPC, plus effect commands | Not yet |
| [scroll](https://github.com/dawsers/scroll) | sway IPC, plus scrolling-layout extensions (`scrollmsg`) | Not yet |
| [swirl](https://github.com/visnudeva/swirl) | sway IPC (stock `swaymsg`) | Not yet |
| [miracle-wm](https://wiki.miracle-wm.org/develop/ipc/) | i3/sway IPC; no `GET_CONFIG`, `GET_BAR_CONFIG`, `GET_INPUTS` or `GET_SEATS` yet | Not yet |

i3-gaps was merged into i3 in 4.22, so the i3 snapshot covers it. A project gets
a snapshot only after its maintainers have had a courtesy note.

## Contributing

Read [`CONTRIBUTING.md`](CONTRIBUTING.md) before changing a runner, an adapter
or a snapshot. It explains how snapshots stay reproducible and fair.

## Licence

BSD-3-Clause. The i3 tests keep their original notice in
[`i3/LICENSE`](i3/LICENSE).
