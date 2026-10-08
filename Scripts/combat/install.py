"""Installing on the characters: puts the health, weapon and footstep
components on BP_ThirdPersonCharacter and the wanderer, and retires
superseded assets.
"""

import unreal

from Sound.bind import write_components
from Sound.sound_monsters import BINDINGS as MONSTER_SOUNDS
from Sound.sound_weapons import RETIRED_SOUNDS
from combat.camera import aim_camera, face_the_camera
from combat.log import _log
from uebp import net
from uebp.graph import (
    BEL, _add_component, _assets, _component_object, _drop_components, _handles,
    _root_handle)
from combat.hit_reaction import install_hit_reactions
from combat.hit_zones import install_hit_zones, make_shootable
from combat.paths import CHARACTER_BP_PATH, NPC_BP_PATH, NPC_CLASS_PATH
from combat.player_move import reparent_player, set_move_numbers
from combat.player_pace import set_jog_speed
from combat.weapon_component.stance import allow_crouch
from net import relevancy
from net.relevancy_consts import CHARACTER


# ─── Installing on the characters ────────────────────────────────────────────

OLD_SHOTGUN_PARTS = {"Shotgun", "Receiver", "Barrel", "MagTube", "Pump", "Stock",
                     "Grip", "TriggerGuard", "ShotgunComponent"}
OLD_SHOTGUN_BP = "/Game/Weapons/BP_ShotgunComponent"


def _uninstall_old_shotgun(bp):
    """Strip what build_shotgun_and_health.py welded onto the character.

    The old design hung the weapon's seven primitives off the character's mesh
    directly. Those have to go, or the player carries a second shotgun that no
    longer responds to anything.
    """
    present = {var for _h, var in _handles(bp)} & OLD_SHOTGUN_PARTS
    if present:
        _drop_components(bp, present)
        _log(f"removed the old welded shotgun: {sorted(present)}")


def install_on_character(health_bp, weapon_bp, footstep_bp):
    eas = _assets()
    bp = eas.load_asset(CHARACTER_BP_PATH)
    if not bp:
        raise RuntimeError(f"could not load {CHARACTER_BP_PATH}")
    # First: it recompiles the Blueprint, and component handles do not outlive that.
    reparent_player(bp)
    _uninstall_old_shotgun(bp)
    _drop_components(bp, {"HealthComponent", "WeaponComponent", "FootstepComponent"})
    handles = {}
    for name, source in (("HealthComponent", health_bp),
                         ("WeaponComponent", weapon_bp),
                         ("FootstepComponent", footstep_bp)):
        handles[name] = _add_component(bp, _root_handle(bp),
                                       BEL.generated_class(source), name)
    # Symmetry, and forward planning: the player carries health too, so anything
    # that shoots back later needs to be able to hit them -- and hit them in
    # the head. (The wanderers' punch is not a trace and stays a body hit.)
    make_shootable(bp)
    install_hit_zones(bp, handles["HealthComponent"])
    install_hit_reactions(bp, handles["HealthComponent"])
    aim_camera(bp)
    face_the_camera(bp)
    allow_crouch(bp)
    set_jog_speed(bp)
    set_move_numbers(bp)
    if not BEL.compile_blueprint(bp):
        raise RuntimeError("BP_ThirdPersonCharacter failed to compile")
    # The weapon component replicates (the look: weapon_component/look.py),
    # and the health component (damage.py), on this character too: a
    # template's default, written after a compile.
    net.replicate_component(bp, "WeaponComponent")
    net.replicate_component(bp, "HealthComponent")
    # How far a player's character is sent, and how often (task A2).
    relevancy.apply(bp, CHARACTER)
    if not BEL.compile_blueprint(bp):
        raise RuntimeError("BP_ThirdPersonCharacter failed to compile")
    eas.save_loaded_asset(bp)
    _log("player: HealthComponent + WeaponComponent + FootstepComponent installed")


def install_on_npc(health_bp, footstep_bp):
    """The NPC gets health that despawns and respawns it.

    DespawnOnDeath and RespawnClass are set on *this* Blueprint's component
    template rather than on BP_HealthComponent's defaults, which is what keeps
    the same component class usable on the player without the player vanishing
    at 0 HP.
    """
    eas = _assets()
    bp = eas.load_asset(NPC_BP_PATH)
    if not bp:
        _log(f"note: {NPC_BP_PATH} not found — skipping the NPC")
        return None
    _drop_components(bp, {"HealthComponent", "FootstepComponent"})
    handle = _add_component(bp, _root_handle(bp),
                            BEL.generated_class(health_bp), "HealthComponent")
    # The same component the player carries. A wanderer at 600 cm/s covers a
    # stride more than three times a second, and ten of them arriving through
    # the trees is most of what the approach sounds like.
    _add_component(bp, _root_handle(bp),
                   BEL.generated_class(footstep_bp), "FootstepComponent")
    # ...with takes of its own (Sound/sound_monsters.py), on this Blueprint's
    # copy of the component: the class's own are the player's.
    write_components(bp, MONSTER_SOUNDS)
    comp = _component_object(handle)
    comp.set_editor_property("DespawnOnDeath", True)
    comp.set_editor_property("RespawnClass", unreal.load_class(None, NPC_CLASS_PATH))

    # A respawned wanderer is spawned, not placed, so the default
    # "Placed in World" would leave it with no AI controller and no movement.
    cdo = unreal.get_default_object(BEL.generated_class(bp))
    try:
        cdo.set_editor_property(
            "auto_possess_ai", unreal.AutoPossessAI.PLACED_IN_WORLD_OR_SPAWNED)
    except Exception as exc:                                      # noqa: BLE001
        _log(f"note: could not set auto_possess_ai: {exc}")

    make_shootable(bp)
    install_hit_zones(bp, handle)
    # The PARENT's clips, i.e. whichever creature BP_ForestWanderer wears. Each
    # variant child is a different skeleton and cannot override an inherited
    # component's defaults from Python (see _author_stats_and_voice in
    # build_npc_blueprints.py), so its own six are copied onto the component at
    # possession by its own AI controller -- the same route its health takes.
    install_hit_reactions(bp, handle)

    if not BEL.compile_blueprint(bp):
        raise RuntimeError("BP_ForestWanderer failed to compile")
    # Its health replicates as the player's does (damage.py): a template's
    # default, written after a compile.
    net.replicate_component(bp, "HealthComponent")
    # How far a wanderer is sent, and how often (task A2): on the body here as
    # npc/character.py writes it, so either build leaves it in place.
    relevancy.apply(bp, CHARACTER)
    if not BEL.compile_blueprint(bp):
        raise RuntimeError("BP_ForestWanderer failed to compile")
    eas.save_loaded_asset(bp)
    _log("NPC: HealthComponent + FootstepComponent installed "
         "(despawns and respawns at 0 HP)")
    return bp


def retire_old_assets():
    """Delete assets this build has superseded, once nothing references them.

    Both cases are the same shape: an asset that an earlier version of this
    builder created and that nothing now points at. Neither disappears on its
    own -- this builder updates in place, so a reference it simply stops
    emitting leaves the old asset sitting in the content tree, where the next
    person to read the audio folder will reasonably assume it is still in use.
    """
    eas = _assets()
    for path in (OLD_SHOTGUN_BP,) + RETIRED_SOUNDS:
        if not eas.does_asset_exist(path):
            continue
        try:
            if eas.delete_asset(path):
                _log(f"deleted the superseded {path}")
        except Exception as exc:                                  # noqa: BLE001
            _log(f"note: {path} still referenced, left in place: {exc}")
