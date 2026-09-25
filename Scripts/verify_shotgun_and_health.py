"""
verify_shotgun_and_health.py — in-engine checks for the shotgun and health.

    UnrealEditor-Cmd <uproject> -ExecutePythonScript="<abs>/Scripts/verify_shotgun_and_health.py" -NoUI -stdout

Reads the *saved* assets back, so it catches anything that compiled but did not
persist.  Two failure modes on this project are invisible any other way:

  * an FKey pin set to struct text imports back as a key named "(" -- it
    compiles, it saves, and the trigger never fires;
  * add_member_variable accepts a default value, reports success, and leaves the
    property at zero -- a health component that starts dead.

Logs `[VERIFY]` lines and a PASS/FAIL tally.
"""

import os
import re
import sys

import unreal

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_shotgun_and_health as G

BEL = unreal.BlueprintEditorLibrary
BGE = unreal.BlueprintGraphEditor
PIN = unreal.BlueprintGraphPinLibrary
SDL = unreal.SubobjectDataBlueprintFunctionLibrary

_results = []


def check(name, condition, detail=""):
    _results.append((name, bool(condition)))
    mark = "ok  " if condition else "FAIL"
    unreal.log_warning(f"[VERIFY] {mark} {name}{(' — ' + detail) if detail else ''}")


def pin_names(node, inputs=True):
    """Pin names with spaces stripped -- macro pins are "First Index"."""
    pins = BEL.list_input_pins(node) if inputs else BEL.list_output_pins(node)
    return {str(PIN.get_pin_name(p)).replace(" ", "") for p in pins}


def value(node, pin_name):
    p = BEL.find_input_pin(node, pin_name)
    return p.get_pin_value() if p and p.is_valid() else None


def components(bp):
    """{variable name: component template} for a blueprint's subobjects."""
    sds = unreal.get_engine_subsystem(unreal.SubobjectDataSubsystem)
    out = {}
    for h in sds.k2_gather_subobject_data_for_blueprint(bp):
        data = sds.k2_find_subobject_data_from_handle(h)
        if data:
            out[str(SDL.get_variable_name(data))] = SDL.get_object(data)
    return out


def main():
    eas = unreal.get_editor_subsystem(unreal.EditorAssetSubsystem)

    # ─── the skeleton actually has the socket the weapon hangs from ──────────
    skm = eas.load_asset("/Game/Characters/Mannequins/Meshes/SKM_Quinn_Simple")
    check(f"{G.GRIP_SOCKET} is a real socket on SKM_Quinn_Simple",
          skm.find_socket(G.GRIP_SOCKET) is not None)

    # ─── BP_HealthComponent ─────────────────────────────────────────────────
    check("health component exists", eas.does_asset_exist(G.HEALTH_BP_PATH))
    health_bp = eas.load_asset(G.HEALTH_BP_PATH)
    check("health parented to ActorComponent",
          BEL.get_blueprint_parent_class(health_bp) ==
          unreal.ActorComponent.static_class())
    hcdo = unreal.get_default_object(BEL.generated_class(health_bp))
    for field in ("Health", "MaxHealth"):
        got = hcdo.get_editor_property(field)
        check(f"{field} starts at {G.START_HEALTH:.0f}",
              abs(float(got) - G.START_HEALTH) < 1e-6, str(got))

    # ─── BP_ShotgunComponent ────────────────────────────────────────────────
    check("shotgun component exists", eas.does_asset_exist(G.SHOTGUN_BP_PATH))
    gun_bp = eas.load_asset(G.SHOTGUN_BP_PATH)
    gcdo = unreal.get_default_object(BEL.generated_class(gun_bp))
    check(f"Damage is {G.PELLET_DAMAGE} per pellet",
          abs(float(gcdo.get_editor_property("Damage")) - G.PELLET_DAMAGE) < 1e-6,
          str(gcdo.get_editor_property("Damage")))
    check(f"Range is {G.WEAPON_RANGE:.0f} cm",
          abs(float(gcdo.get_editor_property("Range")) - G.WEAPON_RANGE) < 1e-6,
          str(gcdo.get_editor_property("Range")))

    ed = BGE.get_graph_editor_by_name(gun_bp, "EventGraph")
    nodes = ed.list_all_nodes()
    check("shotgun graph has no node errors", not ed.list_nodes_with_errors(),
          str(len(ed.list_nodes_with_errors())))
    check("shotgun graph has no node warnings", not ed.list_nodes_with_warnings(),
          str(len(ed.list_nodes_with_warnings())))

    def by_pins(*required):
        want = {r.replace(" ", "") for r in required}
        return [n for n in nodes if want <= pin_names(n)]

    tick = ed.find_event_node("ReceiveTick")
    check("Event Tick present", tick is not None)
    if tick:
        then = BEL.find_then_pin(tick)
        # Not cosmetic: the compiler only sets bCanEverTick when this pin is
        # connected, and bCanEverTick is unreachable from Python.
        check("Event Tick is connected (this is what enables ticking)",
              bool(then and then.list_connected_pins()))
    check("Event BeginPlay present",
          ed.find_event_node("ReceiveBeginPlay") is not None)

    keys = sorted(value(n, "Key") for n in by_pins("Key"))
    check(f"fires on exactly {sorted(G.FIRE_KEYS)}",
          keys == sorted(G.FIRE_KEYS), str(keys))

    gun_cdo_tick = gcdo.get_editor_property("primary_component_tick")
    check("ticks after the player controller has processed input",
          gun_cdo_tick.get_editor_property("tick_group") ==
          unreal.TickingGroup.TG_POST_PHYSICS,
          str(gun_cdo_tick.get_editor_property("tick_group")))

    attach = by_pins("SocketName")
    check("one attach-to-socket call", len(attach) == 1, str(len(attach)))
    if attach:
        check(f"attaches to {G.GRIP_SOCKET}",
              value(attach[0], "SocketName") == G.GRIP_SOCKET,
              str(value(attach[0], "SocketName")))
        rules = [value(attach[0], r) for r in
                 ("LocationRule", "RotationRule", "ScaleRule")]
        # SnapToTarget would discard the measured grip offset.
        check("attach keeps the weapon's relative transform",
              rules == ["KeepRelative"] * 3, str(rules))

    traces = by_pins("Start", "End", "TraceChannel")
    check("one pellet trace (inside the loop)", len(traces) == 1, str(len(traces)))
    if traces:
        check("pellet traces are drawn so firing is visible",
              value(traces[0], "DrawDebugType") ==
              ("ForDuration" if G.TRACE_DEBUG_SECONDS > 0 else "None"),
              str(value(traces[0], "DrawDebugType")))
        check("traces the Visibility channel",
              value(traces[0], "TraceChannel") == "TraceTypeQuery1",
              str(value(traces[0], "TraceChannel")))
        # Without this the shot hits the player's own capsule or the weapon.
        check("trace ignores the shooter",
              value(traces[0], "bIgnoreSelf") == "true",
              str(value(traces[0], "bIgnoreSelf")))

    loops = by_pins("FirstIndex", "LastIndex")
    check("one ForLoop over the pellets", len(loops) == 1, str(len(loops)))
    if loops:
        check(f"{G.PELLET_COUNT} pellets per shot",
              value(loops[0], "LastIndex") == str(G.PELLET_COUNT - 1),
              f"LastIndex={value(loops[0], 'LastIndex')}")

    lookups = by_pins("ComponentClass")
    check("one health lookup on the hit actor", len(lookups) == 1)
    if lookups:
        check("looks up BP_HealthComponent",
              G.HEALTH_CLASS_PATH in str(value(lookups[0], "ComponentClass")),
              str(value(lookups[0], "ComponentClass")))
    check("damage is clamped at zero",
          any(value(n, "Min") == "0.0" for n in by_pins("Min", "Max")))

    # ─── the player ─────────────────────────────────────────────────────────
    char = eas.load_asset(G.CHARACTER_BP_PATH)
    comps = components(char)
    for name in ("HealthComponent", "ShotgunComponent", G.SHOTGUN_ROOT):
        check(f"player has {name}", name in comps)
    part_names = [p[0] for p in G._parts()]
    check("all weapon parts present",
          all(n in comps for n in part_names),
          f"{sum(n in comps for n in part_names)}/{len(part_names)}")
    # Re-running the builder used to stack a second, auto-named copy of the
    # weapon on the character, because deleting the root left its parts orphaned
    # and they then held the names the new parts wanted.
    debris = [n for n in comps if re.fullmatch(r"StaticMesh\d*", n)]
    check("no orphaned weapon parts from an earlier run", not debris, str(debris))
    check("exactly one weapon root", list(comps).count(G.SHOTGUN_ROOT) == 1)

    root = comps.get(G.SHOTGUN_ROOT)
    if root:
        want = G._grip_rotation()
        got = root.get_editor_property("relative_rotation")
        check("weapon aims down the skeleton's own muzzle direction",
              abs(got.yaw - want.yaw) < 0.01 and abs(got.pitch - want.pitch) < 0.01,
              f"pitch={got.pitch:.2f} yaw={got.yaw:.2f}")

    missing_mesh = [n for n in part_names
                    if comps.get(n) and not comps[n].get_editor_property("static_mesh")]
    check("every weapon part has a mesh", not missing_mesh, str(missing_mesh))
    unmaterialed = [n for n in part_names
                    if comps.get(n) and
                    not list(comps[n].get_editor_property("override_materials"))]
    check("every weapon part has a material", not unmaterialed, str(unmaterialed))

    # The player's own health component is what the HUD reads.
    if "HealthComponent" in comps:
        check("player's health component is BP_HealthComponent",
              "BP_HealthComponent" in comps["HealthComponent"].get_class().get_name())

    # ─── the NPC ────────────────────────────────────────────────────────────
    npc = eas.load_asset(G.NPC_BP_PATH)
    npc_comps = components(npc)
    check("NPC has a health component", "HealthComponent" in npc_comps)
    if "HealthComponent" in npc_comps:
        check("NPC's health component is BP_HealthComponent",
              "BP_HealthComponent" in
              npc_comps["HealthComponent"].get_class().get_name())

    passed = sum(1 for _, ok in _results if ok)
    unreal.log_warning(f"[VERIFY] {passed}/{len(_results)} checks passed")
    for name, ok in _results:
        if not ok:
            unreal.log_warning(f"[VERIFY] failed: {name}")


main()
