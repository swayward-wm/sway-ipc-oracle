#!/usr/bin/env python3
"""Measure how far explored pr-check seeds get toward crash 4's precondition.

For each settled state (observations.jsonl) compute:
  H  a hidden scratchpad toplevel exists
  HS a hidden scratchpad toplevel that is a split (has child nodes)
  MT a mark on a hidden scratchpad toplevel (early-return case, not crash 4)
  MC a mark on a strict descendant of a hidden scratchpad toplevel (crash-4 target)
  F  focused node is a floating toplevel
and for the command sent next: is it 'move container to mark <m>' and does <m> name an MC mark.
"""
import json, re, sys
from collections import Counter
from pathlib import Path

def scratch_toplevels(tree):
    for out in tree.get("nodes", []):
        if out.get("name") != "__i3": continue
        for ws in out.get("nodes", []):
            if ws.get("name") == "__i3_scratch":
                yield from ws.get("floating_nodes", [])

def descendants(node):
    for k in ("nodes", "floating_nodes"):
        for c in node.get(k, []):
            yield c
            yield from descendants(c)

def focused_floating_toplevel(tree):
    def walk(n, parent):
        if n.get("focused"):
            return n.get("type") == "floating_con" and parent is not None and parent.get("type") == "workspace"
        for k in ("nodes", "floating_nodes"):
            for c in n.get(k, []):
                r = walk(c, n)
                if r is not None: return r
        return None
    return bool(walk(tree, None))

def state(tree):
    tops = list(scratch_toplevels(tree))
    mt = {m for t in tops for m in t.get("marks", [])}
    mc = {m for t in tops for d in descendants(t) for m in d.get("marks", [])}
    return {"H": bool(tops), "HS": any(t.get("nodes") for t in tops), "MT": mt, "MC": mc,
            "F": focused_floating_toplevel(tree)}

MOVE_MARK = re.compile(r"^(?:\[.*?\]\s*)?move (?:container |window )?(?:to )?mark (\S+)$")

def main(dirs):
    seeds = Counter(); steps = Counter()
    for d in map(Path, dirs):
        rows = {}
        for line in open(d / "results.jsonl"):
            r = json.loads(line)
            if r["phase"] == "explore": rows[(r["side"], r["seed"])] = r
        for (side, seed), r in rows.items():
            obs = d / "seeds" / f"{side}-{seed}" / "observations.jsonl"
            if not obs.exists(): continue
            cmds = r["commands"]
            got = set()
            seeds["seeds"] += 1
            if any(MOVE_MARK.match(c.split(";")[-1].strip()) for c in cmds): got.add("cmd move-to-mark anywhere")
            for line in open(obs):
                o = json.loads(line)
                s = state(o["tree"]); i = o["step"]
                nxt = cmds[i] if i < len(cmds) else None
                keys = []
                if s["H"]: keys.append("H hidden scratchpad")
                if s["HS"]: keys.append("HS hidden split")
                if s["MT"]: keys.append("MT mark on hidden toplevel")
                if s["MC"]: keys.append("MC mark on hidden child")
                if s["MC"] and s["F"]: keys.append("MC+F floating focused")
                # Approximate: counts any next move-to-mark, not only one naming
                # the hidden mark (the regex capture is not compared to MC/MT).
                m = MOVE_MARK.match(nxt.split(";")[-1].strip()) if nxt else None
                if m and s["MC"]: keys.append("MC + next move-to-mark")
                if m and s["MC"] and s["F"]: keys.append("MC+F + next move-to-mark")
                if m and s["MT"]: keys.append("MT + next move-to-mark")
                for k in keys: steps[k] += 1
                got.update(keys)
            for k in got: seeds[k] += 1
    print(f"seeds with observations: {seeds['seeds']}")
    for k in sorted(set(seeds) - {"seeds"}):
        print(f"  {k:32s} seeds {seeds[k]:5d}  steps {steps[k]:6d}")

if __name__ == "__main__":
    main(sys.argv[1:])
