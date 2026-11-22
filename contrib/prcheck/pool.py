"""The worker pool shared by exploration, judging and minimising.
"""

import math
import multiprocessing
import queue
import json
import signal
import sys
import time


CFG = None


def init_worker(cfg):
    global CFG
    CFG = cfg
    # Ctrl-C reaches the parent, which terminates the pool; SIGTERM then unwinds
    # the worker through run_sequence's finally, so its sway is stopped.
    signal.signal(signal.SIGINT, signal.SIG_IGN)
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(143))


def append_row(out, row):
    with open(out / "results.jsonl", "a") as results:
        results.write(json.dumps(row) + "\n")
        results.flush()


def pooled(task, tasks, out, cfg, jobs, deadline=math.inf):
    """Run task over tasks in a pool of jobs workers; append each row as it finishes.

    A task returns one row, or a list of rows (each appended; the list
    counts as one finished task). tasks is any iterable, possibly endless.
    The next task is drawn only when a worker is free and time.monotonic() <
    deadline, so a generator computes a task's arguments as it starts, and no
    task starts after the deadline.
    """
    rows, tasks, end = [], iter(tasks), object()

    def draw():
        return next(tasks, end) if time.monotonic() < deadline else end

    pending = draw()
    if pending is end:
        return rows
    done = queue.SimpleQueue()
    # fork: workers inherit the loaded runner and the modules of this process.
    with multiprocessing.get_context("fork").Pool(jobs, init_worker, (cfg,)) as workers:
        running = 0
        while True:
            while pending is not end and running < jobs:
                workers.apply_async(task, (pending,), callback=done.put, error_callback=done.put)
                running += 1
                pending = draw() if running < jobs else None
            if not running:
                break
            row = done.get()
            running -= 1
            if isinstance(row, BaseException):
                raise row
            for item in row if isinstance(row, list) else [row]:
                append_row(out, item)
                rows.append(item)
            if pending is None:
                pending = draw()
        # Let idle workers exit on their own; the with-exit's terminate() (SIGTERM) is
        # for Ctrl-C and would hit workers already in their atexit handlers.
        workers.close()
        workers.join()
    return rows
