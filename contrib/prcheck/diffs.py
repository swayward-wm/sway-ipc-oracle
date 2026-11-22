"""Behaviour differences: compare two runs' observations under the exact sway-vs-sway rules.

An observation is one observations.jsonl entry: {"step", "reply", "tree",
"workspaces"}, the settled state after a step. normalised() applies the exact
rules: the keys in DROP are deleted at any depth (runtime ids, which differ
between any two runs; gating run 1 measured foreign_toplevel_identifier as
the only other source), and every integer in a "focus" array is replaced by
its index in the sorted list of the node ids in that step's tree. Nothing
else is relaxed: none of sway-ipc/normalize.toml's tolerances apply.

A difference is the first path, in document order, where two normalised
observations differ, with both values. Its group key is the shape of the
command that caused it and the shape of the path (see group_key()); the
minimise predicate is the exact path and values (see same_difference()).
"""

import json
import re


DROP = frozenset({"id", "pid", "window", "foreign_toplevel_identifier"})


ABSENT = "(absent)"  # the value of a dict key or list element one side does not have


def node_ids(value, ids=None):
    """Every integer "id" in value, at any depth."""
    ids = set() if ids is None else ids
    if isinstance(value, dict):
        if isinstance(value.get("id"), int):
            ids.add(value["id"])
        for item in value.values():
            node_ids(item, ids)
    elif isinstance(value, list):
        for item in value:
            node_ids(item, ids)
    return ids


def normalise(value, index):
    """value without the DROP keys, focus ids mapped through index ("unknown:<id>" if absent)."""
    if isinstance(value, dict):
        return {key: ([index.get(item, f"unknown:{item}") if isinstance(item, int) else item
                       for item in item_value]
                      if key == "focus" and isinstance(item_value, list)
                      else normalise(item_value, index))
                for key, item_value in value.items() if key not in DROP}
    if isinstance(value, list):
        return [normalise(item, index) for item in value]
    return value


def normalised(observation):
    """The reply, tree and workspaces of an observation under the exact rules."""
    index = {node: n for n, node in enumerate(sorted(node_ids(observation["tree"])))}
    return {request: normalise(observation[request], index)
            for request in ("reply", "tree", "workspaces")}


def first_path(a, b, path=""):
    """(path, a value, b value) of the first difference between a and b, or None.

    Dict keys are visited in a's order, then b's extra keys; a key or list
    element only one side has is ABSENT on the other. Values of different
    types differ as a whole.
    """
    if type(a) is not type(b):
        return path, a, b
    if isinstance(a, dict):
        for key in [*a, *(key for key in b if key not in a)]:
            if key not in a or key not in b:
                return f"{path}.{key}", a.get(key, ABSENT), b.get(key, ABSENT)
            found = first_path(a[key], b[key], f"{path}.{key}")
            if found is not None:
                return found
        return None
    if isinstance(a, list):
        for n, (x, y) in enumerate(zip(a, b)):
            found = first_path(x, y, f"{path}[{n}]")
            if found is not None:
                return found
        if len(a) != len(b):
            n = min(len(a), len(b))
            return (f"{path}[{n}]", a[n] if n < len(a) else ABSENT,
                    b[n] if n < len(b) else ABSENT)
        return None
    return None if a == b or (a != a and b != b) else (path, a, b)  # NaN == NaN here


def first_difference(head, base, commands):
    """The first difference between two runs' observations of the same commands, or None.

    head and base are lists of observations, one per step. Only the steps
    both runs observed are compared: a run that died early is the crash
    check's business, not a behaviour difference. Returns {"step", "command"
    (the symbolic command of that step), "path", "head", "base"}.
    """
    for h, b in zip(head, base):
        assert h["step"] == b["step"], (h["step"], b["step"])
        found = first_path(normalised(h), normalised(b))
        if found is not None:
            path, head_value, base_value = found
            return {"step": h["step"], "command": commands[h["step"] - 1], "path": path,
                    "head": head_value, "base": base_value}
    return None


CRITERIA = re.compile(r'\[(?:"[^"]*"|[^\]"])*\]\s*')


def subcommands(text):
    """A step's subcommands as sway's execute_command splits it, criteria removed.

    sway splits at ";" and "," outside quotes (a backslash escapes the next
    character) and skips empty subcommands, so the reply list has one
    entry per subcommand here, in order, up to the first invalid one.
    """
    parts, current, quote, escaped = [], [], None, False
    for char in CRITERIA.sub("", text):
        if escaped:
            escaped = False
        elif char == "\\":
            escaped = True
        elif quote:
            quote = None if char == quote else quote
        elif char in "\"'":
            quote = char
        elif char in ";,":
            parts.append("".join(current))
            current = []
            continue
        current.append(char)
    parts.append("".join(current))
    return [part.strip() for part in parts if part.strip()]


def subcommand_shape(subcommand):
    """A subcommand with numbers as N and whitespace collapsed."""
    return " ".join(re.sub(r"\d+", "N", subcommand).split())


REPLY = re.compile(r"\.reply\[(\d+)\]")


def command_shape(text, reply=None):
    """The causing command's shape: one subcommand, criteria removed, numbers as N.

    A difference in reply[k] is caused by subcommand k, since sway replies
    once per subcommand. Any other difference is in the state observed after
    the whole step, and minimising cannot split a step, so it is named after
    the last subcommand: "fullscreen toggle; move scratchpad" and "move
    scratchpad" are one group. A reply index past the subcommands (one side
    replied more often) names the whole step.
    """
    parts = [subcommand_shape(part) for part in subcommands(text)]
    if reply is None:
        return parts[-1] if parts else ""
    return parts[reply] if reply < len(parts) else "; ".join(parts)


NESTED = re.compile(r"(?:\.nodes\[\])+")


def path_shape(path):
    """A path with list indices folded and container nesting below a workspace folded.

    .tree.nodes[0].nodes[1].floating_nodes[0].nodes[0].nodes[2].x ->
    .tree.nodes[].nodes[].floating_nodes[].nodes[]*.x: the output and
    workspace levels stay, and any run of .nodes[] under them (one or more
    nested containers) is .nodes[]*, so the same change one split deeper is
    the same group. Tiled (.nodes[]*) and floating (.floating_nodes[]) stay
    apart. A reply index stays: .reply[1].success names subcommand 1.
    """
    if (match := REPLY.match(path)):
        return match.group(0) + re.sub(r"\[\d+\]", "[]", path[match.end():])
    shape = re.sub(r"\[\d+\]", "[]", path)
    prefix = ".tree.nodes[].nodes[]"
    if not shape.startswith(prefix):
        return shape
    return prefix + NESTED.sub(".nodes[]*", shape[len(prefix):])


def group_key(difference):
    """(command shape, path shape): the identity of a difference across seeds, for grouping.

    Lossy on purpose (seeds whose difference sits at another index or depth
    are one group), so it is not the minimise predicate: see same_difference().
    """
    match = REPLY.match(difference["path"])
    return (command_shape(difference["command"], int(match.group(1)) if match else None),
            path_shape(difference["path"]))


def same_difference(a, b):
    """The minimise predicate: the same exact path, the same values (NaN equals NaN), the same group.

    The exact path, not its shape: a reduction must not move the difference
    to another node, depth or reply. The group key adds the causing command's shape.
    """
    def same(x, y):
        return json.dumps(x, sort_keys=True) == json.dumps(y, sort_keys=True)
    return (a["path"] == b["path"] and group_key(a) == group_key(b)
            and same(a["head"], b["head"]) and same(a["base"], b["base"]))


def group(rows):
    """Differing diff rows grouped by group_key: [{"key", "rows"}], largest group first.

    Within a group rows are ordered by (first differing step, seed), so the
    first row is the shortest example; groups of equal size by their first seed.
    """
    groups = {}
    for row in rows:
        if row["outcome"] == "differ":
            groups.setdefault(group_key(row["difference"]), []).append(row)
    ordered = [{"key": key, "rows": sorted(members, key=lambda r: (r["difference"]["step"], r["seed"]))}
               for key, members in groups.items()]
    return sorted(ordered, key=lambda g: (-len(g["rows"]), min(r["seed"] for r in g["rows"])))


def value_text(value, limit=80):
    """A value for the report: JSON, cut at limit characters."""
    text = value if value == ABSENT else json.dumps(value, sort_keys=True)
    return text if len(text) <= limit else text[:limit - 3] + "..."
