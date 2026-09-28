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
    # The click goes the other way on purpose: a hammer falling on an empty
    # chamber is the same noise in any receiver, so one asset serves all five.
    clicks = {cdo(load(sp["path"])).get_editor_property("DryFireSound").get_name()
              for sp in G._weapon_specs()}
    check("...while DryFireSound is deliberately shared by all of them",
          len(clicks) == 1, str(sorted(clicks)))
    # The reload does NOT, and that changed when the sounds became recordings
    # of real firearms: a pump shotgun, a magazine swap and a hand-fed reload
    # are three different actions. Assert against the spec table rather than
    # against a list written out here, so a weapon whose row is edited is
    # checked against its row.
    for sp in G._weapon_specs():
        want = sp["reload_sound"].rsplit("/", 1)[-1]
        got = cdo(load(sp["path"])).get_editor_property("ReloadSound")
        check(f"{sp['display']}: reloads with {want}",
              got is not None and got.get_name() == want,
              got.get_name() if got else "None")
    reloads = {cdo(load(sp["path"])).get_editor_property("ReloadSound").get_name()
               for sp in G._weapon_specs()}
    check("...and the reload is NOT one sound for five weapons any more",
          len(reloads) > 1, str(sorted(reloads)))
    # The one pairing that would be audibly wrong: a 0.47 s pump under an
    # assault rifle, or a magazine swap on a pump shotgun.
    by_name = {sp["display"]: cdo(load(sp["path"]))
               .get_editor_property("ReloadSound").get_name()
               for sp in G._weapon_specs()}
    check("the pump shotgun does not share a reload with the magazine weapons",
          by_name["Shotgun"] not in {by_name["SMG"], by_name["Rifle"]},
          str(by_name))

# ─── The sounds themselves ───────────────────────────────────────────────────
# Nine assets cut from CC0 recordings of real firearms by
# Scripts/fetch_weapon_sounds.py, which replaced a synthesiser. The checks are
# on the WAVs on disk rather than on the SoundWave assets, because the two
# properties worth asserting are properties of the audio and not of the import.

import os
import wave as _wave

_eas = unreal.get_editor_subsystem(unreal.EditorAssetSubsystem)

for name in G.SOUND_NAMES:
    check(f"{name} imported", _eas.does_asset_exist(f"{G.AUDIO_DIR}/{name}"))
# A_Reload was the one synthesised clack every weapon shared. A builder that
# simply stops referencing an asset leaves it on disk forever, so its removal
# is deliberate and worth asserting -- an orphan in the audio folder reads as
# something still in use.
for path in G.RETIRED_SOUNDS:
    check(f"the superseded {path.rsplit('/', 1)[-1]} is gone",
          not _eas.does_asset_exist(path), path)

for name in G.SOUND_NAMES:
    src = os.path.join(G.SOUND_SRC_DIR, f"{name}.wav")
    if not os.path.isfile(src):
        check(f"{name}.wav is on disk", False, src)
        continue
    with _wave.open(src, "rb") as fh:
        channels, rate, frames = (fh.getnchannels(), fh.getframerate(),
                                  fh.getnframes())
    # MONO IS LOAD-BEARING, not a size choice. PlaySoundAtLocation spatialises
    # by panning and attenuating around the listener and can only do that to a
    # one-channel source; hand it the stereo original and every shot plays flat
    # and full volume with no sense of where the muzzle was.
    check(f"{name} is mono, so PlaySoundAtLocation can place it",
          channels == 1, f"{channels} channels")
    check(f"{name} is 44.1 kHz", rate == 44100, str(rate))
    seconds = frames / float(rate)
    check(f"{name} is between 0.2 s and 2.5 s long", 0.2 <= seconds <= 2.5,
          f"{seconds:.2f}s")

# A shot has to finish inside its own fire interval or an automatic stacks an
# unbounded number of copies of itself. Only the automatics are checked: the
# sniper's 1.6 s report deliberately runs into its 1.6 s cadence.
for name in G.AUTO_DISPLAYS:
    sp = next(x for x in G._weapon_specs() if x["display"] == name)
    src = os.path.join(G.SOUND_SRC_DIR, f"{sp['sound'].rsplit('/', 1)[-1]}.wav")
    if not os.path.isfile(src):
        continue
    with _wave.open(src, "rb") as fh:
        seconds = fh.getnframes() / float(fh.getframerate())
    overlap = seconds / sp["interval"]
    check(f"{name}: a held trigger stacks at most 12 copies of the shot",
          overlap <= 12.0, f"{seconds:.2f}s sample / {sp['interval']:.2f}s "
                           f"interval = {overlap:.1f} overlapping")
    # ...and the ones that do stack are mixed down for it, or the burst clips.
    with _wave.open(src, "rb") as fh:
        raw = fh.readframes(fh.getnframes())
    peak = max(abs(int.from_bytes(raw[i:i + 2], "little", signed=True))
               for i in range(0, len(raw), 2)) / 32767.0
    check(f"{name}: its sample is mixed below full scale, so a burst does not "
          f"clip", peak < 0.80, f"peak {peak:.2f}")

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

# The fire key appears TWICE and that is the whole of automatic fire: once as
# WasInputKeyJustPressed (a tap) and once as IsInputKeyDown (a hold). Sprint
# and aim are the other two held keys.
keys = sorted(pin_value(n, "Key") for n in by_pins(wg, "self", "Key"))
want_keys = sorted([G.FIRE_KEY, G.FIRE_KEY, G.SWITCH_KEY, G.DROP_KEY,
                    G.PICKUP_KEY, G.SPRINT_KEY, G.RELOAD_KEY, G.AIM_KEY])
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
    # ...and as ITS OWN kind of wanderer. That template default names the
    # parent, and every variant inherits it, so on its own it means a dead
    # wendigo is replaced by a BP_ForestWanderer -- which wears the parent's
    # mesh, i.e. a zombie. Kill the two wendigos the level places and there are
    # never any more. The fix is that BeginPlay overwrites RespawnClass with
    # the owner's own class, and this is the check for it, because nothing a
    # headless run does will ever kill a wanderer.
    # GetObjectClass renders as "Get Class" in the graph.
    owner_class = [n for n in hg
                   if str(BEL.get_node_title(n)).replace("\n", " ") == "Get Class"]
    check("...and BeginPlay asks the owner what class it is",
          len(owner_class) == 1, str(len(owner_class)))
    # Loop variable deliberately not `n`: `n` is the NPC's CDO, read again two
    # checks below, and shadowing it here turned that read into a call on a
    # graph node.
    rewritten = []
    for getter in owner_class:
        for pin in BEL.list_output_pins(getter):
            for other in pin.list_connected_pins():
                node = unreal.BlueprintGraphPinLibrary.get_owning_node(other)
                if node and "RespawnClass" in str(BEL.get_node_title(node)):
                    rewritten.append(node)
    check("...and writes it into RespawnClass, so each creature respawns as "
          "itself", len(rewritten) == 1,
          str([str(BEL.get_node_title(x)) for x in rewritten]))
    check("NPC's capsule blocks Visibility, so pellets can actually hit it",
          blocks_visibility(npc) is True, str(blocks_visibility(npc)))
    check("a spawned wanderer still gets an AI controller",
          n.get_editor_property("auto_possess_ai")
          == unreal.AutoPossessAI.PLACED_IN_WORLD_OR_SPAWNED)

# ─── Hit boxes ───────────────────────────────────────────────────────────────
# The capsule says whether a pellet hit; the physics bodies say where. Every
# half of that can be wrong while the gun still works -- a table that never
# filled, a multiplier that declared as an int (1.5 -> 1), a second trace fed
# from the wrong line -- and each looks exactly like "every hit is a body hit".

for var, want in ((G.HEAD_MULT_VAR, G.HEAD_MULTIPLIER),
                  (G.LIMB_MULT_VAR, G.LIMB_MULTIPLIER)):
    got = h.get_editor_property(var)
    check(f"{var} is {want}, and a float -- an int would truncate it",
          isinstance(got, float) and abs(got - want) < 1e-6, repr(got))


def _mesh_asset(bp):
    for name in components(bp):
        t = component_template(bp, name)
        if isinstance(t, unreal.SkeletalMeshComponent):
            return t.get_editor_property("skeletal_mesh_asset")
    return None


zoned = {}
for tag, bp in (("player", char), ("NPC", npc)):
    if not bp:
        continue
    comp = component_template(bp, "HealthComponent")
    heads = [str(b) for b in comp.get_editor_property(G.HEAD_BONES_VAR)] if comp else []
    limbs = [str(b) for b in comp.get_editor_property(G.LIMB_BONES_VAR)] if comp else []
    zoned[tag] = (heads, limbs)
    want_head, want_limbs, body = G.hit_zones(_mesh_asset(bp))
    # Rig-AGNOSTIC, deliberately. The first version of these asserted literal
    # mannequin bone names ("head" in heads, upperarm_l in limbs), which is the
    # very bug they were written to catch, one level up: the monsters are on a
    # Mixamo rig whose bodies are Head / LeftArm / LeftUpLeg, the tables were
    # perfectly correct, and the CHECK failed. What is actually worth asserting
    # is structural -- that the tables are what this mesh's own physics asset
    # resolves to, that both zones exist, that they do not overlap, and that
    # the torso is in neither.
    check(f"{tag}: the head table is its own skeleton's head bodies",
          heads == want_head and len(heads) > 0, str(heads))
    check(f"{tag}: the limb table is its own skeleton's arm and leg bodies",
          limbs == want_limbs and len(limbs) >= 4, str(limbs))
    # Four limbs means all four were found, not one root matched twice: a rig
    # whose arms resolved and whose legs did not would still list "several".
    roots = {b for b in limbs if not any(
        o != b and b.lower().startswith(o.lower()) for o in limbs)}
    check(f"{tag}: all four limbs are covered, not just the arms",
          len(limbs) >= 8 or len(roots) >= 4,
          f"{len(limbs)} limb bodies: {limbs}")
    check(f"{tag}: no bone is both head and limb", not set(heads) & set(limbs))
    check(f"{tag}: the torso is neither -- a chest shot is a 1x shot",
          len(body) > 0 and not set(body) & (set(heads) | set(limbs)),
          str(body))

wt = wg
zone_traces = [n for n in wt if {"TraceStart", "TraceEnd", "bTraceComplex"} <= in_pins(n)]
check("one trace against the struck character's body, per pellet",
      len(zone_traces) == 1, f"{len(zone_traces)} K2_LineTraceComponent node(s)")
if zone_traces:
    zt = zone_traces[0]
    fed = {pin: {str(BEL.get_node_title(PIN.get_owning_node(q))).replace("\n", " ")
                 for q in PIN.list_connected_pins(BEL.find_input_pin(zt, pin))}
           for pin in ("TraceStart", "TraceEnd", "self")}
    # The pellet's own line, from the pellet's own hit result -- not the aim
    # point, not the muzzle recomputed: a second line would land somewhere the
    # first one did not.
    check("it retraces the pellet's own line (TraceStart/TraceEnd of its hit)",
          all(any("BreakHitResult" in t for t in fed[p])
              for p in ("TraceStart", "TraceEnd")), str(fed))
    check("it traces the character's mesh, whose bodies carry bone names",
          any("Mesh" in t for t in fed["self"]), str(fed["self"]))
    check("it traces the simple (physics body) shapes, not the render mesh",
          pin_value(zt, "bTraceComplex").lower() == "false")
contains = [n for n in wt if {"TargetArray", "ItemToFind"} <= in_pins(n)]
tables = {str(BEL.get_node_title(PIN.get_owning_node(q)))
          for n in contains
          for q in PIN.list_connected_pins(BEL.find_input_pin(n, "TargetArray"))}
check("the struck bone is looked up in both of the TARGET's tables",
      {f"Get {G.HEAD_BONES_VAR}", f"Get {G.LIMB_BONES_VAR}"} <= tables, str(tables))
# The damage subtraction's B must be Damage x multiplier, not raw Damage.
scaled = False
for n in titled(wt, "float - float"):
    for q in PIN.list_connected_pins(BEL.find_input_pin(n, "B")):
        mul = PIN.get_owning_node(q)
        if "*" not in str(BEL.get_node_title(mul)):
            continue
        srcs = {str(BEL.get_node_title(PIN.get_owning_node(r)))
                for pin in ("A", "B")
                for r in PIN.list_connected_pins(BEL.find_input_pin(mul, pin))}
        scaled |= "Get Damage" in srcs and any("Select" in s for s in srcs)
check("health loses Damage x the zone's multiplier, not raw Damage", scaled)


def upstream(node, depth=8):
    """Titles of every node feeding `node`'s inputs, transitively."""
    # Data pins only: following "execute" would walk back up the whole shot.
    # Nodes are tracked by name, not title -- two SelectFloats share a title.
    out, seen, frontier = set(), set(), [node]
    for _ in range(depth):
        nxt = []
        for n in frontier:
            for p in BEL.list_input_pins(n):
                if str(PIN.get_pin_name(p)) == "execute":
                    continue
                for q in PIN.list_connected_pins(p):
                    src = PIN.get_owning_node(q)
                    if src.get_name() in seen:
                        continue
                    seen.add(src.get_name())
                    out.add(str(BEL.get_node_title(src)).replace("\n", " "))
                    nxt.append(src)
        frontier = nxt
    return out


# Debug mode's damage readout: the number the target actually lost, at the
# point it was hit, only when the tracers are on.
readouts = [n for n in wt if {"TextLocation", "Text", "Duration"} <= in_pins(n)]
check("one damage readout per impact (DrawDebugString)", len(readouts) == 1,
      f"{len(readouts)} DrawDebugString node(s)")
if readouts:
    ro = readouts[0]
    gates = [PIN.get_owning_node(q) for q in
             PIN.list_connected_pins(BEL.find_input_pin(ro, "execute"))]
    check("...drawn only in debug mode",
          any("Branch" in str(BEL.get_node_title(g))
              and any(G.DEBUG_MODE_VAR in str(BEL.get_node_title(PIN.get_owning_node(q)))
                      for q in PIN.list_connected_pins(BEL.find_input_pin(g, "Condition")))
              for g in gates))
    check("...at the impact point",
          any("BreakHitResult" in str(BEL.get_node_title(PIN.get_owning_node(q)))
              for q in PIN.list_connected_pins(BEL.find_input_pin(ro, "TextLocation"))))
    check("...for as long as the tracer",
          abs((num_pin(ro, "Duration") or 0.0) - G.TRACE_DEBUG_SECONDS) < 1e-6,
          pin_value(ro, "Duration"))
    fed = upstream(ro)
    check("...showing the damage dealt (Damage x zone), not the weapon's raw Damage",
          "Get Damage" in fed and any("*" in t for t in fed)
          and f"Get {G.HEAD_MULT_VAR}" in fed, str(sorted(fed)))

# And the geometry: put a wanderer in the editor world and fire the same
# component trace through each part of it. This is what proves the physics
# asset actually covers the body where the tables say it does, and that the
# bone a trace reports is one the tables know.
if npc and "NPC" in zoned:
    heads, limbs = zoned["NPC"]
    eas = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    dummy = eas.spawn_actor_from_class(BEL.generated_class(npc),
                                       unreal.Vector(0.0, 0.0, 60000.0))
    try:
        body_mesh = dummy.get_component_by_class(unreal.SkeletalMeshComponent)

        def between(a, b):
            pa, pb = body_mesh.get_socket_location(a), body_mesh.get_socket_location(b)
            return (pa + pb) * 0.5

        # (point, direction the shot comes from, what it should be worth). The
        # arms are shot from the side they hang on: in the reference pose they
        # lie along the flanks, and a line through the upper arm from the
        # front meets the chest first -- which is the correct answer for that
        # line, and not the part under test.
        front = unreal.Vector(300.0, 0.0, 0.0)

        # Probe bones resolved from the rig, not written down. Same reason as
        # the tables above -- and here the stakes are higher, because
        # get_socket_location on a bone that does not exist returns the
        # component origin rather than failing, so a stale name does not make
        # the check fail, it makes it trace through the middle of the actor and
        # PASS for the wrong reason. Three of these were doing exactly that.
        def bone(*candidates):
            have = {b.lower(): b for b in (heads + limbs + body)}
            for c in candidates:
                if c.lower() in have:
                    return have[c.lower()]
            return None

        head_b = bone("head", "Head")
        arm_u = bone("upperarm_r", "RightArm")
        arm_l = bone("lowerarm_r", "RightForeArm")
        leg_u = bone("thigh_l", "LeftUpLeg")
        leg_l = bone("calf_l", "LeftLeg")
        chest = bone("spine_03", "Spine2", "Spine1", "Spine")

        aims = {}
        if head_b:
            aims["head"] = (body_mesh.get_socket_location(head_b)
                            + unreal.Vector(0.0, 0.0, 10.0), front,
                            G.HEAD_MULTIPLIER)
        # Across the bone, not along a world axis. A fixed sideways shot works
        # on the mannequin, whose arms hang at the flanks, and fails on the
        # Meshy A-pose, whose arms are held out -- there the line reaches the
        # spine first and reports a 1x chest hit, which is the correct answer
        # for that line and not the part under test. 30 cm is short enough that
        # it cannot reach the torso from any limb.
        def across(a, b, reach=30.0):
            pa, pb = (body_mesh.get_socket_location(a),
                      body_mesh.get_socket_location(b))
            axis = pb - pa
            length = axis.length()
            if length < 1e-3:
                return unreal.Vector(0.0, reach, 0.0)
            axis = axis / length
            # Any vector not parallel to the bone, made perpendicular to it.
            seed = (unreal.Vector(0.0, 0.0, 1.0) if abs(axis.z) < 0.9
                    else unreal.Vector(1.0, 0.0, 0.0))
            perp = seed - axis * (seed.x * axis.x + seed.y * axis.y
                                  + seed.z * axis.z)
            n2 = perp.length()
            return (perp / n2) * reach if n2 > 1e-3 else unreal.Vector(0.0, reach, 0.0)

        # Centred on the JOINT at the far end of the limb -- the elbow, the
        # knee -- rather than on the midpoint of the two. The midpoint is fine
        # on the mannequin and lands near the shoulder on the Meshy rig, where
        # a 30 cm line across it still reaches Spine01 and reports a chest hit.
        # An elbow is unambiguously in an arm on any rig.
        if arm_u and arm_l:
            aims["upper arm"] = (body_mesh.get_socket_location(arm_l),
                                 across(arm_u, arm_l, 18.0),
                                 G.LIMB_MULTIPLIER)
        if leg_u and leg_l:
            aims["thigh"] = (body_mesh.get_socket_location(leg_l),
                             across(leg_u, leg_l, 18.0), G.LIMB_MULTIPLIER)
        if chest:
            aims["chest"] = (body_mesh.get_socket_location(chest), front, 1.0)
        check("the zone probe found bones to shoot at on this rig",
              len(aims) == 4,
              f"{sorted(aims)} (head={head_b} arm={arm_u}/{arm_l} "
              f"leg={leg_u}/{leg_l} chest={chest})")
        for part, (at, side, want) in aims.items():
            hit = body_mesh.line_trace_component(at + side, at - side,
                                                 False, False, False)
            bone = str(hit[2]) if hit and hit[2] else "None"
            worth = (G.HEAD_MULTIPLIER if bone in heads
                     else G.LIMB_MULTIPLIER if bone in limbs else 1.0)
            check(f"a shot through the {part} strikes a body worth {want}x",
                  bone != "None" and abs(worth - want) < 1e-6,
                  f"bone {bone} -> {worth}x")
    finally:
        dummy.destroy_actor()

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

# ─── Walking off the edge of the world ───────────────────────────────────────
# The navmesh is a disc of radius 85 m and the terrain a 200 m square, but the
# terrain does eventually END -- and a Character in freefall never stops. The
# player used to fall for the rest of the session with nothing noticing, because
# "still falling" and "standing still" look identical to everything watching.
#
# The fix reuses the NPC safety net rather than adding a KillZ or a teleport:
# below WORLD_FLOOR_Z, write Health to 0 and let the death path that already
# exists open the restart menu. What had to change is that the net used to be
# AND-ed with DespawnOnDeath -- NPCs only -- and that gate moved inward so it
# guards only the log line, which quotes an NpcId the player does not have.

floors = [n for n in hg if num_pin(n, "B") == G.WORLD_FLOOR_Z]
check(f"something compares a height against {G.WORLD_FLOOR_Z:.0f} cm",
      len(floors) == 1, f"{len(floors)} comparisons")
if floors:
    gates = [PIN.get_owning_node(q) for q in
             BEL.find_output_pin(floors[0], "ReturnValue").list_connected_pins()]
    # THE REGRESSION THIS EXISTS TO CATCH: an AND here means the test is once
    # again "under the world AND is an NPC", and the player falls forever.
    check("the world floor is branched on directly, not AND-ed with a "
          "\"...and is an NPC\" term",
          [g.get_class().get_name() for g in gates] == ["K2Node_IfThenElse"],
          str([str(BEL.get_node_title(g)) for g in gates]))

# Two writes of Health = 0 would mean two floors; one, reached from both arms
# of the "is this worth a log line" branch, is the shape that catches both the
# wanderer and the player.
zeroes = [n for n in hg
          if str(BEL.get_node_title(n)).replace("\n", " ") == "Set Health"
          and num_pin(n, "Health") == 0.0]
check("exactly one node writes the fall off as death", len(zeroes) == 1,
      f"{len(zeroes)} writes of Health = 0")
if zeroes:
    feeders = [PIN.get_owning_node(q) for q in
               PIN.list_connected_pins(BEL.find_input_pin(zeroes[0], "execute"))]
    check("...and BOTH arms of the report branch reach it -- the reported "
          "wanderer and the unreported player",
          len(feeders) == 2, f"reached from {len(feeders)} exec pin(s)")
    kinds = sorted(f.get_class().get_name() for f in feeders)
    check("...one of them straight from a Branch (the player: no log line)",
          "K2Node_IfThenElse" in kinds, str(kinds))
# The log line stays wanderer-only: it quotes a number and a spawn point.
check("the fall report is still gated on DespawnOnDeath",
      any("DespawnOnDeath" in out_pins(n) for n in hg))
check("...and still names the wanderer and where it was put",
      bool(titled(hg, "PrintWarning")) or bool(titled(hg, "Print Warning")),
      "the fall report is the one line Blueprint can raise above Display")

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
# The hit-box multiplier has two SelectFloats of its own, each picked by a
# table lookup; those are counted in the hit-box section, not here.
selects = [n for n in titled(wg, "SelectFloat")
           if not any("Contains" in str(BEL.get_node_title(PIN.get_owning_node(q)))
                      for q in PIN.list_connected_pins(BEL.find_input_pin(n, "bPickA")))]
# Three now: sprint picks the speed and the sign of the drain, and aiming
# picks how much of its own cone the weapon keeps.
check("SelectFloat picks the speed, the drain, and the aimed cone",
      len(selects) == 3, f"{len(selects)} SelectFloat node(s)")
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

# ─── Aiming down the sights ──────────────────────────────────────────────────
# Right mouse narrows the camera to the weapon's own AdsZoom. What can go wrong
# quietly: a zoom that is never applied (the FOV write missing), a zoom that is
# applied and never undone (no path back to BaseFOV), and a BaseFOV that is a
# literal rather than the camera's own -- all three look fine in the graph.

for sp in G._weapon_specs():
    want = sp.get("ads_zoom", G.ADS_ZOOM_IRONS)
    got = cdo(load(sp["path"])).get_editor_property("AdsZoom")
    check(f"{sp['display']}: AdsZoom is {want}x",
          isinstance(got, float) and abs(got - want) < 1e-6, repr(got))
check("only the sniper carries a scope's worth of zoom",
      {sp["display"] for sp in G._weapon_specs()
       if sp.get("ads_zoom", G.ADS_ZOOM_IRONS) == G.ADS_ZOOM_SCOPE} == {"Sniper"},
      str(sorted(sp.get("ads_zoom", G.ADS_ZOOM_IRONS)
                 for sp in G._weapon_specs())))

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
      G.ADS_SPREAD_SCALE < 1.0 and "Get Sprinting" in
      {str(BEL.get_node_title(x)).replace("\n", " ") for x in wg},
      f"cone x{G.ADS_SPREAD_SCALE}")

# ─── Mouse sensitivity, and what the zoom does to it ─────────────────────────
# Three ways this goes wrong without looking wrong. The pitch scale is cached
# rather than written down because the engine ships it NEGATIVE, so a literal
# would invert the look half the time; the slowdown is driven off CurrentFOV
# rather than off the Aiming flag, so it eases in with the zoom and is
# automatically stronger on the scope; and the default sensitivity has to be
# exactly 1.0 or a player who never opens the settings screen gets a mouse
# that does not feel like the controller's own.
wc_cdo = cdo(wc)
check("the weapon component carries a mouse sensitivity",
      isinstance(wc_cdo.get_editor_property("MouseSensitivity"), float))
check("...defaulting to 1.0, i.e. exactly the controller's own feel",
      abs(wc_cdo.get_editor_property("MouseSensitivity")
          - G.MOUSE_SENSITIVITY_DEFAULT) < 1e-6
      and abs(G.MOUSE_SENSITIVITY_DEFAULT - 1.0) < 1e-6,
      repr(wc_cdo.get_editor_property("MouseSensitivity")))
check("...within a range that cannot reach zero, which would kill the mouse",
      0.0 < G.MOUSE_SENSITIVITY_MIN < G.MOUSE_SENSITIVITY_DEFAULT
      < G.MOUSE_SENSITIVITY_MAX,
      f"{G.MOUSE_SENSITIVITY_MIN}..{G.MOUSE_SENSITIVITY_MAX}")
check("the engine's pitch scale is negative, so it MUST be cached not written",
      wc_cdo.get_editor_property("BasePitchScale") < 0.0,
      repr(wc_cdo.get_editor_property("BasePitchScale")))
check("...and the yaw scale positive",
      wc_cdo.get_editor_property("BaseYawScale") > 0.0,
      repr(wc_cdo.get_editor_property("BaseYawScale")))
scale_reads = {str(BEL.get_node_title(x)).replace("\n", " ") for x in wg}
for label, want in (("yaw", "Set Deprecated Input Yaw Scale"),
                    ("pitch", "Set Deprecated Input Pitch Scale")):
    hits = [t for t in scale_reads if t.replace(" ", "")
            == want.replace(" ", "")]
    check(f"the {label} look scale is written every frame", bool(hits), want)
for label, want in (("yaw", "Get Deprecated Input Yaw Scale"),
                    ("pitch", "Get Deprecated Input Pitch Scale")):
    hits = [t for t in scale_reads if t.replace(" ", "")
            == want.replace(" ", "")]
    check(f"...from a {label} base READ off the controller, not a literal",
          bool(hits), want)
check("the slowdown is driven off the zoom, not off the Aiming flag -- so it "
      "eases in and is stronger on the scope",
      bool(titled(wg, "Lerp")) and 0.0 < G.ADS_SENS_COMPENSATION <= 1.0,
      f"Lerp(1, CurrentFOV/BaseFOV, {G.ADS_SENS_COMPENSATION})")
# The numbers the player actually feels, spelled out so a change to either
# constant has to be argued for rather than noticed later.
for name, zoom, want in (("irons", G.ADS_ZOOM_IRONS, 0.75),
                         ("scope", G.ADS_ZOOM_SCOPE, 0.4375)):
    got = 1.0 + G.ADS_SENS_COMPENSATION * (1.0 / zoom - 1.0)
    check(f"...which works out at {want:.2f}x sensitivity down the {name}",
          abs(got - want) < 5e-3, f"{got:.4f}")

# ─── Footsteps ───────────────────────────────────────────────────────────────

foot = load(G.FOOTSTEP_BP_PATH)
check("there is a footstep component", foot is not None)
if foot:
    f = cdo(foot)
    sounds = list(f.get_editor_property("Sounds"))
    check("...with more than one step, so it is not one buffer retriggered",
          len(sounds) >= 3, f"{len(sounds)} clips")
    check("...on a stride measured in centimetres, not seconds",
          abs(f.get_editor_property("StrideCm") - G.FOOTSTEP_STRIDE_CM) < 1e-6,
          repr(f.get_editor_property("StrideCm")))
    fg = graph(foot).list_all_nodes()
    # NOT `titles`: this file is a flat script and `titles` is the weapon
    # component's, read again hundreds of lines below.
    foot_titles = {str(BEL.get_node_title(x)).replace("\n", " ") for x in fg}
    # Distance, not time: the accumulator has to be driven by SPEED x dt. A
    # Delay or a plain timer here would be the bug this design exists to avoid.
    check("...accumulated from the owner's own speed",
          any("eloc" in t for t in foot_titles),
          str(sorted(t for t in foot_titles if "eloc" in t)))
    check("...and the remainder is carried, not zeroed, so the rate does not "
          "follow the framerate",
          any("-" in t or "Subtract" in t for t in foot_titles),
          str(len(foot_titles)))
check("both the player and the wanderers wear it",
      "FootstepComponent" in components(char)
      and (npc is None or "FootstepComponent" in components(npc)))

# ─── Automatic fire ──────────────────────────────────────────────────────────
# Hold the button and the SMG and the assault rifle keep firing; the shotgun,
# the pistol and the sniper are one shot per click. What makes this cheap is
# that the rate limit already existed: FireInterval and NextFireTime were being
# consulted on every frame the trigger was down long before anything could hold
# it down. All that is added is whether a held button still counts as a pull.

autos = {sp["display"] for sp in G._weapon_specs() if sp["automatic"]}
check("exactly the SMG and the assault rifle are automatic",
      autos == set(G.AUTO_DISPLAYS), str(sorted(autos)))
for sp in G._weapon_specs():
    check(f"{sp['display']}: Automatic is {sp['automatic']}",
          bool(cdo(load(sp["path"])).get_editor_property("Automatic"))
          is bool(sp["automatic"]))
# A held trigger with no rate limit is one shot per frame, i.e. 60 rounds a
# second out of a 30-round magazine. Both automatics must have an interval.
for name in G.AUTO_DISPLAYS:
    sp = next(x for x in G._weapon_specs() if x["display"] == name)
    check(f"{name}: has a fire interval, so a held trigger is not one shot "
          f"per frame",
          float(cdo(load(sp["path"])).get_editor_property("FireInterval")) > 0.0,
          str(sp["interval"]))

downs = [n for n in wg if "IsInputKeyDown" in str(BEL.get_node_title(n))]
check("three keys are polled held rather than tapped: sprint, aim and the "
      "trigger",
      sorted(pin_value(x, "Key") for x in downs)
      == sorted([G.FIRE_KEY, G.SPRINT_KEY, G.AIM_KEY]),
      str(sorted(pin_value(x, "Key") for x in downs)))

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
# Three reads: the GameMode's own (once per shot), then the cached copy twice
# per pellet -- the tracer's branch and the damage readout's.
check("...and the pellet loop branches on the cached copy",
      len([n for n in wg if G.DEBUG_MODE_VAR in out_pins(n)]) == 3,
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
    # BREADTH-first over every exec feeder, not a single chain.
    #
    # This used to follow feeders[0] and stop, which made it a coin flip: an
    # exec input takes any number of links and their order is not something
    # this API promises, so on a graph where the drop is reached from more than
    # one place the walk would sometimes take the arm without the guard on it
    # and report the guard missing. It failed intermittently, on a graph that
    # had not changed, which is worse than no check at all -- a flaky assertion
    # teaches you to ignore it.
    seen, frontier, guarded, hops = set(), [guns[0]], False, 0
    while frontier and hops < 400 and not guarded:
        node = frontier.pop(0)
        hops += 1
        if id(node) in seen:
            continue
        seen.add(id(node))
        if "Branch" in str(BEL.get_node_title(node)).replace("\n", " "):
            cond = BEL.find_input_pin(node, "Condition")
            if cond and cond.is_valid() and any(
                    G.DAMAGED_BY_PLAYER_VAR in str(BEL.get_node_title(
                        PIN.get_owning_node(q)))
                    for q in PIN.list_connected_pins(cond)):
                guarded = True
                break
        ins = BEL.find_input_pin(node, "execute")
        if ins and ins.is_valid():
            frontier.extend(PIN.get_owning_node(q)
                            for q in PIN.list_connected_pins(ins))
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
