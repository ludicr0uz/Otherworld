"""The crouch and the crawl clips in the running game: the body comes down
crouched, and lies on the ground prone with the held gun still up in both
hands.

No key can be injected, so the probe writes the weapon component's Stance
(1 crouch, 2 prone) as the C and Z toggles do, and waits for the eased
PoseCrouch / PoseProne weights on the anim instance to arrive. Heights are
measured from the ground under the capsule. The player starts holding the
issued shotgun, so the prone half also shows the aim layer over the crawl:
the chest propped, the gun level and in both hands. (A 60 deg tip of the
aimed chest, carried over from the procedural prone, put the hands 2 cm off
the ground; this probe is what caught it.)
"""

import unreal

from combat.carry_tuning import RAISE_FORCED_VAR
from combat.paths import WEAPON_COMP_BP_PATH, WEAPON_COMP_CLASS_PATH
from combat.skin import SKIN_ADVENTURER
from combat.weapon_component import vars as WV

WRITABLE = [(WEAPON_COMP_BP_PATH, WV.Stance), (WEAPON_COMP_BP_PATH, RAISE_FORCED_VAR)]

SETTLE_S = 0.6


def _heights(player):
    """{bone: cm above the ground under the capsule}."""
    mesh = player.get_editor_property("mesh")
    capsule = player.get_component_by_class(unreal.CapsuleComponent)
    ground = player.get_actor_location().z - capsule.get_scaled_capsule_half_height()
    b = SKIN_ADVENTURER.pose_bones
    bones = {"head": "Head", "hips": b["hips"], "hand_l": b["hand_l"],
             "hand_r": b["hand_r"], "foot_l": b["foot_l"], "foot_r": b["foot_r"]}
    return {k: mesh.get_socket_location(v).z - ground for k, v in bones.items()}


def _hand_gap(player):
    mesh = player.get_editor_property("mesh")
    b = SKIN_ADVENTURER.pose_bones
    return (mesh.get_socket_location(b["hand_l"])
            - mesh.get_socket_location(b["hand_r"])).length()


def _settle(p, anim, weight):
    yield lambda: p.get(anim, weight) > 0.98
    yield SETTLE_S


def probe(p):
    yield 0.5
    player = p.pawn()
    wc = p.component(player, WEAPON_COMP_CLASS_PATH)
    mesh = player.get_editor_property("mesh")
    worn = mesh.get_skeletal_mesh_asset().get_path_name().split(".")[0]
    p.check("the player wears the adventurer (the rig with the stance clips)",
            wc is not None and worn == SKIN_ADVENTURER.mesh, worn)
    if wc is None or worn != SKIN_ADVENTURER.mesh:
        return
    # A headless game renders nothing, and by default an unrendered mesh
    # never refreshes its bones.
    mesh.set_editor_property(
        "visibility_based_anim_tick_option",
        unreal.VisibilityBasedAnimTickOption.ALWAYS_TICK_POSE_AND_REFRESH_BONES,
        unreal.PropertyAccessChangeNotifyMode.NEVER)
    anim = mesh.get_anim_instance()
    # The gun is held up, as an aim key holds it (no key can be injected): at
    # rest, standing or crouched, it is carried lowered. Prone keeps it up.
    p.set(wc, RAISE_FORCED_VAR, True)
    yield 0.5
    stand = _heights(player)
    stand_gap = _hand_gap(player)
    p.note(f"standing: { {k: round(v) for k, v in stand.items()} }")

    p.set(wc, "Stance", 1)
    yield from _settle(p, anim, "PoseCrouch")
    low = _heights(player)
    p.note(f"crouched: { {k: round(v) for k, v in low.items()} }")
    p.check("crouched: the head comes down at least 40 cm, the feet stay down",
            stand["head"] - low["head"] >= 40.0
            and max(low["foot_l"], low["foot_r"]) < 25.0,
            f"head {stand['head']:.0f} -> {low['head']:.0f}")

    p.set(wc, "Stance", 2)
    yield from _settle(p, anim, "PoseProne")
    lying = _heights(player)
    p.note(f"prone: { {k: round(v) for k, v in lying.items()} }")
    p.check("prone: the hips lie low (under 30 cm) and the head under 80 cm",
            lying["hips"] < 30.0 and lying["head"] < 80.0,
            f"hips {lying['hips']:.0f}, head {lying['head']:.0f}")
    p.check("prone: nothing of the body is under the ground",
            min(lying.values()) > -5.0, f"lowest {min(lying.values()):.1f}")
    gap = _hand_gap(player)
    p.check("prone with the shotgun raised: both hands are up off the ground, as "
            "far apart as standing (the gun is still in both)",
            min(lying["hand_l"], lying["hand_r"]) > 15.0 and abs(gap - stand_gap) < 3.0,
            f"hands {lying['hand_l']:.0f} / {lying['hand_r']:.0f} cm up, "
            f"{stand_gap:.1f} -> {gap:.1f} cm apart")
    p.set(wc, RAISE_FORCED_VAR, False)
    yield SETTLE_S
    crawl = _heights(player)
    p.check("...and with no key held too: prone, the gun is not lowered",
            min(crawl["hand_l"], crawl["hand_r"]) > 15.0
            and abs(_hand_gap(player) - stand_gap) < 3.0,
            f"hands {crawl['hand_l']:.0f} / {crawl['hand_r']:.0f} cm up")
    p.set(wc, "Stance", 0)
