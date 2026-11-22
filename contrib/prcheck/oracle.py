"""The sway-ipc-run runner and the random-v3 generator, loaded once.

sway-ipc-run has no .py suffix, so it is loaded by path; it imports
sway_ipc_v3 from contrib/ itself.
"""

import importlib.machinery
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
runner = importlib.machinery.SourceFileLoader(
    "sway_ipc_run", str(ROOT / "contrib/sway-ipc-run")
).load_module()
v3 = runner.sway_ipc_v3
