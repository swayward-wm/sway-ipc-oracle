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

Each row is one pinned compositor measured against the oracle. The i3-suite
column is pass/skip/fail (fail includes assertions the run never reached) over
stable assertions. The sway-ipc column is match/mismatch/not applicable; for i3
it is match/differs/not applicable, because i3's protocol lacks sway's
extensions. These are measurements, not scores. Results listed in
[`pending.toml`](pending.toml) predate a harness change and await regeneration;
their figures are the last measured values. Rows marked "not yet measured"
are compositors that speak i3/sway IPC but have no snapshot yet; see the
inventory below.

| Snapshot | i3 suite (pass/skip/fail) | Unstable | sway IPC | Events | Commit |
| --- | --- | --- | --- | --- | --- |
| `i3-4.25` | 3,754/1/0 | 0 | 242/246/540 | 1/41/30 | `9be3249a` |
| `sway-1.12` | 1,461/20/2,117 | 142 | 740/0/40 | 45/0/0 | `88869399` |
| `swayward-ec03e0af` | 1,453/11/2,269 | 12 | 749/31/0 | 44/1/0 | `ec03e0af` |
| SwayFX | not yet measured | — | — | — | — |
| scroll | not yet measured | — | — | — | — |
| swirl | not yet measured | — | — | — | — |
| miracle-wm | not yet measured | — | — | — | — |

Unstable counts assertions whose outcome changed between harness runs; it is a
harness-timing measure, not a compositor verdict.

Most of sway's non-passes against i3's tests are deliberate: sway is a Wayland
compositor, and many i3 tests assume X11. Every non-pass carries a reviewed
classification with a source citation, in `i3/classifications/`.

The events column replays 38 scenarios with a subscription to all nine sway
event families and compares the ordered event stream (match/mismatch/not
applicable; match/differs/not applicable for i3).
`sway-ipc/command-coverage.toml` records which of sway 1.12's 90 top-level
commands the scenarios exercise, and why the rest cannot run headless.

### i3-derived sway IPC corpus

The derived corpus contains 401 distinct states reached by i3's unchanged test
suite. Counts are match/mismatch/unstable/not applicable; i3 uses differs
instead of mismatch because its protocol lacks sway extensions. A mismatch
that changes on an immediate fresh retry is unstable rather than a compositor
verdict.

| Snapshot | Match | Mismatch or differs | Unstable | Not applicable |
| --- | ---: | ---: | ---: | ---: |
| `i3-4.25` | 1,096 | 2,248 | 0 | 2,227 |
| `sway-1.12` | 4,180 | 0 | 0 | 0 |
| `swayward-ec03e0af` | 4,118 | 62 | 0 | 0 |

### Random sequence corpus

The random corpus replays 500 captured 20-step sequences and reports
match/mismatch/unstable/not applicable per seed. A mismatch that changes on an
immediate fresh retry is unstable rather than a compositor verdict. The i3
replay is pending.

| Snapshot | match/mismatch/unstable/n.a. | Commit |
| --- | --- | --- |
| `sway-1.12-random` | 500/0/0/0 | `88869399` |
| `swayward-ec03e0af-random` | 329/171/0/0 | `ec03e0af` |

### Fuzz corpora

Malformed commands (`command-fuzz`) and broken IPC framing (`wire-fuzz`),
captured from sway 1.12 and replayed at the fixed CI budget. Figures are
match/mismatch/not applicable/crash/hang, or match/differs/not applicable/crash/hang
for i3. Crash and hang record compositor health, separately from mismatch.
Human review of fuzz mismatches lives in `sway-ipc/classifications/`, keyed by
snapshot and case. `contrib/validate` checks that each classification names a
measured mismatch and includes its triage, finding, reason, and source.

| Snapshot | match/mismatch/n.a./crash/hang | Commit |
| --- | --- | --- |
| `i3-4.25-command-fuzz` | 33/159/3/0/0 | `9be3249a` |
| `i3-4.25-wire-fuzz` | 3/7/0/0/0 | `9be3249a` |
| `sway-1.12-command-fuzz` | 195/0/0/0/0 | `88869399` |
| `sway-1.12-wire-fuzz` | 10/0/0/0/0 | `88869399` |
| `swayward-ec03e0af-command-fuzz` | 195/0/0/0/0 | `ec03e0af` |
| `swayward-ec03e0af-wire-fuzz` | 6/4/0/0/0 | `ec03e0af` |

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
