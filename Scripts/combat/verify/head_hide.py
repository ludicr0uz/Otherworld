"""verify.head_hide -- down the sights the player's own head is hidden
(weapon_component/head_hide.py): one Branch on SightSeat, the hide on one arm
and the show on the other, both on the wearer's head bone; and the dead arm's
show (dead.py). The head's own parts (a MetaHuman skin's Face and grooms)
go out of their owner's view instead, on the same two arms, and are tagged
and shadowed for it on the Character (metahuman_body.py).

That it is hidden in the game for every gun in the bag, and back afterwards
and on death, is probes/probe_head_hide.py.
"""

import unreal

from asset_pipeline.metahuman_paths import CLOTHING, GROOMS
from combat import metahuman_body
from combat.seat_tuning import HEAD_HIDE_SEAT, HEAD_PART_TAG, SEAT_VAR
from combat.skin import player_skin
from combat.verify.common import BEL, PIN, by_pins, check, in_pins, num_pin, pin_value
from combat.verify.fixtures import char, exec_reach, wg, wg_dead
from combat.verify.sights import _feeds, _tag_gated, _tag_gates, _title
from uebp.graph import _component_object, _find_handle
from combat.weapon_component.head_hide import PHYS_BODY_OP


def _on_cast(node):
    """Fed by a cast of a part under OwnerMesh (body_parts.py's loop)."""
    return any(_title(n).startswith("Cast To")
               for n in _feeds(BEL.find_input_pin(node, "self")))


def _hides(nodes, parts=False):
    return [n for n in by_pins(nodes, "BoneName", "PhysBodyOption")
            if _on_cast(n) == parts]


def _shows(nodes, parts=False):
    return [n for n in by_pins(nodes, "BoneName")
            if "PhysBodyOption" not in in_pins(n) and _on_cast(n) == parts]


def _on_owner_mesh(node, head):
    return (pin_value(node, "BoneName") == head and "Get OwnerMesh" in
            {_title(n) for n in _feeds(BEL.find_input_pin(node, "self"))})


def _run_by(node):
    """(the node whose exec output runs ``node``, that output's name) pairs."""
    return [(PIN.get_owning_node(q), str(PIN.get_pin_name(q)))
            for q in PIN.list_connected_pins(BEL.find_execute_pin(node))]


def check_head_bone():
    skin = player_skin()
    check(f"the player's skin names its head bone ({skin.head}), and its mesh "
          "has it", _has_bone(skin), skin.mesh)


def _has_bone(skin):
    mesh = unreal.load_asset(skin.mesh)
    pose = unreal.AnimPoseExtensions.get_reference_pose(
        mesh.get_editor_property("skeleton"))
    return skin.head in {str(b) for b in unreal.AnimPoseExtensions.get_bone_names(pose)}


def check_head_hide():
    head = player_skin().head
    hides, shows = _hides(wg), _shows(wg)
    check(f"the Tick hides {head} on OwnerMesh in one place, and shows it in one",
          len(hides) == 1 and len(shows) == 1
          and all(_on_owner_mesh(n, head) for n in hides + shows),
          f"{len(hides)} hides, {len(shows)} shows")
    parts_hide, parts_show = _hides(wg, parts=True), _shows(wg, parts=True)
    check(f"...and {head} on every skinned part under it (body_parts.py: a "
          "MetaHuman skin's face and body), hidden and shown with it",
          len(parts_hide) == 1 and len(parts_show) == 1
          and all(pin_value(n, "BoneName") == head for n in parts_hide + parts_show),
          f"{len(parts_hide)} hides, {len(parts_show)} shows")
    if len(hides) != 1 or len(shows) != 1:
        return
    # A literal equal to its pin's default is not saved: "" once loaded.
    check(f"...leaving the bone's physics body alone ({PHYS_BODY_OP}): the "
          "head can still be hit",
          pin_value(hides[0], "PhysBodyOption") in (PHYS_BODY_OP, ""),
          pin_value(hides[0], "PhysBodyOption"))
    by_hide, by_show = _run_by(hides[0]), _run_by(shows[0])
    gates = {n for n, _ in by_hide + by_show}
    gate = next(iter(gates)) if len(gates) == 1 else None
    check("...the two arms of one Branch: hidden on true, shown on false",
          gate is not None and "Condition" in in_pins(gate)
          and [name for _, name in by_hide] == ["then"]
          and [name for _, name in by_show] == ["else"],
          f"{[(_title(n), name) for n, name in by_hide + by_show]}")
    if gate is None:
        return
    fed = _feeds(BEL.find_input_pin(gate, "Condition"))
    names = {_title(n) for n in fed}
    check(f"...on {SEAT_VAR} > {HEAD_HIDE_SEAT:g} alone: whatever is held, so "
          "no gun needs an eye point that clears the head",
          names >= {f"Get {SEAT_VAR}"} and len(fed) == 2
          and any(abs((num_pin(n, "B") or 0.0) - HEAD_HIDE_SEAT) < 1e-9
                  for n in fed if "B" in in_pins(n)),
          str(sorted(names)))
    # Each arm ends in the OwnerNoSee call and then the loop that carries it
    # to the parts under the mannequin (body_parts.py): the loop is what
    # runs the gate.
    check(f"...after the sight camera has written {SEAT_VAR} this frame, on "
          "both of its arms (armed and empty-handed)",
          len(PIN.list_connected_pins(BEL.find_execute_pin(gate))) == 2
          and all(_title(PIN.get_owning_node(q)) == "For Each Loop"
                  for q in PIN.list_connected_pins(BEL.find_execute_pin(gate))),
          str([_title(PIN.get_owning_node(q))
               for q in PIN.list_connected_pins(BEL.find_execute_pin(gate))]))


def _head_arms(node):
    """The arms of a Branch on HEAD_PART_TAG that run ``node`` (the Tick has
    Branches on other tags: an actor's)."""
    return [arm for g, arm in _tag_gates(node)
            if HEAD_PART_TAG in {pin_value(f, "Tag") for f in _feeds(
                BEL.find_input_pin(g, "Condition"), 4) if "Tag" in in_pins(f)}]


def _head_no_see(nodes):
    """The SetOwnerNoSee calls on the head's own parts alone: on a cast of a
    part, on the true arm of a Branch on HEAD_PART_TAG."""
    return [n for n in by_pins(nodes, "bNewOwnerNoSee")
            if _on_cast(n) and _head_arms(n) == ["then"]]


def check_head_parts():
    head = player_skin().head
    calls = _head_no_see(wg)
    values = sorted(pin_value(n, "bNewOwnerNoSee") for n in calls)
    # A literal equal to its pin's default is not saved: "" once loaded.
    check(f"the head's own parts ({HEAD_PART_TAG}: a MetaHuman skin's Face and "
          "grooms, which a hidden bone does not reach) are set OwnerNoSee in "
          "two places, true in one and false in the other",
          len(calls) == 2 and values[-1] == "true" and values[0] in ("false", ""),
          str(values))
    hides, shows = _hides(wg), _shows(wg)
    if len(calls) != 2 or len(hides) != 1 or len(shows) != 1:
        return
    gates = {n for n, _ in _run_by(hides[0])}
    gate = next(iter(gates)) if len(gates) == 1 else None
    if gate is None:
        return
    on = {n.get_path_name() for n in exec_reach([BEL.find_then_pin(gate)])}
    off = {n.get_path_name() for n in exec_reach(
        [p for p in BEL.list_output_pins(gate) if str(PIN.get_pin_name(p)) == "else"])}
    hidden = next(n for n in calls if pin_value(n, "bNewOwnerNoSee") == "true")
    shown = next(n for n in calls if n is not hidden)
    check(f"...out of their owner's view on the arm that hides {head}, and back "
          "in it on the other: per view, so every other player still sees them",
          hidden.get_path_name() in on and hidden.get_path_name() not in off
          and shown.get_path_name() in off and shown.get_path_name() not in on)
    parts_hide = _hides(wg, parts=True)
    check(f"...and the hidden {head} skips them (a face with its bone hidden "
          "casts no shadow): the hide on the parts is the false arm of a "
          f"Branch on {HEAD_PART_TAG}",
          len(parts_hide) == 1
          and _head_arms(parts_hide[0]) == ["else"],
          str([_head_arms(n) for n in parts_hide]))
    check("...and nothing else in the Tick is hidden by that tag: the body, "
          "the arms and the garments stay in the sight picture",
          len([n for n in wg if _head_arms(n)]) == 3,
          str(sorted(_title(n) for n in wg if _head_arms(n))))


def check_head_part_components():
    """The tag and the shadow, on the Character's own components."""
    if not char or not metahuman_body.installed(char):
        return      # a mannequin skin has no part of its own for the head
    want = (metahuman_body.FACE, *GROOMS)
    parts = {n: _component_object(_find_handle(char, n))
             for n in (*want, metahuman_body.BODY, *CLOTHING)}

    def tags(comp):
        return [str(t) for t in comp.get_editor_property("component_tags")]

    off = [n for n in want if tags(parts[n]) != [HEAD_PART_TAG]]
    check(f"the MetaHuman's Face and its {len(GROOMS)} grooms carry the "
          f"{HEAD_PART_TAG} tag the sights hide them by", not off, str(off))
    dark = [n for n in want if not parts[n].get_editor_property("cast_hidden_shadow")]
    check("...and cast their shadow while hidden (bCastHiddenShadow): the "
          "owner's shadow keeps its head down the sights", not dark, str(dark))
    wrong = [n for n in (metahuman_body.BODY, *CLOTHING) if HEAD_PART_TAG in tags(parts[n])]
    check("...and the body and the garment slots do not: they are never out "
          "of the sight picture", not wrong, str(wrong))


def check_dead_shows_head():
    head = player_skin().head
    shows = _shows(wg_dead)
    check(f"a dead owner's {head} is shown: the corpse of a player killed down "
          "the sights has its head",
          len(shows) == 1 and _on_owner_mesh(shows[0], head)
          and not _hides(wg_dead), f"{len(shows)} shows, {len(_hides(wg_dead))} hides")
    check("...and the parts under the mannequin theirs",
          len(_shows(wg_dead, parts=True)) == 1 and not _hides(wg_dead, parts=True))
    back = [n for n in by_pins(wg_dead, "bNewOwnerNoSee") if _on_cast(n)]
    check("...and the head's own parts are back in its owner's view: the dead "
          "arm's OwnerNoSee(false) is on every part under the mannequin, with "
          f"no Branch on {HEAD_PART_TAG} before it",
          len(back) == 1 and not _tag_gated(back[0])
          and pin_value(back[0], "bNewOwnerNoSee") in ("false", ""),
          f"{len(back)} calls, {[_tag_gated(n) for n in back]}")


def run():
    check_head_bone()
    check_head_hide()
    check_head_parts()
    check_head_part_components()
    check_dead_shows_head()
