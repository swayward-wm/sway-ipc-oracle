# Run and read the i3 test oracle

`i3/t/` contains unchanged tests from i3 commit
`9be3249ac5b377ed3270e36bca83df53d8023337`. Keep its [licence and author notice](LICENSE).
[Run the suite](../docs/reproducing.md) or read [adapter setup](../docs/adding-a-compositor.md).

## Check a result file

```sh
./contrib/coverage-report i3/results/sway-1.12.toml --check
```

Each `i3/results/<snapshot>.toml` is raw runner output. `pins.toml` names the
snapshot; `[run]` records the exact compositor commit. `[files]` has an entry
for every vendored `.t` file, and its counts must cover the full plan.

| Field | Meaning |
| --- | --- |
| `assertions` | Authoritative TAP assertion plan from the test |
| `tap_plan` | Captured plan, or `"none"` if none was emitted |
| `pass` | Passing assertions |
| `skip` | One table per skipped assertion |
| `fail` | Assertions that ran and failed |
| `unreached` | Assertions the run did not reach |
| `unstable_assertions` | Assertion numbers that differed across repeated runs; kept raw, excluded from stable counts |
| `flaky = true` | The plan differed or the abort point moved, preventing assertion-level comparison |
| `survived = true` | A zero-assertion crash-regression file reached `1..0` without compositor or test failure; it ran, rather than being skipped |

See [unstable assertions and bucket terms](../docs/results.md#how-to-read-a-block).

## Explain an abort without changing the measurement

`abort-causes/<snapshot>.toml` holds evidence for unverified unreached rows.
Each `[[file]]` is a focused rerun on the pinned compositor in the pinned container:

- It records the committed first unreached assertion, rerun stop point, runner
  exit, and verified cause (`kill`, `xtest`, or `other`).
- It includes TAP and compositor-log excerpts with SHA-256; each excerpt must
  show the signature defined in the file header.
- `contrib/validate` checks the entries against results and classifications.
  Evidence never changes either file.

Validation requires evidence when an unverified file stops at the same first
assertion as swayward's verified kill or XTEST row. It also checks the sway
N-x11-all/N-harness split in `docs/results.md` against that evidence.

Only `kill` or `xtest` moves a file's unverified unreached rows to N-x11-all;
other rows stay N-harness. [Result terms](../docs/results.md#how-to-read-a-block) define both buckets.

## Review a skip or update a test

- A skip is a measured difference. Name the assertion, reason and i3 or sway
  source line; use it only when the compositor cannot or deliberately does
  not satisfy the premise. Keep `fail` or `unreached` until reviewed.
- Never edit `i3/t/` to make a failure pass. Record X11 or process-lifecycle
  limits rather than changing assertions. Follow the [adapter and skip rules](../CONTRIBUTING.md#keep-test-rules-the-same-for-every-compositor).
- Before accepting a test update, compare it with upstream `testcases/t/`
  at the pinned i3 revision. `unvendored.toml` records missing upstream files
  and reasons, so a partial set cannot be presented as the whole suite.
