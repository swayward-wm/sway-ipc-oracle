# pr-check: check a sway change for new crashes

`contrib/pr-check` takes two sway binaries you built: base (for example
master) and head (your branch). It sends generated IPC command sequences to
head, one fresh headless sway per sequence, and keeps every sequence that
crashes head. Each crash is then replayed twice on head and twice on base.
Only crashes that head reproduces and base survives count against the
change. For each of those it tries to reduce the list to a minimal
`repro.sh` and checks that the script itself crashes head and not base.
The script can be unreduced or missing; see
[Reading the report](#reading-the-report). Crashes that master already has are
listed as pre-existing and do not fail the run. Sway CI only builds, so this
gives a PR author a cheap way to show that a change does not add a crash on
sequences nobody wrote a test for.

## Quickstart

```sh
meson setup build -Db_sanitize=address,undefined -Dbuildtype=debug && meson compile -C build   # in each sway checkout
./contrib/pr-check --base /path/to/sway-master/build/sway/sway --head /path/to/sway-pr/build/sway/sway --out /tmp/pr-check   # in the oracle checkout
less /tmp/pr-check/report.txt
```

`--out` must be a new or empty directory. The run takes 15 minutes by
default.

## Requirements

- Python 3.11 or later. pr-check uses only the standard library.
- `foot`, and a font that matches `monospace`. Generated windows are foot
  windows, plus the hinted test client described below.
- Optional: `git`. If a binary sits inside a git checkout, the report shows
  its commit and whether the tree is dirty.
- Optional: the fixture toolchain (`cc`, `pkg-config`, `wayland-scanner`, and
  the `wayland-client` and `wayland-protocols` headers). With it, some
  windows are a small test client that sets size hints. Without it, the
  report says `hinted windows disabled: <missing> not found` and only foot
  windows are used.
- Optional: `systemd-run --user --scope`. If it works, each sway runs in a
  scope capped at 2 GiB with no swap. If not, sway runs under plain
  `timeout`.

If your machine lacks any of these, use the oracle container (see
[Reproducing the results](reproducing.md)) and build sway inside it, so the
binaries link against the image's libraries. Set `ORACLE_CONTAINER=1` there.
Clone each sway checkout rather than using a git worktree: a worktree's
`.git` file points at a host path that does not exist in the container, so
the report cannot show the commit.

## Options

| Option | Default | Meaning |
|---|---|---|
| `--minutes M` | 15 | Wall time for the whole run, at least 1. No seed starts after 60% of it. Judging and minimising get the rest. |
| `--seeds N` | | Explore exactly N head seeds, with no wall limit. `--minutes` is ignored. |
| `--also-base N` | 0 | Explore up to N more seeds with base as the explorer. This is the only way to see fixed crashes. |
| `--jobs J` | nproc / 4, at least 1 | Parallel compositors. Each job runs one sway plus its foot windows. |
| `--steps S` | 40 | Commands per seed. |
| `--timeout T` | 60 | Wall seconds for one compositor run. |
| `--seed K` | 0 | First seed. |

`--replay out/new-<n>/commands.json --binary <sway>` replays one recorded
list once and prints the outcome. It exits 0 if sway survived, 1 if it
crashed and 2 for a harness problem.

## Why ASan matters

A crash is identified by its signature: the ASan error type and the first
three sway functions of the fatal stack, innermost first, without line
numbers. For example `SEGV: container_swap < cmd_swap < execute_command`.
Line numbers are left out so that the same bug matches when head moves code
around. UBSan runs with `halt_on_error=0`, so its diagnostics never count as
the fatal error.

Without ASan, the signature is only the signal, such as `signal:SIGSEGV`. Two
different bugs then look the same, and a shared crash is weak evidence of a
shared bug. pr-check still runs, but the report prints a warning. Build both
binaries with `-Db_sanitize=address,undefined`.

## Reading the report

The summary goes to stdout. `report.txt` adds every crash with its replays
and its command list. Here is gating run 3, where head is master and base is
a branch that fixes five crashes (three entries cut):

```
pr-check: base 17cdc7db clean ASan, head 1652c54b clean ASan
explored 300 seeds (head), 9m21s, 4 jobs; hinted windows enabled
--seeds 300: fixed exploration size, no wall limit (--minutes ignored)
NEW in head: 5
  1. SEGV: view_is_visible < transaction_commit < transaction_commit_pending
     head 2/2, base 0/2; repro.sh verified (9 commands): out/new-1/
  ...
  4. SEGV: container_swap < cmd_swap < execute_command
     head 2/2, base 0/2; repro.sh verified (8 commands): out/new-4/
pre-existing 0, fixed 0, blocked 0, unconfirmed 0, harness 0. Details: out/report.txt
```

The first line gives each binary's commit, clean or dirty, and whether it
has ASan. `head 2/2` means head crashed with the same signature in both
replays. `base 0/2` means base crashed in neither.

Each crashed seed gets one outcome. The table describes head-explored
seeds. For an `--also-base` seed base is the explorer, so head and base swap
in every row: pre-existing means head also crashed with the same signature,
blocked means head crashed earlier, with a different signature or in only
one replay, unconfirmed means base did not crash with the same signature in
both replays, and what would be new is reported as fixed.

| Outcome | Meaning | Fails the run |
|---|---|---|
| new | Head crashed with the same signature in both replays, and base survived both. | yes |
| pre-existing | Base also crashed with the same signature in both replays, at the same step or later. The summary counts distinct signatures. | no |
| fixed | From `--also-base` only: base crashed in both replays and head survived both. | no |
| blocked | Base crashed earlier, with a different signature, or in only one replay. A base crash hides or muddles the head crash. `report.txt` lists both signatures. | no |
| unconfirmed | Head did not crash with the same signature in both replays. | no |
| harness | A run ended because of the harness, not sway: the wall timeout, the memory cap, or a replay error. The summary counts seeds. | only over 5% |
| unjudged | The budget ran out before the seed was judged. Rerun with a larger `--minutes`. | yes |

Each new crash has a directory `out/new-<n>/` with `commands.json` (the list
for `--replay`), `signature.txt`, the logs and usually `repro.sh`. The
`repro.sh` state is one of:

- **verified**: the script crashed head with the signature and left base
  running, twice each.
- **unverified**: the script did not reproduce, for example because the
  crash is timing sensitive. Use the `--replay` command instead.
- **needs fixture client**: the list opens a hinted test window, which is
  not a plain shell command. No script is written. Use `--replay`.
- **out of time**: the budget ran out before minimising finished. The report
  keeps the full explored list. If a probe had already shortened the list,
  and no final check had rejected the shorter list, `best.json` holds it as
  the best partial reduction, unverified. Otherwise there is no
  `best.json`.

`repro.sh` runs one `swaymsg` per step against the sway named by `SWAYSOCK`.
It starts nothing itself. Its header comment shows how to start a headless
sway set up the way pr-check sets one up, because the con_ids in the script
are those of a fresh sway.

Exit codes:

- **2**: harness failure. A binary failed to start, foot is missing, the
  budget ran out during the startup check, no seed was explored, or more
  than 5% of explored seeds had a harness run. This takes precedence.
- **1**: at least one new or unjudged crash.
- **0**: otherwise.

## What it does not test

- **Behaviour differences.** v1 reports crashes only. A change that makes
  sway reply differently, or build a different tree, passes. pr-check
  records head's settled observation after every step, so that a later
  version can compare them.
- **Input, output hotplug and client lifecycle.** pr-check sends IPC
  commands and opens foot or fixture windows. It does not send keyboard or
  pointer input, add or remove outputs, or make clients misbehave. Many
  recent sway crash fixes are in those areas.
- **Sequences only base would reach.** By default, generation reads head's
  state, so sequences that only base-driven generation would reach are not
  covered. `--also-base N` adds a separate base exploration pass.
- **Commands sent back to back.** pr-check waits for the tree to settle
  after every command, so crashes that need two commands with no settling
  between them are out of reach. One known sway crash in
  `container_get_gaps` is of that kind.
- **Whatever the generator does not reach.** The generator is random and
  state-aware, but it does not reach every sway path. In gating run 2 it
  did not reach a known `workspace_add_floating` crash in 600 seeds.

pr-check does not build sway and does not post anything to GitHub.

## Gating runs

Before release pr-check was run against three known pairs of ASan builds.
The reports, results and command lists are in
[`docs/pr-check-evidence/`](pr-check-evidence/README.md). The binaries:
master `1652c54b`; fixed `17cdc7db`, which is master plus 5 crash fixes,
including one in `root.c`; and noroot `06539d3e`, which is master plus every
fix except `root.c`. Every run used `--seeds 300 --jobs 4`.

**Run 1, same binary** (master vs master). Required: 0 new and 0 blocked.
Met. 300 seeds in 5m37s: new 0, pre-existing 3, fixed 0, blocked 0,
unconfirmed 0, harness 0. Five seeds crashed, and each reproduced 2/2 on
both sides at the same step (3 distinct signatures).

The same run measured the noise floor for comparing observations. Each of
the 295 seeds that survived was replayed once more on the same binary, and
each step's observation was compared with the first run's. The comparison
dropped only `id`, `pid` and `window`, and mapped focus ids to indexes.
Under those rules 295 of 295 seeds and 11262 of 11800 steps differed. Every
first difference was `foreign_toplevel_identifier`, a random identifier sway
assigns to each toplevel (ext-foreign-toplevel-list), so it differs between
any two runs. With that key also dropped, 0 of 295 seeds and 0 of 11800
steps differed. A behaviour comparison must drop
`foreign_toplevel_identifier`. With it dropped, the same-binary noise floor
over these 300 seeds is zero.

**Run 2, a real fix branch** (base master, head noroot, `--also-base 300`).
Required: every crash found is classified correctly, and the
`workspace_add_floating` crash is checked by a targeted replay. Met. 300 head
seeds and 300 base seeds in 10m58s: new 0, pre-existing 1, fixed 4, blocked
0, unconfirmed 0, harness 0. The pre-existing crash is the
`view_is_visible` crash that the `root.c` fix addresses, which noroot lacks.
The four fixed seeds are two of `SEGV: seat_node_from_node <
seat_set_raw_focus < workspace_focus_fullscreen` and two of `SEGV:
container_swap < cmd_swap < execute_command`.

The generator did not reach `workspace_add_floating` in 600 seeds. That is a
gap in the generator, not in pr-check. The known reproducer was replayed with
`--replay` instead. On master it crashed at step 8 with `SEGV:
workspace_add_floating < container_move_to_workspace <
container_move_to_container` (exit 1). On noroot it survived (exit 0). So
pr-check would classify the crash as fixed if exploration reached it.

**Run 3, planted regression** (base fixed, head master). Every master crash
should be new. Required: every master crash signature is new, and each
`repro.sh` is verified, or unverified with counts, with at least one
verified. Met. 300 seeds in 9m21s: new 5, pre-existing 0, fixed 0, blocked
0, unconfirmed 0, harness 0. The 5 new crashes cover 3 signatures. They were
minimised to 9, 6, 6, 8 and 8 commands, and all 5 `repro.sh` scripts are
verified: 2/2 crashes on head and 2/2 survivals on base. No probe or
verification run was a harness failure.

## Next: behaviour differences

The next version replays each explored list on base and compares the
observations step by step, with only runtime ids (including
`foreign_toplevel_identifier`) dropped. Differences are grouped by the
command and tree path that caused them, so an intended change shows up as
one group the PR author can point to, and anything else stands out.
