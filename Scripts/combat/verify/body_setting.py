"""verify.body_setting -- the player's body is ONE setting
(asset_pipeline/player_body.py PLAYER_BODY), and everything that names the
player's body follows it: the skin, the stance clips, the worn mesh, and for
a body that stands in for another, the bodies it can be shot in.
"""

import dataclasses

import unreal

from asset_pipeline import catalog, player_body, quaternius_paths
from combat.hit_bodies import _bodies
from combat.skin import SKIN_ADVENTURER, player_skin
from combat.verify.common import _mesh_asset, check, load
from combat.verify.fixtures import char


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
    check(f"the player wears {name}, not the mannequin fallback: all of its "
          "assets are built",
          player_skin().mesh == SKIN_ADVENTURER.mesh and worn is not None
          and worn.get_path_name().split(".")[0] == _mesh_path(name),
          f"skin {player_skin().mesh}, worn {worn.get_path_name() if worn else None}")

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
