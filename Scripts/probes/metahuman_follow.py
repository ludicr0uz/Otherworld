"""metahuman_follow -- how far the MetaHuman stands from the hidden mesh it
follows, and whether its face and garments are on it.  Shared by
probe_metahuman_body (the mannequin under it) and probe_gas_idle (the UEFN
mannequin under it): one measure and one tolerance for both.
"""

import unreal

# A MetaHuman limb ends where the mannequin's does, give or take the two
# bodies' proportions: the retargeter scales, it does not pin.
FOLLOW_CM = 12.0
# A garment is skinned to the body's bones and should sit on them.
GARMENT_CM = 1.5
BONES = ("head", "hand_l", "hand_r", "foot_l", "foot_r", "pelvis", "spine_05")


def _comp(actor, name):
    for c in actor.get_components_by_class(unreal.ActorComponent):
        if c.get_name() == name:
            return c
    return None


def _gap(a, b, bone):
    return (a.get_socket_location(bone) - b.get_socket_location(bone)).length()


def _follow(p, label, mannequin, body, face, torso, legs, feet):
    gaps = {b: _gap(mannequin, body, b) for b in BONES}
    p.note(f"{label}: MetaHuman to mannequin, cm: "
           + ", ".join(f"{b} {g:.1f}" for b, g in gaps.items()))
    worst = max(gaps.items(), key=lambda kv: kv[1])
    p.check(f"{label}: the MetaHuman body is on the mannequin's pose "
            f"(every bone within {FOLLOW_CM:.0f} cm)", worst[1] < FOLLOW_CM,
            f"worst {worst[0]} {worst[1]:.1f} cm")
    p.check(f"{label}: the face is on the body's head",
            _gap(body, face, "head") < 1.0, f"{_gap(body, face, 'head'):.1f} cm")
    # A garment slot with nothing on it has no bones to measure: the body
    # starts in its underwear (combat/metahuman_body.py).
    for name, comp, bones in (("hoodie", torso, ("spine_02", "spine_04", "upperarm_l", "hand_l")),
                              ("jeans", legs, ("pelvis", "thigh_l", "calf_l", "foot_l")),
                              ("shoes", feet, ("calf_l", "foot_l", "ball_l", "foot_r"))):
        if comp.get_skeletal_mesh_asset() is None:
            continue
        gaps = {b: _gap(body, comp, b) for b in bones}
        worst = max(gaps.items(), key=lambda kv: kv[1])
        p.check(f"{label}: the {name} are on the body (within {GARMENT_CM:.0f} cm)",
                worst[1] < GARMENT_CM,
                ", ".join(f"{b} {g:.1f}" for b, g in gaps.items()))


def _undressed(p, torso, legs, feet):
    """The three garment components are there, bare and not drawn."""
    told = {c.get_name(): (c.get_skeletal_mesh_asset().get_name()
                           if c.get_skeletal_mesh_asset() else None, c.is_visible())
            for c in (torso, legs, feet)}
    p.check("Torso, Legs and Feet wear no mesh and are hidden: the body starts in its "
            "underwear", all(v == (None, False) for v in told.values()), str(told))
