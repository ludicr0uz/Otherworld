"""verify.stance -- crouch and prone (weapon_component/stance.py): the two
keys, the character being allowed to crouch, the Stance toggle, the crouch it
drives, and what a stance does to the footsteps (combat/footsteps.py).
"""

from combat.footsteps import FOOTSTEP_BP_PATH
from combat.noise import NOISE_RANGE_VAR
from combat.tuning import BIND_VARS, COMBAT, CROUCH_KEY, PRONE_KEY
from combat.verify.common import (
    BEL, PIN, cdo, check, graph, in_pins, load, num_pin, titled,
)
from combat.verify.fixtures import char, w, wg
from combat.weapon_component.stance import CROUCH, PRONE, STANCE_VAR, STAND


def _title(n):
    return str(BEL.get_node_title(n)).replace("\n", " ")


def _flat(n):
    return _title(n).replace(" ", "")


def _feeds(pin, limit=250):
    """Every node feeding this pin through DATA links only."""
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


def _runs(node):
    pin = BEL.find_input_pin(node, "execute")
    return bool(pin and PIN.list_connected_pins(pin))


def _sets(nodes, var):
    return [n for n in nodes if _title(n) == f"Set {var}" and var in in_pins(n)]


def _movement(bp):
    return cdo(bp).get_editor_property("character_movement")


def check_stance_keys():
    names = [v for v, _k in BIND_VARS]
    check(f"crouch ({CROUCH_KEY}) and prone ({PRONE_KEY}) are their own binds, "
          f"appended after every older one so no saved bind changes meaning",
          names[9:11] == ["KeyCrouch", "KeyProne"]
          and w.get_editor_property("KeyCrouch").export_text() == CROUCH_KEY
          and w.get_editor_property("KeyProne").export_text() == PRONE_KEY,
          str(names))
    check("Stance is an int that starts standing",
          w.get_editor_property(STANCE_VAR) == STAND
          and isinstance(w.get_editor_property(STANCE_VAR), int),
          repr(w.get_editor_property(STANCE_VAR)))


def check_character_can_crouch():
    m = _movement(char)
    check("the player's movement component may crouch (the template ships it off)",
          m.get_editor_property("nav_agent_props").get_editor_property("can_crouch"))
    check("...and may walk off a ledge while low",
          m.get_editor_property("can_walk_off_ledges_when_crouching"))
    cap = cdo(char).get_editor_property("capsule_component")
    radius = cap.get_unscaled_capsule_radius()
    standing = cap.get_unscaled_capsule_half_height()
    # The engine clamps a crouch to the radius; a prone height under it would
    # never match the capsule, and the stance code would re-crouch every frame.
    check("prone is lower than crouched, which is lower than standing, and "
          "prone is no shorter than the capsule's radius",
          radius <= COMBAT.prone_half_height_cm < COMBAT.crouch_half_height_cm < standing,
          f"radius {radius}, prone {COMBAT.prone_half_height_cm}, "
          f"crouch {COMBAT.crouch_half_height_cm}, standing {standing}")
    check("a low stance is slower, and prone slowest",
          0.0 < COMBAT.prone_speed_scale < COMBAT.crouch_speed_scale < 1.0)


def check_stance_toggle():
    sets = _sets(wg, STANCE_VAR)
    check("Stance is written once a frame, in one place", len(sets) == 1, str(len(sets)))
    if len(sets) != 1:
        return
    src = _feeds(BEL.find_input_pin(sets[0], STANCE_VAR))
    names = {_title(n) for n in src}
    check("...toggled by the crouch and prone keys, tapped, and stood up by sprinting",
          {"Get KeyCrouch", "Get KeyProne", "Get Sprinting", f"Get {STANCE_VAR}"} <= names
          and sum("WasInputKeyJustPressed" in _flat(n) for n in src) == 2
          and not any("IsInputKeyDown" in _flat(n) for n in src),
          str(sorted(names)))
    literals = {num_pin(n, p) for n in src for p in ("A", "B")
                if "Select" in _flat(n) or "==" in _title(n)}
    check("...between the three stances", {STAND, CROUCH, PRONE} <= literals,
          str(sorted(x for x in literals if x is not None)))
    check("...and every step of it runs", _runs(sets[0]))


def check_crouch_applied():
    # How low and how fast are the movement component's (verify/movement.py),
    # so the owning client and the server make the same capsule.
    # The call, not the variable's write, which has the same title.
    tells = [n for n in wg if _flat(n) == "SetStance" and "Character" in in_pins(n)]
    src = ({PIN.get_owning_node(q) for q in PIN.list_connected_pins(
        BEL.find_input_pin(tells[0], "Stance"))} if tells else set())
    check("the stance is handed to the movement component, once a frame, on "
          "the exec chain",
          len(tells) == 1 and _runs(tells[0])
          and {_title(n) for n in src} == {f"Get {STANCE_VAR}"},
          f"{len(tells)} SetStance, fed by {sorted(_title(n) for n in src)}")
    own = [n for n in wg if _flat(n) in ("Crouch", "UnCrouch")
           or _title(n) in ("Set CrouchedHalfHeight", "Set MaxWalkSpeedCrouched")]
    check("...and no graph crouches the character or sizes its crouch itself",
          not own, str([_title(n) for n in own]))


def check_footsteps_by_stance():
    fbp = load(FOOTSTEP_BP_PATH)
    f = cdo(fbp)
    fg = graph(fbp).list_all_nodes()
    check("a footstep's volume and reach default to 1.0, as floats (the "
          "wanderers never change them)",
          all(isinstance(f.get_editor_property(v), float)
              and f.get_editor_property(v) == 1.0 for v in ("StepVolume", "StepNoise")))
    plays = [n for n in fg if "PlaySoundAtLocation" in _flat(n)]
    check("the step, and the rustle of a bush gone through, play at StepVolume",
          len(plays) == 2 and all("Get StepVolume" in {
              _title(n) for n in _feeds(BEL.find_input_pin(p, "VolumeMultiplier"))}
              for p in plays),
          f"{len(plays)} PlaySoundAtLocation")
    ranges = [n for n in fg if _title(n) == f"Set {NOISE_RANGE_VAR}"]
    check("the step's noise reach is scaled by StepNoise",
          len(ranges) == 1 and "Get StepNoise" in {
              _title(n) for n in _feeds(BEL.find_input_pin(ranges[0], NOISE_RANGE_VAR))})
    # CanJump is false while crouched, so it silenced every low step.
    check("the ground test is the movement component's, not CanJump",
          any(_flat(n) == "IsMovingOnGround" for n in fg)
          and not any(_flat(n) == "CanJump" for n in fg))
    for var, crouch, prone in (
            ("StepVolume", COMBAT.crouch_step_volume, COMBAT.prone_step_volume),
            ("StepNoise", COMBAT.crouch_step_noise, COMBAT.prone_step_noise)):
        writes = _sets(wg, var)
        src = _feeds(BEL.find_input_pin(writes[0], var)) if writes else set()
        lits = {num_pin(n, p) for n in src for p in ("A", "B")}
        check(f"the stance writes the player's {var}: 1 standing, {crouch} "
              f"crouched, {prone} prone",
              len(writes) == 1 and _runs(writes[0]) and 0.0 < prone < crouch < 1.0
              and {1.0, crouch, prone} <= lits
              and f"Get {STANCE_VAR}" in {_title(n) for n in src},
              str(sorted(x for x in lits if x is not None)))


def run():
    check_stance_keys()
    check_character_can_crouch()
    check_stance_toggle()
    check_crouch_applied()
    check_footsteps_by_stance()
