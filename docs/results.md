# Results

One block per measured compositor. Each block shows what that compositor did against the oracle at its pinned commit, with a link to every raw result file. No table holds more than one compositor, and nothing here is a score or a ranking.

Figures marked † come from results listed in [`pending.toml`](../pending.toml): an input changed after they were measured, and they wait for the next regeneration in the pinned container. They are the last measured values.

The i3 suite has not been run against SwayFX, scroll, miracle-wm or swirl yet; their blocks say `not measured` for it. `contrib/tests/readme-snapshots` checks every figure on this page against the committed result files.

## Snapshots

Every block sorts the same 3,755 assertions of the i3 suite and the same sway IPC corpora, so a figure means the same thing in every block.

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
- **Events** replays 36 scenarios (45 captures) with a subscription to all
  nine sway event families and compares the ordered event stream.
  `sway-ipc/command-coverage.toml` records which of sway 1.12's 90 top-level
  commands the scenarios or the `random-v2` generator exercise, and why the
  rest cannot run headless.
- **i3-derived** replays 418 distinct states reached by i3's unchanged test
  suite. A mismatch that changes on an immediate fresh retry is unstable rather
  than a compositor verdict.
- **Random** replays 500 captured 20-step sequences, one verdict per seed.
- **Random v2** replays 1,000 captured 20-step sequences drawn from a wider
  command vocabulary (`sway-ipc/random-v2/vocabulary.json`), one verdict per
  seed. Random v1 is unchanged, so its figures stay comparable.
- **Command fuzz** (malformed commands) and **wire fuzz** (broken IPC framing)
  replay sway 1.12 captures at the fixed CI budget. Crash and hang record
  compositor health, separately from mismatch.

Human review of sway-IPC mismatches lives in `sway-ipc/classifications/`, one
file per result, keyed by case (fuzz), seed (random) or scenario and request
(state, events, i3-derived). Each swayward row is a swayward bug (naming its
open task), a documented deviation (citing its KNOWN_DEVIATIONS anchor) or a
harness issue (with evidence). A row of another compositor is a design
difference (behaviour the compositor documents or builds on purpose), a
deviation (an undocumented difference from sway) or a harness issue, each
citing the compositor's source at its pin. `contrib/validate` checks that each classification names a
measured mismatch and includes its triage, finding, reason, and source, and
prints the untriaged count per corpus. A `[basis]` table names a newer,
unpinned measurement the review used; mismatches that matched there are listed
in it instead of classified.

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
  unreached assertions whose abort cause neither the source nor a focused
  rerun (`i3/abort-causes/`) shows.
- **N-gap**: a comparable non-pass: reviewed findings, unreviewed fails, and
  declared deviations.

A compositor's comparable view is the set of assertions whose bucket, for that
compositor, is not N-i3, N-x11-all or N-harness. Each view is shown only in
its own block, with its asymmetries: it excludes rows by that compositor's own
labels, so the views have different denominators. No view is the fair one.

`contrib/i3_buckets.py` holds the bucket rules and generates each block's
i3-suite region (the bucket table, review line, comparable view and
asymmetries) from the committed TOML; `contrib/validate` fails if a region
differs from its output.

Many of sway's non-passes against i3's tests are deliberate: sway is a Wayland
compositor, and many i3 tests assume X11. Every stable non-pass has a row in
`i3/classifications/`, but not every row is reviewed. A verified row names a
reviewed reason family or cites its source. An unverified row carries a
provisional note, such as "the pinned run emitted no TAP plan", or is marked
`unclassified`. Each block's review line counts these rows from its
classification file, and `contrib/validate` checks the line.


### i3 4.25 (`9be3249a`)

| Corpus | Outcome | Raw result |
| --- | --- | --- |
| i3 suite | 3,754 pass / 1 skip / 0 fail / 0 unreached / 0 unstable / 0 flaky | [i3 suite](../i3/results/i3-4.25.toml) |
| sway IPC state | 245 match / 251 differs / 546 not applicable† | [sway IPC state](../sway-ipc/results/i3-4.25.toml) |
| events | 1 match / 41 differs / 30 not applicable† | [events](../sway-ipc/results/i3-4.25-events.toml) |
| i3-derived | 1,096 match / 2,248 differs / 0 unstable / 2,227 not applicable† | [i3-derived](../sway-ipc/results/i3-4.25-i3-derived.toml) |
| random | not yet measured | — |
| random-v2 | not yet measured | — |
| command fuzz | 33 match / 159 differs / 3 not applicable / 0 crash / 0 hang† | [command fuzz](../sway-ipc/results/i3-4.25-command-fuzz.toml) |
| wire fuzz | 3 match / 7 differs / 0 not applicable / 0 crash / 0 hang† | [wire fuzz](../sway-ipc/results/i3-4.25-wire-fuzz.toml) |

<!-- i3-suite: generated by contrib/i3_buckets.py from the committed results; do not edit by hand -->
| P | S | N-i3 | N-x11-all | N-x11-sway | N-harness | N-gap |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 3,754 | 1 | 0 | 0 | 0 | 0 | 0 |

i3-suite review: 1 non-pass row; 1 verified, 0 unverified, 0 of them unclassified.

Comparable view of i3 4.25 (3,755 rows):

| P | S | N-x11-sway | N-gap | pass | skip | fail | unreached | unstable | flaky |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 3,754 | 1 | 0 | 0 | 3,754 | 1 | 0 | 0 | 0 | 0 |

Asymmetries: i3's view excludes no rows: every assertion is P or S.
<!-- end i3-suite -->

The i3 suite was written for i3, so this view is the suite's own baseline, not
a measure of sway compatibility.

### sway 1.12 (`88869399`)

| Corpus | Outcome | Raw result |
| --- | --- | --- |
| i3 suite | 1,461 pass / 20 skip / 716 fail / 1,401 unreached / 135 unstable / 22 flaky† | [i3 suite](../i3/results/sway-1.12.toml) |
| sway IPC state | 750 match / 0 mismatch / 40 not applicable† | [sway IPC state](../sway-ipc/results/sway-1.12.toml) |
| events | 45 match / 0 mismatch / 0 not applicable† | [events](../sway-ipc/results/sway-1.12-events.toml) |
| i3-derived | 4,180 match / 0 mismatch / 0 unstable / 0 not applicable† | [i3-derived](../sway-ipc/results/sway-1.12-i3-derived.toml) |
| random | 500 match / 0 mismatch / 0 unstable / 0 not applicable / 0 crash† | [random](../sway-ipc/results/sway-1.12-random.toml) |
| random-v2 | not yet measured | — |
| command fuzz | 195 match / 0 mismatch / 0 not applicable / 0 crash / 0 hang† | [command fuzz](../sway-ipc/results/sway-1.12-command-fuzz.toml) |
| wire fuzz | 10 match / 0 mismatch / 0 not applicable / 0 crash / 0 hang† | [wire fuzz](../sway-ipc/results/sway-1.12-wire-fuzz.toml) |

<!-- i3-suite: generated by contrib/i3_buckets.py from the committed results; do not edit by hand -->
| P | S | N-i3 | N-x11-all | N-x11-sway | N-harness | N-gap |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1,461† | 20† | 360† | 815† (539† abort causes verified by focused reruns) | 0† | 309† | 790† (233† not yet reviewed) |

i3-suite review: 2,137† non-pass rows; 915† verified, 1,222† unverified, 587† of them unclassified.

Comparable view of sway 1.12 (2,271† rows):

| P | S | N-x11-sway | N-gap | pass | skip | fail | unreached | unstable | flaky |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1,461† | 20† | 0† | 790† | 1,461† | 20† | 619† | 171† | 0† | 0† |

Asymmetries: sway's view and swayward's view share 2,146† rows. 125† rows are in sway's view only, excluded by swayward's labels, and sway passes 20† of them. By swayward's bucket and cause:

- 86† N-x11-all: family: `xwm_kill_client_fallback`
- 20† N-harness: flaky file
- 9† N-i3: family: `sway_no_append_layout`
- 5† N-x11-all: family: `headless_xtest_boundary`
- 4† N-i3: family: `i3_output_selection_semantics`
- 1† N-i3: family: `i3_workspace_rename_semantics`

Measured on sway's view, swayward has 1,304† P.
<!-- end i3-suite -->

Sway-sourced `*_finding` families describe where sway differs from i3, and
each names its test file.

### swayward (`ec03e0af`)

| Corpus | Outcome | Raw result |
| --- | --- | --- |
| i3 suite | 1,453 pass / 11 skip / 800 fail / 1,469 unreached / 0 unstable / 22 flaky† | [i3 suite](../i3/results/swayward-ec03e0af.toml) |
| sway IPC state | 758 match / 32 mismatch / 0 not applicable† | [sway IPC state](../sway-ipc/results/swayward-ec03e0af.toml) |
| events | 44 match / 1 mismatch / 0 not applicable† | [events](../sway-ipc/results/swayward-ec03e0af-events.toml) |
| i3-derived | 4,118 match / 62 mismatch / 0 unstable / 0 not applicable† | [i3-derived](../sway-ipc/results/swayward-ec03e0af-i3-derived.toml) |
| random | 329 match / 171 mismatch / 0 unstable / 0 not applicable / 0 crash† | [random](../sway-ipc/results/swayward-ec03e0af-random.toml) |
| random-v2 | not yet measured | — |
| command fuzz | 195 match / 0 mismatch / 0 not applicable / 0 crash / 0 hang† | [command fuzz](../sway-ipc/results/swayward-ec03e0af-command-fuzz.toml) |
| wire fuzz | 6 match / 4 mismatch / 0 not applicable / 0 crash / 0 hang† | [wire fuzz](../sway-ipc/results/swayward-ec03e0af-wire-fuzz.toml) |

<!-- i3-suite: generated by contrib/i3_buckets.py from the committed results; do not edit by hand -->
| P | S | N-i3 | N-x11-all | N-x11-sway | N-harness | N-gap |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1,453† | 11† | 327† | 836† | 381† | 118† | 629† (81† not yet reviewed) |

i3-suite review: 2,280† non-pass rows; 2,199† verified, 81† unverified, 81† of them unclassified.

Comparable view of swayward `ec03e0af` (2,474† rows):

| P | S | N-x11-sway | N-gap | pass | skip | fail | unreached | unstable | flaky |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1,453† | 11† | 381† | 629† | 1,453† | 11† | 715† | 295† | 0† | 0† |

Asymmetries: swayward's view and sway's view share 2,146† rows. 328† rows are in swayward's view only, excluded by sway's labels, and swayward passes 149† of them. By sway's bucket and cause:

- 121† N-harness: unstable assertion
- 65† N-harness: unreached, abort cause undetermined
- 49† N-x11-all: abort point decided from the test source: kill disconnects i3test X client
- 25† N-i3: family: `i3_open_command`
- 22† N-harness: flaky file
- 17† N-x11-all: family: `headless_xtest_boundary`
- 12† N-x11-all: abort point decided from the test source: EWMH _NET_MOVERESIZE_WINDOW
- 5† N-x11-all: abort point decided from the test source: EWMH _NET_WM_DESKTOP client message
- 5† N-x11-all: abort point decided from the test source: EWMH _NET_WM_VISIBLE_NAME
- 2† N-harness: abort point decided from the test source: 65,536 sync_with_i3 loop vs settle-poll shim
- 2† N-i3: family: `sway_command_vocabulary`
- 2† N-i3: family: `sway_hidden_scratchpad_floating`
- 1† N-x11-all: abort point decided from the test source: XTEST button press

Measured on swayward's view, sway has 1,441† P.
<!-- end i3-suite -->

### swayfx 0.6 (`fd71a6bd`)

| Corpus | Outcome | Raw result |
| --- | --- | --- |
| i3 suite | not measured | — |
| sway IPC state | 790 match / 0 mismatch / 0 not applicable† | [sway IPC state](../sway-ipc/results/swayfx-0.6.toml) |
| events | 45 match / 0 mismatch / 0 not applicable† | [events](../sway-ipc/results/swayfx-0.6-events.toml) |
| i3-derived | not yet measured | — |
| random | 500 match / 0 mismatch / 0 unstable / 0 not applicable / 0 crash† | [random](../sway-ipc/results/swayfx-0.6-random.toml) |
| random-v2 | not yet measured | — |
| command fuzz | 195 match / 0 mismatch / 0 not applicable / 0 crash / 0 hang | [command fuzz](../sway-ipc/results/swayfx-0.6-command-fuzz.toml) |
| wire fuzz | 10 match / 0 mismatch / 0 not applicable / 0 crash / 0 hang | [wire fuzz](../sway-ipc/results/swayfx-0.6-wire-fuzz.toml) |

SwayFX is sway 1.12 with visual effects (blur, shadows, rounded corners) built on scenefx. The adapter subclasses sway's with no translations. Every non-match would need a classification; there are none. Adapter notes: [`sway-ipc/adapters/swayfx.md`](../sway-ipc/adapters/swayfx.md).

### scroll 1.12.21 (`f80c5820`)

| Corpus | Outcome | Raw result |
| --- | --- | --- |
| i3 suite | not measured | — |
| sway IPC state | 578 match / 212 mismatch / 0 not applicable† | [sway IPC state](../sway-ipc/results/scroll-1.12.21.toml) |
| events | 1 match / 44 mismatch / 0 not applicable† | [events](../sway-ipc/results/scroll-1.12.21-events.toml) |
| i3-derived | not yet measured | — |
| random | 0 match / 499 mismatch / 0 unstable / 0 not applicable / 1 crash† | [random](../sway-ipc/results/scroll-1.12.21-random.toml) |
| random-v2 | not yet measured | — |
| command fuzz | 173 match / 22 mismatch / 0 not applicable / 0 crash / 0 hang | [command fuzz](../sway-ipc/results/scroll-1.12.21-command-fuzz.toml) |
| wire fuzz | 10 match / 0 mismatch / 0 not applicable / 0 crash / 0 hang | [wire fuzz](../sway-ipc/results/scroll-1.12.21-wire-fuzz.toml) |

scroll is a sway fork with a scrolling column layout. It removes `split`, `splith`, `splitv`, `splitt` and `layout`, so most tree-shape mismatches are by design. Every non-match is classified in [`sway-ipc/classifications/`](../sway-ipc/classifications/) as a design difference or a deviation, citing scroll's source. Adapter notes: [`sway-ipc/adapters/scroll.md`](../sway-ipc/adapters/scroll.md).

### miracle-wm 0.11.2 (`2df22b0e`)

| Corpus | Outcome | Raw result |
| --- | --- | --- |
| i3 suite | not measured | — |
| sway IPC state | 173 match / 459 mismatch / 158 not applicable† | [sway IPC state](../sway-ipc/results/miracle-wm-0.11.2.toml) |
| events | 1 match / 44 mismatch / 0 not applicable† | [events](../sway-ipc/results/miracle-wm-0.11.2-events.toml) |
| i3-derived | not yet measured | — |
| random | 0 match / 500 mismatch / 0 unstable / 0 not applicable / 0 crash† | [random](../sway-ipc/results/miracle-wm-0.11.2-random.toml) |
| random-v2 | not yet measured | — |
| command fuzz | 24 match / 168 mismatch / 0 not applicable / 3 crash / 0 hang | [command fuzz](../sway-ipc/results/miracle-wm-0.11.2-command-fuzz.toml) |
| wire fuzz | 4 match / 4 mismatch / 0 not applicable / 2 crash / 0 hang | [wire fuzz](../sway-ipc/results/miracle-wm-0.11.2-wire-fuzz.toml) |

miracle-wm is a Mir compositor (not wlroots) that speaks i3/sway IPC and a subset of sway's commands. It has no `GET_CONFIG`, `GET_BAR_CONFIG`, `GET_INPUTS` or `GET_SEATS`, so those requests are not applicable, and no `kill`, so the adapter closes windows from the client side. Every non-match is classified, citing miracle-wm's source. Adapter notes: [`sway-ipc/adapters/miracle-wm.md`](../sway-ipc/adapters/miracle-wm.md).

### swirl (`dc6382f2`)

| Corpus | Outcome | Raw result |
| --- | --- | --- |
| i3 suite | not measured | — |
| sway IPC state | 578 match / 212 mismatch / 0 not applicable† | [sway IPC state](../sway-ipc/results/swirl-dc6382f2.toml) |
| events | 1 match / 44 mismatch / 0 not applicable† | [events](../sway-ipc/results/swirl-dc6382f2-events.toml) |
| i3-derived | not yet measured | — |
| random | 0 match / 499 mismatch / 0 unstable / 0 not applicable / 1 crash† | [random](../sway-ipc/results/swirl-dc6382f2-random.toml) |
| random-v2 | not yet measured | — |
| command fuzz | 173 match / 22 mismatch / 0 not applicable / 0 crash / 0 hang | [command fuzz](../sway-ipc/results/swirl-dc6382f2-command-fuzz.toml) |
| wire fuzz | 10 match / 0 mismatch / 0 not applicable / 0 crash / 0 hang | [wire fuzz](../sway-ipc/results/swirl-dc6382f2-wire-fuzz.toml) |

swirl is a rebrand of scroll 1.12.17 with no tagged release, so its snapshot name carries the commit. Its classifications reuse scroll's where the cause is the same code, citing swirl's source. Adapter notes: [`sway-ipc/adapters/swirl.md`](../sway-ipc/adapters/swirl.md).

## Where the review lives

- i3-suite reasons: [`i3/classifications/`](../i3/classifications/), with abort-cause evidence in [`i3/abort-causes/`](../i3/abort-causes/).
- sway IPC reasons: [`sway-ipc/classifications/`](../sway-ipc/classifications/), one file per result.
- Crashes of pinned sway that the corpora avoid or record: [`sway-crashes.md`](sway-crashes.md).
