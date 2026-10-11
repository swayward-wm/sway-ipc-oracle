# Run the oracle in your compositor's CI

This guide adds the oracle to a compositor's CI, so a pull request that
changes how the compositor answers i3/sway IPC fails before it merges. It
assumes the oracle already has an adapter for your compositor. If it does not,
read [Adding a compositor](adding-a-compositor.md) first.

[swayward](https://github.com/swayward-wm/swayward) runs the oracle this way
on every push. Its `contrib/fetch-oracle`, `contrib/targeted-oracle` and
`.github/workflows/ci.yml` are a complete working example.

## How it works

The oracle compares your compositor against sway 1.12's recorded replies.
Your compositor will not match sway on every row, and it does not have to. CI
checks for change, not for perfection:

1. Keep a baseline: a result file that records what your compositor did at a
   known-good commit.
2. On each pull request, run the same corpus against the new build.
3. Fail only on rows that matched in the baseline and mismatch now.

Rows that mismatched before and still mismatch are known differences. Rows
that mismatched before and match now are fixes. Update the baseline when you
accept either.

## Pin the oracle

Pin the oracle at an exact commit in your repository, so an oracle change
never breaks your CI without a commit on your side:

```toml
# tests/oracle.toml
repo = "https://github.com/swayward-wm/sway-ipc-oracle.git"
commit = "<40-hex oracle commit>"
```

Fetch it with a shallow clone of that commit:

```sh
cache=.cache/sway-ipc-oracle
repo=$(awk -F '"' '$1 ~ /^repo = / { print $2 }' tests/oracle.toml)
commit=$(awk -F '"' '$1 ~ /^commit = / { print $2 }' tests/oracle.toml)
[ -d "$cache/.git" ] || { git init -q "$cache"; git -C "$cache" remote add origin "$repo"; }
git -C "$cache" fetch --depth 1 origin "$commit"
git -C "$cache" checkout -q --detach FETCH_HEAD
```

To move to a newer oracle, change the commit and regenerate your baseline in
the same change.

## Point the oracle at your build

The runners measure only committed, clean builds of the commit named in the
oracle's `pins.toml`. The runner finds the commit by walking up from the
binary to its git checkout. Most adapters also check the commit in the
compositor's `GET_VERSION` reply after start; your adapter's README says how
it checks. So in CI:

- Build from a clean checkout, and keep the binary inside it. A
  `CARGO_TARGET_DIR` outside the checkout breaks the commit lookup.
- Before a run, set your compositor's line in the fetched oracle's
  `pins.toml` to the commit under test. Leave its `[snapshot]` name
  unchanged.
- If your adapter checks `GET_VERSION`, make sure your build reports the
  commit it was built from, as sway does (`1.12-88869399`).

```sh
head=$(git rev-parse HEAD)
sed -i "s/^mycompositor = \"[0-9a-f]\{40\}\"$/mycompositor = \"$head\"/" \
  .cache/sway-ipc-oracle/pins.toml
```

## Pick the corpora

Each corpus costs a different amount of CI time. Start with the cheap ones.

| Corpus | Command | What it catches |
| --- | --- | --- |
| State | `sway-ipc-run scenarios` | Tree, workspace and output replies after a command sequence |
| Events | `sway-ipc-run scenarios --corpus events` | Event order and payloads |
| Command fuzz | `sway-ipc-run command-fuzz` | Crashes, hangs and wrong replies on malformed commands |
| Wire fuzz | `sway-ipc-run wire-fuzz` | Crashes and hangs on broken IPC framing |
| Random | `sway-ipc-run random` | Behaviour along 500 captured 20-step command sequences |
| i3-derived | `sway-ipc-run i3-derived` | 418 window-tree states reached by i3's own tests |
| i3 suite | `i3-suite-run` | i3's 242 unchanged test files |

The fuzz corpora are the cheapest useful first step: a crash or hang is a bug
on any compositor, with or without a baseline. The i3 suite and i3-derived
corpora take the longest. Swayward runs them in a slower job, not on every
pull request.

To run a few scenarios, pass `--scenario NAME` once for each.
`contrib/targeted-oracle` in swayward picks scenarios from the paths a pull
request changes, through a map in `tests/oracle-targets.toml`.

## Run a corpus

Always pass `--out`. Without it, the runner writes to the committed snapshot
path inside the oracle checkout.

```sh
oracle=.cache/sway-ipc-oracle
"$oracle/contrib/sway-ipc-run" command-fuzz --compositor mycompositor \
  --binary "$PWD/target/release/mycompositor" --out results/command-fuzz.toml
```

The runner exits 0 when every row matches, 1 when any row mismatches,
crashes or hangs, and 2 when the harness itself fails. For a compositor with
known differences, exit 1 is the normal case. Let the result file decide, not
the exit code.

Each run needs:

- Python 3.11 or later. The runners use only the standard library.
- `foot`, which the scenarios use as the client window.
- A C compiler, `pkg-config`, `wayland-scanner`, and the `wayland-client` and
  `wayland-protocols` development packages. Without them, the size-hint and
  taskbar scenarios report not applicable.
- A user systemd instance. Outside the oracle container, each compositor runs
  in a `systemd-run --user --scope` with a 2 GiB memory cap. GitHub's Ubuntu
  runners have one. In a container without systemd, set `ORACLE_CONTAINER=1`.

## Compare with the baseline

A result file is TOML. Each row has a key and a `verdict`:

```toml
[[result]]
scenario = "split_toggle_on_empty_workspace"
request = "tree"
verdict = "match"
```

The key is `scenario` and `request` for the state and events corpora, `case`
for the fuzz corpora, and `seed` for the random corpus. To compare, load both
files, key each row, and fail on every key whose verdict is `match` in the
baseline and is anything else now:

```python
import sys, tomllib

def verdicts(path):
    """Map each row's key to its verdict. Random rows group seeds that fail alike."""
    out = {}
    for r in tomllib.load(open(path, "rb")).get("result", []):
        if "seed" in r:
            for seed in r.get("seeds", [r["seed"]]):
                out[seed] = r["verdict"]
        else:
            out[r.get("case") or (r["scenario"], r["request"])] = r["verdict"]
    return out

before, now = verdicts(sys.argv[1]), verdicts(sys.argv[2])
new = sorted(str(k) for k, v in now.items() if v != "match" and before.get(k) == "match")
print("\n".join(f"NEW {k}" for k in new))
sys.exit(1 if new else 0)
```

Swayward's `contrib/targeted-oracle` does the same in its `compare()`
function, and also reports known and fixed rows.

To see why a row differs, read its `differences` list. Each entry names a
field path and both values, sway's first:

```toml
differences = ["$tree.layout: 'splith' != 'horizontal'"]
```

## Keep the baseline honest

- Commit the baseline to your repository, beside `tests/oracle.toml`.
- Regenerate it only from a clean build of a commit on your main branch.
- When a pull request fixes rows, update the baseline in the same pull request.
  The diff then shows exactly which rows it fixed.
- When you change behaviour on purpose, update the baseline and say why in
  the commit message.

## Publish a snapshot

CI needs only your own baseline. A published snapshot in this repository is a
separate step. It is measured in the pinned container, every non-match is
classified with a source citation, and your maintainers get a courtesy note
first. Read [Reproducing the results](reproducing.md) and
[CONTRIBUTING.md](../CONTRIBUTING.md) for that process.
