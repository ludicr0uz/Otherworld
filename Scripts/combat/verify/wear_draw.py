"""verify.wear_draw -- a worn garment drawn on the body.

Mirrors weapon_component/wear_draw.py: the DrawWorn event (what it sets on
the garment's component, on and off, and that a dedicated server does none of
it, and the skin it cuts out of the body: asset_pipeline/body_cover.py) and
its six calls from the wears, the take-off and the drop. Checked on the wiring; probes/probe_clothing.py wears the jacket and the pants in a game.
"""

import unreal

from asset_pipeline.metahuman_paths import (
    BODY_COVER_MASK, BODY_MATERIAL_BARE, BODY_SKIN_WORN, CLOTHING, COVER_PARTS,
)
from combat.verify.common import check, graph, in_pins, pin_value
from combat.verify.fixtures import wc, wg
from combat.verify.record import _upstream
from combat.record_vars import VIEW_WORN
from combat.verify.wear import _chain, _feeders, _title
from combat.wear_tuning import DRAW_WORN, STARTER_PANTS_CLASS_VAR, WORN_PART_VAR, WORN_VAR
from combat.weapon_component.wear_draw import (
    ITEM_PARAM, ON_PARAM, TICK_ALWAYS, TICK_OPTION_VAR,
)


def _on(n):
    # "" too: a literal equal to its pin's default reads back empty once the
    # graph is loaded from disk (CLAUDE.md).
    return (pin_value(n, ON_PARAM) or "false").lower() == "true"


def _view_calls(calls):
    """The client's view's (view_worn.py): on for the garment it spawned, off
    for one it is about to destroy."""
    made = [n for n in calls if any("SpawnTransform" in in_pins(f)
                                    for f in _feeders(n, ITEM_PARAM))]
    ended = [n for n in calls if n not in made
             and "DestroyActor" in _title(_chain(n, 2)[-1]).replace(" ", "")]
    return made, ended


def _starter_calls(calls):
    """BeginPlay's (starter_worn.py): on for the garment spawned from
    StarterPantsClass."""
    return [n for n in calls for f in _feeders(n, ITEM_PARAM)
            if "SpawnTransform" in in_pins(f)
            and f"Get {STARTER_PANTS_CLASS_VAR}" in [_title(c) for c in _feeders(f, "Class")]]


def check_draw_calls():
    every = [n for n in wg if _title(n).replace(" ", "") == DRAW_WORN
             and ON_PARAM in in_pins(n)]
    starter = _starter_calls(every)
    check(f"BeginPlay draws the pants a player starts in ({STARTER_PANTS_CLASS_VAR}, "
          f"starter_worn.py): one {DRAW_WORN} on, for the garment it spawned",
          [_on(n) for n in starter] == [True], f"{len(starter)} calls")
    every = [n for n in every if n not in starter]
    made, ended = _view_calls(every)
    check(f"a client's view draws what it was sent ({VIEW_WORN}): {DRAW_WORN} on for the "
          "garment it spawned, off for one of another class and for one past the "
          "rows, each before it is destroyed",
          [_on(n) for n in made] == [True] and [_on(n) for n in ended] == [False, False],
          f"{len(made)} on, {len(ended)} off")
    calls = [n for n in every if n not in made and n not in ended]
    check(f"{DRAW_WORN} is called six times more: on by the wear and the dragged wear, off "
          "for the garment each swaps out, by the take-off and by the drop of a worn one",
          sorted(_on(n) for n in calls) == [False, False, False, False, True, True],
          str([pin_value(n, ON_PARAM) for n in calls]))
    check(f"...each handed an {ITEM_PARAM}",
          bool(calls) and all(len(_feeders(n, ITEM_PARAM)) == 1 for n in calls))
    writes = [n for n in wg if "bSizeToFit" in in_pins(n)
              and any(_title(f) == f"Get {WORN_VAR}" for f in _feeders(n, "TargetArray"))]
    # Worn[slot] is a pure read: an off-call fed by it after the slot is
    # rewritten would be handed the new garment, or nothing.
    read = [n for n in calls if any(
        _title(g) == f"Get {WORN_VAR}" for f in _feeders(n, ITEM_PARAM)
        for g in _feeders(f, "TargetArray"))]
    check(f"...and one fed by a read of {WORN_VAR}[slot] is called before the slot is "
          "rewritten, which is the next thing done (the swaps' and the take-off's: "
          "three)",
          len(read) == 3 and all(not _on(n) and _chain(n, 2)[-1] in writes for n in read),
          str([_title(_chain(n, 2)[-1]) for n in read]))


def check_draw_event():
    event = graph(wc).find_event_node(DRAW_WORN)
    check(f"the weapon component has the {DRAW_WORN} event", bool(event))
    if not event:
        return
    body = [n for n in wg if event in _upstream(n)]
    first = [n for n in body if event in _feeders(n, "execute")]
    check("...which first asks whether this is a dedicated server, and draws nothing "
          "on one",
          len(first) == 1 and any("Dedicated" in _title(f).replace(" ", "")
                                  for f in _feeders(first[0], "Condition")),
          str([_title(n) for n in first]))
    meshes = [n for n in body if "NewMesh" in in_pins(n)]
    check("...sets the garment's mesh on its component, and no mesh when it comes off",
          sorted(len(_feeders(n, "NewMesh")) for n in meshes) == [0, 1], str(len(meshes)))
    leads = [n for n in body if "NewLeaderBoneComponent" in in_pins(n)]
    check("...leads it by the body's pose on the body's skeleton only: one leader set, "
          "and cleared for a mesh on its own skeleton and when it comes off",
          sorted(len(_feeders(n, "NewLeaderBoneComponent")) for n in leads) == [0, 0, 1],
          str(len(leads)))
    ticks = [n for n in body if _title(n).startswith("Set")
             and TICK_OPTION_VAR in in_pins(n)]
    check("...poses it whether or not it is rendered, as the body is",
          len(ticks) == 1 and pin_value(ticks[0], TICK_OPTION_VAR) == TICK_ALWAYS,
          str([pin_value(n, TICK_OPTION_VAR) for n in ticks]))
    hides = [n for n in body if "NewHidden" in in_pins(n)]
    check("...and shows it, or hides it again",
          sorted((pin_value(n, "NewHidden") or "false").lower() for n in hides)
          == ["false", "true"], str([pin_value(n, "NewHidden") for n in hides]))
    cuts = [n for n in body if {"ParameterName", "ParameterValue"} <= set(in_pins(n))]
    check(f"...and cuts the skin under it out of the body while it is worn: the body's "
          f"material parameter named by its {WORN_PART_VAR} at 1 on, 0 off, set on the "
          "part's parent past a cast that held",
          sorted(float(pin_value(n, "ParameterValue") or 0.0) for n in cuts) == [0.0, 1.0]
          and all(_title(f) == f"Get {WORN_PART_VAR}" for n in cuts
                  for f in _feeders(n, "ParameterName"))
          and all(any("Cast" in _title(f).replace(" ", "") for f in _feeders(n, "self"))
                  for n in cuts),
          str([(pin_value(n, "ParameterValue"), [_title(f) for f in _feeders(n, "self")])
               for n in cuts]))


def check_body_cut():
    """The material the body wears cuts each part's skin by its parameter."""
    eal, mel = unreal.EditorAssetLibrary, unreal.MaterialEditingLibrary
    bare = eal.load_asset(BODY_MATERIAL_BARE)
    parent = bare and bare.get_editor_property("parent")
    check(f"the body's material ({BODY_MATERIAL_BARE.rsplit('/', 1)[1]}) is an instance of "
          f"{BODY_SKIN_WORN.rsplit('/', 1)[1]} (asset_pipeline/body_cover.py)",
          bool(parent) and parent.get_path_name().split(".")[0] == BODY_SKIN_WORN,
          parent.get_path_name() if parent else str(bare))
    mat = eal.load_asset(BODY_SKIN_WORN)
    if not mat:
        return
    params = list(mel.get_scalar_parameter_names(mat))
    defaults = {p: mel.get_material_default_scalar_parameter_value(mat, p)
                for p in COVER_PARTS if p in params}
    check(f"...which is Masked, with a parameter per garment drawn on the body "
          f"({', '.join(COVER_PARTS)}), each 0 by default, so a bare body is whole",
          mat.get_editor_property("blend_mode") == unreal.BlendMode.BLEND_MASKED
          and set(COVER_PARTS) == set(CLOTHING)
          and defaults == {p: 0.0 for p in COVER_PARTS},
          f"{mat.get_editor_property('blend_mode')}, {defaults}")
    # The graph behind the opacity mask, not get_used_textures: that list is
    # the shader map's, and a headless editor never compiles a new one.
    used, todo = [], [mel.get_material_property_input_node(
        mat, unreal.MaterialProperty.MP_OPACITY_MASK)]
    while todo:
        node = todo.pop()
        if not node:
            continue
        if isinstance(node, unreal.MaterialExpressionTextureSample):
            t = node.get_editor_property("texture")
            used.append(t.get_path_name().split(".")[0] if t else None)
        todo.extend(mel.get_inputs_for_material_expression(mat, node))
    tex = eal.load_asset(BODY_COVER_MASK)
    check(f"...cut by {BODY_COVER_MASK.rsplit('/', 1)[1]} (its opacity mask samples it), "
          f"a linear mask with no mips",
          BODY_COVER_MASK in used and bool(tex) and not tex.get_editor_property("srgb")
          and tex.get_editor_property("mip_gen_settings")
          == unreal.TextureMipGenSettings.TMGS_NO_MIPMAPS,
          str(used))


def run():
    check_draw_calls()
    check_draw_event()
    check_body_cut()
