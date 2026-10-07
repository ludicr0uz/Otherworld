"""verify.headshot -- the headshot stamp (weapon_component/headshot.py):
HeadshotTime, written with the game's time by a pellet and by a thrown blade
that struck a bone of the target's head, and left alone by any other hit.

That a round in a live wanderer's head stamps it is probes/probe_headshot.py;
the X the HUD draws off it is verify_graphics_menu's (reticle_checks.py).
"""

from combat.headshot_tuning import HEADSHOT_NEVER, HEADSHOT_TIME_VAR
from combat.hit_zones import HEAD_BONES_VAR, HIT_BONE_VAR
from combat.verify.common import BEL, PIN, check, in_pins
from combat.verify.fixtures import w, wg
from combat.verify.sights import _feeds, _title
from combat.weapon_component.throw_strike import THROW_BONE_VAR


def _one(pin):
    for q in PIN.list_connected_pins(pin):
        return PIN.get_owning_node(q)
    return None


def check_headshot_stamp():
    value = w.get_editor_property(HEADSHOT_TIME_VAR)
    check(f"{HEADSHOT_TIME_VAR} is a float on the weapon component, "
          f"{HEADSHOT_NEVER:g} until a head is struck: game time starts at 0, "
          f"and a 0 would read as a headshot at the start of a level",
          isinstance(value, float) and value == HEADSHOT_NEVER, repr(value))
    # A RepNotify's Set reads "Set with Notify": match the head and the tail.
    writes = [n for n in wg if _title(n).startswith("Set")
              and _title(n).endswith(f" {HEADSHOT_TIME_VAR}")]
    check("two things write it: a pellet's wound and a thrown blade's (its arrival on "
          "the owning client is a third, in the OnRep: verify/fx.py)",
          len(writes) == 2, str(len(writes)))
    bones = set()
    for n in writes:
        pick = _one(BEL.find_input_pin(n, HEADSHOT_TIME_VAR))
        ok = pick is not None and {"A", "B", "bPickA"} <= in_pins(pick)
        a = {_title(m) for m in _feeds(BEL.find_input_pin(pick, "A"))} if ok else set()
        b = {_title(m) for m in _feeds(BEL.find_input_pin(pick, "B"))} if ok else set()
        cond = {_title(m) for m in _feeds(BEL.find_input_pin(pick, "bPickA"))} if ok else set()
        bone = sorted(t for t in cond if t in (f"Get {HIT_BONE_VAR}", f"Get {THROW_BONE_VAR}"))
        bones.update(bone)
        check(f"...{' / '.join(bone) or 'a write'}: the game's time if that "
              f"bone is one of the target's {HEAD_BONES_VAR}, else what "
              f"{HEADSHOT_TIME_VAR} was",
              ok and any("Time" in t for t in a) and b == {f"Get {HEADSHOT_TIME_VAR}"}
              and len(bone) == 1 and any(HEAD_BONES_VAR in t for t in cond)
              and bool(PIN.list_connected_pins(BEL.find_input_pin(n, "execute"))),
              f"A {sorted(a)}, B {sorted(b)}, pick {sorted(cond)}")
    check(f"...one off the pellet's {HIT_BONE_VAR}, one off the blade's {THROW_BONE_VAR}",
          bones == {f"Get {HIT_BONE_VAR}", f"Get {THROW_BONE_VAR}"}, str(sorted(bones)))


def run():
    check_headshot_stamp()
