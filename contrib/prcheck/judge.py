"""Phase 2: judge every crashed seed by replaying it on both binaries.
"""

import math
import time

from . import pool, sequence
from .signature import crash_key


JUDGE_REPLAYS = 2


def classify(key, explorer, other):
    """Outcome of a candidate with explore signature key, from 2 replays per side; first match wins.

    harness: any replay is harness. unconfirmed: the explorer did not crash
    with key in both replays. With H the explorer's earliest step for key:
    blocked: the other side crashed at a step before H, with another key, or
    in only one replay (its crash hides or muddles the explorer's).
    pre-existing: the other side crashed with key in both, at steps >= H.
    new: the other side survived both.
    """
    if any(result["outcome"] == "harness" for result in explorer + other):
        return "harness"
    confirmed = [result["step"] for result in explorer if crash_key(result) == key]
    if len(confirmed) < len(explorer):
        return "unconfirmed"
    first = min(confirmed)
    crashed = [result for result in other if result["outcome"] == "crashed"]
    if not crashed:
        return "new"
    if len(crashed) < len(other) or any(result["step"] < first or crash_key(result) != key
                                        for result in crashed):
        return "blocked"
    return "pre-existing"


def judge(row, explorer_binary, other_binary, out, timeout, replays=JUDGE_REPLAYS,
          deadline=math.inf):
    """Judge a crashed explore row: replay its commands on the explorer, then the other binary.

    The row's side names the explorer ("head" or "base"); the other binary is
    the other side. Returns the results.jsonl judge row (see judge_row). A
    replay that raises stops the judgement: the row is harness with error set
    and keeps the replays completed before it. Every replay first checks the
    deadline: once time.monotonic() > deadline the row is "unjudged" with the
    replays completed so far, so at most the replay in flight overruns.
    """
    side = row.get("side", "head")
    other_side = "base" if side == "head" else "head"
    seed_dir = out / "seeds" / f"{side}-{row['seed']}"
    results = {side: [], other_side: []}
    error = None
    try:
        for label, binary in ((side, explorer_binary), (other_side, other_binary)):
            for n in range(1, replays + 1):
                if time.monotonic() > deadline:
                    return judge_row(row, results, replays, unjudged=True)
                results[label].append(sequence.replay(binary, row["commands"], row["outputs"],
                                             seed_dir / f"judge-{label}-{n}.log", timeout))
    except Exception as exc:
        error = f"{type(exc).__name__}: {exc}"
    return judge_row(row, results, replays, error)


def judge_row(row, results, replays, error=None, unjudged=False):
    """The judge row for row from results ({side: completed replays}); one schema always.

    outcome is unjudged when unjudged is set, harness when error is set, else
    classify, with "new" renamed "fixed" for a base-explored row (base
    crashes, head survives). "<explorer>_key" is
    the explore signature key. Per side, outcomes, keys (None unless crashed)
    and steps hold one entry per replay, None for a replay that raised or did
    not run. error is present only when set.
    """
    side = row.get("side", "head")
    other_side = "base" if side == "head" else "head"
    key = (row.get("signature") or {}).get("key")
    outcome = ("unjudged" if unjudged else "harness" if error
               else classify(key, results[side], results[other_side]))
    if side == "base" and outcome == "new":
        outcome = "fixed"
    judged = {"phase": "judge", "side": side, "seed": row["seed"], "outcome": outcome,
              f"{side}_key": key}
    for label in ("head", "base"):
        done = results[label]
        missing = [None] * (replays - len(done))
        judged[f"{label}_outcomes"] = [result["outcome"] for result in done] + missing
        judged[f"{label}_keys"] = [crash_key(result) for result in done] + missing
        judged[f"{label}_steps"] = [result["step"] for result in done] + missing
    if error:
        judged["error"] = error
    return judged


def judge_task(task):
    row, explorer_binary, other_binary, out, deadline = task
    try:
        return judge(row, explorer_binary, other_binary, out, pool.CFG["timeout"], deadline=deadline)
    except Exception as error:
        return judge_row(row, {"head": [], "base": []}, JUDGE_REPLAYS,
                         f"{type(error).__name__}: {error}")


def judge_all(rows, base, head, out, cfg, jobs, deadline=math.inf):
    """Judge every crashed explore row in a pool, head-explored first; one row per candidate.

    A row is replayed on its side's binary, then the other's (see judge).
    """
    binaries = {"head": head, "base": base}
    crashed = sorted((row for row in rows if row["outcome"] == "crashed"),
                     key=lambda row: (row["side"] != "head", row["seed"]))
    tasks = [(row, binaries[row["side"]], binaries["base" if row["side"] == "head" else "head"],
              out, deadline) for row in crashed]
    return pool.pooled(judge_task, tasks, out, cfg, jobs)
