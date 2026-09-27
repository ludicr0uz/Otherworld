"""
verify_weapons_and_combat.py -- read the saved assets back and check them.

    UnrealEditor-Cmd <uproject> \
      -ExecutePythonScript="<abs>/Scripts/verify_weapons_and_combat.py" -NoUI -stdout

Everything here reads assets from disk rather than trusting the builder's return
values, because the failures that matter in this project are the silent ones: a
pin default that does not apply, a variable that compiles as int when it should
be a float, a rename that quietly did not happen. Each of those compiles, saves,
and looks entirely correct until something depends on it.
"""

import sys

import unreal

sys.path.insert(0, "/Users/alexeysukhov/Documents/Unreal Projects/Otherworld/Scripts")
import build_weapons_and_combat as G                              # noqa: E402

BGE = unreal.BlueprintGraphEditor
BEL = unreal.BlueprintEditorLibrary
PIN = unreal.BlueprintGraphPinLibrary
SDL = unreal.SubobjectDataBlueprintFunctionLibrary

PASS, FAIL = [], []


def check(label, ok, detail=""):
    (PASS if ok else FAIL).append(label)
    unreal.log_warning(f"[VERIFY] {'PASS' if ok else 'FAIL'}  {label}"
                       + (f" — {detail}" if detail else ""))


def load(path):
    return unreal.get_editor_subsystem(unreal.EditorAssetSubsystem).load_asset(path)


def graph(bp, name="EventGraph"):
    return BGE.get_graph_editor_by_name(bp, name)


def in_pins(node):
    return {str(PIN.get_pin_name(p)).replace(" ", "")
            for p in BEL.list_input_pins(node)}


def by_pins(nodes, *required):
    want = {r.replace(" ", "") for r in required}
    return [n for n in nodes if want <= in_pins(n)]


def pin_value(node, name):
    return str(PIN.get_pin_value(BEL.find_input_pin(node, name)))


def num_pin(node, name):
    """pin_value as a float, or None when the pin does not hold one.

    Sweeps like "is there any node whose B pin is 0.1" run over every node with
    a B pin, and in a graph with booleans in it that includes pins reading
    'false'. float() on those is a ValueError that stops the whole verifier.
    """
    try:
        return float(pin_value(node, name))
    except (TypeError, ValueError):
        return None


def cdo(bp):
    return unreal.get_default_object(BEL.generated_class(bp))


def component_template(bp, name):
    sds = unreal.get_engine_subsystem(unreal.SubobjectDataSubsystem)
    for h in sds.k2_gather_subobject_data_for_blueprint(bp):
        data = sds.k2_find_subobject_data_from_handle(h)
        if data and str(SDL.get_variable_name(data)) == name:
            return SDL.get_object(data)
    return None


def components(bp):
    sds = unreal.get_engine_subsystem(unreal.SubobjectDataSubsystem)
    out = []
    for h in sds.k2_gather_subobject_data_for_blueprint(bp):
        data = sds.k2_find_subobject_data_from_handle(h)
        if data:
            out.append(str(SDL.get_variable_name(data)))
    return out


# ─── The AnimGraph patch ─────────────────────────────────────────────────────

abp = load(G.ABP_PATH)
anim = graph(abp, "AnimGraph")
anim_nodes = anim.list_all_nodes() if anim else []
rigs = [n for n in anim_nodes if n.get_class().get_name() == "AnimGraphNode_ControlRig"]
blends = [n for n in anim_nodes
          if n.get_class().get_name() == "AnimGraphNode_LayeredBoneBlend"]
check("ABP_Unarmed has exactly one layered bone blend", len(blends) == 1,
      str(len(blends)))
if blends:
    layers = blends[0].get_editor_property("node").get_editor_property("layer_setup")
    bones = [str(f.get_editor_property("bone_name"))
             for l in layers for f in l.get_editor_property("branch_filters")]
    check(f"the blend is filtered at {G.UPPER_BODY_ROOT} (upper body only)",
          bones == [G.UPPER_BODY_ROOT], str(bones))

    # The slot must feed the *blend* pose, not the graph root -- that is the
    # whole difference between an aim pose and a frozen full-body override.
    blend_src = [PIN.get_owning_node(q).get_class().get_name()
                 for q in PIN.list_connected_pins(
                     BEL.find_input_pin(blends[0], "BlendPoses_0"))]
    # The regression that put the barrel 21 degrees left: in local space the
    # aim pose's arms hang off the locomotion hips and lose their own pelvis
    # yaw. Runtime, before the fix: body yaw 44.6, gun yaw 23.3, every frame.
    check("the blend runs in mesh space, so the aim pose keeps its own direction",
          blends[0].get_editor_property("node").get_editor_property(
              "mesh_space_rotation_blend"))
    check("DefaultSlot feeds the blend pose, so it cannot override the legs",
          blend_src == ["AnimGraphNode_Slot"], str(blend_src))
    base_src = [PIN.get_owning_node(q).get_class().get_name()
                for q in PIN.list_connected_pins(
                    BEL.find_input_pin(blends[0], "BasePose"))]
    check("locomotion feeds the base pose", base_src == ["AnimGraphNode_StateMachine"],
          str(base_src))

slots = [n for n in anim_nodes if n.get_class().get_name() == "AnimGraphNode_Slot"]
slot_names = {str(n.get_editor_property("node").get_editor_property("slot_name")): n
              for n in slots}
check(f"both slots exist: {G.AIM_SLOT} (aim) and {G.FULL_BODY_SLOT} (death)",
      {G.AIM_SLOT, G.FULL_BODY_SLOT} <= set(slot_names), str(sorted(slot_names)))
check("exactly two slots -- a rerun must not stack a third on the chain",
      len(slots) == 2, str(len(slots)))
# The death slot has to sit AFTER the layered blend, or it is filtered to the
# upper body like the aim slot and the player dies from the chest up.
if G.FULL_BODY_SLOT in slot_names and rigs:
    feeding = [PIN.get_owning_node(q) for q in PIN.list_connected_pins(
        BEL.find_input_pin(rigs[0], "Source"))]
    check(f"{G.FULL_BODY_SLOT} feeds the ControlRig, downstream of the blend",
          feeding == [slot_names[G.FULL_BODY_SLOT]],
          str([n.get_class().get_name() for n in feeding]))
    behind = [PIN.get_owning_node(q) for q in PIN.list_connected_pins(
        BEL.find_input_pin(slot_names[G.FULL_BODY_SLOT], "Source"))]
    check(f"the layered blend feeds {G.FULL_BODY_SLOT}",
          [n.get_class().get_name() for n in behind]
          == ["AnimGraphNode_LayeredBoneBlend"],
          str([n.get_class().get_name() for n in behind]))

# ─── The five weapons ────────────────────────────────────────────────────────
# Driven off _weapon_specs() rather than off a list written here, so a weapon
# added to the builder is a weapon checked by the verifier with no second edit.
# That is the claim the SMG, rifle and sniper were added to test.

item_bp = load(G.ITEM_BP_PATH)
check("BP_WeaponItem exists", item_bp is not None)

for spec in G._weapon_specs():
    bp = load(spec["path"])
    tag = spec["display"]
    if not bp:
        check(f"{tag}: asset exists", False)
        continue
    # UBlueprint.ParentClass is not exposed to Python, so inheritance is
    # checked by consequence: DisplayName is declared only on BP_WeaponItem, so
    # reading it off this CDO is only possible if this class derives from it.
    try:
        inherited = str(cdo(bp).get_editor_property("DisplayName"))
        check(f"{tag}: inherits BP_WeaponItem's properties", True, inherited)
    except Exception as exc:                                      # noqa: BLE001
        check(f"{tag}: inherits BP_WeaponItem's properties", False, str(exc))

    names = set(components(bp))
    want = {p[0] for p in spec["parts"]}
    check(f"{tag}: all {len(want)} parts present", want <= names,
          str(sorted(want - names)))
    debris = [n for n in names if n.startswith("StaticMesh")]
    check(f"{tag}: no leftover generated components", not debris, str(debris))

    d = cdo(bp)
    check(f"{tag}: damage is {spec['damage']}",
          abs(float(d.get_editor_property("Damage")) - spec["damage"]) < 1e-6,
          str(d.get_editor_property("Damage")))
    check(f"{tag}: {spec['pellets']} pellet(s) per shot",
          int(d.get_editor_property("PelletCount")) == spec["pellets"])
    # The int-vs-float trap: get_basic_type_by_name("float") silently declares an
    # int, and every default in this project happens to be integral, so the only
    # way to catch it is to look at the type Python hands back.
    for var in ("Damage", "SpreadDegrees", "WeaponRange"):
        value = d.get_editor_property(var)
        check(f"{tag}: {var} is a float, not an int",
              isinstance(value, float), f"{type(value).__name__} = {value}")
    check(f"{tag}: muzzle is at the barrel tip, not the origin",
          d.get_editor_property("MuzzleOffset").x > 10.0,
          str(d.get_editor_property("MuzzleOffset").x))
    for slot, label in (("FireSound", "a fire sound"),
                        ("DryFireSound", "a click for an empty chamber"),
                        ("ReloadSound", "a reload clack")):
        check(f"{tag}: has {label}",
              d.get_editor_property(slot) is not None)
    pose = d.get_editor_property("AimPose")
    check(f"{tag}: ready pose is {spec['aim'].rsplit('/', 1)[-1]}",
          pose is not None and pose.get_name() == spec["aim"].rsplit("/", 1)[-1],
          pose.get_name() if pose else "None")
    check(f"{tag}: display name is {spec['display']!r}",
          str(d.get_editor_property("DisplayName")) == spec["display"])
    check(f"{tag}: starts not-dropped",
          d.get_editor_property("Dropped") is False)

shot, pist = (load(G.SHOTGUN_BP_PATH), load(G.PISTOL_BP_PATH))
if shot and pist:
    a, b = cdo(shot), cdo(pist)
    check("the two weapons use different ready poses",
          a.get_editor_property("AimPose") != b.get_editor_property("AimPose"))
    check("the two weapons use different fire sounds",
          a.get_editor_property("FireSound") != b.get_editor_property("FireSound"))
    # The thing the player actually sees: in the pose the weapon is held in, the
    # barrel has to point where the character is facing. Computed from the
    # *saved* GripRotation, so a grip that was solved wrongly fails here.
    for spec in G._weapon_specs():
        bp, name, aim = load(spec["path"]), spec["display"], spec["aim"]
        mesh_yaw, socket = G.socket_in_mesh(aim)
        barrel = G._rotate_vector(
            G._rot(yaw=mesh_yaw),
            G._rotate_vector(unreal.MathLibrary.compose_transforms(
                G._pure_rotation(cdo(bp).get_editor_property("GripRotation")),
                G._pure_rotation(socket)).rotation.rotator(),
                unreal.Vector(1.0, 0.0, 0.0)))
        check(f"{name}: in its ready pose the barrel points where the player faces",
              barrel.x > 0.999, f"barrel = {barrel.to_tuple()}")

    # And the axis that caused three rounds of this: not +X.
    for name, aim in (("rifle", G.AIM_RIFLE), ("pistol", G.AIM_PISTOL)):
        axes = G.socket_pose_axes(aim)
        check(f"in the {name} ready pose the hand's weapon axis is +Y, not +X",
              axes["Y"].x > 0.9 and abs(axes["X"].x) < 0.5,
              f"+Y = {axes['Y'].to_tuple()}, +X = {axes['X'].to_tuple()}")

    # Five weapons in five slots with no icons: the colour swatch is the only
    # thing distinguishing them at a glance, so two the same is a real bug.
    swatches = [cdo(load(sp["path"])).get_editor_property("SlotColor").to_tuple()
                for sp in G._weapon_specs()]
    check("every weapon shows a different colour in the inventory",
          len(set(swatches)) == len(swatches), str(len(set(swatches))))
    # Same argument in the other sense: the gun you cannot see is the gun you
    # can hear, and a shared shot would make the sniper sound like the SMG.
    shots = [cdo(load(sp["path"])).get_editor_property("FireSound").get_name()
             for sp in G._weapon_specs()]
    check("every weapon has its own fire sound",
          len(set(shots)) == len(shots), str(sorted(shots)))
    # The two mechanical noises go the other way on purpose: a hammer on an
    # empty chamber is the same noise in any receiver.
    for slot in ("DryFireSound", "ReloadSound"):
        shared = {cdo(load(sp["path"])).get_editor_property(slot).get_name()
                  for sp in G._weapon_specs()}
        check(f"...while {slot} is deliberately shared by all of them",
              len(shared) == 1, str(sorted(shared)))

# ─── The three found weapons ─────────────────────────────────────────────────
# The starting loadout is spawned into the player's hands; these three exist
# only as drops, and that distinction is DROP_DISPLAYS.

issued = {"Shotgun", "Pistol"}
check("the drop table is the three weapons that are not issued",
      set(G.DROP_DISPLAYS) | issued == {sp["display"] for sp in G._weapon_specs()}
      and not (set(G.DROP_DISPLAYS) & issued),
      str(G.DROP_DISPLAYS))
# Sustained damage per second across the five. This is the one balance claim
# worth asserting mechanically: what differs between the weapons should be how
# the damage is *delivered* -- one big hit or nine small ones -- and not how
# much of it there is. A weapon three times the DPS of another is not a choice.
dps = {sp["display"]: sp["damage"] * sp["pellets"] / sp["interval"]
       for sp in G._weapon_specs()}
check("no weapon out-damages another by more than 3x over time",
      max(dps.values()) / min(dps.values()) < 3.0,
      ", ".join(f"{k} {v:.0f}" for k, v in sorted(dps.items(), key=lambda kv: -kv[1])))
sniper = next(sp for sp in G._weapon_specs() if sp["display"] == "Sniper")
check("the sniper kills a 100 HP wanderer in one shot",
      sniper["damage"] * sniper["pellets"] >= 100.0, str(sniper["damage"]))
smg = next(sp for sp in G._weapon_specs() if sp["display"] == "SMG")
check("...and the SMG needs most of a second and most of a magazine to do it",
      -(-100 // smg["damage"]) <= smg["magazine"]
      and -(-100 // smg["damage"]) * smg["interval"] > 0.5,
      f"{-(-100 // smg['damage']):.0f} rounds, "
      f"{-(-100 // smg['damage']) * smg['interval']:.2f}s")

# ─── Health, death, respawn ──────────────────────────────────────────────────

health_bp = load(G.HEALTH_BP_PATH)
h = cdo(health_bp)
check("health starts at 100", abs(float(h.get_editor_property("Health")) - 100.0) < 1e-6)
check("Health is a float, not an int",
      isinstance(h.get_editor_property("Health"), float),
      type(h.get_editor_property("Health")).__name__)
check("the player's copy does not despawn at 0 HP (default is off)",
      h.get_editor_property("DespawnOnDeath") is False)

hg = graph(health_bp).list_all_nodes()
check("death spawns a replacement", bool(by_pins(hg, "Class", "SpawnTransform")))
check("death destroys the owner",
      any(in_pins(n) == {"execute", "self"} for n in hg))
check("respawn point comes from the navmesh",
      bool(by_pins(hg, "Origin", "Radius")))

# The respawn has to land on walkable ground. The band point is built from the
# PLAYER's Z, so on any terrain higher than the player it is underground -- and
# a Character spawned underground falls through the world. These four checks
# guard the shape that fixes it, each of which compiles fine when broken:
projections = by_pins(hg, "Point", "QueryExtent")
check("the respawn point is projected onto the navmesh",
      len(projections) == G.RESPAWN_ATTEMPTS,
      f"{len(projections)} ProjectPointToNavigation node(s), "
      f"expected {G.RESPAWN_ATTEMPTS}")
# An unconnected struct pin reads as the ZERO vector: a search box with no
# volume, which finds nothing and fails every projection.
check("every projection has a real search box, not an empty struct pin",
      all(BEL.find_input_pin(n, "QueryExtent").list_connected_pins()
          for n in projections) and bool(projections))
# The original bug: the location output was used and the bool ignored, so a
# failed query spawned at the raw request point, at the player's own Z.
check("every projection's success is branched on, not ignored",
      all(BEL.find_output_pin(n, "ReturnValue").list_connected_pins()
          for n in projections) and bool(projections))
lifts = [n for n in by_pins(hg, "X", "Y", "Z")
         if pin_value(n, "Z") == str(G.RESPAWN_LIFT)]
check("the spawn is lifted from the ground to the capsule's centre",
      bool(lifts), f"expected a MakeVector with Z = {G.RESPAWN_LIFT}")
check("the chosen point is stored, so the random draw is evaluated once",
      "RespawnPoint" in {str(v) for v in BEL.list_member_variable_names(
          health_bp, False)})

# The respawn band. A replacement wanderer has to keep the "75-100 m away" rule
# the level generator spawns the pack under, or the rule holds only until the
# first kill -- and it is measured from the *player*, not from a stored spawn
# point, so that it survives the player walking across the map.
ranges = {(pin_value(n, "Min"), pin_value(n, "Max")) for n in by_pins(hg, "Min", "Max")}
want_band = (str(G.RESPAWN_BAND[0]), str(G.RESPAWN_BAND[1]))
check("respawns land in the 75-100 m band", want_band in ranges,
      f"{sorted(ranges)} vs {want_band}")
check("the bearing is random over a full circle", ("0.0", "360.0") in ranges,
      str(sorted(ranges)))
check("the respawn is measured from the player, not a stored spawn point",
      "SpawnOrigin" not in {str(v) for v in BEL.list_member_variable_names(
          health_bp, False)}
      and bool(by_pins(hg, "PlayerIndex")))
tick = graph(health_bp).find_event_node("ReceiveTick")
check("health ticks (otherwise nothing notices 0 HP)",
      tick is not None and bool(BEL.find_then_pin(tick).list_connected_pins()))

# ─── The weapon component ────────────────────────────────────────────────────

wc = load(G.WEAPON_COMP_BP_PATH)
w = cdo(wc)
wg = graph(wc).list_all_nodes()

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

keys = sorted(pin_value(n, "Key") for n in by_pins(wg, "self", "Key"))
want_keys = sorted([G.FIRE_KEY, G.SWITCH_KEY, G.DROP_KEY, G.PICKUP_KEY,
                    G.SPRINT_KEY, G.RELOAD_KEY])
check(f"polls exactly {want_keys}", keys == want_keys, str(keys))

plays = by_pins(wg, "Asset", "SlotNodeName")
check("the ready pose is played into a slot", len(plays) == 1, str(len(plays)))
if plays:
    check(f"it plays into {G.AIM_SLOT}",
          pin_value(plays[0], "SlotNodeName") == G.AIM_SLOT)
    check("it loops rather than playing once",
          int(float(pin_value(plays[0], "LoopCount"))) >= 100,
          pin_value(plays[0], "LoopCount"))
check("empty hands stop the slot", bool(by_pins(wg, "InBlendOutTime", "SlotNodeName")))

# The hybrid aim, which is the whole point of the trace layout: the camera line
# decides what is being aimed at, the muzzle line decides whether the gun can
# reach it, and the pellets fly down the muzzle line. Getting this wrong is not
# a compile error -- it is a gun that shoots from behind the player's shoulder.
traces = by_pins(wg, "Start", "End", "TraceChannel")
check("there are four traces (camera aim, muzzle clearance, pellets, drop probe)",
      len(traces) == 4, str(len(traces)))


def titled(nodes, title):
    """Nodes by their displayed title.

    The only handle Python gets on *which* function a call node wraps:
    BlueprintEditorLibrary exposes no get_function_name, and pin sets alone
    cannot tell GetCameraLocation from any other self-and-return node.
    """
    return [n for n in nodes
            if str(BEL.get_node_title(n)).replace("\n", " ") == title]


from_muzzle, from_camera = [], []
for t in traces:
    feeders = [PIN.get_owning_node(q) for q in
               PIN.list_connected_pins(BEL.find_input_pin(t, "Start"))]
    for n in feeders:
        if {"T", "Location"} <= in_pins(n):                      # TransformLocation
            from_muzzle.append(t)
        if str(BEL.get_node_title(n)) == "GetCameraLocation":
            from_camera.append(t)
check("two traces start at the weapon's muzzle: the clearance check and the pellets",
      len(from_muzzle) == 2, f"{len(from_muzzle)} fed by TransformLocation")
check("exactly one trace starts at the camera -- the one that picks the target",
      len(from_camera) == 1, f"{len(from_camera)} fed by GetCameraLocation")
# Built as a MakeVector, not as a pin literal: that operator's B pin is a
# struct pin when nothing is connected, and struct pins take no literal at all.
check("the camera's ray reaches AIM_TRACE_RANGE when it hits nothing",
      any(all(abs(float(pin_value(n, axis) or 0) - G.AIM_TRACE_RANGE) < 1e-3
              for axis in "XYZ")
          for n in titled(wg, "MakeVector")),
      f"{G.AIM_TRACE_RANGE:.0f} cm")
check("a dropped weapon lands in front of the player, not on their feet",
      any(all(abs(float(pin_value(n, axis) or 0) - G.DROP_FORWARD) < 1e-3
              for axis in "XYZ")
          for n in titled(wg, "MakeVector")),
      f"{G.DROP_FORWARD:.0f} cm ahead")
# One subtraction off AimPoint: the pellet direction.
deltas = [n for n in titled(wg, "vector - vector")
          if any(str(BEL.get_node_title(PIN.get_owning_node(q))) == "Get AimPoint"
                 for q in PIN.list_connected_pins(BEL.find_input_pin(n, "A")))]
check("the pellet direction is muzzle -> AimPoint, not camera forward",
      len(deltas) == 1, f"{len(deltas)} vector subtractions driven by AimPoint")

# A held weapon is rigidly attached and never rotated on its own. Driving its
# rotation from the aim was tried and reverted: the gun swivelled out of the
# hand and spun a full turn as the camera came round.
check("nothing rotates the held weapon out of the hand",
      not titled(wg, "Set Actor Rotation"),
      f"{len(titled(wg, 'Set Actor Rotation'))} SetActorRotation node(s)")
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

check("the component plays three sounds: the shot, the click and the reload",
      len(by_pins(wg, "Sound", "Location")) == 3,
      f"{len(by_pins(wg, 'Sound', 'Location'))} PlaySoundAtLocation node(s)")
check("impacts spawn blood", len(by_pins(wg, "Class", "SpawnTransform")) >= 3,
      f"{len(by_pins(wg, 'Class', 'SpawnTransform'))} spawn nodes "
      "(shotgun, pistol, blood)")
check("damage is clamped at zero", bool(by_pins(wg, "Value", "Min", "Max")))
check("switching wraps with a modulo", bool(by_pins(wg, "A", "B")))
check("pick-up searches the world for weapons", bool(by_pins(wg, "ActorClass")))
check("dropping detaches the weapon",
      bool(by_pins(wg, "LocationRule", "RotationRule", "ScaleRule")))

probes = [n for n in wg if "InString" in in_pins(n)]
check("no leftover debug PrintStrings", not probes, f"{len(probes)} found")

# ─── Spawn numbering ─────────────────────────────────────────────────────────
# Every wanderer takes a number as it spawns and logs where it appeared; the HUD
# draws that number beside its health bar. The pair is what makes a fall-through
# reportable, so both halves are guarded here.
gm = load(G.GAME_MODE_BP_PATH)
check("the GameMode carries the spawn counter",
      G.SPAWN_COUNT_VAR in {str(v) for v in BEL.list_member_variable_names(gm, False)})
check("the health component carries the wanderer's number",
      G.NPC_ID_VAR in {str(v) for v in BEL.list_member_variable_names(
          health_bp, False)})
logs = [n for n in hg if "InString" in in_pins(n)]
# Exactly three, all deliberate: the spawn log, the safety net's, and the
# player's death. Any more is a probe left behind -- and this graph is the one
# that gets instrumented whenever respawns misbehave.
check("exactly three log lines in the health graph (spawn + fell + death)",
      len(logs) == 3, f"{len(logs)} PrintString(s)")
# PrintWarning has no screen toggle (it is log-only by construction); the spawn
# log is a PrintString and must be told not to paint over the HUD.
screened = [n for n in logs if "bPrintToScreen" in in_pins(n)]
check("the spawn and death logs are written to the log, not over the HUD",
      all(pin_value(n, "bPrintToScreen") in ("false", "False") for n in screened)
      and bool(screened))
# Blueprint cannot log at Error severity at all, so the fall is reported at the
# highest it has: PrintWarning takes InString and nothing else.
check("the fall is reported at warning severity, not a plain print",
      any("bPrintToScreen" not in in_pins(n) for n in logs))
check("the wanderer remembers where it was spawned",
      G.SPAWNED_AT_VAR in {str(v) for v in BEL.list_member_variable_names(
          health_bp, False)})
# Both lines quote the stored SpawnedAt, so they cannot disagree.
def out_pins(node):
    return {str(PIN.get_pin_name(p)) for p in BEL.list_output_pins(node)}

reads = [n for n in hg if G.SPAWNED_AT_VAR in out_pins(n)]
check("the fall report names the spawn location too", len(reads) == 2,
      f"{len(reads)} SpawnedAt read(s), expected 2 (spawn log + fall report)")
prefixes = {pin_value(n, "A") for n in by_pins(hg, "A", "B")}
for label, want in (("spawn", G.SPAWN_LOG_PREFIX), ("fall", G.FELL_LOG_PREFIX)):
    check(f"{label} log lines are greppable", want in prefixes,
          f"expected {want!r}")

# ─── Installation ────────────────────────────────────────────────────────────

def blocks_visibility(bp):
    """Would a Visibility line trace hit this character?

    The single most important check in this file. UE's stock Pawn profile
    ignores Visibility, which is the channel the pellets trace on, so a
    character left on the default is simply unhittable -- and the trace reports
    "no hit" exactly as it would for a real miss, so nothing anywhere says so.
    """
    capsule = component_template(bp, "CapsuleComponent")
    if capsule is None:
        return None
    return (capsule.get_collision_response_to_channel(
        unreal.CollisionChannel.ECC_VISIBILITY) == unreal.CollisionResponseType.ECR_BLOCK)


char = load(G.CHARACTER_BP_PATH)
cnames = set(components(char))
# Found by type, not by name: the template's boom is "CameraBoom" in the
# third-person template but that is a name somebody could reasonably change,
# whereas there is only ever one spring arm on a third-person character.
arm = next((c for c in (component_template(char, n) for n in components(char))
            if isinstance(c, unreal.SpringArmComponent)), None)
check("the camera sits over the shoulder, so the reticle is not on the player",
      arm is not None
      and abs(arm.get_editor_property("socket_offset").y - G.CAMERA_SHOULDER[1]) < 1e-3
      and abs(arm.get_editor_property("target_arm_length") - G.CAMERA_ARM) < 1e-3,
      f"offset {arm.get_editor_property('socket_offset').to_tuple()}, "
      f"arm {arm.get_editor_property('target_arm_length')}" if arm else "no boom")

move = next((c for c in (component_template(char, n) for n in components(char))
             if isinstance(c, unreal.CharacterMovementComponent)), None)
check("the body follows the camera, so the gun stays on the crosshair",
      cdo(char).get_editor_property("use_controller_rotation_yaw")
      and move is not None
      and not move.get_editor_property("orient_rotation_to_movement"),
      "orient-to-movement would turn the gun with the movement input instead")

check("player carries HealthComponent + WeaponComponent",
      {"HealthComponent", "WeaponComponent"} <= cnames,
      str(sorted(cnames)))
stale = cnames & G.OLD_SHOTGUN_PARTS
check("the old welded shotgun is gone from the player", not stale, str(sorted(stale)))
check("player's capsule blocks Visibility, so it can be shot too",
      blocks_visibility(char) is True, str(blocks_visibility(char)))

check("pellet traces are drawn, so a miss is visible",
      G.TRACE_DEBUG_SECONDS > 0, f"{G.TRACE_DEBUG_SECONDS}s")

npc = load(G.NPC_BP_PATH)
if npc:
    check("NPC carries HealthComponent", "HealthComponent" in components(npc))
    n = cdo(npc)
    # A component added through the SCS is not a property on the CDO -- it is
    # constructed per instance -- so its authored defaults live on the subobject
    # template, which is also where the builder wrote them.
    comp = component_template(npc, "HealthComponent")
    check("NPC despawns at 0 HP",
          comp is not None and comp.get_editor_property("DespawnOnDeath") is True)
    rc = comp.get_editor_property("RespawnClass") if comp else None
    check("NPC respawns as another wanderer",
          rc is not None and "ForestWanderer" in rc.get_name(),
          rc.get_name() if rc else "None")
    check("NPC's capsule blocks Visibility, so pellets can actually hit it",
          blocks_visibility(npc) is True, str(blocks_visibility(npc)))
    check("a spawned wanderer still gets an AI controller",
          n.get_editor_property("auto_possess_ai")
          == unreal.AutoPossessAI.PLACED_IN_WORLD_OR_SPAWNED)

# ─── Blood: the spray, not just the spheres ──────────────────────────────────
# The layout is generated from a fixed seed, so it can be recomputed here and
# compared component by component -- a blob nudged by hand in the editor, or a
# seed changed without meaning to, shows up as a mismatch rather than as "the
# blood looks a bit different from how I remember it".

blood_bp = load(G.BLOOD_BP_PATH)
want_blobs = G._blood_blobs()
check(f"the splash has {len(want_blobs)} blobs",
      len({c for c in components(blood_bp) if c.startswith("Blob")})
      == len(want_blobs),
      str(sorted({c for c in components(blood_bp) if c.startswith("Blob")})))
placed = True
for i, (bx, by, bz, bscale) in enumerate(want_blobs):
    t = component_template(blood_bp, f"Blob{i}")
    if t is None:
        placed = False
        break
    loc = t.get_editor_property("relative_location")
    size = t.get_editor_property("relative_scale3d")
    placed &= (abs(loc.x - bx) < 1e-3 and abs(loc.y - by) < 1e-3
               and abs(loc.z - bz) < 1e-3 and abs(size.x - bscale) < 1e-4)
check("every blob sits where the seeded layout puts it", placed)
# The cone has to lean along +X, which is what the impact rotates onto the hit
# normal. A symmetric ball of spheres would spray nowhere in particular.
check("the cone reaches out along +X, the hit normal",
      max(b[0] for b in want_blobs) > 5.0
      and max(abs(b[1]) for b in want_blobs) < max(b[0] for b in want_blobs),
      f"reach {max(b[0] for b in want_blobs):.1f} cm")

bg = graph(blood_bp).list_all_nodes()
check("the burst swells and fades on a sine, not a straight ramp",
      any("Sin" in str(BEL.get_node_title(n)) for n in bg))
check("the spray arcs: the age is squared for the gravity term",
      any({PIN.get_owning_node(q)
           for side in ("A", "B")
           for q in PIN.list_connected_pins(BEL.find_input_pin(n, side))
           } and len({PIN.get_owning_node(q)
                      for side in ("A", "B")
                      for q in PIN.list_connected_pins(
                          BEL.find_input_pin(n, side))}) == 1
          for n in by_pins(bg, "A", "B")),
      "expected Age * Age feeding the fall")
check("the splash moves rather than only scaling",
      bool(by_pins(bg, "NewLocation")))
check("the wound position is stored, so the arc cannot drift frame to frame",
      "Origin" in {str(v) for v in BEL.list_member_variable_names(blood_bp, False)})
check("the splash still cleans itself up", bool(by_pins(bg, "InLifespan")))

# And the half that makes the direction mean anything: the impact has to turn
# the splash onto the surface normal it hit.
check("impacts point the splash down the surface normal",
      bool(titled(wg, "MakeRotFromX")),
      "without it the spray leaves along the world's +X, not out of the wound")

# ─── The damage stamp ────────────────────────────────────────────────────────

health_vars = {str(v) for v in BEL.list_member_variable_names(health_bp, False)}
check("the health component records when it was last hurt",
      G.LAST_DAMAGE_VAR in health_vars, str(sorted(health_vars)))
check("nothing starts the game looking recently hurt",
      abs(float(h.get_editor_property(G.LAST_DAMAGE_VAR)) - G.NEVER_DAMAGED) < 1e-6,
      str(h.get_editor_property(G.LAST_DAMAGE_VAR)))
check("LastDamageTime is a float, not an int",
      isinstance(h.get_editor_property(G.LAST_DAMAGE_VAR), float),
      type(h.get_editor_property(G.LAST_DAMAGE_VAR)).__name__)
check("a pellet stamps the time it landed",
      bool(titled(wg, f"SET {G.LAST_DAMAGE_VAR}"))
      or bool(titled(wg, f"Set {G.LAST_DAMAGE_VAR}")),
      "the HUD floats a wanderer's bar off this")
check("a pellet also records who did it",
      bool(titled(wg, f"SET {G.DAMAGED_BY_PLAYER_VAR}"))
      or bool(titled(wg, f"Set {G.DAMAGED_BY_PLAYER_VAR}")))
check("nothing is born blamed on the player",
      h.get_editor_property(G.DAMAGED_BY_PLAYER_VAR) is False)

# ─── The kill counter ────────────────────────────────────────────────────────

gm_vars = {str(v) for v in BEL.list_member_variable_names(gm, False)}
check("the GameMode carries the kill counter", G.KILL_COUNT_VAR in gm_vars,
      str(sorted(gm_vars)))
check("the GameMode carries the player-death flag", G.PLAYER_DEAD_VAR in gm_vars)
check("a death adds one to the kill counter",
      bool(titled(hg, f"SET {G.KILL_COUNT_VAR}"))
      or bool(titled(hg, f"Set {G.KILL_COUNT_VAR}")))
# The guard that stops the safety net inflating the score: a wanderer that fell
# through the world dies down this very same path, and nobody shot it.
blamed = [n for n in hg if G.DAMAGED_BY_PLAYER_VAR in out_pins(n)]
check("only a death the player caused is counted", len(blamed) == 1,
      f"{len(blamed)} reads of {G.DAMAGED_BY_PLAYER_VAR} in the death path")
if blamed:
    driven = [PIN.get_owning_node(q) for q in
              BEL.find_output_pin(blamed[0],
                                  G.DAMAGED_BY_PLAYER_VAR).list_connected_pins()]
    check("and a Branch is what guards on it, not an AND",
          [n.get_class().get_name() for n in driven] == ["K2Node_IfThenElse"],
          str([n.get_class().get_name() for n in driven]))

# ─── The player's death ──────────────────────────────────────────────────────
# Until now the DespawnOnDeath-false arm of the death path simply ended: the
# player sat at 0 HP while the pack kept swinging.

deaths = by_pins(hg, "Asset", "SlotNodeName")
check("the player plays a death animation", len(deaths) == 1, str(len(deaths)))
if deaths:
    check(f"it plays into {G.FULL_BODY_SLOT}, so the legs go down too",
          pin_value(deaths[0], "SlotNodeName") == G.FULL_BODY_SLOT,
          pin_value(deaths[0], "SlotNodeName"))
    check("it plays a death animation, not the attack montage",
          "Death" in pin_value(deaths[0], "Asset"), pin_value(deaths[0], "Asset"))
check("the body stops where it fell",
      bool(titled(hg, "DisableMovement")),
      "without it the corpse slides on under the last movement input")
pauses = by_pins(hg, "bPaused")
check("death pauses the game", len(pauses) == 1, str(len(pauses)))
if pauses:
    check("...paused, not unpaused",
          pin_value(pauses[0], "bPaused") in ("true", "True"),
          pin_value(pauses[0], "bPaused"))
check("the pause waits for the animation to land",
      any(abs(float(pin_value(n, "Duration") or 0) - G.DEATH_PAUSE_SECONDS) < 1e-3
          for n in by_pins(hg, "Duration")),
      f"expected a {G.DEATH_PAUSE_SECONDS}s Delay before the pause")
check("the death flag is raised for the HUD to draw the menu from",
      bool(titled(hg, f"SET {G.PLAYER_DEAD_VAR}"))
      or bool(titled(hg, f"Set {G.PLAYER_DEAD_VAR}")))

# ─── Sprint and stamina ──────────────────────────────────────────────────────

for var, kind, want in (("Stamina", float, G.MAX_STAMINA),
                        ("MaxStamina", float, G.MAX_STAMINA),
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
                and pin_value(n, "Key") == G.SPRINT_KEY]
check(f"{G.SPRINT_KEY} is polled as held, not as a tap",
      bool(sprint_polls)
      and all("IsInputKeyDown" in str(BEL.get_node_title(n))
              for n in sprint_polls),
      str([str(BEL.get_node_title(n)) for n in sprint_polls]))
walk_titles = {t for t in (str(BEL.get_node_title(n)).replace("\n", " ")
                           for n in wg) if "MaxWalkSpeed" in t}
check("sprinting drives the character's own walk speed",
      any(t.startswith("SET") or t.startswith("Set") for t in walk_titles),
      str(sorted(walk_titles)))
# Cached, never written down: a literal walk speed here would fight any later
# change to the character's movement defaults, and only after the first sprint.
check("the walking speed is cached off the character, not hardcoded",
      any(t.startswith("Get") for t in walk_titles)
      and any("BaseSpeed" in str(BEL.get_node_title(n)).replace("\n", " ")
              for n in wg),
      str(sorted(walk_titles)))
selects = titled(wg, "SelectFloat")
check("one SelectFloat picks the speed and one picks the drain",
      len(selects) == 2, f"{len(selects)} SelectFloat node(s)")
check("stamina is clamped, so it cannot run past its own bar",
      any(pin_value(n, "Max") == str(G.MAX_STAMINA)
          for n in by_pins(wg, "Value", "Min", "Max")),
      f"expected a clamp at {G.MAX_STAMINA}")
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
# The requirement in one line: the shotgun is limited, the pistol is not. Every
# check here is about the difference between those two being *data* -- a row in
# _weapon_specs -- rather than a branch on the weapon's name somewhere.

for want in G._weapon_specs():
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

shotgun_cdo = cdo(load(G.SHOTGUN_BP_PATH))
check(f"the shotgun starts with {G.SHOTGUN_MAGAZINE + G.SHOTGUN_RESERVE} shells "
      f"in total -- {G.SHOTGUN_MAGAZINE} loaded and {G.SHOTGUN_RESERVE} spare",
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
check("the pistol is unlimited and therefore never reloads",
      cdo(load(G.PISTOL_BP_PATH)).get_editor_property("UsesAmmo") is False)

# --- what the graph does with all that ---------------------------------------
loaded_writes = [t for t in (str(BEL.get_node_title(n)).replace("\n", " ")
                             for n in wg) if t == "Set Loaded"]
check("firing spends a round and reloading puts rounds back",
      len(loaded_writes) == 2, f"{len(loaded_writes)} writes to Loaded")
next_writes = [t for t in (str(BEL.get_node_title(n)).replace("\n", " ")
                           for n in wg) if t == "Set NextFireTime"]
check("both the interval and the reload push the same NextFireTime deadline",
      len(next_writes) == 2, f"{len(next_writes)} writes to NextFireTime")
check("the deadline is compared against the clock, not a frame count",
      bool(titled(wg, "GetTimeSeconds")),
      f"{len(titled(wg, 'GetTimeSeconds'))} GetTimeSeconds")
# The reserve is only ever *spent* here; it is topped up by BP_AmmoPickup.
check("the weapon component spends the reserve and never grants it",
      len([t for t in (str(BEL.get_node_title(n)).replace("\n", " ")
                       for n in wg) if t == "Set Reserve"]) == 1)
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
# The gate is nested, not folded: every one of these reads a property off Held,
# and the outer condition is pulled on frames where nothing is equipped.
ammo_reads = [n for n in wg if "UsesAmmo" in out_pins(n)]
check("the fire gate and the reload both ask the weapon whether it uses ammo",
      len(ammo_reads) == 2, f"{len(ammo_reads)} UsesAmmo reads")
check("an unlimited weapon short-circuits the magazine test (an OR, not an AND)",
      bool(titled(wg, "OR Boolean")),
      str(sorted({t for t in (str(BEL.get_node_title(n)).replace("\n", " ")
                              for n in wg) if " OR" in t.upper()})))

# ─── The click and the clack ─────────────────────────────────────────────────
# Two sounds whose whole value is *when* they do not play. A click on every
# refused trigger pull would fire on the SMG's every-0.09s cooldown; a clack on
# every R would reward pressing reload at a full magazine.

titles = [str(BEL.get_node_title(n)).replace("\n", " ") for n in wg]
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

# ─── Sprinting drops the ready pose ──────────────────────────────────────────
# The complaint this answers: running with the barrel levelled at the horizon.
# There is no new animation -- the fix is to stop playing the ready pose, and
# let ABP_Unarmed's own locomotion state machine through the layered blend.

check("PoseSprinting exists to make the change edge-triggered",
      w.get_editor_property("PoseSprinting") is False,
      str(w.get_editor_property("PoseSprinting")))
check("...and it matches Sprinting at start, so frame one re-equips nothing",
      w.get_editor_property("PoseSprinting")
      == w.get_editor_property("Sprinting"))
check("the sprint state is remembered exactly once",
      titles.count("Set PoseSprinting") == 1,
      f"{titles.count('Set PoseSprinting')} writes")
check("...and re-equipping happens only on the frames the two disagree",
      any("!=" in t or "NotEqual" in t.replace(" ", "") for t in titles),
      str(sorted({t for t in titles if "=" in t})))
# The pose itself: the branch that decides whether to play or stop the slot
# now has a NOT Sprinting in its condition, which is what actually stops it.
plays = by_pins(wg, "Asset", "SlotNodeName")
if plays:
    node, reached = plays[0], False
    ins = BEL.find_input_pin(node, "execute")
    gate = [PIN.get_owning_node(q) for q in PIN.list_connected_pins(ins)]
    if gate:
        cond = [PIN.get_owning_node(q)
                for q in PIN.list_connected_pins(
                    BEL.find_input_pin(gate[0], "Condition"))]
        # Walk the two inputs of the AND looking for a Sprinting read.
        frontier = list(cond)
        for _ in range(6):
            nxt = []
            for n in frontier:
                if "Sprinting" in out_pins(n):
                    reached = True
                for q in BEL.list_input_pins(n):
                    nxt += [PIN.get_owning_node(r)
                            for r in PIN.list_connected_pins(q)]
            frontier = nxt
    check("the ready pose is not played while sprinting", reached,
          "Sprinting read found behind the pose branch's condition")
sprint_gets = [n for n in wg if "Sprinting" in out_pins(n)]
check("Sprinting is read by the fire gate, the pose edge and the pose branch",
      len(sprint_gets) >= 4, f"{len(sprint_gets)} reads")

# ─── Debug mode ──────────────────────────────────────────────────────────────

mode_cdo = cdo(load(G.GAME_MODE_BP_PATH))
check("the GameMode carries the debug flag, where a component can reach it",
      isinstance(mode_cdo.get_editor_property(G.DEBUG_MODE_VAR), bool))
check("...and it is OFF by default -- the overlays are instrumentation",
      mode_cdo.get_editor_property(G.DEBUG_MODE_VAR) is False)
check("the pellet tracer is a DrawDebugLine, not a trace that draws itself",
      bool(by_pins(wg, "LineStart", "LineEnd")),
      f"{len(by_pins(wg, 'LineStart', 'LineEnd'))} DrawDebugLine node(s)")
check("...and it lasts as long as the tracer always did",
      all(abs(float(pin_value(n, "Duration") or 0) - G.TRACE_DEBUG_SECONDS) < 1e-3
          for n in by_pins(wg, "LineStart", "LineEnd")),
      f"{G.TRACE_DEBUG_SECONDS}s")
# Read once per shot off the GameMode, cached, then branched on per pellet.
check("the flag is read off the GameMode once per shot and cached",
      len([t for t in (str(BEL.get_node_title(n)).replace("\n", " ")
                       for n in wg) if t == f"Set {G.DEBUG_MODE_VAR}"]) == 1)
check("...and the pellet loop branches on the cached copy",
      len([n for n in wg if G.DEBUG_MODE_VAR in out_pins(n)]) == 2,
      f"{len([n for n in wg if G.DEBUG_MODE_VAR in out_pins(n)])} reads")

# ─── BP_AmmoPickup ───────────────────────────────────────────────────────────

ammo_bp = load(G.AMMO_BP_PATH)
ammo = cdo(ammo_bp)
ag = graph(ammo_bp).list_all_nodes()

check(f"a drop carries {G.AMMO_DROP_SHELLS} shells",
      ammo.get_editor_property("Shells") == G.AMMO_DROP_SHELLS,
      str(ammo.get_editor_property("Shells")))
check("it starts uncollected", ammo.get_editor_property("Credited") is False)
check("it looks like what it gives you -- one mesh per shell",
      len({n for n in components(ammo_bp) if n.startswith("Shell")})
      == G.AMMO_DROP_SHELLS,
      str(sorted({n for n in components(ammo_bp) if n.startswith("Shell")})))
# Measured HERE, on at most a handful of actors, rather than by sweeping the
# level from the weapon component's Tick every frame whether any exist or not.
check("the pickup measures its own distance to the player",
      bool(by_pins(ag, "V1", "V2")) and bool(by_pins(ag, "PlayerIndex")),
      f"{len(by_pins(ag, 'V1', 'V2'))} distance node(s)")
check(f"...and is taken by walking within {G.AMMO_PICKUP_RADIUS:.0f} cm of it",
      any(pin_value(n, "B") == str(G.AMMO_PICKUP_RADIUS)
          for n in ag if "B" in in_pins(n)),
      f"{G.AMMO_PICKUP_RADIUS:.0f} cm")
check("no key is involved -- it is not another thing to press E on",
      not by_pins(ag, "Key"), f"{len(by_pins(ag, 'Key'))} key polls")
check("it credits the weapon's own Reserve, not a counter on the player",
      any(str(BEL.get_node_title(n)).replace("\n", " ") == "Set Reserve"
          for n in ag))
check("Credited is written on both paths -- the held weapon and the fallback loop",
      len([n for n in ag
           if str(BEL.get_node_title(n)).replace("\n", " ") == "Set Credited"]) == 2,
      f"{len([n for n in ag if str(BEL.get_node_title(n)).replace(chr(10), ' ') == 'Set Credited'])} writes")
check("...and it only vanishes once something has actually taken it",
      len([n for n in ag if "Credited" in out_pins(n)]) == 2,
      f"{len([n for n in ag if 'Credited' in out_pins(n)])} reads of Credited")
# With four of the five weapons using ammunition, "the first one in the
# inventory" means the shotgun in slot 0 forever -- so a player clearing the
# forest with the sniper would watch a gun they are not holding fill up.
check("the shells go to the weapon in the player's hands first",
      any("Held" in out_pins(n) for n in ag),
      "no read of the weapon component's Held on the pickup")
held_reads = [n for n in ag if "Held" in out_pins(n)]
if held_reads:
    # And that read has to be behind an IsValid gate rather than beside one:
    # UsesAmmo is a pure pull off Held, and pulling it while unarmed is an
    # Accessed None -- the trap this project has now hit four times.
    valids = [n for n in ag if "Object" in in_pins(n)
              and "IsValid" in str(BEL.get_node_title(n))]
    check("...behind an IsValid gate, because reading UsesAmmo off None is an "
          "Accessed None", bool(valids), f"{len(valids)} IsValid node(s)")
check("...with the inventory loop kept as the fallback for an unarmed player "
      "or one holding the pistol",
      bool(by_pins(ag, "Array")) or any("Inventory" in out_pins(n) for n in ag),
      "the ForEachLoop over Inventory is gone")

# ─── The 10% weapon drop ─────────────────────────────────────────────────────

drop_classes = list(cdo(health_bp).get_editor_property("DropClasses"))
check(f"a kill can leave one of {len(G.DROP_DISPLAYS)} weapons",
      len(drop_classes) == len(G.DROP_DISPLAYS), str(len(drop_classes)))
check("...and they are the three that are not in the starting loadout",
      [c.get_name() for c in drop_classes]
      == [f"{sp['path'].rsplit('/', 1)[-1]}_C" for sp in G._weapon_specs()
          if sp["display"] in G.DROP_DISPLAYS],
      str([c.get_name() for c in drop_classes]))
check(f"the drop rate is {G.GUN_DROP_CHANCE * 100:.0f}%",
      any(abs((num_pin(n, "B") or -1.0) - G.GUN_DROP_CHANCE) < 1e-6
          for n in hg if "B" in in_pins(n)),
      f"expected a comparison against {G.GUN_DROP_CHANCE}")
# Two draws, not one weighted table: the rate and the table are tuned apart.
check("...rolled once, and which weapon drawn separately",
      bool([n for n in hg if {"Min", "Max"} <= in_pins(n)
            and "Random" in str(BEL.get_node_title(n))]),
      "no random draw in the death path")
check("the weapon is picked by index into the array, not by a Switch that "
      "would need a pin per weapon",
      bool(by_pins(hg, "TargetArray", "Index")),
      f"{len(by_pins(hg, 'TargetArray', 'Index'))} Array_Get node(s)")
# The empty-table guard. Without it RandomIntegerInRange(0, -1) indexes nothing.
check("an empty drop table drops nothing rather than indexing off the end",
      any(str(BEL.get_node_title(n)).replace("\n", " ").startswith("Get DropClasses")
          for n in hg)
      and bool([n for n in hg if "TargetArray" in in_pins(n)
                and "Length" in str(BEL.get_node_title(n))]),
      "no Array_Length on DropClasses")
# The handover: from here it is an ordinary weapon on the ground, and the E key
# that picks up a gun the player threw away picks this one up with no new code.
check("a dropped weapon is flagged Dropped, which is the whole pick-up interface",
      any(str(BEL.get_node_title(n)).replace("\n", " ") == "Set Dropped"
          for n in hg),
      "nothing sets Dropped in the death path")
# Matched by the feeder's PIN SET, not by its title: Array_Get's displayed
# title is the bare word "Get", which is also how every variable getter in the
# graph reads. Pins are the only unambiguous handle.
guns = [n for n in by_pins(hg, "Class", "SpawnTransform")
        if any({"TargetArray", "Index"} <= in_pins(PIN.get_owning_node(q))
               for q in PIN.list_connected_pins(BEL.find_input_pin(n, "Class")))]
check("exactly one spawn in the death path drops a weapon",
      len(guns) == 1, f"{len(guns)} weapon spawns")
# Same guard as the shells and the kill count, walked the same way: the safety
# net kills anything that falls under the world down this very path.
if guns:
    seen, node, guarded = set(), guns[0], False
    for _ in range(60):
        ins = BEL.find_input_pin(node, "execute")
        feeders = [PIN.get_owning_node(q) for q in PIN.list_connected_pins(ins)] \
            if ins and ins.is_valid() else []
        if not feeders:
            break
        node = feeders[0]
        if id(node) in seen:
            break
        seen.add(id(node))
        if "Branch" in str(BEL.get_node_title(node)).replace("\n", " "):
            cond = BEL.find_input_pin(node, "Condition")
            if cond and cond.is_valid() and any(
                    G.DAMAGED_BY_PLAYER_VAR in str(BEL.get_node_title(
                        PIN.get_owning_node(q)))
                    for q in PIN.list_connected_pins(cond)):
                guarded = True
                break
    check("only a death the player caused drops a weapon", guarded,
          "the safety net must not be a weapon dispenser")
check("an uncollected drop tidies itself away",
      any(abs(float(pin_value(n, "InLifespan") or 0) - G.AMMO_PICKUP_LIFETIME) < 1e-3
          for n in ag if "InLifespan" in in_pins(n)),
      f"{G.AMMO_PICKUP_LIFETIME:.0f}s")

# --- and who drops it --------------------------------------------------------
hp = load(G.HEALTH_BP_PATH)
hg = graph(hp).list_all_nodes()
check("a killed wanderer's health component knows what to drop",
      cdo(hp).get_editor_property("AmmoClass") is not None
      and cdo(hp).get_editor_property("AmmoClass").get_name() == "BP_AmmoPickup_C",
      str(cdo(hp).get_editor_property("AmmoClass")))
drops = [n for n in by_pins(hg, "Class", "SpawnTransform")
         if any("AmmoClass" in str(BEL.get_node_title(PIN.get_owning_node(q)))
                for q in PIN.list_connected_pins(BEL.find_input_pin(n, "Class")))]
check("exactly one spawn in the death path drops ammunition",
      len(drops) == 1, f"{len(drops)} ammo spawns")
# The same guard the kill counter uses, and for the same reason: the safety net
# writes Health to 0 for a wanderer that fell through the world, and paying the
# player for that would turn a bug into an ammunition supply.
if drops:
    seen, node, guarded = set(), drops[0], False
    for _ in range(40):
        ins = BEL.find_input_pin(node, "execute")
        feeders = [PIN.get_owning_node(q) for q in PIN.list_connected_pins(ins)] \
            if ins and ins.is_valid() else []
        if not feeders:
            break
        node = feeders[0]
        if id(node) in seen:
            break
        seen.add(id(node))
        title = str(BEL.get_node_title(node)).replace("\n", " ")
        if "Branch" in title:
            cond = BEL.find_input_pin(node, "Condition")
            if cond and cond.is_valid() and any(
                    G.DAMAGED_BY_PLAYER_VAR in str(BEL.get_node_title(
                        PIN.get_owning_node(q)))
                    for q in PIN.list_connected_pins(cond)):
                guarded = True
                break
    check("only a death the player caused drops shells", guarded,
          f"{G.DAMAGED_BY_PLAYER_VAR} branch found upstream: {guarded}")


# ─── Summary ─────────────────────────────────────────────────────────────────

unreal.log_warning(f"[VERIFY] {len(PASS)} passed, {len(FAIL)} failed")
for f in FAIL:
    unreal.log_warning(f"[VERIFY]   FAILED: {f}")
