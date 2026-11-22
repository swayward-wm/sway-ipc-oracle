"""Identify the fatal failure in a sway log (the crash signature) and its key.
"""

import re
import signal


# The bug type ends before the variable part: " on <address>", ": <details>" or " (pc ...".
ASAN_ERROR = re.compile(r"^==\d+==ERROR: AddressSanitizer: ([^:(]+?)(?: on |:| \(|$)")


# A stack frame; unsymbolized frames ("#1 0x... (/lib.so+0x39a)") have no " in <function>".
ASAN_FRAME = re.compile(r"^\s*#\d+ 0x[0-9a-fA-F]+(?: in (\S+))?(?: (.*))?$")


DETAIL_LINES = 30


def crash_signature(log_text: str, exit_code) -> dict:
    """Identify the fatal failure in a sway log: {"kind", "frames", "key", "detail"}.

    kind "asan": the last ASan ERROR block is the fatal one (UBSan runs with
    halt_on_error=0, so its runtime errors never are). frames are the first
    three in-sway function names of that block's stack, or the first three
    symbolized of any path if none is in sway (an unsymbolized frame is part
    of the stack but names nothing); no line numbers, so the key survives source
    line shifts between base and head. key is "<TYPE>: f1 < f2 < f3".
    kind "signal": no ASan report; key from exit_code: "signal:<NAME>" for a
    negative code, "exit:<code>" otherwise, "unresponsive" for None (alive
    but not answering IPC). frames are empty. detail is the 30 lines from the
    ASan block, or the last 30 log lines.
    """
    lines = log_text.splitlines()
    start = next((i for i in range(len(lines) - 1, -1, -1) if ASAN_ERROR.match(lines[i])), None)
    if start is None:
        if exit_code is None:
            key = "unresponsive"
        elif exit_code < 0:
            try:
                key = f"signal:{signal.Signals(-exit_code).name}"
            except ValueError:
                key = f"signal:{-exit_code}"
        else:
            key = f"exit:{exit_code}"
        return {"kind": "signal", "frames": [], "key": key,
                "detail": "\n".join(lines[-DETAIL_LINES:])}
    bug = ASAN_ERROR.match(lines[start]).group(1)
    stack = []  # (function or None, path) of the first stack after the ERROR line
    for line in lines[start + 1:]:
        frame = ASAN_FRAME.match(line)
        if frame:
            stack.append((frame.group(1), frame.group(2) or ""))
        elif stack:
            break
    named = [(func, path) for func, path in stack if func]
    in_sway = [func for func, path in named if "/sway/" in path or path.startswith("../sway/")]
    frames = (in_sway or [func for func, _ in named])[:3]
    return {"kind": "asan", "frames": frames, "key": f"{bug}: {' < '.join(frames)}",
            "detail": "\n".join(lines[start:start + DETAIL_LINES])}


def crash_key(result):
    return result["signature"]["key"] if result["outcome"] == "crashed" else None
