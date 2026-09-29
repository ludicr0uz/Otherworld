"""verify.accuracy -- the accuracy cloud and the stance/aim recoil factors
(weapon_component/accuracy.py, GUN_ACCURACY in weapon_specs.py): the per-gun
table, the variables it lands in, the per-frame AimSpread/RecoilScale/
ReticleSpread, and the shot's one draw inside the cloud (firing.py).
"""

from combat.verify.common import (
    BEL, PIN, cdo, check, in_pins, load, num_pin,
)
from combat.verify.fixtures import w, wg
from combat.weapon_component.accuracy import (
    ACCURACY_OUT_VARS, AIM_SPREAD_VAR,
)
from combat.weapon_component.firing import SHOT_DIRECTION_VAR
from combat.weapon_component.stance import CROUCH, PRONE
from combat.weapon_specs import ACCURACY_VARS, GUN_ACCURACY, _weapon_specs


def _title(n):
    return str(BEL.get_node_title(n)).replace("\n", " ")


def _sources(node, pin_name):
    """Titles of the nodes wired straight into one input pin."""
    pin = BEL.find_input_pin(node, pin_name)
    return {_title(PIN.get_owning_node(q)) for q in PIN.list_connected_pins(pin)} \
        if pin else set()


def _sets(var):
    return [n for n in wg if _title(n) == f"Set {var}" and var in in_pins(n)]


def check_accuracy_table():
    specs = _weapon_specs()
    check("every weapon has an accuracy row, and every row a weapon",
          set(GUN_ACCURACY) == {sp["display"] for sp in specs},
          str(sorted(GUN_ACCURACY)))
    columns = {col for col, _var in ACCURACY_VARS}
    for sp in specs:
        row, name = GUN_ACCURACY.get(sp["display"], {}), sp["display"]
        check(f"{name}: the row sets every accuracy column",
              set(row) == columns, str(sorted(set(row) ^ columns)))
        if set(row) != columns:
            continue
        check(f"{name}: recoil climbs 4x more than it swings "
              f"({row['recoil']} up, +/-{row['recoil_yaw']} sideways)",
              abs(row["recoil"] - 4.0 * row["recoil_yaw"]) < 1e-9)
        for kind in ("spread", "recoil"):
            prone, crouch = row[f"{kind}_prone"], row[f"{kind}_crouch"]
            check(f"{name}: {kind} is steadied prone ({prone}) more than "
                  f"crouched ({crouch}), and crouched more than standing",
                  0.0 < prone < crouch < 1.0)
            check(f"{name}: the shoulder aim steadies {kind} "
                  f"(x{row[f'{kind}_shoulder']})",
                  0.0 < row[f"{kind}_shoulder"] < 1.0)
        check(f"{name}: down the sights kicks less than on the shoulder",
              0.0 < row["recoil_sights"] < row["recoil_shoulder"])
        check(f"{name}: a cloud at the hip ({row['spread']} deg)",
              row["spread"] > 0.0)
        check(f"{name}: a pellet pattern only with more than one pellet",
              (row["pellet_spread"] > 0.0) == (sp["pellets"] > 1),
              f"{sp['pellets']} pellets, pattern {row['pellet_spread']}")


def check_accuracy_on_weapons():
    for sp in _weapon_specs():
        d = cdo(load(sp["path"]))
        bad = []
        for col, var in ACCURACY_VARS:
            got = d.get_editor_property(var)
            if not isinstance(got, float) or abs(got - sp[col]) > 1e-6:
                bad.append(f"{var}={got!r} want {sp[col]}")
        check(f"{sp['display']}: all {len(ACCURACY_VARS)} accuracy variables "
              f"are floats holding its row", not bad, "; ".join(bad))


def check_accuracy_per_frame():
    for var in ACCURACY_OUT_VARS:
        got = w.get_editor_property(var)
        check(f"{var} is a float on the component, starting at zero",
              isinstance(got, float) and abs(got) < 1e-9, repr(got))
        sets = _sets(var)
        check(f"...and {var} is written twice a frame: from the held gun, "
              f"and zero with empty hands", len(sets) == 2, str(len(sets)))

    # Each factor is read off Held exactly once, behind the IsValid Branch.
    for _col, var in ACCURACY_VARS:
        if var in ("PelletSpreadDegrees", "RecoilPitch", "RecoilYaw"):
            continue
        reads = [n for n in wg if _title(n) == f"Get {var}"]
        check(f"accuracy.py reads Held.{var} once", len(reads) == 1, str(len(reads)))

    sights = [n for n in wg if {"A", "B", "bPickA"} <= in_pins(n)
              and "Get SightAiming" in _sources(n, "bPickA")]
    exact = [n for n in sights if not _sources(n, "A") and num_pin(n, "A") == 0.0]
    check("down the sights picks a cloud of exactly zero, and the gun's own "
          "sights factor for the kick", len(sights) == 2 and len(exact) == 1,
          f"{len(sights)} SightAiming selects, {len(exact)} to zero")
    for kind in ("Spread", "Recoil"):
        for low, value in (("Crouch", CROUCH), ("Prone", PRONE)):
            var = f"{kind}{low}Scale"
            picks = [n for n in wg if {"A", "B", "bPickA"} <= in_pins(n)
                     and f"Get {var}" in _sources(n, "A")]
            gates = [PIN.get_owning_node(q) for n in picks for q in
                     PIN.list_connected_pins(BEL.find_input_pin(n, "bPickA"))]
            check(f"{var} is picked when Stance == {value}",
                  len(picks) == 1 and len(gates) == 1
                  and "Get Stance" in _sources(gates[0], "A")
                  and num_pin(gates[0], "B") == value,
                  f"{len(picks)} picks")
    tans = [n for n in wg if _title(n).replace(" ", "").startswith("Tan(Degrees)")
            or _title(n).replace(" ", "") == "DegTan"]
    check("ReticleSpread is the cloud's tangent over the half field of view's",
          len(tans) == 2, str(sorted({_title(n) for n in tans})))


def check_shot_draw():
    holds = _sets(SHOT_DIRECTION_VAR)
    check("the shot's direction is drawn once per trigger pull, into "
          "ShotDirection", len(holds) == 1, str(len(holds)))
    cones = [n for n in wg if {"ConeDir", "ConeHalfAngleInRadians"} <= in_pins(n)]
    check("two cones: the shot inside the cloud, each pellet inside the pattern",
          len(cones) == 2, str(len(cones)))
    if len(holds) != 1 or len(cones) != 2:
        return
    readers = [PIN.get_owning_node(q) for c in cones
               for q in PIN.list_connected_pins(BEL.find_output_pin(c, "ReturnValue"))]
    drawn = [c for c in cones if any(
        PIN.get_owning_node(q) == holds[0]
        for q in PIN.list_connected_pins(BEL.find_output_pin(c, "ReturnValue")))]
    check("...the cloud's draw is read by the ShotDirection write alone -- the "
          "cone is pure, so a second reader would be a second draw",
          len(drawn) == 1 and len([r for r in readers if r == holds[0]]) == 1)
    if len(drawn) != 1:
        return
    pellet = next(c for c in cones if c != drawn[0])

    def angle_from(cone):
        rad = [PIN.get_owning_node(q) for q in PIN.list_connected_pins(
            BEL.find_input_pin(cone, "ConeHalfAngleInRadians"))]
        return _sources(rad[0], "A") if rad else set()

    check("...inside AimSpread, which is zero down the sights",
          angle_from(drawn[0]) == {f"Get {AIM_SPREAD_VAR}"},
          str(angle_from(drawn[0])))
    check("each pellet flies around ShotDirection inside the gun's own pattern",
          _sources(pellet, "ConeDir") == {f"Get {SHOT_DIRECTION_VAR}"}
          and angle_from(pellet) == {"Get PelletSpreadDegrees"},
          f"{_sources(pellet, 'ConeDir')} / {angle_from(pellet)}")
    then = BEL.find_then_pin(holds[0])
    nxt = {_title(PIN.get_owning_node(q)) for q in PIN.list_connected_pins(then)}
    check("...drawn before the pellet loop starts", any("For" in t for t in nxt),
          str(nxt))


def run():
    check_accuracy_table()
    check_accuracy_on_weapons()
    check_accuracy_per_frame()
    check_shot_draw()
