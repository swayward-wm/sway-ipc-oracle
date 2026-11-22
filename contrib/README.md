# Contributor tools

## Check a change or choose a runner

```sh
./contrib/validate
```

For a first run, use the [quickstart](../docs/start.md). Before changing
measurements or classifications, read the [contribution rules](../CONTRIBUTING.md).

The tables list every file directly in `contrib/` except this README;
validation checks the inventory.

## Measure a compositor or check a sway PR

| Script | Purpose and inputs or outputs | Who runs it | Why separate |
| --- | --- | --- | --- |
| `i3-suite-run` | Runs the unchanged i3 suite against i3, sway or swayward; writes `i3/results/<snapshot>.toml`, named by `pins.toml`. Owns the TAP parser and its self-test. | Maintainers refreshing evidence; CI runs only `--self-test` | Uses the upstream Perl harness and adapters, rather than Wayland scenario data. |
| `sway-ipc-run` | Runs, captures or compares IPC scenarios; reads scenario and normalization TOML, writes fixtures or result TOML. See [running](../docs/running.md). | Maintainers refreshing fixtures; contributors investigating differences | Owns compositor lifecycle and raw IPC, separate from the i3 suite. |
| `pr-check` | Explores random-v3 command sequences on a user's head sway build, replays crashes on head and base, and reduces new crashes. See the [options, reports and limits](../docs/pr-check.md). | Sway contributors checking a branch | Uses unpinned binaries and reports per side, rather than measuring published pins. |
| `regenerate-rc` | Repins one swayward commit, builds the image, recaptures i3-derived inputs, and refreshes pending and swayward results. See [release-candidate regeneration](../docs/reproducing.md#release-candidate-regeneration) for dry runs, two-run agreement, unstable rows and `target/rc/<sha8>/evidence.log`. | Maintainer once per milestone (T4) | Drives Podman on the host and composes runners; `validate reproduce` runs one snapshot inside a container. |

### Inspect pr-check's machine-readable output

`run.json` records measured provenance of both binaries. `results.jsonl` has
one row per explored seed: symbolic, resolved and sent commands, and the outcome
(`survived`, `crashed` or `harness`). Per-seed directories hold logs and settled observations.

Each crashed seed adds a judgment row after two replays on each side: new,
pre-existing, blocked, unconfirmed or harness; unjudged if the budget ran out.
Base-explored seeds use the same rules with sides swapped; base-only crashes are fixed.

New crashes go in `new-<n>/`. Script states include `needs-fixture` (a step
needs the fixture client) and `unminimised` (out of time). See
[how to read the report](../docs/pr-check.md#reading-the-report) for the other states.

With `--diffs`, each survived head seed is also replayed once on base. First
behaviour differences are grouped by causing command (the subcommand for a
reply difference) and path, and one seed per group is minimised into
`diff-<n>/` with the exact first-difference path as the predicate. They never change the exit code.

## Review results or check their inputs

| Script | Purpose and inputs or outputs | Who runs it | Why separate |
| --- | --- | --- | --- |
| `coverage-report` | Checks one `i3/results/<snapshot>.toml` or prints its summary, gaps or JSON. | CI through `validate`; contributors classifying results | Read-only validation; `i3-suite-run` executes compositors and writes measurements. |
| `i3_buckets.py` | Partitions assertions into [buckets](../docs/glossary.md) using results, classifications, `i3/unstable.toml` and `i3/abort-causes/`; renders the generated i3-suite regions in `docs/results.md`, and the per-request tables of each sway IPC state result. | `readme-snapshots` through `validate`; maintainers after result or classification edits | Interpretation stays outside runners and raw-result validation. Use the [review command](../CONTRIBUTING.md#review-an-i3-result). |
| `provenance.py` | Lists tracked result inputs and hashes their contents into `inputs`. See [when restamping is allowed](../CONTRIBUTING.md#resolve-a-stale-input-hash). | Both runners, `validate`; maintainers restamping | All three share one definition of inputs. |
| `sway_ipc_triage.py` | Checks result and classification coverage for every sway-IPC corpus of pinned swayward (state, events, random, i3-derived, command fuzz, wire fuzz); rejects classifications of unmeasured mismatches and reports untriaged counts and unstable rows. | `validate`; `tests/sway-ipc-triage` | Shared with its negative test, which deletes each result and classification in turn. |
| `check-sway-fixture-schema` | Takes a pinned sway checkout; compares its serializer fields with checked-in fixture fields and reports mismatches. | CI through `validate`; maintainers updating fixtures | Needs source; the scenario runner observes only IPC. |
| `validate` | Checks results, fixture schema, inventories and self-tests; `reproduce` regenerates snapshots in the pinned container. | CI and contributors before pushing or refreshing evidence | One entry point, using domain checks that contributors can also run directly. |

## Work on generators or fixture clients

| File | Purpose and inputs or outputs | Who uses it | Why separate |
| --- | --- | --- | --- |
| `sway_ipc_v3.py` | Generates commands from stable tree/workspace features, vocabulary weights, state multipliers, preconditions and recipes in `sway-ipc/random-v3/`; resolves symbolic `@con:` IDs per compositor. | `sway-ipc-run differential`, `random --capture --generator v3`; `fuzz-self-test` | Pure state-to-command logic with its own self-test, separate from lifecycle and IPC. |
| `foreign-toplevel-request.c` | Sends `set_minimized`, `unset_minimized`, `set_maximized` or `unset_maximized` to a toplevel by app_id; exits when handled. The runner compiles it against protocol XML in `protocols/`, vendored from pinned wlroots. | `sway-ipc-run` for `foreign_toplevel:` actions | Taskbar requests have no IPC equivalent; sway and swayward need identical protocol input. |
| `xdg-toplevel-fixture.c` | Maps an xdg toplevel with minimum/maximum sizes and an optional parent; the runner compiles it with pinned Wayland development packages. | `sway-ipc-run` for default-floating scenarios | Foot cannot set xdg-shell hints or a parent; sway and swayward need identical protocol input. |

Directories are not inventory rows:

- `prcheck/` implements `pr-check`; the script imports it and
  `prcheck/__init__.py` lists its modules.
- `tests/` contains tests called only by `validate`.
- `protocols/` holds Wayland protocol XML vendored unchanged from pinned wlroots.

Do not put Python bytecode or other generated files in `contrib/`.
