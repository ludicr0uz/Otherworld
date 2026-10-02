"""Checks for the next tree of the wendigo's hunt (npc/stalk_cover.py), read
back off the saved controllers. Called by npc/verify_stalk.py, which owns the
rest of the step.

What it proves, of each stalker's BT_Stalk: a leg's spot is behind a tree a
sweep struck (an instanced mesh, by its own transform) whose trunk is wide
enough to hide it, with that same tree between the spot and the player, on
the navmesh; or in the open when no sweep found one. And, of the numbers,
that every species planted has its trunk's width on record.
"""

from forest_generator.npc_stalk import (
    NPC_STALK_ADVANCE_MAX_CM, NPC_STALK_ADVANCE_MIN_CM, NPC_STALK_ARC_DEG,
    NPC_STALK_BEHIND_CM, NPC_STALK_COVER_MIN_CM, NPC_STALK_GAIN_MIN_CM,
    NPC_STALK_SAPLING, NPC_STALK_SWEEP_RADIUS_CM, NPC_STALK_TRUNK_CM,
    NPC_STALK_TRUNK_MIN_CM, cover_trees,
)
from forest_generator.tree_placement import DEFAULT_TREE_SPECS
from npc.paths import (
    STALK_COVER_VAR, STALK_HIDDEN_VAR, STALK_IGNORE_VAR, STALK_SIDE_VAR,
)
from npc.stalk_cover import NO_COVER_SCALE
from npc.verify import (
    BEL, PIN, _close, _drivers, _exec_reach, _feeders, _ins, _lit, _num, _sources,
    _title, _titled, check,
)


def _titles(nodes):
    return {_title(n) for n in nodes}


def _is(node, pin, value):
    """A bool literal; a false one is the pin's default, which a graph loaded
    from disk holds as ""."""
    return _lit(node, pin) in (("true",) if value else ("false", ""))


def _with(nodes, *pins):
    return [n for n in nodes if set(pins) <= _ins(n)]


def _after(pin):
    return [PIN.get_owning_node(q) for q in PIN.list_connected_pins(pin)]


def check_cover_settings():
    planted = {s.name for s in DEFAULT_TREE_SPECS}
    check("stalk: every species planted has its trunk's width on record",
          planted <= set(NPC_STALK_TRUNK_CM)
          and all(w > 0.0 for w in NPC_STALK_TRUNK_CM.values()),
          f"{sorted(planted - set(NPC_STALK_TRUNK_CM))}")
    cover = dict(cover_trees())
    specs = {s.name: s for s in DEFAULT_TREE_SPECS}
    least = {name: cover.get(s.mesh_path) for name, s in specs.items()}
    check(f"stalk: a tree is cover from the scale its trunk is "
          f"{NPC_STALK_TRUNK_MIN_CM:.0f} cm wide at; a sapling never is",
          bool(cover) and planted <= set(NPC_STALK_TRUNK_CM)
          and NPC_STALK_SAPLING in specs and least[NPC_STALK_SAPLING] is None
          and all(abs(s * NPC_STALK_TRUNK_CM[name] - NPC_STALK_TRUNK_MIN_CM) < 0.1
                  if s is not None else
                  specs[name].scale_max * NPC_STALK_TRUNK_CM[name] < NPC_STALK_TRUNK_MIN_CM
                  for name, s in least.items()),
          f"{least}")
    check("stalk: it looks for a tree up to 18 m closer than it stands, with "
          "a 3 m sphere (half as far again as the 12 m and 2 m it began with)",
          _close(NPC_STALK_ADVANCE_MAX_CM, 1.5 * 1200.0)
          and _close(NPC_STALK_SWEEP_RADIUS_CM, 1.5 * 200.0)
          and NPC_STALK_ADVANCE_MIN_CM < NPC_STALK_ADVANCE_MAX_CM)


def _least_scales(test):
    """The (mesh name, least scale) rows a "scale >= least" test reads its
    least through, and what the chain of them ends on."""
    rows, picks, end = [], _feeders(test, "B"), None
    while len(picks) == 1 and _title(picks[0]) == "SelectFloat":
        pick = picks[0]
        names = _feeders(pick, "bPickA")
        if not (len(names) == 1 and _title(names[0]) == "Equal Exactly (String)"
                and _titles(_feeders(names[0], "A")) == {"GetObjectName"}
                and "Get StaticMesh" in _titles(_sources(names[0], "A"))):
            return None, None
        rows.append((_lit(names[0], "B"), _num(pick, "A")))
        picks, end = _feeders(pick, "B"), _num(pick, "B")
    return rows, (end if not picks else None)


def check_wide(tag, own, sweeps, raws):
    """A sapling, or any tree too slight for its mesh, is no cover."""
    wanted = sorted((path.rsplit(".", 1)[-1], least) for path, least in cover_trees())
    gates = [d for raw in raws for d in _drivers(raw)]
    tests = [t for g in gates for t in _feeders(g, "Condition")]
    chains = [_least_scales(t) for t in tests]
    check(f"{tag}: a tree is cover only if its trunk is "
          f"{NPC_STALK_TRUNK_MIN_CM:.0f} cm wide: its mesh, by name, and its own "
          f"scale against that mesh's least ({', '.join(n for n, _ in wanted)}); "
          f"no other mesh at any scale",
          len(gates) == len(sweeps) == len(tests) > 0
          and all(_title(g) == "Branch" and raw in
                  [n for p in [BEL.find_then_pin(g)] for n in _after(p)]
                  for g, raw in zip(gates, raws))
          and all(_title(t) == "float >= float"
                  and _titles(_feeders(t, "A")) == {"BreakVector"}
                  and "BreakTransform" in _titles(_sources(t, "A")) for t in tests)
          and all(rows is not None and len(rows) == len(wanted)
                  and all(n == wn and _close(s, ws)
                          for (n, s), (wn, ws) in zip(sorted(rows), wanted))
                  and end is not None and _close(end, NO_COVER_SCALE)
                  for rows, end in chains),
          f"{chains[:1]}")
    return gates


def check_cover(tag, own):
    sweeps = _with(own, "Start", "End", "Radius", "ActorsToIgnore")
    turns = sorted(_num(m, "B") for s in sweeps for m in _sources(s, "Start")
                   if _title(m) == "float * float"
                   and _titles(_feeders(m, "A")) == {f"Get {STALK_SIDE_VAR}"})
    check(f"{tag}: one sweep per angle ({', '.join(f'{a:.0f}' for a in NPC_STALK_ARC_DEG)} "
          f"deg), each turned the hunt's own way round the player",
          len(sweeps) == len(NPC_STALK_ARC_DEG) and len(turns) == len(sweeps)
          and all(_close(t, a) for t, a in zip(turns, sorted(NPC_STALK_ARC_DEG))),
          f"{len(sweeps)} sweeps, turned {turns}")
    check(f"{tag}: ...a {NPC_STALK_SWEEP_RADIUS_CM:.0f} cm sphere, along the line "
          f"at the player",
          bool(sweeps) and all(
              _close(_num(s, "Radius"), NPC_STALK_SWEEP_RADIUS_CM)
              and {"GetPlayerPawn", "Rotate Vector Around Axis",
                   "Normalize 2D (Vector)"} <= _titles(_sources(s, pin))
              for s in sweeps for pin in ("Start", "End")))
    clears = [n for n in own if _ins(n) == {"execute", "TargetArray"}]
    adds = _with(own, "TargetArray", "NewItem")
    spared = sorted(_title(f) for a in adds for f in _feeders(a, "NewItem"))
    check(f"{tag}: ...ignoring the ground it stands on and its own pawn, "
          f"listed afresh for each leg",
          len(clears) == 1 and spared == ["Get Controlled Pawn", "GetMovementBaseActor"]
          and all(a in _exec_reach(clears[0]) for a in adds)
          and all(s in _exec_reach(a) for a in adds for s in sweeps)
          and all(_titles(_feeders(s, "ActorsToIgnore")) == {f"Get {STALK_IGNORE_VAR}"}
                  for s in sweeps))

    raws = [s for s in _titled(own, f"Set {STALK_COVER_VAR}")
            if "BreakTransform" in _titles(_sources(s, STALK_COVER_VAR))]
    stands = _with(own, "InstanceIndex", "bWorldSpace")
    check(f"{tag}: a tree is an instanced mesh the sweep struck, and stands "
          f"where that instance's own transform says",
          len(stands) == len(sweeps) and all(
              _is(t, "bWorldSpace", True)
              and _titles(_feeders(t, "InstanceIndex")) == {"BreakHitResult"}
              and _titles(_feeders(t, "self")) == {"Cast To InstancedStaticMeshComponent"}
              for t in stands))
    hides = [n for n in _titled(own, f"Set {STALK_HIDDEN_VAR}")
             if _is(n, STALK_HIDDEN_VAR, True)]
    snaps = [d for h in hides for d in _drivers(h)]
    on_nav = [b for s in snaps for b in _drivers(s)]
    steps_in = [r for b in on_nav for r in _with(_sources(b, "Condition"),
                                                  "Value", "Min", "Max")]
    check(f"{tag}: a spot counts only {NPC_STALK_GAIN_MIN_CM:.0f} cm or more "
          f"closer to the player than the pawn stands, and no nearer than "
          f"{NPC_STALK_COVER_MIN_CM:.0f} cm",
          len(steps_in) == len(sweeps) > 0 and all(
              _close(_num(r, "Min"), NPC_STALK_COVER_MIN_CM)
              and _titles(_feeders(r, "Value")) == {"Distance2D (Vector)"}
              and f"Get {STALK_COVER_VAR}" in _titles(_sources(r, "Value"))
              and any(_title(m) == "float - float"
                      and _close(_num(m, "B"), NPC_STALK_GAIN_MIN_CM)
                      for m in _feeders(r, "Max"))
              for r in steps_in))
    check(f"{tag}: the spot is {NPC_STALK_BEHIND_CM:.0f} cm past the trunk, seen "
          f"from the player, and counts only once it is on the navmesh",
          len(hides) == len(sweeps) and len(snaps) == len(hides)
          and all(_title(s) == f"Set {STALK_COVER_VAR}"
                  and _titles(_feeders(s, STALK_COVER_VAR)) == {"Project Point to Navigation"}
                  for s in snaps)
          and len(on_nav) == len(snaps)
          and all(_title(b) == "Branch" and "Project Point to Navigation"
                  in _titles(_sources(b, "Condition"))
                  and _titles(_feeders(b, "Condition")) == {"AND Boolean"}
                  for b in on_nav)
          and len(raws) == len(sweeps)
          and all(any(_title(m) == "MakeVector"
                      and _close(_num(m, "X"), NPC_STALK_BEHIND_CM)
                      for m in _sources(raw, STALK_COVER_VAR))
                  and {"GetPlayerPawn", "Normalize 2D (Vector)"}
                  <= _titles(_sources(raw, STALK_COVER_VAR)) for raw in raws))
    check_wide(tag, own, sweeps, raws)
    lines = [n for n in _with(own, "Start", "End", "ActorsToIgnore")
             if "Radius" not in _ins(n)]
    # The Branch on "that same tree" behind each line's own "it struck".
    sames = [[c for c in _drivers(b) if _title(c) == "Branch"
              and any(ln in _drivers(g) for g in _drivers(c) for ln in lines)]
             for b in on_nav]
    check(f"{tag}: ...and only if a line from it to the player strikes that "
          f"same tree (its cell and its instance): a leaning trunk hides "
          f"nothing, nor another tree's leaves",
          len(lines) == len(raws) == len(on_nav) > 0 and all(
              _titles(_feeders(ln, "Start")) == {f"Get {STALK_COVER_VAR}"}
              and "GetPlayerPawn" in _titles(_sources(ln, "End"))
              and _titles(_feeders(ln, "ActorsToIgnore")) == {f"Get {STALK_IGNORE_VAR}"}
              and len(_drivers(ln)) == 1 and _drivers(ln)[0] in raws
              for ln in lines)
          and all(len(found) == 1
                  and _titles(_feeders(found[0], "Condition")) == {"AND Boolean"}
                  and {"Equal (Object)", "Equal (Integer)", "BreakHitResult",
                       "Cast To InstancedStaticMeshComponent"}
                  <= _titles(_sources(found[0], "Condition"))
                  and len([n for n in _sources(found[0], "Condition")
                           if _title(n) == "BreakHitResult"]) == 2
                  for found in sames))
    bare = [n for n in _titled(own, f"Set {STALK_HIDDEN_VAR}")
            if _is(n, STALK_HIDDEN_VAR, False)]
    opens = [s for s in _titled(own, f"Set {STALK_COVER_VAR}")
             if s not in raws and s not in snaps
             and "BreakHitResult" not in _titles(_sources(s, STALK_COVER_VAR))
             and "Project Point to Navigation"
             not in _titles(_feeders(s, STALK_COVER_VAR))]
    check(f"{tag}: no tree on any line: the leg ends in the open, on round "
          f"the player",
          len(bare) == 1 and len(sweeps) == len(NPC_STALK_ARC_DEG)
          and all(bare[0] in _exec_reach(s) for s in sweeps)
          and [_titles(_feeders(d, STALK_COVER_VAR)) for d in _drivers(bare[0])]
          == [{"Project Point to Navigation"}]
          and len(opens) == 1 and all(opens[0] in _exec_reach(s) for s in sweeps)
          and bare[0] in _exec_reach(opens[0]))
    return hides + bare
