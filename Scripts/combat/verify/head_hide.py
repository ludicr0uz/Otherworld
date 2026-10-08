"""verify.head_hide -- down the sights the player's own head is hidden
(weapon_component/head_hide.py): one Branch on SightSeat, the hide on one arm
and the show on the other, both on the wearer's head bone; and the dead arm's
show (dead.py).

That it is hidden in the game for every gun in the bag, and back afterwards
and on death, is probes/probe_head_hide.py.
"""

import unreal

from combat.seat_tuning import HEAD_HIDE_SEAT, SEAT_VAR
from combat.skin import player_skin
from combat.verify.common import BEL, PIN, by_pins, check, in_pins, num_pin, pin_value
from combat.verify.fixtures import wg, wg_dead
from combat.verify.sights import _feeds, _title
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


def check_dead_shows_head():
    head = player_skin().head
    shows = _shows(wg_dead)
    check(f"a dead owner's {head} is shown: the corpse of a player killed down "
          "the sights has its head",
          len(shows) == 1 and _on_owner_mesh(shows[0], head)
          and not _hides(wg_dead), f"{len(shows)} shows, {len(_hides(wg_dead))} hides")
    check("...and the parts under the mannequin theirs",
          len(_shows(wg_dead, parts=True)) == 1 and not _hides(wg_dead, parts=True))


def run():
    check_head_bone()
    check_head_hide()
    check_dead_shows_head()
