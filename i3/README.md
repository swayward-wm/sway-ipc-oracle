# i3 test oracle

`i3/t/` contains unchanged files from i3 commit `9be3249ac5b377ed3270e36bca83df53d8023337`. Compare a file with `testcases/t/` at that revision before accepting an update. The original licence and author notice are in [`LICENSE`](LICENSE).

## Result schema

A result file has a `[files]` entry for every vendored `.t` file. Each entry records:

- `assertions`: the test's authoritative TAP plan.
- `tap_plan`: the plan captured from the run, or `"none"` if the test emitted no plan.
- `pass`: the number of passing assertions.
- `skip`: one table per skipped assertion.
- `fail`: assertions that ran and did not pass.
- `unreached`: assertions the run did not reach.
- `unstable_assertions`: assertion numbers whose outcomes differed between
  repeated runs. They remain in the raw result but are omitted from stable
  pass/skip/fail counts.
- `flaky = true`: the file's TAP plan differed between runs or the file aborted
  at a different point, so assertion-level comparison is not valid.
- `survived = true`: a zero-assertion crash-regression file reached its `1..0`
  plan without the compositor or test process failing. This is distinct from a
  file-level skip: the test ran and its survival condition passed.

Each result is `i3/results/<snapshot>.toml`, named in `pins.toml` `[snapshot]`; for example, `i3/results/sway-1.12.toml` is the i3 suite run on sway 1.12. The exact commit is in the file's `[run]` section. The counts must cover the full plan. Run `contrib/coverage-report i3/results/<snapshot>.toml --check` to validate a file.

## Abort-cause evidence

`abort-causes/<snapshot>.toml` records why unreached assertions stopped, for
rows whose classification is unverified. Each `[[file]]` entry is one focused
rerun of that test file on the pinned compositor in the pinned container. It
records the committed first unreached assertion, where the rerun stopped, the
runner exit code, the verified `cause` (`kill`, `xtest`, or `other`), and an
excerpt of the TAP and compositor log at the abort with its SHA-256. The file
header defines each cause's signature. `contrib/validate` checks the entries
against the committed result and classification. Bucket rules move a file's
unverified unreached rows to N-x11-all only for a `kill` or `xtest` cause; any
other row stays N-harness. Evidence never edits results or classifications.

## Skip policy

A skip is a measured difference, not a hidden failure. Each skip names the assertion, gives a reason, and cites the relevant i3 or sway source line. Use a skip only when the compositor cannot or deliberately does not satisfy the test's premise. Keep a failed or unreached assertion as `fail` or `unreached` until the reason has been checked.

Do not edit `i3/t/` to turn a failure into a pass. If an adapter cannot establish an X11 or process-lifecycle premise, record that limit in the result instead of changing the assertion.

`unvendored.toml` records upstream test files that are not present and why. It prevents a partial vendored set from being presented as the complete i3 suite.
