"""verify.weapon_inputs -- BP_WeaponComponent basics: defaults, polled keys, the
traces, sprint, and each gun's ammunition defaults. What the graph does with
the ammunition, and the dry-fire click, is verify/ammo_graph.py.
"""

import unreal

from combat.anim_blueprint import AIM_SLOT, HIT_SLOT
from combat.camera import AIM_TRACE_RANGE
from combat.paths import PISTOL_BP_PATH, SHOTGUN_BP_PATH
from combat.slot_tuning import DROP_ITEM_VAR, SLOT_KEYS, SLOT_VAR, UNPLACED
from combat.tuning import (
    BIND_VARS, COMBAT, DROP_FORWARD, PISTOL_MAGAZINE, SHOTGUN_MAGAZINE,
    SHOTGUN_RESERVE,
)
from combat.weapon_specs import _weapon_specs
from combat.shot_vars import AIM_PARAM, SHOT_FIRED
from combat.strike_vars import SERVER_TAKE
from combat.verify.anchor import (
    event, event_nodes, feeders, pure_feeds, reads, title,
)
from combat.verify.fixtures import w, wg
from combat.verify.common import (
    BEL, PIN, by_pins, cdo, check, in_pins, load, out_pins, past_marks, pellet_calls,
    pin_value, titled,
)
from combat.weapon_component import vars as WV
from combat.weapon_component.look_vars import HandPose


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
    for var, default in BIND_VARS + tuple((v, k) for v, k, _s in SLOT_KEYS):
        got = w.get_editor_property(var)
        check(f"{var} defaults to {default}, the key this file documents",
              got is not None and got.export_text() == default,
              got.export_text() if got is not None else "None")

    # The punch's, the knife's and the throw's clips, and the throw's ready
    # pose, are their own sections' (verify/punch.py, knife.py, throw.py,
    # throw_aim.py).
    # A play has a rate; IsPlayingSlotAnimation has an Asset and a slot too.
    # The ready pose's plays are the ones handed HandPose, each behind its own
    # gate: the keepalive's asks the slots, the equip's does not.
    plays = [n for n in by_pins(wg, "Asset", "SlotNodeName", "InPlayRate")
             if [title(f) for f in feeders(n, "Asset")] == [f"Get {HandPose}"]]
    keepalive = [n for n in plays
                 if any("IsSlotActive" in t.replace(" ", "")
                        for g in feeders(n, "execute") for t in reads(g))]
    equip = [n for n in plays if n not in keepalive]
    # TWO, and the second one is not a duplicate. A montage started in HitSlot stops
    # the ready pose in DefaultSlot -- montages are stopped per GROUP and UE 5.8
    # exposes no way to put a slot in a different group from Python -- so the flinch
    # costs the aim pose, and the keepalive in Tick is what puts it back on the
    # first frame after the stagger. Measured before it existed: DefaultSlot sat at
    # weight 1.000 until the first punch landed and read 0.000 for the rest of the
    # session.
    check("the ready pose is played into a slot twice: on equip, and again after a "
          "hit reaction has taken it away", bool(equip) and bool(keepalive),
          f"{len(equip)} on equip, {len(keepalive)} behind the slots' test")
    for name, group in (("the equip's", equip), ("the keepalive's", keepalive)):
        check(f"{name} ready-pose play goes into {AIM_SLOT}",
              bool(group) and all(pin_value(n, "SlotNodeName") == AIM_SLOT for n in group),
              str([pin_value(n, "SlotNodeName") for n in group]))
        check(f"{name} ready-pose play loops rather than playing once",
              bool(group) and all(int(float(pin_value(n, "LoopCount"))) >= 100
                                  for n in group),
              str([pin_value(n, "LoopCount") for n in group]))
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
    # Each trace is found where its fragment puts it, not by how many the
    # graph holds: the aim's by the camera it starts at, the clearance by the
    # AimPoint it ends on, the drop's behind the item being let go. The
    # pellets' are the native base's (FirePellets, C++), called under ShotFired.
    lines = by_pins(wg, "Start", "End", "TraceChannel")
    aim = [t for t in lines
           if any(title(f) == "GetCameraLocation" for f in feeders(t, "Start"))]
    clearance = [t for t in lines
                 if [title(f) for f in feeders(t, "End")] == [f"Get {AIM_PARAM}"]]
    pellets = pellet_calls(event_nodes(SHOT_FIRED))
    drop = [t for t in lines
            if any(title(f) == f"Get {DROP_ITEM_VAR}"
                   for b in feeders(t, "execute") for f in feeders(b, "self"))]
    traces = aim + clearance + pellets + drop
    check("there are four traces (camera aim, muzzle clearance, the pellets' in the "
          "native FirePellets and the one that sets a dropped item on the ground: the "
          "drop key's and the dragged drop's are one, the server's)",
          all((aim, clearance, pellets, drop)),
          f"aim {len(aim)}, clearance {len(clearance)}, pellets {len(pellets)}, "
          f"drop {len(drop)}")

    def _from_muzzle(t, pin):
        # The muzzle comes through the carry's SelectVector (verify/carry.py):
        # its B is the muzzle, its A where the muzzle will be once raised.
        return any({"A", "B", "bPickA"} <= in_pins(n) and all(
            {"T", "Location"} <= in_pins(f)  # TransformLocation
            for side in ("A", "B") for f in feeders(n, side))
            for n in feeders(t, pin))

    check("two traces start at the weapon's muzzle: the clearance check and the pellets",
          bool(clearance) and bool(pellets)
          and all(_from_muzzle(t, "Start") for t in clearance)
          and all(_from_muzzle(t, "Muzzle") for t in pellets),
          str([title(f) for t in clearance for f in feeders(t, "Start")]
              + [title(f) for t in pellets for f in feeders(t, "Muzzle")]))
    check("exactly one trace starts at the camera -- the one that picks the target",
          bool(aim) and not [t for t in clearance + pellets + drop if t in aim],
          str([title(f) for t in clearance + drop for f in feeders(t, "Start")]))
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
    # The pellets fly around ShotDirection, which ShotFired draws once
    # around a subtraction off the shooter's AimPoint, its own parameter
    # (shot.py), since the shot is traced by the machine that owns it. (The
    # throw's launch takes its own, from the variable: verify/throw_aim.py.)
    fire_event = event(SHOT_FIRED)
    drawn = [n for n in event_nodes(SHOT_FIRED) if title(n) == f"Set {WV.ShotDirection}"]
    deltas = [n for d in drawn for n in pure_feeds(d)
              if title(n) == "vector - vector"
              and any(PIN.get_owning_node(q) == fire_event
                      and str(PIN.get_pin_name(q)) == AIM_PARAM
                      for q in PIN.list_connected_pins(BEL.find_input_pin(n, "A")))]
    check("the pellet direction is muzzle -> the AimPoint the shooter sent, not camera "
          "forward",
          bool(deltas) and bool(pellets)
          and all([title(f) for f in feeders(t, "Direction")] == [f"Get {WV.ShotDirection}"]
                  for t in pellets),
          f"{len(deltas)} vector subtractions driven by {SHOT_FIRED}'s {AIM_PARAM} "
          f"behind {WV.ShotDirection}, which the pellets' Direction reads")

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
          not held_turns,
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

    # Which sounds there are is each section's own to say (the guns' three in
    # the click and the clack below, a swing's and a blow's in verify/fx.py, an
    # item's in verify/sound_states.py). What holds of every one of them: it is
    # read off a variable (Sound/sound_weapons.py, sound_items.py), since a
    # sound left as a pin literal is one build_sound.py cannot rebind.
    sounds = by_pins(wg, "Sound", "Location")
    unbound = [n for n in sounds if not feeders(n, "Sound")]
    check("every sound the component plays is read off a variable, none a pin "
          "literal: the guns' three, a swing and a landed blow for the fist and for "
          "the blade, the chop, a throw's four, the match, a thrown axe's kill by "
          "the head, the breath, an item handled and an item used up",
          bool(sounds) and not unbound,
          f"{len(unbound)} of {len(sounds)} PlaySoundAtLocation node(s) with no "
          "Sound linked")
    blood = [n for n in by_pins(wg, "Class", "SpawnTransform")
             if [title(f) for f in feeders(n, "Class")] == ["Get BloodClass"]]
    check("impacts spawn blood", bool(blood),
          f"{len(blood)} spawn node(s) handed BloodClass")
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
    # The pick-up is Server_Take's add to Inventory (item_world.py).
    takes = [a for a in by_pins(event_nodes(SERVER_TAKE), "TargetArray", "NewItem")
             if [title(f) for f in feeders(a, "TargetArray")] == ["Get Inventory"]]
    placed = [n for a in takes for n in past_marks(_linked(a, "then"))
              if title(n).startswith(f"Set {SLOT_VAR}")
              and pin_value(n, SLOT_VAR) == str(UNPLACED)]
    check("...it is set UNPLACED: the slot sync finds it a weapon slot, a bag slot, or the hand",
          bool(takes) and bool(placed),
          f"{len(takes)} add(s) to Inventory under {SERVER_TAKE}, {len(placed)} followed "
          f"by Set {SLOT_VAR} = {UNPLACED}")


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
    # The graph has many SelectFloats (the hit boxes', the stance's, the
    # chop's, the throw's, the held breath's: each its own section's). These
    # are found by what they feed and what picks them: the zoom's feeds
    # AimZoom, picked by the sights key; accuracy.py's shoulder factor of the
    # cloud and of the kick is picked by Aiming and handed on to the sights'
    # pick. (The sprint's two, the speed and the sign of the drain, went into
    # the movement component with the sprint.)
    def _picked_by(n, what):
        return any(what in title(f) for f in feeders(n, "bPickA"))

    zoom = [f for n in wg if title(n) == "Set AimZoom"
            for f in feeders(n, "AimZoom") if title(f) == "SelectFloat"]
    factors = {}
    for kind in ("Spread", "Recoil"):
        shoulder = [n for n in titled(wg, "SelectFloat")
                    if [title(f) for f in feeders(n, "A")] == [f"Get {kind}ShoulderScale"]]
        factors[kind] = [c for n in shoulder if _picked_by(n, "Get Aiming")
                         for c in _linked(n, "ReturnValue")
                         if title(c) == "SelectFloat" and _picked_by(c, "Get SightAiming")]
    check("SelectFloat picks the aimed zoom, and the shoulder and sights "
          "factors of the cloud and the kick",
          bool(zoom) and all(_picked_by(n, "SightAiming") for n in zoom)
          and all(factors.values()),
          f"{len(zoom)} into AimZoom, "
          + ", ".join(f"{k}: {len(v)}" for k, v in factors.items()))
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


def run():
    check_weapon_component()
    check_keys_are_variables()
    check_sprint_and_stamina()
    check_ammunition()
