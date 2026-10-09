"""Players can hurt players (task M15): a blade, a thrown blade and a round
take health off another player's character through the one damage path a
wanderer is hurt by, and the kill is counted for the player who struck it.

    server     removes the wanderers, and keeps client 2's character in front
               of client 1's; it restores the victim's health between steps
    server     brings client 1's knife to hand and asks its slash: the knife's
               damage off client 2, by client 1's hand
    server     asks client 1's throw of that knife, at client 2: a thrown
               blade's damage (the head's multiple if that is where it went)
    client 1   with its pistol in hand, down the sights, shoots client 2 in
               the body, then in the head: the head's round takes the head
               multiplier's times the body's, the wanderers' own table
    client 1   shoots again, the victim at 1 HP: client 2 is dead
    everyone   after each step the server says what health it has for client
               2, and both clients hold that same number; after the last, all
               three read one player kill for client 1, none for client 2, and
               no monster kill for either

The slash and the throw are asked on the server (its copy of the Server
events, which is where a client's ask arrives: probe_net_melee.py and
probe_net_throw.py prove the asks); the shots are client 1's own, through
FireForced and SightsForced. Friendly fire is on: there are no teams yet.
"""

SYSTEMS = ('net',)

import unreal

from combat import health_vars as HV
from combat.game_state import KILL_COUNT_VAR, PLAYER_DEAD_VAR
from combat.hit_zones import (
    HEAD_BONES_VAR, HEAD_MULT_VAR, HIT_BONE_VAR, LIMB_BONES_VAR, LIMB_MULT_VAR)
from combat import item_vars as IV
from combat.paths import (
    HEALTH_BP_PATH, WEAPON_COMP_BP_PATH, WEAPON_COMP_CLASS_PATH)
from combat.seat_tuning import SIGHTS_FORCED_VAR
from combat.shot_vars import ReloadForced
from combat.slot_tuning import MELEE_SLOT, PISTOL_SLOT
from combat.strike_vars import SERVER_SLASH, SERVER_THROW
from combat.throw_tuning import THROW_DAMAGE_VAR, THROW_SPEED_VAR
from combat.tuning import COMBAT
from combat.weapon_component.accuracy import AIM_SPREAD_VAR
from combat.weapon_component.knife import NEXT_KNIFE_VAR
from combat.weapon_component.throw_flight import THROWN_VAR
from combat.weapon_component.tick import FIRE_FORCED_VAR
from graphics_menu import umg_consts as C
from net.state_consts import PLAYER_KILL_COUNT_VAR
from probes.probe_hot_blade import _wanderers
from probes.probe_net_fire import (
    SIGHTS_SPREAD_DEG, _aim, _await, _bodies, _health, _nearest, _vec)
from probes.probe_net_player_state import SHOWN, _drawn
from probes.probe_throw_strike import _launch

RUNS_ON = ("server", "client")
WRITABLE = ([(WEAPON_COMP_BP_PATH, v) for v in
             (FIRE_FORCED_VAR, ReloadForced, SIGHTS_FORCED_VAR)]
            + [(HEALTH_BP_PATH, v) for v in (HV.Health, HV.PlayerRespawnWait)])

SHOOTER, VICTIM = "client 1", "client 2"
SLASH_CM, THROW_CM, SHOT_CM = 90.0, 300.0, 400.0
FULL, AMPLE, LAST = 100.0, 1000.0, 1.0
NO_RESPAWN_S = 600.0
STEPS = ("slash", "throw", "body", "head", "kill")
SHOTS = ("body", "head", "kill")
MAX_ROUNDS = 4


def _now(p):
    return unreal.GameplayStatics.get_time_seconds(p.world())


def _counts(p, state):
    return [int(p.get(state, PLAYER_KILL_COUNT_VAR)), int(p.get(state, KILL_COUNT_VAR))]


# ─── the server ──────────────────────────────────────────────────────────────

def probe_server(p):
    yield _await(lambda: p.posted(SHOOTER, "pos"))
    if not p.posted(SHOOTER, "pos"):
        p.check("client 1 said where it stands", False, "no post")
        return
    players, _npcs = _bodies(p)
    one = _nearest(players, p.posted(SHOOTER, "pos"))
    two = next((b for b in players if b != one), None)
    if two is None:
        p.check("the server has two players' characters", False, str(len(players)))
        return
    by, victim = one.get_controller(), two.get_controller()
    wc = p.component(one, WEAPON_COMP_CLASS_PATH)
    health = _health(p, two)
    hp = lambda: float(p.get(health, HV.Health))
    for ctrl in _wanderers(p):
        pawn = ctrl.get_controlled_pawn()
        if pawn:
            pawn.destroy_actor()
    p.set(health, HV.PlayerRespawnWait, NO_RESPAWN_S)
    gun = p.get(wc, "Held")
    apart = [SLASH_CM]

    def stand():
        if hp() > 0.0:
            two.set_actor_location(
                one.get_actor_location() + one.get_actor_forward_vector() * apart[0],
                False, True)
        return False

    def said(step):
        """Tell the clients what the server holds for the victim after ``step``."""
        p.post(f"hp {step}", hp())

    def blamed(cause):
        return p.get(health, HV.LastInstigator) == by and p.get(health, HV.LastCause) == cause

    # --- the knife's slash ---------------------------------------------------------
    p.ask_slot(wc, MELEE_SLOT)
    yield _await(lambda: stand() or (p.get(wc, "Held") not in (None, gun)), 5.0)
    knife = p.get(wc, "Held")
    yield _await(lambda: stand() or _now(p) > p.get(wc, NEXT_KNIFE_VAR) + 0.2, 5.0)
    was = hp()
    wc.call_method(SERVER_SLASH)
    yield _await(lambda: stand() or hp() < was, 5.0)
    p.check("client 1's slash takes the knife's damage off client 2's character, by "
            "client 1's hand and with its knife",
            abs((was - hp()) - COMBAT.knife_damage) < 1e-3 and blamed(knife),
            f"{was - hp():.0f} HP, by {p.get(health, HV.LastInstigator)}")
    said("slash")
    yield _await(lambda: stand() or all(p.posted(c, "saw slash") for c in (SHOOTER, VICTIM)))

    # --- the knife, thrown ---------------------------------------------------------
    p.set(health, HV.Health, FULL)
    apart[0] = THROW_CM
    yield _await(lambda: stand() or _now(p) > p.get(wc, NEXT_KNIFE_VAR) + 0.2, 5.0)
    yield 0.3
    stand()
    worth = float(p.get(knife, THROW_DAMAGE_VAR))
    start = _launch(one.get_actor_location(), one.get_actor_rotation().yaw)
    aim = (two.get_actor_location() + unreal.Vector(0.0, 0.0, 20.0) - start).normal()
    was = hp()
    wc.call_method(SERVER_THROW, (start, aim * float(p.get(knife, THROW_SPEED_VAR))))
    yield _await(lambda: stand() or hp() < was, 8.0)
    took = was - hp()
    p.check("client 1's thrown knife takes a thrown blade's damage off client 2 (the "
            "head's multiple of it in the head), by client 1's hand",
            any(abs(took - worth * m) < 1e-3 for m in (1.0, COMBAT.head_multiplier))
            and blamed(knife), f"{took:.1f} HP of {worth:g}, thrown {p.get(wc, THROWN_VAR)}")
    said("throw")
    yield _await(lambda: stand() or all(p.posted(c, "saw throw") for c in (SHOOTER, VICTIM)))

    # --- the pistol to hand (one round a shot, where the shotgun's pellets ----------
    # land on several zones at once), and three shots
    apart[0] = SHOT_CM
    p.ask_slot(wc, PISTOL_SLOT)
    yield _await(lambda: stand() or p.get(wc, "Held") not in (None, gun, knife), 5.0)
    pistol = p.get(wc, "Held")
    if pistol is None:
        p.check("client 1's pistol is in its hand on the server", False, "empty hands")
        return
    round_hp = float(p.get(pistol, IV.Damage))
    head, limb = float(p.get(health, HEAD_MULT_VAR)), float(p.get(health, LIMB_MULT_VAR))
    zones = {str(b): head for b in p.get(health, HEAD_BONES_VAR)}
    zones.update({str(b): limb for b in p.get(health, LIMB_BONES_VAR)
                  if str(b) not in zones})
    for step, before in zip(SHOTS, (AMPLE, AMPLE, LAST)):
        p.set(health, HV.Health, before)
        yield _await(lambda: stand(), 0.5)
        p.post(f"shoot {step}", pistol.get_class().get_name())
        yield _await(lambda: stand() or p.posted(SHOOTER, f"shot {step}"), 60.0)
        yield _await(lambda: stand(), 0.4)
        drop, bone = before - hp(), str(p.get(wc, HIT_BONE_VAR))
        worth = zones.get(bone, 1.0)
        if step == "body":
            p.check("client 1's round in client 2's body takes the round's damage times "
                    "the zone it struck, by client 1's hand and with its gun",
                    abs(drop - round_hp * worth) < 1e-3 and worth < head and blamed(pistol),
                    f"{drop:.2f} HP of {round_hp:g}, bone {bone} (x{worth:g})")
        elif step == "head":
            p.check(f"...and one in the head {head:g} times the round's: a player's hit "
                    "boxes are a wanderer's (the target's own table)",
                    worth == head and abs(head - COMBAT.head_multiplier) < 1e-6
                    and abs(drop - round_hp * head) < 1e-3,
                    f"{drop:.2f} HP of {round_hp:g}, bone {bone} (x{worth:g})")
        said(step)
        if step != "kill":
            yield _await(lambda: stand() or all(
                p.posted(c, f"saw {step}") for c in (SHOOTER, VICTIM)))

    # --- the kill -----------------------------------------------------------------
    yield _await(lambda: bool(p.get(health, HV.Dead)), 5.0)
    p.check("client 2's character is dead on the server, at 0 HP",
            bool(p.get(health, HV.Dead)) and hp() == 0.0, f"Health {hp():.1f}")
    yield _await(lambda: _counts(p, by.player_state)[0] > 0, 5.0)
    p.check("the kill is client 1's: one player kill on its PlayerState, and no "
            "monster kill", _counts(p, by.player_state) == [1, 0],
            f"[player kills, monster kills] = {_counts(p, by.player_state)}")
    p.check("...and none of either for client 2, who died",
            _counts(p, victim.player_state) == [0, 0], str(_counts(p, victim.player_state)))
    p.post("counts", {"by": by.player_state.get_editor_property("player_id"),
                      "victim": victim.player_state.get_editor_property("player_id")})
    yield _await(lambda: all(p.posted(c, "counted") for c in (SHOOTER, VICTIM)), 20.0)


# ─── the clients ─────────────────────────────────────────────────────────────

def _shoot(p, wc, point, done):
    """Client 1's rounds at ``point()``, down the sights, until ``done()``."""
    held = p.get(wc, "Held")
    for _ in range(MAX_ROUNDS):
        if done():
            break
        if int(p.get(held, "Loaded")) == 0:
            p.set(wc, ReloadForced, True)
            yield _await(lambda: int(p.get(held, "Loaded")) > 0, 5.0)
            p.set(wc, ReloadForced, False)
        yield from _aim(p, wc, point)
        yield _await(lambda: _now(p) > p.get(held, "NextFireTime") + 0.05, 5.0)
        was = int(p.get(held, "Loaded"))
        p.set(wc, FIRE_FORCED_VAR, True)
        yield _await(lambda: int(p.get(held, "Loaded")) < was, 3.0)
        p.set(wc, FIRE_FORCED_VAR, False)
        yield _await(done, 2.0)


def _states(p):
    return {s.get_editor_property("player_id"): s for s in p.game_state().get_editor_property("player_array")}


def probe_client(p):
    mine = p.pawn()
    wc = p.component(mine, WEAPON_COMP_CLASS_PATH)
    yield _await(lambda: p.get(wc, "Held") is not None)
    gun = p.get(wc, "Held")
    yield _await(lambda: len(_bodies(p)[0]) == 2)
    other = next((b for b in _bodies(p)[0] if b != mine), None)
    if gun is None or other is None:
        p.check(f"{p.where} holds its gun and sees the other player", False,
                f"{gun}, {other}")
        return
    shooting = p.where == SHOOTER
    body = other if shooting else mine
    health = _health(p, body)
    hp = lambda: float(p.get(health, HV.Health))
    if shooting:
        p.post("pos", _vec(mine.get_actor_location()))

    for step in STEPS:
        if shooting and step in SHOTS:
            yield _await(lambda: p.posted("server", f"shoot {step}") is not None, 90.0)
            want_held = p.posted("server", f"shoot {step}")
            yield _await(lambda: p.get(wc, "Held") is not None
                         and p.get(wc, "Held").get_class().get_name() == want_held, 5.0)
            p.set(wc, SIGHTS_FORCED_VAR, True)
            yield _await(lambda: p.get(wc, "SightAiming")
                         and float(p.get(wc, AIM_SPREAD_VAR)) < SIGHTS_SPREAD_DEG, 5.0)
            yield 0.5
            was = hp()
            point = ((lambda: other.mesh.get_socket_location("head")) if step == "head"
                     else other.get_actor_location)
            yield from _shoot(p, wc, point, lambda: hp() < was)
            p.post(f"shot {step}")
        yield _await(lambda: p.posted("server", f"hp {step}") is not None, 120.0)
        want = p.posted("server", f"hp {step}")
        if want is None:
            p.check(f"the server said client 2's health after the {step}", False, "no post")
            return
        yield _await(lambda: abs(hp() - want) < 1e-3, 5.0)
        whose = "its copy of client 2" if shooting else "its own character"
        p.check(f"after the {step}, {p.where} holds the server's health for {whose}: "
                f"{want:.1f}", abs(hp() - want) < 1e-3, f"{hp():.1f}")
        p.post(f"saw {step}")
    p.set(wc, SIGHTS_FORCED_VAR, False)

    yield _await(lambda: bool(p.get(health, HV.Dead)), 5.0)
    p.check(f"{p.where} sees client 2's character dead", bool(p.get(health, HV.Dead)))
    yield _await(lambda: p.posted("server", "counts") is not None, 30.0)
    ids = p.posted("server", "counts")
    if not ids:
        p.check("the server counted the kill", False, "no post")
        return
    yield _await(lambda: ids["by"] in _states(p)
                 and _counts(p, _states(p)[ids["by"]])[0] > 0, 5.0)
    states = _states(p)
    got = {k: _counts(p, states[v]) if v in states else None for k, v in ids.items()}
    p.check(f"{p.where} reads the server's counts: one player kill for client 1, none "
            "for client 2, and no monster kill for either",
            got == {"by": [1, 0], "victim": [0, 0]}, str(got))
    own = _counts(p, p.player_state())
    p.check(f"...and its own PlayerState is the {'killer' if shooting else 'victim'}'s",
            own == ([1, 0] if shooting else [0, 0]), str(own))
    if not shooting:
        yield _await(lambda: bool(p.get(p.player_state(), PLAYER_DEAD_VAR)), 15.0)
        yield from _drawn(p.hud())
        death = p.get(p.hud(), "UiDeath")
        line = str(death.get_editor_property(C.DEATH_PLAYER_SCORE).get_text())
        p.check("client 2's death menu is up, with its player kills beside its monster "
                "kills", death.get_visibility() == SHOWN
                and line == f"{C.DEATH_PLAYER_SCORE_PREFIX}0"
                and str(death.get_editor_property(C.DEATH_SCORE).get_text())
                == f"{C.DEATH_SCORE_PREFIX}0", f"'{line}'")
    p.post("counted")
