"""Phase 3: delta-debug every new crash, render and verify its repro.sh.
"""

import json
import math
import time

from . import pool, repro, sequence
from .oracle import runner
from .signature import crash_key


class _Deadline(Exception):
    """The minimise deadline passed; raised by the predicate to stop minimize_commands."""


VERIFY_RUNS = 2


def minimise(row, judged, base, head, out, deadline, *, n, timeout, counts=None):
    """Minimise a new candidate, render its repro.sh and verify the script; return its row.

    Delta-debugs row's commands with the predicate: one head replay crashed
    with key S (the judge's head_key), then one base replay survived (base
    is skipped when head did not). Harness replays count as not reproduced.
    The list is then replayed VERIFY_RUNS x head (key S each) and
    VERIFY_RUNS x base (survived each), the "reduced" check; if that fails
    the full list is checked the same way, the "fallback" check (row
    "fallback" says why). Each check has its own logs and its counts in
    counts.replay.<label> (null if it did not run). The last head replay
    with key S gives resolved.json and sent.json, sent is rendered to
    repro.sh, and the script is run VERIFY_RUNS x on head and on base:
    "verified" if head crashed with S and base survived every time, else
    "unverified"; "needs-fixture" if the list has an xdg-hinted step.
    Every replay and script run first checks the deadline: once
    time.monotonic() > deadline it raises _Deadline instead of starting, so
    at most the one replay in flight overruns. The candidate then ends
    "unminimised" with the full explored list (and the explore record's
    resolved and sent) and nothing further is started; counts of a check cut
    short are not recorded and no repro.sh is kept. If an accepted probe
    shortened the list and no fallback started, that best list so far goes
    to best.json (unverified) and the row's "partial" is its length, else
    None. counts.harness counts every harness replay and script run,
    including those of a check cut short. counts (the row's, filled in as
    replays finish) may be passed in so a caller keeps it if minimise raises.
    Writes out/new-<n>/{commands.json, resolved.json, sent.json,
    signature.txt, repro.sh?, best.json?, repro-*.log}; replay logs go to
    out/seeds/head-<seed>/{min-<k>-{head,base},final-<label>-{head,base}-<i>}.log.
    """
    key = judged["head_key"]
    outputs = row["outputs"]
    seed_dir = out / "seeds" / f"head-{row['seed']}"
    new_dir = out / f"new-{n}"
    new_dir.mkdir(parents=True, exist_ok=True)
    original = list(row["commands"])
    best = {"commands": original, "head": None}
    if counts is None:
        counts = new_counts()

    def guarded(run, *args):
        if time.monotonic() > deadline:
            raise _Deadline
        result = run(*args)
        counts["harness"] += result["outcome"] == "harness"
        return result

    def reproduces(candidate):
        k = counts["probes"] + 1
        result = guarded(sequence.replay, head, candidate, outputs, seed_dir / f"min-{k}-head.log", timeout)
        counts["probes"] = k
        harness, ok = result["outcome"] == "harness", False
        if crash_key(result) == key:
            other = guarded(sequence.replay, base, candidate, outputs, seed_dir / f"min-{k}-base.log", timeout)
            harness, ok = other["outcome"] == "harness", other["outcome"] == "survived"
        counts["probe_harness"] += harness
        if ok:
            best.update(commands=list(candidate), head=result)
        return ok

    def final_check(commands, label):
        heads = [guarded(sequence.replay, head, commands, outputs,
                         seed_dir / f"final-{label}-head-{i}.log", timeout)
                 for i in range(1, VERIFY_RUNS + 1)]
        bases = ([guarded(sequence.replay, base, commands, outputs,
                          seed_dir / f"final-{label}-base-{i}.log", timeout)
                  for i in range(1, VERIFY_RUNS + 1)]
                 if all(crash_key(result) == key for result in heads) else [])
        counts["replay"][label] = check = {"head": repro.tally(heads, key), "base": repro.tally(bases, key)}
        return check, next((r for r in reversed(heads) if crash_key(r) == key), None)

    def write_list(commands, last_head):
        record = last_head or row  # the explore record when no head replay of this list crashed with S
        signature = (last_head or {}).get("signature") or row.get("signature") or {}
        (new_dir / "commands.json").write_text(json.dumps(
            {"commands": commands, "outputs": outputs, "key": key}, indent=2) + "\n")
        (new_dir / "resolved.json").write_text(json.dumps(record["resolved"], indent=2) + "\n")
        (new_dir / "sent.json").write_text(json.dumps(record["sent"], indent=2) + "\n")
        (new_dir / "signature.txt").write_text(f"{key}\n\n{signature.get('detail', '')}\n")
        return record

    minimised, fallback, commands, partial = True, None, original, None
    try:
        runner.minimize_commands(original, reproduces)
        commands = best["commands"]
        check, final_head = final_check(commands, "reduced")
        if not repro.reproduced(check["head"], check["base"]) and commands != original:
            fallback = (f"the minimised list ({len(commands)} commands) did not reproduce "
                        f"(head {check['head']}, base {check['base']}); using the full list")
            minimised, commands = False, original
            check, final_head = final_check(commands, "fallback")
        if not repro.reproduced(check["head"], check["base"]) and fallback is None:
            fallback = "the final list did not reproduce; repro.sh is rendered from it anyway"
        last_head = final_head or (best["head"] if commands == best["commands"] else None)
        record = write_list(commands, last_head)
        header = {"base": runner.binary_provenance(base), "head": runner.binary_provenance(head),
                  "key": key, "seed": row["seed"]}
        text = repro.render_repro(record["sent"], outputs, header)
        if text is None:
            state = "needs-fixture"
        else:
            script = new_dir / "repro.sh"
            script.write_text(text)
            script.chmod(0o755)
            runs = {label: [guarded(repro.run_script, binary, script, outputs,
                                    new_dir / f"repro-{label}-{i}.log", timeout)
                            for i in range(1, VERIFY_RUNS + 1)]
                    for label, binary in (("head", head), ("base", base))}
            counts["script"] = {label: repro.tally(results, key) for label, results in runs.items()}
            state = ("verified" if repro.reproduced(counts["script"]["head"], counts["script"]["base"])
                     else "unverified")
    except _Deadline:
        # The full list is the report's; a reduction whose reduced check failed is no partial.
        minimised, state, commands = False, "unminimised", original
        write_list(original, None)
        (new_dir / "repro.sh").unlink(missing_ok=True)
        if not fallback and best["commands"] != original:
            partial = len(best["commands"])
            (new_dir / "best.json").write_text(json.dumps(
                {"commands": best["commands"], "outputs": outputs, "key": key}, indent=2) + "\n")
    return {"phase": "minimise", "side": "head", "seed": row["seed"], "n": n, "key": key,
            "length": len(commands), "minimised": minimised, "repro": state,
            "fallback": fallback, "partial": partial, "counts": counts,
            "dir": str(new_dir.relative_to(out))}


def new_counts():
    return {"probes": 0, "probe_harness": 0, "replay": {"reduced": None, "fallback": None},
            "script": None, "harness": 0}


def minimise_task(task):
    """minimise(); if it raises, an unminimised row with the error and the counts so far
    (so harness replays before the error still count toward the harness share)."""
    row, judged, base, head, out, deadline, n, timeout = task
    counts = new_counts()
    try:
        return minimise(row, judged, base, head, out, deadline, n=n, timeout=timeout,
                        counts=counts)
    except Exception as error:
        return {"phase": "minimise", "side": "head", "seed": row["seed"], "n": n,
                "key": judged.get("head_key"), "length": len(row["commands"]),
                "minimised": False, "repro": "unminimised", "fallback": None,
                "partial": None, "counts": counts, "dir": f"new-{n}", "error": f"{type(error).__name__}: {error}"}


def minimise_deadline(now, run_deadline, remaining):
    """A new candidate's minimise deadline when it starts with remaining candidates not started."""
    return min(run_deadline, now + max(60.0, (run_deadline - now) / remaining))


def minimise_all(rows, judged, base, head, out, cfg, jobs, run_deadline=math.inf):
    """Minimise every new head-side judgement in a pool; new-<n> numbered by seed.

    Each candidate's deadline is minimise_deadline() at the moment it starts.
    """
    explored = {(row["side"], row["seed"]): row for row in rows}
    new = sorted((row for row in judged
                  if row["outcome"] == "new" and row.get("side", "head") == "head"),
                 key=lambda row: row["seed"])

    def tasks():
        for n, row in enumerate(new, 1):
            deadline = minimise_deadline(time.monotonic(), run_deadline, len(new) - n + 1)
            yield (explored[("head", row["seed"])], row, base, head, out, deadline, n,
                   cfg["timeout"])
    return pool.pooled(minimise_task, tasks(), out, cfg, jobs)
