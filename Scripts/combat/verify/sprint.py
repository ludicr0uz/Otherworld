"""verify.sprint -- the sprint's two ends in the weapon component's graph
(weapon_component/sprint.py): the key goes to the movement component, and
its answers come back into the variables the other graphs read.

The sprint's rules are the movement component's, in C++ (the latch: a sprint
that runs Stamina out stays off until the key is let go; the cone: only
while steering within 60 degrees of the way the character faces). A graph
check cannot see them, so they are checked in the running game:
probes/probe_sprint_latch.py, probe_sprint_forward.py and
probe_net_move_states.py. The component and its numbers are
verify/movement.py's.

Its numbers (player_tuning.csv through COMBAT): the jog on the character, the
sprint's speed and the stamina's two rates as variables the graph hands over.
"""

import unreal

from combat.player_tuning import (
    JOG_SPEED, SPRINT_DURATION, SPRINT_SPEED, STAMINA_RECHARGE, cms, table,
)
from combat.verify.fixtures import char, w, wg
from combat.verify.common import (
    BEL, BGE, PIN, cdo, check, has_in_pin, in_pins, load, num_pin, out_pins,
    pin_value,
)
from combat.sprint_tuning import (
    SPRINT_AHEAD_VAR, SPRINT_CONE_HALF_ANGLE_DEG, SPRINT_CONE_MIN_DOT,
    SPRINT_FORCED_VAR, SPRINT_SPEED_VAR, STAMINA_DRAIN_VAR, STAMINA_REGEN_VAR,
)
from combat.player_gait import (
    JOG_ROW_CMS, STOCK_DIR, gait_scale, is_scale_node, speed_feeders,
)
from combat.skin import player_skin
from combat.tuning import COMBAT
from combat.weapon_component.sprint import SPRINT_SPENT_VAR


def _title(n):
    return str(BEL.get_node_title(n)).replace("\n", " ")


def _feeders(node, *pins):
    return [PIN.get_owning_node(q)
            for pin in pins if has_in_pin(node, pin)
            for q in PIN.list_connected_pins(BEL.find_input_pin(node, pin))]


def _is_zero(node, pin):
    """An unconnected pin holding 0: a literal 0 reads back as an empty string
    once the Blueprint is loaded from disk, and as "0.0" in the editor that
    authored it."""
    return (not _feeders(node, pin)
            and (num_pin(node, pin) == 0.0 or pin_value(node, pin) == ""))


def _is_sprint_poll(node):
    return (in_pins(node) == {"self", "Key"}
            and "IsInputKeyDown" in _title(node)
            and any("Get KeySprint" in _title(f) for f in _feeders(node, "Key")))


def _copy_of(var, getter):
    """Is ``var`` written exactly once, straight off ``getter``'s answer?"""
    writes = [n for n in wg if has_in_pin(n, var) and _title(n) == f"Set {var}"]
    feeders = [_title(f).replace(" ", "") for n in writes for f in _feeders(n, var)]
    return len(writes) == 1 and feeders == [getter], (len(writes), feeders)


def check_sprint_latch():
    value = w.get_editor_property(SPRINT_SPENT_VAR)
    check(f"{SPRINT_SPENT_VAR} starts False", value is False, repr(value))
    asks = [n for n in wg if _title(n).replace(" ", "") == "SetSprintHeld"]
    held = [f for n in asks for f in _feeders(n, "bHeld")]
    halves = [f for n in held for f in _feeders(n, "A", "B")]
    check("the sprint key is handed to the movement component once a frame: "
          "the key, or a probe's hand on it",
          len(asks) == 1 and len(held) == 1 and "OR" in _title(held[0]).upper()
          and any(_is_sprint_poll(n) for n in halves)
          and any(SPRINT_FORCED_VAR in out_pins(n) for n in halves),
          str([_title(n) for n in held + halves]))
    forced = w.get_editor_property(SPRINT_FORCED_VAR)
    check(f"...and {SPRINT_FORCED_VAR} starts False", forced is False, repr(forced))
    for var, getter, words in (
            (SPRINT_SPENT_VAR, "IsSprintSpent", "the latch"),
            ("Sprinting", "IsSprinting", "Sprinting"),
            ("Stamina", "GetStamina", "Stamina")):
        ok, seen = _copy_of(var, getter)
        check(f"{words} is the movement component's answer, copied once a frame, "
              f"with no rule of this graph's own to disagree with the server's",
              ok, str(seen))


def check_sprint_forward():
    value = w.get_editor_property(SPRINT_AHEAD_VAR)
    check(f"{SPRINT_AHEAD_VAR} starts False", value is False, repr(value))
    check(f"the sprint's cone is {SPRINT_CONE_HALF_ANGLE_DEG:.0f} deg either "
          f"side of forward (a dot of {SPRINT_CONE_MIN_DOT})",
          SPRINT_CONE_HALF_ANGLE_DEG == 60.0 and SPRINT_CONE_MIN_DOT == 0.5,
          f"{SPRINT_CONE_HALF_ANGLE_DEG}, {SPRINT_CONE_MIN_DOT}")
    ok, seen = _copy_of(SPRINT_AHEAD_VAR, "IsSprintAhead")
    check(f"{SPRINT_AHEAD_VAR} is the movement component's answer, copied once "
          f"a frame", ok, str(seen))


def check_player_gait():
    """The jog plays the jog clip: the body's anim Blueprint scales GroundSpeed
    onto the blend space's jog row (player_gait.py)."""
    skin = player_skin()
    if skin.anim_bp.startswith(STOCK_DIR):
        unreal.log_warning("[VERIFY] player gait: the mannequin's anim "
                           "Blueprint, left in cm/s")
        return
    ed = BGE.get_graph_editor_by_name(load(skin.anim_bp), "EventGraph")
    _setter, feeders = speed_feeders(ed)
    scales = [n for n in feeders if is_scale_node(n)]
    check("the player's anim Blueprint scales GroundSpeed before the blend "
          "space reads it",
          len(feeders) == 1 and len(scales) == 1
          and {"Vector Length XY"} == {_title(f) for f in _feeders(scales[0], "A")},
          str([_title(n) for n in feeders]))
    scale = num_pin(scales[0], "B") if scales else None
    check(f"...by {JOG_ROW_CMS:g} over the jog's speed, so at "
          f"player_tuning.csv's jog the blend space is on its jog row, not "
          f"between it and the walk's",
          scale is not None and abs(scale - gait_scale()) < 1e-3
          and abs(COMBAT.jog_speed_cms * scale - JOG_ROW_CMS) < 1.0,
          f"x {scale}, want {gait_scale():.4f}")
    bs = load(skin.anim_bp.replace("ABP_Unarmed", "BS_Idle_Walk_Run"))
    rows = {}
    for s in (bs.get_editor_property("sample_data") if bs else []):
        clip = s.get_editor_property("animation")
        rows.setdefault(round(s.get_editor_property("sample_value").y, 1), set()).add(
            "Jog" if clip and "_Jog_" in clip.get_name() else "other")
    check(f"...and that row, at {JOG_ROW_CMS:g}, holds the jog clips alone, as the "
          f"blend space was baked",
          rows.get(JOG_ROW_CMS) == {"Jog"} and len(rows) == 3
          and len(bs.get_editor_property("sample_data")) == 27,
          str({k: sorted(v) for k, v in sorted(rows.items())}))


def check_sprint_rates():
    tuned = table()
    jog = cdo(char).get_editor_property("character_movement").get_editor_property(
        "max_walk_speed")
    check(f"the player jogs at player_tuning.csv's {tuned[JOG_SPEED]:g} m/s: the "
          f"character's own MaxWalkSpeed, which BeginPlay caches as BaseSpeed",
          abs(jog - cms(tuned[JOG_SPEED])) < 1e-3
          and abs(COMBAT.jog_speed_cms - jog) < 1e-3, f"{jog} cm/s")
    full = COMBAT.max_stamina
    for var, want, words in (
            (SPRINT_SPEED_VAR, cms(tuned[SPRINT_SPEED]),
             f"sprints at {tuned[SPRINT_SPEED]:g} m/s"),
            (STAMINA_DRAIN_VAR, full / tuned[SPRINT_DURATION],
             f"a full bar sprints for {tuned[SPRINT_DURATION]:g} s"),
            (STAMINA_REGEN_VAR, full / tuned[STAMINA_RECHARGE],
             f"an empty one refills in {tuned[STAMINA_RECHARGE]:g} s")):
        value = w.get_editor_property(var)
        check(f"...{words} ({var}, a float)",
              isinstance(value, float) and abs(value - want) < 1e-6, repr(value))
    # Variables, not literals: the PLAYER SETTINGS tab writes them in play.
    paces = [n for n in wg if _title(n).replace(" ", "") == "SetPace"]
    fed = {pin: [_title(f) for n in paces for f in _feeders(n, pin)]
           for pin in ("JogSpeed", "SprintSpeed", "StaminaDrainPerSecond",
                       "StaminaRegenPerSecond")}
    check("the movement component is handed BaseSpeed, SprintSpeed and the "
          "stamina's two rates, all read off the component",
          len(paces) == 1 and fed == {
              "JogSpeed": ["Get BaseSpeed"],
              "SprintSpeed": [f"Get {SPRINT_SPEED_VAR}"],
              "StaminaDrainPerSecond": [f"Get {STAMINA_DRAIN_VAR}"],
              "StaminaRegenPerSecond": [f"Get {STAMINA_REGEN_VAR}"]},
          str(fed))


def run():
    check_sprint_latch()
    check_sprint_forward()
    check_sprint_rates()
    check_player_gait()
