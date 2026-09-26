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
    check("DefaultSlot feeds the blend pose, so it cannot override the legs",
          blend_src == ["AnimGraphNode_Slot"], str(blend_src))
    base_src = [PIN.get_owning_node(q).get_class().get_name()
                for q in PIN.list_connected_pins(
                    BEL.find_input_pin(blends[0], "BasePose"))]
    check("locomotion feeds the base pose", base_src == ["AnimGraphNode_StateMachine"],
          str(base_src))

slots = [n for n in anim_nodes if n.get_class().get_name() == "AnimGraphNode_Slot"]
if slots:
    name = str(slots[0].get_editor_property("node").get_editor_property("slot_name"))
    check(f"the slot is still named {G.AIM_SLOT}", name == G.AIM_SLOT, name)

# ─── The two weapons ─────────────────────────────────────────────────────────

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
    check(f"{tag}: has a fire sound",
          d.get_editor_property("FireSound") is not None)
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
    check("the two weapons are held at different angles",
          a.get_editor_property("GripRotation").to_tuple()
          != b.get_editor_property("GripRotation").to_tuple())
    check("the two weapons show different colours in the inventory",
          a.get_editor_property("SlotColor").to_tuple()
          != b.get_editor_property("SlotColor").to_tuple())

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
want_keys = sorted([G.FIRE_KEY, G.SWITCH_KEY, G.DROP_KEY, G.PICKUP_KEY])
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

# The regression this whole rework exists to fix: the pellet cone must start at
# the muzzle, not at the camera behind the player's shoulder.
traces = by_pins(wg, "Start", "End", "TraceChannel")
check("there are two traces (pellets, and the drop's ground probe)",
      len(traces) == 2, str(len(traces)))
from_muzzle = []
for t in traces:
    src = [PIN.get_owning_node(q) for q in
           PIN.list_connected_pins(BEL.find_input_pin(t, "Start"))]
    from_muzzle += [n for n in src if {"T", "Location"} <= in_pins(n)]
check("a pellet trace starts at the weapon's muzzle transform, not the camera",
      len(from_muzzle) == 1, f"{len(from_muzzle)} trace(s) fed by TransformLocation")

check("firing plays a sound", bool(by_pins(wg, "Sound", "Location")))
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

# ─── Installation ────────────────────────────────────────────────────────────

char = load(G.CHARACTER_BP_PATH)
cnames = set(components(char))
check("player carries HealthComponent + WeaponComponent",
      {"HealthComponent", "WeaponComponent"} <= cnames,
      str(sorted(cnames)))
stale = cnames & G.OLD_SHOTGUN_PARTS
check("the old welded shotgun is gone from the player", not stale, str(sorted(stale)))

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
    check("a spawned wanderer still gets an AI controller",
          n.get_editor_property("auto_possess_ai")
          == unreal.AutoPossessAI.PLACED_IN_WORLD_OR_SPAWNED)

# ─── Summary ─────────────────────────────────────────────────────────────────

unreal.log_warning(f"[VERIFY] {len(PASS)} passed, {len(FAIL)} failed")
for f in FAIL:
    unreal.log_warning(f"[VERIFY]   FAILED: {f}")
