"""random-v3: a state-aware command generator for the sway IPC differential runner.

v2 draws a fixed command list from (seed, steps) before the run. v3 picks each
command after reading the current sway state, so it can build the state
preconditions that sway's branches test (floating, fullscreen, tabbed parents,
marks, scratchpad, several workspaces) on purpose. The data lives in
sway-ipc/random-v3/{vocabulary,recipes}.json; this module only interprets it.

Reproducibility rules:
  * One RNG per purpose, seeded from "random-v3:<seed>:<purpose>".
  * Features read only stable IPC fields: counts, layouts, types,
    fullscreen_mode, floating, sticky, scratchpad_state, marks, urgent,
    visible, focus, workspace names. Never rect, percent or ids.
  * The emitted list is recorded, so a seed replays without the generator.
"""

from collections import Counter, deque
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import random
import re

ROOT = Path(__file__).resolve().parents[1]
RANDOM_V3 = ROOT / "sway-ipc/random-v3"
PURPOSES = ("setup", "window", "recipe", "pick", "args")
TWO_OUTPUT_LAYOUT = [[1280, 720, 0, 0, True], [1280, 720, 1280, 0, False]]
WINDOW_TOKEN = "@window"
CON_TOKEN = re.compile(r"@con:(parent-of:)?([A-Za-z0-9_.-]+)")
# Seen in place of a symbolic id whose window is gone: matches nothing on either side.
MISSING_CON_ID = "999999"


@dataclass(frozen=True)
class Features:
    outputs: int
    workspaces: tuple
    focused_ws: str
    focus_kind: str                 # "view" | "split" | "workspace"
    focused_floating: bool
    focused_in_floating_split: bool
    focused_fs: int
    ws_fullscreen: bool
    global_fs: bool
    parent_layout: str
    parent_is_workspace: bool
    only_child: bool
    views: int
    tiling_views_ws: int
    floaters_ws: int
    floaters_any: int
    floating_splits: int
    depth: int
    layouts_present: frozenset
    scratch_hidden: int
    scratch_visible: int
    sticky: int
    marks: tuple                    # ((mark, kind), ...), kind in view/split/floating/hidden/self
    urgent: int
    hidden_views: int
    ws_empty: bool
    apps: tuple                     # app_ids of every view, tree order
    focused_app: str
    siblings: tuple
    inactive_tabs: tuple
    hidden_apps: tuple
    transient: bool


def is_view(node):
    return node.get("type") in ("con", "floating_con") and (
        "shell" in node or node.get("app_id") is not None or node.get("window") is not None)


def features(tree, workspaces):
    """Pure function of one sway get_tree and get_workspaces reply (stable fields only)."""
    records = []

    def walk(node, ancestors):
        records.append((node, ancestors))
        for key in ("nodes", "floating_nodes"):
            for child in node.get(key, []):
                walk(child, ancestors + (node,))

    walk(tree, ())

    def in_scratch(ancestors):
        return any(item.get("name") == "__i3_scratch" for item in ancestors)

    def workspace_of(ancestors):
        return next((item for item in reversed(ancestors) if item.get("type") == "workspace"), None)

    outputs = [node for node in tree.get("nodes", []) if node.get("name") != "__i3"]
    focused, focus_ancestors = next(((node, anc) for node, anc in records if node.get("focused")),
                                    (None, ()))
    focused_ws = next((ws.get("name", "") for ws in workspaces if ws.get("focused")), "")
    ws_node = next((node for node, anc in records if node.get("type") == "workspace"
                    and node.get("name") == focused_ws and not in_scratch(anc + (node,))), None)
    live = [(node, anc) for node, anc in records if not in_scratch(anc + (node,))]
    views = [(node, anc) for node, anc in records if is_view(node)]
    if focused is None:
        kind = "workspace"
    elif is_view(focused):
        kind = "view"
    elif focused.get("type") in ("con", "floating_con"):
        kind = "split"
    else:
        kind = "workspace"
    parent = focus_ancestors[-1] if focus_ancestors else None
    focused_floating = bool(focused and focused.get("type") == "floating_con")
    if focused_floating:
        parent_layout = "floating"
    elif parent is not None and parent.get("type") in ("con", "workspace", "floating_con"):
        parent_layout = parent.get("layout", "none")
    else:
        parent_layout = "none"
    chain = [focused, *focus_ancestors] if focused else []
    marks = []
    for node, anc in records:
        for mark in node.get("marks", []):
            if node is focused:
                mark_kind = "self"
            elif in_scratch(anc):
                mark_kind = "hidden"
            elif node.get("type") == "floating_con":
                mark_kind = "floating"
            else:
                mark_kind = "view" if is_view(node) else "split"
            marks.append((mark, mark_kind))
    depth = 0
    for node, anc in live:
        if node.get("type") in ("con", "floating_con"):
            depth = max(depth, 1 + sum(item.get("type") in ("con", "floating_con") for item in anc))
    layouts = frozenset(node.get("layout") for node, _ in live
                        if (node.get("type") == "workspace" or
                            (node.get("type") in ("con", "floating_con") and not is_view(node)))
                        and node.get("layout") not in (None, "none", "output"))
    sibling_nodes = parent.get("nodes", []) if parent is not None and not focused_floating else []
    tiling_ws = 0
    if ws_node is not None:
        tiling_ws = sum(1 for node, anc in records if is_view(node) and ws_node in anc
                        and node.get("type") == "con"
                        and not any(item.get("type") == "floating_con" for item in anc))
    return Features(
        outputs=len(outputs),
        workspaces=tuple(ws.get("name", "") for ws in workspaces),
        focused_ws=focused_ws,
        focus_kind=kind,
        focused_floating=focused_floating,
        focused_in_floating_split=bool(focused) and not focused_floating and any(
            item.get("type") == "floating_con" for item in focus_ancestors),
        focused_fs=max((node.get("fullscreen_mode") or 0 for node in chain
                        if node.get("type") in ("con", "floating_con")), default=0),
        ws_fullscreen=ws_node is not None and any(
            node.get("fullscreen_mode") == 1 for node, anc in records if ws_node in anc),
        global_fs=any(node.get("fullscreen_mode") == 2 for node, _ in records),
        parent_layout=parent_layout,
        parent_is_workspace=bool(parent is not None and parent.get("type") == "workspace"),
        only_child=len(sibling_nodes) == 1 and kind != "workspace",
        views=len(views),
        tiling_views_ws=tiling_ws,
        floaters_ws=len(ws_node.get("floating_nodes", [])) if ws_node else 0,
        floaters_any=sum(1 for node, _ in live if node.get("type") == "floating_con"),
        floating_splits=sum(1 for node, _ in live
                            if node.get("type") == "floating_con" and not is_view(node)),
        depth=depth,
        layouts_present=layouts,
        scratch_hidden=sum(1 for node, anc in views if in_scratch(anc)),
        scratch_visible=sum(1 for node, anc in live if node.get("type") == "floating_con"
                            and node.get("scratchpad_state") not in (None, "none")),
        sticky=sum(1 for node, _ in records if node.get("sticky")),
        marks=tuple(marks),
        urgent=sum(1 for node, _ in live if node.get("urgent") and node.get("type") != "workspace"),
        hidden_views=sum(1 for node, anc in views if not in_scratch(anc) and node.get("visible") is False),
        ws_empty=ws_node is not None and not ws_node.get("nodes") and not ws_node.get("floating_nodes"),
        apps=tuple(node.get("app_id") or "" for node, _ in views if node.get("app_id")),
        focused_app=(focused.get("app_id") or "") if kind == "view" else "",
        siblings=tuple(node.get("app_id") for node in sibling_nodes
                       if node is not focused and is_view(node) and node.get("app_id")),
        inactive_tabs=tuple(node.get("app_id") for node, anc in views
                            if anc and anc[-1].get("layout") in ("tabbed", "stacked")
                            and node.get("visible") is False and node.get("app_id")),
        hidden_apps=tuple(node.get("app_id") for node, anc in views
                          if in_scratch(anc) and node.get("app_id")),
        transient=any(node.get("app_id") == "fixture-hint-parent" for node, _ in views),
    )


def resolve_con_tokens(tree, text):
    """Rewrite @con:<app_id> and @con:parent-of:<app_id> to this compositor's numeric ids."""
    if "@con:" not in text:
        return text
    ids, parents = {}, {}

    def walk(node, parent):
        if is_view(node) and node.get("app_id") and node["app_id"] not in ids:
            ids[node["app_id"]] = node.get("id")
            parents[node["app_id"]] = parent.get("id") if parent else None
        for key in ("nodes", "floating_nodes"):
            for child in node.get(key, []):
                walk(child, node)

    walk(tree, None)
    return CON_TOKEN.sub(lambda match: str(
        (parents if match[1] else ids).get(match[2]) or MISSING_CON_ID), text)


CONDITION = re.compile(r"^(!?)(\w+)(?:(==|!=|>=|<=|>|<|~)([\w.-]+))?$")


def condition_values(f, memory):
    values = dict(f.__dict__)
    values.update(memory)
    values.update(
        marks_any=bool(f.marks),
        marks_other=any(kind != "self" for _, kind in f.marks),
        marks_self=any(kind == "self" for _, kind in f.marks),
        parent_tabbed=f.parent_layout in ("tabbed", "stacked"),
        shallow=f.depth < 2 and f.views >= 3,
        two_ws=len([name for name in f.workspaces if not name.startswith("__")]) >= 2,
        has_siblings=bool(f.siblings),
        inactive_tab_count=len(f.inactive_tabs),
        scratch_any=f.scratch_hidden + f.scratch_visible > 0,
    )
    return values


def holds(conditions, values):
    for text in conditions or ():
        match = CONDITION.match(text)
        if not match:
            raise ValueError(f"random-v3: bad condition {text!r}")
        negate, name, op, rhs = match.groups()
        if name not in values:
            raise ValueError(f"random-v3: unknown feature {name!r}")
        value = values[name]
        if op is None:
            result = bool(value)
        elif op == "~":
            result = rhs in value
        else:
            other = int(rhs) if rhs.lstrip("-").isdigit() else rhs
            result = {"==": value == other, "!=": value != other, ">=": value >= other,
                      "<=": value <= other, ">": value > other, "<": value < other}[op]
        if result == bool(negate):
            return False
    return True


def load_v3(root=RANDOM_V3):
    vocabulary = json.loads((root / "vocabulary.json").read_text())
    recipes = json.loads((root / "recipes.json").read_text())["recipes"]
    return vocabulary, recipes


def v3_sha256(root=RANDOM_V3):
    digest = hashlib.sha256()
    for name in ("vocabulary.json", "recipes.json"):
        digest.update((root / name).read_bytes())
    return digest.hexdigest()


def as_step(item):
    if item is None or isinstance(item, (str, list)):
        return {"do": item}
    return item


class V3Generator:
    def __init__(self, seed, vocabulary, recipes, outputs="auto", steps=40):
        self.seed, self.vocab, self.recipes, self.steps = seed, vocabulary, recipes, steps
        self.rng = {purpose: random.Random(f"random-v3:{seed}:{purpose}") for purpose in PURPOSES}
        draw = self.rng["setup"].random()
        self.outputs = {"auto": 2 if draw < vocabulary["two_output_probability"] else 1,
                        "1": 1, "2": 2}[str(outputs)]
        self.queue = deque()
        # Stratify over the one-output recipes. A two-output seed exists to test D1,
        # and a run stops at its first divergence, so it starts R14 (the recipes
        # with "outputs": 2) first and the stratified recipe right after it.
        single = [recipe for recipe in recipes if recipe.get("outputs", 1) == 1]
        stratified = single[seed % len(single)]
        multi = [recipe for recipe in recipes if recipe.get("outputs", 1) == 2]
        if self.outputs == 2 and multi:
            self.primary, self.follow = multi[0], stratified
        else:
            self.primary, self.follow = stratified, None
        self.primary_step = None    # generator step (prelude excluded) that started it
        self.generated = 0
        self.next_window = 1
        self.pending = None
        self.glued = False
        self.axis_hits = Counter()
        self.started = []
        self.triggered = []         # recipe names, one per trigger step emitted
        self.memory = {"has_prev_ws": False, "prev_layout": False}
        self.last_ws = None
        self.base = vocabulary["base_weights"]
        self._prelude = list(vocabulary["prelude"])
        for draw_spec in vocabulary["prelude_draws"]:
            if self.rng["setup"].random() < draw_spec["probability"]:
                self._prelude.append(self.rng["setup"].choice(draw_spec["choices"]))

    def scenario(self):
        if self.outputs == 2:
            return {"outputs": 2, "output_layout": TWO_OUTPUT_LAYOUT}
        return None

    def prelude(self):
        return list(self._prelude)

    # -- window decisions -------------------------------------------------
    def window_probability(self, views):
        probability = 0.0
        for threshold, value in self.vocab["window_probability"]:
            if views >= threshold:
                probability = value
        return probability

    def _ident(self):
        ident = f"fixture-diff-{self.next_window}"
        self.next_window += 1
        return ident

    def _exec(self, ident):
        return self.vocab["window"].format(ident=ident)

    def _window(self):
        rng = self.rng["window"]
        draw = rng.random()
        if draw < self.vocab["hinted_fraction"]:
            shape = rng.choice(self.vocab["hinted_shapes"])
            return "xdg-hinted " + " ".join(map(str, [self._ident(), *shape]))
        if draw < self.vocab["hinted_fraction"] + self.vocab["rule_fraction"]:
            ident = f"fixture-diff-{self.next_window}"
            rule = rng.choice(self.vocab["map_rules"]).format(next=ident)
            self.pending = self._exec(self._ident())
            return rule
        return self._exec(self._ident())

    # -- placeholders -----------------------------------------------------
    def _fill(self, template, f):
        if template == WINDOW_TOKEN:
            return self._exec(self._ident())
        rng = self.rng["args"]
        names = [name for name in f.workspaces if not name.startswith("__")]

        def pick(options, fallback):
            options = [item for item in options if item]
            return rng.choice(options) if options else fallback

        def value(match):
            key = match[1]
            others = [app for app in f.apps if app != f.focused_app]
            if key == "app":
                return pick(f.apps, "fixture-diff-1")
            if key == "other_app":
                return pick(others, "fixture-diff-1")
            if key == "sibling":
                return pick(f.siblings, pick(others, "fixture-diff-1"))
            if key == "inactive_tab":
                return pick(f.inactive_tabs, pick(others, "fixture-diff-1"))
            if key == "hidden_app":
                return pick(f.hidden_apps, pick(f.apps, "fixture-diff-1"))
            if key == "mark":
                return pick([mark for mark, kind in f.marks if kind != "self"],
                            pick([mark for mark, _ in f.marks], "m"))
            if key == "newmark":
                return rng.choice(("m", "n", "z"))
            if key == "dir":
                return rng.choice(("left", "right", "up", "down"))
            if key == "o":
                return rng.choice(("left", "right"))
            if key == "ws_other":
                return pick([name for name in names if name != f.focused_ws], "2")
            if key == "ws_new":
                return pick([name for name in ("2", "3", "4", "oracle") if name not in names], "5")
            if key == "ws_focused":
                return f.focused_ws or "1"
            if key == "next":
                return f"fixture-diff-{self.next_window}"
            if key == "con_other":
                return "@con:" + pick(others, "fixture-diff-1")
            if key == "con_focused":
                return "@con:" + (f.focused_app or pick(f.apps, "fixture-diff-1"))
            if key == "con_parent":
                return "@con:parent-of:" + (f.focused_app or pick(f.apps, "fixture-diff-1"))
            raise ValueError(f"random-v3: unknown placeholder {key!r}")

        return re.sub(r"\{(\w+)\}", value, template)

    # -- recipes ----------------------------------------------------------
    def _choose_alternative(self, do):
        if isinstance(do, list):
            return self.rng["args"].choice(do)
        return do

    def _start(self, recipe, f):
        rng = self.rng["args"]
        setup = rng.choice(recipe["setups"])
        low, high = recipe.get("trigger_count", [1, 3])
        count = min(rng.randint(low, high), len(recipe["triggers"]))
        indices = sorted(rng.sample(range(len(recipe["triggers"])), count))
        steps = [as_step(item) for item in setup] + [
            {**as_step(recipe["triggers"][i]), "trigger": recipe["name"]} for i in indices]
        for step in steps:
            command = self._choose_alternative(step["do"])
            if command is not None:
                self.queue.append({**step, "do": command})
        self.started.append(recipe["name"])
        for axis in recipe["axes"]:
            self.axis_hits[axis] += 1
        return self._pop(f)

    def _pop(self, f):
        step = self.queue.popleft()
        self.glued = bool(step.get("glue"))
        if "trigger" in step:
            self.triggered.append(step["trigger"])
        return self._fill(step["do"], f)

    def _step_ok(self, step, values):
        if step["do"] == WINDOW_TOKEN and values["views"] >= self.vocab["window_cap"]:
            return False
        return holds(step.get("guard"), values)

    def _eligible(self, recipe, values):
        return values["views"] >= recipe.get("min_views", 0) and holds(recipe.get("requires"), values)

    def _choose_recipe(self, values):
        eligible = [recipe for recipe in self.recipes if self._eligible(recipe, values)]
        if not eligible:
            return None
        weights = [1.0 / (1 + sum(self.axis_hits[axis] for axis in recipe["axes"]))
                   for recipe in eligible]
        return self.rng["recipe"].choices(eligible, weights)[0]

    # -- weighted pick ----------------------------------------------------
    def weight(self, entry, values, active):
        weight = self.base[entry["class"]]
        tags = set(entry.get("tags", ()))
        for rule in active:
            if tags & rule["favour_set"]:
                weight *= rule.get("factor", 3.0)
            if tags & rule["disfavour_set"]:
                weight *= rule.get("disfactor", 0.3)
        if not holds(entry.get("needs"), values):
            weight *= self.vocab["precondition_factor"]
        return weight

    def _weighted_pick(self, f, values):
        active = [{**rule, "favour_set": set(rule.get("favour", ())),
                   "disfavour_set": set(rule.get("disfavour", ()))}
                  for rule in self.vocab["multipliers"] if holds(rule["when"], values)]
        entries = self.vocab["commands"]
        weights = [self.weight(entry, values, active) for entry in entries]
        entry = self.rng["pick"].choices(entries, weights)[0]
        if entry["cmd"] == WINDOW_TOKEN:
            if values["views"] >= self.vocab["window_cap"]:
                return self._fill("focus parent", f)
            return self._window()
        return self._fill(entry["cmd"], f)

    def _next_primary(self, f):
        """Stratified schedule: plain windows up to min_views, then the seed's recipe.

        Nothing random runs first, so every seed starts its primary recipe by
        generator step min_views + 1 <= primary_deadline (prelude excluded).
        Windows are counted here, not read from the tree, so a slow map cannot
        push the start past the deadline.
        """
        self.generated += 1
        need = self.primary.get("min_views", 0)
        if self.next_window <= need and self.generated < self.vocab["primary_deadline"]:
            return self._exec(self._ident())
        self.primary_step = self.generated
        return self._start(self.primary, f)

    # -- main entry -------------------------------------------------------
    def next(self, f, step):
        if self.last_ws is not None and f.focused_ws != self.last_ws:
            self.memory["has_prev_ws"] = True
        self.last_ws = f.focused_ws
        values = condition_values(f, self.memory)
        if self.pending:
            command, self.pending = self.pending, None
            return command
        if self.glued and self.queue:
            return self._pop(f)
        self.glued = False
        if self.primary_step is None:
            return self._next_primary(f)
        if self.follow is not None and not self.queue:
            if values["views"] < self.follow.get("min_views", 0):
                return self._exec(self._ident())
            recipe, self.follow = self.follow, None
            return self._start(recipe, f)
        if self.rng["window"].random() < self.window_probability(f.views):
            return self._window()
        if self.queue:
            if not self._step_ok(self.queue[0], values):
                self.queue.clear()
            elif self.rng["recipe"].random() >= self.vocab["noise_probability"]:
                return self._pop(f)
            else:
                return self._weighted_pick(f, values)
        if self.rng["recipe"].random() < self.vocab["recipe_probability"]:
            recipe = self._choose_recipe(values)
            if recipe:
                return self._start(recipe, f)
        return self._weighted_pick(f, values)

    def observe_reply(self, command, reply):
        if (command.startswith(("layout ", "split")) and isinstance(reply, list)
                and reply and all(item.get("success") for item in reply)):
            self.memory["prev_layout"] = True


def self_test():
    """Pure checks: data parses, placeholders and conditions resolve, generation is deterministic."""
    vocabulary, recipes = load_v3()
    assert len(recipes) == 17 and len({r["name"] for r in recipes}) == 17
    assert [r["name"] for r in recipes if r.get("outputs", 1) == 2] == ["R14-multi-output"]
    known = {"app", "other_app", "sibling", "inactive_tab", "hidden_app", "mark", "newmark", "dir",
             "o", "ws_other", "ws_new", "ws_focused", "next", "con_other", "con_focused", "con_parent"}
    templates = [entry["cmd"] for entry in vocabulary["commands"]] + vocabulary["map_rules"]
    for recipe in recipes:
        for item in [step for setup in recipe["setups"] for step in setup] + recipe["triggers"]:
            do = as_step(item)["do"]
            templates += [do] if isinstance(do, str) else [x for x in (do or []) if x]
    for template in templates:
        unknown = set(re.findall(r"\{(\w+)\}", template)) - known
        assert not unknown, (template, unknown)
    assert set(entry["class"] for entry in vocabulary["commands"]) <= set(vocabulary["base_weights"])
    # Canned states stand in for sway: the same seed and states give the same list.
    view = {"type": "con", "shell": "xdg_shell", "nodes": [], "floating_nodes": [], "layout": "none"}
    empty_ws = {"type": "workspace", "name": "1", "layout": "splith", "nodes": [], "floating_nodes": []}
    def tree(count):
        ws = dict(empty_ws, nodes=[dict(view, app_id=f"fixture-diff-{i}", id=10 + i,
                                        focused=i == count) for i in range(1, count + 1)])
        return {"type": "root", "nodes": [{"type": "output", "name": "HEADLESS-1", "nodes": [ws]}]}
    workspaces = [{"name": "1", "focused": True}]
    def run(seed):
        gen = V3Generator(seed, vocabulary, recipes)
        commands = gen.prelude()
        while len(commands) < 40:
            state = features(tree(min(commands.count("x") + len(commands) // 5, 6)), workspaces)
            commands.append(gen.next(state, len(commands) + 1))
            gen.observe_reply(commands[-1], [{"success": True}])
        return commands
    for seed in (0, 7, 16):
        assert run(seed) == run(seed)
    assert run(0) != run(1)
    # Stratified schedule (v3-design.md "Recipe schedule"): a one-output seed
    # starts single[seed % 16] first, within its first five generated steps,
    # with the canned tree tracking the windows actually opened. A two-output
    # seed starts R14 there instead, then single[seed % 16] once R14 has drained.
    single = [r["name"] for r in recipes if r.get("outputs", 1) == 1]
    for outputs in ("1", "2"):
        for seed in range(3 * len(single)):
            gen = V3Generator(seed, vocabulary, recipes, outputs)
            opened = 0
            for step in range(1, 25):
                command = gen.next(features(tree(opened), workspaces), step)
                opened += command.startswith(("exec ", "xdg-hinted "))
                gen.observe_reply(command, [{"success": True}])
            expected = ([single[seed % len(single)]] if outputs == "1" else
                        ["R14-multi-output", single[seed % len(single)]])
            assert gen.started[:len(expected)] == expected, (outputs, seed, gen.started)
            assert gen.primary_step <= vocabulary["primary_deadline"], (seed, gen.primary_step)
            assert "R14-multi-output" in gen.triggered or outputs == "1", (seed, gen.triggered)
    sample = features(tree(3), workspaces)
    assert sample.views == 3 and sample.focus_kind == "view" and sample.siblings == (
        "fixture-diff-1", "fixture-diff-2")
    assert resolve_con_tokens(tree(2), "[con_id=@con:fixture-diff-2] focus") == "[con_id=12] focus"
    assert resolve_con_tokens(tree(2), "swap container with con_id @con:gone") == \
        f"swap container with con_id {MISSING_CON_ID}"
    assert holds(["views>=2", "!focused_floating", "focus_kind==view"], condition_values(sample, {}))
