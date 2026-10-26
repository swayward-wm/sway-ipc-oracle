# Run a first check

Clone the oracle and run every command below from the clone's root:

```sh
git clone https://github.com/swayward-wm/sway-ipc-oracle.git
cd sway-ipc-oracle
```

Set the input variables to absolute paths on your machine. Output goes to
`target/`, never the committed snapshots. Start each run and its `wait` in
the same shell: `wait` only knows that shell's background jobs.

## Check a sway PR

Have two sway builds ready: `BASE` before the change and `HEAD` with it.
Build each checkout [with ASan](pr-check.md#why-asan-matters), for useful
crash signatures:

```sh
meson setup build -Db_sanitize=address,undefined -Dbuildtype=debug && meson compile -C build
```

You need Python 3.11+, foot and a monospace font; see
[requirements](pr-check.md#requirements).

```sh
BASE=/path/to/sway-base/build/sway/sway
HEAD=/path/to/sway-head/build/sway/sway
OUT="$PWD/target/pr-check-$(date +%Y%m%d-%H%M%S)"
mkdir -p "$OUT"
./contrib/pr-check --base "$BASE" --head "$HEAD" --out "$OUT" > "$OUT.log" 2>&1 &
PID=$!
```

The run takes 15 minutes by default (`--minutes`). It starts about one sway
per four CPU cores at once (`--jobs`), each with its foot windows.
Progress is in `$OUT/results.jsonl`.

Run `wait "$PID"; echo "$?"` to get the exit code. Then read `$OUT.log` (the
summary) and `$OUT/report.txt`. Exit 1 means new or unjudged crashes, 2 a
harness problem, 130 an interruption.

[Read the report](pr-check.md#reading-the-report) before calling a crash a regression.
Passing does not prove safety: see [test limits](pr-check.md#what-it-does-not-test)
and [gating evidence](pr-check-evidence/README.md).

Missing dependencies? [Build the pinned container](reproducing.md) and build
both sway checkouts inside it, so they link against its libraries.
This checks crashes only.

Use regular clones, not git worktrees.
[The gating builds](pr-check-evidence/README.md#binaries) show the commands.

## Measure your compositor

Start with malformed commands: crashes and hangs are useful without a baseline.
Adapters exist for i3, sway, swayward, swayfx, scroll, miracle-wm and swirl.
For another compositor, [add an adapter](adding-a-compositor.md); tests stay unchanged.

Sway is accepted only at the captured reference pin; use pr-check for sway changes.

Set `COMPOSITOR` to your adapter's key in `pins.toml` (the example uses
`swayward`). Set `SOURCE` to its clean, committed checkout and `BINARY` to
your build inside that checkout.

Check [requirements](ci.md#run-a-corpus) and
[adapter notes](../sway-ipc/adapters/).

```sh
COMPOSITOR=swayward
SOURCE=/path/to/swayward
BINARY=/path/to/compositor/binary
COMMIT=$(git -C "$SOURCE" rev-parse HEAD)
OLD=$(grep -x "$COMPOSITOR = \"[0-9a-f]\{40\}\"" pins.toml)
sed -i "s/^$COMPOSITOR = \"[0-9a-f]\{40\}\"$/$COMPOSITOR = \"$COMMIT\"/" pins.toml
grep -x "$COMPOSITOR = \"$COMMIT\"" pins.toml || echo "pin edit failed"
OUT="$PWD/target/command-fuzz.toml"
mkdir -p "$(dirname "$OUT")"
./contrib/sway-ipc-run command-fuzz --compositor "$COMPOSITOR" \
  --binary "$BINARY" --out "$OUT" > "$OUT.log" 2>&1 &
PID=$!
```

`OLD` keeps the previous pin line. The second `grep` prints the new one. If
it prints `pin edit failed`, fix `COMPOSITOR` before reading the result.

Run `wait "$PID"; echo "$?"`, then read `$OUT.log` and `$OUT`. Exit 1 means a
mismatch, crash or hang; 2 means the run could not start or the setup is wrong
(for example a dirty checkout or a pin mismatch).

Not every mismatch is a bug. Save the result, then undo only your local pin
edit before validating the committed snapshots. This restores the `OLD` line
and keeps any other edits to `pins.toml`:

```sh
sed -i "s/^$COMPOSITOR = \"$COMMIT\"$/$OLD/" pins.toml
```

Your own host is fine for checking your own build. Published snapshots must
be measured in the [pinned container](reproducing.md), so that every
compositor gets the same libraries, fonts and clients.

Next, [choose more corpora](ci.md#pick-the-corpora) and
[keep a CI baseline](ci.md#compare-with-the-baseline) to gate on new differences.
To check published pins rather than your build, [reproduce a snapshot](reproducing.md).
