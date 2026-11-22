"""pr-check: the base-vs-head sway crash check, and with --diffs behaviour check
(entry point: contrib/pr-check).

Modules, in the order a run uses them:

  cli        argument parsing, the three phases, run.json, report.txt, the exit code
  explore    phase 1: explore random-v3 seeds on one binary; the startup check
  judge      phase 2: replay each crashed seed on both binaries and classify it
  minimise   phase 3: delta-debug each new crash, render and verify its repro.sh
  behaviour  --diffs: replay head's seeds on base, minimise one seed per difference group
  repro      the repro.sh text and running it against a fresh sway
  report     results.jsonl rows to the report text and the exit code
  budget     the --minutes plan

Below them:

  sequence   run one command list on one fresh sway and classify the outcome
  signature  the crash signature of a sway log
  diffs      the exact sway-vs-sway comparison, the first difference and its group key
  pool       the worker pool and results.jsonl appends
  oracle     the sway-ipc-run runner and the random-v3 generator
  coverage   pr-check's own random-v3 recipes, added to the committed ones
"""
