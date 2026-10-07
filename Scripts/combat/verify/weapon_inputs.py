"""verify.weapon_inputs -- BP_WeaponComponent basics: defaults, polled keys, sprint, ammunition,
reload and the dry-fire click.
"""

import unreal

from combat.anim_blueprint import AIM_SLOT, HIT_SLOT
from combat.camera import AIM_TRACE_RANGE
from combat.paths import PISTOL_BP_PATH, SHOTGUN_BP_PATH
from combat.slot_tuning import SLOT_KEYS, SLOT_VAR, UNPLACED
from combat.tuning import (
    BIND_VARS, COMBAT, DROP_FORWARD, PISTOL_MAGAZINE, SHOTGUN_MAGAZINE,
    SHOTGUN_RESERVE,
)
from combat.weapon_specs import _weapon_specs
from combat.shot_vars import AIM_PARAM, SERVER_FIRE
from combat.verify.fixtures import titles, w, wc, wg
from combat.verify.chop import is_chop_node
from combat.verify.light import is_light_trace
from combat.verify.knife import is_melee_play, is_melee_sweep
from combat.verify.throw import is_throw_play, is_throw_trace, launch_nodes
from combat.verify.throw_aim import is_ready_node
from combat.verify.common import (
    BEL, PIN, by_pins, cdo, check, graph, in_pins, load, out_pins, pin_value, shot_traces,
    titled,
)


# ─── The weapon component ────────────────────────────────────────────────────

def _after_detach(node, limit=12):
    """Whether a DetachFromActor runs before this node, on its exec chain."""
    seen, stack = set(), [node]
    while stack and len(seen) < limit:
        for q in PIN.list_connected_pins(BEL.find_input_pin(stack.pop(), "execute")):
            n = PIN.get_owning_node(q)
            if "detach" in str(BEL.get_node_title(n)).lower():
                return True
            if n not in seen:
                seen.add(n)
                stack.append(n)
    return False


def check_weapon_component():
    check("tick group is PostPhysics, so input is already processed",
          w.get_editor_property("primary_component_tick").get_editor_property("tick_group")
          == unreal.TickingGroup.TG_POST_PHYSICS)

    for var, want in (("ShotgunClass", "BP_Shotgun_C"),
                      ("PistolClass", "BP_Pistol_C"),
                      ("ItemClass", "BP_WeaponItem_C"),
                      ("BloodClass", "BP_BloodSplash_C")):
        got = w.get_editor_property(var)
        check(f"{var} points at {want}", got is not None and got.get_name() == want,
              got.get_name() if got else "None")


# ─── The keys, and the fact that not one of them is a literal ────────────────

def check_keys_are_variables():
    # Every Key pin in this graph is DRIVEN by a member variable, which is the
    # whole of rebinding: the HUD writes those variables every DrawHUD frame from
    # the player's save, and a pin literal cannot be written to. A pin that went
    # back to a literal would compile, save, and simply ignore the settings screen
    # for ever -- so the assertion is on the wiring, not on the value.
    polls = by_pins(wg, "self", "Key")
    literal = [pin_value(n, "Key") for n in polls if pin_value(n, "Key")]
    check("no key is polled as a pin literal any more", not literal, str(literal))
    driven = []
    for n in polls:
        src = PIN.list_connected_pins(BEL.find_input_pin(n, "Key"))
        driven += [str(BEL.get_node_title(PIN.get_owning_node(q))).replace("\n", " ")
                   for q in src]
    # The fire key appears TWICE and that is the whole of automatic fire: once as
    # WasInputKeyJustPressed (a tap) and once as IsInputKeyDown (a hold). Sprint
    # and aim are the other two held keys.
    # And the slots' number keys (slot_tuning.SLOT_KEYS), fixed rather than
    # bound, but variables all the same.
    want_keys = sorted([f"Get {v}" for v, _k in BIND_VARS] + ["Get KeyFire"]
                       + [f"Get {v}" for v, _k, _s in SLOT_KEYS])
    check(f"polls exactly {want_keys}", sorted(driven) == want_keys, str(sorted(driven)))
    # One Get per bind, reused by every poll -- an output pin takes any number of
    # links, so eight polls come off seven reads.
    reads = [n for n in wg
             if str(BEL.get_node_title(n)).replace("\n", " ")
             in {f"Get {v}" for v, _k in BIND_VARS}]
    check("one read per bind, shared by the polls that use it",
          len(reads) == len(BIND_VARS), str(len(reads)))
    for var, default in BIND_VARS + tuple((v, k) for v, k, _s in SLOT_KEYS):
        got = w.get_editor_property(var)
        check(f"{var} defaults to {default}, the key this file documents",
              got is not None and got.export_text() == default,
              got.export_text() if got is not None else "None")

    # The punch's, the knife's and the throw's clips, and the throw's ready
    # pose, are their own sections' (verify/punch.py, knife.py, throw.py,
    # throw_aim.py).
    # A play has a rate; IsPlayingSlotAnimation has an Asset and a slot too.
    plays = [n for n in by_pins(wg, "Asset", "SlotNodeName", "InPlayRate")
             if not is_melee_play(n) and not is_throw_play(n)
             and not is_ready_node(n)]
    # TWO, and the second one is not a duplicate. A montage started in HitSlot stops
    # the ready pose in DefaultSlot -- montages are stopped per GROUP and UE 5.8
    # exposes no way to put a slot in a different group from Python -- so the flinch
    # costs the aim pose, and the keepalive in Tick is what puts it back on the
    # first frame after the stagger. Measured before it existed: DefaultSlot sat at
    # weight 1.000 until the first punch landed and read 0.000 for the rest of the
    # session.
    check("the ready pose is played into a slot twice: on equip, and again after a "
          "hit reaction has taken it away", len(plays) == 2, str(len(plays)))
    for i, play in enumerate(plays):
        check(f"ready-pose play {i} goes into {AIM_SLOT}",
              pin_value(play, "SlotNodeName") == AIM_SLOT,
              pin_value(play, "SlotNodeName"))
        check(f"ready-pose play {i} loops rather than playing once",
              int(float(pin_value(play, "LoopCount"))) >= 100,
              pin_value(play, "LoopCount"))
    check("empty hands stop the slot", bool(by_pins(wg, "InBlendOutTime", "SlotNodeName")))

    # The keepalive's two guards. Without the HitSlot one it restarts the ready pose
    # on the frame the flinch begins, the restart stops the flinch (same group), and
    # the reaction is one frame of twitch.
    _slot_tests = {pin_value(n, "SlotNodeName")
                   for n in wg
                   if str(BEL.get_node_title(n)).replace("\n", " ").startswith("Is Slot Active")
                   or "IsSlotActive" in str(BEL.get_node_title(n)).replace(" ", "")}
    check(f"the keepalive asks whether {AIM_SLOT} and {HIT_SLOT} are quiet "
          f"before it replays the pose",
          {AIM_SLOT, HIT_SLOT} <= _slot_tests, str(sorted(_slot_tests)))

    # The hybrid aim, which is the whole point of the trace layout: the camera line
    # decides what is being aimed at, the muzzle line decides whether the gun can
    # reach it, and the pellets fly down the muzzle line. Getting this wrong is not
    # a compile error -- it is a gun that shoots from behind the player's shoulder.
    traces = [n for n in by_pins(wg, "Start", "End", "TraceChannel") + shot_traces(wg)
              if not is_melee_sweep(n) and not is_throw_trace(n)
              and not is_chop_node(n) and not is_light_trace(n)]
    check("there are four traces (camera aim, muzzle clearance, the pellets' ShotTrace "
          "and the one that sets a dropped item on the ground: the drop key's and "
          "the dragged drop's are one, the server's)",
          len(traces) == 4, str(len(traces)))




    from_muzzle, from_camera = [], []
    for t in traces:
        feeders = [PIN.get_owning_node(q) for q in
                   PIN.list_connected_pins(BEL.find_input_pin(t, "Start"))]
        for n in feeders:
            # The muzzle comes through the carry's SelectVector (verify/carry.py):
            # its B is the muzzle, its A where the muzzle will be once raised.
            if {"A", "B", "bPickA"} <= in_pins(n) and all(
                    {"T", "Location"} <= in_pins(PIN.get_owning_node(q))  # TransformLocation
                    for side in ("A", "B")
                    for q in PIN.list_connected_pins(BEL.find_input_pin(n, side))):
                from_muzzle.append(t)
            if str(BEL.get_node_title(n)) == "GetCameraLocation":
                from_camera.append(t)
    check("two traces start at the weapon's muzzle: the clearance check and the pellets",
          len(from_muzzle) == 2, f"{len(from_muzzle)} fed by the carry's pick of two TransformLocations")
    check("exactly one trace starts at the camera -- the one that picks the target",
          len(from_camera) == 1, f"{len(from_camera)} fed by GetCameraLocation")
    # Built as a MakeVector, not as a pin literal: that operator's B pin is a
    # struct pin when nothing is connected, and struct pins take no literal at all.
    check("the camera's ray reaches AIM_TRACE_RANGE when it hits nothing",
          any(all(abs(float(pin_value(n, axis) or 0) - AIM_TRACE_RANGE) < 1e-3
                  for axis in "XYZ")
              for n in titled(wg, "MakeVector")),
          f"{AIM_TRACE_RANGE:.0f} cm")
    check("a dropped weapon lands in front of the player, not on their feet",
          any(all(abs(float(pin_value(n, axis) or 0) - DROP_FORWARD) < 1e-3
                  for axis in "XYZ")
              for n in titled(wg, "MakeVector")),
          f"{DROP_FORWARD:.0f} cm ahead")
    # One subtraction off the shooter's AimPoint: the pellet direction, taken
    # from Server_Fire's own parameter (shot.py), since the shot is traced by
    # the machine that owns it. (The throw's launch takes its own, from the
    # variable: verify/throw_aim.py.)
    throw_launch = launch_nodes()
    fire_event = graph(wc).find_event_node(SERVER_FIRE)
    deltas = [n for n in titled(wg, "vector - vector")
              if n not in throw_launch
              and any(PIN.get_owning_node(q) == fire_event
                      and str(PIN.get_pin_name(q)) == AIM_PARAM
                      for q in PIN.list_connected_pins(BEL.find_input_pin(n, "A")))]
    check("the pellet direction is muzzle -> the AimPoint the shooter sent, not camera "
          "forward", len(deltas) == 1,
          f"{len(deltas)} vector subtractions driven by {SERVER_FIRE}'s {AIM_PARAM}")

    # A held weapon is rigidly attached and never rotated on its own. Driving its
    # rotation from the aim was tried and reverted: the gun swivelled out of the
    # hand and spun a full turn as the camera came round.
    # The one turn there is comes after the hand has let go: the throw's
    # release detaches a melee weapon, then squares it up to the throw
    # (throw_flight._author_square).
    turns = titled(wg, "Set Actor Rotation")
    held_turns = [n for n in turns if not _after_detach(n)]
    check("nothing rotates the held weapon in the hand: the only turn is the "
          "throw's, after the item is detached",
          len(turns) <= 1 and not held_turns,
          f"{len(turns)} SetActorRotation node(s), {len(held_turns)} not after a detach")
    # No trace draws itself any more: DrawDebugType is an enum literal on the pin
    # and an enum pin cannot be driven, so "only in debug mode" is inexpressible
    # there. The tracer is a DrawDebugLine behind a Branch instead.
    drawn = [t for t in traces if "ForDuration" in pin_value(t, "DrawDebugType")]
    check("no trace draws itself -- the tracer is conditional and a pin literal is not",
          not drawn, f"{len(drawn)} drawn")

    for var, kind in (("AimPoint", unreal.Vector), ("AimValid", bool),
                      ("AimBlocked", bool)):
        value = w.get_editor_property(var)
        check(f"{var} exists on the weapon component for the HUD to read",
              isinstance(value, kind), type(value).__name__)

    # The guns' three, and the component's own (Sound/sound_weapons.py, sound_items.py):
    # a swing for the punch and one for the blade, the axe on a tree, a match.
    #   3  the shot, the click, the reload
    #   2  a swing: the fist's and the blade's, each once, in its Fx_ event
    #      (the Server event's Multicast and the owning client's prediction
    #      both call it: verify/fx.py)
    #   2  a blow landing on a body: the fist's and the blade's
    #   1  the axe's chop in a tree
    #   4  a throw: leaving the hand (a blade's, and a blunt thing's), sinking
    #      into a body, lodging in a tree
    #   1  the match
    #   5  the axe's kill by the head, the breath of a spent sprint, an item
    #      handled (where the server serves the move, and where a client's
    #      picture follows it: view.py) and an item used up
    #      (verify/sound_states.py)
    check("the component plays eighteen sounds: the guns' three, a swing and "
          "a landed blow for the fist and for the blade, the chop, a throw's "
          "four, the match, a thrown axe's kill by the head, the breath, an "
          "item handled (the server's serve, a client's picture) and an item used up",
          len(by_pins(wg, "Sound", "Location")) == 18,
          f"{len(by_pins(wg, 'Sound', 'Location'))} PlaySoundAtLocation node(s)")
    check("impacts spawn blood", len(by_pins(wg, "Class", "SpawnTransform")) >= 3,
          f"{len(by_pins(wg, 'Class', 'SpawnTransform'))} spawn nodes "
          "(shotgun, pistol, blood)")
    check("damage is clamped at zero", bool(by_pins(wg, "Value", "Min", "Max")))
    check("switching wraps with a modulo", bool(by_pins(wg, "A", "B")))
    check("interact searches the world for items to pick up", bool(by_pins(wg, "ActorClass")))
    _check_pickup_keeps_held()
    check("dropping detaches the weapon",
          bool(by_pins(wg, "LocationRule", "RotationRule", "ScaleRule")))

    probes = [n for n in wg if "InString" in in_pins(n)]
    check("no leftover debug PrintStrings", not probes, f"{len(probes)} found")


def _linked(node, pin_name):
    """The nodes on the far side of one of ``node``'s output pins."""
    return [PIN.get_owning_node(q)
            for q in PIN.list_connected_pins(BEL.find_output_pin(node, pin_name))]


def _check_pickup_keeps_held():
    """A pick-up joins the inventory without switching to it: the item it
    adds is set UNPLACED, for the slot sync to put in the bag (or in empty
    hands, with the bag full), and no Array_Add feeds EquippedIndex.
    """
    adds = by_pins(wg, "TargetArray", "NewItem")
    straight = [n for a in adds for n in _linked(a, "ReturnValue")
                if "EquippedIndex" in str(BEL.get_node_title(n))]
    check("pick-up does not switch straight to what it picked up",
          not straight, f"{len(straight)} EquippedIndex write(s) fed by Array_Add")
    placed = [n for a in adds for n in _linked(a, "then")
              if str(BEL.get_node_title(n)).replace("\n", " ").startswith(f"Set {SLOT_VAR}")
              and pin_value(n, SLOT_VAR) == str(UNPLACED)]
    check("...it is set UNPLACED: the slot sync finds it a weapon slot, a bag slot, or the hand",
          len(placed) == 1, f"{len(placed)} Set {SLOT_VAR} = {UNPLACED} after an add")


# ─── Sprint and stamina ──────────────────────────────────────────────────────

def check_sprint_and_stamina():
    for var, kind, want in (("Stamina", float, COMBAT.max_stamina),
                            ("MaxStamina", float, COMBAT.max_stamina),
                            ("Sprinting", bool, False)):
        value = w.get_editor_property(var)
        check(f"{var} starts at {want!r}",
              isinstance(value, kind)
              and (value == want if kind is bool else abs(value - want) < 1e-6),
              f"{type(value).__name__} = {value}")
    check("BaseSpeed is a float, not an int",
          isinstance(w.get_editor_property("BaseSpeed"), float),
          type(w.get_editor_property("BaseSpeed")).__name__)
    sprint_polls = [n for n in wg
                    if in_pins(n) == {"self", "Key"}
                    and any("Get KeySprint" in
                            str(BEL.get_node_title(PIN.get_owning_node(q)))
                            for q in PIN.list_connected_pins(
                                BEL.find_input_pin(n, "Key")))]
    check("the sprint bind is polled as held, not as a tap",
          bool(sprint_polls)
          and all("IsInputKeyDown" in str(BEL.get_node_title(n))
                  for n in sprint_polls),
          str([str(BEL.get_node_title(n)) for n in sprint_polls]))
    walk_titles = {t for t in (str(BEL.get_node_title(n)).replace("\n", " ")
                               for n in wg) if "MaxWalkSpeed" in t}
    # The speed is the movement component's now (verify/movement.py): a write
    # from this graph would exist on one machine only.
    check("sprinting writes no walk speed from the graph",
          not any(t.startswith("SET") or t.startswith("Set") for t in walk_titles),
          str(sorted(walk_titles)))
    # Cached, never written down: a literal walk speed here would fight any later
    # change to the character's movement defaults, and only after the first sprint.
    check("the walking speed is cached off the character, not hardcoded",
          any(t.startswith("Get") for t in walk_titles)
          and any("BaseSpeed" in str(BEL.get_node_title(n)).replace("\n", " ")
                  for n in wg),
          str(sorted(walk_titles)))
    # The hit-box multiplier has two SelectFloats of its own, each picked by a
    # table lookup; those are counted in the hit-box section, not here. So are
    # the stance's, each picked by comparing Stance (verify/stance.py), the
    # side the chopped wood lands on (verify/chop.py), and the throw's yaw
    # and pitch (verify/throw_aim.py), and the held breath's, picked by
    # BreathHeld and Winded (verify/breath.py).
    throw_launch = launch_nodes()
    selects = [n for n in titled(wg, "SelectFloat")
               if not is_chop_node(n) and n not in throw_launch and not any(k in str(BEL.get_node_title(PIN.get_owning_node(q)))
                          for k in ("Contains", "Equal", "Get BreathHeld", "Get Winded")
                          for q in PIN.list_connected_pins(BEL.find_input_pin(n, "bPickA")))]
    # Five: the sights key picks the zoom (the weapon's, or the shoulder's),
    # and accuracy.py picks the shoulder's and the sights' factor for the
    # cloud and the kick. (The sprint's two, the speed and the sign of the
    # drain, went into the movement component with the sprint.)
    check("SelectFloat picks the aimed zoom, and the shoulder and sights "
          "factors of the cloud and the kick",
          len(selects) == 5,
          f"{len(selects)} SelectFloat node(s)")
    # The requirement the flag exists for: you cannot shoot while running.
    sprint_reads = [n for n in wg if "Sprinting" in out_pins(n)]
    check("the trigger reads Sprinting", bool(sprint_reads),
          f"{len(sprint_reads)} reads")
    negated = [n for n in sprint_reads
               if any("NOT" in str(BEL.get_node_title(PIN.get_owning_node(q))).upper()
                      for q in BEL.find_output_pin(n, "Sprinting").list_connected_pins())]
    check("...through a NOT, so firing is refused while it is set", bool(negated),
          str([str(BEL.get_node_title(PIN.get_owning_node(q)))
               for n in sprint_reads
               for q in BEL.find_output_pin(n, "Sprinting").list_connected_pins()]))


# ─── Ammunition, the cooldown and the reload ─────────────────────────────────

def check_ammunition():
    # The requirement in one line: the shotgun is limited, the pistol is not. Every
    # check here is about the difference between those two being *data* -- a row in
    # _weapon_specs -- rather than a branch on the weapon's name somewhere.

    for want in _weapon_specs():
        spec = want["display"]
        gun = cdo(load(want["path"]))
        check(f"{spec}: UsesAmmo is {want['uses_ammo']}",
              gun.get_editor_property("UsesAmmo") == want["uses_ammo"],
              str(gun.get_editor_property("UsesAmmo")))
        check(f"{spec}: it starts loaded, not empty",
              gun.get_editor_property("Loaded")
              == gun.get_editor_property("MagazineSize") == want["magazine"],
              f"{gun.get_editor_property('Loaded')} / "
              f"{gun.get_editor_property('MagazineSize')}")
        endless = bool(want.get("infinite_reserve", False))
        check(f"{spec}: InfiniteReserve is {endless}",
              gun.get_editor_property("InfiniteReserve") is endless,
              str(gun.get_editor_property("InfiniteReserve")))
        check(f"{spec}: reserve is {want['reserve']}",
              gun.get_editor_property("Reserve") == want["reserve"],
              str(gun.get_editor_property("Reserve")))
        check(f"{spec}: there is a pause between shots",
              abs(gun.get_editor_property("FireInterval") - want["interval"]) < 1e-6,
              f"{gun.get_editor_property('FireInterval'):.2f}s")
        check(f"{spec}: the first shot of a session is free",
              gun.get_editor_property("NextFireTime") == 0.0,
              str(gun.get_editor_property("NextFireTime")))
        check(f"{spec}: reloading takes {want['reload_s']}s",
              abs(gun.get_editor_property("ReloadSeconds") - want["reload_s"]) < 1e-6,
              f"{gun.get_editor_property('ReloadSeconds'):.2f}s")

    shotgun_cdo = cdo(load(SHOTGUN_BP_PATH))
    check(f"the shotgun starts with {SHOTGUN_MAGAZINE + SHOTGUN_RESERVE} shells "
          f"in total -- {SHOTGUN_MAGAZINE} loaded and {SHOTGUN_RESERVE} spare",
          shotgun_cdo.get_editor_property("Loaded")
          + shotgun_cdo.get_editor_property("Reserve") == 20,
          str(shotgun_cdo.get_editor_property("Loaded")
              + shotgun_cdo.get_editor_property("Reserve")))
    # 2x what it was. The pellet count is unchanged, so this is the whole change:
    # 8 x 18 = 144 against a 100 HP wanderer, i.e. one connected shot is a kill.
    check("the shotgun does twice the damage it used to (9 -> 18 per pellet)",
          abs(shotgun_cdo.get_editor_property("Damage") - 18.0) < 1e-6,
          str(shotgun_cdo.get_editor_property("Damage")))
    check("...and still fires the same 8 pellets, so the change is damage and not spread",
          shotgun_cdo.get_editor_property("PelletCount") == 8,
          str(shotgun_cdo.get_editor_property("PelletCount")))
    # The fallback weapon: a magazine to reload, over a reserve that never ends.
    pistol = cdo(load(PISTOL_BP_PATH))
    check(f"the pistol reloads every {PISTOL_MAGAZINE} shots",
          pistol.get_editor_property("UsesAmmo") is True
          and pistol.get_editor_property("MagazineSize") == PISTOL_MAGAZINE == 8,
          f"UsesAmmo {pistol.get_editor_property('UsesAmmo')}, "
          f"magazine {pistol.get_editor_property('MagazineSize')}")
    check("...over an infinite reserve, so it can never run dry for good",
          pistol.get_editor_property("InfiniteReserve") is True)
    check("...and the reload costs it a pause like any other gun",
          pistol.get_editor_property("ReloadSeconds") > 0.0,
          f"{pistol.get_editor_property('ReloadSeconds'):.2f}s")


# --- what the graph does with all that ---------------------------------------

def check_ammunition_graph():
    loaded_writes = [t for t in (str(BEL.get_node_title(n)).replace("\n", " ")
                                 for n in wg) if t == "Set Loaded"]
    # The server's shot, the owning client's predicted round (shot.py), the
    # reload, and a client's picture of the server's record (view.py).
    check("firing spends a round, on the server and as the owning client's "
          "prediction, and reloading puts rounds back (and a client's picture takes "
          "the record's)",
          len(loaded_writes) == 4, f"{len(loaded_writes)} writes to Loaded")
    next_writes = [t for t in (str(BEL.get_node_title(n)).replace("\n", " ")
                               for n in wg) if t == "Set NextFireTime"]
    check("the interval (the server's, and the owning client's predicted one) and the "
          "reload push the same NextFireTime deadline",
          len(next_writes) == 3, f"{len(next_writes)} writes to NextFireTime")
    check("the deadline is compared against the clock, not a frame count",
          bool(titled(wg, "GetTimeSeconds")),
          f"{len(titled(wg, 'GetTimeSeconds'))} GetTimeSeconds")
    # The reserve is only ever *spent* here; it is topped up by BP_AmmoPickup.
    check("the weapon component spends the reserve and never grants it (its other "
          "write is a client's picture of the record)",
          len([t for t in (str(BEL.get_node_title(n)).replace("\n", " ")
                           for n in wg) if t == "Set Reserve"]) == 2)
    # The pure-node trap, in the one place where getting it wrong is free ammo.
    check("the reload works out how many rounds move ONCE and stores it",
          len([t for t in (str(BEL.get_node_title(n)).replace("\n", " ")
                           for n in wg) if t == "Set ReloadTake"]) == 1)
    check("...and reads it back three times rather than recomputing it",
          len([n for n in wg if "ReloadTake" in out_pins(n)]) == 3,
          f"{len([n for n in wg if 'ReloadTake' in out_pins(n)])} reads")
    check("the reload can never take more than the reserve holds",
          bool(titled(wg, "Min (Integer)")),
          str(sorted({t for t in (str(BEL.get_node_title(n)).replace("\n", " ")
                                  for n in wg) if t.lower().startswith("min")})))
    # The pistol's reload: the gap stands in for its reserve (so the magazine
    # fills even from a negative count), and the reserve is written back as is.
    endless_reads = [n for n in wg if "InfiniteReserve" in out_pins(n)]
    check("the reload asks InfiniteReserve twice: what it may take, what it is charged",
          len(endless_reads) == 2, f"{len(endless_reads)} InfiniteReserve reads")
    selects = [n for n in wg if {"A", "B", "bPickA"} <= in_pins(n)]
    check("...each through a Select, not a branch around the reload",
          len(selects) >= 2, f"{len(selects)} Select nodes")
    # The gate is nested, not folded: every one of these reads a property off Held,
    # and the outer condition is pulled on frames where nothing is equipped.
    ammo_reads = [n for n in wg if "UsesAmmo" in out_pins(n)]
    check("the fire gate, the server's own test of the shot and the reload each ask "
          "the weapon whether it uses ammo",
          len(ammo_reads) == 3, f"{len(ammo_reads)} UsesAmmo reads")
    check("an unlimited weapon short-circuits the magazine test (an OR, not an AND)",
          bool(titled(wg, "OR Boolean")),
          str(sorted({t for t in (str(BEL.get_node_title(n)).replace("\n", " ")
                                  for n in wg) if " OR" in t.upper()})))


# ─── The click and the clack ─────────────────────────────────────────────────

def check_click_and_clack():
    # Two sounds whose whole value is *when* they do not play. A click on every
    # refused trigger pull would fire on the SMG's every-0.09s cooldown; a clack on
    # every R would reward pressing reload at a full magazine.

    check("the empty chamber clicks",
          titles.count("Get DryFireSound") == 1,
          f"{titles.count('Get DryFireSound')} reads of DryFireSound")
    check("the reload clacks",
          titles.count("Get ReloadSound") == 1,
          f"{titles.count('Get ReloadSound')} reads of ReloadSound")
    dry = [n for n in by_pins(wg, "Sound", "Location")
           if any("DryFireSound" in str(BEL.get_node_title(PIN.get_owning_node(q)))
                  for q in PIN.list_connected_pins(BEL.find_input_pin(n, "Sound")))]
    check("exactly one node plays the click", len(dry) == 1, f"{len(dry)}")
    if dry:
        # The gate above it must be an AND, not a bare NOT: "empty" alone would
        # click through every cooldown frame of a held trigger.
        ins = BEL.find_input_pin(dry[0], "execute")
        gate = [PIN.get_owning_node(q) for q in PIN.list_connected_pins(ins)]
        cond = ([PIN.get_owning_node(q)
                 for q in PIN.list_connected_pins(
                     BEL.find_input_pin(gate[0], "Condition"))] if gate else [])
        check("...behind a Branch whose condition is an AND of two things, so it "
              "stays silent between shots as well as when loaded",
              bool(cond) and "AND" in str(BEL.get_node_title(cond[0])).upper(),
              str([str(BEL.get_node_title(n)) for n in cond]))
        # And one of the two has to be the negation of the ammunition test.
        nots = [t for t in titles if "NOT" in t.upper() and "Boolean" in t]
        check("...one half of which is \"has no ammunition\"", len(nots) >= 3,
              f"{len(nots)} NOT nodes (unlimited-weapon, not-sprinting, empty, pose)")


def run():
    check_weapon_component()
    check_keys_are_variables()
    check_sprint_and_stamina()
    check_ammunition()
    check_ammunition_graph()
    check_click_and_clack()
