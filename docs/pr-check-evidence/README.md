# pr-check gating runs

Runs 1 to 3 are the first three [gating runs](../pr-check.md#gating-runs),
run on 2026-10-24. Runs 4 and 5 gate `--diffs` (v2, behaviour differences)
and were run on 2026-10-26; see [Runs 4 and 5](#runs-4-and-5-behaviour-differences-v2).

Run 6 gates the generator recipe that reaches `workspace_add_floating`; see
[Run 6](#run-6-generator-coverage).

Each directory holds the run's `report.txt` and `run.json` exactly as
pr-check wrote them, and runs 1 to 3 also hold `results.jsonl`. The per-seed
logs and observations are too large to commit ([Not committed](#not-committed)).

Paths: `<scratch>` (`$S` in shell) is the host directory holding the sway
checkouts and builds. It is mounted at `/w` in the oracle image.
`<workspace>` is this repository, mounted at `/oracle`.

## Binaries

All three are ASan+UBSan debug builds (`-Db_sanitize=address,undefined
-Dbuildtype=debug`), and `run.json` records `asan: true, dirty: false` for each.

| Name | Container path | Revision |
|---|---|---|
| master | `/w/sway-master/build/sway/sway` | `1652c54b` (sway master) |
| fixed | `/w/sway-fixed/build/sway/sway` | `17cdc7db`: master + 5 crash fixes, including `root.c` |
| sway-noroot | `/w/sway-noroot/build/sway/sway` | `06539d3e`: master + every fix except `root.c` |

sway-noroot was built for run 2. It was cloned rather than created as a git
worktree, because the harness runs git inside the container and a worktree's
`.git` points at a host path:

```sh
S=<scratch>
git clone $S/sway $S/sway-noroot && cd $S/sway-noroot
git checkout -b noroot 1652c54b
git cherry-pick c75b36ba 75a19d77 04a131ab 17cdc7db
# HEAD 06539d3e; the picks are 630c28f6 9562591b 44871d80 06539d3e
git diff 1652c54b -- sway/tree/root.c     # empty
mkdir subprojects && cp -r $S/sway-fixed/subprojects/wlroots subprojects/ && rm -rf subprojects/wlroots/build
# in the oracle image, mounted at /w:
meson setup build -Ddefault-wallpaper=false -Dman-pages=disabled -Db_sanitize=address,undefined -Dbuildtype=debug
meson compile -C build -j 4
```

## How the runs were invoked

Every run used the oracle image `localhost/sway-ipc-oracle:rc-1fd3c25b`, one
container at a time:

```sh
podman run --rm --memory 8g --security-opt label=disable \
  -v <scratch>:/w -v <workspace>:/oracle localhost/sway-ipc-oracle:rc-1fd3c25b \
  bash -lc 'git config --global --add safe.directory "*"; cd /oracle && ORACLE_CONTAINER=1 <command>'
```

| Run | `<command>` | Exit | Wall |
|---|---|---|---|
| 1 | `./contrib/pr-check --base /w/sway-master/build/sway/sway --head /w/sway-master/build/sway/sway --out /w/prcheck-gate-1 --seeds 300 --jobs 4` | 0 | 5m37s |
| 1, noise floor | `python3 /w/prcheck-gate-1-noise/noise-floor.py replay /w/prcheck-gate-1 /w/sway-master/build/sway/sway /w/prcheck-gate-1-noise 4` | 0 | 5m05s |
| 2 | `./contrib/pr-check --base /w/sway-master/build/sway/sway --head /w/sway-noroot/build/sway/sway --out /w/prcheck-gate-2 --seeds 300 --also-base 300 --jobs 4` | 0 | 10m58s |
| 2, targeted | `./contrib/pr-check --replay /w/prcheck-gate-2-mark/commands.json --binary /w/sway-master/build/sway/sway --out /w/prcheck-gate-2-mark/sway-master` | 1 | seconds |
| 2, targeted | `./contrib/pr-check --replay /w/prcheck-gate-2-mark/commands.json --binary /w/sway-noroot/build/sway/sway --out /w/prcheck-gate-2-mark/sway-noroot` | 0 | seconds |
| 3 | `./contrib/pr-check --base /w/sway-fixed/build/sway/sway --head /w/sway-master/build/sway/sway --out /w/prcheck-gate-3 --seeds 300 --jobs 4` | 1 | 9m21s |

The noise-floor comparison itself ran on the host, outside the image:
`python3 noise-floor.py compare <scratch>/prcheck-gate-1 <scratch>/prcheck-gate-1-noise`.
Its output is `run-1-same-binary/noise-floor.txt`.

Exit 1 means "new crashes found", which is the expected result for run 3.
Each container prints `fatal: gitfile does not point to a valid repository:
/oracle/.git` once. The workspace was a git worktree, so its `.git` points at
a host path. The message is harmless: provenance reads the sway checkouts
under `/w`.

## Run 1: same binary (master vs master)

Requirement: 0 new and 0 blocked. **Met.**

```
pr-check: base 1652c54b clean ASan, head 1652c54b clean ASan
explored 300 seeds (head), 5m37s, 4 jobs; hinted windows enabled
NEW in head: 0
pre-existing 3, fixed 0, blocked 0, unconfirmed 0, harness 0
```

Five seeds crashed. Every one reproduced 2/2 on both sides at the same step,
so all are pre-existing (3 distinct keys):

| Seed | Step | Key |
|---|---|---|
| 37 | 40 | `SEGV: view_is_visible < transaction_commit < transaction_commit_pending` |
| 64 | 22 | `SEGV: seat_node_from_node < seat_set_raw_focus < workspace_focus_fullscreen` |
| 67 | 18 | same as 64 |
| 69 | 38 | `SEGV: container_swap < cmd_swap < execute_command` |
| 282 | 32 | same as 64 |

### v2 noise floor

Each of the 295 explored seeds that survived was replayed once on base (the
same master binary) with `replay(..., keep_observations=True)`. The replay
recorded the same per-step observation that explore writes to
`observations.jsonl`, and each step was compared with head's observation
under the exact rules. The rules delete the keys `id`, `pid` and `window` at
any depth, and replace every integer in a `focus` array with its index in the
sorted list of that step's node ids. Everything else is compared, including
`inhibit_idle` and `idle_inhibitors`.

| | Seeds with any difference | Steps with a difference |
|---|---|---|
| Exact rules | **295 / 295** | 11262 / 11800 |
| Exact rules, also dropping `foreign_toplevel_identifier` (diagnostic only) | 0 / 295 | 0 / 11800 |

All 295 base replays survived. In every seed, the first differing path is
`foreign_toplevel_identifier` on the first window, at the first step after
it maps (292 seeds at `.tree.nodes[].nodes[].nodes[]`, 3 in
`floating_nodes[]`). The per-seed list is in
`run-1-same-binary/noise-floor.txt`, and the diagnostic run is in
`noise-floor-diagnostic.txt`.

`foreign_toplevel_identifier` is a random identifier that sway assigns to
each toplevel (ext-foreign-toplevel-list). Like a node id, it differs between
any two runs. **The v2 rules must drop `foreign_toplevel_identifier`.** With
that key dropped, the same-binary noise floor over these 300 seeds is zero.

The helper script was written for this run under `/tmp`, and a copy is at
`<scratch>/prcheck-gate-1-noise/noise-floor.py`. Its full text:

```python
#!/usr/bin/env python3
"""Gating run 1 noise floor: replay every survived head seed once on base and
compare each step's observation with head's observations.jsonl.

  noise-floor.py replay RUN_OUT BASE_BINARY NOISE_OUT JOBS   (in the oracle image)
  noise-floor.py compare RUN_OUT NOISE_OUT [EXTRA_KEY...]    (anywhere)

Exact rules: delete the keys "id", "pid" and "window" at any depth; replace
every integer inside a "focus" array with its index into the sorted list of
node ids of that step's tree. Everything else is compared.
EXTRA_KEY... (diagnostic only, not the exact rules) deletes more keys.
"""
import importlib.machinery
import json
import multiprocessing
import re
from pathlib import Path
import sys

DROP = {"id", "pid", "window"}


def survived(run_out):
    rows = [json.loads(line) for line in (run_out / "results.jsonl").read_text().splitlines()]
    return [r for r in rows if r["phase"] == "explore" and r["side"] == "head"
            and r["outcome"] == "survived"]


def replay_one(task):
    base, row, noise_out = task
    pc = importlib.machinery.SourceFileLoader("pr_check", "/oracle/contrib/pr-check").load_module()
    seed_dir = noise_out / "seeds" / f"base-{row['seed']}"
    seed_dir.mkdir(parents=True, exist_ok=True)
    result = pc.replay(Path(base), row["commands"], row["outputs"], seed_dir / "replay.log", 60,
                       keep_observations=True)
    with open(seed_dir / "observations.jsonl", "w") as f:
        for entry in result.pop("observations"):
            f.write(json.dumps(entry) + "\n")
    return {"seed": row["seed"], "outcome": result["outcome"], "step": result["step"],
            "error": result["error"]}


def replay(run_out, base, noise_out, jobs):
    rows = survived(run_out)
    noise_out.mkdir(parents=True, exist_ok=True)
    with multiprocessing.get_context("fork").Pool(jobs) as pool, \
            open(noise_out / "replays.jsonl", "w") as f:
        for result in pool.imap_unordered(replay_one, [(base, r, noise_out) for r in rows]):
            f.write(json.dumps(result) + "\n")
            f.flush()
        pool.close()
        pool.join()


def node_ids(value, ids):
    if isinstance(value, dict):
        if isinstance(value.get("id"), int):
            ids.add(value["id"])
        for v in value.values():
            node_ids(v, ids)
    elif isinstance(value, list):
        for v in value:
            node_ids(v, ids)
    return ids


def normalise(value, index):
    if isinstance(value, dict):
        out = {}
        for k, v in value.items():
            if k in DROP:
                continue
            if k == "focus" and isinstance(v, list):
                out[k] = [index.get(x, f"unknown:{x}") if isinstance(x, int) else x for x in v]
            else:
                out[k] = normalise(v, index)
        return out
    if isinstance(value, list):
        return [normalise(v, index) for v in value]
    return value


def normalised(entry):
    index = {node: n for n, node in enumerate(sorted(node_ids(entry["tree"], set())))}
    return normalise(entry, index)


def first_difference(a, b, path=""):
    if type(a) is not type(b):
        return path or "."
    if isinstance(a, dict):
        for k in list(a) + [k for k in b if k not in a]:
            if k not in a or k not in b:
                return f"{path}.{k}"
            if (found := first_difference(a[k], b[k], f"{path}.{k}")) is not None:
                return found
        return None
    if isinstance(a, list):
        for n, (x, y) in enumerate(zip(a, b)):
            if (found := first_difference(x, y, f"{path}[{n}]")) is not None:
                return found
        return f"{path}[len {len(a)} != {len(b)}]" if len(a) != len(b) else None
    return None if a == b else path


def load(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def compare(run_out, noise_out, extra=()):
    DROP.update(extra)
    replays = {r["seed"]: r for r in load(noise_out / "replays.jsonl")}
    rows = survived(run_out)
    diffs, steps, differing_steps = {}, 0, 0
    for row in sorted(rows, key=lambda r: r["seed"]):
        seed = row["seed"]
        rep = replays.get(seed)
        if rep is None or rep["outcome"] != "survived":
            diffs[seed] = f"base replay {rep and rep['outcome']} at step {rep and rep['step']}"
            continue
        head = load(run_out / "seeds" / f"head-{seed}" / "observations.jsonl")
        base = load(noise_out / "seeds" / f"base-{seed}" / "observations.jsonl")
        if len(head) != len(base):
            diffs[seed] = f"observation count {len(head)} != {len(base)}"
        first = None
        for h, b in zip(head, base):
            steps += 1
            found = first_difference(normalised(h), normalised(b))
            if found is not None:
                differing_steps += 1
                first = first or f"step {h['step']} {found}"
        if first and seed not in diffs:
            diffs[seed] = first
    print(f"dropped keys: {sorted(DROP)}; focus ints -> sorted node-id index")
    print(f"seeds compared: {len(rows)}; seeds with any difference: {len(diffs)}; "
          f"steps compared: {steps}; steps with a difference: {differing_steps}")
    shapes = {}
    for where in diffs.values():
        shape = re.sub(r"\[\d+\]", "[]", re.sub(r"^step \d+ ", "", where))
        shapes[shape] = shapes.get(shape, 0) + 1
    print("first differing path, indices folded (seeds):")
    for shape, count in sorted(shapes.items(), key=lambda kv: -kv[1]):
        print(f"  {count:4d}  {shape}")
    print("first differing path per seed:")
    for seed, where in diffs.items():
        print(f"  seed {seed}: {where}")


if __name__ == "__main__":
    if sys.argv[1] == "replay":
        replay(Path(sys.argv[2]), sys.argv[3], Path(sys.argv[4]), int(sys.argv[5]))
    else:
        compare(Path(sys.argv[2]), Path(sys.argv[3]), sys.argv[4:])
```

## Run 2: today's branch (base master, head sway-noroot)

Requirement, as amended by the maintainer after this run (see the end of
this section): every crash found is classified correctly, and
`workspace_add_floating` is checked by a targeted replay. **Met.**

```
pr-check: base 1652c54b clean ASan, head 06539d3e clean ASan
explored 300 seeds (head), 300 (base), 10m58s, 4 jobs; hinted windows enabled
NEW in head: 0
pre-existing 1, fixed 4, blocked 0, unconfirmed 0, harness 0
```

| Classification | Seed (explorer) | Key | Expected |
|---|---|---|---|
| pre-existing | head 37 | `SEGV: view_is_visible < transaction_commit < transaction_commit_pending` | yes: sway-noroot lacks the `root.c` fix |
| fixed | base 320, base 456 | `SEGV: seat_node_from_node < seat_set_raw_focus < workspace_focus_fullscreen` | yes |
| fixed | base 433, base 502 (2 outputs) | `SEGV: container_swap < cmd_swap < execute_command` | yes |

`workspace_add_floating` was not reached by 600 v3 seeds. Its classification
was checked by `--replay` of the known reproducer instead
(`run-2-todays-branch/workspace-add-floating/commands.json`).

The reproducer sends one floating, split, marked window to the scratchpad,
then moves a second floating window to that mark.

- On master the replay crashed at step 8 with `SEGV: workspace_add_floating
  < container_move_to_workspace < container_move_to_container` (exit 1).
- On sway-noroot it survived (exit 0).

So the fix is in the head build, and pr-check would classify the crash as
fixed if exploration reached it.

This crash was first found with v3 seed 40167 under an older generator.
With the current generator, base seed 40167 survives (checked with
`--seed 40166 --seeds 1 --also-base 1`).

`container_get_gaps` is unreachable by design: it needs two commands sent
back to back with no settling between them, and pr-check waits for the tree
to settle after every command.

What was amended: the original requirement said `workspace_add_floating`
must appear as a fixed key. The maintainer replaced it with the targeted
replay.

Whether exploration reaches a crash is a property of the generator, not of
pr-check. Run 6 later closed that generator gap.

## Run 3: planted regression (base fixed, head master)

Head is unmodified master and base is the 5-commit fixed build, so every
master crash should be judged new.

The first plan reverted one fix on top of fixed. The maintainer changed it to
plain master, which holds every crash that fixed fixes.

Requirement: every master crash key is new, and each `repro.sh` is verified,
or unverified with counts; at least one verified. **Met: 5 new, 5 verified.**

```
pr-check: base 17cdc7db clean ASan, head 1652c54b clean ASan
explored 300 seeds (head), 9m21s, 4 jobs; hinted windows enabled
NEW in head: 5
pre-existing 0, fixed 0, blocked 0, unconfirmed 0, harness 0
```

| new | Seed | Key | Minimised to | Probes | Final replay head / base | repro.sh head / base |
|---|---|---|---|---|---|---|
| 1 | 37 | `SEGV: view_is_visible < transaction_commit < transaction_commit_pending` | 9 commands | 92 | 2/2 key, 2/2 survived | 2/2 key, 2/2 survived |
| 2 | 64 | `SEGV: seat_node_from_node < seat_set_raw_focus < workspace_focus_fullscreen` | 6 | 35 | 2/2, 2/2 | 2/2, 2/2 |
| 3 | 67 | same as 2 | 6 | 40 | 2/2, 2/2 | 2/2, 2/2 |
| 4 | 69 | `SEGV: container_swap < cmd_swap < execute_command` | 8 | 64 | 2/2, 2/2 | 2/2, 2/2 |
| 5 | 282 | same as 2 | 8 | 69 | 2/2, 2/2 | 2/2, 2/2 |

No probe or verification run was a harness failure. The rendered `repro.sh`
files are in `<scratch>/prcheck-gate-3/new-*/` (not committed); their
command lists are in `results.jsonl` and `report.txt`.

## Runs 4 and 5: behaviour differences (v2)

Both used the same binaries (master `1652c54b`, fixed `17cdc7db`) and image as
runs 1 to 3, run from a git worktree of this repository with `--memory 8g`.

The main repository's `.git` was mounted read-only at its host path, and a
scratch output directory (`<out>`) was mounted at `/out`:

```sh
podman run --rm --memory 8g --security-opt label=disable -v <scratch>/sway-fix:/w \
  -v <out>:/out -v <workspace>:/oracle:ro -v <main .git>:<main .git>:ro \
  localhost/sway-ipc-oracle:rc-1fd3c25b \
  bash -lc "git config --global --add safe.directory '*'; cd /oracle && ORACLE_CONTAINER=1 PYTHONDONTWRITEBYTECODE=1 <command>"
```

| Run | `<command>` | Exit | Wall |
|---|---|---|---|
| 4, noise | `./contrib/pr-check --base /w/sway-master/build/sway/sway --head /w/sway-master/build/sway/sway --out /out/noise4 --seeds 300 --jobs 4 --diffs` | 0 | 17m37s |
| 5, diffs | `./contrib/pr-check --base /w/sway-master/build/sway/sway --head /w/sway-fixed/build/sway/sway --out /out/diffs4 --seed 300 --seeds 300 --jobs 4 --diffs` | 0 | 31m40s |
| 5, replay | `./contrib/pr-check --replay /out/diffs4/diff-<n>/commands.json --binary <fixed or master> --against /w/sway-master/build/sway/sway`, 3 times each for group 1, 5 times each for group 2 | 1 / 0 | seconds |

Each directory holds `report.txt` and `run.json`. `results.jsonl` (1.4 MB
per run) is not committed; every differing seed's first difference is in
`report.txt`. `run-5-v2-diffs/diff-<n>/` has each group's `commands.json`
(plus `resolved.json` and `sent.json` for the verified group 1), and
`replay-against.txt` has the `--replay ... --against` outputs.

These runs were made at the commit that changed the minimise predicate to
the exact first-difference path and values and named reply differences
after the replying subcommand. The last runs at the previous commit gave
run 4: 0 of 295, and run 5: the same 5-seed group (minimised to 5 commands)
and no other; only their outcomes are recorded here.

### Run 4: same binary (master vs master), `--diffs`

Requirement: 0 differing seeds over at least 100 seeds. **Met.**

```
NEW in head: 0
pre-existing 3, fixed 0, blocked 0, unconfirmed 0, harness 0
behaviour differences: 0 of 295 compared seeds in 0 groups (same 295, base crashed 0, harness 0)
```

All 295 seeds that head survived were compared over 40 steps each, 11,800
steps in total. The 5 crashed seeds are the pre-existing crashes of run 1.

Earlier runs from the same day decided the rules, and only their outcomes
are recorded here:

- **First run:** 0 of 295. The rules were exact, with `NaN` compared as
  JSON compares it.
- **Second run:** 2 of 295 (seeds 130 and 148). In both, a window had just
  mapped at an `exec foot` step, and one side still showed its
  pre-transaction `border` (`none`, width 0) while the other showed the
  applied value (`normal`, or width 2). Sway waits up to `txn_timeout_ms`
  (200 ms, `sway/server.c:701`) for a new window's first transaction. The
  runner's settle (two equal reads 50 ms apart) can finish before that. The
  fix is that `--diffs` re-reads a map step's state until it has been
  unchanged for 0.3 s (`prcheck/sequence.py`, `settle_map`). Every later run
  includes that fix. Neither difference reproduced when minimised.

### Run 5: base master, head fixed, `--diffs`

Requirement: the `root.c` `fullscreen_mode` change is reported as one group,
and nothing is left unexplained. **Met.**

```
NEW in head: 0
pre-existing 0, fixed 0, blocked 0, unconfirmed 0, harness 0
behaviour differences: 6 of 300 compared seeds in 2 groups (same 290, base crashed 4, harness 0)
  1. move scratchpad -> .tree.nodes[].nodes[].floating_nodes[].nodes[]*.fullscreen_mode: 5 seeds (428, 470, 355, 588, 496)
     head 0, base 1; verified (8 commands): /out/diffs4/diff-1/
  2. floating enable -> .tree.nodes[].nodes[].floating_nodes[].percent: 1 seed (447)
     head 0.3987630208333333, base 0.9083615451388888; not reproduced (reduced 0/2, full 1/2): unstable, possibly not caused by head (28 commands): /out/diffs4/diff-2/
```

**Group 1 is the `root.c` change.** It holds the three seeds that the
earlier fuzz runs found (355, 428, 470), plus 588 and 496. In 496 the
fullscreen child sits one split deeper. Seed 428's difference is at
`floating_nodes[0].nodes[1]`, the second child of the floating split. Its
list was minimised in 25 probes to 8 commands, and the difference came back
at that exact path 2/2 in the final check:

1. `exec foot --app-id=fixture-diff-1 ...`
2. `exec foot --app-id=fixture-diff-2 ...`
3. `exec foot --app-id=fixture-diff-4 ...`
4. `focus parent`
5. `floating enable`
6. `focus child`
7. `move container to workspace 2`
8. `fullscreen toggle; move scratchpad`

The earlier 5-command reduction (one window, so the fullscreen child was
`floating_nodes[0].nodes[0]`) is no longer accepted: it moves the
difference to another node. Under `--replay ... --against master`, fixed
showed the difference at the same path 3 times out of 3 (exit 1). Master
against master was the same 3 times out of 3 (exit 0).

**Group 2 is sway run variance, not the fix.** Seed 447, a floating
window's `percent` after `floating enable`: 0.3988 vs 0.9084, from width
700 vs 1282.

- It did not reproduce when minimised (reduced 0/2), and the full
  28-command prefix reproduced 1/2.
- Under `--replay ... --against master` with `diff-2/commands.json`, master
  against master differed 2 times out of 5 and fixed against master 3 times
  out of 5, with the values in both directions.

So sway chooses this floating size from client state that varies between
runs (compare `floating-rect-run-variance` in `sway-ipc/normalize.toml`).

The same seed appeared with the same values, and was not reproduced, in the
first run 5 made while the previous commit was developed. In the last run at
that commit its two sides happened to match.

The 4 seeds that were not compared crashed base (master) during its replay.
They are known master crashes that the fixed build fixes:

| Seed | Base step | ASan key (first frames) |
|---|---|---|
| 320 | 24 | `seat_node_from_node < seat_set_raw_focus < workspace_focus_fullscreen` |
| 433 | 32 | `container_swap < cmd_swap < execute_command` |
| 456 | 39 | `cmd_mode < execute_command < ipc_client_handle_command` (SEGV at the same pc as 320) |
| 502 | 39 | `container_swap < cmd_swap < execute_command` |

The first run of run 5 at the previous commit, before the `NaN` and
nesting rules, gave 4 groups: group 1 split in two (496 was its own group
until nested containers were folded into `.nodes[]*`), seed 447 as above,
and seed 317, `percent` NaN vs NaN, which is not a difference: NaN now
equals NaN.

## Run 6: generator coverage

Gating run 2 never reached `workspace_add_floating` (sway crash 4). pr-check
now adds a recipe of its own, `P1-mark-in-hidden-split`
(`contrib/prcheck/coverage.py`; see `docs/pr-check.md`, "Generation"), to
random-v3's recipes. Run 6 checks that pr-check now finds the crash on master
and not on fixed, and that the same-binary `--diffs` noise gate is still 0.
It was run on 2026-10-26 with the binaries and image of runs 4 and 5, from a
git worktree, with the same `podman run` line (`--memory 8g
--memory-swap 8g`, scratch output at `/out`).

| Run | `<command>` | Exit | Wall |
|---|---|---|---|
| 6, master | `./contrib/pr-check --base /w/sway-fixed/build/sway/sway --head /w/sway-master/build/sway/sway --out /out/cov-master --seeds 300 --jobs 4` | 1 | 15m05s |
| 6, fixed | `./contrib/pr-check --base /w/sway-master/build/sway/sway --head /w/sway-fixed/build/sway/sway --out /out/cov-fixed --seeds 300 --jobs 4` | 0 | 5m13s |
| 6, noise | `./contrib/pr-check --base /w/sway-master/build/sway/sway --head /w/sway-master/build/sway/sway --out /out/noise --seeds 300 --jobs 4 --diffs` | 0 | 17m52s |
| 6, 3 minutes | `./contrib/pr-check --base /w/sway-fixed/build/sway/sway --head /w/sway-master/build/sway/sway --out /out/min3 --minutes 3 --jobs 4` | 1 | 3m03s |

Each directory under `run-6-coverage/` holds that run's `report.txt` and
`run.json`. `master/new-1/` holds the first new crash's minimised
`commands.json`, `repro.sh` and `signature.txt`. `gap.py` measures how close
explored seeds get to the crash's precondition, from their
`observations.jsonl`, and `gap.txt` is its output for gating run 2 and for
runs 6 master and fixed.

**Master (head) against fixed (base), 300 seeds.** Required: a
`workspace_add_floating` crash within a stated budget. **Met.**

29 of 300 seeds crashed with `SEGV: workspace_add_floating <
container_move_to_workspace < container_move_to_container`, each judged new
(head 2/2, base 0/2).

- All 12 seeds whose first recipe is P1 (17, 35, 125, 143, 161, 179, 197,
  215, 233, 251, 269 and 287) crashed, the first at seed 17 step 10.
- The other 17 drew P1 later: 4 (seeds 53, 71, 89 and 107, two outputs)
  through the deterministic follow slot, 13 by the weighted recipe choice.
- Every one of the 29 ends in P1's steps: `floating enable`, then
  `move container to mark m`.
- 27 `repro.sh` scripts are verified, minimised to 8 commands (24) or 10 (3).
  2 need the fixture client (6 commands), because the list opens a hinted
  window.

new-1 (seed 17):

```
exec foot --app-id=fixture-diff-1 ...
exec foot --app-id=fixture-diff-2 ...
floating enable
splith
mark m
move scratchpad
floating enable
move container to mark m
```

The other 3 new crashes are the known master crashes that fixed also fixes:
`seat_node_from_node < seat_set_raw_focus < workspace_focus_fullscreen`,
`view_is_visible < transaction_commit < transaction_commit_pending` and
`container_swap < cmd_swap < execute_command`, one seed each.

**Fixed (head) against master (base), the same 300 seeds.** Required: no
`workspace_add_floating` crash. **Met.** No seed crashed (new 0,
pre-existing 0). Each of the 29 seeds that crashed master sent the same
commands up to that step, and fixed replied to `move container to mark m`
with `Can't move a floating container into a hidden scratchpad container`,
the guard that its commit `75a19d77` adds.

**Noise, master against master with `--diffs`, 300 seeds.** Required: 0
differing seeds, as in run 4. **Met.**

```
NEW in head: 0
pre-existing 4, fixed 0, blocked 0, unconfirmed 0, harness 0
behaviour differences: 0 of 268 compared seeds in 0 groups (same 268, base crashed 0, harness 0)
```

All 268 surviving seeds were compared over 40 steps each. The 32 crashed
seeds are the master crashes above, each pre-existing (4 distinct keys).

**3 minutes, master against fixed.** For the default kind of budget: 106
seeds were explored (no seed starts after 60% of the run, 1m48s), and 10 of
the 11 new crashes are
`workspace_add_floating`. None was minimised in the 3 minutes (each
reported "out of time" with its full list), so `--minutes 3` finds the crash
but needs more time to reduce it. The default 15 minutes left time to
minimise in run 6 master.

**Why random-v3 alone missed it** (`gap.txt`). The crash needs a mark on a
container inside a split hidden in the scratchpad, a floating container
focused, and `move container to mark` naming that mark. In gating run 2's
600 seeds, 12 seeds reached such a mark, 2 of them with a floating container
focused, and none then moved it to the mark. In run 6 master, 42 seeds
reached such a mark, 32 with a floating container focused, and 29 moved it
to the mark next, which is the 29 crashes.

## Not committed

The per-seed logs (`explore.log`, judge, minimise and script logs),
`observations.jsonl`, `new-*/` and `preflight/` are left out because of
their size:

| Directory | Total | Committed here | Left out |
|---|---|---|---|
| `<scratch>/prcheck-gate-1` | 145.0 MB | 1.4 MB | 143.6 MB |
| `<scratch>/prcheck-gate-1-noise` (base replays) | 141.7 MB | noise-floor output only | 141.7 MB |
| `<scratch>/prcheck-gate-2` | 292.6 MB | 2.7 MB | 289.9 MB |
| `<scratch>/prcheck-gate-3` | 145.9 MB | 1.4 MB | 144.5 MB |

In total about 720 MB (719,724,389 bytes) of logs and observations are not
committed.

Runs 4 and 5 leave out their `results.jsonl` and the logs, observations and
replay logs under `<out>/{noise4,diffs4}`. Run 6 leaves out the same, under
`<out>/{cov-master,cov-fixed,noise,min3}` (1.4 MB of `results.jsonl` on master).

`run-5-v2-diffs/replay-against.txt` is pr-check output as written, so its log
paths still name the host directories.
