"""build_weapon_component(): declares BP_WeaponComponent's variables, sets
its defaults and authors BeginPlay and Tick from the sibling modules.
"""

import unreal

from combat.log import _log
from uebp.graph import (
    BEL, BGE, _apply_defaults, _assets, _create_blueprint, _events, _must_load,
    _post_physics_tick,
)
from uebp import net
from uebp.layout import arrange
from combat.paths import (
    CHARACTER_BP_PATH, HEALTH_BP_PATH, ITEM_BP_PATH, THROW_ARC_BP_PATH,
    THROW_READY_ANIM_PATH, WEAPON_COMP_BP_PATH,
)
from combat.skin import player_skin
from combat.weapon_component.interact import INTERACT_NO_GAP, RETIRED_VARS
from combat.weapon_component.inventory import _author_wc_begin_play
from combat.weapon_component.knife import axe_clip_defaults
from combat.weapon_component.stance import STAND
from combat.weapon_component.asks import author_asks
from combat.weapon_component.look import author_set_look, replicate_look
from combat.weapon_component.look_vars import TABLE as LOOK_TABLE
from combat.record_vars import TABLE as RECORD_TABLE
from combat.weapon_component.record import retire_mirror
from combat.dirty import CARRIER, mark_change_sites
from combat.weapon_component.view import author_view_events
from combat.weapon_component.view_worn import author_view_worn_event
from combat.weapon_component.consume import author_consume_event
from combat.weapon_component.wear import author_wear_event
from combat.weapon_component.wear_draw import author_draw_worn_event
from combat.weapon_component.shot import author_shot_events, replicate_shot
from combat.weapon_component import native
from combat.weapon_component.headshot import replicate_headshot
from combat.weapon_component.chop import author_chop_fx
from combat.weapon_component.fire import author_fire_events
from combat.weapon_component.impact import author_pellet_fx
from combat.weapon_component.throw import author_throw_fx
from combat.weapon_component.throw_strike import author_throw_strike_fx
from combat import fx_vars as FX
from combat.shot_vars import TABLE as SHOT_TABLE
from combat.strike_vars import TABLE as STRIKE_TABLE
from combat.weapon_component.holds import author_set_holds, replicate_holds
from combat.weapon_component.knife import KNIFE
from combat.weapon_component.pickup import author_take_event
from combat.weapon_component.punch import PUNCH, author_strike_event, author_strike_fx
from combat.weapon_component.throw import author_throw_event
from combat.weapon_component.loot_take import author_loot_take
from combat.weapon_component.save_exit import author_ask_save_exit
from combat.weapon_component.tick import _author_wc_tick
from uebp.vars import declare, defaults
from Sound.bind import defaults_for
from Sound.sound_items import BINDINGS as ITEM_SOUNDS
from Sound.sound_weapons import BINDINGS as WEAPON_SOUNDS
from Sound.sound_world import BINDINGS as WORLD_SOUNDS
from combat.weapon_component import vars as WV


def _kept_class(bp, var):
    """A class default as the last build left it, or None on a first build."""
    cls = BEL.generated_class(bp)
    try:
        return unreal.get_default_object(cls).get_editor_property(var) if cls else None
    except Exception:                                             # noqa: BLE001
        return None


def build_weapon_component(item_bp, shotgun_bp, pistol_bp, knife_bp, axe_bp,
                           knife_clip, blood_bp, impact_bp, throw_arc_bp, wood_bp,
                           matches_bp, stick_bp, rebuild=True):
    # Cast nodes only appear in the palette for classes that are already loaded,
    # and this graph casts to all three. Without these loads
    # create_node_from_name returns None and the failure reads as a typo in the
    # node name rather than as a missing asset.
    for path in (CHARACTER_BP_PATH, ITEM_BP_PATH, HEALTH_BP_PATH, THROW_ARC_BP_PATH):
        if not _assets().load_asset(path):
            raise RuntimeError(f"could not load {path} for its cast node")

    # A child of the native base (native.py): the shot's server half is C++.
    bp = _create_blueprint(WEAPON_COMP_BP_PATH, native.base_class())
    # Re-declaring a variable empties it, and this one is build_survival.py's
    # to fill: what an earlier build was given is put back below.
    campfire_class = _kept_class(bp, WV.CampfireClass)
    ed = BGE.get_graph_editor_by_name(bp, "EventGraph")
    native.retire_events(ed)
    native.reparent(bp, ed)
    # The reparent compiled the Blueprint: the graph is asked for again.
    ed = BGE.get_graph_editor_by_name(bp, "EventGraph")
    tick, begin = _events(ed, rebuild)

    item_class = BEL.generated_class(item_bp)
    declare(ed, WV.CORE)
    # The headshot's stamp travels to the owner (headshot.py).
    replicate_headshot(bp)
    # The fight as everyone sees and hears it (fx.py): the counter a probe reads.
    declare(ed, FX.TABLE)
    # The look (look.py): declared, then replicated, on every build.
    declare(ed, LOOK_TABLE)
    replicate_look(bp)
    # The view of the inventory's record and the probes' asks (record_vars.py):
    # nothing of it replicates here, the record is its own component's.
    declare(ed, RECORD_TABLE)
    retire_mirror(bp, ed)
    # The shot's and the reload's asks (shot.py): the counters that reconcile
    # a client's predicted rounds.
    declare(ed, SHOT_TABLE)
    replicate_shot(bp)
    # Melee, the guard, the throw and the take as server requests
    # (combat/strike_vars.py): what the owning machine reports and the server keeps.
    declare(ed, STRIKE_TABLE)
    # The rest of the component's own, last as it always was. The order is not
    # free: declared ahead of the tables above, the one literal on an array
    # node (shot_hits.note's Add onto ShotHitBloods) is kept as "0", not "false".
    declare(ed, WV.STATE)
    # The names the interact had as the pick-up are taken off a component
    # built before the rename.
    for name in RETIRED_VARS + native.RETIRED_VARS:
        ed.remove_member_variable(name)
    arc_class = BEL.generated_class(throw_arc_bp)

    # First: the Tick calls it by name, and a call finds only an event that exists.
    author_set_look(ed)
    # What a screen asks of the component: one event each (combat/ask_consts.py).
    # The slots' keys call theirs, and the upkeep the view's two (view.py).
    author_asks(ed)
    author_draw_worn_event(ed)      # before the wears, which call it by name
    author_wear_event(ed)
    author_consume_event(ed)
    author_view_events(ed)
    author_view_worn_event(ed)
    # The cosmetics (fx.py, combat/fx_vars.py): each pair before the event
    # or the Tick fragment that tells or predicts it.
    author_pellet_fx(ed)
    author_strike_fx(ed, PUNCH)
    author_strike_fx(ed, KNIFE)
    author_throw_fx(ed)
    author_throw_strike_fx(ed)
    author_chop_fx(ed)
    author_shot_events(ed)
    # M20's requests: the two swings, the guard and the use key, the throw
    # and the take. Blocking travels to the other players, and Thrown to the
    # owner, whose arc waits for it: flagged here, after every declare.
    replicate_holds(bp)
    net.replicate(bp, WV.Thrown, unreal.LifetimeCondition.COND_OWNER_ONLY)
    author_strike_event(ed, PUNCH)
    author_strike_event(ed, KNIFE)
    author_set_holds(ed)
    author_throw_event(ed)
    author_take_event(ed)
    author_fire_events(ed)   # M25: the matches, the stick, the heat, the bleed
    _author_wc_begin_play(ed, begin)
    _author_wc_tick(ed, tick)
    author_loot_take(ed)
    author_ask_save_exit(ed)

    # Every node above that changes what is carried is followed by the mark
    # that has the record written (combat/dirty.py): last, once the graph is
    # whole.
    sites = mark_change_sites(ed, CARRIER)
    _log(f"BP_WeaponComponent: {len(sites)} change sites marked for the record")
    _post_physics_tick(bp)
    arrange(ed)
    if not BEL.compile_blueprint(bp):
        raise RuntimeError("BP_WeaponComponent failed to compile")
    # The names the native base reads the Blueprints by, baked in with the rest.
    native.write_names(bp)
    _apply_defaults(bp, {**defaults(WV.TABLE), **defaults(LOOK_TABLE), **defaults(RECORD_TABLE), **defaults(SHOT_TABLE), **defaults(FX.TABLE), **defaults_for(WEAPON_COMP_BP_PATH, WEAPON_SOUNDS + ITEM_SOUNDS + WORLD_SOUNDS),
        # What the table cannot name: a constant of a graph module, a class
        # this build was handed, a clip it loads.
        WV.Stance: STAND,
        WV.InteractGap: INTERACT_NO_GAP,
        WV.ShotgunClass: BEL.generated_class(shotgun_bp),
        WV.PistolClass: BEL.generated_class(pistol_bp),
        WV.KnifeClass: BEL.generated_class(knife_bp),
        WV.AxeClass: BEL.generated_class(axe_bp),
        WV.MatchesClass: BEL.generated_class(matches_bp),
        WV.StickClass: BEL.generated_class(stick_bp),
        WV.ItemClass: item_class,
        WV.BloodClass: BEL.generated_class(blood_bp),
        WV.ImpactClass: BEL.generated_class(impact_bp),
        WV.WoodClass: BEL.generated_class(wood_bp),
        WV.CampfireClass: campfire_class,
        WV.PunchAnim: _must_load(player_skin().punch),
        WV.KnifeAnim: knife_clip,
        **axe_clip_defaults(),
        # No entry for a skin without the clip: the variable stays None.
        **({WV.ThrowAnim: _must_load(player_skin().throw),
            WV.ThrowReadyAnim: _must_load(THROW_READY_ANIM_PATH)}
           if player_skin().throw else {}),
        WV.ThrowArcClass: arc_class,
    })
    # The component replicates (its look, to the other players): a class
    # default, so after the compile and with one more (uebp/CLAUDE.md).
    net.replicate_component(bp)
    if not BEL.compile_blueprint(bp):
        raise RuntimeError("BP_WeaponComponent failed to compile")
    if native.wrong_names(bp):
        raise RuntimeError(f"the native base's names did not hold: {native.wrong_names(bp)}")
    _assets().save_loaded_asset(bp)
    _log(f"built {WEAPON_COMP_BP_PATH}")
    return bp
