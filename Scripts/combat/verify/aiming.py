"""verify.aiming -- Aiming down the sights, sensitivity under zoom, what aiming costs in
mobility, and sprint dropping the ready pose.
"""

from combat.carry_tuning import LOWERED_VAR, POSE_LOWERED_VAR
from combat.tuning import COMBAT
from combat.weapon_specs import _weapon_specs
from combat.verify.fixtures import titles, w, wc_cdo, wg
from combat.verify.throw import is_throw_play
from combat.verify.knife import is_melee_play
from combat.verify.common import (
    BEL, PIN, by_pins, cdo, check, in_pins, load, num_pin, out_pins, titled,
)


# ─── Aiming down the sights ──────────────────────────────────────────────────

def check_aiming_down_sights():
    # Either aim key narrows the camera (the shoulder by COMBAT.shoulder_zoom, the
    # sights by the weapon's own AdsZoom; verify/sights.py). What can go wrong
    # quietly: a zoom that is never applied (the FOV write missing), a zoom that is
    # applied and never undone (no path back to BaseFOV), and a BaseFOV that is a
    # literal rather than the camera's own -- all three look fine in the graph.

    for sp in _weapon_specs():
        want = sp.get("ads_zoom", COMBAT.ads_zoom_irons)
        got = cdo(load(sp["path"])).get_editor_property("AdsZoom")
        check(f"{sp['display']}: AdsZoom is {want}x",
              isinstance(got, float) and abs(got - want) < 1e-6, repr(got))
    check("only the sniper carries a scope's worth of zoom",
          {sp["display"] for sp in _weapon_specs()
           if sp.get("ads_zoom", COMBAT.ads_zoom_irons) == COMBAT.ads_zoom_scope} == {"Sniper"},
          str(sorted(sp.get("ads_zoom", COMBAT.ads_zoom_irons)
                     for sp in _weapon_specs())))

    # Scoped is what the HUD branches on to black the screen out and draw the
    # sniper reticle, and it is deliberately a separate fact from AdsZoom -- so
    # both the flag and the agreement between the two are worth checking.
    scoped = set()
    for sp in _weapon_specs():
        want = bool(sp.get("scoped", False))
        got = cdo(load(sp["path"])).get_editor_property("Scoped")
        check(f"{sp['display']}: Scoped is {want}", got is want, repr(got))
        if got:
            scoped.add(sp["display"])
    check("the sniper is the only weapon with glass on it", scoped == {"Sniper"},
          str(sorted(scoped)))
    # The HUD fades the scope over (BaseFOV/CurrentFOV - shoulder) /
    # (AdsZoom - shoulder), so a scoped weapon that does not zoom past the
    # shoulder aim would divide by zero every frame it is aimed. build_weapon
    # refuses to build one; this is the same rule read off the assets that shipped.
    flat = {sp["display"] for sp in _weapon_specs()
            if sp.get("scoped")
            and sp.get("ads_zoom", COMBAT.ads_zoom_irons) <= COMBAT.shoulder_zoom}
    check("...and it zooms past the shoulder aim, so the scope's fade has "
          "something to divide by",
          not flat, str(sorted(flat)))

    fov_writes = [x for x in wg if "SetFieldOfView" in
                  str(BEL.get_node_title(x)).replace(" ", "")]
    check("one write of the camera's field of view, so the two directions cannot "
          "drift", len(fov_writes) == 1, str(len(fov_writes)))
    # Two TargetFOV writes -- the zoomed arm and the unzoomed one -- is what makes
    # letting go of the button a path back rather than a second mechanism.
    target_writes = [x for x in wg
                     if str(BEL.get_node_title(x)).replace("\n", " ")
                     == "Set TargetFOV"]
    check("...fed from two writes of TargetFOV: aiming, and not aiming",
          len(target_writes) == 2, str(len(target_writes)))
    check("the zoom is interpolated, not snapped",
          bool(titled(wg, "FInterp To")) or bool(titled(wg, "FInterpTo")),
          "FInterpTo")
    base_reads = [x for x in wg if "FieldOfView" in out_pins(x)]
    check("BaseFOV is cached off the camera, not written down as a literal",
          bool(base_reads), str(len(base_reads)))
    check("aiming is refused while sprinting, which cannot fire anyway",
          "Get Sprinting" in
          {str(BEL.get_node_title(x)).replace("\n", " ") for x in wg})


# ─── Mouse sensitivity, and what the zoom does to it ─────────────────────────

def check_mouse_sensitivity():
    # Three ways this goes wrong without looking wrong. The pitch scale is cached
    # rather than written down because the engine ships it NEGATIVE, so a literal
    # would invert the look half the time; the slowdown is driven off CurrentFOV
    # rather than off the Aiming flag, so it eases in with the zoom and is
    # automatically stronger on the scope; and the default sensitivity has to be
    # exactly 1.0 or a player who never opens the settings screen gets a mouse
    # that does not feel like the controller's own.
    check("the weapon component carries a mouse sensitivity",
          isinstance(wc_cdo.get_editor_property("MouseSensitivity"), float))
    check("...defaulting to 1.0, i.e. exactly the controller's own feel",
          abs(wc_cdo.get_editor_property("MouseSensitivity")
              - COMBAT.mouse_sensitivity_default) < 1e-6
          and abs(COMBAT.mouse_sensitivity_default - 1.0) < 1e-6,
          repr(wc_cdo.get_editor_property("MouseSensitivity")))
    check("...within a range that cannot reach zero, which would kill the mouse",
          0.0 < COMBAT.mouse_sensitivity_min < COMBAT.mouse_sensitivity_default
          < COMBAT.mouse_sensitivity_max,
          f"{COMBAT.mouse_sensitivity_min}..{COMBAT.mouse_sensitivity_max}")


# ─── What aiming costs in mobility ───────────────────────────────────────────

def check_aiming_mobility():
    # Full ADS is half speed. The slowdown is the movement component's (C++,
    # combat/player_move.py): the graph tells it the player is aiming, as a
    # flag each move carries, and it eases the walk towards the scale at the
    # zoom's own speed. verify/movement.py checks the flag and the numbers;
    # probes/probe_net_move_states.py the walk itself, on both machines.

    check(f"aiming costs {(1 - COMBAT.ads_move_speed_scale) * 100:.0f}% of the "
          f"walking speed, which is the ask",
          abs(COMBAT.ads_move_speed_scale - 0.5) < 1e-9,
          f"x{COMBAT.ads_move_speed_scale}")

    def feeds(pin, limit=250):
        """Every node feeding this pin through DATA links only.

        Same shape, and for the same reason, as the traversal the Automatic check
        uses further down: following the exec pin as well would reach every pure
        node in the graph and make each of these checks pass vacuously.
        """
        seen, stack = set(), [pin]
        while stack and len(seen) < limit:
            for q in PIN.list_connected_pins(stack.pop()):
                node = PIN.get_owning_node(q)
                if node in seen:
                    continue
                seen.add(node)
                stack.extend(x for x in BEL.list_input_pins(node)
                             if str(PIN.get_pin_name(x)) != "execute")
        return seen

    speed_writes = [n for n in wg if "MaxWalkSpeed" in in_pins(n)]
    check("no graph writes MaxWalkSpeed: a speed written here exists on one "
          "machine, and the server would pull the client back",
          not speed_writes, str(len(speed_writes)))
    check("...and BaseSpeed is still written exactly once, at BeginPlay, off "
          "the character's own default",
          len([n for n in wg if "BaseSpeed" in in_pins(n)]) == 1,
          str(len([n for n in wg if "BaseSpeed" in in_pins(n)])))

    # The headless -game run takes no input, so the gate above never opens by
    # itself and the positive case has to be forced with a temporary probe. This is
    # what makes sure the probe left again: Aiming is driven by the aim bind and by
    # nothing else -- a forcing function wired in front of the key poll (a clock, a
    # literal true) would still zoom, still slow the player down, and still pass
    # every structural check above.
    aiming_writes = [n for n in wg if "Aiming" in in_pins(n)]
    check("Aiming is written exactly once", len(aiming_writes) == 1,
          str(len(aiming_writes)))
    if aiming_writes:
        src = feeds(BEL.find_input_pin(aiming_writes[0], "Aiming"))
        src_titles = {str(BEL.get_node_title(n)).replace("\n", " ") for n in src}
        check("...off the two aim binds, and off nothing that stands in for "
              "them -- no clock and no literal left over from forcing the state "
              "at runtime",
              any("Get KeyAim" in t for t in src_titles)
              and any("Get KeySights" in t for t in src_titles)
              and not any("Time Seconds" in t or t.strip() in ("Sin", "Sin (Radians)")
                          for t in src_titles),
              str(sorted(src_titles)))
    check("and no probe is left printing out of the weapon component's Tick",
          not [n for n in wg
               if "printstring" in
               str(BEL.get_node_title(n)).replace(" ", "").lower()],
          str([str(BEL.get_node_title(n)) for n in wg
               if "printstring" in
               str(BEL.get_node_title(n)).replace(" ", "").lower()]))


# ─── Sprinting drops the ready pose ──────────────────────────────────────────

def check_sprint_drops_ready_pose():
    # The complaint this answers: running with the barrel levelled at the horizon.
    # There is no new animation -- the fix is to stop playing the ready pose, and
    # let ABP_Unarmed's own locomotion state machine through the layered blend.

    # Since the carry (verify/carry.py) the pose follows Lowered, which
    # sprinting is one way into: Lowered and PoseLowered are the edge's pair.
    check("PoseLowered exists to make the change edge-triggered",
          w.get_editor_property(POSE_LOWERED_VAR) is False,
          str(w.get_editor_property(POSE_LOWERED_VAR)))
    check("...and it matches Lowered and Sprinting at start, so frame one "
          "re-equips nothing",
          w.get_editor_property(POSE_LOWERED_VAR)
          == w.get_editor_property(LOWERED_VAR)
          == w.get_editor_property("Sprinting"))
    check("the pose's state is remembered exactly once",
          titles.count(f"Set {POSE_LOWERED_VAR}") == 1,
          f"{titles.count(f'Set {POSE_LOWERED_VAR}')} writes")
    check("...and re-equipping happens only on the frames the two disagree",
          any("!=" in t or "NotEqual" in t.replace(" ", "") for t in titles),
          str(sorted({t for t in titles if "=" in t})))
    # The pose itself: the branch that decides whether to play or stop the slot
    # has a NOT Lowered in its condition, and Lowered is made of Sprinting.
    # ...the ready pose's: not a melee clip's, nor the throw's (Fx_ThrowClip).
    plays = [n for n in by_pins(wg, "Asset", "SlotNodeName", "InPlayRate")
             if not is_melee_play(n) and not is_throw_play(n)]
    if plays:
        node, reached = plays[0], False
        ins = BEL.find_input_pin(node, "execute")
        gate = [PIN.get_owning_node(q) for q in PIN.list_connected_pins(ins)]
        if gate:
            cond = [PIN.get_owning_node(q)
                    for q in PIN.list_connected_pins(
                        BEL.find_input_pin(gate[0], "Condition"))]
            # Walk the two inputs of the AND looking for a Lowered read.
            frontier = list(cond)
            for _ in range(6):
                nxt = []
                for n in frontier:
                    if LOWERED_VAR in out_pins(n):
                        reached = True
                    for q in BEL.list_input_pins(n):
                        nxt += [PIN.get_owning_node(r)
                                for r in PIN.list_connected_pins(q)]
                frontier = nxt
        check("the ready pose is not played while sprinting", reached,
              "Lowered read found behind the pose branch's condition")
    lowered = [n for n, t in zip(wg, titles) if t == f"Set {LOWERED_VAR}"]
    check("...and Lowered is made of Sprinting, armed or not",
          bool(lowered) and all(
              any("Sprinting" in out_pins(PIN.get_owning_node(q)) or any(
                  "Sprinting" in out_pins(PIN.get_owning_node(r))
                  for r in PIN.list_connected_pins(
                      BEL.find_input_pin(PIN.get_owning_node(q), "A")))
                  for q in PIN.list_connected_pins(
                      BEL.find_input_pin(n, LOWERED_VAR)))
              for n in lowered), f"{len(lowered)} writes")


def run():
    check_aiming_down_sights()
    check_mouse_sensitivity()
    check_aiming_mobility()
    check_sprint_drops_ready_pose()
