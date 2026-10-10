"""build_steps.py -- the weapons build as a table of steps.

Owns: what ``build_weapons_and_combat.main()`` does, in order, one ``Step`` per
piece (``name``, ``function``, ``needs``), and the selection of a few of them
(``UEPY_BUILD_ONLY=<step[,step]>``, set by ``uepy.py --only``). Each function
takes a ``Ctx``, which holds what earlier steps made (the item Blueprint, the
weapons, the clips...). A step run alone finds those on disk, where the last
full build left them.

``needs`` are the steps whose products a step consumes. Under ``--only``, a
need that is not selected is met by its ``made`` assets existing on disk; if
one is missing the run stops before it builds anything. A need with no
``made`` (a patch to an existing asset) cannot be checked and is accepted.
"""

import os

import unreal

from combat import health_vars as HV
from combat import input_consts as INPUT
from combat import paths as P
from combat.aim_pitch import patch_aim_pitch
from combat.ammo_pickup import build_ammo_pickup
from combat.anim_blueprint import patch_anim_blueprint
from combat.axe import build_axe
from combat.blood import build_blood_splash
from combat.body_pose import patch_body_pose
from combat.bullet_impact import build_bullet_impact
from combat.combat_trace import build_combat_trace_switch
from combat.footsteps import build_footstep_component
from combat.game_state import ensure_game_mode_vars
from combat.glimmer import build_glimmer_material
from combat.input_assets import build_input_assets
from combat.gas_locomotion import build_gas_locomotion, resave_gas_locomotion
from combat.heat import build_hot_material
from combat.health_component import build_health_component
from combat.hit_bodies import fit_hit_bodies
from combat.hold_pose import build_hold_poses
from combat.install import install_on_character, install_on_npc, retire_old_assets
from combat.knife import build_knife
from combat.log import _log
from combat.matches import build_matches
from combat.materials import build_materials
from combat.melee_clips import build_melee_clips
from combat.player_gait import patch_gait
from combat.ragdoll import tune_ragdolls
from combat.server_anim import patch_server_anim, unpatch_server_anim
from combat.server_anim_consts import PLAYER
from combat.settings_savegame import build_settings_savegame
from combat.shotgun_hold import retire_keyed_pose
from combat.skin import player_skin, wear_skin
from combat.stance_clips import patch_stance_clips, retire_player_patches, unpatch_stance_clips
from combat.stick import build_stick
from combat.support_hand import patch_support_hand
from combat.throw_arc import build_throw_arc
from combat.throw_pose import build_throw_ready
from combat.tuning import GUN_DROP_CHANCE, GUN_LOOT_TABLE
from combat.weapon_component.build import build_weapon_component
from combat.weapon_items import build_weapon, build_weapon_item
from combat.weapon_layers import build_weapon_layers
from combat.weapon_specs import DROP_TICKETS, _weapon_specs
from combat.wood import build_wood
from net.players import build_players
from net.state import build_state
from Sound.build import build_sound_assets
from uebp.graph import BEL, _apply_defaults, _must_load

ENV_ONLY = "UEPY_BUILD_ONLY"

# A loot-table name (combat.tuning.GUN_LOOT_TABLE) -> the weapon's Blueprint.
_GUN_PATHS = {"Shotgun": P.SHOTGUN_BP_PATH, "Pistol": P.PISTOL_BP_PATH, "SMG": P.SMG_BP_PATH,
              "Rifle": P.RIFLE_BP_PATH, "Sniper": P.SNIPER_BP_PATH}


class Ctx:
    """What steps hand on. A value no step made in this run is loaded from disk."""

    def __init__(self):
        self._made = {}

    def put(self, key, value):
        self._made[key] = value
        return value

    def _get(self, key, path):
        if key not in self._made:
            self._made[key] = _must_load(path)
        return self._made[key]

    @property
    def skin(self):
        if "skin" not in self._made:
            self._made["skin"] = player_skin()
        return self._made["skin"]

    item_bp = property(lambda s: s._get("item_bp", P.ITEM_BP_PATH))
    knife_bp = property(lambda s: s._get("knife_bp", P.KNIFE_BP_PATH))
    axe_bp = property(lambda s: s._get("axe_bp", P.AXE_BP_PATH))
    wood_bp = property(lambda s: s._get("wood_bp", P.WOOD_BP_PATH))
    matches_bp = property(lambda s: s._get("matches_bp", P.MATCHES_BP_PATH))
    stick_bp = property(lambda s: s._get("stick_bp", P.STICK_BP_PATH))
    blood_bp = property(lambda s: s._get("blood_bp", P.BLOOD_BP_PATH))
    impact_bp = property(lambda s: s._get("impact_bp", P.BULLET_IMPACT_BP_PATH))
    health_bp = property(lambda s: s._get("health_bp", P.HEALTH_BP_PATH))
    footstep_bp = property(lambda s: s._get("footstep_bp", P.FOOTSTEP_BP_PATH))
    throw_arc_bp = property(lambda s: s._get("throw_arc_bp", P.THROW_ARC_BP_PATH))
    weapon_bp = property(lambda s: s._get("weapon_bp", P.WEAPON_COMP_BP_PATH))
    ammo_bp = property(lambda s: s._get("ammo_bp", P.AMMO_BP_PATH))
    knife_clip = property(lambda s: s._get("knife_clip", P.KNIFE_ANIM_PATH))

    def weapon(self, name):
        return self._get("weapon:" + name, _GUN_PATHS[name])


class Step:
    def __init__(self, name, function, needs=(), made=()):
        self.name, self.function, self.needs, self.made = name, function, tuple(needs), tuple(made)


# ─── The steps ───────────────────────────────────────────────────────────────

def _materials(c):
    build_materials()


def _hot_material(c):
    # Before the knife and the axe, whose glow is an instance of it.
    build_hot_material()


def _sound_assets(c):
    # Scripts/build_sound.py's first step, run here too so a fresh checkout
    # builds in the old order.
    build_sound_assets()


def _anim_blueprint(c):
    # Before any builder walks the anim graph (server_anim.py, "Order").
    unpatch_server_anim(P.ABP_PATH)
    patch_anim_blueprint()


def _settings_savegame(c):
    # First of the Blueprints: the weapon component's defaults and the HUD's
    # settings screen both have to be able to load BP_Settings.
    build_settings_savegame()


def _body(c):
    # Before the weapons: every GripRotation is solved against the ready pose
    # as seen through the player's own rig, so the body is final first.
    skin = c.skin
    if skin.gas:
        # The weapon layers' graph from nothing, then the motion-matching anim
        # Blueprint that links it in, both before the body that runs them.
        build_weapon_layers()
        build_gas_locomotion()
    wear_skin(skin)
    if skin.anim_bp != P.ABP_PATH:
        # ABP_Unarmed is not the player's: what an earlier body left in it goes.
        retire_player_patches(P.ABP_PATH)
    unpatch_server_anim(skin.anim_bp)
    # Before anything compiles the anim BP (see unpatch_stance_clips).
    unpatch_stance_clips(skin)


def _anim_patches(c):
    skin = c.skin
    # Before the weapon component, whose Tick sets the AimPitch this declares.
    patch_aim_pitch(skin)
    patch_body_pose(skin)
    # After the pitch, whose chain it joins the end of.
    patch_support_hand(skin)
    # The crouch and the crawl clips under everything else.
    patch_stance_clips(skin)
    # The jog's speed onto the blend space's jog row, or the player walks.
    patch_gait(skin)
    # Last of the anim graph's patches: the one branch a dedicated server takes.
    patch_server_anim(skin.anim_bp, PLAYER)
    if skin.gas:
        # The base holds the layers' class, which every patch above recompiled.
        resave_gas_locomotion()


def _input_assets(c):
    # Before the install, which names them on the player character.
    build_input_assets()


def _glimmer_material(c):
    # Before the items: the base one carries the sprite it is drawn on.
    build_glimmer_material()


def _weapon_item(c):
    c.put("item_bp", build_weapon_item())


def _weapons(c):
    for spec in _weapon_specs():
        c.put("weapon:" + spec["display"], build_weapon(spec, c.item_bp))
    # The shotgun's Blueprint no longer names its keyed pose (C3).
    retire_keyed_pose()


def _hold_poses(c):
    # Before the knife and the consumables, whose grips are solved in them.
    build_hold_poses(c.skin)


def _melee_clips(c):
    # The knife's and the axe's ready pose and swing: Mixamo's clips.
    c.put("knife_clip", build_melee_clips(c.skin)[P.KNIFE_ANIM_PATH])


def _throw_ready(c):
    # The arm cocked while a throw is aimed: the throw clip, stopped.
    build_throw_ready(c.skin)


def _knife(c):
    c.put("knife_bp", build_knife(c.item_bp))


def _axe(c):
    c.put("axe_bp", build_axe(c.item_bp))


def _wood(c):
    c.put("wood_bp", build_wood(c.item_bp))


def _matches(c):
    c.put("matches_bp", build_matches(c.item_bp))


def _stick(c):
    c.put("stick_bp", build_stick(c.item_bp))


def _blood(c):
    c.put("blood_bp", build_blood_splash())


def _bullet_impact(c):
    c.put("impact_bp", build_bullet_impact())


def _state(c):
    # Before the health component: its BeginPlay casts to the GameMode, and a
    # cast node only appears in the palette for a class that is already loaded.
    # The PlayerState and the GameState (what a client reads) first, for the
    # same reason, and named on the GameMode.
    build_state()
    build_players()
    ensure_game_mode_vars()
    build_combat_trace_switch()


def _health(c):
    c.put("health_bp", build_health_component())


def _footsteps(c):
    c.put("footstep_bp", build_footstep_component())


def _throw_arc(c):
    c.put("throw_arc_bp", build_throw_arc())


def _weapon_component(c):
    c.put("weapon_bp", build_weapon_component(
        c.item_bp, c.weapon("Shotgun"), c.weapon("Pistol"), c.knife_bp, c.axe_bp,
        c.knife_clip, c.blood_bp, c.impact_bp, c.throw_arc_bp,
        c.wood_bp, c.matches_bp, c.stick_bp))


def _ammo_pickup(c):
    # After the weapon component, because the pickup's graph casts to it.
    c.put("ammo_bp", build_ammo_pickup())


def _health_defaults(c):
    # After the ammo pickup and the weapons: a default written here rather than
    # a parameter of the health component, which the pickup's spawner precedes.
    _apply_defaults(c.health_bp, {
        HV.AmmoClass: BEL.generated_class(c.ammo_bp),
        # The loot table, one entry per ticket (GUN_LOOT_TABLE's weights), so
        # the graph's uniform pick roll over it is the weighted draw.
        HV.DropClasses: [BEL.generated_class(c.weapon(name)) for name in DROP_TICKETS],
    })
    _log(f"{P.HEALTH_BP_PATH}.AmmoClass -> {P.AMMO_BP_PATH}")
    _log(f"{P.HEALTH_BP_PATH}.DropClasses -> "
         f"{', '.join(f'{n} x{w}' for n, w in GUN_LOOT_TABLE)} "
         f"({GUN_DROP_CHANCE * 100:.0f}% per kill)")


def _bodies(c):
    tune_ragdolls()
    fit_hit_bodies()


def _install(c):
    install_on_character(c.health_bp, c.weapon_bp, c.footstep_bp)
    install_on_npc(c.health_bp, c.footstep_bp)
    retire_old_assets()


def _done(c):
    _log(f"done — five weapons, a knife, an axe, matches and a stick, ammunition, inventory, aiming down the sights, "
         f"footsteps, blood, death, drops and respawn, worn by "
         f"{c.skin.mesh.rsplit('/', 1)[1]}")


_WEAPONS = tuple(_GUN_PATHS.values())

STEPS = (
    Step("materials", _materials),
    Step("hot_material", _hot_material),
    Step("sound_assets", _sound_assets),
    Step("anim_blueprint", _anim_blueprint),
    Step("settings_savegame", _settings_savegame, made=(P.SETTINGS_BP_PATH,)),
    Step("body", _body),
    Step("anim_patches", _anim_patches, needs=("body",)),
    Step("glimmer_material", _glimmer_material),
    Step("input_assets", _input_assets, made=(INPUT.IMC_DEFAULT, INPUT.IA_FIRE)),
    Step("weapon_item", _weapon_item, made=(P.ITEM_BP_PATH,)),
    Step("weapons", _weapons, needs=("weapon_item",), made=_WEAPONS),
    Step("hold_poses", _hold_poses),
    Step("melee_clips", _melee_clips, made=(P.KNIFE_ANIM_PATH,)),
    Step("throw_ready", _throw_ready),
    Step("knife", _knife, needs=("weapon_item", "melee_clips"), made=(P.KNIFE_BP_PATH,)),
    Step("axe", _axe, needs=("weapon_item",), made=(P.AXE_BP_PATH,)),
    Step("wood", _wood, needs=("weapon_item",), made=(P.WOOD_BP_PATH,)),
    Step("matches", _matches, needs=("weapon_item",), made=(P.MATCHES_BP_PATH,)),
    Step("stick", _stick, needs=("weapon_item",), made=(P.STICK_BP_PATH,)),
    Step("blood", _blood, made=(P.BLOOD_BP_PATH,)),
    Step("bullet_impact", _bullet_impact, made=(P.BULLET_IMPACT_BP_PATH,)),
    Step("state", _state),
    Step("health", _health, needs=("state",), made=(P.HEALTH_BP_PATH,)),
    Step("footsteps", _footsteps, made=(P.FOOTSTEP_BP_PATH,)),
    Step("throw_arc", _throw_arc, made=(P.THROW_ARC_BP_PATH,)),
    Step("weapon_component", _weapon_component,
         needs=("weapon_item", "weapons", "melee_clips", "knife", "axe", "wood", "matches", "stick",
                "blood", "bullet_impact", "throw_arc", "health"),
         made=(P.WEAPON_COMP_BP_PATH,)),
    Step("ammo_pickup", _ammo_pickup, needs=("weapon_component",), made=(P.AMMO_BP_PATH,)),
    Step("health_defaults", _health_defaults, needs=("health", "weapons", "ammo_pickup")),
    Step("bodies", _bodies),
    Step("install", _install, needs=("health", "weapon_component", "footsteps", "input_assets")),
    Step("done", _done),
)
BY_NAME = {s.name: s for s in STEPS}


# ─── Selection ───────────────────────────────────────────────────────────────

def selection(raw):
    """The steps named in ``raw`` ("a,b"), in table order; None for all of them.
    An unknown name, or a need that was not run and whose assets are not on
    disk, is an error."""
    names = [n.strip() for n in (raw or "").split(",") if n.strip()]
    if not names:
        return None
    unknown = [n for n in names if n not in BY_NAME]
    if unknown:
        raise RuntimeError(f"{ENV_ONLY}: no such step {', '.join(unknown)}; steps: "
                           f"{', '.join(BY_NAME)}")
    chosen = [s for s in STEPS if s.name in names]
    eas = unreal.EditorAssetLibrary
    for step in chosen:
        for need in step.needs:
            if need in names:
                continue
            missing = [p for p in BY_NAME[need].made if not eas.does_asset_exist(p)]
            if missing:
                raise RuntimeError(f"step {step.name} needs step {need}, which was not run and "
                                   f"left no {missing[0]}: run it too, or a full build first")
    return chosen


def run(raw=None):
    """Run the steps named in ``raw`` (default: $UEPY_BUILD_ONLY; empty: all)."""
    if raw is None:
        raw = os.environ.pop(ENV_ONLY, "")
    chosen = selection(raw)
    if chosen is not None:
        _log(f"only: {', '.join(s.name for s in chosen)}")
    ctx = Ctx()
    for step in (STEPS if chosen is None else chosen):
        step.function(ctx)
