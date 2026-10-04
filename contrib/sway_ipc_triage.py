"""Triage classifications for the swayward sway-IPC corpora.

Classifications are review metadata keyed to raw result rows, one file per
result: case for fuzz, scenario.request rows for state, events and
i3-derived, seeds for random. They cannot classify a match or invent a row.
A [basis] table records the newer unpinned measurement a triage was made
from; its `match` lists measured mismatches that matched there. Every other
measured mismatch without a classification is untriaged, and the count is
reported per corpus. Every expected corpus of the pinned swayward snapshot
needs both a result and a classification file.

check(root, names) raises SystemExit on the first problem and otherwise
returns the per-snapshot untriaged count lines. contrib/validate calls it;
contrib/tests/sway-ipc-triage exercises it on a copy of the repository.
"""
import tomllib
from pathlib import Path

ALLOWED_TRIAGE = {"swayward bug", "documented deviation", "harness issue"}
CORPUS_KEYS = {"state": "rows", "events": "rows", "i3-derived": "rows", "random": "seeds",
               "command-fuzz": "case", "wire-fuzz": "case"}


def mismatches(doc, corpus):
    found = []
    for row in doc.get("result", []):
        if row["verdict"] != "mismatch":
            continue
        if corpus == "random":
            found += row.get("seeds") or [row["seed"]]
        elif corpus.endswith("-fuzz"):
            found.append(row["case"])
        else:
            found.append(f"{row['scenario']}.{row['request']}")
    return found


def check(root, names):
    root = Path(root)
    results_dir = root / "sway-ipc/results"
    classification_dir = root / "sway-ipc/classifications"
    lines = []
    known_classifications = set()
    for compositor, name in names.items():
        if compositor in ("i3", "sway"):
            continue  # i3 reports differs; sway is the reference and cannot mismatch
        counts = []
        for corpus, field in CORPUS_KEYS.items():
            stem = name if corpus == "state" else f"{name}-{corpus}"
            result_path = results_dir / f"{stem}.toml"
            path = classification_dir / f"{stem}.toml"
            if not result_path.exists():
                raise SystemExit(f"{result_path}: missing {corpus} result for {name}")
            if not path.exists():
                raise SystemExit(f"{result_path}: no classification file {path}")
            measured = mismatches(tomllib.load(result_path.open("rb")), corpus)
            if len(measured) != len(set(measured)):
                raise SystemExit(f"{result_path}: duplicate mismatch rows")
            doc = tomllib.load(path.open("rb"))
            known_classifications.add(path.name)
            basis = doc.get("basis")
            basis_match = set()
            if basis is not None:
                for key in ("swayward", "oracle", "measurement"):
                    if not basis.get(key):
                        raise SystemExit(f"{path}: [basis] has no {key}")
                basis_match = set(basis.get("match", []))
                if len(basis_match) != len(basis.get("match", [])) or basis_match - set(measured):
                    raise SystemExit(f"{path}: [basis] match must list distinct measured mismatches")
            seen = set()
            for row in doc.get("classification", []):
                keys = [row.get(field)] if field == "case" else row.get(field)
                if not keys or not isinstance(keys, list) or None in keys:
                    raise SystemExit(f"{path}: classification has no {field}")
                for key in keys:
                    if key in seen:
                        raise SystemExit(f"{path}: duplicate classification for {key}")
                    seen.add(key)
                    if key not in measured:
                        raise SystemExit(f"{path}: {key} does not name a measured mismatch")
                    if key in basis_match:
                        raise SystemExit(f"{path}: {key} matched in [basis] and is classified")
                if row.get("triage") not in ALLOWED_TRIAGE:
                    raise SystemExit(f"{path}: {keys[0]} has invalid triage {row.get('triage')!r}")
                for key in ("finding", "reason", "source"):
                    if not row.get(key):
                        raise SystemExit(f"{path}: {keys[0]} has no {key}")
                if row["triage"] == "documented deviation" and "KNOWN_DEVIATIONS.md#" not in row["source"]:
                    raise SystemExit(f"{path}: documented deviation {keys[0]} cites no KNOWN_DEVIATIONS anchor")
            open_rows = len(measured) - len(basis_match)
            note = f", {len(basis_match)} match in basis" if basis is not None else ""
            counts.append(f"{corpus} {open_rows - len(seen)} of {open_rows}{note}")
        lines.append(f"{name} untriaged sway-IPC mismatches: " + "; ".join(counts))
    stray = {p.name for p in classification_dir.glob("*.toml")} - known_classifications
    if stray:
        raise SystemExit(f"{classification_dir}: classifications without a result: {sorted(stray)}")
    return lines
