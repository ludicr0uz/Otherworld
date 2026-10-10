"""verify.body_setting -- the player's body is ONE setting
(asset_pipeline/player_body.py PLAYER_BODY), and everything that names the
player's body follows it: the skin, the stance clips, the worn mesh, and for
a body that stands in for another, the bodies it can be shot in.
"""

import dataclasses

import unreal

from asset_pipeline import catalog, player_body, quaternius_paths
from asset_pipeline.metahuman_paths import (
    BODY_HIDE_PARAM, BODY_MATERIAL_BARE, BODY_MESH_WHOLE, CLOTHING,
)
from combat.hit_bodies import _bodies
from combat.skin import SKIN_ADVENTURER, SKIN_BOUND, SKIN_METAHUMAN, player_skin
from combat.verify.common import _mesh_asset, check, load
from combat.verify.fixtures import char
from uebp.graph import _component_object, _find_handle


def _mesh_path(name):
    return f"/Game/Sourced/Characters/SKM_{name}/SKM_{name}"


def check_one_setting():
    name = player_body.PLAYER_NAME
    spec = catalog.by_id(player_body.PLAYER_BODY)
    check("the player's body is a catalog character",
          spec.dest.endswith(f"/SKM_{name}"), f"{player_body.PLAYER_BODY} -> {spec.dest}")

    paths = {f.name: getattr(SKIN_ADVENTURER, f.name)
             for f in dataclasses.fields(SKIN_ADVENTURER)
             if isinstance(getattr(SKIN_ADVENTURER, f.name), str)
             and getattr(SKIN_ADVENTURER, f.name).startswith("/Game/")}
    off = {k: v for k, v in paths.items() if f"_{name}" not in v}
    check(f"every asset the adventurer skin names is {name}'s", not off and len(paths) >= 9,
          str(off or len(paths)))
    check("the stance, kneel and throw clips are retargeted onto that body",
          quaternius_paths.UAL_CHARACTERS == (name,), str(quaternius_paths.UAL_CHARACTERS))

    if not unreal.EditorAssetLibrary.does_asset_exist(_mesh_path(name)):
        # A checkout that has never run the asset pipeline: the mannequin.
        return
    worn = _mesh_asset(char) if char else None
    # Which mesh that is depends on how the body is rigged
    # (player_body.PLAYER_RIG): on its own skeleton, or bound to the
    # mannequin's -- the same body either way, and not Quinn.
    bound = (player_body.PLAYER_RIG == "mannequin"
             and unreal.EditorAssetLibrary.does_asset_exist(SKIN_BOUND.mesh))
    # A "metahuman" rig wears the MetaHuman under its hidden mannequin: the
    # Character's own mesh is then the mannequin, and the generated body is
    # not drawn.
    metahuman = player_body.PLAYER_RIG == "metahuman" and player_skin().metahuman
    # The hidden mesh is the mannequin, or under the motion matching the UEFN
    # one (combat/skin.SKIN_GAS).
    want = (player_skin().mesh if metahuman and player_skin().gas
            else SKIN_METAHUMAN.mesh if metahuman else SKIN_BOUND.mesh if bound
            else _mesh_path(name))
    hidden = want
    check(f"the player wears {'the MetaHuman over the mannequin' if metahuman else name}, "
          "not the mannequin fallback: all of its assets are built",
          player_skin().mesh == want and worn is not None
          and worn.get_path_name().split(".")[0] == hidden,
          f"skin {player_skin().mesh}, worn {worn.get_path_name() if worn else None}")
    if metahuman:
        # The MetaHuman starts in its underwear: the three garment
        # components are there for the LOD sync, bare and not drawn.
        told = {}
        for part in CLOTHING:
            handle = _find_handle(char, part)
            comp = _component_object(handle) if handle else None
            told[part] = comp and (comp.get_editor_property("skeletal_mesh_asset"),
                                   comp.get_editor_property("visible"),
                                   comp.get_editor_property("hidden_in_game"))
        check(f"the MetaHuman's {', '.join(CLOTHING)} components wear no mesh and are "
              "hidden (combat/metahuman_body.py)",
              all(v == (None, False, True) for v in told.values()), str(told))
        body = _component_object(_find_handle(char, "Body"))
        worn_mats = [m.get_path_name().split(".")[0] if m else None
                     for m in body.get_editor_property("override_materials")]
        bare = unreal.EditorAssetLibrary.load_asset(BODY_MATERIAL_BARE)
        hide = (unreal.MaterialEditingLibrary.get_material_instance_scalar_parameter_value(
            bare, BODY_HIDE_PARAM) if bare else None)
        body_mesh = body.get_editor_property("skeletal_mesh_asset")
        check(f"...and its body is the whole one ({BODY_MESH_WHOLE.rsplit('/', 1)[1]}: Taro's "
              f"has the skin under his clothes cut out) in "
              f"{BODY_MATERIAL_BARE.rsplit('/', 1)[1]}, the sample's material copied with "
              f"{BODY_HIDE_PARAM} at 0",
              body_mesh is not None
              and body_mesh.get_path_name().split(".")[0] == BODY_MESH_WHOLE
              and worn_mats == [BODY_MATERIAL_BARE] and hide == 0.0,
              f"{body_mesh.get_path_name() if body_mesh else None}, {worn_mats}, "
              f"{BODY_HIDE_PARAM} {hide}")
    if bound or metahuman:
        # What follows is about the per-body skeleton's physics asset.
        return

    reference = player_body.reference_of(name)
    if not reference:
        return
    # A body that stands in for another was normalised to it on the way in.
    mine, theirs = load(_mesh_path(name)), load(_mesh_path(reference))
    check(f"{reference}, the body {name} stands in for, is imported",
          isinstance(theirs, unreal.SkeletalMesh), _mesh_path(reference))
    if not isinstance(theirs, unreal.SkeletalMesh):
        return
    have = sorted(_bodies(mine.get_editor_property("physics_asset")))
    want = sorted(_bodies(theirs.get_editor_property("physics_asset")))
    check(f"{name} has a physics body on every bone {reference} has one on "
          "(asset_pipeline/physics_template.py)", have == want,
          f"{sorted(set(want) ^ set(have))}")


def run():
    check_one_setting()
