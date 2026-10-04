"""Which tracked inputs can affect a result file, and their content hash.

A result records `inputs = "<sha256>"` in its [run] table: a hash of every
tracked file that can change its measurements. `validate` recomputes it, so a
result is stale exactly when one of its inputs changed after it was generated.
The hash depends on file contents only, never on commit ids, so it survives
rebases and squashes.

A change that cannot affect a measurement (a diagnostic message, a comment)
still changes the hash. Re-stamp the affected results with
`contrib/provenance.py --restamp RESULT...` and say why in the commit message;
the reviewer sees the restamp in the diff.
"""

import hashlib
import subprocess
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def dependencies(result: Path, compositor: str) -> list[str]:
    """Tracked paths (files or directories) that can affect `result`."""
    if result.parent.name == "results" and result.parent.parent.name == "i3":
        paths = ["contrib/i3-suite-run", "i3/t", "i3/lib", "i3/unstable.toml",
                 "i3/flaky.toml", "i3/flaky-runs.toml"]
        if (ROOT / "i3/adapters" / compositor).is_dir():
            paths.append(f"i3/adapters/{compositor}")
        return paths
    paths = ["sway-ipc/normalize.toml"]
    stem = result.stem
    if stem.endswith("-i3-derived"):
        return paths + ["contrib/sway-ipc-run", "sway-ipc/i3-derived", "sway-ipc/applicability.toml"]
    if stem.endswith("-random-v2"):
        return paths + ["sway-ipc/random-v2"]
    if stem.endswith("-random"):
        return paths + ["sway-ipc/random"]
    if stem.endswith("-command-fuzz"):
        return paths + ["sway-ipc/fuzz/command-fuzz.json", "sway-ipc/fuzz/command-families.json",
                        "sway-ipc/applicability.toml"]
    if stem.endswith("-wire-fuzz"):
        return paths + ["sway-ipc/fuzz/wire-fuzz.json", "sway-ipc/applicability.toml"]
    if stem.endswith("-events"):
        return paths + ["sway-ipc/scenarios.toml", "sway-ipc/fixtures", "sway-ipc/applicability.toml"]
    return paths + ["sway-ipc/scenarios.toml", "sway-ipc/fixtures", "sway-ipc/command-coverage.toml",
                    "sway-ipc/applicability.toml"]


def inputs_hash(result: Path, compositor: str) -> str:
    """sha256 over the sorted (path, content) pairs of the result's tracked inputs.

    Working-tree contents are hashed, so the value describes what actually ran.
    """
    files = subprocess.check_output(
        ["git", "-C", ROOT, "ls-files", "-z", "--", *dependencies(result, compositor)], text=True
    ).split("\0")
    digest = hashlib.sha256()
    for name in sorted(name for name in files if name):
        digest.update(name.encode() + b"\0")
        digest.update(hashlib.sha256((ROOT / name).read_bytes()).hexdigest().encode() + b"\n")
    return digest.hexdigest()


def run_line(result: Path, compositor: str) -> str:
    return f'inputs = "{inputs_hash(result, compositor)}"'


def restamp(result: Path) -> None:
    """Rewrite one result's inputs line in place."""
    text = result.read_text()
    compositor = tomllib.loads(text)["run"]["compositor"]
    lines = text.splitlines()
    try:
        index = next(i for i, line in enumerate(lines) if line.startswith("inputs = "))
        lines[index] = run_line(result, compositor)
    except StopIteration:
        index = next(i for i, line in enumerate(lines) if line.startswith("date = "))
        lines.insert(index, run_line(result, compositor))
    result.write_text("\n".join(lines) + "\n")


if __name__ == "__main__":
    if len(sys.argv) < 3 or sys.argv[1] != "--restamp":
        raise SystemExit("usage: contrib/provenance.py --restamp RESULT...")
    for name in sys.argv[2:]:
        restamp(Path(name).resolve())
