# Results

One block per measured compositor: what it did against the oracle at its
pinned commit, with a link to every raw result file. No table holds more than
one compositor, and nothing here is a score or a ranking.

The [glossary](glossary.md) defines terms such as N-gap, unstable or
comparable view.

## Read a result for your tool

Find your compositor's block. Its **sway IPC state by request** table counts
how often each request's reply matched sway's. In a linked raw result, each
mismatch row's `differences` reads sway's value left, the compositor's right:

```toml
# sway-ipc/results/scroll-1.12.21.toml
scenario = "empty"
request = "workspaces"
verdict = "mismatch"
differences = ["$workspaces[0].layout: 'splitv' != 'vertical'"]
```

Then read why. A mismatch can be a bug, a deliberate design, or a harness
issue; the [classifications](#where-the-review-lives) say which, citing source.

This row is a `design difference` in
[scroll's classifications](../sway-ipc/classifications/scroll-1.12.21.toml)
(`scroll-column-layout`): scroll reports its columns that way on purpose.

[`normalize.toml`](../sway-ipc/normalize.toml) lists, with reasons, what is
never compared exactly: ids, output names, rectangles within 10 px. Do not
rely on those being equal across compositors either.

## Snapshots

Every block sorts the same 3,755 assertions of the i3 suite and the same sway
IPC corpora, so a figure means the same thing in every block.

- † marks figures from results listed in [`pending.toml`](../pending.toml):
  they are the last measured values and wait for the next regeneration.
- [swayward], where the oracle began, is an i3/sway-compatible compositor in
  Rust on Smithay. Its X11 clients go through [xwayland-satellite], a separate
  Xwayland bridge, where sway has its own X11 window manager.
- `not measured`: the i3 suite has not been run against SwayFX, scroll,
  miracle-wm or swirl yet.
- `contrib/tests/readme-snapshots` checks every figure on this page against
  the committed result files.

[swayward]: https://github.com/swayward-wm/swayward
[xwayland-satellite]: https://github.com/Supreeeme/xwayland-satellite

### How to read a block

The corpus table has one row per corpus. [Running the oracle](running.md)
describes how each runs.

- **i3 suite.** Every one of the 3,755 assertions in the 242 test files has
  exactly one [outcome](glossary.md#outcomes). Unstable and flaky are
  harness-timing measures, not compositor verdicts.
- **Sway IPC state** replays 365 scenarios (482 captures, 97 probes) against
  sway 1.12's replies: 365 of the 371 hand-written ones; 6 run only as events.
  Rows are keyed by capture or probe name, so the result names 559 scenarios.
- **Events** replays 36 scenarios (45 captures) with a subscription to all
  nine sway event families and compares the ordered event stream.
- **i3-derived** replays 416 distinct states reached by i3's unchanged test
  suite.
- **Random** replays 500 captured 20-step sequences, one verdict per seed.
- **Random v2** replays 1,000 captured 20-step sequences from a wider
  [vocabulary](../sway-ipc/random-v2/vocabulary.json), one verdict per seed.
  Random v1 is unchanged, so its figures stay comparable.
- **Command fuzz** (malformed commands) and **wire fuzz** (broken IPC framing)
  replay sway 1.12 captures at the fixed CI budget. Crash and hang count
  compositor health, apart from mismatch.

Unstable sway IPC rows changed between runs ([glossary](glossary.md#outcomes)).
[`command-coverage.toml`](../sway-ipc/command-coverage.toml) records which
of sway 1.12's 90 top-level commands are exercised, and why the rest are not.

`contrib/i3_buckets.py` generates two regions under the corpus table from the
committed results: the state table by request and, where the i3 suite ran, the
i3-suite region. `contrib/validate` fails if either is edited by hand.

- **Sway IPC state by request.** The sway IPC state row, split by request.
  `RUN_COMMAND`, one probe, is a single command's reply, compared alone.
- **Command log up to a capture.** Per capture, the list of replies logged since
  the scenario began, probes excluded. Fixture-client actions and i3's window
  opens log a reply the adapter writes, not one from the compositor.
- **i3 rows.** They read differs, not mismatch: i3 lacks sway's extensions. A
  reply compared without those fields adds a not applicable row naming them, so
  a request can have more rows than captures.
- **Bucket table.** Sorts the same 3,755 i3-suite assertions by what each
  result means ([buckets](glossary.md#buckets)). Many of sway's non-passes are
  deliberate: sway is a Wayland compositor, and many i3 tests assume X11.
- **Review line.** How many non-pass rows in `i3/classifications/` are
  [verified](glossary.md#review). Every stable non-pass has a row, but not
  every row is reviewed yet.
- **Comparable view.** The rows this compositor's own labels keep. Views have
  different denominators, so each is shown only in its own block. No view is
  the fair one.
- **Asymmetries.** The rows that one compositor's view keeps and the other's
  excludes.

Sway IPC mismatches are [triaged](glossary.md#review) in
`sway-ipc/classifications/`, one file per result. `contrib/validate` prints
the untriaged count per corpus, as in `state 0 of 32; 2 unstable`.

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

<!-- sway-ipc-state: generated by contrib/i3_buckets.py from the committed results; do not edit by hand -->
Sway IPC state by request:

| Request | match | differs | unstable | not applicable |
| --- | ---: | ---: | ---: | ---: |
| `GET_VERSION` | 440 | 0 | 0 | 479 |
| `GET_BINDING_MODES` | 0 | 440 | 0 | 39 |
| `GET_BINDING_STATE` | 440 | 0 | 0 | 39 |
| `GET_INPUTS` | 0 | 0 | 0 | 479 |
| `GET_SEATS` | 0 | 0 | 0 | 479 |
| `GET_OUTPUTS` | 0 | 440 | 0 | 479 |
| `GET_MARKS` | 433 | 7 | 0 | 39 |
| `GET_WORKSPACES` | 378 | 62 | 0 | 479 |
| `GET_TREE` | 0 | 440 | 0 | 479 |
| `RUN_COMMAND`, one probe | 41 | 55 | 0 | 0 |
| Command log up to a capture | 13 | 427 | 0 | 62 |
<!-- end sway-ipc-state -->

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

The i3 suite was written for i3, so this view is the suite's own baseline,
not a measure of sway compatibility.

Random has not been replayed against i3: all 500 seeds are not applicable.
Its runner first sets outputs to 1280x720 with `output * mode --custom`, which
i3 rejects as a parse error. The result file gives the cause.

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

<!-- sway-ipc-state: generated by contrib/i3_buckets.py from the committed results; do not edit by hand -->
Sway IPC state by request:

| Request | match | mismatch | unstable | not applicable |
| --- | ---: | ---: | ---: | ---: |
| `GET_VERSION` | 482 | 0 | 0 | 0 |
| `GET_BINDING_MODES` | 482 | 0 | 0 | 0 |
| `GET_BINDING_STATE` | 482 | 0 | 0 | 0 |
| `GET_INPUTS` | 482 | 0 | 0 | 0 |
| `GET_SEATS` | 482 | 0 | 0 | 0 |
| `GET_OUTPUTS` | 482 | 0 | 0 | 0 |
| `GET_MARKS` | 482 | 0 | 0 | 0 |
| `GET_WORKSPACES` | 482 | 0 | 0 | 0 |
| `GET_TREE` | 481 | 1 | 0 | 0 |
| `RUN_COMMAND`, one probe | 97 | 0 | 0 | 0 |
| Command log up to a capture | 482 | 0 | 0 | 0 |
<!-- end sway-ipc-state -->

<!-- i3-suite: generated by contrib/i3_buckets.py from the committed results; do not edit by hand -->
| P | S | N-i3 | N-x11-all | N-x11-sway | N-harness | N-gap |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1,517 | 20 | 387 | 813 (539 abort causes verified by focused reruns) | 0 | 312 | 706 |

i3-suite review: 2,080 non-pass rows; 1,091 verified, 989 unverified, 360 of them unclassified.

Comparable view of sway 1.12 (2,243 rows):

| P | S | N-x11-sway | N-gap | pass | skip | fail | unreached | unstable | flaky |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1,517 | 20 | 0 | 706 | 1,517 | 20 | 535 | 171 | 0 | 0 |

Asymmetries: sway's view and swayward's view share 2,114 rows. 129 rows are in sway's view only, excluded by swayward's labels, and sway passes 20 of them. By swayward's bucket and cause:

- 86 N-x11-all: family: `xwm_kill_client_fallback`
- 21 N-harness: flaky file
- 10 N-i3: family: `i3_open_command`
- 6 N-i3: family: `i3_output_selection_semantics`
- 5 N-x11-all: family: `headless_xtest_boundary`
- 1 N-i3: family: `i3_workspace_rename_semantics`

Measured on sway's view, swayward has 1,320 P.
<!-- end i3-suite -->

Sway's `*_finding` families are verified differences from i3, and each row
names its test file.

The one state mismatch is a harness artefact: the capture
`floating_split_on_fresh_workspace_representation` was taken outside the
pinned image, with other font metrics. The next state regeneration redoes it.

Zero sway crashes in the replayed sway IPC corpora (state to wire fuzz) is
expected: they replay inputs captured from this sway build. The [four sway
crashes](sway-crashes.md) came from live exploration of new random sequences.

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

<!-- sway-ipc-state: generated by contrib/i3_buckets.py from the committed results; do not edit by hand -->
Sway IPC state by request:

| Request | match | mismatch | unstable | not applicable |
| --- | ---: | ---: | ---: | ---: |
| `GET_VERSION` | 482 | 0 | 0 | 0 |
| `GET_BINDING_MODES` | 482 | 0 | 0 | 0 |
| `GET_BINDING_STATE` | 482 | 0 | 0 | 0 |
| `GET_INPUTS` | 482 | 0 | 0 | 0 |
| `GET_SEATS` | 482 | 0 | 0 | 0 |
| `GET_OUTPUTS` | 481 | 1 | 0 | 0 |
| `GET_MARKS` | 482 | 0 | 0 | 0 |
| `GET_WORKSPACES` | 480 | 2 | 0 | 0 |
| `GET_TREE` | 476 | 6 | 0 | 0 |
| `RUN_COMMAND`, one probe | 97 | 0 | 0 | 0 |
| Command log up to a capture | 482 | 0 | 0 | 0 |
<!-- end sway-ipc-state -->

<!-- i3-suite: generated by contrib/i3_buckets.py from the committed results; do not edit by hand -->
| P | S | N-i3 | N-x11-all | N-x11-sway | N-harness | N-gap |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1,470 | 12 | 339 | 836 | 368 | 120 | 610 (70 not yet reviewed) |

i3-suite review: 2,261 non-pass rows; 2,191 verified, 70 unverified, 70 of them unclassified.

Comparable view of swayward `1fd3c25b` (2,460 rows):

| P | S | N-x11-sway | N-gap | pass | skip | fail | unreached | unstable | flaky |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1,470 | 12 | 368 | 610 | 1,470 | 12 | 683 | 295 | 0 | 0 |

Asymmetries: swayward's view and sway's view share 2,114 rows. 346 rows are in swayward's view only, excluded by sway's labels, and swayward passes 150 of them. By sway's bucket and cause:

- 118 N-harness: unstable assertion
- 64 N-harness: unreached, abort cause undetermined
- 49 N-x11-all: abort point decided from the test source: kill disconnects i3test X client
- 27 N-i3: family: `i3_open_command`
- 26 N-harness: flaky file
- 15 N-x11-all: family: `headless_xtest_boundary`
- 12 N-x11-all: abort point decided from the test source: EWMH _NET_MOVERESIZE_WINDOW
- 6 N-i3: family: `sway_config_include_ipc`
- 5 N-i3: family: `sway_mark_workspace_rejected`
- 5 N-x11-all: abort point decided from the test source: EWMH _NET_WM_DESKTOP client message
- 5 N-x11-all: abort point decided from the test source: EWMH _NET_WM_VISIBLE_NAME
- 4 N-i3: family: `sway_command_vocabulary`
- 2 N-harness: abort point decided from the test source: 65,536 sync_with_i3 loop vs settle-poll shim
- 2 N-i3: family: `sway_criteria_vocabulary`
- 2 N-i3: family: `sway_hidden_scratchpad_floating`
- 1 N-harness: family: `sway_adapter_scratch_lookup`
- 1 N-harness: family: `sway_adapter_sync_latency`
- 1 N-i3: family: `sway_config_text`
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

<!-- sway-ipc-state: generated by contrib/i3_buckets.py from the committed results; do not edit by hand -->
Sway IPC state by request:

| Request | match | mismatch | unstable | not applicable |
| --- | ---: | ---: | ---: | ---: |
| `GET_VERSION` | 482 | 0 | 0 | 0 |
| `GET_BINDING_MODES` | 482 | 0 | 0 | 0 |
| `GET_BINDING_STATE` | 482 | 0 | 0 | 0 |
| `GET_INPUTS` | 482 | 0 | 0 | 0 |
| `GET_SEATS` | 482 | 0 | 0 | 0 |
| `GET_OUTPUTS` | 482 | 0 | 0 | 0 |
| `GET_MARKS` | 482 | 0 | 0 | 0 |
| `GET_WORKSPACES` | 482 | 0 | 0 | 0 |
| `GET_TREE` | 481 | 1 | 0 | 0 |
| `RUN_COMMAND`, one probe | 97 | 0 | 0 | 0 |
| Command log up to a capture | 482 | 0 | 0 | 0 |
<!-- end sway-ipc-state -->

SwayFX is sway 1.12 with blur, shadows and rounded corners, drawn by
[scenefx](https://github.com/wlrfx/scenefx), a replacement wlroots scene
renderer. Its adapter is sway's, changing only the build check
([notes](../sway-ipc/adapters/swayfx.md)).

The one state mismatch is that same out-of-image sway capture, which pinned
sway fails too: a [harness issue](../sway-ipc/classifications/swayfx-0.6.toml).

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

<!-- sway-ipc-state: generated by contrib/i3_buckets.py from the committed results; do not edit by hand -->
Sway IPC state by request:

| Request | match | mismatch | unstable | not applicable |
| --- | ---: | ---: | ---: | ---: |
| `GET_VERSION` | 482 | 0 | 0 | 0 |
| `GET_BINDING_MODES` | 482 | 0 | 0 | 0 |
| `GET_BINDING_STATE` | 482 | 0 | 0 | 0 |
| `GET_INPUTS` | 482 | 0 | 0 | 0 |
| `GET_SEATS` | 482 | 0 | 0 | 0 |
| `GET_OUTPUTS` | 458 | 24 | 0 | 0 |
| `GET_MARKS` | 478 | 4 | 0 | 0 |
| `GET_WORKSPACES` | 0 | 482 | 0 | 0 |
| `GET_TREE` | 0 | 482 | 0 | 0 |
| `RUN_COMMAND`, one probe | 68 | 29 | 0 | 0 |
| Command log up to a capture | 243 | 239 | 0 | 0 |
<!-- end sway-ipc-state -->

scroll is a sway fork with a scrolling column layout. It removes `split`,
`splith`, `splitv`, `splitt` and `layout`, so most tree-shape mismatches are
by design. Classified rows cite scroll's source.

The state corpus grew at the beta1 regeneration. Its new mismatches are not
classified yet, and `contrib/validate` counts them as untriaged.
[Adapter notes](../sway-ipc/adapters/scroll.md).

### miracle-wm 0.11.2 (`2df22b0e`)

| Corpus | Outcome | Raw result |
| --- | --- | --- |
| i3 suite | not measured | — |
| sway IPC state | 1,103 match / 2,768 mismatch / 50 unstable / 964 not applicable / 32 crash | [sway IPC state](../sway-ipc/results/miracle-wm-0.11.2.toml) |
| events | 1 match / 44 mismatch / 0 unstable / 0 not applicable | [events](../sway-ipc/results/miracle-wm-0.11.2-events.toml) |
| i3-derived | not yet measured | — |
| random | 0 match / 500 mismatch / 0 unstable / 0 not applicable / 0 crash | [random](../sway-ipc/results/miracle-wm-0.11.2-random.toml) |
| random-v2 | not yet measured | — |
| command fuzz | 24 match / 168 mismatch / 0 not applicable / 3 crash / 0 hang | [command fuzz](../sway-ipc/results/miracle-wm-0.11.2-command-fuzz.toml) |
| wire fuzz | 4 match / 4 mismatch / 0 not applicable / 2 crash / 0 hang | [wire fuzz](../sway-ipc/results/miracle-wm-0.11.2-wire-fuzz.toml) |

<!-- sway-ipc-state: generated by contrib/i3_buckets.py from the committed results; do not edit by hand -->
Sway IPC state by request:

| Request | match | mismatch | unstable | not applicable | crash |
| --- | ---: | ---: | ---: | ---: | ---: |
| `GET_VERSION` | 0 | 478 | 0 | 0 | 4 |
| `GET_BINDING_MODES` | 0 | 478 | 0 | 0 | 4 |
| `GET_BINDING_STATE` | 478 | 0 | 0 | 0 | 4 |
| `GET_INPUTS` | 0 | 0 | 0 | 482 | 0 |
| `GET_SEATS` | 0 | 0 | 0 | 482 | 0 |
| `GET_OUTPUTS` | 0 | 475 | 3 | 0 | 4 |
| `GET_MARKS` | 466 | 8 | 4 | 0 | 4 |
| `GET_WORKSPACES` | 0 | 469 | 9 | 0 | 4 |
| `GET_TREE` | 0 | 446 | 32 | 0 | 4 |
| `RUN_COMMAND`, one probe | 40 | 56 | 1 | 0 | 0 |
| Command log up to a capture | 119 | 358 | 1 | 0 | 4 |
<!-- end sway-ipc-state -->

miracle-wm is a Mir compositor (not wlroots) that speaks i3/sway IPC and a
subset of sway's commands. Classified rows cite miracle-wm's source.

- No `GET_CONFIG`, `GET_BAR_CONFIG`, `GET_INPUTS` or `GET_SEATS`: those
  requests are not applicable.
- No `kill`: the adapter closes windows from the client side.
- State mismatches new since the beta1 regeneration are not classified yet;
  `contrib/validate` counts them as untriaged.

[Adapter notes](../sway-ipc/adapters/miracle-wm.md).

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

<!-- sway-ipc-state: generated by contrib/i3_buckets.py from the committed results; do not edit by hand -->
Sway IPC state by request:

| Request | match | mismatch | unstable | not applicable |
| --- | ---: | ---: | ---: | ---: |
| `GET_VERSION` | 482 | 0 | 0 | 0 |
| `GET_BINDING_MODES` | 482 | 0 | 0 | 0 |
| `GET_BINDING_STATE` | 482 | 0 | 0 | 0 |
| `GET_INPUTS` | 482 | 0 | 0 | 0 |
| `GET_SEATS` | 482 | 0 | 0 | 0 |
| `GET_OUTPUTS` | 458 | 24 | 0 | 0 |
| `GET_MARKS` | 478 | 4 | 0 | 0 |
| `GET_WORKSPACES` | 0 | 482 | 0 | 0 |
| `GET_TREE` | 0 | 482 | 0 | 0 |
| `RUN_COMMAND`, one probe | 68 | 29 | 0 | 0 |
| Command log up to a capture | 243 | 239 | 0 | 0 |
<!-- end sway-ipc-state -->

swirl is a rebrand of scroll 1.12.17 with no tagged release, so its snapshot
name carries the commit. Its classifications reuse scroll's where the code is
the same, citing swirl's source.

State mismatches from scenarios added since the last capture are not
classified yet; `contrib/validate` counts them as untriaged.
[Adapter notes](../sway-ipc/adapters/swirl.md).

## Where the review lives

Reviews sit beside the raw results and never inside them.

| Corpus | Review files | Keyed by |
| --- | --- | --- |
| i3 suite | [`i3/classifications/`](../i3/classifications/), abort causes in [`i3/abort-causes/`](../i3/abort-causes/) | file and assertion |
| sway IPC | [`sway-ipc/classifications/`](../sway-ipc/classifications/), one file per result | case (fuzz), seed (random), scenario and request (state, events, i3-derived) |

- **i3-suite rows.** A verified row names a reviewed family or cites its
  source. The [review rules](glossary.md#review) define the rest.
- **sway IPC rows.** Each carries a [triage](glossary.md#review), a finding,
  a reason and a source. `contrib/validate` rejects a classification that
  names no measured mismatch, or names an unstable row.
- **`[basis]` table.** Names a newer, unpinned measurement that a review
  used. Mismatches that matched there are listed in it instead of classified.

[Pinned sway crashes](sway-crashes.md) lists the crashes of sway 1.12 that
the corpora record or avoid.
