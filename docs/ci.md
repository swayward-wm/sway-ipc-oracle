# Run the oracle in your compositor's CI

CI gates on new differences, not a perfect match with sway. Known differences
do not fail the gate.

Keep a result from a known-good commit and run the same corpus on each PR.
Fail when a previously matching row stops matching or any row starts to crash
or hang.

## Run a corpus

After [pinning the oracle](#pin-the-oracle) and [pointing it at your build](#point-the-oracle-at-your-build),
run this from your compositor checkout. Set the adapter name and binary path:

```sh
COMPOSITOR=swayward
BINARY="$PWD/target/release/swayward"
ORACLE="$PWD/.cache/sway-ipc-oracle"
OUT="${OUT:-$PWD/target/oracle}"
mkdir -p "$OUT/tmp"
export TMPDIR="$OUT/tmp"
"$ORACLE/contrib/sway-ipc-run" command-fuzz --compositor "$COMPOSITOR" \
  --binary "$BINARY" --out "$OUT/command-fuzz.toml" > "$OUT/command-fuzz.log" 2>&1 &
PID=$!
status=0; wait "$PID" || status=$?
echo "exit $status"
[ "$status" -le 1 ] || exit "$status"
```

Always pass `--out`: otherwise the runner writes into the oracle's committed
snapshots. Exit 0 means all rows match; 1 means a mismatch, crash or hang;
2 means setup or the run failed.

Known differences often give exit 1, so the step above fails only on 2.
[The baseline check](#compare-with-the-baseline) decides whether exit 1 is new.

Requirements for Wayland adapters:

- Python 3.11+, using only the standard library, and `foot` for client windows.
- A C compiler, `pkg-config`, `wayland-scanner`, and `wayland-client` and
  `wayland-protocols` development packages. Without them, size-hint and
  taskbar scenarios report not applicable.
- A user systemd instance for the runner's 2 GiB memory-capped scope.
  GitHub's Ubuntu runners have one. In a container without systemd, set
  `ORACLE_CONTAINER=1` and supply an outer memory cap.

For pinned builds and dependencies, [use the container](reproducing.md).
Check [adapter-specific requirements](../sway-ipc/adapters/), especially
SwayFX's render device. If your compositor has no adapter, see [adapter setup](adding-a-compositor.md).

## Pin the oracle

Store an exact oracle commit in your compositor repository:

```toml
# tests/oracle.toml
repo = "https://github.com/swayward-wm/sway-ipc-oracle.git"
commit = "<40-hex oracle commit>"
```

Fetch a shallow checkout from that record:

```sh
cache=.cache/sway-ipc-oracle
repo=$(awk -F '"' '$1 ~ /^repo = / { print $2 }' tests/oracle.toml)
commit=$(awk -F '"' '$1 ~ /^commit = / { print $2 }' tests/oracle.toml)
[ -d "$cache/.git" ] || { git init -q "$cache"; git -C "$cache" remote add origin "$repo"; }
git -C "$cache" fetch --depth 1 origin "$commit"
git -C "$cache" checkout -q --detach FETCH_HEAD
```

When you change the oracle pin, regenerate the baseline in the same change.
Use a regular clone for container runs; a worktree's `.git` points outside
its mount, so provenance checks need that shared Git directory mounted too.

## Point the oracle at your build

From your compositor checkout, update its source pin in the fetched oracle:

```sh
COMPOSITOR=swayward
head=$(git rev-parse HEAD)
sed -i "s/^$COMPOSITOR = \"[0-9a-f]\{40\}\"$/$COMPOSITOR = \"$head\"/" \
  .cache/sway-ipc-oracle/pins.toml
```

- Build from a clean, committed checkout and keep the binary inside it.
  The runner walks up from the binary to find its Git commit; an external
  `CARGO_TARGET_DIR` breaks that lookup.
- Change only your compositor's source pin; keep its `[snapshot]` name.
- Most adapters also check the started build's `GET_VERSION` commit
  (for example sway's `1.12-88869399`). See your adapter's version notes.
  Sway itself must stay at the captured reference pin; use [pr-check](pr-check.md) for sway PRs.

## Pick the corpora

| Corpus | What it catches |
| --- | --- |
| State | Tree, workspace and output replies after commands |
| Events | Event order and payloads |
| Command fuzz | Crashes, hangs and wrong replies to malformed commands |
| Wire fuzz | Crashes and hangs on broken IPC framing |
| Random | Behaviour along 500 captured 20-step command sequences |
| [i3-derived](results.md#how-to-read-a-block) | 416 window-tree states reached by i3 tests |
| i3 suite | i3's 242 unchanged test files; [run it separately](reproducing.md) |

Fuzzing is the cheapest useful start: crashes and hangs matter without a
baseline. The i3 suite and i3-derived runs take longest; swayward keeps them
in slower jobs rather than running them on every PR.

With the variables above, try these subsets and the wire-fuzz CI budget.
Each command has a separate output and log; run them one at a time:

```sh
"$ORACLE/contrib/sway-ipc-run" scenarios --scenario one_window \
  --compositor "$COMPOSITOR" --binary "$BINARY" --out "$OUT/state.toml" > "$OUT/state.log" 2>&1 &
PID=$!; wait "$PID"; echo "$?"
"$ORACLE/contrib/sway-ipc-run" scenarios --corpus events --scenario one_window \
  --compositor "$COMPOSITOR" --binary "$BINARY" --out "$OUT/events.toml" > "$OUT/events.log" 2>&1 &
PID=$!; wait "$PID"; echo "$?"
"$ORACLE/contrib/sway-ipc-run" wire-fuzz --compositor "$COMPOSITOR" \
  --binary "$BINARY" --out "$OUT/wire-fuzz.toml" > "$OUT/wire-fuzz.log" 2>&1 &
PID=$!; wait "$PID"; echo "$?"
"$ORACLE/contrib/sway-ipc-run" random --seeds 306 --compositor "$COMPOSITOR" \
  --binary "$BINARY" --out "$OUT/random.toml" > "$OUT/random.log" 2>&1 &
PID=$!; wait "$PID"; echo "$?"
"$ORACLE/contrib/sway-ipc-run" i3-derived --scenario 97fa75f470ff02bd \
  --compositor "$COMPOSITOR" --binary "$BINARY" --out "$OUT/i3-derived.toml" > "$OUT/i3-derived.log" 2>&1 &
PID=$!; wait "$PID"; echo "$?"
```

Remove `--scenario` or `--seeds` for a full corpus. Repeat `--scenario NAME`
to select several scenarios. i3-derived input names are bare hashes from
`scenarios.json`, not the result keys prefixed with `i3-derived/`.

Swayward's `contrib/targeted-oracle` selects scenarios from changed PR paths
using `tests/oracle-targets.toml`. Its `contrib/fetch-oracle` and
`.github/workflows/ci.yml` form a [working integration](https://github.com/swayward-wm/swayward).

## Compare with the baseline

The baseline and current result **must use the same selection**: corpus,
`--scenario`, `--seeds` and `--budget`. For targeted runs, select the same rows
from the baseline first.

The check below fails when:

- a row that matched in the baseline no longer matches;
- any row's verdict becomes `crash` or `hang`, even a known mismatch;
- the baseline has no rows, or a row is in only one of the two files.

Result rows are TOML `[[result]]` tables. State and events keys are
`(scenario, request, occurrence)`; fuzz keys are `case`; random keys are
`seed` (grouped `seeds` are expanded). Save this as `compare-oracle.py`:

```python
import sys, tomllib
from collections import Counter

def verdicts(path):
    out, occurrences = {}, Counter()
    with open(path, "rb") as stream:
        for row in tomllib.load(stream).get("result", []):
            if "seed" in row:
                for seed in row.get("seeds", [row["seed"]]):
                    out[seed] = row["verdict"]
            elif "case" in row:
                out[row["case"]] = row["verdict"]
            else:
                key = (row["scenario"], row["request"])
                out[(*key, occurrences[key])] = row["verdict"]
                occurrences[key] += 1
    return out

before, now = verdicts(sys.argv[1]), verdicts(sys.argv[2])
problems = [] if before else ["EMPTY baseline: no result rows"]
problems += [f"MISSING {k}" for k in sorted(map(str, before.keys() - now.keys()))]
problems += [f"EXTRA {k}" for k in sorted(map(str, now.keys() - before.keys()))]
for k in sorted(before.keys() & now.keys(), key=str):
    if before[k] != now[k] and (before[k] == "match" or now[k] in ("crash", "hang")):
        problems.append(f"NEW {k}: {before[k]} -> {now[k]}")
print("\n".join(problems))
sys.exit(1 if problems else 0)
```

```sh
python3 compare-oracle.py tests/oracle-baseline/command-fuzz.toml "$OUT/command-fuzz.toml"
```

A missing baseline file is an error (exit 1). A row that improves, such as a
mismatch that now matches, passes: update the baseline to keep the fix.

Read a differing row's `differences` list for field paths and both values,
sway's first: `"$tree.layout: 'splith' != 'horizontal'"`. A mismatch is not
necessarily a bug. Swayward's comparator also reports known and fixed rows.

## Update or publish the baseline

- Commit your baseline beside `tests/oracle.toml`, from a clean, committed build.
- When a PR fixes rows, update the baseline in that PR so the diff shows the fixes.
- For deliberate behaviour changes, update it and explain why in the commit.
- Keep normal refreshes tied to your main branch, not an unreviewed PR build.

CI needs only your baseline. To publish a snapshot here, measure it in the
pinned container and classify its non-matches with source citations, or leave
them visibly untriaged. Follow [reproduction](reproducing.md) and [CONTRIBUTING.md](../CONTRIBUTING.md).
