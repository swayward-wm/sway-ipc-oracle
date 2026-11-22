"""Summarise results.jsonl: the report text and the exit code.
"""

import json
from pathlib import Path

from . import diffs


JUDGE_OUTCOMES = ("new", "fixed", "pre-existing", "blocked", "unconfirmed", "harness", "unjudged")


HARNESS_SHARE = 0.05  # more explored seeds than this with a harness outcome: exit 2


NO_ASAN = ("not built with -Db_sanitize=address,undefined; crash signatures are signals "
           "only and shared crashes are weak evidence")


REPRO_TEXT = {"verified": "verified", "unverified": "unverified",
              "needs-fixture": "needs fixture client"}


def explorer_key(row):
    return row.get(f"{row.get('side', 'head')}_key")


def summarise(rows):
    """Counts and listings of a run's results.jsonl rows (explore, judge, minimise).

    Pre-existing counts distinct keys over both sides. harness counts unique
    explored seeds (side, seed) with a harness run (see harness_runs).
    """
    explored = [row for row in rows if row["phase"] == "explore"]
    judged = [row for row in rows if row["phase"] == "judge"]
    by = {outcome: sorted((row for row in judged if row["outcome"] == outcome),
                          key=lambda row: (row["side"] != "head", row["seed"]))
          for outcome in JUDGE_OUTCOMES}
    harness = {(row["side"], row["seed"]) for row in rows if harness_runs(row)}
    return {
        "explored": {side: sum(row["side"] == side for row in explored) for side in ("head", "base")},
        "seeds": len(explored),
        "by": by,
        "pre_existing_keys": sorted({explorer_key(row) or "" for row in by["pre-existing"]}),
        "harness_seeds": sorted(harness, key=lambda item: (item[0] != "head", item[1])),
        "explore": {(row["side"], row["seed"]): row for row in explored},
        "minimised": {row["seed"]: row for row in rows if row["phase"] == "minimise"},
        "diffs": [row for row in rows if row["phase"] == "diff"],
        "groups": diffs.group(row for row in rows if row["phase"] == "diff"),
        "diff_minimised": {row["n"]: row for row in rows if row["phase"] == "diff-minimise"},
    }


def harness_runs(row):
    """A row's harness runs: its explore outcome, judge replay outcomes (also of an
    unjudged row) or outcome, or a minimise row's harness replays and script runs."""
    if row["phase"] == "judge":
        outcomes = row["head_outcomes"] + row["base_outcomes"]
        return outcomes.count("harness") or int(row["outcome"] == "harness")
    if row["phase"] in ("minimise", "diff-minimise"):
        return (row.get("counts") or {}).get("harness", 0)
    return int(row["outcome"] == "harness")


def harness_exceeded(summary):
    return len(summary["harness_seeds"]) > HARNESS_SHARE * summary["seeds"]


def exit_code(run, summary):
    """2: a binary failed to start, foot is missing, the budget ran out during preflight,
    no seed explored or harness over 5% (first); 1: any new or unjudged crash; 0: otherwise."""
    if (run.get("foot_missing") or run.get("preflight_expired")
            or any((run.get("startup") or {}).values())):
        return 2
    if summary["seeds"] == 0 or harness_exceeded(summary):
        return 2
    return 1 if summary["by"]["new"] or summary["by"]["unjudged"] else 0


def describe_short(provenance):
    """'<git_head[:8]|unknown> <clean|dirty|-> <ASan|no ASan>' for the report."""
    git = provenance.get("git_head")
    state = {True: "dirty", False: "clean"}.get(provenance.get("dirty"), "-")
    return f"{git[:8] if git else 'unknown'} {state} {'ASan' if provenance.get('asan') else 'no ASan'}"


def wall_text(seconds):
    seconds = int(round(seconds))
    return f"{seconds // 60}m{seconds % 60:02d}s"


def tally_text(outcomes, keys, key):
    """'<crashed with key>/<runs>' for an explorer, '<crashed>/<runs>' when key is None."""
    runs = [outcome for outcome in outcomes if outcome is not None]
    hits = (sum(k == key for k in keys) if key is not None
            else sum(outcome == "crashed" for outcome in runs))
    return f"{hits}/{len(outcomes)}"


def new_listing(out, judged, minimised):
    """(repro text, command count, path) of a new head crash for the report."""
    key = judged["head_key"]
    head = tally_text(judged["head_outcomes"], judged["head_keys"], key)
    base = tally_text(judged["base_outcomes"], judged["base_keys"], None)
    if minimised is None:
        return f"head {head}, base {base}; not minimised", None
    path = f"{Path(out) / minimised['dir']}/"
    if minimised["repro"] in REPRO_TEXT:
        repro = f"repro.sh {REPRO_TEXT[minimised['repro']]}"
    elif minimised.get("error"):
        repro = f"no repro.sh, minimising failed: {minimised['error']}"
    else:
        repro = "no repro.sh, out of time (unminimised, full list)"
    partial = (f" (best partial reduction: {minimised['partial']} commands in best.json, unverified)"
               if minimised.get("partial") else "")
    return (f"head {head}, base {base}; {repro} ({minimised['length']} commands){partial}: {path}",
            path)


def render_report(run, rows, wall, details=False):
    """The report text for run (run.json) and rows (results.jsonl); details adds every listing."""
    summary = summarise(rows)
    by, out = summary["by"], run["out"]
    lines = [f"pr-check: base {describe_short(run['base'])}, head {describe_short(run['head'])}"]
    no_asan = [side for side in ("base", "head") if not run[side].get("asan")]
    if no_asan:
        lines.append(f"warning: {' and '.join(no_asan)} {'is' if len(no_asan) == 1 else 'are'} "
                     f"{NO_ASAN}")
    for side in ("base", "head"):
        error = (run.get("startup") or {}).get(side)
        if error:
            lines.append(f"error: {side} failed to start: {error}")
    if run.get("foot_missing"):
        lines.append("error: foot is not installed; pr-check needs it for windows")
    if run.get("preflight_expired"):
        lines.append("error: budget exhausted during preflight; rerun with a larger --minutes")
    hinted = run.get("hinted_disabled")
    lines.append(f"explored {summary['explored']['head']} seeds (head)"
                 + (f", {summary['explored']['base']} (base)" if run.get("also_base") else "")
                 + f", {wall_text(wall)}, {run['jobs']} jobs; hinted windows "
                 + (f"disabled: {hinted} not found" if hinted else "enabled"))
    if run.get("seeds") is not None:
        lines.append(f"--seeds {run['seeds']}: fixed exploration size, no wall limit "
                     "(--minutes ignored)")
    if summary["seeds"] == 0:
        lines.append("error: no seeds explored")
    elif harness_exceeded(summary):
        lines.append(f"error: {len(summary['harness_seeds'])} of {summary['seeds']} seeds had a "
                     f"harness outcome, over {HARNESS_SHARE:.0%}; the run is not a result")
    lines.append(f"NEW in head: {len(by['new'])}")
    for i, row in enumerate(by["new"], 1):
        text, _ = new_listing(out, row, summary["minimised"].get(row["seed"]))
        lines += [f"  {i}. {row['head_key']}", f"     {text}"]
    if by["unjudged"]:
        lines.append(f"{len(by['unjudged'])} crashes unjudged: rerun with a larger --minutes")
        lines += [f"  {row['side']} seed {row['seed']}: {explorer_key(row)}" for row in by["unjudged"]]
    lines.append(f"pre-existing {len(summary['pre_existing_keys'])}, fixed {len(by['fixed'])}, "
                 f"blocked {len(by['blocked'])}, unconfirmed {len(by['unconfirmed'])}, "
                 f"harness {len(summary['harness_seeds'])}. Details: {Path(out) / 'report.txt'}")
    if run.get("diffs"):
        lines += diff_summary(summary, out)
    if details:
        lines += report_details(summary, out)
        if run.get("diffs"):
            lines += diff_details(summary, out)
    return "\n".join(lines) + "\n"


def listed_commands(commands):
    return [f"       {i}. {text}" for i, text in enumerate(commands, 1)]


def report_details(summary, out):
    """report.txt's listings: every judged crash with its replays and commands, every harness seed."""
    by, lines = summary["by"], []
    for outcome in JUDGE_OUTCOMES:
        if not by[outcome]:
            continue
        lines += ["", f"== {outcome} ({len(by[outcome])}) =="]
        for row in by[outcome]:
            side, other = row["side"], "base" if row["side"] == "head" else "head"
            explored = summary["explore"].get((side, row["seed"]), {})
            key = explorer_key(row)
            lines.append(f"  {side} seed {row['seed']} ({explored.get('outputs')} outputs, "
                         f"explore crashed at step {explored.get('step')}): {key}")
            for label, label_key in ((side, key), (other, None)):
                keys = row[f"{label}_keys"]
                runs = ", ".join(f"{o}" + (f" at step {s}: {k}" if o == "crashed" else "")
                                 for o, s, k in zip(row[f"{label}_outcomes"],
                                                    row[f"{label}_steps"], keys))
                lines.append(f"     {label} {tally_text(row[f'{label}_outcomes'], keys, label_key)}: {runs}")
            if row.get("error"):
                lines.append(f"     error: {row['error']}")
            commands = explored.get("commands", [])
            minimised = summary["minimised"].get(row["seed"]) if outcome == "new" else None
            if minimised is not None:
                text, path = new_listing(out, row, minimised)
                lines.append(f"     {text.split('; ', 1)[1]}")
                if minimised.get("fallback"):
                    lines.append(f"     note: {minimised['fallback']}")
                try:
                    commands = json.loads((Path(out) / minimised["dir"] / "commands.json")
                                          .read_text())["commands"]
                except (OSError, ValueError, KeyError):
                    lines.append("     (commands.json unreadable; the explored list follows)")
            lines.append(f"     commands ({len(commands)}), replay with --replay:")
            lines += listed_commands(commands)
    if summary["harness_seeds"]:
        lines += ["", f"== harness seeds ({len(summary['harness_seeds'])}) =="]
        judged = {(row["side"], row["seed"]): row for outcome in JUDGE_OUTCOMES
                  for row in by[outcome]}
        for side, seed in summary["harness_seeds"]:
            explored = summary["explore"].get((side, seed), {})
            row = judged.get((side, seed))
            minimised = summary["minimised"].get(seed) if side == "head" else None
            if explored.get("outcome") == "harness":
                lines.append(f"  {side} seed {seed} explore at step {explored.get('step')}: "
                             f"{explored.get('error')}")
            if row is not None and harness_runs(row):
                lines.append(f"  {side} seed {seed} judge ({row['outcome']}): head "
                             f"{row['head_outcomes']}, base {row['base_outcomes']}" +
                             (f"; {row['error']}" if row.get("error") else ""))
            if minimised is not None and harness_runs(minimised):
                lines.append(f"  {side} seed {seed} minimise: {harness_runs(minimised)} harness "
                             f"replays or script runs")
    return lines


def diff_state(minimised):
    """A difference group's minimisation state for the report."""
    if minimised.get("error"):
        return f"minimising failed: {minimised['error']}"
    if minimised["state"] == "unconfirmed":
        verify = minimised["counts"]["verify"]
        runs = f"reduced {verify['reduced']}/2" + (
            f", full {verify['fallback']}/2" if verify["fallback"] is not None else "")
        return f"not reproduced ({runs}): unstable, possibly not caused by head"
    return {"verified": "verified",
            "unminimised": "out of time (unminimised, full prefix)"}[minimised["state"]]


def diff_listing(out, group, minimised):
    """(first line, second line) of a difference group for the report."""
    rows = group["rows"]
    command, path = group["key"]
    seeds = ", ".join(str(row["seed"]) for row in rows[:8]) + (", ..." if len(rows) > 8 else "")
    first = rows[0]["difference"]
    second = f"head {diffs.value_text(first['head'])}, base {diffs.value_text(first['base'])}"
    if minimised is not None:
        second += f"; {diff_state(minimised)} ({minimised['length']} commands): {Path(out) / minimised['dir']}/"
    return (f"{command} -> {path}: {len(rows)} seed{'s' if len(rows) != 1 else ''} ({seeds})",
            second)


def diff_summary(summary, out):
    """The --diffs lines of the report: the counts, then one entry per difference group."""
    rows, groups = summary["diffs"], summary["groups"]
    count = {outcome: sum(row["outcome"] == outcome for row in rows)
             for outcome in ("same", "differ", "harness", "base-crashed")}
    lines = [f"behaviour differences: {count['differ']} of {len(rows)} compared seeds in "
             f"{len(groups)} group{'s' if len(groups) != 1 else ''} (same {count['same']}, "
             f"base crashed {count['base-crashed']}, harness {count['harness']})"]
    for n, group in enumerate(groups, 1):
        first, second = diff_listing(out, group, summary["diff_minimised"].get(n))
        lines += [f"  {n}. {first}", f"     {second}"]
    return lines


def diff_details(summary, out):
    """report.txt's difference listings: every group's seeds and its minimised list."""
    lines = []
    for n, group in enumerate(summary["groups"], 1):
        command, path = group["key"]
        lines += ["", f"== difference group {n}: {command} -> {path} ({len(group['rows'])}) =="]
        for row in group["rows"]:
            difference = row["difference"]
            lines.append(f"  head seed {row['seed']} step {difference['step']} "
                         f"({difference['command']}): {difference['path']}: head "
                         f"{diffs.value_text(difference['head'])}, base "
                         f"{diffs.value_text(difference['base'])}")
        minimised = summary["diff_minimised"].get(n)
        if minimised is None:
            continue
        verify = minimised["counts"]["verify"]
        lines.append(f"     seed {minimised['seed']} minimised: {minimised['counts']['probes']} probes; "
                     f"checks reduced {verify['reduced']}, fallback {verify['fallback']} "
                     f"(of 2 each); {minimised['state']}")
        try:
            commands = json.loads((Path(out) / minimised["dir"] / "commands.json").read_text())["commands"]
        except (OSError, ValueError, KeyError):
            lines.append("     (commands.json unreadable)")
            continue
        lines.append(f"     commands ({len(commands)}), replay with --replay ... --against:")
        lines += listed_commands(commands)
    harness = [row for row in summary["diffs"] if row["outcome"] in ("harness", "base-crashed")]
    if harness:
        lines += ["", f"== seeds not compared ({len(harness)}) =="]
        lines += [f"  head seed {row['seed']}: base replay {row.get('base_outcome', row['outcome'])}"
                  + (f" at step {row['base_step']}" if row.get("base_step") else "")
                  + (f"; {row['error']}" if row.get("error") else "") for row in harness]
    return lines
