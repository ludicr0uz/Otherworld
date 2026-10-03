"""A wendigo's hit can make the player bleed (survival/on_hit.py), and the
bleed drains health at 50 HP over 3 minutes (combat/debuff_drain.py).

The verifiers read the graphs; this watches one wendigo do it. Every other
wanderer is removed, the wendigo is stood in front of the player and left to
swing, and the player's health is topped up after each blow so they live:

  - with the roll made to fail (OnHitChanceBonus -1) three blows leave no bleed;
  - with it made to land (+1) the next blow does: one GE_Bleeding, 3 minutes
    of it, the Debuff.Bleeding tag once;
  - another blow restarts the 3 minutes and does not stack a second bleed;
  - with the wendigo gone, health falls at 50 / 180 HP a second and the
    effect's time runs down.

The chance itself (33%) is a pin literal the verifier reads
(npc/verify_on_hit.py): one roll in three proves nothing in a run this short,
which is what OnHitChanceBonus is for. The full 3 minutes are not waited out;
the effect's remaining time is read instead.
"""

import math

import unreal

from combat.paths import HEALTH_BP_PATH, HEALTH_CLASS_PATH
from combat.tuning import BLEED_DURATION_S, BLEED_HP_PER_S, BLEED_TOTAL_HP, BLEEDING_TAG
from forest_generator.npc_placement import NAV_REACHABLE_EXTENT_CM
from npc.paths import NPC_DIR
from survival.on_hit import ON_HIT_BONUS_VAR
from survival.paths import BLEEDING_GE_CLASS_PATH
from combat import health_vars as HV

WENDIGO_AI = f"{NPC_DIR}/BP_ForestWandererAI_Wendigo"
WRITABLE = [(HEALTH_BP_PATH, HV.Health), (WENDIGO_AI, ON_HIT_BONUS_VAR)]

START_CM = 150.0      # inside its reach
FULL = 100.0
MISSES = 3            # blows watched with the roll failing
SWING_WAIT_S = 12.0   # game seconds allowed for one blow (the first follows a roar)
DRAIN_S = 3.0


def _wanderers(p):
    ctrls = unreal.GameplayStatics.get_all_actors_of_class(p.world(), unreal.AIController)
    return [c for c in ctrls if c.get_class().get_name().startswith("BP_ForestWandererAI")
            and c.get_controlled_pawn() is not None]


def _on_navmesh(p, point):
    return unreal.NavigationSystemV1.project_point_to_navigation(
        p.world(), point, None, None, unreal.Vector(*NAV_REACHABLE_EXTENT_CM))


def _bleeds(p, asc):
    """(stacks of the tag, active GE_Bleedings, seconds left of the first)."""
    lib, tag = unreal.AbilitySystemLibrary, p.tag(BLEEDING_TAG)
    # Every active effect, then the bleeds by name: a query by tag does not
    # find them, because the tag is granted on the spec, not by the asset.
    handles = [h for h in asc.get_active_effects(unreal.GameplayEffectQuery())
               if "GE_Bleeding" in str(lib.get_active_gameplay_effect_debug_string(h))]
    left = (lib.get_active_gameplay_effect_remaining_duration(p.world(), handles[0])
            if handles else 0.0)
    return (asc.get_gameplay_tag_count(tag),
            asc.get_gameplay_effect_count(p.load_class(BLEEDING_GE_CLASS_PATH), None, True),
            left)


def _blow(p, ctrl, health):
    """Wait for the wendigo's next swing; the player's health is then topped
    up. Returns whether one came."""
    armed, since = float(p.get(ctrl, "NextAttackTime")), p.time()
    while float(p.get(ctrl, "NextAttackTime")) == armed:
        if p.time() - since > SWING_WAIT_S:
            return False
        yield 0.05
    hurt = float(p.get(health, "Health")) < FULL
    p.set(health, "Health", FULL)
    return hurt


def probe(p):
    yield lambda: any(c.get_class().get_name().startswith("BP_ForestWandererAI_Wendigo")
                      for c in _wanderers(p))
    yield 0.5
    player = p.pawn()
    health = p.component(player, HEALTH_CLASS_PATH)
    asc = unreal.AbilitySystemLibrary.get_ability_system_component(player)
    ctrl = [c for c in _wanderers(p)
            if c.get_class().get_name().startswith("BP_ForestWandererAI_Wendigo")][0]
    npc = ctrl.get_controlled_pawn()
    for other in _wanderers(p):
        if other != ctrl:
            other.get_controlled_pawn().destroy_actor()

    # A headless -game run was found with no navmesh tiles at all, and none
    # being built; RebuildNavigation builds them in a few seconds.
    if _on_navmesh(p, player.get_actor_location()) is None:
        unreal.SystemLibrary.execute_console_command(
            p.world(), "RebuildNavigation", p.controller())
        p.note("no navmesh under the player: sent RebuildNavigation")
    yield lambda: _on_navmesh(p, player.get_actor_location()) is not None

    p.check("the player starts with no bleed, and the wendigo's chance as built",
            _bleeds(p, asc)[:2] == (0, 0) and float(p.get(ctrl, ON_HIT_BONUS_VAR)) == 0.0,
            f"{_bleeds(p, asc)}, bonus {p.get(ctrl, ON_HIT_BONUS_VAR)}")

    # --- the roll fails: blows, and no bleed -----------------------------------
    p.set(ctrl, ON_HIT_BONUS_VAR, -1.0)
    p.set(health, "Health", FULL)
    home = player.get_actor_location()
    yaw = player.get_actor_rotation().yaw
    ahead = unreal.Vector(math.cos(math.radians(yaw)), math.sin(math.radians(yaw)), 0.0)
    ground = _on_navmesh(p, home + ahead * START_CM)
    if ground is None:
        p.check("there is ground in front of the player to stand a wendigo on", False)
        return
    npc.set_actor_location_and_rotation(
        ground + unreal.Vector(0.0, 0.0, 95.0),
        unreal.Rotator(pitch=0.0, yaw=yaw + 180.0, roll=0.0), False, True)
    landed, seen = 0, []
    for _ in range(MISSES):
        hurt = yield from _blow(p, ctrl, health)
        landed += bool(hurt)
        seen.append(_bleeds(p, asc)[:2])
    p.check(f"with the roll failing, {MISSES} blows land and none leaves a bleed",
            landed == MISSES and all(s == (0, 0) for s in seen), f"{landed} landed, {seen}")
    if landed != MISSES:
        return

    # --- the roll lands: the blow leaves a bleed -------------------------------
    p.set(ctrl, ON_HIT_BONUS_VAR, 1.0)
    hurt = yield from _blow(p, ctrl, health)
    tags, effects, left = _bleeds(p, asc)
    p.check(f"with the roll landing, the next blow leaves one bleed: {BLEEDING_TAG} "
            f"once, GE_Bleeding once, {BLEED_DURATION_S:.0f} s of it",
            bool(hurt) and (tags, effects) == (1, 1) and abs(left - BLEED_DURATION_S) < 1.0,
            f"tag x{tags}, effect x{effects}, {left:.1f} s left")
    if (tags, effects) != (1, 1):
        return
    yield 0.6
    before = _bleeds(p, asc)[2]
    hurt = yield from _blow(p, ctrl, health)
    tags, effects, left = _bleeds(p, asc)
    p.check("a second blow restarts the bleed and does not stack another",
            bool(hurt) and (tags, effects) == (1, 1) and left > before
            and abs(left - BLEED_DURATION_S) < 1.0,
            f"tag x{tags}, effect x{effects}, {before:.1f} -> {left:.1f} s left")

    # --- what it costs -------------------------------------------------------------
    npc.destroy_actor()
    yield 0.2
    p.set(health, "Health", FULL)
    began, left0 = p.time(), _bleeds(p, asc)[2]
    yield DRAIN_S
    took, lost = p.time() - began, FULL - float(p.get(health, "Health"))
    want = BLEED_HP_PER_S * took
    p.check(f"bleeding drains {BLEED_HP_PER_S:.4f} HP a second: "
            f"{BLEED_TOTAL_HP:.0f} HP over {BLEED_DURATION_S:.0f} s",
            abs(lost - want) <= 0.15 * want,
            f"lost {lost:.3f} HP in {took:.2f} s, expected {want:.3f}")
    left = _bleeds(p, asc)[2]
    p.check("...and its time runs down as it does",
            abs((left0 - left) - took) < 0.5 and _bleeds(p, asc)[:2] == (1, 1),
            f"{left0:.1f} -> {left:.1f} s left after {took:.2f} s")
