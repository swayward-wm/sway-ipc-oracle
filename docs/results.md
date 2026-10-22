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
  For state and events, a scenario with a mismatch or crash reruns once on a
  fresh compositor; a row that changes is unstable. A release-candidate
  regeneration also marks unstable any row that differs between its two runs.
  `sway-ipc/command-coverage.toml` records which of sway 1.12's 90 top-level
  commands the scenarios or the `random-v2` generator exercise, and why the
  rest cannot run headless.
- **i3-derived** replays 416 distinct states reached by i3's unchanged test
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
prints the untriaged count per corpus, followed by the corpus's unstable row
count when it has any (`state 0 of 32; 2 unstable`). An unstable row is not a
measured mismatch, so a classification that names it fails validation. A `[basis]` table names a newer,
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
| sway IPC state | 1,745 match / 1,871 differs / 0 unstable / 3,053 not applicable | [sway IPC state](../sway-ipc/results/i3-4.25.toml) |
| events | 1 match / 41 differs / 0 unstable / 30 not applicable | [events](../sway-ipc/results/i3-4.25-events.toml) |
| i3-derived | 1,211 match / 2,117 differs / 0 unstable / 2,214 not applicable | [i3-derived](../sway-ipc/results/i3-4.25-i3-derived.toml) |
| random | 0 match / 0 differs / 0 unstable / 500 not applicable / 0 crash | [random](../sway-ipc/results/i3-4.25-random.toml) |
| random-v2 | not yet measured | — |
| command fuzz | 33 match / 159 differs / 3 not applicable / 0 crash / 0 hang | [command fuzz](../sway-ipc/results/i3-4.25-command-fuzz.toml) |
| wire fuzz | 3 match / 7 differs / 0 not applicable / 0 crash / 0 hang | [wire fuzz](../sway-ipc/results/i3-4.25-wire-fuzz.toml) |

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

The random corpus has not been replayed against i3: its runner first sets every
output to 1280x720 with `output * mode --custom`, a sway command that i3 rejects
as a parse error, so all 500 seeds are not applicable. The result file gives
the cause.

### sway 1.12 (`88869399`)

| Corpus | Outcome | Raw result |
| --- | --- | --- |
| i3 suite | 1,517 pass / 20 skip / 659 fail / 1,401 unreached / 132 unstable / 26 flaky | [i3 suite](../i3/results/sway-1.12.toml) |
| sway IPC state | 4,916 match / 1 mismatch / 0 unstable / 0 not applicable | [sway IPC state](../sway-ipc/results/sway-1.12.toml) |
| events | 45 match / 0 mismatch / 0 unstable / 0 not applicable | [events](../sway-ipc/results/sway-1.12-events.toml) |
| i3-derived | 4,160 match / 0 mismatch / 0 unstable / 0 not applicable | [i3-derived](../sway-ipc/results/sway-1.12-i3-derived.toml) |
| random | 500 match / 0 mismatch / 0 unstable / 0 not applicable / 0 crash | [random](../sway-ipc/results/sway-1.12-random.toml) |
| random-v2 | not yet measured | — |
| command fuzz | 195 match / 0 mismatch / 0 not applicable / 0 crash / 0 hang | [command fuzz](../sway-ipc/results/sway-1.12-command-fuzz.toml) |
| wire fuzz | 10 match / 0 mismatch / 0 not applicable / 0 crash / 0 hang | [wire fuzz](../sway-ipc/results/sway-1.12-wire-fuzz.toml) |

<!-- i3-suite: generated by contrib/i3_buckets.py from the committed results; do not edit by hand -->
| P | S | N-i3 | N-x11-all | N-x11-sway | N-harness | N-gap |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1,517 | 20 | 360 | 813 (539 abort causes verified by focused reruns) | 0 | 310 | 735 (188 not yet reviewed) |

i3-suite review: 2,080 non-pass rows; 903 verified, 1,177 unverified, 542 of them unclassified.

Comparable view of sway 1.12 (2,272 rows):

| P | S | N-x11-sway | N-gap | pass | skip | fail | unreached | unstable | flaky |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1,517 | 20 | 0 | 735 | 1,517 | 20 | 564 | 171 | 0 | 0 |

Asymmetries: sway's view and swayward's view share 2,134 rows. 138 rows are in sway's view only, excluded by swayward's labels, and sway passes 20 of them. By swayward's bucket and cause:

- 86 N-x11-all: family: `xwm_kill_client_fallback`
- 21 N-harness: flaky file
- 10 N-i3: family: `i3_open_command`
- 9 N-i3: family: `sway_no_append_layout`
- 6 N-i3: family: `i3_output_selection_semantics`
- 5 N-x11-all: family: `headless_xtest_boundary`
- 1 N-i3: family: `i3_workspace_rename_semantics`

Measured on sway's view, swayward has 1,322 P.
<!-- end i3-suite -->

Sway-sourced `*_finding` families describe where sway differs from i3, and
each names its test file. The one sway IPC state mismatch is a harness artefact: the
`floating_split_on_fresh_workspace_representation` capture was taken outside
the pinned image, with different font metrics. An in-image capture is due at
the next state regeneration.

### swayward (`1fd3c25b`)

| Corpus | Outcome | Raw result |
| --- | --- | --- |
| i3 suite | 1,470 pass / 12 skip / 780 fail / 1,469 unreached / 0 unstable / 24 flaky | [i3 suite](../i3/results/swayward-1fd3c25b.toml) |
| sway IPC state | 4,908 match / 9 mismatch / 0 unstable / 0 not applicable | [sway IPC state](../sway-ipc/results/swayward-1fd3c25b.toml) |
| events | 45 match / 0 mismatch / 0 unstable / 0 not applicable | [events](../sway-ipc/results/swayward-1fd3c25b-events.toml) |
| i3-derived | 4,148 match / 12 mismatch / 0 unstable / 0 not applicable | [i3-derived](../sway-ipc/results/swayward-1fd3c25b-i3-derived.toml) |
| random | 466 match / 34 mismatch / 0 unstable / 0 not applicable / 0 crash | [random](../sway-ipc/results/swayward-1fd3c25b-random.toml) |
| random-v2 | not yet measured | — |
| command fuzz | 195 match / 0 mismatch / 0 not applicable / 0 crash / 0 hang | [command fuzz](../sway-ipc/results/swayward-1fd3c25b-command-fuzz.toml) |
| wire fuzz | 6 match / 4 mismatch / 0 not applicable / 0 crash / 0 hang | [wire fuzz](../sway-ipc/results/swayward-1fd3c25b-wire-fuzz.toml) |

<!-- i3-suite: generated by contrib/i3_buckets.py from the committed results; do not edit by hand -->
| P | S | N-i3 | N-x11-all | N-x11-sway | N-harness | N-gap |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1,470 | 12 | 339 | 836 | 368 | 120 | 610 (70 not yet reviewed) |

i3-suite review: 2,261 non-pass rows; 2,191 verified, 70 unverified, 70 of them unclassified.

Comparable view of swayward `1fd3c25b` (2,460 rows):

| P | S | N-x11-sway | N-gap | pass | skip | fail | unreached | unstable | flaky |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1,470 | 12 | 368 | 610 | 1,470 | 12 | 683 | 295 | 0 | 0 |

Asymmetries: swayward's view and sway's view share 2,134 rows. 326 rows are in swayward's view only, excluded by sway's labels, and swayward passes 148 of them. By sway's bucket and cause:

- 118 N-harness: unstable assertion
- 64 N-harness: unreached, abort cause undetermined
- 49 N-x11-all: abort point decided from the test source: kill disconnects i3test X client
- 26 N-harness: flaky file
- 25 N-i3: family: `i3_open_command`
- 15 N-x11-all: family: `headless_xtest_boundary`
- 12 N-x11-all: abort point decided from the test source: EWMH _NET_MOVERESIZE_WINDOW
- 5 N-x11-all: abort point decided from the test source: EWMH _NET_WM_DESKTOP client message
- 5 N-x11-all: abort point decided from the test source: EWMH _NET_WM_VISIBLE_NAME
- 2 N-harness: abort point decided from the test source: 65,536 sync_with_i3 loop vs settle-poll shim
- 2 N-i3: family: `sway_command_vocabulary`
- 2 N-i3: family: `sway_hidden_scratchpad_floating`
- 1 N-x11-all: abort point decided from the test source: XTEST button press

Measured on swayward's view, sway has 1,497 P.
<!-- end i3-suite -->

### swayfx 0.6 (`fd71a6bd`)

| Corpus | Outcome | Raw result |
| --- | --- | --- |
| i3 suite | not measured | — |
| sway IPC state | 4,916 match / 1 mismatch / 0 unstable / 0 not applicable | [sway IPC state](../sway-ipc/results/swayfx-0.6.toml) |
| events | 45 match / 0 mismatch / 0 unstable / 0 not applicable | [events](../sway-ipc/results/swayfx-0.6-events.toml) |
| i3-derived | not yet measured | — |
| random | 500 match / 0 mismatch / 0 unstable / 0 not applicable / 0 crash | [random](../sway-ipc/results/swayfx-0.6-random.toml) |
| random-v2 | not yet measured | — |
| command fuzz | 195 match / 0 mismatch / 0 not applicable / 0 crash / 0 hang | [command fuzz](../sway-ipc/results/swayfx-0.6-command-fuzz.toml) |
| wire fuzz | 10 match / 0 mismatch / 0 not applicable / 0 crash / 0 hang | [wire fuzz](../sway-ipc/results/swayfx-0.6-wire-fuzz.toml) |

SwayFX is sway 1.12 with visual effects (blur, shadows, rounded corners) built on scenefx. The adapter subclasses sway's with no translations. Its one state mismatch comes from a sway capture taken outside the pinned image, which pinned sway fails too; it is classified as a harness issue in [`sway-ipc/classifications/swayfx-0.6.toml`](../sway-ipc/classifications/swayfx-0.6.toml). Adapter notes: [`sway-ipc/adapters/swayfx.md`](../sway-ipc/adapters/swayfx.md).

### scroll 1.12.21 (`f80c5820`)

| Corpus | Outcome | Raw result |
| --- | --- | --- |
| i3 suite | not measured | — |
| sway IPC state | 3,657 match / 1,260 mismatch / 0 unstable / 0 not applicable | [sway IPC state](../sway-ipc/results/scroll-1.12.21.toml) |
| events | 1 match / 44 mismatch / 0 unstable / 0 not applicable | [events](../sway-ipc/results/scroll-1.12.21-events.toml) |
| i3-derived | not yet measured | — |
| random | 0 match / 499 mismatch / 0 unstable / 0 not applicable / 1 crash | [random](../sway-ipc/results/scroll-1.12.21-random.toml) |
| random-v2 | not yet measured | — |
| command fuzz | 173 match / 22 mismatch / 0 not applicable / 0 crash / 0 hang | [command fuzz](../sway-ipc/results/scroll-1.12.21-command-fuzz.toml) |
| wire fuzz | 10 match / 0 mismatch / 0 not applicable / 0 crash / 0 hang | [wire fuzz](../sway-ipc/results/scroll-1.12.21-wire-fuzz.toml) |

scroll is a sway fork with a scrolling column layout. It removes `split`, `splith`, `splitv`, `splitt` and `layout`, so most tree-shape mismatches are by design. Non-matches are classified in [`sway-ipc/classifications/`](../sway-ipc/classifications/) as a design difference or a deviation, citing scroll's source. The state corpus grew at the beta1 regeneration; its new mismatches are not classified yet and `contrib/validate` counts them as untriaged. Adapter notes: [`sway-ipc/adapters/scroll.md`](../sway-ipc/adapters/scroll.md).

### miracle-wm 0.11.2 (`2df22b0e`)

| Corpus | Outcome | Raw result |
| --- | --- | --- |
| i3 suite | not measured | — |
| sway IPC state | 1,103 match / 2,768 mismatch / 50 unstable / 964 not applicable | [sway IPC state](../sway-ipc/results/miracle-wm-0.11.2.toml) |
| events | 1 match / 44 mismatch / 0 unstable / 0 not applicable | [events](../sway-ipc/results/miracle-wm-0.11.2-events.toml) |
| i3-derived | not yet measured | — |
| random | 0 match / 500 mismatch / 0 unstable / 0 not applicable / 0 crash | [random](../sway-ipc/results/miracle-wm-0.11.2-random.toml) |
| random-v2 | not yet measured | — |
| command fuzz | 24 match / 168 mismatch / 0 not applicable / 3 crash / 0 hang | [command fuzz](../sway-ipc/results/miracle-wm-0.11.2-command-fuzz.toml) |
| wire fuzz | 4 match / 4 mismatch / 0 not applicable / 2 crash / 0 hang | [wire fuzz](../sway-ipc/results/miracle-wm-0.11.2-wire-fuzz.toml) |

miracle-wm is a Mir compositor (not wlroots) that speaks i3/sway IPC and a subset of sway's commands. It has no `GET_CONFIG`, `GET_BAR_CONFIG`, `GET_INPUTS` or `GET_SEATS`, so those requests are not applicable, and no `kill`, so the adapter closes windows from the client side. Non-matches are classified, citing miracle-wm's source; the state corpus's new mismatches since the beta1 regeneration are not classified yet and `contrib/validate` counts them as untriaged. Adapter notes: [`sway-ipc/adapters/miracle-wm.md`](../sway-ipc/adapters/miracle-wm.md).

### swirl (`dc6382f2`)

| Corpus | Outcome | Raw result |
| --- | --- | --- |
| i3 suite | not measured | — |
| sway IPC state | 3,657 match / 1,260 mismatch / 0 unstable / 0 not applicable | [sway IPC state](../sway-ipc/results/swirl-dc6382f2.toml) |
| events | 1 match / 44 mismatch / 0 unstable / 0 not applicable | [events](../sway-ipc/results/swirl-dc6382f2-events.toml) |
| i3-derived | not yet measured | — |
| random | 0 match / 499 mismatch / 0 unstable / 0 not applicable / 1 crash | [random](../sway-ipc/results/swirl-dc6382f2-random.toml) |
| random-v2 | not yet measured | — |
| command fuzz | 173 match / 22 mismatch / 0 not applicable / 0 crash / 0 hang | [command fuzz](../sway-ipc/results/swirl-dc6382f2-command-fuzz.toml) |
| wire fuzz | 10 match / 0 mismatch / 0 not applicable / 0 crash / 0 hang | [wire fuzz](../sway-ipc/results/swirl-dc6382f2-wire-fuzz.toml) |

swirl is a rebrand of scroll 1.12.17 with no tagged release, so its snapshot name carries the commit. Its classifications reuse scroll's where the cause is the same code, citing swirl's source. The state mismatches from scenarios added since the last capture have no classification yet; `contrib/validate` counts them as untriaged. Adapter notes: [`sway-ipc/adapters/swirl.md`](../sway-ipc/adapters/swirl.md).

## Where the review lives

- i3-suite reasons: [`i3/classifications/`](../i3/classifications/), with abort-cause evidence in [`i3/abort-causes/`](../i3/abort-causes/).
- sway IPC reasons: [`sway-ipc/classifications/`](../sway-ipc/classifications/), one file per result.
- Crashes of pinned sway that the corpora avoid or record: [`sway-crashes.md`](sway-crashes.md).
