"""Installing on the characters: puts the health, weapon and footstep
components on BP_ThirdPersonCharacter and the wanderer (and, on a player who
wears the motion matching, the sample's foley component, silenced), and
retires superseded assets.
"""

import unreal

from Sound.bind import write_components
from Sound.sound_monsters import BINDINGS as MONSTER_SOUNDS
from Sound.sound_weapons import RETIRED_SOUNDS
from combat import gas_locomotion_consts as GAS
from combat.camera import aim_camera, face_the_camera
from combat import gas_moves_tuning as MOVES
from combat.gas_locomotion import silent_foley_bank
from combat.gas_traversal import (
    author_jump, install_traversal, replicate_traversal, unauthor_jump,
)
from combat.log import _log
from uebp import net
from uebp.nodes.guard import GUARD_CLASS
from uebp.graph import (
    BEL, _add_component, _assets, _component_object, _drop_components, _handles,
    _root_handle)
from combat.hit_reaction import install_hit_reactions
from combat.hit_zones import install_hit_zones, make_shootable
from combat.paths import CHARACTER_BP_PATH, NPC_BP_PATH, NPC_CLASS_PATH
from combat.player_move import reparent_player, set_move_numbers
from combat.player_pace import set_jog_speed
from combat.skin import player_skin
from combat.record_vars import (
    RECORD_COMPONENT, RECORD_COMPONENT_CLASS, RECORD_HAND_SLOT, RECORD_SOURCE, RECORD_VIEW)
from combat.weapon_component.stance import allow_crouch
from net import relevancy
from net.guard_consts import GUARD_COMPONENT, NUMBERS, RATES
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


def install_record(bp):
    """The component that holds the inventory's record (C++; task A3a), beside
    the weapon component it reads, told the names it reads by and the one it
    raises on a client when a record arrives (combat/record_vars.py). It replicates by its own constructor."""
    cls = unreal.load_class(None, RECORD_COMPONENT_CLASS)
    if not cls:
        raise RuntimeError(f"{RECORD_COMPONENT_CLASS} is not loaded: compile the "
                           "Otherworld module (Source/CLAUDE.md)")
    template = _component_object(_add_component(bp, _root_handle(bp), cls, RECORD_COMPONENT))
    for prop, name in {**RECORD_SOURCE, **RECORD_VIEW}.items():
        template.set_editor_property(prop, name)
        if str(template.get_editor_property(prop)) != name:
            raise RuntimeError(f"{RECORD_COMPONENT}.{prop} did not take {name!r}")
    template.set_editor_property(*RECORD_HAND_SLOT)


def install_guard(bp):
    """The component every Server event asks first (C++; task A5), given its
    table: how often each event may be asked, when refusals close the
    connection, and the aim a shot may name (net/guard_consts.py)."""
    cls = unreal.load_class(None, GUARD_CLASS)
    if not cls:
        raise RuntimeError(f"{GUARD_CLASS} is not loaded: compile the Otherworld "
                           "module (Source/CLAUDE.md)")
    template = _component_object(_add_component(bp, _root_handle(bp), cls, GUARD_COMPONENT))
    template.set_editor_property("rates", dict(RATES))
    got = {str(k): float(v) for k, v in template.get_editor_property("rates").items()}
    if got.keys() != RATES.keys() or any(abs(got[k] - RATES[k]) > 1e-4 for k in RATES):
        raise RuntimeError(f"{GUARD_COMPONENT}.rates did not take the table: {got}")
    for prop, value in NUMBERS.items():
        template.set_editor_property(prop, value)
        if abs(float(template.get_editor_property(prop)) - value) > 1e-3:
            raise RuntimeError(f"{GUARD_COMPONENT}.{prop} did not take {value!r}")


def install_foley(bp):
    """The Game Animation Sample's foley component, with a sound bank that
    holds nothing, on a player who wears its motion matching (player_skin().gas).
    Its clips' foot, jump and land notifies look for it on the owner and,
    finding none, play the sample's own sound in 2D; found, they fire into it,
    and it has nothing to play. The game's footsteps stay BP_FootstepComponent's."""
    if not player_skin().gas:
        return
    name = GAS.FOLEY_COMPONENT_BP.rsplit("/", 1)[1]
    cls = unreal.load_class(None, f"{GAS.FOLEY_COMPONENT_BP}.{name}_C")
    if not cls:
        raise RuntimeError(f"{GAS.FOLEY_COMPONENT_BP} is not here: run "
                           "asset_pipeline/import_gas.py")
    bank = silent_foley_bank()
    template = _component_object(_add_component(bp, _root_handle(bp), cls,
                                                GAS.FOLEY_COMPONENT))
    template.set_editor_property(GAS.FOLEY_BANK_VAR, bank)
    if template.get_editor_property(GAS.FOLEY_BANK_VAR) != bank:
        raise RuntimeError(f"{GAS.FOLEY_COMPONENT} did not take the silent bank: the "
                           "sample's footsteps would play over the game's")


def install_on_character(health_bp, weapon_bp, footstep_bp):
    eas = _assets()
    bp = eas.load_asset(CHARACTER_BP_PATH)
    if not bp:
        raise RuntimeError(f"could not load {CHARACTER_BP_PATH}")
    # First: it recompiles the Blueprint, and component handles do not outlive that.
    reparent_player(bp)
    _uninstall_old_shotgun(bp)
    # Before its component goes: the jump key's traversal nodes read it.
    unauthor_jump(bp)
    _drop_components(bp, {"HealthComponent", "WeaponComponent", "FootstepComponent",
                          RECORD_COMPONENT, GUARD_COMPONENT, GAS.FOLEY_COMPONENT,
                          MOVES.TRAVERSAL_COMPONENT, MOVES.WARP_COMPONENT})
    handles = {}
    for name, source in (("HealthComponent", health_bp),
                         ("WeaponComponent", weapon_bp),
                         ("FootstepComponent", footstep_bp)):
        handles[name] = _add_component(bp, _root_handle(bp),
                                       BEL.generated_class(source), name)
    install_record(bp)
    install_guard(bp)
    install_foley(bp)
    # The sample's traversal (G5): its component and the warp its montages need.
    install_traversal(bp)
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
    replicate_traversal(bp)
    # The jump key tries a traversal first (G5); it reads the component, so
    # after the compile that made it a variable.
    author_jump(bp)
    # How far a player's character is sent, and how often (task A2).
    relevancy.apply(bp, CHARACTER)
    if not BEL.compile_blueprint(bp):
        raise RuntimeError("BP_ThirdPersonCharacter failed to compile")
    eas.save_loaded_asset(bp)
    _log("player: HealthComponent + WeaponComponent + FootstepComponent + "
         f"{RECORD_COMPONENT} + {GUARD_COMPONENT} installed")


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
