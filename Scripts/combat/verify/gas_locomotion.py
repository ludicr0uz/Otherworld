"""verify.gas_locomotion -- the player's motion-matching base (task G3): the
Game Animation Sample's anim Blueprint as combat/gas_locomotion.py patched
it, and the body that runs it. Nothing while the player wears the mannequin
(gas_locomotion_consts.GAS_LOCOMOTION off, or the sample not imported).

What it plays in a game is probes/probe_gas_locomotion.py's.
"""

import unreal

from asset_pipeline.gas_bridge_paths import PLAYER_SOCKETS
from combat.gas_locomotion import enum_values, graphs, server_branches, slot_in_line
from combat.gas_locomotion_consts import (
    ADDED_VARS, CHOOSER, EYE_CLASSES, FIELDS_SET, FOLEY_BANK_TABLE, FOLEY_BANK_VAR,
    FOLEY_COMPONENT, FOLEY_SILENT_BANK,
    HISTORY_CLASS, WALK_BELOW_CMS, WEAPON_LAYERS,
)
from combat.server_anim_consts import CLIENT_PIN, SERVER_PIN, SERVER_POSE_VAR
from combat.skin import player_skin, worn_skin
from combat.verify.common import _mesh_asset, check, component_template, components
from combat.verify.fixtures import char
from combat.verify.server_anim import _class, _flag_written_once, _sources, _title
from uebp.graph import BEL, PIN, _assets

FEET = ("AnimGraphNode_FootPlacement", "AnimGraphNode_LegIK")
SEARCH = "AnimGraphNode_MotionMatching"


def _linked(pin):
    return bool(PIN.list_connected_pins(pin))


def check_properties(bp, ed):
    nodes = list(ed.list_all_nodes())
    titles = [_title(n) for n in nodes]
    check("the motion matching reads its character off the movement component, on any "
          "Character: no call through the sample's pawn interface is left",
          not [n for n in nodes if _class(n) == "K2Node_Message"]
          and "TryGetPawnOwner" in [t.replace(" ", "") for t in titles],
          str(sorted({t for t in titles if "Pawn" in t or "Properties" in t})))
    makes = [n for n in nodes if _class(n) == "K2Node_MakeStruct"
             and "Character Properties" in _title(n)]
    fed = sorted(str(PIN.get_pin_name(p)).split("_")[0]
                 for m in makes for p in BEL.list_input_pins(m) if _linked(p))
    check(f"...one struct, with {len(FIELDS_SET)} fields of it set from the character "
          "and the rest left at the sample's defaults (Stance among them: no crouch yet)",
          len(makes) == 1 and fed == sorted(FIELDS_SET), str(fed))
    sprint = [n for n in nodes if _title(n).replace(" ", "") == "IsSprinting"]
    paces = [n for n in nodes if _title(n).replace(" ", "") == "GetMaxSpeed"]
    limits = {float(PIN.get_pin_value(BEL.find_input_pin(c, "B")) or 0.0)
              for p in paces for c in (PIN.get_owning_node(q)
                                       for q in PIN.list_connected_pins(
                                           BEL.find_output_pin(p, "ReturnValue")))}
    check("...the gait is read off the game's own movement: Sprint while the C++ "
          f"movement sprints, Walk under {WALK_BELOW_CMS:g} cm/s of pace",
          len(sprint) >= 1 and limits == {WALK_BELOW_CMS}, f"{len(sprint)} / {limits}")
    values = enum_values(bp)
    check("...and the sample's enums still have the members the numbers were read for",
          {"WALK", "RUN", "SPRINT"} <= set(values["Gait"])
          and {"ON_GROUND", "IN_AIR"} <= set(values["MovementMode"])
          and {"STRAFE", "ORIENT_TO_MOVEMENT"} <= set(values["RotationMode"]), str(values))
    cdo = unreal.get_default_object(BEL.generated_class(bp))
    kept = [v for v in ADDED_VARS if _has(cdo, v)]
    check("...and the landing is kept on the anim instance (when, and the fall's last "
          "velocity)", len(kept) == len(ADDED_VARS), str([str(v) for v in kept]))


def _has(obj, name):
    try:
        obj.get_editor_property(name)
        return True
    except Exception:
        return False


def check_anim_graph(bp, anim):
    check("the weapon layers are off the motion-matching base (G3): its montage slot is "
          f"{'in' if WEAPON_LAYERS else 'out of'} the pose line, as WEAPON_LAYERS says",
          slot_in_line(anim) == WEAPON_LAYERS, f"in line: {slot_in_line(anim)}")
    branches = server_branches(anim)
    roots = [n for n in anim.list_all_nodes() if _class(n) == "AnimGraphNode_Root"]
    check("the motion-matching graph has ONE branch on what a dedicated server needs "
          f"of it (a Blend Poses by bool on {SERVER_POSE_VAR})",
          len(branches) == 1 and len(roots) == 1, f"{len(branches)} branch(es)")
    if len(branches) != 1 or len(roots) != 1:
        return
    branch = branches[0]
    written, how = _flag_written_once(bp)
    default = unreal.get_default_object(BEL.generated_class(bp)).get_editor_property(
        SERVER_POSE_VAR)
    check("...false by default and written once, from IsDedicatedServer, as the anim "
          "instance starts", written and default is False, f"{how}; default {default!r}")
    times = list(branch.get_editor_property("node").get_editor_property("blend_time"))
    check("...with no blend between its arms", times == [0.0, 0.0], str(times))
    server = {_class(n) for n in arm_of(roots[0], branch, SERVER_PIN)}
    client = {_class(n) for n in arm_of(roots[0], branch, CLIENT_PIN)}
    check("...a server skips the feet (Foot Placement and Leg IK trace the ground and "
          "are for the eye), which a client keeps",
          not server & set(FEET) and set(FEET) <= client,
          f"on the server arm: {sorted(server & set(EYE_CLASSES))}")
    check("...and both arms search the databases and write the pose history the next "
          "search reads", {SEARCH, HISTORY_CLASS} <= server and {SEARCH, HISTORY_CLASS} <= client,
          str(sorted(c for c in server if "Search" in c or "Motion" in c)))
    check("...the server's pose is the one the feet's nodes start from",
          feet_start_at_server_pose(branch))


def arm_of(root, branch, take):
    """verify.server_anim.arm, for a graph with another blend by bool of its
    own (the sample's aim offset): only ``branch`` is the server's."""
    seen, stack = [], [root]
    while stack:
        node = stack.pop()
        if node in seen:
            continue
        seen.append(node)
        ups = _sources(node, take) if node == branch else _sources(node)
        stack.extend(n for n in ups if _class(n).startswith("AnimGraphNode_"))
    return seen


def feet_start_at_server_pose(branch):
    """Whether the client arm, walked back through the feet's nodes, ends on
    the node the server arm is taken from."""
    server = PIN.list_connected_pins(BEL.find_input_pin(branch, SERVER_PIN))
    client = PIN.list_connected_pins(BEL.find_input_pin(branch, CLIENT_PIN))
    if not server or not client:
        return False
    pin, walked = client[0], 0
    while _class(PIN.get_owning_node(pin)) in EYE_CLASSES:
        node = PIN.get_owning_node(pin)
        source = next(p for p in BEL.list_input_pins(node)
                      if str(PIN.get_pin_name(p)) in ("ComponentPose", "LocalPose"))
        pin, walked = PIN.list_connected_pins(source)[0], walked + 1
    return (PIN.get_owning_node(pin) == PIN.get_owning_node(server[0])
            and walked == len(EYE_CLASSES))


def check_body():
    worn = _mesh_asset(char)
    missing = [s for s in PLAYER_SOCKETS if worn is None or worn.find_socket(s) is None]
    check("the UEFN mannequin the player wears has the sockets the game attaches to "
          "(the mannequin's own, copied: asset_pipeline/gas_player_mesh.py)",
          not missing, str(missing))
    foley = component_template(char, FOLEY_COMPONENT)
    bank = foley.get_editor_property(FOLEY_BANK_VAR) if foley else None
    check("the player carries the sample's foley component with a sound bank that holds "
          "nothing: its clips' footstep notifies fire into it and play nothing",
          bank is not None and bank.get_path_name().split(".")[0] == FOLEY_SILENT_BANK
          and len(bank.get_editor_property(FOLEY_BANK_TABLE)) == 0,
          bank.get_path_name() if bank else "no component, or no bank")
    check("...and the game's footsteps are still BP_FootstepComponent's",
          "FootstepComponent" in components(char))
    check("the sample's chooser of databases is here", _assets().does_asset_exist(CHOOSER),
          CHOOSER)
    keyed = player_skin()
    check("the weapon layers are still built, on the rig they are keyed on and into the "
          "anim Blueprint the player no longer runs (G4 brings them over)",
          keyed.anim_bp != worn_skin().anim_bp and _assets().does_asset_exist(keyed.anim_bp),
          keyed.anim_bp)


def run():
    skin = worn_skin()
    if not skin.gas:
        unreal.log_warning("[VERIFY] gas_locomotion: the player wears the mannequin; skipped")
        return
    bp = _assets().load_asset(skin.anim_bp)
    check("the player's anim Blueprint is the Game Animation Sample's", bp is not None,
          skin.anim_bp)
    if bp is None:
        return
    anim, _events, properties = graphs(bp)
    check_properties(bp, properties)
    check_anim_graph(bp, anim)
    check_body()
