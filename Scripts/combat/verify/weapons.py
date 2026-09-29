"""verify.weapons -- The five weapon Blueprints, their parts, grips and the three findable ones.
"""

import unreal

from combat.graph import _rot
from combat.grip import (
    _pure_rotation, _rotate_vector, socket_in_mesh, socket_pose_axes,
)
from combat.paths import ITEM_BP_PATH, PISTOL_BP_PATH, SHOTGUN_BP_PATH
from combat.skin import SKIN_QUINN, player_skin
from combat.weapon_specs import DROP_DISPLAYS, _weapon_specs
from combat.verify.common import cdo, check, components, load


# ─── The five weapons ────────────────────────────────────────────────────────

def check_five_weapons():
    # Driven off _weapon_specs() rather than off a list written here, so a weapon
    # added to the builder is a weapon checked by the verifier with no second edit.
    # That is the claim the SMG, rifle and sniper were added to test.

    item_bp = load(ITEM_BP_PATH)
    check("BP_WeaponItem exists", item_bp is not None)

    for spec in _weapon_specs():
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

    shot, pist = (load(SHOTGUN_BP_PATH), load(PISTOL_BP_PATH))
    if shot and pist:
        a, b = cdo(shot), cdo(pist)
        check("the two weapons use different ready poses",
              a.get_editor_property("AimPose") != b.get_editor_property("AimPose"))
        check("the two weapons use different fire sounds",
              a.get_editor_property("FireSound") != b.get_editor_property("FireSound"))
        # The thing the player actually sees: in the pose the weapon is held in, the
        # barrel has to point where the character is facing. Computed from the
        # *saved* GripRotation, so a grip that was solved wrongly fails here.
        for spec in _weapon_specs():
            bp, name, aim = load(spec["path"]), spec["display"], spec["aim"]
            mesh_yaw, socket = socket_in_mesh(aim)
            barrel = _rotate_vector(
                _rot(yaw=mesh_yaw),
                _rotate_vector(unreal.MathLibrary.compose_transforms(
                    _pure_rotation(cdo(bp).get_editor_property("GripRotation")),
                    _pure_rotation(socket)).rotation.rotator(),
                    unreal.Vector(1.0, 0.0, 0.0)))
            check(f"{name}: in its ready pose the barrel points where the player faces",
                  barrel.x > 0.999, f"barrel = {barrel.to_tuple()}")

        # And the axis that caused three rounds of this. On the mannequin's
        # HandGrip_R the weapon rides the socket's +Y and +X reads 0.94 to the
        # player's left -- the assertion that stopped that from being re-learned.
        # A rig with no socket is gripped by its hand BONE, whose frame is Meshy's
        # to choose, so what is asserted there is the weaker true thing: the bone
        # is a clean frame for the grip solve to start from.
        _skin = player_skin()
        _socketed = _skin is SKIN_QUINN
        for name, aim in (("rifle", _skin.aim_rifle), ("pistol", _skin.aim_pistol)):
            axes = socket_pose_axes(aim)
            if _socketed:
                check(f"in the {name} ready pose the hand's weapon axis is +Y, not +X",
                      axes["Y"].x > 0.9 and abs(axes["X"].x) < 0.5,
                      f"+Y = {axes['Y'].to_tuple()}, +X = {axes['X'].to_tuple()}")
            else:
                # On a hand BONE nothing carries the weapon, so no fixed offset
                # is written down and _grip_rotation's solve is load-bearing --
                # the check that the solve worked is the per-weapon barrel test
                # above. What is asserted here is only that the bone gives the
                # solve a frame to work from.
                #
                # This used to assert further that NO axis lay on the aim
                # (measured 0.55, -0.78, -0.31 along the player's forward).
                # That was the wrist bend chain alignment left between the
                # Meshy hand and the mannequin's, not a property of the rig:
                # since build_retarget turns the whole hand onto the
                # mannequin's (measure_clip_hand_turn, which the fingers need),
                # the bone's Y runs down the aim at 0.98, as the mannequin's
                # hand does in these poses.
                check(f"in the {name} ready pose the grip bone is an orthonormal "
                      "frame for the grip solve to work from",
                      all(abs(a.length() - 1.0) < 1e-3 for a in axes.values()),
                      ", ".join(f"{k} = {v.to_tuple()}" for k, v in axes.items()))

        # Five weapons in five slots with no icons: the colour swatch is the only
        # thing distinguishing them at a glance, so two the same is a real bug.
        swatches = [cdo(load(sp["path"])).get_editor_property("SlotColor").to_tuple()
                    for sp in _weapon_specs()]
        check("every weapon shows a different colour in the inventory",
              len(set(swatches)) == len(swatches), str(len(set(swatches))))
        # Same argument in the other sense: the gun you cannot see is the gun you
        # can hear, and a shared shot would make the sniper sound like the SMG.
        shots = [cdo(load(sp["path"])).get_editor_property("FireSound").get_name()
                 for sp in _weapon_specs()]
        check("every weapon has its own fire sound",
              len(set(shots)) == len(shots), str(sorted(shots)))
        # The click goes the other way on purpose: a hammer falling on an empty
        # chamber is the same noise in any receiver, so one asset serves all five.
        clicks = {cdo(load(sp["path"])).get_editor_property("DryFireSound").get_name()
                  for sp in _weapon_specs()}
        check("...while DryFireSound is deliberately shared by all of them",
              len(clicks) == 1, str(sorted(clicks)))
        # The reload does NOT, and that changed when the sounds became recordings
        # of real firearms: a pump shotgun, a magazine swap and a hand-fed reload
        # are three different actions. Assert against the spec table rather than
        # against a list written out here, so a weapon whose row is edited is
        # checked against its row.
        for sp in _weapon_specs():
            want = sp["reload_sound"].rsplit("/", 1)[-1]
            got = cdo(load(sp["path"])).get_editor_property("ReloadSound")
            check(f"{sp['display']}: reloads with {want}",
                  got is not None and got.get_name() == want,
                  got.get_name() if got else "None")
        reloads = {cdo(load(sp["path"])).get_editor_property("ReloadSound").get_name()
                   for sp in _weapon_specs()}
        check("...and the reload is NOT one sound for five weapons any more",
              len(reloads) > 1, str(sorted(reloads)))
        # The one pairing that would be audibly wrong: a 0.47 s pump under an
        # assault rifle, or a magazine swap on a pump shotgun.
        by_name = {sp["display"]: cdo(load(sp["path"]))
                   .get_editor_property("ReloadSound").get_name()
                   for sp in _weapon_specs()}
        check("the pump shotgun does not share a reload with the magazine weapons",
              by_name["Shotgun"] not in {by_name["SMG"], by_name["Rifle"]},
              str(by_name))


# ─── The three found weapons ─────────────────────────────────────────────────

def check_found_weapons():
    # The starting loadout is spawned into the player's hands; these three exist
    # only as drops, and that distinction is DROP_DISPLAYS.

    issued = {"Shotgun", "Pistol"}
    check("the drop table is the three weapons that are not issued",
          set(DROP_DISPLAYS) | issued == {sp["display"] for sp in _weapon_specs()}
          and not (set(DROP_DISPLAYS) & issued),
          str(DROP_DISPLAYS))
    # Sustained damage per second across the five. This is the one balance claim
    # worth asserting mechanically: what differs between the weapons should be how
    # the damage is *delivered* -- one big hit or nine small ones -- and not how
    # much of it there is. A weapon three times the DPS of another is not a choice.
    dps = {sp["display"]: sp["damage"] * sp["pellets"] / sp["interval"]
           for sp in _weapon_specs()}
    check("no weapon out-damages another by more than 3x over time",
          max(dps.values()) / min(dps.values()) < 3.0,
          ", ".join(f"{k} {v:.0f}" for k, v in sorted(dps.items(), key=lambda kv: -kv[1])))
    sniper = next(sp for sp in _weapon_specs() if sp["display"] == "Sniper")
    check("the sniper kills a 100 HP wanderer in one shot",
          sniper["damage"] * sniper["pellets"] >= 100.0, str(sniper["damage"]))
    smg = next(sp for sp in _weapon_specs() if sp["display"] == "SMG")
    check("...and the SMG needs most of a second and most of a magazine to do it",
          -(-100 // smg["damage"]) <= smg["magazine"]
          and -(-100 // smg["damage"]) * smg["interval"] > 0.5,
          f"{-(-100 // smg['damage']):.0f} rounds, "
          f"{-(-100 // smg['damage']) * smg['interval']:.2f}s")


def run():
    check_five_weapons()
    check_found_weapons()
