# Glossary

The words used on the [results page](results.md) and in the result files.
This page is the one place that defines them; other pages link here.

## Sources and corpora

- **Oracle.** The reference answers: i3's unchanged test suite, and the IPC
  replies recorded from pinned sway 1.12.
- **Pin.** The exact source commit of each compositor, in
  [`pins.toml`](../pins.toml). The runners refuse a dirty build or another
  commit.
- **Snapshot.** What one pinned compositor did against the oracle: its result
  files, named in `pins.toml` under `[snapshot]` (for example `sway-1.12`).
  Raw runner output, not edited by hand ([one exception](../CONTRIBUTING.md)).
- **Corpus.** One set of inputs with its own runner and result file: the i3
  suite, sway IPC state, events, i3-derived, random, random-v2, command fuzz
  and wire fuzz. [Running the oracle](running.md) describes each.
- **i3-derived.** Window-tree states that i3's own tests reach, recorded on
  sway and replayed on other compositors. They are captured, not hand-written.
- **Adapter.** The small layer that starts a compositor headless and
  translates a test's config into its own config language. It never changes
  an assertion. To keep a test's premise it may also translate some values in
  IPC replies and events: the sway and swayward i3-suite adapters map
  headless output names back to i3's `fake-N`, and swayward's returns the
  source config path from `GET_VERSION`. The
  [sway](../i3/adapters/sway/README.md) and
  [swayward](../i3/adapters/swayward/README.md) adapter READMEs describe the
  main translations; the adapter code is the full record.
- **Adapted.** A row whose premise the adapter translated, for example i3's
  fake outputs into headless outputs. Each adapter's README lists its rules.

## Runs and the harness

- **Harness.** The runners, adapters, containers and test clients around a
  compositor. A harness problem (a timeout, the memory cap, a client that
  failed to start) is reported apart from compositor results.
- **Canary.** One of five i3 test files (`003-ipc.t`, `115-ipc-workspaces.t`,
  `126-regress-close.t`, `134-invalid-command.t`, `139-ws-numbers.t`) that
  pass completely on i3, sway and swayward. An i3-suite reproduction runs them
  first and stops if one does not pass: the harness is broken, not the compositor.
- **Seed.** The number that fixes a random command sequence: the same seed
  and generator give the same commands against the same compositor state.
- **Delta debugging.** Shortening a command list that shows a crash or a
  difference by removing commands, keeping each shorter list only if it still
  shows the same result.

## Outcomes

i3-suite assertions:

- **Pass, skip, fail.** As reported by the test's TAP output. A skip is one
  the i3 test itself declares.
- **Unreached.** The test file stopped before this assertion ran, often
  because an earlier step needs X11 behaviour the compositor lacks.
- **Unstable.** Outside flaky files, the assertion's outcome changed between
  repeated harness runs ([`i3/unstable.toml`](../i3/unstable.toml)). It stays
  visible but out of the stable counts, and is not a compositor verdict.
- **Flaky.** The whole file's TAP plan or abort point changed between runs
  ([`i3/flaky.toml`](../i3/flaky.toml)), so every assertion in it is set aside.

Sway IPC rows:

- **Match, mismatch.** The reply equals sway's after the rules in
  [`normalize.toml`](../sway-ipc/normalize.toml), or it does not. i3 rows say
  **differs** instead, because i3's protocol lacks sway's extensions.
- **Not applicable.** The request, field or scenario does not apply to that
  compositor: it has no such request, or the field is a sway extension
  ([`applicability.toml`](../sway-ipc/applicability.toml)).
- **Crash, hang.** In committed snapshots, a crash means the compositor
  exited. Hang appears only in the fuzz corpora, for a compositor that is
  still running but no longer answers `GET_VERSION`. Both are counted apart
  from mismatches. The developer-only
  [`differential` runner](running.md#random-v3-state-aware)
  does not commit its results, and it also calls a live compositor that stops
  answering IPC a crash.
- **Unstable.** A mismatch or crash row that changed on an immediate rerun on
  a fresh compositor, or any row that differs between the two runs of a
  [release-candidate regeneration](reproducing.md#release-candidate-regeneration).
- **†.** The figure comes from a result listed in
  [`pending.toml`](../pending.toml): an input changed since it was measured,
  and it waits for the next regeneration. It is the last measured value.

## Review

- **Classification.** A human review of one non-pass, kept beside the raw
  result and never inside it. The [results page](results.md#where-the-review-lives)
  says where each corpus keeps them.
- **Reason, family.** Why a row differs. A family is a named reason shared by
  many rows, defined once under `[families]` in the classification file.
- **Verified, unverified, unclassified.** A row is verified when its
  classification has `reason_verified = true`: it names a reviewed family or
  cites its source. Any row with `reason_verified = false` is unverified. In
  the committed classifications that covers three kinds: a provisional note
  such as "the pinned run emitted no TAP plan", the reason `unclassified`, and
  one sway `upstream_skip` row (`313-include.t` assertion 19).
- **Not yet reviewed.** A fail whose reason is still `unclassified` or that
  provisional no-TAP note. The N-gap cell counts these per compositor.
- **Finding.** A verified difference that the review keeps as evidence
  (families ending in `_finding`). A sway finding says what sway does
  differently from i3, not what sway should do.
- **Triage** (sway IPC rows). One label per classified mismatch:

  | Compositor | Triage labels |
  | --- | --- |
  | swayward | swayward bug (naming its open task), documented deviation (citing its [KNOWN_DEVIATIONS](https://github.com/swayward-wm/swayward/blob/main/docs/KNOWN_DEVIATIONS.md) anchor), harness issue (with evidence) |
  | any other | design difference (behaviour the compositor documents or builds on purpose), deviation (an undocumented difference from sway), harness issue; each cites the compositor's source at its pin |

  An **untriaged** mismatch has no classification yet.

## Buckets

Buckets sort every i3-suite assertion into exactly one class by what the
result means. [`contrib/i3_buckets.py`](../contrib/i3_buckets.py) holds the
rules and generates each block's bucket table on the results page.

| Bucket | Meaning |
| --- | --- |
| P | Pass. |
| S | Upstream skip: the i3 test itself skips it. |
| N-i3 | Tests an i3-only premise, so only i3 can pass it. |
| N-x11-all | An X11 premise that neither measured Wayland stack meets (sway 1.12's wlroots XWM, swayward's xwayland-satellite). This says nothing about what another XWM could do. |
| N-x11-sway | X11 metadata that swayward cannot receive through xwayland-satellite, while sway's in-process XWM sees it. |
| N-harness | A measurement artefact: flaky files, unstable assertions, and unreached assertions whose abort cause neither the source nor a focused rerun ([`i3/abort-causes/`](../i3/abort-causes/)) shows. |
| N-gap | A comparable non-pass: reviewed findings, fails not yet reviewed, and declared deviations. |

- **Comparable view.** The assertions whose bucket, for that compositor, is
  not N-i3, N-x11-all or N-harness. Each compositor's own labels decide what
  it excludes, so views have different denominators. No view is the fair one.
- **Asymmetries.** The rows in one compositor's view that the other
  compositor's labels exclude from its own view.
