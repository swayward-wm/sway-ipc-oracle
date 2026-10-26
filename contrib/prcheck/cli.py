"""Base-vs-head sway crash check: reports crashes that are new in head.

Both binaries are first started once (preflight). Phase 1 runs the random-v3
generator against head alone, one fresh sway per seed, and records each
seed's commands (symbolic, resolved and as sent), its settled observations
and its outcome; --also-base N then explores up to N more seeds (numbered
after head's) with base as the explorer. Phase 2 judges every crashed seed:
its symbolic list is replayed twice on its explorer and twice on the other
binary and classified new, pre-existing, blocked, unconfirmed or harness (see
judge.classify()); for base-explored seeds "new" is reported as "fixed". Phase 3
minimises every new crash, renders the minimised list as repro.sh and runs
that script twice on head and twice on base (see minimise.minimise()).
With --diffs, every head seed that survived is also replayed once on base
right after it is explored, and its observations are compared step by step
(see behaviour.py); after phase 3 one seed per difference group is
minimised and verified. Differences are reported but never change the exit
code.

Budget (see budget.plan_budget()): --minutes M is the whole run's wall time.
Exploration starts no seed after 60% of it (head and base 30% each with
--also-base); judging and minimising get the rest. A candidate not judged by
the end is "unjudged"; a new one out of time is unminimised and reported
with its full explored list (its best partial reduction, if any, goes to
best.json). --minutes is at least 1; the budget is checked before each
binary's startup check. --seeds N explores exactly N head seeds with no wall
limit and ignores --minutes.

The report goes to stdout and, with per-crash listings, to out/report.txt.
Exit 2: a binary failed to start, foot is missing, the budget ran out during
preflight, no seed was explored or more than 5% of explored seeds had a
harness run (explore, any judge replay or any minimise replay or script run);
else 1: a new or an unjudged crash; else 0.
Under --out:

  run.json                          binaries' measured provenance, argv, start, budget
  results.jsonl                     one row per finished seed, judgement or minimisation, appended as it ends
  report.txt                        the report with every crash's listing
  preflight/<side>.log              the startup check's compositor log
  seeds/<side>-<seed>/explore.log   the compositor log
  seeds/<side>-<seed>/observations.jsonl  one settled observation per step
  seeds/<side>-<seed>/judge-<head|base>-<1|2>.log  the replays' compositor logs
  seeds/head-<seed>/{min-<k>,final}-*.log  minimisation probes and the final check
  new-<n>/{commands.json,resolved.json,sent.json,signature.txt,repro.sh,repro-*.log}
  new-<n>/best.json                 an out-of-time candidate's best partial reduction (unverified)
  seeds/head-<seed>/diff-base{.log,-observations.jsonl}  --diffs: the base replay
  seeds/head-<seed>/diff-*-{head,base}.log  --diffs: difference minimisation probes and checks
  diff-<n>/{commands.json,resolved.json,sent.json}  --diffs: difference group n's minimised list

--replay out/new-<n>/commands.json --binary <sway> replays one list once;
--replay out/diff-<n>/commands.json --binary <head> --against <base> replays it
once on each and prints the first difference.
sequence.run_sequence() is the per-sequence loop shared by exploration and replay.
"""

import argparse
import datetime
import itertools
import json
import math
import os
from pathlib import Path
import sys
import tempfile
import time

from . import behaviour, coverage, explore, judge, minimise, sequence
from .budget import plan_budget
from .oracle import runner
from .report import exit_code, render_report, summarise
from .signature import crash_key


def replay_main(path, binary, timeout, out):
    """--replay: replay a commands.json once on binary; exit 0 survived, 1 crashed, 2 harness."""
    spec = json.loads(Path(path).read_text())
    out = Path(out) if out else Path(tempfile.mkdtemp(prefix="pr-check-replay-"))
    log = out / "replay.log"
    result = sequence.replay(binary, spec["commands"], spec["outputs"], log, timeout)
    key = crash_key(result)
    print(f"{result['outcome']}; step {result['step']}; key {key}"
          + (f" (expected {spec['key']})" if spec.get("key") and key != spec["key"] else "")
          + (f"; error {result['error']}" if result["error"] else "") + f"; log {log}")
    return {"survived": 0, "crashed": 1}.get(result["outcome"], 2)


def replay_against_main(path, head, base, timeout, out):
    out = Path(out) if out else Path(tempfile.mkdtemp(prefix="pr-check-replay-"))
    out.mkdir(parents=True, exist_ok=True)
    return behaviour.replay_against(Path(path), head, base, timeout, out)


def executable(text):
    """An existing executable file, made absolute so env/timeout never search PATH."""
    path = Path(text)
    if not path.is_file() or not os.access(path, os.X_OK):
        raise argparse.ArgumentTypeError(f"not an executable file: {text}")
    return path.resolve()


def minutes_arg(text):
    """--minutes: a number of at least 1."""
    try:
        value = float(text)
    except ValueError:
        raise argparse.ArgumentTypeError(f"not a number: {text}") from None
    if not value >= 1:
        raise argparse.ArgumentTypeError(f"must be at least 1, got {text}")
    return value


def load_rows(out):
    with open(Path(out) / "results.jsonl") as results:
        return [json.loads(line) for line in results if line.strip()]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--base", type=executable, help="base sway binary")
    parser.add_argument("--head", type=executable, help="head sway binary")
    parser.add_argument("--out", type=Path,
                        help="output directory (new or empty; with --replay, default a new tempdir)")
    parser.add_argument("--minutes", type=minutes_arg, default=15,
                        help="wall minutes for the whole run, at least 1 (ignored with --seeds)")
    parser.add_argument("--seeds", type=int, default=None,
                        help="explore exactly this many head seeds, with no wall limit")
    parser.add_argument("--also-base", type=int, default=0, metavar="N",
                        help="explore up to N more seeds with base as the explorer (fixed crashes)")
    parser.add_argument("--seed", type=int, default=0, help="first seed")
    parser.add_argument("--steps", type=int, default=40, help="commands per seed")
    parser.add_argument("--jobs", type=int, default=max(1, (os.cpu_count() or 1) // 4))
    parser.add_argument("--timeout", type=int, default=60,
                        help="wall seconds for one compositor run")
    parser.add_argument("--replay", type=Path, metavar="COMMANDS_JSON",
                        help="replay an out/new-<n>/commands.json once on --binary and print the outcome")
    parser.add_argument("--binary", type=executable, help="sway binary for --replay")
    parser.add_argument("--against", type=executable, metavar="BASE",
                        help="with --replay: also replay on this binary and print the first difference")
    parser.add_argument("--diffs", action="store_true",
                        help="also replay each survived head seed on base and report behaviour differences")
    args = parser.parse_args(argv)
    if args.replay:
        if not args.binary:
            parser.error("--replay needs --binary")
        if args.against:
            sequence.MAP_SETTLE = sequence.DIFF_MAP_SETTLE
            return replay_against_main(args.replay, args.binary, args.against, args.timeout, args.out)
        return replay_main(args.replay, args.binary, args.timeout, args.out)
    missing = [f"--{name}" for name in ("base", "head", "out") if getattr(args, name) is None]
    if missing:
        parser.error(f"the following arguments are required: {', '.join(missing)}")
    if args.out.exists() and (not args.out.is_dir() or any(args.out.iterdir())):
        parser.error(f"--out must be a new or empty directory: {args.out}")
    if args.seeds is not None and args.seeds < 0:
        parser.error("--seeds must be >= 0")
    try:
        plan = plan_budget(args.minutes, args.also_base, args.jobs) if args.seeds is None else None
    except ValueError as error:
        parser.error(str(error))
    if args.diffs:
        sequence.MAP_SETTLE = sequence.DIFF_MAP_SETTLE
    start = time.monotonic()
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "results.jsonl").touch()
    cfg, hinted_disabled = explore.make_cfg(args.timeout)
    run = {
        "argv": sys.argv if argv is None else ["pr-check", *argv],
        "start": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
        "out": str(args.out), "jobs": args.jobs, "seeds": args.seeds, "also_base": args.also_base,
        "diffs": args.diffs, "map_settle": sequence.MAP_SETTLE,
        "minutes": None if plan is None else args.minutes, "budget": plan,
        "base": runner.binary_provenance(args.base),
        "head": runner.binary_provenance(args.head),
        "hinted_disabled": hinted_disabled,
        "extra_recipes": [recipe["name"] for recipe in coverage.EXTRA_RECIPES],
        "foot_missing": sequence.foot_missing(), "startup": {}, "preflight_expired": False,
    }

    def at(offset):
        return math.inf if plan is None or offset is None else start + offset

    if not run["foot_missing"]:
        # One startup check at a time, none started after the run's deadline.
        for side, binary in (("base", args.base), ("head", args.head)):
            if time.monotonic() > at(plan and plan["run"]):
                run["preflight_expired"] = True
                break
            run["startup"][side] = explore.preflight(binary, args.out, args.timeout, side)
    (args.out / "run.json").write_text(json.dumps(run, indent=2) + "\n")

    if (not run["foot_missing"] and not run["preflight_expired"]
            and not any(run["startup"].values())):
        if plan is None:
            head_seeds = range(args.seed, args.seed + args.seeds)
        else:
            head_seeds = itertools.count(args.seed)
        try:
            rows = explore.explore(args.head, head_seeds, args.steps, args.out, cfg, args.jobs, "head",
                           at(plan and plan["head_explore"]), args.base if args.diffs else None)
            if args.also_base:
                first = args.seed + len(rows)
                rows += explore.explore(args.base, range(first, first + args.also_base), args.steps,
                                args.out, cfg, args.jobs, "base", at(plan and plan["base_explore"]))
            judged = judge.judge_all(rows, args.base, args.head, args.out, cfg, args.jobs,
                               at(plan and plan["run"]))
            minimise.minimise_all(rows, judged, args.base, args.head, args.out, cfg, args.jobs,
                         at(plan and plan["run"]))
            if args.diffs:
                behaviour.minimise_all(load_rows(args.out), args.base, args.head, args.out, cfg,
                                       args.jobs, at(plan and plan["run"]))
        except KeyboardInterrupt:
            print(f"interrupted; finished rows are in {args.out / 'results.jsonl'}", file=sys.stderr)
            return 130
    rows = load_rows(args.out)
    wall = time.monotonic() - start
    (args.out / "report.txt").write_text(render_report(run, rows, wall, details=True))
    sys.stdout.write(render_report(run, rows, wall))
    return exit_code(run, summarise(rows))
