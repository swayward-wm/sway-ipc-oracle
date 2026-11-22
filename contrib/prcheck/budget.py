"""The wall-time budget of a --minutes run.
"""




EXPLORE_SHARE = 0.6   # of --minutes: no seed starts after it


def plan_budget(minutes, also_base, jobs):
    """Offsets in seconds from the run's start for --minutes M (pure; the caller adds start).

    run: the whole budget, after which nothing new is judged and minimising
    stops. head_explore: no head seed starts after it; base_explore: no base
    seed starts after it (None without --also-base). Exploration ends at
    EXPLORE_SHARE of run, split evenly between head and base when
    also_base > 0; base_seeds caps the base seeds. judge: the seconds left
    for judging and minimising if exploration uses its share. jobs: workers
    per phase.
    """
    if minutes <= 0 or also_base < 0 or jobs < 1:
        raise ValueError(f"bad budget: minutes {minutes}, also_base {also_base}, jobs {jobs}")
    run = 60.0 * minutes
    explore_end = EXPLORE_SHARE * run
    return {"run": run,
            "head_explore": explore_end / 2 if also_base else explore_end,
            "base_explore": explore_end if also_base else None,
            "base_seeds": also_base, "judge": run - explore_end, "jobs": jobs}
