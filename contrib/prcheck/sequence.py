"""Run one command list on one fresh unpinned sway and classify the outcome.

The layer under exploration, judging, minimising and --replay: run_sequence()
is the per-sequence loop they share; replay() runs a recorded symbolic list.
"""

import argparse
import json
from pathlib import Path
import shutil
import signal
import tempfile
import time

from .oracle import runner, v3
from .signature import crash_signature


# Exits of the timeout wrapper (124, 137) and a SIGKILL from it or a scope OOM
# kill: the harness ended sway, sway did not crash. Sway never SIGKILLs itself.
HARNESS_EXITS = frozenset({124, 137, -signal.SIGKILL})


SETTLE = 0.3          # grace after the last step: sway crashes a transaction after replying


FAILURE_SETTLE = 0.5  # grace after a step raised, before deciding whether sway died


DYING_GRACE = 5.0     # an unresponsive sway may still be writing its ASan report


# --diffs sets MAP_SETTLE to DIFF_MAP_SETTLE before any run starts (pool workers fork after).
# A step that maps a window is then observed only once the tree and workspaces have been
# unchanged for that long. random_observation's settle (two equal reads 50 ms apart) can
# return before the new window's first transaction applies: sway waits up to
# txn_timeout_ms (200 ms, sway/server.c:701) for the client's ack, and a same-binary
# --diffs run saw 2 of 295 seeds with border/current_border_width of a just-mapped window
# from before it. 0 (crash-only runs): unchanged.
DIFF_MAP_SETTLE = 0.3
MAP_SETTLE = 0.0
MAP_POLL = 0.05
MAP_SETTLE_LIMIT = 5.0  # a map step whose state keeps changing this long raises


class Generated:
    """v3 commands chosen online from the settled state of the compositor being driven."""
    def __init__(self, gen, steps):
        self.gen, self.steps, self.prelude = gen, steps, gen.prelude()

    def next(self, step, state):
        if step > self.steps:
            return None
        if step <= len(self.prelude):
            return self.prelude[step - 1]
        return self.gen.next(v3.features(state["tree"], state["workspaces"]), step)

    def observe(self, text, observation):
        self.gen.observe_reply(text, observation["command"])


class Fixed:
    """A recorded symbolic list, replayed as is (tokens resolve against the live tree)."""
    def __init__(self, commands):
        self.commands = list(commands)

    def next(self, step, state):
        return self.commands[step - 1] if step <= len(self.commands) else None

    def observe(self, text, observation):
        pass


def layout_for(outputs):
    return {"outputs": 2, "output_layout": v3.TWO_OUTPUT_LAYOUT} if outputs == 2 else None


def new_record():
    return {"commands": [], "resolved": [], "sent": []}


def run_steps(adapter, source, record, observed=None):
    """Drive one started adapter until source is exhausted; raise on the first failing step.

    Every step is resolved before it is executed, and its symbolic, resolved
    and sent texts are appended to record first, so after a raise
    len(record["commands"]) is the step that failed (a failure while
    resolving step k leaves k-1: nothing of step k reached sway).
    observed(step, observation) is called for every settled step.
    """
    state = {request: runner.ipc(adapter.socket, request) for request in ("tree", "workspaces")}
    step = 1
    while (text := source.next(step, state)) is not None:
        resolved = (v3.resolve_con_tokens(runner.ipc(adapter.socket, "tree"), text)
                    if "@con:" in text else text)
        record["commands"].append(text)
        record["resolved"].append(resolved)
        record["sent"].append(adapter.translate_command(resolved))
        state = runner.random_observation(adapter, resolved)
        if MAP_SETTLE and resolved.startswith(("exec foot ", "xdg-hinted ")):
            state = settle_map(adapter, state)
        source.observe(text, state)
        if observed is not None:
            observed(step, state)
        step += 1


def settle_map(adapter, state):
    """state, re-read until the tree and workspaces are unchanged for MAP_SETTLE seconds."""
    def read():
        return {request: runner.ipc(adapter.socket, request) for request in ("tree", "workspaces")}

    def key(value):
        return json.dumps([value["tree"], value["workspaces"]], sort_keys=True)
    start = time.monotonic()
    stable, last = start, key(state)
    while time.monotonic() - stable < MAP_SETTLE:
        if time.monotonic() - start > MAP_SETTLE_LIMIT:
            raise RuntimeError("mapped window state did not settle")
        time.sleep(MAP_POLL)
        current = read()
        if key(current) != last:
            state, stable, last = {**current, "command": state["command"]}, time.monotonic(), key(current)
    return state


def liveness(adapter, settle):
    """(dead, exit_code) after settle seconds; exit_code is None for an unresponsive sway."""
    time.sleep(settle)
    code = adapter.process.poll() if adapter.process else None
    if code is not None:
        return True, code
    try:
        runner.ipc(adapter.socket, "version")
        return False, None
    except (OSError, RuntimeError, ValueError):
        return True, runner.exited_code(adapter, grace=DYING_GRACE)


def foot_missing():
    return shutil.which("foot") is None


def run_sequence(binary, layout, source, record, log_path, timeout, observed=None):
    """Start one fresh unpinned sway, run source on it and classify the outcome.

    Returns {"outcome": "survived"|"crashed"|"harness", "step", "error",
    "exit_code"}. crashed: sway exited (any code but HARNESS_EXITS) or stopped
    answering IPC; step is the step after which the death was seen. harness:
    startup failed, a step failed while sway stayed alive, or the wrapper
    killed sway. record fills in place (see run_steps). The log is kept.
    """
    return run_on_sway(binary, layout, lambda adapter: run_steps(adapter, source, record, observed),
                       log_path, timeout, SETTLE, lambda: len(record["commands"]))


def run_on_sway(binary, layout, drive, log_path, timeout, settle, step=lambda: None):
    """Start one fresh unpinned sway, call drive(adapter) and classify the outcome.

    The setup and outcome rules of run_sequence; settle is the grace after
    drive returns, step() names the step a crash or failure was seen at.
    """
    def result(outcome, step=None, error=None, exit_code=None):
        return {"outcome": outcome, "step": step, "error": error, "exit_code": exit_code}

    if foot_missing():
        return result("harness", error="missing foot")
    args = argparse.Namespace(binary=Path(binary), timeout=timeout, unpinned=True)
    try:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log = open(log_path, "w")
    except OSError as error:
        return result("harness", error=f"could not open the log: {type(error).__name__}: {error}")
    # A short run directory: the Wayland socket path must stay under 100 bytes.
    with log, tempfile.TemporaryDirectory(prefix="pc-", dir="/tmp") as run_dir:
        adapter = None
        try:
            try:
                adapter = runner.differential_adapter("sway", args, Path(run_dir), layout)
                adapter.start(log)
                reply = adapter.set_differential_mode()
                if not reply or not reply[0].get("success"):
                    raise RuntimeError(f"could not set the output mode: {reply}")
            except Exception as error:
                return result("harness", error=f"startup failed: {error}")
            failure = None
            try:
                drive(adapter)
            except Exception as error:
                failure = f"{type(error).__name__}: {error}"
            dead, code = liveness(adapter, FAILURE_SETTLE if failure else settle)
            if dead and code in HARNESS_EXITS:
                return result("harness", step(), failure or f"killed by the harness (exit {code})", code)
            if dead:
                return result("crashed", step(), failure, code)
            if failure:
                return result("harness", step(), failure)
            return result("survived")
        finally:
            if adapter is not None:
                adapter.stop()


def observation_line(step, state):
    """One observations.jsonl entry: the settled state after step."""
    return {"step": step, "reply": state["command"], "tree": state["tree"],
            "workspaces": state["workspaces"]}


def signature_of(outcome, log):
    """crash_signature of a crashed run_sequence outcome's log, else None.

    run_sequence took exit_code before stopping sway and closed the log after.
    """
    if outcome["outcome"] != "crashed":
        return None
    return crash_signature(log.read_text(errors="replace"), outcome["exit_code"])


def replay(binary: Path, commands: list, outputs: int, out_log: Path, timeout: int,
           keep_observations: bool = False) -> dict:
    """Replay a recorded symbolic list once on a fresh sway (the exploring setup and loop).

    Returns run_sequence's outcome, step, error and exit_code, plus signature
    (crashed only) and the commands, resolved and sent records of this replay.
    keep_observations adds "observations": the observations.jsonl entries
    explore would have written for this run, one per settled step.
    """
    record = new_record()
    observations = []
    observed = ((lambda step, state: observations.append(observation_line(step, state)))
                if keep_observations else None)
    outcome = run_sequence(binary, layout_for(outputs), Fixed(commands), record, out_log, timeout,
                           observed)
    result = {**outcome, "signature": signature_of(outcome, out_log), **record}
    if keep_observations:
        result["observations"] = observations
    return result
