# pr-check: check a sway change for new crashes

`contrib/pr-check` runs generated IPC command sequences on two sway builds
you made: base (for example master) and head (your branch). It reports the
crashes that head has and base does not, with a short reproducer when it can.

## Quickstart

```sh
meson setup build -Db_sanitize=address,undefined -Dbuildtype=debug && meson compile -C build   # in each sway checkout
./contrib/pr-check --base /path/to/sway-master/build/sway/sway --head /path/to/sway-pr/build/sway/sway --out /tmp/pr-check   # in the oracle checkout
less /tmp/pr-check/report.txt
```

`--out` must be a new or empty directory. The run takes 15 minutes by
default. Exit 0 means no new or unjudged crash; see [Exit codes](#exit-codes).

- Add `--diffs` to also see where head behaves differently from base. See
  [Behaviour differences](#behaviour-differences).
- Missing foot or Python 3.11? See [Requirements](#requirements).
- Build both binaries with ASan, as above. See [Why ASan matters](#why-asan-matters).

## What a run does

1. **Explore.** Each [seed](glossary.md#runs-and-the-harness), a number
   that fixes one random command list, drives a [generator](#generation)
   that picks commands from head's current state, on one fresh headless sway
   per seed. Every list that crashes head is kept.
2. **Judge.** Each crash is replayed twice on head and twice on base. It is
   **new** only if head crashes the same way both times and base survives both.
3. **Minimise.** Each new crash is reduced to a short `repro.sh`, and the
   script is checked: it must crash head and leave base running. Some end
   unreduced or without a script; see [The reproducer](#the-reproducer).

Crashes that base also has are **pre-existing** and do not fail the run.
Sway's CI only builds, so this is a cheap way to show that a change adds no
crash on sequences nobody wrote a test for.

## Exit codes

| Exit | Meaning |
|---|---|
| 0 | No new or unjudged crash. |
| 1 | At least one new crash, or a crash the budget ran out before judging (unjudged). |
| 2 | The run is not a result: a binary failed to start, foot is missing, the budget ran out during the startup check, no seed was explored, or more than 5% of explored seeds had a [harness](glossary.md#runs-and-the-harness) run. Checked before 1. Invalid options also exit 2. |
| 130 | Interrupted. Finished rows stay in `results.jsonl`. |

Behaviour differences (`--diffs`) never change the exit code.

## Requirements

- Python 3.11 or later. pr-check uses only the standard library.
- `foot`, and a font that matches `monospace`. Generated windows are foot
  windows, plus the hinted test client below.
- Optional: `git`. If a binary sits inside a git checkout, the report shows
  its commit and whether the tree is dirty.
- Optional: the fixture toolchain (`cc`, `pkg-config`, `wayland-scanner`,
  and the `wayland-client` and `wayland-protocols` headers). With it, some
  windows are a small test client that sets size hints. Without it, the
  report says `hinted windows disabled: <missing> not found`.
- Optional: `systemd-run --user --scope`. If it works, each sway runs in a
  scope capped at 2 GiB with no swap. If not, or with `ORACLE_CONTAINER=1`,
  sway runs under plain `timeout`.

If your machine lacks any of these, use the oracle container (see
[Reproducing the results](reproducing.md)). Build sway inside it, so the
binaries link against the image's libraries, and set `ORACLE_CONTAINER=1`.

Clone each sway checkout rather than using a git worktree. A worktree's
`.git` file points at a host path that does not exist in the container, so
the report cannot show the commit.

## Options

| Option | Default | Meaning |
|---|---|---|
| `--minutes M` | 15 | Wall time for the whole run, at least 1. No seed starts after 60% of it (30% each for head and base with `--also-base`). Judging and minimising get the rest. |
| `--seeds N` | | Explore exactly N head seeds, with no wall limit. `--minutes` is ignored. |
| `--also-base N` | 0 | Explore up to N more seeds with base as the explorer. This is the only way to see fixed crashes. |
| `--jobs J` | nproc / 4, at least 1 | Parallel compositors. Each job runs one sway plus its foot windows. |
| `--steps S` | 40 | Commands per seed. |
| `--timeout T` | 60 | Wall seconds for one compositor run. |
| `--seed K` | 0 | First seed. |
| `--diffs` | off | Also report behaviour differences. |

## Replay one crash or difference

```sh
./contrib/pr-check --replay /tmp/pr-check/new-1/commands.json --binary /path/to/sway-pr/build/sway/sway
./contrib/pr-check --replay /tmp/pr-check/diff-1/commands.json --binary /path/to/sway-pr/build/sway/sway --against /path/to/sway-master/build/sway/sway
```

The first replays a crash's list once and prints the outcome. It exits 0 if
sway survived, 1 if it crashed and 2 for a harness problem.

The second replays a difference group's list once on `--binary` (head) and
once on `--against` (base), and prints the first difference. It exits 0 if
there is none, 1 if there is one and 2 if either replay did not survive.

## Why ASan matters

A crash is identified by its signature: the ASan error type and the first
three sway functions of the fatal stack, innermost first, for example
`SEGV: container_swap < cmd_swap < execute_command`.

Line numbers are left out, so the same bug matches when head moves code
around. UBSan runs with `halt_on_error=0`, so its diagnostics never count as
the fatal error.

Without ASan the signature is only the signal, such as `signal:SIGSEGV`, so
two different bugs look the same. pr-check still runs, but the report prints
a warning. Build both binaries with `-Db_sanitize=address,undefined`.

## Reading the report

The summary goes to stdout. `report.txt` adds every crash with its replays
and its command list. This is gating run 3, where head is master and base is
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
has ASan. `NEW in head: 5` counts seeds, not bugs: these 5 seeds have 3
distinct signatures.

`head 2/2` means head crashed with the same signature in both replays;
`base 0/2` means base crashed in neither.

### Outcomes

Each crashed seed gets one outcome:

| Outcome | Meaning | Fails the run |
|---|---|---|
| new | Head crashed with the same signature in both replays, and base survived both. | yes |
| pre-existing | Base also crashed with the same signature in both replays, at the same step or later. The summary counts distinct signatures. | no |
| fixed | From `--also-base` only: base crashed in both replays and head survived both. | no |
| blocked | Base crashed earlier, with a different signature, or in only one replay. A base crash hides or muddles the head crash. `report.txt` lists both signatures. | no |
| unconfirmed | Head did not crash with the same signature in both replays. | no |
| harness | A run ended because of the harness, not sway: the wall timeout, the memory cap, or a replay error. The summary counts seeds. | only over 5% |
| unjudged | The budget ran out before the seed was judged. Rerun with a larger `--minutes`. | yes |

The table describes head-explored seeds, except `fixed`. For an `--also-base`
seed base is the explorer: in the other rows read "head" as base and "base"
as head, and what would be new is reported as fixed.

### The reproducer

Each new crash has a directory `out/new-<n>/` with `commands.json` (the list
for `--replay`), `signature.txt`, the logs and usually `repro.sh`. The
report gives the `repro.sh` state:

- **verified**: the script crashed head with the signature and left base
  running, twice each.
- **unverified**: the script did not reproduce, for example because the
  crash is timing sensitive. Use `--replay` instead.
- **needs fixture client**: the list opens a hinted test window, which is
  not a plain shell command. No script is written. Use `--replay`.
- **out of time**: the budget ran out before minimising finished. The
  report keeps the full explored list. If a probe had already shortened
  it and no final check rejected that, `best.json` holds it, unverified.

`repro.sh` runs one `swaymsg` per step against the sway named by `SWAYSOCK`
and starts nothing itself. Its header shows how to start a headless sway set
up as pr-check sets one up, because the con_ids in it are a fresh sway's.

## Behaviour differences

`--diffs` asks "does this change behaviour anywhere I did not mean to?" for
the sequences pr-check explores.

An intended change usually shows up as one group, or a few with the same
command (for example tiled and floating paths). Say which groups are the point
of the PR; the rest are news.

### What is compared

Each head seed that survived is replayed once on base, right after it is
explored. After each step, base's settled reply, `get_tree` and
`get_workspaces` are compared with head's.

- **Exact.** Every value must be equal, including every rectangle to the
  pixel. None of the oracle's sway-vs-i3 tolerances
  (`sway-ipc/normalize.toml`) apply.
- **Runtime ids dropped.** The keys `id`, `pid`, `window` and
  `foreign_toplevel_identifier` are removed at any depth. A `focus` array's
  ids become indexes into that step's sorted node ids, so focus order still counts.
- **`NaN` equals `NaN`.** Sway reports the `percent` of some hidden
  scratchpad children as `NaN`, which otherwise never equals itself.
- **Only common steps.** Steps only one binary reached are not compared.
  If base crashes, the seed is listed as "base crashed" and left to the
  crash check and `--also-base`.

`foreign_toplevel_identifier` is a random id per toplevel. Gating run 1
found it was the only other key that differed between two runs of the same
binary, in 295 seeds.

With `--diffs`, a step that opens a window is observed once the tree is
unchanged for 0.3 s, since sway waits up to 200 ms for a new client. Without
this, 2 of 295 same-binary seeds differed on a new window's `border`.

### How seeds are grouped

Each differing seed contributes its first difference: the step, the command,
the first differing path and both values. Seeds are grouped by command and
path, both simplified:

- **Command.** Criteria and numbers are removed. A difference in reply `k`
  (`.reply[k]...`) is named after the `k`th command of the step, the one
  that replied, and keeps its index. Any other difference is named after
  the step's last command, since the state is observed after the whole step.
- **Path.** List indexes are removed, and any depth of nested containers
  below a workspace counts as one level (`.nodes[]*`). The same change one
  split deeper is the same group. Tiled and floating containers stay apart.

So `fullscreen enable; nop` and `floating enable; nop` failing in reply 0 are
two groups.

### How a group is minimised

One seed per group, the one whose difference comes earliest, is minimised
like a crash. Its list up to the differing step is
[delta-debugged](glossary.md#runs-and-the-harness).

Each probe replays once on head and once on base.

A probe is accepted only if both survive and the first difference has the
same exact path and values, and the same group. A probe that moves it to
another container, depth or reply is rejected, even if the group matches.

The result is replayed twice more on each binary:

- **verified**: the difference came back both times. If not, the full
  prefix is checked the same way.
- **not reproduced**: the full prefix failed too; the report gives the
  counts. Two fresh runs of the same commands on the same binary can differ
  (sway picks some floating sizes from client state that varies between
  runs). Treat it as noise unless `--replay ... --against` shows it again.
- **out of time**: the budget ran out; the group keeps the full prefix.

Each group's list is in `out/diff-<n>/commands.json`. The report adds one
line of counts and one entry per group. This is gating run 5 (output
directories shortened):

```
behaviour differences: 6 of 300 compared seeds in 2 groups (same 290, base crashed 4, harness 0)
  1. move scratchpad -> .tree.nodes[].nodes[].floating_nodes[].nodes[]*.fullscreen_mode: 5 seeds (428, 470, 355, 588, 496)
     head 0, base 1; verified (8 commands): out/diff-1/
  2. floating enable -> .tree.nodes[].nodes[].floating_nodes[].percent: 1 seed (447)
     head 0.3987630208333333, base 0.9083615451388888; not reproduced (reduced 0/2, full 1/2): unstable, possibly not caused by head (28 commands): out/diff-2/
```

### Cost and limits

- Harness runs among the base replays and minimising replays count toward
  the 5% harness threshold.
- `--diffs` costs time. Master against master over the same 300 seeds
  took 5m37s without it (run 1) and 17m37s with it (run 4). With
  `--minutes`, the base replays use the exploration share, so fewer seeds
  are explored.
- It covers only seeds that head survived and that head's generator chose.
  A behaviour that only appears after base-specific state is not covered.

## What it does not test

- **Behaviour differences, by default.** Without `--diffs`, a change that
  makes sway reply differently or build a different tree passes. With
  `--diffs` they are reported but never fail the run: only the PR author can
  say which ones are intended.
- **Input, output hotplug and client lifecycle.** pr-check sends IPC
  commands and opens foot or fixture windows. It sends no keyboard or
  pointer input and has no misbehaving clients. It changes outputs only over
  IPC (disable, enable, scale and transform); no output is hotplugged. Many recent sway crash fixes are in those areas.
- **Sequences only base would reach.** Generation reads head's state.
  `--also-base N` adds a separate base exploration pass.
- **Commands sent back to back.** pr-check waits for the tree to settle
  after every command. One known sway crash, in `container_get_gaps`, needs
  two commands with no settling between them.
- **Whatever the generator does not reach.** The generator is random and
  state-aware, but it does not reach every sway path. See
  [Generation](#generation) for one gap that was found and closed.

pr-check does not build sway and does not post anything to GitHub.

## Generation

pr-check uses the oracle's
[random-v3 generator](running.md#random-v3-state-aware)
(`contrib/sway_ipc_v3.py`, data in `sway-ipc/random-v3/`).

It adds its own recipes from `contrib/prcheck/coverage.py`, listed in
`run.json` under `extra_recipes`. They are used for exploration only, so the
oracle's sway-ipc results, which depend on random-v3, do not change.

Each one-output seed starts with one recipe, in turn: seed modulo the 18
one-output recipes. A two-output seed starts with the first multi-output recipe,
then the recipe its number picks. Later recipes are chosen at random, by weight.

So P1 below starts 21 of the seeds 0 to 599 (17, 35, 125, ...), comes second
in 12 (53, 71, 89, ...), and any seed can choose it later.

**Adding a recipe changes this mapping:** a seed number from runs 1 to 5
now explores a different list.

**P1-mark-in-hidden-split** reaches the `workspace_add_floating` crash
([sway crash 4](sway-crashes.md)). random-v3 alone did not reach it in
gating run 2's 600 seeds. The crash needs three things at once:

1. a mark on a container *inside* a split hidden in the scratchpad. A mark
   on the hidden split itself does not count: `move container to mark` then
   takes its early return and acts as `move scratchpad`;
2. a floating container focused;
3. `move container to mark` naming that mark.

No random-v3 recipe builds all three. Its mark recipe marks the window it
hides, not a child. The recipe that floats a split can mark its children
and hide it, but has no move-to-mark step and leaves nothing floating focused.

In gating run 2, 12 seeds reached a mark inside a hidden split, 2 of them
with a floating container focused, and none then moved to the mark. In
those 2 states the weighted choice picks that move about 7% of the time.

P1 floats a split around a window (or floats a tiled split), marks a child,
hides the split, floats the focused window and moves it to the mark. The
steps run back to back, so no random step takes the focus or the mark.

A second trigger follows: swap with the mark, focus or kill it, show the
scratchpad, move to a new workspace, or nothing. Run 6 under
[Gating runs](#gating-runs) shows what P1 finds.

## Where the code is

`contrib/pr-check` is a thin entry point. The code is the stdlib-only
package `contrib/prcheck/`: its `__init__.py` lists the modules in the order
a run uses them, and `cli.py`'s docstring describes a run and its output files.

The self-test is `contrib/tests/pr-check`.

## Gating runs

Before release pr-check was run against known pairs of ASan builds. The
reports, command lists and full details are in
[`docs/pr-check-evidence/`](pr-check-evidence/README.md).

| Build | Commit | What it is |
|---|---|---|
| master | `1652c54b` | sway master |
| fixed | `17cdc7db` | master plus 5 crash fixes: the four [pinned sway crashes](sway-crashes.md) and a fifth, `view_is_visible` (a fullscreen descendant left in the scratchpad), fixed in `root.c` |
| noroot | `06539d3e` | master plus every fix except `root.c` |

Every run used `--jobs 4` and, except one 3-minute run, `--seeds 300`. Runs
1 to 5 predate pr-check's own recipe, so their seed numbers now explore
other lists (see [Generation](#generation)).

| Run | Base, head | Required | Result |
|---|---|---|---|
| 1, same binary | master, master | 0 new and 0 blocked | Met. 5 crashed seeds, all pre-existing (3 signatures); 5m37s. |
| 2, fix branch | master, noroot, `--also-base 300` | every crash classified correctly; `workspace_add_floating` checked by targeted replay | Met. Pre-existing 1 (the `root.c` crash noroot lacks), fixed 4. The replay crashed master (exit 1) and noroot survived (exit 0). |
| 3, planted regression | fixed, master | every master crash new; each `repro.sh` verified, or unverified with counts, at least one verified | Met. 5 new (3 signatures), minimised to 6 to 9 commands, all 5 `repro.sh` verified. |
| 4, same binary, `--diffs` | master, master | 0 differing seeds | Met. 0 of 295 compared seeds. |
| 5, fix branch, `--diffs`, seeds 300 to 599 | master, fixed | the `root.c` change is one group; nothing unexplained | Met. Group 1 is `root.c` (5 seeds, verified at 8 commands). Group 2, seed 447, was not reproduced and differs master against master 2 times in 5: sway run variance. 4 seeds crashed base and were not compared. |
| 6, generator coverage | fixed, master | `workspace_add_floating` found on master within a stated budget, not on fixed; `--diffs` noise still 0 | Met. 29 of 300 seeds hit it, the first at seed 17 step 10; 27 `repro.sh` verified, 2 need the fixture client. |
| 6, continued | master, fixed | | No crash: in all 29 lists, fixed rejects the `move container to mark`. |
| 6, continued | master, master, `--diffs` | | 0 of 268 compared seeds differ. |
| 6, continued | fixed, master, `--minutes 3` | | 106 seeds explored, the crash in 10, no time left to minimise. |

Run 1 also measured the noise floor that shaped the `--diffs` rules: with
only `id`, `pid` and `window` dropped, all 295 surviving seeds differed, each
first at `foreign_toplevel_identifier`. With that key dropped too, none did.
