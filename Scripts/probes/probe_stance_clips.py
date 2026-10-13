"""The crouch and the prone clips in the running game: the body comes down
crouched, and lies on the ground prone, still and crawling, empty-handed and
with each gun up in both hands.

No key can be injected, so the probe writes the weapon component's Stance
(1 crouch, 2 prone) as the C and Z toggles do, and waits for the eased
PoseCrouch / PoseProne weights on the anim instance to arrive. Heights are
the mesh component's own (its origin is the capsule's bottom, which a check
holds it to), so a slope under the body does not read as a limb in the
ground. Prone (P1, the Free Animation Library's idle and forward crawl):

    still, empty-handed   the head under the capsule's top and steady, no
                          hand, knee or foot under the ground
    crawling forward      the same limbs through two seconds of it, and the
                          hips held where the capsule is (a clip that kept
                          its travel would slide forward and snap back)
    each gun              stood up with it raised, then prone still and
                          crawling: both hands off the ground and as far
                          apart as standing (the gun is still in both)

(A 60 deg tip of the aimed chest, carried over from the procedural prone, put
the hands 2 cm off the ground; this probe is what caught it.)
"""

LEVEL = "/Game/Maps/Lvl_Forest_200m"  # passes here, fails on the 50 m probe level (T11)
SYSTEMS = ('animation', 'movement')

import unreal

from combat.carry_tuning import RAISE_FORCED_VAR
from combat.paths import WEAPON_COMP_BP_PATH, WEAPON_COMP_CLASS_PATH
from combat.skin import skin_of_mesh
from combat.slot_tuning import HAND, PRIMARY
from combat.weapon_component import vars as WV
from graphics_menu.dev_consts import DEV_GUNS_REQUEST_VAR

HUD_BP_PATH = "/Game/UI/BP_GraphicsMenuHUD"
WRITABLE = [(WEAPON_COMP_BP_PATH, WV.Stance), (WEAPON_COMP_BP_PATH, RAISE_FORCED_VAR),
            (WEAPON_COMP_BP_PATH, WV.EquippedIndex), (HUD_BP_PATH, DEV_GUNS_REQUEST_VAR)]

SETTLE_S = 0.6
# A gun held prone is up off the ground in both hands: the rifle's fore hand is
# the lowest of them.
HANDS_UP_CM = 8.0
# The shotgun and the pistol are issued; the rifle is a drop, put in the bag
# by the dev-all-guns request.
GUNS = (("shotgun", "BP_Shotgun_C"), ("pistol", "BP_Pistol_C"),
        ("rifle", "BP_AssaultRifle_C"))
# A joint this far under the ground is a palm or a knee pressed into grass.
SINK_CM = 1.0
# Lying still the head holds within this; the prone idle is a breath.
HEAD_STEADY_CM = 2.0
# The head joint is the base of the skull: the crown is about this far above.
CROWN_CM = 15.0
# Crawling, the hips stay over the capsule within this (the clip is in place).
HIPS_HELD_CM = 3.0
STILL_S, CRAWL_S, CRAWL_START_S = 1.5, 2.5, 0.7
LIMBS = ("hand_l", "hand_r", "calf_l", "calf_r", "foot_l", "foot_r")


def _skin(player):
    mesh = player.get_editor_property("mesh")
    return skin_of_mesh(mesh.get_skeletal_mesh_asset().get_path_name())


def _heights(player):
    """{bone: cm above the mesh component's origin, the capsule's bottom}, and
    "ahead": how far the hips are ahead of it."""
    mesh = player.get_editor_property("mesh")
    skin = _skin(player)
    b = skin.pose_bones
    bones = {"head": skin.head, "hips": b["hips"], **{k: b[k] for k in LIMBS}}
    space = unreal.RelativeTransformSpace.RTS_COMPONENT
    at = {k: mesh.get_socket_transform(v, space).translation for k, v in bones.items()}
    return {**{k: v.z for k, v in at.items()}, "ahead": at["hips"].y}


def _mesh_off_ground(player):
    """How far the mesh component's origin is from the capsule's bottom (cm)."""
    capsule = player.get_component_by_class(unreal.CapsuleComponent)
    mesh = player.get_editor_property("mesh")
    return mesh.get_world_location().z - (player.get_actor_location().z
                                          - capsule.get_scaled_capsule_half_height())


def _hand_gap(player):
    mesh = player.get_editor_property("mesh")
    b = _skin(player).pose_bones
    return (mesh.get_socket_location(b["hand_l"])
            - mesh.get_socket_location(b["hand_r"])).length()


def _settle(p, anim, weight, up=True):
    yield lambda: (p.get(anim, weight) > 0.98) == up or (not up and p.get(anim, weight) < 0.02)
    yield SETTLE_S


def _watch(p, player, seconds, forward=0.0, skip=0.0):
    """Sample _heights every tick for ``seconds`` (walking ``forward`` if
    asked), into the list this returns with the step to yield."""
    seen, speeds = [], []
    world = p.world()
    t0 = unreal.GameplayStatics.get_time_seconds(world)

    def step():
        t = unreal.GameplayStatics.get_time_seconds(world) - t0
        if forward:
            player.add_movement_input(player.get_actor_forward_vector(), forward)
        if t >= skip:
            seen.append(_heights(player))
            speeds.append(player.get_velocity().length())
        return t >= seconds
    return seen, speeds, step


def _span(seen, key):
    return min(h[key] for h in seen), max(h[key] for h in seen)


def _prone_empty(p, player, real):
    """Lying still and crawling forward with nothing in the hands."""
    capsule = player.get_component_by_class(unreal.CapsuleComponent)
    top = 2.0 * capsule.get_scaled_capsule_half_height()
    off = _mesh_off_ground(player)
    p.check("prone: the mesh's origin is the capsule's bottom (within 3 cm), so the "
            "heights here are heights off the ground", abs(off) < 3.0, f"{off:.1f} cm")
    seen, _speeds, step = _watch(p, player, STILL_S)
    yield step
    lo, hi = _span(seen, "head")
    low = min(min(h[k] for h in seen) for k in LIMBS)
    p.note(f"prone, still: head {lo:.1f}..{hi:.1f}, hips {_span(seen, 'hips')}, "
           f"lowest limb {low:.1f}, capsule top {top:.0f}")
    if not real:
        p.note("no prone idle on this rig (the held crawl): the still and crawling "
               "checks of a real prone are skipped")
        return
    p.check(f"prone, still: the head stays under the capsule's top ({top:.0f} cm, the "
            f"crown {CROWN_CM:g} over the joint) and holds steady (within "
            f"{HEAD_STEADY_CM:g} cm over {STILL_S:g} s)",
            hi + CROWN_CM < top and hi - lo < HEAD_STEADY_CM,
            f"head {lo:.1f}..{hi:.1f} cm over {len(seen)} frames")
    p.check(f"prone, still: no hand, knee or foot is under the ground (by {SINK_CM:g} cm)",
            low > -SINK_CM, f"lowest {low:.1f}")
    seen, speeds, step = _watch(p, player, CRAWL_S, forward=1.0, skip=CRAWL_START_S)
    yield step
    lows = {k: _span(seen, k)[0] for k in LIMBS}
    ahead = _span(seen, "ahead")
    speed = sum(speeds) / max(len(speeds), 1)
    p.note(f"crawling: {speed:.0f} cm/s, hips {_span(seen, 'hips')}, head "
           f"{_span(seen, 'head')}, lows { {k: round(v, 1) for k, v in lows.items()} }")
    p.check("crawling forward: the player moves (over 60 cm/s)", speed > 60.0,
            f"{speed:.0f} cm/s over {len(seen)} frames")
    p.check(f"crawling forward: no foot, knee or hand goes under the ground (by "
            f"{SINK_CM:g} cm)", min(lows.values()) > -SINK_CM,
            str({k: round(v, 1) for k, v in lows.items()}))
    p.check(f"crawling forward: the hips stay over the capsule (within {HIPS_HELD_CM:g} "
            "cm: no slide forward and snap back each loop) and the head under its top",
            ahead[1] - ahead[0] < HIPS_HELD_CM and _span(seen, "head")[1] + CROWN_CM < top,
            f"hips {ahead[0]:.1f}..{ahead[1]:.1f} cm ahead, head to {_span(seen, 'head')[1]:.1f}")
    yield SETTLE_S


def _prone_with(p, player, wc, anim, label, cls):
    """Stand with ``cls`` raised, then lie down and crawl with it."""
    bag = [i.get_class().get_name() for i in p.get(wc, "Inventory")]
    p.check(f"{label}: it is in the bag", cls in bag, str(bag))
    if cls not in bag:
        return
    p.set(wc, "Stance", 0)
    yield from _settle(p, anim, "PoseProne", up=False)
    p.hold(wc, bag.index(cls))
    yield lambda: p.get(wc, "Held") is not None and \
        p.get(wc, "Held").get_class().get_name() == cls
    # Held up, as an aim key holds it (no key can be injected): at rest,
    # standing, it is carried lowered. Prone keeps it up.
    p.set(wc, RAISE_FORCED_VAR, True)
    yield 0.8
    stand_gap = _hand_gap(player)
    p.set(wc, RAISE_FORCED_VAR, False)
    p.set(wc, "Stance", 2)
    yield from _settle(p, anim, "PoseProne")
    seen, _speeds, step = _watch(p, player, 0.8)
    yield step
    gap = _hand_gap(player)
    hands = min(_span(seen, "hand_l")[0], _span(seen, "hand_r")[0])
    p.check(f"prone with the {label}, no key held: both hands are up off the ground "
            f"(over {HANDS_UP_CM:g} cm), as far apart as standing with it raised (the "
            "gun is still in both), and nothing is under the ground",
            hands > HANDS_UP_CM and abs(gap - stand_gap) < 3.0
            and min(_span(seen, k)[0] for k in LIMBS) > -SINK_CM,
            f"hands from {hands:.1f} cm up, {stand_gap:.1f} -> {gap:.1f} cm apart, head "
            f"{_span(seen, 'head')[1]:.1f}")
    seen, speeds, step = _watch(p, player, 1.8, forward=1.0, skip=CRAWL_START_S)
    yield step
    hands = min(_span(seen, "hand_l")[0], _span(seen, "hand_r")[0])
    legs = min(_span(seen, k)[0] for k in LIMBS[2:])
    p.check(f"crawling with the {label}: the hands stay off the ground and no knee "
            "or foot goes under it",
            hands > HANDS_UP_CM and legs > -SINK_CM,
            f"hands from {hands:.1f}, legs from {legs:.1f}, "
            f"{sum(speeds) / max(len(speeds), 1):.0f} cm/s")


def probe(p):
    yield 0.5
    player = p.pawn()
    wc = p.component(player, WEAPON_COMP_CLASS_PATH)
    mesh = player.get_editor_property("mesh")
    worn = mesh.get_skeletal_mesh_asset().get_path_name().split(".")[0]
    skin = skin_of_mesh(worn)
    p.check("the player wears a rig with the stance clips",
            wc is not None and skin is not None and skin.stance_clips, worn)
    if wc is None or skin is None or not skin.stance_clips:
        return
    # A headless game renders nothing, and by default an unrendered mesh
    # never refreshes its bones.
    mesh.set_editor_property(
        "visibility_based_anim_tick_option",
        unreal.VisibilityBasedAnimTickOption.ALWAYS_TICK_POSE_AND_REFRESH_BONES,
        unreal.PropertyAccessChangeNotifyMode.NEVER)
    anim = p.pose_instance(mesh)
    yield 0.5
    stand = _heights(player)
    p.note(f"standing: { {k: round(v) for k, v in stand.items()} }")

    p.set(wc, "Stance", 1)
    yield from _settle(p, anim, "PoseCrouch")
    low = _heights(player)
    p.note(f"crouched: { {k: round(v) for k, v in low.items()} }")
    p.check("crouched: the head comes down at least 40 cm, the feet stay down",
            stand["head"] - low["head"] >= 40.0
            and max(low["foot_l"], low["foot_r"]) < 25.0,
            f"head {stand['head']:.0f} -> {low['head']:.0f}")

    # The issued shotgun starts in hand: onto its slot, as a drag puts it
    # (before the dev guns fill the weapon slots: a filled one would swap).
    p.ask_move(wc, HAND, PRIMARY)
    yield lambda: p.get(wc, "Held") is None
    yield 0.5
    p.set(wc, "Stance", 2)
    yield from _settle(p, anim, "PoseProne")
    lying = _heights(player)
    p.note(f"prone: { {k: round(v) for k, v in lying.items()} }")
    p.check("prone: the hips lie low (under 30 cm) and the head under 80 cm",
            lying["hips"] < 30.0 and lying["head"] < 80.0,
            f"hips {lying['hips']:.0f}, head {lying['head']:.0f}")
    yield from _prone_empty(p, player, bool(skin.prone_idle))

    p.set(p.hud(), DEV_GUNS_REQUEST_VAR, True)
    yield lambda: not p.get(p.hud(), DEV_GUNS_REQUEST_VAR)
    for label, cls in GUNS:
        yield from _prone_with(p, player, wc, anim, label, cls)
    p.set(wc, "Stance", 0)
