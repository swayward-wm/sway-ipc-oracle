# Contributing to sway-ipc-oracle

## Check your change

```sh
./contrib/validate
```

This must pass before every push. For a first measurement, use the
[quickstart](docs/start.md); for maintenance tools, see [contrib/](contrib/README.md).

The rules below keep snapshots reproducible: a pinned-container rerun should
recover the committed measurement, apart from metadata. Past hand edits and
uncommitted builds produced plausible numbers and a 2,712-line rerun diff.

## Review an i3 result

```sh
python3 contrib/i3_buckets.py --write docs/results.md
```

Run this after editing `i3/classifications/<snapshot>.toml`. Put reasons,
citations and families there, keyed by test file and assertion, not in the raw
result. See the [bucket terms](docs/glossary.md) and [results guide](docs/results.md).

Never hand-edit the generated regions in `docs/results.md`. A review must not
change a measurement, and regenerating a snapshot must not erase a review.

## Update a snapshot

Follow [reproduction commands and agreement checks](docs/reproducing.md).
Result files in `i3/results/` and `sway-ipc/results/` are raw output from
`contrib/i3-suite-run` and `contrib/sway-ipc-run`, not hand-edited records.

The sole exception is `sway-ipc/results/i3-4.25-random.toml`: a hand-written
not-applicable record explaining why the random runner cannot drive i3.

- `pins.toml` names each compositor's exact source revision and, in `[snapshot]`,
  its result filename version. Runners refuse builds whose `git describe` ends
  in `-dirty` or `-modified`.
- To measure a newer compositor, change its pin in one commit and regenerate
  its snapshot in the same pull request.
- If validation fails, fix the generator, adapter or classification.
  Measured counts stay as measured.

### Resolve a stale input hash

Each result's `inputs` hashes tracked runner, adapter, normalization and corpus
contents, as defined by `contrib/provenance.py`. It depends on file contents,
not commit IDs, so it survives rebases and squashes.

| Change | Required action |
| --- | --- |
| Can affect a measurement | Regenerate affected results in the same change. |
| Regeneration must wait | List every stale result and its reason in `pending.toml`; regenerate later in one pinned-container run. |
| Cannot affect any measurement, such as a diagnostic message | Restamp affected results and explain why in the commit message, beside the restamp diff. |

For a measurement-neutral change only, set `RESULT` to an affected file.
The tool also accepts several result paths in one invocation:

```sh
python3 contrib/provenance.py --restamp "$RESULT"
```

Validation rejects stale results not listed in `pending.toml`, and listed
results that are no longer stale. The backlog stays explicit.

## Keep test rules the same for every compositor

- Declare [unstable assertions](docs/glossary.md) only when outcomes differ
  across the same number of runs for each compositor. Record per-assertion
  outcomes in `i3/flaky-runs.toml`; list them in `i3/unstable.toml`.
- Unstable assertions stay visible but are excluded from published stable
  counts. Exclude a whole file only if its TAP plan changes between runs or
  it aborts at a different point.
- If one compositor has far more unstable assertions, check adapter
  synchronisation first. Sway's list shrank after its adapter waited for
  X11 focus to settle.
- An adapter may translate a premise into the compositor's configuration
  language, such as i3 config into KDL or `fake-outputs` into headless outputs.
  Translate the same premise for every compositor that can express it.
- Document each translation in the adapter README and flag affected rows as
  `adapted`. Never change the test's meaning: rewriting X11 `class` criteria
  to Wayland `app_id` for one compositor once hid a limitation as a pass.
- A skip family claims a premise does not apply, with a source citation.
  Never apply it to a compositor whose adapter translates that premise.

## Add a comparison tolerance

Put every exemption in `sway-ipc/normalize.toml` as a named rule with a reason
and measured evidence. Scope it to the fields and scenarios that need it;
validation rejects field exemptions written into the runner.

A global rectangle tolerance was once widened from 10 to 70 pixels for a font
difference. The fix was to make the fonts agree.

## Check the harness before trusting a run

- Before a full run, every Wayland compositor must pass the canary files that
  pass on all pinned compositors. A flaky canary is a harness bug to fix;
  it stays in the canary set.
- After the run, reject snapshots with too many zero-pass files, or adapter
  logs containing `No such atom (I3_SOCKET_PATH)` or `no free X11 display`.

A container without working X11 displays once reported 446 swayward passes
where the figure was over 1,400. Reproducibility alone does not make a run valid.

## Work safely

- Run long jobs in the background with a log; poll every few minutes.
  A timed-out one-hour tool call loses the run.
- For edits, use a git worktree beside your checkout, sharing its object store
  and fetch:
  `git worktree add ../sway-ipc-oracle.worktrees/<name> -b <branch> origin/main`.
  Clean up with `git worktree remove`.
- For manual container runs that mount only the oracle checkout at `/oracle`,
  use a regular oracle clone. A worktree's `.git` file points outside that
  mount, so provenance cannot read tracked inputs. See
  [reproduction commands](docs/reproducing.md). `regenerate-rc` also mounts the
  git common directory and can run from a worktree.
- Use a fresh clone for a reproduction proof, as a new reader would.
  Sway builds used inside the container also need regular clones; see
  [pr-check requirements](docs/pr-check.md#requirements).
- Put scratch output and build directories on disk, never in `/tmp`,
  which is often RAM.
- Give every nested compositor a private socket and a memory cap.
  Keep the operator's session out of reach.

## Present one compositor at a time

Each result file describes one compositor at one version, relative to the
oracle. Keep cross-compositor comparisons, findings lists and triage of one
compositor against another in the compositor projects, not here. Results are
not a ranking.

A sway/i3 difference that looks like a sway bug belongs on a list offered to
the sway maintainers.
