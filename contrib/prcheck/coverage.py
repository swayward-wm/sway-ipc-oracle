"""pr-check's own random-v3 recipes, added to the committed ones for exploration only.

sway-ipc/random-v3 and contrib/sway_ipc_v3.py stay unchanged (the sway-ipc
results depend on them). explore.make_cfg() appends EXTRA_RECIPES to the loaded
recipes, so each one takes part in the stratified primary schedule (a
one-output seed starts single[seed % len(single)] first) and in the weighted
recipe choice like any committed recipe.

P1-mark-in-hidden-split closes the gap that kept random-v3 from reaching
sway-crashes.md crash 4 (`workspace_add_floating < container_move_to_workspace
< container_move_to_container`) in gating run 2's 600 seeds. The crash needs
three things at once: a mark on a container *inside* a hidden scratchpad split
(a mark on the hidden toplevel itself takes cmd_move_container's early
return to the scratchpad command), a floating toplevel focused, and `move
container to mark` naming that mark. No committed recipe builds all three:
R7's scratchpad setup ("mark m", "move scratchpad") marks the toplevel, and
R3, which floats a split, can mark its children (`[tiling] mark --add x`) and
send it to the scratchpad, but has no move-to-mark trigger and leaves nothing
floating focused. So the state arose only by random chaining, and then the
weighted pick had to choose `move container to mark` (about 7% per step).
See docs/pr-check.md "Generation".
"""


def glued(setup):
    """setup with every step glued to the step after it (see V3Generator._pop)."""
    return [{"do": step, "glue": True} for step in setup]


MARK_IN_HIDDEN_SPLIT = {
    "name": "P1-mark-in-hidden-split",
    "axes": ["hidden_split_mark"],
    "min_views": 2,
    "requires": ["focus_kind==view", "!focused_floating", "focused_fs==0"],
    # Both triggers, in order: move-to-mark always, then one follow-up (or none).
    "trigger_count": [2, 2],
    # Every setup step is glued to the next and the last to the move-to-mark trigger, so
    # no random step (a new window takes focus and the mark) lands in between.
    "setups": [glued(setup) for setup in (
        # A floating split around the focused view; its only child carries the mark.
        ["floating enable", ["splitv", "splith", "splitt"], "mark m", "move scratchpad",
         ["@window", None], "floating enable"],
        # A tiled split with a second view, marked, then floated with its parent.
        [["splitv", "splith"], "@window", "mark m", "focus parent", "floating enable",
         "move scratchpad", "floating enable"],
        # As the first, but the split is shown and hidden again before the trigger.
        ["floating enable", ["splitv", "splitt"], "mark m", "move scratchpad", "scratchpad show",
         "move scratchpad", "floating enable"],
    )],
    "triggers": [
        "move container to mark m",
        ["swap container with mark m", "[con_mark=m] focus", "[con_mark=m] kill",
         "scratchpad show", "move container to workspace {ws_new}", None],
    ],
}

EXTRA_RECIPES = (MARK_IN_HIDDEN_SPLIT,)


def with_extra_recipes(recipes):
    """recipes (the loaded random-v3 list, not mutated) followed by EXTRA_RECIPES."""
    return [*recipes, *EXTRA_RECIPES]
