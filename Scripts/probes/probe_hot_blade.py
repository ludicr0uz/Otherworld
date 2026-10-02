"""The heated blade: the interact key at a campfire makes the knife (or the
axe) hot for 20 s, a hot blade cauterises a bleed on the use key, and its blow
does double damage to a wendigo.

The fire is lit the way the game lights it (wood cut with the axe, a strike
of the matches: probe_campfire.py's steps). InteractForced and SightsForced
stand in for the two keys and KnifeQueued for the click (no key can be
injected into a headless game).

  - with no campfire anywhere, and then out of a fire's reach, the interact
    key heats nothing; nor does it heat the stick, which does not Heat;
  - within reach it makes the knife Hot until CoolTime, HEAT_S on: the model
    wears its glow and the light is lit;
  - a bleed (GE_Bleeding, its tag granted on the spec as a wendigo's blow
    grants it) is left alone by the use key on a cold blade, and taken off by
    it on a hot one, which stays hot;
  - its time run out (CoolTime written into the past: a headless game's clock
    is slow) the blade cools by itself, and the glow goes with it;
  - a cold slash takes the knife's damage off a wendigo, a hot one twice
    that; a hot one takes only the knife's damage off a zombie;
  - the axe heats too.

One wendigo and one zombie are kept, without their controllers, so they
stand where they are put and do not hit back; the rest are removed.

Any profile on disk is set aside first, so the game starts on the issued
loadout, and put back at the end.

Run with --windowed and OW_HOT_SHOTS=1 to save a picture of the hot knife and
the hot axe, from in front of the player, to Saved/Screenshots/MacEditor.
"""

import os
import shutil

import unreal

from combat.heat_tuning import (
    COOL_VAR, FIRE_FEAR_TAG, HEAT_GLOW, HEAT_MATERIAL_VAR, HEAT_S, HEATS_VAR,
    HOT_BLOW_SCALE, HOT_VAR, MODEL,
)
from combat.paths import (
    HEALTH_BP_PATH, HEALTH_CLASS_PATH, ITEM_BP_PATH, WEAPON_COMP_BP_PATH,
    WEAPON_COMP_CLASS_PATH,
)
from combat.seat_tuning import SIGHTS_FORCED_VAR
from combat.tuning import BLEEDING_TAG, COMBAT, INTERACT_RADIUS
from combat.weapon_component.interact import INTERACT_FORCED_VAR
from combat.weapon_component.knife import KNIFE_PENDING_VAR, KNIFE_QUEUED_VAR
from combat.weapon_component.tick import FIRE_FORCED_VAR
from probes.probe_campfire import MATCHES, _bag, _cut_wood, _fires, _strike
from probes.probe_chop_tree import _equip
from probes.probe_knife import _file, _held_name
from survival.paths import BLEEDING_GE_CLASS_PATH

WRITABLE = ([(WEAPON_COMP_BP_PATH, v) for v in
             ("EquippedIndex", "NeedsRefresh", "Inventory", KNIFE_QUEUED_VAR,
              INTERACT_FORCED_VAR, FIRE_FORCED_VAR, SIGHTS_FORCED_VAR)]
            + [(ITEM_BP_PATH, COOL_VAR), (HEALTH_BP_PATH, "Health")])

KNIFE, AXE, STICK = "BP_Knife_C", "BP_Axe_C", "BP_Stick_C"
FAR_CM = 2.0 * INTERACT_RADIUS
IN_FRONT_CM = 100.0       # capsule centre to capsule centre: inside the reach
BODY_HP = 200.0           # room for a doubled blow
AWAY_CM = 3000.0          # where the body not being struck waits
SHOTS = bool(os.environ.get("OW_HOT_SHOTS"))
SHOT_FROM_CM = 110.0      # the eye, in front of the player
SHOT_FOV = 60.0


def probe(p):
    backup = _file() + ".probe-backup"
    if os.path.exists(_file()):
        shutil.move(_file(), backup)
    try:
        yield from _run(p)
    finally:
        if os.path.exists(backup):
            shutil.move(backup, _file())


def _wanderers(p):
    ctrls = unreal.GameplayStatics.get_all_actors_of_class(p.world(), unreal.AIController)
    return [c for c in ctrls if c.get_class().get_name().startswith("BP_ForestWandererAI")
            and c.get_controlled_pawn() is not None]


def _of(p, creature):
    return next((c for c in _wanderers(p)
                 if c.get_class().get_name().startswith(f"BP_ForestWandererAI_{creature}")),
                None)


def _look(item):
    """(the model's overlay by name, whether the heat's light shows)."""
    overlay, lit = None, None
    for c in item.get_components_by_class(unreal.MeshComponent):
        if c.get_name() == MODEL:
            m = c.get_overlay_material()
            overlay = m.get_name() if m else None
    for c in item.get_components_by_class(unreal.PointLightComponent):
        if c.get_name() == HEAT_GLOW:
            lit = bool(c.is_visible())
    return overlay, lit


def _shot(p, player, eye):
    """Save a picture of the player's front (windowed runs only). The view
    turns the body with it (camera.py), so the game's own camera only ever
    sees the back: this looks through ``eye``, a body stood in front of the
    player and hidden, and puts it back where it was."""
    if not SHOTS:
        return
    pc, was = p.controller(), eye.get_actor_location()
    here, ahead = player.get_actor_location(), player.get_actor_forward_vector()
    eye.set_actor_hidden_in_game(True)
    eye.set_actor_location_and_rotation(
        here + ahead * SHOT_FROM_CM,
        unreal.Rotator(pitch=0.0, yaw=player.get_actor_rotation().yaw + 180.0, roll=0.0),
        False, True)
    pc.set_view_target_with_blend(eye)
    # The controller's own console command: it locks the camera manager's
    # FOV, and 0 lets it go again.
    unreal.SystemLibrary.execute_console_command(p.world(), f"FOV {SHOT_FOV:g}", pc)
    yield 0.6
    unreal.SystemLibrary.execute_console_command(p.world(), "shot")
    yield 0.4
    unreal.SystemLibrary.execute_console_command(p.world(), "FOV 0", pc)
    pc.set_view_target_with_blend(player)
    eye.set_actor_location(was, False, True)
    eye.set_actor_hidden_in_game(False)
    yield 0.1


def _press(p, wc):
    """One press of the interact key."""
    p.set(wc, INTERACT_FORCED_VAR, True)
    yield lambda: not p.get(wc, INTERACT_FORCED_VAR)
    yield 0.1


def _use(p, wc):
    """One press of the use key, let go again."""
    p.set(wc, SIGHTS_FORCED_VAR, True)
    yield 0.15
    p.set(wc, SIGHTS_FORCED_VAR, False)
    yield 0.1


def _bleeds(p, asc):
    """(stacks of the tag, active GE_Bleedings)."""
    return (asc.get_gameplay_tag_count(p.tag(BLEEDING_TAG)),
            asc.get_gameplay_effect_count(p.load_class(BLEEDING_GE_CLASS_PATH), None, True))


def _wound(p, asc):
    """A bleed as a blow leaves it (survival/on_hit_graph.py): the tag is
    granted on the spec, not by the asset."""
    spec = asc.make_outgoing_spec(p.load_class(BLEEDING_GE_CLASS_PATH), 1.0,
                                  asc.make_effect_context())
    spec = unreal.AbilitySystemLibrary.add_granted_tag(spec, p.tag(BLEEDING_TAG))
    asc.apply_gameplay_effect_spec_to_self(spec)


def _slash(p, wc, player, body, health):
    """Stand ``body`` in front of the player and slash it; returns the health
    it lost."""
    def place():
        body.set_actor_location(
            player.get_actor_location() + player.get_actor_forward_vector() * IN_FRONT_CM,
            False, True)

    p.set(health, "Health", BODY_HP)
    place()
    yield 0.05
    place()
    p.set(wc, KNIFE_QUEUED_VAR, True)
    yield lambda: not p.get(wc, KNIFE_QUEUED_VAR)
    place()
    yield lambda: not p.get(wc, KNIFE_PENDING_VAR)
    lost = BODY_HP - float(p.get(health, "Health"))
    # Out the cooldown, so the next slash is taken on its press.
    yield COMBAT.knife_interval_s
    return lost


def _run(p):
    yield lambda: _of(p, "Wendigo") is not None and _of(p, "Zombie") is not None
    yield 0.5
    player = p.pawn()
    wc = p.component(player, WEAPON_COMP_CLASS_PATH)
    asc = unreal.AbilitySystemLibrary.get_ability_system_component(player)
    p.check("the player has a weapon component and an ability system",
            wc is not None and asc is not None)
    if wc is None or asc is None:
        return

    # One of each creature, with no mind of its own; the rest are gone.
    bodies = {}
    for creature in ("Wendigo", "Zombie"):
        ctrl = _of(p, creature)
        bodies[creature] = ctrl.get_controlled_pawn()
        ctrl.un_possess()
    for other in _wanderers(p):
        other.get_controlled_pawn().destroy_actor()
    tags = {k: [str(t) for t in b.tags] for k, b in bodies.items()}
    p.check(f"the wendigo carries the {FIRE_FEAR_TAG} actor tag and the zombie does not",
            tags == {"Wendigo": [FIRE_FEAR_TAG], "Zombie": []}, str(tags))

    bag = _bag(p, wc)
    items = dict(zip(bag, p.get(wc, "Inventory")))
    p.check("the knife and the axe are the items that Heat",
            [n for n, i in items.items() if p.get(i, HEATS_VAR)] == [KNIFE, AXE], str(bag))
    if KNIFE not in items or AXE not in items:
        return
    knife, axe, stick = items[KNIFE], items[AXE], items.get(STICK)
    glow = p.get(knife, HEAT_MATERIAL_VAR)

    yield from _equip(p, wc, KNIFE)
    p.check("in hand the knife is cold: no overlay, no light",
            not p.get(knife, HOT_VAR) and _look(knife) == (None, False),
            f"Hot {p.get(knife, HOT_VAR)} {_look(knife)}")
    yield from _press(p, wc)
    p.check("the interact key with no campfire anywhere heats nothing",
            not p.get(knife, HOT_VAR) and not _fires(p), f"Hot {p.get(knife, HOT_VAR)}")

    # --- a bleed, and a cold blade ------------------------------------------------
    _wound(p, asc)
    yield 0.1
    p.check("the player is given a bleed", _bleeds(p, asc) == (1, 1), str(_bleeds(p, asc)))
    yield from _use(p, wc)
    p.check("the use key on a cold knife leaves the bleed", _bleeds(p, asc) == (1, 1),
            str(_bleeds(p, asc)))

    # --- the fire -------------------------------------------------------------------
    got = yield from _cut_wood(p, player, wc)
    p.check("the axe cuts a piece of wood and E takes it into the bag", got, str(_bag(p, wc)))
    if not got:
        return
    yield from _equip(p, wc, MATCHES)
    yield from _strike(p, wc)
    fires = _fires(p)
    p.check("a strike of the matches lights a campfire", len(fires) == 1, str(len(fires)))
    if len(fires) != 1:
        return
    at = fires[0].get_actor_location()
    near = player.get_actor_location()

    yield from _equip(p, wc, KNIFE)
    player.set_actor_location(near - player.get_actor_forward_vector() * FAR_CM
                              + unreal.Vector(0.0, 0.0, 30.0), False, True)
    yield 0.1
    gap = (player.get_actor_location() - at).length()
    yield from _press(p, wc)
    p.check(f"out of the fire's reach ({INTERACT_RADIUS:g} cm) the key heats nothing",
            gap > INTERACT_RADIUS and not p.get(knife, HOT_VAR),
            f"{gap:.0f} cm away, Hot {p.get(knife, HOT_VAR)}")
    player.set_actor_location(near, False, True)
    yield 0.1
    gap = (player.get_actor_location() - at).length()

    if stick is not None:
        yield from _equip(p, wc, STICK)
        yield from _press(p, wc)
        p.check("within it, with the stick in hand, the key heats nothing: a "
                "stick does not Heat",
                not p.get(stick, HOT_VAR) and not p.get(knife, HOT_VAR)
                and _held_name(p, wc) == STICK, _held_name(p, wc))
        yield from _equip(p, wc, KNIFE)

    t0 = p.time()
    p.set(wc, INTERACT_FORCED_VAR, True)
    yield lambda: not p.get(wc, INTERACT_FORCED_VAR)
    t1 = p.time()
    yield 0.1
    cool = float(p.get(knife, COOL_VAR))
    p.check("with the knife in hand, the interact key at the fire heats it",
            gap < INTERACT_RADIUS and p.get(knife, HOT_VAR) and _held_name(p, wc) == KNIFE,
            f"{gap:.0f} cm away, Hot {p.get(knife, HOT_VAR)}")
    p.check(f"...to stay hot {HEAT_S:g} s from the press",
            t0 + HEAT_S - 0.01 <= cool <= t1 + HEAT_S + 0.01,
            f"{COOL_VAR} {cool:.3f}, pressed between {t0:.3f} and {t1:.3f}")
    p.check("...glowing red: its model wears its glow and the light is lit",
            glow is not None and _look(knife) == (glow.get_name(), True), str(_look(knife)))
    p.check("...and the fire still burns, the knife still in the fist",
            len(_fires(p)) == 1 and knife.get_attach_parent_actor() == player)
    yield from _shot(p, player, bodies["Zombie"])

    # --- the hot blade on the bleed ---------------------------------------------------
    yield from _use(p, wc)
    p.check("the use key on the hot knife stops the bleeding",
            _bleeds(p, asc) == (0, 0), str(_bleeds(p, asc)))
    p.check("...and the knife stays hot", p.get(knife, HOT_VAR) and _look(knife)[1] is True,
            f"Hot {p.get(knife, HOT_VAR)}")
    health = p.component(player, HEALTH_CLASS_PATH)
    hp0, began = float(p.get(health, "Health")), p.time()
    yield 1.0
    p.check("...and the player's health no longer drains",
            float(p.get(health, "Health")) >= hp0 - 1e-3,
            f"{hp0:.3f} -> {float(p.get(health, 'Health')):.3f} in {p.time() - began:.2f} s")

    # --- it cools ----------------------------------------------------------------------
    p.set(knife, COOL_VAR, p.time() - 1.0)
    yield 0.2
    p.check("its time run out, the knife is cold again: no overlay, no light",
            not p.get(knife, HOT_VAR) and _look(knife) == (None, False),
            f"Hot {p.get(knife, HOT_VAR)} {_look(knife)}")

    # --- the blow ----------------------------------------------------------------------
    # The bodies stand behind the player, who turns to them: the fire is in
    # front, in the sweep's way.
    turn = unreal.Rotator(pitch=0.0, yaw=player.get_actor_rotation().yaw + 180.0, roll=0.0)
    player.set_actor_rotation(turn, False)
    player.get_controller().set_control_rotation(turn)
    yield 0.2
    wendigo, zombie = bodies["Wendigo"], bodies["Zombie"]
    w_health = p.component(wendigo, HEALTH_CLASS_PATH)
    z_health = p.component(zombie, HEALTH_CLASS_PATH)
    park = near + unreal.Vector(AWAY_CM, AWAY_CM, 200.0)
    zombie.set_actor_location(park, False, True)

    lost = yield from _slash(p, wc, player, wendigo, w_health)
    p.check(f"a cold knife takes {COMBAT.knife_damage:.0f} HP off the wendigo",
            abs(lost - COMBAT.knife_damage) < 1e-3, f"lost {lost}")
    yield from _press(p, wc)
    hot = bool(p.get(knife, HOT_VAR))
    lost = yield from _slash(p, wc, player, wendigo, w_health)
    want = COMBAT.knife_damage * HOT_BLOW_SCALE
    p.check(f"heated again, it takes {HOT_BLOW_SCALE:g} times that: {want:.0f} HP",
            hot and abs(lost - want) < 1e-3, f"Hot {hot}, lost {lost}")

    wendigo.set_actor_location(park, False, True)
    yield from _press(p, wc)
    hot = bool(p.get(knife, HOT_VAR))
    lost = yield from _slash(p, wc, player, zombie, z_health)
    p.check(f"a hot knife takes only {COMBAT.knife_damage:.0f} HP off the zombie, "
            "which does not fear fire",
            hot and abs(lost - COMBAT.knife_damage) < 1e-3, f"Hot {hot}, lost {lost}")

    # --- the axe heats too ----------------------------------------------------------------
    zombie.set_actor_location(park, False, True)
    yield from _equip(p, wc, AXE)
    yield from _press(p, wc)
    axe_glow = p.get(axe, HEAT_MATERIAL_VAR)
    p.check("the axe heats at the fire as the knife does, in its own glow",
            p.get(axe, HOT_VAR) and axe_glow is not None and axe_glow != glow
            and _look(axe) == (axe_glow.get_name(), True),
            f"Hot {p.get(axe, HOT_VAR)} {_look(axe)}")
    yield from _shot(p, player, bodies["Zombie"])
    lost = yield from _slash(p, wc, player, wendigo, w_health)
    p.check(f"...and hot, its blow takes {want:.0f} HP off the wendigo",
            abs(lost - want) < 1e-3, f"lost {lost}")
