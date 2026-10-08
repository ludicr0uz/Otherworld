"""verify.knife -- the knife (combat/knife.py, knife_anim.py and
weapon_component/knife.py): the item, the slash clip, the loadout, the press
behind the fire gate, the swing and the blow.

The helpers is_melee_play / is_melee_sweep / is_melee_gate / is_melee_write
(the punch's or the knife's) let the sections that count the ready-pose plays,
the traces, the fire gate and the hit's stamps set both attacks aside.
"""

import unreal

from combat.anim_blueprint import AIM_SLOT
from combat.heat_tuning import BLOW_DAMAGE_VAR
from combat.knife import KNIFE_DISPLAY, KNIFE_MESH
from combat.knife_anim import FPS, FRAMES, SLASH_KEYS
from combat.light_tuning import LIGHTS_VAR
from combat.paths import (
    HOLD_KNIFE_ANIM_PATH, ITEM_BP_PATH, KNIFE_ANIM_PATH, KNIFE_BP_PATH,
)
from combat.skin import player_skin
from combat.strike_vars import SERVER_SLASH
from combat.tuning import COMBAT
from combat.verify.common import (
    take_hits,
    BEL, PIN, by_pins, cdo, check, component_template, graph, in_pins, load, num_pin,
    out_pins, pin_value,
)
from combat.verify import fx as fxv
from combat import fx_vars as FX
from combat.verify.fixtures import w, wc, wg
from combat.verify.punch import (
    _feeders, _feeds, _title, is_punch_gate, is_punch_play, is_punch_sweep,
    is_punch_write,
)
from combat.weapon_component.knife import (
    KNIFE_ANIM_VAR, KNIFE_DUE_VAR, KNIFE_PENDING_VAR, KNIFE_QUEUED_VAR, MELEE_VAR,
    NEXT_KNIFE_VAR,
)


def is_knife_play(node):
    return any(_title(f) == f"Get {KNIFE_ANIM_VAR}" for f in _feeders(node, "Asset"))


def is_knife_sweep(node):
    return "Radius" in in_pins(node) and num_pin(node, "Radius") == COMBAT.knife_radius_cm


def is_knife_gate(node):
    return (_title(node) == "Branch"
            and f"Get {NEXT_KNIFE_VAR}"
            in {_title(x) for x in _feeds(BEL.find_input_pin(node, "Condition"))})


def is_melee_play(node):
    return is_punch_play(node) or is_knife_play(node)


def is_melee_sweep(node):
    return is_punch_sweep(node) or is_knife_sweep(node)


def is_melee_gate(node):
    return is_punch_gate(node) or is_knife_gate(node)


def is_melee_write(node, pin):
    """A write whose value comes off either melee sweep's hit result."""
    return is_punch_write(node, pin) or any(
        is_knife_sweep(t) for b in _feeders(node, pin) for t in _feeders(b, "Hit"))


def _exec_next(node):
    then = BEL.find_then_pin(node)
    return [PIN.get_owning_node(q) for q in PIN.list_connected_pins(then)] if then else []


def check_knife_item():
    bp = load(KNIFE_BP_PATH)
    check("BP_Knife exists", bp is not None)
    if bp is None:
        return
    check("...a child of BP_WeaponItem, so the bag, Q, G, E and the HUD take it",
          bp.get_blueprint_parent_class() == BEL.generated_class(load(ITEM_BP_PATH)))
    d = cdo(bp)
    flags = {k: d.get_editor_property(k) for k in
             (MELEE_VAR, "Consumable", "UsesAmmo", "Automatic", "Dropped")}
    check("...Melee, and not a consumable, a gun or lying about",
          flags == {MELEE_VAR: True, "Consumable": False, "UsesAmmo": False,
                    "Automatic": False, "Dropped": False}, str(flags))
    model = component_template(bp, "Model")
    mesh = model.get_editor_property("skeletal_mesh_asset") if model else None
    check("...drawn by the pack's M9 knife (SK_M9_Knife_X)",
          mesh is not None and mesh == load(KNIFE_MESH), str(mesh))
    blade = (unreal.MathLibrary.greater_greater_vector_rotator(
        unreal.Vector(0.0, 0.0, -1.0), model.get_editor_property("relative_rotation"))
        if model else None)
    check("...blade up and forward out of the fist",
          blade is not None and blade.z > 0.8 and blade.x > 0.1, str(blade))
    pose = d.get_editor_property("AimPose")
    check("...held in A_HoldKnife, with an icon and its name",
          pose is not None and pose == load(HOLD_KNIFE_ANIM_PATH)
          and d.get_editor_property("Icon") is not None
          and str(d.get_editor_property("DisplayName")) == KNIFE_DISPLAY,
          f"{pose} {d.get_editor_property('Icon')}")


def check_knife_clip():
    skin = player_skin()
    clip = w.get_editor_property(KNIFE_ANIM_VAR)
    check(f"{KNIFE_ANIM_VAR} is A_KnifeSlash",
          clip is not None and clip == load(KNIFE_ANIM_PATH), str(clip))
    if clip is None:
        return
    worn = load(skin.mesh)
    check("...on the worn skeleton, or the slot would play nothing",
          clip.get_editor_property("skeleton") == worn.get_editor_property("skeleton"))
    check(f"...{FRAMES / FPS:.1f} s long, no longer than the knife's interval",
          abs(clip.get_play_length() - FRAMES / FPS) < 1e-3
          and clip.get_play_length() <= COMBAT.knife_interval_s + 1e-3,
          f"{clip.get_play_length():.3f}")
    src = load(HOLD_KNIFE_ANIM_PATH)
    arm = skin.pose_bones["upperarm_r"]
    lib = unreal.AnimationLibrary

    def turn(anim, t):
        return lib.get_bone_pose_for_time(anim, arm, t, False).rotation

    start = turn(clip, 0.0).angular_distance(turn(src, 0.0))
    end = turn(clip, clip.get_play_length()).angular_distance(turn(src, 0.0))
    check("...starting and ending in the ready pose",
          start < 1e-3 and end < 1e-3, f"{start:.4f} {end:.4f} rad")
    swing = turn(clip, SLASH_KEYS[1][0]).angular_distance(turn(clip, SLASH_KEYS[2][0]))
    check("...and the arm really swings between the wind-up and the cut (> 40 deg)",
          swing > 0.7, f"{swing:.2f} rad")
    check("...with the blow between the wind-up and the end of the cut",
          SLASH_KEYS[1][0] < COMBAT.knife_impact_s <= SLASH_KEYS[2][0],
          f"{COMBAT.knife_impact_s}")


def check_knife_loadout():
    got = w.get_editor_property("KnifeClass")
    check("KnifeClass points at BP_Knife_C",
          got is not None and got.get_name() == "BP_Knife_C", str(got))
    spawned = {_title(f) for n in by_pins(wg, "Class", "SpawnTransform")
               for f in _feeders(n, "Class")}
    check("BeginPlay spawns the shotgun, the pistol and the knife",
          {"Get ShotgunClass", "Get PistolClass", "Get KnifeClass"} <= spawned,
          str(sorted(spawned)))


def check_knife_press():
    melee = [n for n in wg if _title(n) == "Branch"
             and any(MELEE_VAR in out_pins(f) for f in _feeders(n, "Condition"))]
    # Three ask: the fire gate; the throw's ask, which picks a blade's sound or
    # a blunt thing's once the launch is stored (throw.py); and the slash's
    # Server event, which swings only a Melee item (punch.py). The gate is
    # the one that is neither.
    # The throw's sound picks a blade's or a blunt thing's on Fx_Throw's Sharp,
    # which the ask (the prediction) and the Server event (the tell) read off
    # Held.Melee (throw.py, verify/fx.py).
    thrown = [n for n in fxv.calls(FX.THROW) + fxv.predicts(FX.THROW)
              if any(MELEE_VAR in out_pins(f) for f in _feeders(n, FX.SHARP_PARAM))]
    slash = graph(wc).find_event_node(SERVER_SLASH)
    served = [n for n in melee if slash is not None
              and slash in [e for f in _feeders(n, "execute") for a in _feeders(f, "execute")
                            # ...past the guard's Allow and its Branch (verify/guard.py).
                            for b in _feeders(a, "execute") for e in _feeders(b, "execute")]]
    melee = [n for n in melee if n not in served]
    check("one Branch asks Held.Melee at the fire gate and one in the slash's Server "
          "event; the throw's tell and its prediction read it for the sound's Sharp",
          len(melee) == 1 and len(thrown) == 2 and len(served) == 1,
          f"{len(melee)} + {len(thrown)} + {len(served)}")
    if len(melee) != 1:
        return
    gate = melee[0]
    before = _feeders(gate, "execute")
    check("...on the Consumable test's False arm, inside the fire gate",
          len(before) == 1 and any("Consumable" in out_pins(f)
                                   for f in _feeders(before[0], "Condition")),
          str([_title(b) for b in before]))
    other = [PIN.get_owning_node(q) for q in
             PIN.list_connected_pins(BEL.find_else_pin(gate))]
    # ...by way of the matches' test (verify/light.py follows it from there).
    check("...and anything not Melee goes on towards the guns' ready gate",
          len(other) == 1 and f"Get {LIGHTS_VAR}" in
          {_title(x) for x in _feeds(BEL.find_input_pin(other[0], "Condition"))},
          str([_title(o) for o in other]))
    press = _exec_next(gate)
    names = ({_title(x) for x in _feeds(BEL.find_input_pin(press[0], "Condition"))}
             if len(press) == 1 else set())
    check("...then a tap off the knife's cooldown",
          f"Get {NEXT_KNIFE_VAR}" in names and "Get KeyFire" in names
          and not any("IsInputKeyDown" in t.replace(" ", "") for t in names),
          str(sorted(names)))
    after = _exec_next(press[0]) if len(press) == 1 else []
    check("...only queues the slash",
          [_title(a) for a in after] == [f"Set {KNIFE_QUEUED_VAR}"]
          and pin_value(after[0], KNIFE_QUEUED_VAR) == "true",
          str([_title(a) for a in after]))


def check_knife_swing():
    plays = [n for n in by_pins(wg, "Asset", "SlotNodeName") if is_knife_play(n)]
    check("one knife clip play, in its Fx_ event: the Server event's Multicast and "
          "the owning client's prediction both call it (verify/fx.py)",
          len(plays) == 1 and fxv.in_fx(FX.SLASH, plays) == plays, str(len(plays)))
    if len(plays) != 1:
        return
    check(f"...into {AIM_SLOT}, the upper-body slot, once",
          all(pin_value(p, "SlotNodeName") == AIM_SLOT
              and int(float(pin_value(p, "LoopCount"))) == 1 for p in plays))
    # The two callers: the server's tell, and the client's prediction.
    plays = fxv.calls(FX.SLASH) + fxv.predicts(FX.SLASH)

    def chain(node):
        """The Sets before a play, walked back along the exec chain."""
        seen = []
        for _ in range(6):
            prev = _feeders(node, "execute")
            if len(prev) != 1:
                break
            node = prev[0]
            seen.append(_title(node))
        return set(seen)

    served = [p for p in plays if f"Set {KNIFE_PENDING_VAR}" in chain(p)]
    mine = [p for p in plays if p not in served]
    check("...the Server event tells it (Multicast) and the Tick predicts it (Fx_): one "
          "call each", len(plays) == 2 and len(fxv.calls(FX.SLASH)) == 1
          and len(fxv.predicts(FX.SLASH)) == 1, str(len(plays)))
    stamps = {f"Set {v}" for v in (NEXT_KNIFE_VAR, KNIFE_DUE_VAR, KNIFE_PENDING_VAR)}
    check("...the server's after the cooldown, the blow's time and "
          "KnifePending are stamped; the client's after its own cooldown alone",
          len(served) == 1 and stamps <= chain(served[0]) and len(mine) == 1
          and chain(mine[0]) & stamps == {f"Set {NEXT_KNIFE_VAR}"},
          str([sorted(chain(p)) for p in plays]))
    delays = {num_pin(n, "B") for n in by_pins(wg, "A", "B")}
    check("...the cooldown and the blow's delay are COMBAT.knife_*",
          {COMBAT.knife_interval_s, COMBAT.knife_impact_s} <= delays)


def check_knife_blow():
    sweeps = [n for n in by_pins(wg, "Start", "End", "TraceChannel") if is_knife_sweep(n)]
    check("one knife sweep, of COMBAT.knife_radius_cm", len(sweeps) == 1, str(len(sweeps)))
    if len(sweeps) != 1:
        return
    gate = _feeders(sweeps[0], "execute")
    gate = _feeders(gate[0], "execute") if gate else []
    names = ({_title(x) for x in _feeds(BEL.find_input_pin(gate[0], "Condition"))}
             if gate else set())
    check("...swept only when KnifePending and KnifeDueTime has come",
          {f"Get {KNIFE_PENDING_VAR}", f"Get {KNIFE_DUE_VAR}"} <= names, str(sorted(names)))
    # What it takes is a variable, written before the health is: the strike's
    # damage, or more with a hot blade (verify/heat.py checks the more).
    writes = [n for n in take_hits(wg)
              if [_title(f) for f in _feeders(n, "Amount")] == [f"Get {BLOW_DAMAGE_VAR}"]]
    plain = [n for n in wg if _title(n) == f"Set {BLOW_DAMAGE_VAR}"
             and num_pin(n, BLOW_DAMAGE_VAR) == COMBAT.knife_damage]
    check(f"...and the body it meets loses {BLOW_DAMAGE_VAR}, which every blow "
          f"starts at {COMBAT.knife_damage:.0f} HP",
          len(writes) == 1 and len(plain) == 1
          and any("Cast" in _title(f) or "HealthComponent" in _title(f)
                  for f in _feeders(plain[0], "execute")),
          f"{len(writes)} TakeHit call(s), {len(plain)} start(s)")
    from_where = [n for n in writes
                  if any(is_knife_sweep(t) for b in _feeders(n, "From")
                         for t in _feeders(b, "Hit"))]
    check("...stamped like a pellet, down to which way the flinch goes",
          len(from_where) == 1, str(len(from_where)))


def run():
    check_knife_item()
    check_knife_clip()
    check_knife_loadout()
    check_knife_press()
    check_knife_swing()
    check_knife_blow()
