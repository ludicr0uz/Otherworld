"""verify.aiming -- Aiming down the sights, sensitivity under zoom, what aiming costs in
mobility, and sprint dropping the ready pose.
"""

from combat.carry_tuning import LOWERED_VAR, POSE_LOWERED_VAR
from combat.tuning import COMBAT
from combat.weapon_specs import _weapon_specs
from combat.verify.fixtures import titles, w, wc_cdo, wg
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
    # Full ADS is half speed, and it is a second MaxWalkSpeed write layered on top
    # of the sprint block's unconditional one. Four ways that goes wrong while the
    # graph still looks right: the factor is applied to the LIVE walk speed rather
    # than to BaseSpeed, which compounds to a standstill in about a second; nothing
    # ever restores the speed, because the author added an "undo" path that turns
    # out to be dead; the slowdown is driven off the Aiming flag, so it snaps on a
    # frame before the camera moves; and it is driven off the raw CurrentFOV/BaseFOV
    # ratio the sensitivity uses, which would make the sniper slower on its legs
    # than the pistol and never reach exactly half on anything.

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
    check("MaxWalkSpeed is written exactly twice: the sprint block's "
          "unconditional write, and the ADS slowdown layered on top of it",
          len(speed_writes) == 2, str(len(speed_writes)))
    # The sprint write reaches the movement component through a cast to Character
    # (it wants the CastFailed pin as a continuation); the ADS one takes the
    # GetComponentByClass shortcut, which is what tells the two apart from here.
    by_class = [n for n in speed_writes
                if any("getcomponentbyclass" in
                       str(BEL.get_node_title(PIN.get_owning_node(q)))
                       .replace(" ", "").lower()
                       for q in PIN.list_connected_pins(
                           BEL.find_input_pin(n, "self")))]
    check("...the second of them off GetComponentByClass, which reshapes its "
          "return pin to the chosen class and so needs no cast",
          len(by_class) == 1, str(len(by_class)))

    if by_class:
        ads_speed = by_class[0]
        up = feeds(BEL.find_input_pin(ads_speed, "MaxWalkSpeed"))
        up_titles = {str(BEL.get_node_title(n)).replace("\n", " ") for n in up}
        check("THE COMPOUNDING TRAP: the slowed speed is computed from BaseSpeed, "
              "never from the MaxWalkSpeed that is already set -- this write runs "
              "every frame, so a factor on the live value would walk the player to "
              "a standstill in about a second",
              any("BaseSpeed" in out_pins(n) for n in up)
              and not any("MaxWalkSpeed" in out_pins(n) for n in up),
              str(sorted(up_titles)))
        check("...and BaseSpeed is still written exactly once, at BeginPlay, off "
              "the character's own default",
              len([n for n in wg if "BaseSpeed" in in_pins(n)]) == 1,
              str(len([n for n in wg if "BaseSpeed" in in_pins(n)])))
        check("the slowdown is driven off how far the zoom has actually travelled, "
              "not off the Aiming flag -- the flag would snap it on a frame before "
              "the camera moved",
              "Set CurrentFOV" in up_titles
              and not any("Aiming" in out_pins(n) for n in up),
              str(sorted(t for t in up_titles if "FOV" in t or "Aiming" in t)))
        check("...normalised by AimZoom, the zoom being aimed at, so full zoom "
              "is the same half speed on a 4x scope, 1.5x irons and the "
              "shoulder -- and not by Held.AdsZoom, which would leave the "
              "sniper's 1.5x shoulder aim at a sixth of the slowdown",
              any("AimZoom" in out_pins(n) for n in up)
              and not any("AdsZoom" in out_pins(n) for n in up),
              str(sorted(up_titles)))
        # An FInterpTo can overshoot its target on a long frame, and an unclamped
        # progress past 1 is a walk speed below the number anybody chose.
        # `num_pin(n, "Min") or X` would be the wrong test and quietly the wrong
        # answer: a Min that really is 0.0 is falsy, so the fallback wins and the
        # clamp that exists reads as missing.
        def holds(node, name, want):
            got = num_pin(node, name)
            return got is not None and abs(got - want) < 1e-9

        clamps = [n for n in up if {"Value", "Min", "Max"} <= in_pins(n)]
        check("...clamped to 0..1, because the interpolation can overshoot",
              any(holds(n, "Min", 0.0) and holds(n, "Max", 1.0) for n in clamps),
              str(len(clamps)))
        lerps = [n for n in up
                 if holds(n, "B", COMBAT.ads_move_speed_scale)
                 and holds(n, "A", 1.0)]
        check(f"...and eased Lerp(1, {COMBAT.ads_move_speed_scale:g}, progress), "
              f"so it arrives with the zoom rather than with the key",
              len(lerps) == 1, str(len(lerps)))

        # THE REASON THE GATE IS THERE. Sprint writes MaxWalkSpeed unconditionally
        # every frame, earlier in the same Tick, which is what makes releasing the
        # aim key need no code at all -- and also what would make the two writes
        # fight over the frames the player is sprinting, if this one were not shut
        # off on exactly the condition the zoom is.
        driving = [PIN.get_owning_node(q) for q in PIN.list_connected_pins(
            BEL.find_input_pin(ads_speed, "execute"))]
        gates = [n for n in driving if n.get_class().get_name() == "K2Node_IfThenElse"]
        check("the ADS write sits behind a Branch, so the frames it does not run "
              "are the frames sprint's unconditional write stands -- that is the "
              "whole of \"letting go restores the speed\"",
              len(gates) == 1, str([n.get_class().get_name() for n in driving]))
        if gates:
            cond = feeds(BEL.find_input_pin(gates[0], "Condition"))
            cond_titles = {str(BEL.get_node_title(n)).replace("\n", " ")
                           for n in cond}
            check("...gated on NOT Sprinting, the same pin the zoom is, so the two "
                  "MaxWalkSpeed writes can never disagree about a frame",
                  any("Sprinting" in out_pins(n) for n in cond)
                  and any("NOT" in t.upper() for t in cond_titles),
                  str(sorted(cond_titles)))
            check("...and on a valid Held, the same as Aiming is, so empty hands "
                  "always walk at sprint's speed",
                  any("isvalid" in t.replace(" ", "").lower() for t in cond_titles),
                  str(sorted(cond_titles)))

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

    # The numbers the player actually feels, spelled out so that a change to either
    # the scale or a weapon's zoom has to be argued for rather than noticed later.
    # At full zoom CurrentFOV is BaseFOV/AimZoom, so progress is exactly 1 whatever
    # the zoom -- which is the point of dividing by (AimZoom - 1).
    def _eased(zoom, travelled):
        """The walk-speed factor once the camera is `travelled` of the way in."""
        now = 1.0 / (1.0 + travelled * (zoom - 1.0))        # CurrentFOV / BaseFOV
        progress = min(max((1.0 / now - 1.0) / (zoom - 1.0), 0.0), 1.0)
        return 1.0 + (COMBAT.ads_move_speed_scale - 1.0) * progress

    # Every zoom the player can be at: each weapon down its sights, and the
    # shoulder aim, which is the same on all of them.
    zooms = {**{f"{sp['display']} sights": sp.get("ads_zoom", COMBAT.ads_zoom_irons)
                for sp in _weapon_specs()},
             "shoulder": COMBAT.shoulder_zoom}
    full_ads = {k: _eased(z, 1.0) for k, z in zooms.items()}
    check(f"every weapon, down its sights or off the shoulder, lands on exactly "
          f"{COMBAT.ads_move_speed_scale:g}x speed at full zoom",
          all(abs(v - COMBAT.ads_move_speed_scale) < 1e-9
              for v in full_ads.values()),
          str(sorted(full_ads.items())))
    check("...and on full speed with the button up, so nothing is left behind",
          all(abs(_eased(z, 0.0) - 1.0) < 1e-9 for z in zooms.values()))
    halfway = {k: _eased(z, 0.5) for k, z in zooms.items()}
    check("...half way in it is 0.75x on every weapon too: the easing follows the "
          "zoom's curve, not the zoom's magnitude",
          all(abs(v - 0.75) < 1e-9 for v in halfway.values()),
          str(sorted(halfway.items())))
    # And the contrast that justifies normalising at all: the raw ratio the mouse
    # uses would be a different speed per weapon and never exactly the number asked
    # for -- right for sensitivity, wrong for legs.
    raw = {k: 1.0 + (1.0 - COMBAT.ads_move_speed_scale) * (1.0 / z - 1.0)
           for k, z in zooms.items()}
    check("...which the raw CurrentFOV/BaseFOV ratio the sensitivity uses would "
          "NOT have been: that is why this one is normalised and that one is not",
          len({round(v, 6) for v in raw.values()}) > 1
          and all(abs(v - COMBAT.ads_move_speed_scale) > 1e-6
                  for v in raw.values()),
          str(sorted(raw.items())))


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
    plays = [n for n in by_pins(wg, "Asset", "SlotNodeName") if not is_melee_play(n)]
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
