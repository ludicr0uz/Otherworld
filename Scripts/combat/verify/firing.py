"""verify.firing -- Recoil, automatic fire and debug mode.
"""

from combat.game_state import DEBUG_MODE_VAR, TRACE_DEBUG_SECONDS
from combat.paths import GAME_MODE_BP_PATH
from combat.tuning import AUTO_DISPLAYS, COMBAT
from combat.weapon_specs import _weapon_specs
from combat.verify.fixtures import titles, wc_cdo, wg
from combat.verify.common import (
    BEL, PIN, by_pins, cdo, check, in_pins, load, num_pin, out_pins,
    pin_value,
)


# ─── Recoil ──────────────────────────────────────────────────────────────────

def check_recoil():
    # The requested ordering, read off the built assets rather than off the table
    # that produced them, plus the one trap this feature had: routing the kick
    # through AddControllerPitchInput would multiply it by the deprecated
    # InputPitchScale, which is exactly the handle the mouse-sensitivity setting
    # drives -- so the recoil would scale with the player's slider.

    kick = {}
    for sp in _weapon_specs():
        got = cdo(load(sp["path"])).get_editor_property("RecoilPitch")
        check(f"{sp['display']}: RecoilPitch is {sp['recoil']} deg",
              isinstance(got, float) and abs(got - sp["recoil"]) < 1e-6, repr(got))
        kick[sp["display"]] = got

    check("every weapon kicks at all", all(v > 0.0 for v in kick.values()),
          str(sorted(kick.items(), key=lambda kv: -kv[1])))
    heavy = min(kick["Shotgun"], kick["Sniper"])
    check("the shotgun and the sniper kick hardest of the five",
          heavy > max(kick["Rifle"], kick["SMG"], kick["Pistol"]),
          f"shotgun {kick['Shotgun']}, sniper {kick['Sniper']} vs "
          f"rifle {kick['Rifle']}")
    check("...the assault rifle next", kick["Rifle"] > kick["SMG"],
          f"rifle {kick['Rifle']} > smg {kick['SMG']}")
    check("...the SMG less than that", kick["SMG"] > kick["Pistol"],
          f"smg {kick['SMG']} > pistol {kick['Pistol']}")
    check("...and the pistol least of all",
          kick["Pistol"] == min(kick.values()),
          f"pistol {kick['Pistol']}, lowest of {sorted(kick.values())}")

    for name in ("RecoilDebt", "RecoilYawDebt", "RecoilYawKick"):
        got = wc_cdo.get_editor_property(name)
        check(f"{name} is a float on the component, starting settled at zero",
              isinstance(got, float) and abs(got) < 1e-9, repr(got))

    flat = [t.replace(" ", "") for t in titles]
    banned = sorted({t for t in flat
                     if "PitchInput" in t or "ControllerYawInput" in t})
    check("the kick never goes through AddControllerPitchInput -- that route "
          "multiplies by the deprecated InputPitchScale the sensitivity setting "
          "drives, so recoil would scale with the player's slider",
          not banned, str(banned))
    # The sights' pitch (verify/aim_pitch.py) reads the view too, but writes
    # only the anim BP, so it is not one of the read-before-write pairs.
    pitch_reads = sum(1 for t in flat if t.startswith("SetAimPitch"))
    for label, want, n in (("written", "SetControlRotation", 2),
                           ("read back first", "GetControlRotation", 2)):
        hits = [t for t in flat if t.startswith(want)]
        if want == "GetControlRotation":
            hits = hits[pitch_reads:]
        check(f"the control rotation is {label} exactly {n}x: the kick and the "
              f"recovery", len(hits) == n, f"{len(hits)} x {want}")
    makers = [n for n in wg if {"Roll", "Pitch", "Yaw"} <= in_pins(n)]
    check("both writes are rebuilt through a Make Rotator", len(makers) == 2,
          str(len(makers)))
    check("...whose Roll comes from the rotation that was read, not a literal zero "
          "that would quietly decide the view never rolls",
          bool(makers) and all(PIN.list_connected_pins(BEL.find_input_pin(m, "Roll"))
                               for m in makers),
          str(len(makers)))

    interps = by_pins(wg, "Current", "Target", "DeltaTime", "InterpSpeed")
    check("the two debts recover by interpolation, alongside the zoom's and "
          "the sight camera's",
          len(interps) == 4,
          f"{len(interps)} FInterpTo (2 recoil + 1 FOV + 1 SightBlend)")
    settling = [n for n in interps
                if (num_pin(n, "Target") or 0.0) == 0.0
                and abs((num_pin(n, "InterpSpeed") or 0.0)
                        - COMBAT.recoil_recovery_speed) < 1e-6]
    check(f"...toward zero at {COMBAT.recoil_recovery_speed:g}, so the "
          f"accumulator always settles and nothing builds up across a magazine",
          len(settling) == 2, str(len(settling)))
    check("only part of each step is handed back, which is what makes a burst "
          "climb instead of springing exactly home",
          0.0 < COMBAT.recoil_recovery_fraction < 1.0,
          f"{COMBAT.recoil_recovery_fraction} of every kick returned, "
          f"{(1 - COMBAT.recoil_recovery_fraction) * 100:.0f}% kept")
    paid = [n for n in by_pins(wg, "A", "B")
            if abs((num_pin(n, "B") or 0.0)
                   - COMBAT.recoil_recovery_fraction) < 1e-9]
    check("...and that fraction is in the graph twice, pitch and yaw",
          len(paid) == 2, str(len(paid)))
    for var in ("RecoilDebt", "RecoilYawDebt"):
        writes = [t for t in titles if t == f"Set {var}"]
        check(f"{var} is written twice: charged by the shot, settled by the tick",
              len(writes) == 2, str(len(writes)))

    check("aiming down the sights steadies the kick",
          0.0 < COMBAT.recoil_ads_scale < 1.0, f"x{COMBAT.recoil_ads_scale}")
    steadied = [n for n in by_pins(wg, "A", "B", "bPickA")
                if abs((num_pin(n, "A") or 0.0) - COMBAT.recoil_ads_scale) < 1e-9]
    check("...through the same SelectFloat shape the cone uses, so the aimed and "
          "unaimed cases cannot drift into two branches", len(steadied) == 1,
          str(len(steadied)))
    check("the sideways kick is a fraction of the vertical rather than a second "
          "per-weapon column", 0.0 < COMBAT.recoil_horizontal_ratio < 1.0,
          f"+/-{COMBAT.recoil_horizontal_ratio} of the pitch")
    draws = [n for n in wg if str(BEL.get_node_title(n)).replace(" ", "").lower()
             .startswith("randomfloatinrange")]
    check("...drawn once per shot", len(draws) == 1, str(len(draws)))
    if draws:
        readers = {str(BEL.get_node_title(PIN.get_owning_node(q))).replace("\n", " ")
                   for q in PIN.list_connected_pins(
                       BEL.find_output_pin(draws[0], "ReturnValue"))}
        check("...and read by exactly one thing, the RecoilYawKick write -- "
              "RandomFloatInRange is pure, so a second reader would be a second "
              "number and the recovery would never cancel the kick",
              readers == {"Set RecoilYawKick"}, str(sorted(readers)))


# ─── Automatic fire ──────────────────────────────────────────────────────────

def check_automatic_fire():
    # Hold the button and the SMG and the assault rifle keep firing; the shotgun,
    # the pistol and the sniper are one shot per click. What makes this cheap is
    # that the rate limit already existed: FireInterval and NextFireTime were being
    # consulted on every frame the trigger was down long before anything could hold
    # it down. All that is added is whether a held button still counts as a pull.

    autos = {sp["display"] for sp in _weapon_specs() if sp["automatic"]}
    check("exactly the SMG and the assault rifle are automatic",
          autos == set(AUTO_DISPLAYS), str(sorted(autos)))
    for sp in _weapon_specs():
        check(f"{sp['display']}: Automatic is {sp['automatic']}",
              bool(cdo(load(sp["path"])).get_editor_property("Automatic"))
              is bool(sp["automatic"]))
    # A held trigger with no rate limit is one shot per frame, i.e. 60 rounds a
    # second out of a 30-round magazine. Both automatics must have an interval.
    for name in AUTO_DISPLAYS:
        sp = next(x for x in _weapon_specs() if x["display"] == name)
        check(f"{name}: has a fire interval, so a held trigger is not one shot "
              f"per frame",
              float(cdo(load(sp["path"])).get_editor_property("FireInterval")) > 0.0,
              str(sp["interval"]))

    downs = [n for n in wg if "IsInputKeyDown" in str(BEL.get_node_title(n))]
    held_binds = sorted(
        str(BEL.get_node_title(PIN.get_owning_node(q))).replace("\n", " ")
        for x in downs
        for q in PIN.list_connected_pins(BEL.find_input_pin(x, "Key")))
    check("five keys are polled held rather than tapped: sprint, the two aims, "
          "the guard and the trigger",
          held_binds == ["Get KeyAim", "Get KeyBlock", "Get KeyFire", "Get KeySights",
                         "Get KeySprint"],
          str(held_binds))

    # THE TRAP THIS SECTION EXISTS FOR. Automatic lives on the weapon, so reading
    # it means a pure Get with its self pin driven by Held -- and Held is null
    # whenever the player's hands are empty. Read in the OUTER fire gate's
    # condition, which is pulled on every frame, that is an "Accessed None" per
    # frame forever; read behind it, where Held has been checked valid, it is free.
    #
    # Rather than try to name the outer gate, assert the invariant: Automatic is
    # read in the same Branch condition as the other Held properties, all of which
    # are already known to sit behind the valid-Held gate.
    def upstream(pin, limit=200):
        """Every node feeding this pin, following DATA links only.

        Skipping the exec pin is the whole of it. list_input_pins hands back the
        node's "execute" pin alongside its data pins, and following that walks
        backwards up the exec chain -- from which every pure node in the graph is
        reachable, so the traversal answers "yes" for every Branch and proves
        nothing. The first version of this check did exactly that and reported
        five branches consulting Automatic when there is one.
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

    def reads(nodes, var):
        return any(var in out_pins(x) for x in nodes)

    conds = [(x, upstream(BEL.find_input_pin(x, "Condition")))
             for x in wg
             if x.get_class().get_name() == "K2Node_IfThenElse"
             and BEL.find_input_pin(x, "Condition")]
    with_auto = [(x, up) for x, up in conds if reads(up, "Automatic")]
    check("exactly one Branch consults Automatic", len(with_auto) == 1,
          f"{len(with_auto)} branches")
    if with_auto:
        _, up = with_auto[0]
        check("...and it is the gate that also reads Loaded and NextFireTime, so "
              "Automatic is read behind the valid-Held check and not in front of it",
              reads(up, "Loaded") and reads(up, "NextFireTime"),
              f"Loaded={reads(up, 'Loaded')} NextFireTime={reads(up, 'NextFireTime')}")
        # The held button only counts when the weapon says so: Automatic must be
        # AND-ed with the key, never read on its own.
        consumers = [PIN.get_owning_node(q)
                     for x in wg if "Automatic" in out_pins(x)
                     for q in PIN.list_connected_pins(
                         BEL.find_output_pin(x, "Automatic"))]
        check("Automatic is AND-ed with the held key, not used on its own",
              bool(consumers) and all("AND" in str(BEL.get_node_title(c)).upper()
                                      for c in consumers),
              str([str(BEL.get_node_title(c)) for c in consumers]))
    # ...and a semi-automatic still fires: the tap has to bypass the Automatic
    # test, which means an OR sits between them.
    check("a tapped trigger fires regardless of Automatic (an OR, not an AND)",
          len([x for x in wg if "OR Boolean"
               in str(BEL.get_node_title(x)).replace("\n", " ")]) >= 2,
          "one OR for the unlimited-ammo short circuit, one for tap-or-hold")


# ─── Debug mode ──────────────────────────────────────────────────────────────

def check_debug_mode():
    mode_cdo = cdo(load(GAME_MODE_BP_PATH))
    check("the GameMode carries the debug flag, where a component can reach it",
          isinstance(mode_cdo.get_editor_property(DEBUG_MODE_VAR), bool))
    check("...and it is OFF by default -- the overlays are instrumentation",
          mode_cdo.get_editor_property(DEBUG_MODE_VAR) is False)
    check("the pellet tracer is a DrawDebugLine, not a trace that draws itself",
          bool(by_pins(wg, "LineStart", "LineEnd")),
          f"{len(by_pins(wg, 'LineStart', 'LineEnd'))} DrawDebugLine node(s)")
    check("...and it lasts as long as the tracer always did",
          all(abs(float(pin_value(n, "Duration") or 0) - TRACE_DEBUG_SECONDS) < 1e-3
              for n in by_pins(wg, "LineStart", "LineEnd")),
          f"{TRACE_DEBUG_SECONDS}s")
    # Read once per shot off the GameMode, cached, then branched on per pellet.
    check("the flag is read off the GameMode once per shot and cached",
          len([t for t in (str(BEL.get_node_title(n)).replace("\n", " ")
                           for n in wg) if t == f"Set {DEBUG_MODE_VAR}"]) == 1)
    # Three reads: the GameMode's own (once per shot), then the cached copy twice
    # per pellet -- the tracer's branch and the damage readout's.
    check("...and the pellet loop branches on the cached copy",
          len([n for n in wg if DEBUG_MODE_VAR in out_pins(n)]) == 3,
          f"{len([n for n in wg if DEBUG_MODE_VAR in out_pins(n)])} reads")


def run():
    check_recoil()
    check_automatic_fire()
    check_debug_mode()
