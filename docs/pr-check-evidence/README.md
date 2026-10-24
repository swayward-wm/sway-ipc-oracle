# pr-check gating runs

These are the three real gating runs from the pr-check spec ("Gating runs"),
run on 2026-10-24. Each directory holds the run's `report.txt`,
`results.jsonl` and `run.json` exactly as pr-check wrote them. The per-seed
logs and observations are not committed because of their size (see
[Not committed](#not-committed)).

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

Requirement, as amended by the orchestrator: every crash found is classified
correctly, and `workspace_add_floating` is checked by a targeted replay.
**Met.**

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

`workspace_add_floating` was not reached by 600 v3 seeds; its classification
was checked by `--replay` of the known reproducer
(`run-2-todays-branch/workspace-add-floating/commands.json`: one floating,
split, marked window sent to the scratchpad, then a second floating window
moved to that mark). On master the replay crashed at step 8 with
`SEGV: workspace_add_floating < container_move_to_workspace <
container_move_to_container` (exit 1). On sway-noroot it survived (exit 0).
So the fix is in the head build, and pr-check would classify the crash as
fixed if exploration reached it. This crash was originally found with v3
seed 40167 under an older generator. With the current generator, base seed
40167 survives (checked with `--seed 40166 --seeds 1 --also-base 1`).

`container_get_gaps` is unreachable by design: it needs two commands sent
back to back with no settling between them, and pr-check waits for the tree
to settle after every command.

The original requirement named `workspace_add_floating` as a fixed key that
had to appear. The orchestrator amended it after this run, because that
requirement was a guess about generator coverage, not a property of
pr-check.

## Run 3: planted regression (base fixed, head master)

The spec amendment: head is unmodified master and base is the 5-commit fixed
build, so every master crash should be judged new. Requirement: every master
crash key is new, and each `repro.sh` is verified, or unverified with counts;
at least one verified. **Met: 5 new, 5 verified.**

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
