"""The zombie animates with the Mixamo packs (asset_pipeline/import_mixamo.py).

import_mixamo.py checks the assets: the blend space rows play the Mixamo idle,
walk and run, and the clips stand, stay in place and step. This proves the
game uses them: a zombie wanderer wears SKM_Zombie01 with its anim Blueprint
running, and put beside the player it swings -- and the montage its swing
plays is built from the Mixamo attack, not the mannequin's MM_Attack_01.
"""

import unreal

BESIDE_CM = 100.0     # well inside the touch range and the melee range
MIXAMO_ATTACK = "A_Zombie01_Mx_Scary_ZombieAttack"


def _zombies(p):
    ctrls = unreal.GameplayStatics.get_all_actors_of_class(p.world(), unreal.AIController)
    return [c for c in ctrls if c.get_class().get_name().startswith("BP_ForestWandererAI_Zombie")
            and c.get_controlled_pawn() is not None]


def _montage_clips(montage):
    """Names of the sequences a montage's slot tracks play."""
    out = []
    for track in montage.get_editor_property("slot_anim_tracks"):
        for seg in track.get_editor_property("anim_track").get_editor_property("anim_segments"):
            ref = seg.get_editor_property("anim_reference")
            if ref:
                out.append(ref.get_name())
    return out


def probe(p):
    yield lambda: len(_zombies(p)) > 0
    yield 0.5
    ctrl = _zombies(p)[0]
    npc, player = ctrl.get_controlled_pawn(), p.pawn()
    mesh = npc.get_editor_property("mesh")
    worn = mesh.get_skeletal_mesh_asset()
    p.check("a zombie wanderer wears SKM_Zombie01",
            worn is not None and worn.get_name() == "SKM_Zombie01",
            worn.get_name() if worn else "None")
    anim = mesh.get_anim_instance()
    p.check("...with its anim Blueprint running", anim is not None,
            anim.get_class().get_name() if anim else "None")
    if anim is None:
        return

    npc.set_actor_location(player.get_actor_location()
                           + unreal.Vector(BESIDE_CM, 0.0, 0.0), False, True)
    yield lambda: anim.get_current_active_montage() is not None
    montage = anim.get_current_active_montage()
    p.check("beside the player it swings (a montage plays)", montage is not None)
    if montage is None:
        return
    clips = _montage_clips(montage)
    p.check("...and the swing is the Mixamo zombie attack",
            MIXAMO_ATTACK in clips, f"{clips}")
