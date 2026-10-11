"""player_clip_swap -- the editor's half of Scripts/dev/swap_clip.py: one role
of player_clips.csv onto another Mixamo clip, and nothing else rebuilt.

    1. the clip alone is imported onto SK_XBot and retargeted onto the
       player's skeleton (mixamo_player.one_player_clip; a copy already
       there is kept, so swapping back rewrites none of it)
    2. a swing's strike is read off the copy's hand (player_clips.strike_s)
    3. the role's row is rewritten
    4. what is baked from the row is rebuilt: the role's own melee clip
       (melee_clips.build_melee_clips(skin, [role])) and the weapons build's
       steps player_clips.ROLES names for it
    5. a melee role's bake is held to verify/melee_clips.py's checks

A step that fails puts the row back.  The outcome is written as JSON for the
command to print (``result``).  The clip the role left stays on disk, its
source and its copy: prune() deletes the ones no row names.
"""

import json
import sys
import time

import unreal

from asset_pipeline import player_clips
from asset_pipeline.gas_bridge_paths import PLAYER_FAMILY
from asset_pipeline.mixamo_paths import PACKS, PLAYER_PACKS, mixamo_anim_dir, pack_dir
from asset_pipeline.mixamo_player import one_player_clip
from asset_pipeline.rig_util import _log

EAL = unreal.EditorAssetLibrary
FPS = 30


def hand_forward(clip, bone):
    """``bone``'s place ahead of the body (cm, +Y), a sample per frame."""
    length = clip.get_play_length()
    out = []
    for i in range(int(round(length * FPS)) + 1):
        pose = unreal.AnimPoseExtensions.get_anim_pose_at_time(
            clip, min(i / float(FPS), length), unreal.AnimPoseEvaluationOptions())
        out.append(unreal.AnimPoseExtensions.get_bone_pose(
            pose, bone, unreal.AnimPoseSpaces.WORLD).translation.y)
    return out


def _forget():
    """Drop the modules that read the table as they loaded."""
    for name in [m for m in sys.modules
                 if m.split(".")[0] in ("asset_pipeline", "combat", "uebp", "net")]:
        del sys.modules[name]


def _rebuild(role):
    """Bake what the row feeds; returns the melee checks as (label, ok)."""
    _forget()
    from asset_pipeline.player_clips import ROLES
    from combat import build_steps
    from combat.melee_clips import MELEE_CLIPS, build_melee_clips
    from combat.skin import player_skin
    from combat.verify import common
    from combat.verify.melee_clips import check_axe_falls, check_melee_clip
    skin = player_skin()
    rows = [r for r in MELEE_CLIPS if r.role == role]
    if rows:
        build_melee_clips(skin, [role])
    if ROLES[role][1]:
        build_steps.run(",".join(ROLES[role][1]))
    del common.PASS[:], common.FAIL[:]
    for row in rows:
        check_melee_clip(row, skin)
    if role == "axe_swing":
        check_axe_falls()
    return [(label, True) for label in common.PASS] + [(label, False) for label in common.FAIL]


def swap(role, short, stem, hit_s=None, reimport=False, result=None):
    """Put ``role`` on the clip ``stem`` of the pack ``short``.  ``hit_s``
    overrides the strike read off a swing; the clip the role has already
    keeps its row's."""
    began = time.time()
    player_clips.check_role(role)
    old = next(r for r in player_clips.read_rows() if r.role == role)
    out = {"role": role, "old": player_clips.line_of(old), "ok": False}
    try:
        clip, made = one_player_clip(short, stem, reimport)
        out.update(made=list(made), length_s=round(clip.get_play_length(), 2))
        if role in player_clips.SWINGS:
            from combat.skin import player_skin
            from combat.tuning import COMBAT
            forward = hand_forward(clip, player_skin().pose_bones["hand_r"])
            found = player_clips.strike_s(forward, FPS)
            out.update(detected_s=found, impact_s=COMBAT.knife_impact_s,
                       reach_cm=[round(min(forward), 1), round(max(forward), 1)])
            if hit_s is None:
                # The same clip again (a rebake, a --reimport) keeps a strike
                # that was given by hand.
                hit_s = old.hit_s if (short, stem) == (old.pack, old.clip) else found
            if hit_s is None:
                raise RuntimeError(
                    f"{stem}: the hand travels {max(forward) - min(forward):.0f} cm forward, "
                    f"under {player_clips.MIN_TRAVEL_CM:.0f}: no strike to time the blow to "
                    "(give one with --hit-s if it is a swing all the same)")
            if not COMBAT.knife_impact_s <= hit_s <= clip.get_play_length():
                raise RuntimeError(
                    f"{stem}: a strike at {hit_s:.2f} s is outside the clip "
                    f"({COMBAT.knife_impact_s:.2f} s of wind-up, {clip.get_play_length():.2f} s long)")
        else:
            hit_s = None
        new = player_clips.Row(role, short, stem, hit_s)
        out["new"] = player_clips.line_of(new)
        player_clips.write_row(new)
        try:
            checks = _rebuild(role)
        except Exception:
            player_clips.write_row(old)
            _forget()
            raise
        out.update(checks=checks, ok=all(ok for _, ok in checks))
        _log(f"{role}: {out['old']} -> {out['new']}"
             + (f" (strike read at {out['detected_s']} s)" if "detected_s" in out else ""))
    except Exception as exc:
        out["error"] = str(exc)
        raise
    finally:
        out["seconds"] = round(time.time() - began, 1)
        if result:
            with open(result, "w", encoding="utf-8") as f:
                json.dump(out, f, indent=1)
    return out


def prune(result=None):
    """Delete the player's clips no row names: the copies on the player's
    skeleton, and their sources in the packs that are the player's alone (a
    pack the creatures wear too keeps every clip)."""
    rows = player_clips.read_rows()
    keep = {f"{r.pack}_{r.clip}" for r in rows}
    shared = {short for _, short in PACKS}
    folders = [mixamo_anim_dir(PLAYER_FAMILY)] + [
        pack_dir(short) for _, short in PLAYER_PACKS if short not in shared]
    gone = []
    for folder in folders:
        if not EAL.does_directory_exist(folder):
            continue
        for path in EAL.list_assets(folder, recursive=False):
            pkg = str(path).split(".")[0]
            if "_Mx_" in pkg and pkg.rsplit("_Mx_", 1)[1] not in keep:
                if not EAL.delete_asset(pkg):
                    raise RuntimeError(f"could not delete {pkg}")
                gone.append(pkg)
    _log(f"pruned {len(gone)} clips no role names")
    if result:
        with open(result, "w", encoding="utf-8") as f:
            json.dump({"ok": True, "pruned": gone}, f, indent=1)
    return gone
