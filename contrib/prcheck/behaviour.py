"""--diffs: replay each head-explored list on base, report and minimise behaviour differences.

diff_seed() runs in the explore task right after a head seed is explored
(so --minutes budgets a seed's exploration and its base replay together): it
replays the seed's symbolic list once on base, keeping base's observations,
and compares them step by step with head's observations.jsonl under the
exact rules of diffs.py. Only seeds head survived are replayed. The diff
row's outcome is "same", "differ", "harness" (the base replay was a harness
run) or "base-crashed" (not compared: a base-only crash is what
--also-base looks for, and the crash check owns crashes).

minimise_all() then takes one seed per group (diffs.group(): the same
causing command shape and path shape; the seed whose difference comes
earliest) and delta-debugs its list up to the differing step with the
predicate: one head replay and one base replay, both survive, and their
first difference is diffs.same_difference() as the seed's (the exact path
and values, not just the group). The result is
checked VERIFY_RUNS times (a head and a base replay each, the same
difference every time): "verified", else the full prefix is checked the
same way ("fallback"); if that fails too the group is "unconfirmed".
Differences never change the exit code; their harness replays count
toward the harness share like any other.
"""

import json
import math
import time

from . import diffs, pool, sequence
from .minimise import minimise_deadline
from .oracle import runner


VERIFY_RUNS = 2


class _Deadline(Exception):
    """The group's minimise deadline passed."""


def read_observations(path):
    with open(path) as lines:
        return [json.loads(line) for line in lines if line.strip()]


def diff_seed(row, base, out, timeout):
    """The diff row of an explored head row: one base replay compared with head's observations."""
    seed_dir = out / "seeds" / f"head-{row['seed']}"
    result = sequence.replay(base, row["commands"], row["outputs"], seed_dir / "diff-base.log",
                             timeout, keep_observations=True)
    observations = result.pop("observations")
    with open(seed_dir / "diff-base-observations.jsonl", "w") as saved:
        saved.writelines(json.dumps(entry) + "\n" for entry in observations)
    head = read_observations(seed_dir / "observations.jsonl")
    diff = {"phase": "diff", "side": "head", "seed": row["seed"], "base_outcome": result["outcome"],
            "base_step": result["step"], "steps": min(len(head), len(observations))}
    if result["outcome"] != "survived":  # a base crash is --also-base's business
        return {**diff, "outcome": "harness" if result["outcome"] == "harness" else "base-crashed",
                "difference": None, "error": result["error"]}
    difference = diffs.first_difference(head, observations, row["commands"])
    return {**diff, "outcome": "differ" if difference else "same", "difference": difference}


def compare(head, base, commands, outputs, logs, timeout, guarded=lambda run, *args: run(*args)):
    """(difference or None, head result, base result) of one head and one base replay of commands.

    logs: (head log, base log). The difference is None unless both survived.
    """
    results = [guarded(sequence.replay, binary, commands, outputs, log, timeout, True)
               for binary, log in zip((head, base), logs)]
    if any(result["outcome"] != "survived" for result in results):
        return None, *results
    return diffs.first_difference(results[0]["observations"], results[1]["observations"],
                                  commands), *results


def minimise(row, diff, base, head, out, deadline, *, n, timeout, counts=None):
    """Minimise group n's representative (explore row, diff row); return its diff-minimise row.

    The predicate and checks are those of the module docstring. Writes
    out/diff-<n>/commands.json ({"commands", "outputs", "difference"}: the
    final list and the difference its last verifying run saw, else the
    seed's) and, when verified, resolved.json and sent.json of that run's
    head replay. Replay logs go to out/seeds/head-<seed>/diff-{min-<k>,
    <reduced|fallback>-<i>}-{head,base}.log. Every replay first checks the
    deadline; past it the group is "unminimised" with the full prefix (the
    seed's list up to its differing step) and nothing else starts.
    """
    target = diff["difference"]
    prefix = row["commands"][:target["step"]]
    outputs, seed_dir = row["outputs"], out / "seeds" / f"head-{row['seed']}"
    new_dir = out / f"diff-{n}"
    new_dir.mkdir(parents=True, exist_ok=True)
    counts = new_counts() if counts is None else counts
    best = {"commands": prefix}

    def guarded(run, *args):
        if time.monotonic() > deadline:
            raise _Deadline
        result = run(*args)
        counts["harness"] += result["outcome"] == "harness"
        return result

    def logs(name):
        return [seed_dir / f"diff-{name}-{label}.log" for label in ("head", "base")]

    def reproduces(candidate):
        counts["probes"] += 1
        found, *_ = compare(head, base, candidate, outputs, logs(f"min-{counts['probes']}"),
                            timeout, guarded)
        if found is not None and diffs.same_difference(found, target):
            best["commands"] = list(candidate)
            return True
        return False

    def check(commands, label):
        hits, last = 0, None
        for i in range(1, VERIFY_RUNS + 1):
            found, head_result, _ = compare(head, base, commands, outputs, logs(f"{label}-{i}"),
                                            timeout, guarded)
            if found is not None and diffs.same_difference(found, target):
                hits, last = hits + 1, (found, head_result)
        counts["verify"][label] = hits
        return hits == VERIFY_RUNS, last

    def write(commands, found=None, head_result=None):
        (new_dir / "commands.json").write_text(json.dumps(
            {"commands": commands, "outputs": outputs, "difference": found or target}, indent=2) + "\n")
        for name in ("resolved", "sent"):
            if head_result is not None:
                (new_dir / f"{name}.json").write_text(json.dumps(head_result[name], indent=2) + "\n")

    state, commands, fallback = "unconfirmed", prefix, False
    try:
        runner.minimize_commands(prefix, reproduces)
        commands = best["commands"]
        ok, last = check(commands, "reduced")
        if not ok and commands != prefix:
            commands, fallback = prefix, True
            ok, last = check(commands, "fallback")
        state = "verified" if ok else "unconfirmed"
        write(commands, *(last if ok else ()))
    except _Deadline:
        state, commands = "unminimised", prefix
        write(prefix)
    return {"phase": "diff-minimise", "side": "head", "seed": row["seed"], "n": n,
            "key": list(diffs.group_key(target)), "length": len(commands), "fallback": fallback,
            "state": state, "counts": counts, "dir": str(new_dir.relative_to(out))}


def new_counts():
    return {"probes": 0, "harness": 0, "verify": {"reduced": None, "fallback": None}}


def minimise_task(task):
    row, diff, base, head, out, deadline, n, timeout = task
    counts = new_counts()
    try:
        return minimise(row, diff, base, head, out, deadline, n=n, timeout=timeout, counts=counts)
    except Exception as error:
        return {"phase": "diff-minimise", "side": "head", "seed": row["seed"], "n": n,
                "key": list(diffs.group_key(diff["difference"])), "length": diff["difference"]["step"],
                "fallback": False, "state": "unminimised", "counts": counts, "dir": f"diff-{n}",
                "error": f"{type(error).__name__}: {error}"}


def minimise_all(rows, base, head, out, cfg, jobs, run_deadline=math.inf):
    """Minimise one representative per difference group, group n = diffs.group() order."""
    explored = {row["seed"]: row for row in rows if row["phase"] == "explore" and row["side"] == "head"}
    groups = diffs.group(row for row in rows if row["phase"] == "diff")

    def tasks():
        for n, members in enumerate(groups, 1):
            diff = members["rows"][0]
            deadline = minimise_deadline(time.monotonic(), run_deadline, len(groups) - n + 1)
            yield (explored[diff["seed"]], diff, base, head, out, deadline, n, cfg["timeout"])
    return pool.pooled(minimise_task, tasks(), out, cfg, jobs)


def replay_against(path, head, base, timeout, out):
    """--replay ... --against: one replay on each binary, print the first difference.

    Exit 0 the same, 1 a difference, 2 a replay did not survive.
    """
    spec = json.loads(path.read_text())
    found, head_result, base_result = compare(head, base, spec["commands"], spec["outputs"],
                                              (out / "replay-head.log", out / "replay-base.log"),
                                              timeout)
    if head_result["outcome"] != "survived" or base_result["outcome"] != "survived":
        print(f"not compared: head {head_result['outcome']}, base {base_result['outcome']}; logs {out}")
        return 2
    if found is None:
        print(f"same; logs {out}")
        return 0
    expected = spec.get("difference")
    note = ("" if expected is None or diffs.same_difference(found, expected)
            else f" (expected {expected['path']}: {diffs.value_text(expected['head'])} != "
                 f"{diffs.value_text(expected['base'])})")
    print(f"differ; {difference_text(found)}{note}; logs {out}")
    return 1


def difference_text(difference):
    """'step k (<command>): <path>: head <v>, base <v>'"""
    return (f"step {difference['step']} ({difference['command']}): {difference['path']}: "
            f"head {diffs.value_text(difference['head'])}, base {diffs.value_text(difference['base'])}")
