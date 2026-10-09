"""A hit from each side plays that side's reaction.

LastHitFrom points from the victim towards the source; the Tick picks Front,
Back, Left or Right off the owner's forward and right (hit_reaction.py). The
probe writes it and Health, as a damage source would, and reads which clip
the HitSlot plays (`anim.get_current_active_montage()`).
"""

LEVEL = "/Game/Maps/Lvl_Forest_200m"  # passes here, fails on the 50 m probe level (T11)
SYSTEMS = ('health',)

import unreal

from combat.anim_blueprint import HIT_SLOT
from combat.hit_reaction import HIT_DIR_BACK, HIT_DIR_FRONT, HIT_DIR_LEFT, HIT_DIR_RIGHT
from combat.paths import HEALTH_BP_PATH, HEALTH_CLASS_PATH
from combat import health_vars as HV
from forest_generator.npc_placement import NPC_HIT_REACTION_CLIPS

WRITABLE = [(HEALTH_BP_PATH, HV.Health), (HEALTH_BP_PATH, "LastHitFrom")]


def _clip(m):
    """The animation a dynamic montage wraps (its own name is AnimMontage_N)."""
    if m is None:
        return ""
    try:
        seg = m.slot_anim_tracks[0].anim_track.anim_segments[0]
        return seg.get_editor_property("anim_reference").get_name()
    except Exception:
        return m.get_name()


def probe(p):
    pawn = p.pawn()
    health = p.component(pawn, HEALTH_CLASS_PATH)
    anim = pawn.mesh.get_anim_instance()
    yield 1.0
    fwd, right = pawn.get_actor_forward_vector(), pawn.get_actor_right_vector()
    sides = (("front", fwd, HIT_DIR_FRONT), ("back", fwd * -1.0, HIT_DIR_BACK),
             ("left", right * -1.0, HIT_DIR_LEFT), ("right", right, HIT_DIR_RIGHT))
    for name, vec, (first, count) in sides:
        yield lambda: not anim.is_slot_active(HIT_SLOT)
        yield 0.7                      # the cooldown
        p.set(health, "LastHitFrom", vec)
        p.set(health, "Health", p.get(health, "Health") - 1.0)
        yield lambda: anim.is_slot_active(HIT_SLOT)
        m = anim.get_current_active_montage()
        clip = _clip(m)
        allowed = [NPC_HIT_REACTION_CLIPS[i] for i in range(first, first + count)]
        p.check(f"a hit from the {name} plays a {name} reaction",
                any(a in clip for a in allowed), f"{clip!r}, want one of {allowed}")
