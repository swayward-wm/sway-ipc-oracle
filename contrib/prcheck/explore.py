"""Phase 1: explore random-v3 seeds on one binary, and the startup check.
"""

import json
import math
from pathlib import Path
import shutil
import subprocess

from . import behaviour, coverage, pool, sequence
from .oracle import v3


def explore_seed(binary: Path, seed: int, steps: int, out: Path, cfg: dict,
                 side: str = "head") -> dict:
    """Explore one v3 seed on binary; return its results.jsonl row (log relative to out)."""
    seed_dir = out / "seeds" / f"{side}-{seed}"
    seed_dir.mkdir(parents=True, exist_ok=True)
    log = seed_dir / "explore.log"
    gen = v3.V3Generator(seed, cfg["vocabulary"], cfg["recipes"], "auto", steps)
    record = sequence.new_record()
    with open(seed_dir / "observations.jsonl", "w") as observations:
        def observed(step, state):
            observations.write(json.dumps(sequence.observation_line(step, state)) + "\n")
            observations.flush()
        outcome = sequence.run_sequence(binary, gen.scenario(), sequence.Generated(gen, steps), record, log,
                               cfg["timeout"], observed)
    return {"phase": "explore", "side": side, "seed": seed, "outputs": gen.outputs,
            **record, **outcome, "signature": sequence.signature_of(outcome, log),
            "log": str(log.relative_to(out))}


def explore_task(task):
    """The explore row of one seed; with diff_base, [explore row, diff row] for a survived seed."""
    binary, seed, steps, out, side, diff_base = task
    try:
        row = explore_seed(binary, seed, steps, out, pool.CFG, side)
    except Exception as error:
        return {"phase": "explore", "side": side, "seed": seed, "outputs": None,
                **sequence.new_record(), "outcome": "harness", "step": None,
                "error": f"{type(error).__name__}: {error}", "exit_code": None,
                "signature": None,
                "log": str(Path("seeds", f"{side}-{seed}", "explore.log"))}
    if diff_base is None or row["outcome"] != "survived":
        return row
    try:
        diff = behaviour.diff_seed(row, diff_base, out, pool.CFG["timeout"])
    except Exception as error:
        diff = {"phase": "diff", "side": side, "seed": seed, "outcome": "harness",
                "difference": None, "error": f"{type(error).__name__}: {error}"}
    return [row, diff]


def explore(binary, seeds, steps, out, cfg, jobs, side="head", deadline=math.inf, diff_base=None):
    """Explore seeds (possibly endless) in a pool, none started after deadline; one row per seed.

    diff_base: a base binary; each survived seed is then also replayed on it
    and compared (behaviour.diff_seed), its diff row appended to
    results.jsonl but not returned.
    """
    tasks = ((binary, seed, steps, out, side, diff_base) for seed in seeds)
    rows = pool.pooled(explore_task, tasks, out, cfg, jobs, deadline)
    return [row for row in rows if row["phase"] == "explore"]


def missing_fixture_toolchain():
    """The first missing piece of the hinted fixture client's toolchain, or None.

    The same checks as WaylandAdapter.fixture_client, without compiling.
    """
    for tool in ("pkg-config", "wayland-scanner", "cc"):
        if shutil.which(tool) is None:
            return tool
    for package in ("wayland-protocols", "wayland-client"):
        if subprocess.run(["pkg-config", "--exists", package], check=False).returncode:
            return package
    return None


def make_cfg(timeout):
    """(cfg, hinted_disabled): the shared run config; hinted windows off if the toolchain is missing.

    The recipes are random-v3's plus pr-check's own (coverage.EXTRA_RECIPES).
    """
    vocabulary, recipes = v3.load_v3()
    recipes = coverage.with_extra_recipes(recipes)
    missing = missing_fixture_toolchain()
    if missing:
        vocabulary = {**vocabulary, "hinted_fraction": 0}
    return {"timeout": timeout, "vocabulary": vocabulary, "recipes": recipes}, missing


def preflight(binary, out, timeout, side):
    """None if binary starts and answers IPC on a fresh sway, else why not."""
    result = sequence.run_sequence(binary, None, sequence.Fixed([]), sequence.new_record(),
                          out / "preflight" / f"{side}.log", timeout)
    if result["outcome"] == "survived":
        return None
    return f"{result['outcome']}: {result['error'] or 'exit ' + str(result['exit_code'])}"
