"""probe_clothing's drawn half: what wearing puts on the body
(weapon_component/wear_draw.py). Not a probe of its own: probe_clothing.py
calls these around its own wears, on the 200 m map's MetaHuman.

    dress(player)       what each garment component (Torso, Legs, Feet)
                        draws: its mesh's path, or None, and whether it shows
    jacket_checks       the worn jacket is the hoodie on Torso, shown, and
                        its bones are the body's after a walk; taken off,
                        Torso is bare and hidden; worn again and set down on
                        the ground (DropRequest), bare and hidden again

    pants_checks        the worn pants are the jeans on Legs, which are on
                        the body's own skeleton: led by the body (leader
                        pose), and the legs' bones are the body's in a walk

The bones are compared while the walk is still held, so a garment that
stopped being posed, or lags the body by a frame of the clip, is caught.
"""

SYSTEMS = ('clothing',)

import unreal

from asset_pipeline.metahuman_paths import CLOTHING
from combat.metahuman_body import BODY
from combat.slot_tuning import DROP_REQUEST_VAR, NO_REQUEST, SLOT_COUNT
from combat.wear_tuning import NOT_CLOTHING, TAKE_OFF_VAR

TORSO, LEGS = "Torso", "Legs"
LEG_BONES = ("thigh_l", "calf_l")
# The spine the task names, and an arm: the reference pose holds the arms
# out, so an unposed hoodie is far off there.
BONES = ("spine_03", "lowerarm_l")
FOLLOW_CM = 1.0
WALK_S, WALK_CM = 1.5, 100.0
BARE = (None, False)


def _skeletal(player, name):
    return next((c for c in player.get_components_by_class(unreal.SkeletalMeshComponent)
                 if c.get_name() == name), None)


def dress(player):
    """{part: (mesh path or None, shown)} for the three garment components."""
    seen = {}
    for name in CLOTHING:
        comp = _skeletal(player, name)
        mesh = comp.get_skeletal_mesh_asset() if comp else None
        seen[name] = (mesh.get_path_name().split(".")[0] if mesh else None,
                      bool(comp) and comp.is_visible()
                      and not comp.get_editor_property("hidden_in_game"))
    return seen


def bare(player):
    return all(v == BARE for v in dress(player).values())


def _gap(part, body, bones=BONES):
    return max((part.get_socket_location(b) - body.get_socket_location(b)).length()
               for b in bones)


def _walk(p, player, part, body, bones):
    """Walk backwards (the test garments lie in a row ahead) for WALK_S:
    (the ground covered, the gap on each frame of its second half)."""
    world = p.world()
    now = lambda: unreal.GameplayStatics.get_time_seconds(world)
    start, t0, gaps = player.get_actor_location(), now(), []
    while now() - t0 < WALK_S:
        player.add_movement_input(player.get_actor_forward_vector(), -1.0)
        yield 0.0
        if now() - t0 > WALK_S * 0.5:
            gaps.append(_gap(part, body, bones))
    return (player.get_actor_location() - start).length(), gaps


def jacket_checks(p, player, wc, jacket, slot, wear):
    """With ``jacket`` just worn in ``slot``. ``wear(jacket)`` is the caller's
    hold and fire. Leaves the jacket on the ground, Dropped."""
    torso, body = _skeletal(player, TORSO), _skeletal(player, BODY)
    seen = dress(player)
    p.check("the worn jacket is drawn: Torso has the hoodie and shows, Legs and Feet "
            "stay bare",
            seen == {**{n: BARE for n in CLOTHING}, TORSO: (CLOTHING[TORSO], True)},
            str(seen))
    p.check("...whose mesh has the bones compared below",
            all(torso.get_bone_index(b) >= 0 and body.get_bone_index(b) >= 0 for b in BONES))
    walked, gaps = yield from _walk(p, player, torso, body, BONES)
    p.check(f"...and follows the body: after a walk its spine and its forearm are "
            f"within {FOLLOW_CM:.0f} cm of the body's on every frame",
            walked > WALK_CM and gaps and max(gaps) < FOLLOW_CM,
            f"walked {walked:.0f} cm, {len(gaps)} frames, worst "
            f"{max(gaps) if gaps else -1:.2f} cm")
    yield 0.3

    p.set(wc, TAKE_OFF_VAR, slot)
    yield lambda: p.get(wc, TAKE_OFF_VAR) == NOT_CLOTHING
    yield 0.1
    p.check("taken off, the jacket is in the bag and Torso is empty and hidden",
            jacket in list(p.get(wc, "Inventory")) and bare(player), str(dress(player)))

    yield from wear(jacket)
    p.check("worn again, it is drawn again", dress(player)[TORSO] == (CLOTHING[TORSO], True),
            str(dress(player)))
    p.set(wc, DROP_REQUEST_VAR, SLOT_COUNT + slot)
    yield lambda: p.get(wc, DROP_REQUEST_VAR) == NO_REQUEST
    yield 0.1
    p.check("a worn jacket set down on the ground leaves Torso empty and hidden",
            bool(jacket.get_editor_property("Dropped")) and bare(player), str(dress(player)))


def pants_checks(p, player, wc, pants, wear):
    """With ``pants`` in the bag: worn, the leader-pose way of following."""
    legs, body = _skeletal(player, LEGS), _skeletal(player, BODY)
    yield from wear(pants)
    seen = dress(player)
    p.check("the worn pants are drawn: Legs has the jeans and shows",
            seen[LEGS] == (CLOTHING[LEGS], True), str(seen))
    p.check("...on the body's own skeleton, so led by the body's pose and running no "
            "anim Blueprint of their own",
            legs.get_skeletal_mesh_asset().get_editor_property("skeleton")
            == body.get_skeletal_mesh_asset().get_editor_property("skeleton")
            and legs.get_post_process_instance() is None)
    walked, gaps = yield from _walk(p, player, legs, body, LEG_BONES)
    p.check(f"...whose thigh and calf are within {FOLLOW_CM:.0f} cm of the body's on "
            "every frame of a walk",
            walked > WALK_CM and gaps and max(gaps) < FOLLOW_CM,
            f"walked {walked:.0f} cm, {len(gaps)} frames, worst "
            f"{max(gaps) if gaps else -1:.2f} cm")
