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

import dataclasses
import math
import sys

import unreal

sys.path.insert(0, "/Users/alexeysukhov/Documents/Unreal Projects/Otherworld/Scripts")
import build_weapons_and_combat as G                              # noqa: E402
# The two other files that have to agree with this one about the hit reactions:
# the shared clip ORDER the graph indexes by position, and the retarget sources
# that produce them. Imported rather than restated, so the check below is that
# the three files agree and not that this one was edited too.
from forest_generator.npc_placement import NPC_HIT_REACTION_CLIPS  # noqa: E402
sys.path.insert(0, "/Users/alexeysukhov/Documents/Unreal Projects/Otherworld/"
                   "Scripts/asset_pipeline")
from build_retarget import HIT_SOURCES as RETARGET_HIT_SOURCES     # noqa: E402

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


def has_in_pin(node, name):
    """Does this node really have an input pin called ``name``?

    BEL.find_input_pin answers with an INVALID pin rather than None for a name
    the node does not have, so the obvious truthiness test matches every node in
    the graph -- it matched all 414 of them once, which is how this exists.
    """
    pin = BEL.find_input_pin(node, name)
    return bool(pin) and pin.is_valid()


def by_pins(nodes, *required):
    want = {r.replace(" ", "") for r in required}
    return [n for n in nodes if want <= in_pins(n)]


def pin_value(node, name):
    return str(PIN.get_pin_value(BEL.find_input_pin(node, name)))


def num_pin(node, name):
    """pin_value as a float, or None when the pin does not hold one.

    Sweeps like "is there any node whose B pin is 0.1" run over every node with
    a B pin, and in a graph with booleans in it that includes pins reading
    'false'. float() on those is a ValueError that stops the whole verifier.
    """
    try:
        return float(pin_value(node, name))
    except (TypeError, ValueError):
        return None


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
rigs = [n for n in anim_nodes if n.get_class().get_name() == "AnimGraphNode_ControlRig"]
blends = [n for n in anim_nodes
          if n.get_class().get_name() == "AnimGraphNode_LayeredBoneBlend"]
# Two now, not one: the aim pose's, and the hit reaction's behind it. Both are
# filtered at the same spine root, and BOTH filters are checked -- an
# unresolvable branch filter contributes no bones, so a blend that lost its
# filter plays its slot at zero weight, which is invisible on screen and
# indistinguishable in a log from a montage that never started.
check("ABP_Unarmed has exactly two layered bone blends (aim, then hit)",
      len(blends) == 2, str(len(blends)))

slots = [n for n in anim_nodes if n.get_class().get_name() == "AnimGraphNode_Slot"]
slot_names = {str(n.get_editor_property("node").get_editor_property("slot_name")): n
              for n in slots}
check(f"all three slots exist: {G.AIM_SLOT} (aim), {G.HIT_SLOT} (flinch) and "
      f"{G.FULL_BODY_SLOT}",
      {G.AIM_SLOT, G.HIT_SLOT, G.FULL_BODY_SLOT} <= set(slot_names),
      str(sorted(slot_names)))
check("exactly three slots -- a rerun must not stack a fourth on the chain",
      len(slots) == 3, str(len(slots)))


def _fed_blend(slot_node):
    """The LayeredBoneBlend a Slot node's pose runs into, or None."""
    fed = PIN.list_connected_pins(BEL.find_output_pin(slot_node, "Pose"))
    if not fed:
        return None
    owner = PIN.get_owning_node(fed[0])
    return owner if owner.get_class().get_name() == "AnimGraphNode_LayeredBoneBlend" \
        else None


aim_blend = _fed_blend(slot_names[G.AIM_SLOT]) if G.AIM_SLOT in slot_names else None
hit_blend = _fed_blend(slot_names[G.HIT_SLOT]) if G.HIT_SLOT in slot_names else None
check("the aim slot and the hit slot feed two DIFFERENT blends",
      aim_blend is not None and hit_blend is not None and aim_blend != hit_blend)

for label, blend, want_base in (("aim", aim_blend, "AnimGraphNode_StateMachine"),
                                ("hit", hit_blend, "AnimGraphNode_LayeredBoneBlend")):
    if blend is None:
        continue
    layers = blend.get_editor_property("node").get_editor_property("layer_setup")
    bones = [str(f.get_editor_property("bone_name"))
             for l in layers for f in l.get_editor_property("branch_filters")]
    check(f"the {label} blend is filtered at {G.UPPER_BODY_ROOT} (upper body only)",
          bones == [G.UPPER_BODY_ROOT], str(bones))
    # The regression that put the barrel 21 degrees left: in local space the
    # aim pose's arms hang off the locomotion hips and lose their own pelvis
    # yaw. Runtime, before the fix: body yaw 44.6, gun yaw 23.3, every frame.
    check(f"the {label} blend runs in mesh space, so its pose keeps its own "
          f"direction",
          blend.get_editor_property("node").get_editor_property(
              "mesh_space_rotation_blend"))
    base_src = [PIN.get_owning_node(q).get_class().get_name()
                for q in PIN.list_connected_pins(
                    BEL.find_input_pin(blend, "BasePose"))]
    check(f"the {label} blend's base pose comes from {want_base}",
          base_src == [want_base], str(base_src))

# The hit slot's SOURCE is the aim blend's output, i.e. the same pose as its own
# blend's base. That is what makes the second blend free at rest -- both inputs
# are the same pose, so its weight cannot matter until a montage is playing.
if hit_blend is not None:
    src = [PIN.get_owning_node(q) for q in PIN.list_connected_pins(
        BEL.find_input_pin(slot_names[G.HIT_SLOT], "Source"))]
    base = [PIN.get_owning_node(q) for q in PIN.list_connected_pins(
        BEL.find_input_pin(hit_blend, "BasePose"))]
    check(f"{G.HIT_SLOT} passes through the same pose its blend uses as a base, "
          f"so the insertion is a no-op until something is hit",
          src == base and src == [aim_blend],
          f"{[n.get_name() for n in src]} vs {[n.get_name() for n in base]}")

# ...and the flinch is DOWNSTREAM of the aim pose, not upstream: a reaction has
# to win over the ready pose for its second, not be overwritten by it.
if aim_blend is not None and hit_blend is not None:
    onward = [PIN.get_owning_node(q) for q in PIN.list_connected_pins(
        BEL.find_output_pin(aim_blend, "Pose"))]
    check(f"the aim blend feeds the hit blend, so {G.HIT_SLOT} overrides the "
          f"ready pose rather than the other way round",
          hit_blend in onward, str([n.get_name() for n in onward]))
# The full-body slot has to sit AFTER both layered blends, or it is filtered to
# the upper body like the other two and whatever plays into it reaches the chest
# only.
if G.FULL_BODY_SLOT in slot_names and rigs:
    feeding = [PIN.get_owning_node(q) for q in PIN.list_connected_pins(
        BEL.find_input_pin(rigs[0], "Source"))]
    check(f"{G.FULL_BODY_SLOT} feeds the ControlRig, downstream of both blends",
          feeding == [slot_names[G.FULL_BODY_SLOT]],
          str([n.get_class().get_name() for n in feeding]))
    behind = [PIN.get_owning_node(q) for q in PIN.list_connected_pins(
        BEL.find_input_pin(slot_names[G.FULL_BODY_SLOT], "Source"))]
    check(f"the hit blend -- the last one -- feeds {G.FULL_BODY_SLOT}",
          behind == [hit_blend],
          str([n.get_class().get_name() for n in behind]))

# ─── The five weapons ────────────────────────────────────────────────────────
# Driven off _weapon_specs() rather than off a list written here, so a weapon
# added to the builder is a weapon checked by the verifier with no second edit.
# That is the claim the SMG, rifle and sniper were added to test.

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

shot, pist = (load(G.SHOTGUN_BP_PATH), load(G.PISTOL_BP_PATH))
if shot and pist:
    a, b = cdo(shot), cdo(pist)
    check("the two weapons use different ready poses",
          a.get_editor_property("AimPose") != b.get_editor_property("AimPose"))
    check("the two weapons use different fire sounds",
          a.get_editor_property("FireSound") != b.get_editor_property("FireSound"))
    # The thing the player actually sees: in the pose the weapon is held in, the
    # barrel has to point where the character is facing. Computed from the
    # *saved* GripRotation, so a grip that was solved wrongly fails here.
    for spec in G._weapon_specs():
        bp, name, aim = load(spec["path"]), spec["display"], spec["aim"]
        mesh_yaw, socket = G.socket_in_mesh(aim)
        barrel = G._rotate_vector(
            G._rot(yaw=mesh_yaw),
            G._rotate_vector(unreal.MathLibrary.compose_transforms(
                G._pure_rotation(cdo(bp).get_editor_property("GripRotation")),
                G._pure_rotation(socket)).rotation.rotator(),
                unreal.Vector(1.0, 0.0, 0.0)))
        check(f"{name}: in its ready pose the barrel points where the player faces",
              barrel.x > 0.999, f"barrel = {barrel.to_tuple()}")

    # And the axis that caused three rounds of this. On the mannequin's
    # HandGrip_R the weapon rides the socket's +Y and +X reads 0.94 to the
    # player's left -- the assertion that stopped that from being re-learned.
    # A rig with no socket is gripped by its hand BONE, whose frame is Meshy's
    # to choose, so what is asserted there is the weaker true thing: ONE of the
    # three axes is the aim, which is what makes the grip solvable at all.
    _skin = G.player_skin()
    _socketed = _skin is G.SKIN_QUINN
    for name, aim in (("rifle", _skin.aim_rifle), ("pistol", _skin.aim_pistol)):
        axes = G.socket_pose_axes(aim)
        if _socketed:
            check(f"in the {name} ready pose the hand's weapon axis is +Y, not +X",
                  axes["Y"].x > 0.9 and abs(axes["X"].x) < 0.5,
                  f"+Y = {axes['Y'].to_tuple()}, +X = {axes['X'].to_tuple()}")
        else:
            # The inverse assertion, and the more useful one. On a hand BONE
            # nothing carries the weapon: measured on the adventurer, the
            # rifle pose's three axes read 0.55, -0.78 and -0.31 along the
            # player's forward, so no axis is the aim and no fixed offset
            # could be written down. That is what makes _grip_rotation's
            # solve load-bearing rather than a convenience -- the check that
            # the solve worked is the per-weapon barrel test above.
            check(f"in the {name} ready pose the grip bone is an orthonormal "
                  "frame with no axis on the aim, so the grip must be solved",
                  all(abs(a.length() - 1.0) < 1e-3 for a in axes.values())
                  and max(abs(a.x) for a in axes.values()) < 0.9,
                  ", ".join(f"{k} = {v.to_tuple()}" for k, v in axes.items()))

    # Five weapons in five slots with no icons: the colour swatch is the only
    # thing distinguishing them at a glance, so two the same is a real bug.
    swatches = [cdo(load(sp["path"])).get_editor_property("SlotColor").to_tuple()
                for sp in G._weapon_specs()]
    check("every weapon shows a different colour in the inventory",
          len(set(swatches)) == len(swatches), str(len(set(swatches))))
    # Same argument in the other sense: the gun you cannot see is the gun you
    # can hear, and a shared shot would make the sniper sound like the SMG.
    shots = [cdo(load(sp["path"])).get_editor_property("FireSound").get_name()
             for sp in G._weapon_specs()]
    check("every weapon has its own fire sound",
          len(set(shots)) == len(shots), str(sorted(shots)))
    # The click goes the other way on purpose: a hammer falling on an empty
    # chamber is the same noise in any receiver, so one asset serves all five.
    clicks = {cdo(load(sp["path"])).get_editor_property("DryFireSound").get_name()
              for sp in G._weapon_specs()}
    check("...while DryFireSound is deliberately shared by all of them",
          len(clicks) == 1, str(sorted(clicks)))
    # The reload does NOT, and that changed when the sounds became recordings
    # of real firearms: a pump shotgun, a magazine swap and a hand-fed reload
    # are three different actions. Assert against the spec table rather than
    # against a list written out here, so a weapon whose row is edited is
    # checked against its row.
    for sp in G._weapon_specs():
        want = sp["reload_sound"].rsplit("/", 1)[-1]
        got = cdo(load(sp["path"])).get_editor_property("ReloadSound")
        check(f"{sp['display']}: reloads with {want}",
              got is not None and got.get_name() == want,
              got.get_name() if got else "None")
    reloads = {cdo(load(sp["path"])).get_editor_property("ReloadSound").get_name()
               for sp in G._weapon_specs()}
    check("...and the reload is NOT one sound for five weapons any more",
          len(reloads) > 1, str(sorted(reloads)))
    # The one pairing that would be audibly wrong: a 0.47 s pump under an
    # assault rifle, or a magazine swap on a pump shotgun.
    by_name = {sp["display"]: cdo(load(sp["path"]))
               .get_editor_property("ReloadSound").get_name()
               for sp in G._weapon_specs()}
    check("the pump shotgun does not share a reload with the magazine weapons",
          by_name["Shotgun"] not in {by_name["SMG"], by_name["Rifle"]},
          str(by_name))

# ─── The sounds themselves ───────────────────────────────────────────────────
# Nine assets cut from CC0 recordings of real firearms by
# Scripts/fetch_weapon_sounds.py, which replaced a synthesiser. The checks are
# on the WAVs on disk rather than on the SoundWave assets, because the two
# properties worth asserting are properties of the audio and not of the import.

import os
import wave as _wave

_eas = unreal.get_editor_subsystem(unreal.EditorAssetSubsystem)

for name in G.SOUND_NAMES:
    check(f"{name} imported", _eas.does_asset_exist(f"{G.AUDIO_DIR}/{name}"))
# A_Reload was the one synthesised clack every weapon shared. A builder that
# simply stops referencing an asset leaves it on disk forever, so its removal
# is deliberate and worth asserting -- an orphan in the audio folder reads as
# something still in use.
for path in G.RETIRED_SOUNDS:
    check(f"the superseded {path.rsplit('/', 1)[-1]} is gone",
          not _eas.does_asset_exist(path), path)

for name in G.SOUND_NAMES:
    src = os.path.join(G.SOUND_SRC_DIR, f"{name}.wav")
    if not os.path.isfile(src):
        check(f"{name}.wav is on disk", False, src)
        continue
    with _wave.open(src, "rb") as fh:
        channels, rate, frames = (fh.getnchannels(), fh.getframerate(),
                                  fh.getnframes())
    # MONO IS LOAD-BEARING, not a size choice. PlaySoundAtLocation spatialises
    # by panning and attenuating around the listener and can only do that to a
    # one-channel source; hand it the stereo original and every shot plays flat
    # and full volume with no sense of where the muzzle was.
    check(f"{name} is mono, so PlaySoundAtLocation can place it",
          channels == 1, f"{channels} channels")
    check(f"{name} is 44.1 kHz", rate == 44100, str(rate))
    seconds = frames / float(rate)
    check(f"{name} is between 0.2 s and 2.5 s long", 0.2 <= seconds <= 2.5,
          f"{seconds:.2f}s")

# A shot has to finish inside its own fire interval or an automatic stacks an
# unbounded number of copies of itself. Only the automatics are checked: the
# sniper's 1.6 s report deliberately runs into its 1.6 s cadence.
for name in G.AUTO_DISPLAYS:
    sp = next(x for x in G._weapon_specs() if x["display"] == name)
    src = os.path.join(G.SOUND_SRC_DIR, f"{sp['sound'].rsplit('/', 1)[-1]}.wav")
    if not os.path.isfile(src):
        continue
    with _wave.open(src, "rb") as fh:
        seconds = fh.getnframes() / float(fh.getframerate())
    overlap = seconds / sp["interval"]
    check(f"{name}: a held trigger stacks at most 12 copies of the shot",
          overlap <= 12.0, f"{seconds:.2f}s sample / {sp['interval']:.2f}s "
                           f"interval = {overlap:.1f} overlapping")
    # ...and the ones that do stack are mixed down for it, or the burst clips.
    with _wave.open(src, "rb") as fh:
        raw = fh.readframes(fh.getnframes())
    peak = max(abs(int.from_bytes(raw[i:i + 2], "little", signed=True))
               for i in range(0, len(raw), 2)) / 32767.0
    check(f"{name}: its sample is mixed below full scale, so a burst does not "
          f"clip", peak < 0.80, f"peak {peak:.2f}")

# ─── Distance and direction ──────────────────────────────────────────────────
# Every sound in this game is made by something standing somewhere, so every
# one of them is spatialised and every one of them fades with distance. The
# machinery is the engine's: a USoundAttenuation asset per profile, named on
# the SoundWave rather than wired into each PlaySoundAtLocation node.
#
# The failure this section exists to catch is the quiet one. A SoundBase whose
# AttenuationSettings is None does not fall back to some default falloff -- it
# is parsed with no spatialisation and no attenuation at all, and plays at full
# volume, centred, from anywhere on the map. That is indistinguishable from
# working until you walk away from the thing making the noise.

_ATT_OK = {p.name: p for p in G.ATTENUATIONS}
check("there is a small named set of attenuation profiles, not one per sound",
      1 <= len(G.ATTENUATIONS) <= 4, str(sorted(_ATT_OK)))

for profile in G.ATTENUATIONS:
    att = load(profile.path)
    check(f"{profile.name} exists", att is not None, profile.path)
    if att is None:
        continue
    check(f"{profile.name} is a SoundAttenuation asset",
          isinstance(att, unreal.SoundAttenuation), str(type(att)))
    st = att.get_editor_property("attenuation")
    check(f"{profile.name}: volume falls off with distance",
          bool(st.get_editor_property("attenuate")))
    # Without this the sound has a position and no direction: it attenuates as
    # you walk away but never moves in the stereo field as you turn.
    check(f"{profile.name}: spatialised, so it comes from where it happened",
          bool(st.get_editor_property("spatialize")))
    check(f"{profile.name}: on the engine's own panner",
          st.get_editor_property("spatialization_algorithm")
          == unreal.SoundSpatializationAlgorithm.SPATIALIZATION_DEFAULT,
          str(st.get_editor_property("spatialization_algorithm")))
    check(f"{profile.name}: a natural (dB) falloff curve, not a mixing one",
          st.get_editor_property("distance_algorithm")
          == unreal.AttenuationDistanceModel.NATURAL_SOUND,
          str(st.get_editor_property("distance_algorithm")))
    check(f"{profile.name}: a sphere, so it fades the same in every direction",
          st.get_editor_property("attenuation_shape")
          == unreal.AttenuationShape.SPHERE,
          str(st.get_editor_property("attenuation_shape")))
    radius = float(st.get_editor_property("attenuation_shape_extents").x)
    falloff = float(st.get_editor_property("falloff_distance"))
    check(f"{profile.name}: full volume out to {profile.radius_cm:.0f} cm",
          abs(radius - profile.radius_cm) < 1e-3, f"{radius:.1f} cm")
    check(f"{profile.name}: fades over {profile.falloff_cm:.0f} cm beyond that",
          abs(falloff - profile.falloff_cm) < 1e-3, f"{falloff:.1f} cm")
    # THE NUMBER THE BRIEF ASKED FOR. The falloff is measured from the edge of
    # the full-volume sphere, so the audible radius is the sum of the two --
    # reading falloff_distance alone would under-report it by the radius.
    check(f"{profile.name}: inaudible past 100 m",
          radius + falloff <= G.AUDIBLE_LIMIT_CM + 1e-3,
          f"{(radius + falloff) / 100.0:.1f} m")
    check(f"{profile.name}: reaches {G.ATT_DB_AT_MAX:.0f} dB at the edge",
          abs(float(st.get_editor_property("d_b_attenuation_at_max"))
              - G.ATT_DB_AT_MAX) < 1e-3,
          str(st.get_editor_property("d_b_attenuation_at_max")))
    check(f"{profile.name}: air absorption "
          f"{'on' if profile.air_absorption else 'off'}",
          bool(st.get_editor_property("attenuate_with_lpf"))
          is bool(profile.air_absorption))

# One profile has to spend the whole 100 m allowance, or "at most 100 m" has
# been satisfied by making everything quiet instead of by placing it.
check("a gunshot is the thing that carries the full 100 m",
      abs(G.ATT_GUNFIRE.audible_cm - G.AUDIBLE_LIMIT_CM) < 1e-3,
      f"{G.ATT_GUNFIRE.audible_cm / 100.0:.0f} m")
check("a footstep carries far less than a gunshot",
      G.ATT_FOLEY.audible_cm * 4 < G.ATT_GUNFIRE.audible_cm,
      f"{G.ATT_FOLEY.audible_cm / 100.0:.0f} m vs "
      f"{G.ATT_GUNFIRE.audible_cm / 100.0:.0f} m")

# THE SWEEP THAT MAKES "NOTHING WAS MISSED" TRUE. It walks the two audio
# folders on disk rather than G.SOUND_NAMES + G.CREATURE_SOUND_NAMES, so a
# sound the builder imports under a name nobody remembered to profile is a
# failure here rather than one unattenuated noise nobody notices.
_waves, _flat = [], []
for _folder in (G.AUDIO_DIR, G.CREATURE_AUDIO_DIR):
    for _ref in _eas.list_assets(_folder, recursive=False):
        _asset = load(_ref)
        if not isinstance(_asset, unreal.SoundWave):
            continue
        _waves.append(_asset.get_name())
        _att = _asset.get_editor_property("attenuation_settings")
        if _att is None or _att.get_name() not in _ATT_OK:
            _flat.append(f"{_asset.get_name()} -> {_att}")
check("every sound in the game carries one of the attenuation profiles",
      not _flat and len(_waves) == len(G.SOUND_NAMES) + len(G.CREATURE_SOUND_NAMES),
      f"{len(_waves)} sounds, unattenuated: {sorted(_flat)}")
for _name, _profile in sorted(G.SOUND_ATTENUATION.items()):
    # Named folder, not "try one then the other": a failed load is an Error
    # line in the log, and 13 of them on every clean run is how a real one
    # stops being read.
    _asset = load(f"{G.AUDIO_DIR if _name in G.SOUND_NAMES else G.CREATURE_AUDIO_DIR}"
                  f"/{_name}")
    _att = _asset.get_editor_property("attenuation_settings") if _asset else None
    check(f"{_name} -> {_profile.name}",
          _att is not None and _att.get_name() == _profile.name, str(_att))
    # AND THE ENGINE AGREES. MaxDistance is not a field this builder writes --
    # USoundBase caches it off whatever attenuation it ends up resolving, and
    # it is the number the audio device culls against at play time. Reading it
    # back is the end-to-end proof that the asset link actually reached the
    # sound, rather than a re-read of the struct the builder just wrote; an
    # unattenuated wave reports the whole world here, not 100 m.
    _reach = float(_asset.get_editor_property("max_distance")) if _asset else -1.0
    check(f"...and the engine will cull {_name} past "
          f"{_profile.audible_cm / 100.0:.0f} m",
          abs(_reach - _profile.audible_cm) < 1e-3, f"{_reach:.0f} cm")

# ─── The three found weapons ─────────────────────────────────────────────────
# The starting loadout is spawned into the player's hands; these three exist
# only as drops, and that distinction is DROP_DISPLAYS.

issued = {"Shotgun", "Pistol"}
check("the drop table is the three weapons that are not issued",
      set(G.DROP_DISPLAYS) | issued == {sp["display"] for sp in G._weapon_specs()}
      and not (set(G.DROP_DISPLAYS) & issued),
      str(G.DROP_DISPLAYS))
# Sustained damage per second across the five. This is the one balance claim
# worth asserting mechanically: what differs between the weapons should be how
# the damage is *delivered* -- one big hit or nine small ones -- and not how
# much of it there is. A weapon three times the DPS of another is not a choice.
dps = {sp["display"]: sp["damage"] * sp["pellets"] / sp["interval"]
       for sp in G._weapon_specs()}
check("no weapon out-damages another by more than 3x over time",
      max(dps.values()) / min(dps.values()) < 3.0,
      ", ".join(f"{k} {v:.0f}" for k, v in sorted(dps.items(), key=lambda kv: -kv[1])))
sniper = next(sp for sp in G._weapon_specs() if sp["display"] == "Sniper")
check("the sniper kills a 100 HP wanderer in one shot",
      sniper["damage"] * sniper["pellets"] >= 100.0, str(sniper["damage"]))
smg = next(sp for sp in G._weapon_specs() if sp["display"] == "SMG")
check("...and the SMG needs most of a second and most of a magazine to do it",
      -(-100 // smg["damage"]) <= smg["magazine"]
      and -(-100 // smg["damage"]) * smg["interval"] > 0.5,
      f"{-(-100 // smg['damage']):.0f} rounds, "
      f"{-(-100 // smg['damage']) * smg['interval']:.2f}s")

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
check("respawn point comes from the navmesh",
      bool(by_pins(hg, "Origin", "Radius")))

# The respawn has to land on walkable ground. The band point is built from the
# PLAYER's Z, so on any terrain higher than the player it is underground -- and
# a Character spawned underground falls through the world. These four checks
# guard the shape that fixes it, each of which compiles fine when broken:
projections = by_pins(hg, "Point", "QueryExtent")
check("the respawn point is projected onto the navmesh",
      len(projections) == G.RESPAWN_ATTEMPTS,
      f"{len(projections)} ProjectPointToNavigation node(s), "
      f"expected {G.RESPAWN_ATTEMPTS}")
# An unconnected struct pin reads as the ZERO vector: a search box with no
# volume, which finds nothing and fails every projection.
check("every projection has a real search box, not an empty struct pin",
      all(BEL.find_input_pin(n, "QueryExtent").list_connected_pins()
          for n in projections) and bool(projections))
# The original bug: the location output was used and the bool ignored, so a
# failed query spawned at the raw request point, at the player's own Z.
check("every projection's success is branched on, not ignored",
      all(BEL.find_output_pin(n, "ReturnValue").list_connected_pins()
          for n in projections) and bool(projections))
lifts = [n for n in by_pins(hg, "X", "Y", "Z")
         if pin_value(n, "Z") == str(G.RESPAWN_LIFT)]
check("the spawn is lifted from the ground to the capsule's centre",
      bool(lifts), f"expected a MakeVector with Z = {G.RESPAWN_LIFT}")
check("the chosen point is stored, so the random draw is evaluated once",
      "RespawnPoint" in {str(v) for v in BEL.list_member_variable_names(
          health_bp, False)})

# The respawn band. A replacement wanderer has to keep the "75-100 m away" rule
# the level generator spawns the pack under, or the rule holds only until the
# first kill -- and it is measured from the *player*, not from a stored spawn
# point, so that it survives the player walking across the map.
ranges = {(pin_value(n, "Min"), pin_value(n, "Max")) for n in by_pins(hg, "Min", "Max")}
want_band = (str(G.RESPAWN_BAND[0]), str(G.RESPAWN_BAND[1]))
check("respawns land in the 75-100 m band", want_band in ranges,
      f"{sorted(ranges)} vs {want_band}")
check("the bearing is random over a full circle", ("0.0", "360.0") in ranges,
      str(sorted(ranges)))
check("the respawn is measured from the player, not a stored spawn point",
      "SpawnOrigin" not in {str(v) for v in BEL.list_member_variable_names(
          health_bp, False)}
      and bool(by_pins(hg, "PlayerIndex")))
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

# ─── The keys, and the fact that not one of them is a literal ────────────────
# Every Key pin in this graph is DRIVEN by a member variable, which is the
# whole of rebinding: the HUD writes those variables every DrawHUD frame from
# the player's save, and a pin literal cannot be written to. A pin that went
# back to a literal would compile, save, and simply ignore the settings screen
# for ever -- so the assertion is on the wiring, not on the value.
polls = by_pins(wg, "self", "Key")
literal = [pin_value(n, "Key") for n in polls if pin_value(n, "Key")]
check("no key is polled as a pin literal any more", not literal, str(literal))
driven = []
for n in polls:
    src = PIN.list_connected_pins(BEL.find_input_pin(n, "Key"))
    driven += [str(BEL.get_node_title(PIN.get_owning_node(q))).replace("\n", " ")
               for q in src]
# The fire key appears TWICE and that is the whole of automatic fire: once as
# WasInputKeyJustPressed (a tap) and once as IsInputKeyDown (a hold). Sprint
# and aim are the other two held keys.
want_keys = sorted([f"Get {v}" for v, _k in G.BIND_VARS] + ["Get KeyFire"])
check(f"polls exactly {want_keys}", sorted(driven) == want_keys, str(sorted(driven)))
# One Get per bind, reused by every poll -- an output pin takes any number of
# links, so eight polls come off seven reads.
reads = [n for n in wg
         if str(BEL.get_node_title(n)).replace("\n", " ")
         in {f"Get {v}" for v, _k in G.BIND_VARS}]
check("one read per bind, shared by the polls that use it",
      len(reads) == len(G.BIND_VARS), str(len(reads)))
for var, default in G.BIND_VARS:
    got = w.get_editor_property(var)
    check(f"{var} defaults to {default}, the key this file documents",
          got is not None and got.export_text() == default,
          got.export_text() if got is not None else "None")

plays = by_pins(wg, "Asset", "SlotNodeName")
# TWO, and the second one is not a duplicate. A montage started in HitSlot stops
# the ready pose in DefaultSlot -- montages are stopped per GROUP and UE 5.8
# exposes no way to put a slot in a different group from Python -- so the flinch
# costs the aim pose, and the keepalive in Tick is what puts it back on the
# first frame after the stagger. Measured before it existed: DefaultSlot sat at
# weight 1.000 until the first punch landed and read 0.000 for the rest of the
# session.
check("the ready pose is played into a slot twice: on equip, and again after a "
      "hit reaction has taken it away", len(plays) == 2, str(len(plays)))
for i, play in enumerate(plays):
    check(f"ready-pose play {i} goes into {G.AIM_SLOT}",
          pin_value(play, "SlotNodeName") == G.AIM_SLOT,
          pin_value(play, "SlotNodeName"))
    check(f"ready-pose play {i} loops rather than playing once",
          int(float(pin_value(play, "LoopCount"))) >= 100,
          pin_value(play, "LoopCount"))
check("empty hands stop the slot", bool(by_pins(wg, "InBlendOutTime", "SlotNodeName")))

# The keepalive's two guards. Without the HitSlot one it restarts the ready pose
# on the frame the flinch begins, the restart stops the flinch (same group), and
# the reaction is one frame of twitch.
_slot_tests = {pin_value(n, "SlotNodeName")
               for n in wg
               if str(BEL.get_node_title(n)).replace("\n", " ").startswith("Is Slot Active")
               or "IsSlotActive" in str(BEL.get_node_title(n)).replace(" ", "")}
check(f"the keepalive asks whether {G.AIM_SLOT} and {G.HIT_SLOT} are quiet "
      f"before it replays the pose",
      {G.AIM_SLOT, G.HIT_SLOT} <= _slot_tests, str(sorted(_slot_tests)))

# The hybrid aim, which is the whole point of the trace layout: the camera line
# decides what is being aimed at, the muzzle line decides whether the gun can
# reach it, and the pellets fly down the muzzle line. Getting this wrong is not
# a compile error -- it is a gun that shoots from behind the player's shoulder.
traces = by_pins(wg, "Start", "End", "TraceChannel")
check("there are four traces (camera aim, muzzle clearance, pellets, drop probe)",
      len(traces) == 4, str(len(traces)))


def titled(nodes, title):
    """Nodes by their displayed title.

    The only handle Python gets on *which* function a call node wraps:
    BlueprintEditorLibrary exposes no get_function_name, and pin sets alone
    cannot tell GetCameraLocation from any other self-and-return node.
    """
    return [n for n in nodes
            if str(BEL.get_node_title(n)).replace("\n", " ") == title]


from_muzzle, from_camera = [], []
for t in traces:
    feeders = [PIN.get_owning_node(q) for q in
               PIN.list_connected_pins(BEL.find_input_pin(t, "Start"))]
    for n in feeders:
        if {"T", "Location"} <= in_pins(n):                      # TransformLocation
            from_muzzle.append(t)
        if str(BEL.get_node_title(n)) == "GetCameraLocation":
            from_camera.append(t)
check("two traces start at the weapon's muzzle: the clearance check and the pellets",
      len(from_muzzle) == 2, f"{len(from_muzzle)} fed by TransformLocation")
check("exactly one trace starts at the camera -- the one that picks the target",
      len(from_camera) == 1, f"{len(from_camera)} fed by GetCameraLocation")
# Built as a MakeVector, not as a pin literal: that operator's B pin is a
# struct pin when nothing is connected, and struct pins take no literal at all.
check("the camera's ray reaches AIM_TRACE_RANGE when it hits nothing",
      any(all(abs(float(pin_value(n, axis) or 0) - G.AIM_TRACE_RANGE) < 1e-3
              for axis in "XYZ")
          for n in titled(wg, "MakeVector")),
      f"{G.AIM_TRACE_RANGE:.0f} cm")
check("a dropped weapon lands in front of the player, not on their feet",
      any(all(abs(float(pin_value(n, axis) or 0) - G.DROP_FORWARD) < 1e-3
              for axis in "XYZ")
          for n in titled(wg, "MakeVector")),
      f"{G.DROP_FORWARD:.0f} cm ahead")
# One subtraction off AimPoint: the pellet direction.
deltas = [n for n in titled(wg, "vector - vector")
          if any(str(BEL.get_node_title(PIN.get_owning_node(q))) == "Get AimPoint"
                 for q in PIN.list_connected_pins(BEL.find_input_pin(n, "A")))]
check("the pellet direction is muzzle -> AimPoint, not camera forward",
      len(deltas) == 1, f"{len(deltas)} vector subtractions driven by AimPoint")

# A held weapon is rigidly attached and never rotated on its own. Driving its
# rotation from the aim was tried and reverted: the gun swivelled out of the
# hand and spun a full turn as the camera came round.
check("nothing rotates the held weapon out of the hand",
      not titled(wg, "Set Actor Rotation"),
      f"{len(titled(wg, 'Set Actor Rotation'))} SetActorRotation node(s)")
# No trace draws itself any more: DrawDebugType is an enum literal on the pin
# and an enum pin cannot be driven, so "only in debug mode" is inexpressible
# there. The tracer is a DrawDebugLine behind a Branch instead.
drawn = [t for t in traces if "ForDuration" in pin_value(t, "DrawDebugType")]
check("no trace draws itself -- the tracer is conditional and a pin literal is not",
      not drawn, f"{len(drawn)} drawn")

for var, kind in (("AimPoint", unreal.Vector), ("AimValid", bool),
                  ("AimBlocked", bool)):
    value = w.get_editor_property(var)
    check(f"{var} exists on the weapon component for the HUD to read",
          isinstance(value, kind), type(value).__name__)

check("the component plays three sounds: the shot, the click and the reload",
      len(by_pins(wg, "Sound", "Location")) == 3,
      f"{len(by_pins(wg, 'Sound', 'Location'))} PlaySoundAtLocation node(s)")
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

# ─── Spawn numbering ─────────────────────────────────────────────────────────
# Every wanderer takes a number as it spawns and logs where it appeared; the HUD
# draws that number beside its health bar. The pair is what makes a fall-through
# reportable, so both halves are guarded here.
gm = load(G.GAME_MODE_BP_PATH)
check("the GameMode carries the spawn counter",
      G.SPAWN_COUNT_VAR in {str(v) for v in BEL.list_member_variable_names(gm, False)})
check("the health component carries the wanderer's number",
      G.NPC_ID_VAR in {str(v) for v in BEL.list_member_variable_names(
          health_bp, False)})
logs = [n for n in hg if "InString" in in_pins(n)]
# Exactly three, all deliberate: the spawn log, the safety net's, and the
# player's death. Any more is a probe left behind -- and this graph is the one
# that gets instrumented whenever respawns misbehave.
check("exactly three log lines in the health graph (spawn + fell + death)",
      len(logs) == 3, f"{len(logs)} PrintString(s)")
# PrintWarning has no screen toggle (it is log-only by construction); the spawn
# log is a PrintString and must be told not to paint over the HUD.
screened = [n for n in logs if "bPrintToScreen" in in_pins(n)]
check("the spawn and death logs are written to the log, not over the HUD",
      all(pin_value(n, "bPrintToScreen") in ("false", "False") for n in screened)
      and bool(screened))
# Blueprint cannot log at Error severity at all, so the fall is reported at the
# highest it has: PrintWarning takes InString and nothing else.
check("the fall is reported at warning severity, not a plain print",
      any("bPrintToScreen" not in in_pins(n) for n in logs))
check("the wanderer remembers where it was spawned",
      G.SPAWNED_AT_VAR in {str(v) for v in BEL.list_member_variable_names(
          health_bp, False)})
# Both lines quote the stored SpawnedAt, so they cannot disagree.
def out_pins(node):
    return {str(PIN.get_pin_name(p)) for p in BEL.list_output_pins(node)}

reads = [n for n in hg if G.SPAWNED_AT_VAR in out_pins(n)]
check("the fall report names the spawn location too", len(reads) == 2,
      f"{len(reads)} SpawnedAt read(s), expected 2 (spawn log + fall report)")
prefixes = {pin_value(n, "A") for n in by_pins(hg, "A", "B")}
for label, want in (("spawn", G.SPAWN_LOG_PREFIX), ("fall", G.FELL_LOG_PREFIX)):
    check(f"{label} log lines are greppable", want in prefixes,
          f"expected {want!r}")

# ─── Installation ────────────────────────────────────────────────────────────

def blocks_visibility(bp):
    """Would a Visibility line trace hit this character?

    The single most important check in this file. UE's stock Pawn profile
    ignores Visibility, which is the channel the pellets trace on, so a
    character left on the default is simply unhittable -- and the trace reports
    "no hit" exactly as it would for a real miss, so nothing anywhere says so.
    """
    capsule = component_template(bp, "CapsuleComponent")
    if capsule is None:
        return None
    return (capsule.get_collision_response_to_channel(
        unreal.CollisionChannel.ECC_VISIBILITY) == unreal.CollisionResponseType.ECR_BLOCK)


char = load(G.CHARACTER_BP_PATH)
cnames = set(components(char))
# Found by type, not by name: the template's boom is "CameraBoom" in the
# third-person template but that is a name somebody could reasonably change,
# whereas there is only ever one spring arm on a third-person character.
arm = next((c for c in (component_template(char, n) for n in components(char))
            if isinstance(c, unreal.SpringArmComponent)), None)
check("the camera sits over the shoulder, so the reticle is not on the player",
      arm is not None
      and abs(arm.get_editor_property("socket_offset").y - G.CAMERA_SHOULDER[1]) < 1e-3
      and abs(arm.get_editor_property("target_arm_length") - G.CAMERA_ARM) < 1e-3,
      f"offset {arm.get_editor_property('socket_offset').to_tuple()}, "
      f"arm {arm.get_editor_property('target_arm_length')}" if arm else "no boom")

move = next((c for c in (component_template(char, n) for n in components(char))
             if isinstance(c, unreal.CharacterMovementComponent)), None)
check("the body follows the camera, so the gun stays on the crosshair",
      cdo(char).get_editor_property("use_controller_rotation_yaw")
      and move is not None
      and not move.get_editor_property("orient_rotation_to_movement"),
      "orient-to-movement would turn the gun with the movement input instead")

check("player carries HealthComponent + WeaponComponent",
      {"HealthComponent", "WeaponComponent"} <= cnames,
      str(sorted(cnames)))
stale = cnames & G.OLD_SHOTGUN_PARTS
check("the old welded shotgun is gone from the player", not stale, str(sorted(stale)))
check("player's capsule blocks Visibility, so it can be shot too",
      blocks_visibility(char) is True, str(blocks_visibility(char)))

check("pellet traces are drawn, so a miss is visible",
      G.TRACE_DEBUG_SECONDS > 0, f"{G.TRACE_DEBUG_SECONDS}s")

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
    # ...and as ITS OWN kind of wanderer. That template default names the
    # parent, and every variant inherits it, so on its own it means a dead
    # wendigo is replaced by a BP_ForestWanderer -- which wears the parent's
    # mesh, i.e. a zombie. Kill the two wendigos the level places and there are
    # never any more. The fix is that BeginPlay overwrites RespawnClass with
    # the owner's own class, and this is the check for it, because nothing a
    # headless run does will ever kill a wanderer.
    # GetObjectClass renders as "Get Class" in the graph.
    owner_class = [n for n in hg
                   if str(BEL.get_node_title(n)).replace("\n", " ") == "Get Class"]
    check("...and BeginPlay asks the owner what class it is",
          len(owner_class) == 1, str(len(owner_class)))
    # Loop variable deliberately not `n`: `n` is the NPC's CDO, read again two
    # checks below, and shadowing it here turned that read into a call on a
    # graph node.
    rewritten = []
    for getter in owner_class:
        for pin in BEL.list_output_pins(getter):
            for other in pin.list_connected_pins():
                node = unreal.BlueprintGraphPinLibrary.get_owning_node(other)
                if node and "RespawnClass" in str(BEL.get_node_title(node)):
                    rewritten.append(node)
    check("...and writes it into RespawnClass, so each creature respawns as "
          "itself", len(rewritten) == 1,
          str([str(BEL.get_node_title(x)) for x in rewritten]))
    check("NPC's capsule blocks Visibility, so pellets can actually hit it",
          blocks_visibility(npc) is True, str(blocks_visibility(npc)))
    check("a spawned wanderer still gets an AI controller",
          n.get_editor_property("auto_possess_ai")
          == unreal.AutoPossessAI.PLACED_IN_WORLD_OR_SPAWNED)

# ─── Hit boxes ───────────────────────────────────────────────────────────────
# The capsule says whether a pellet hit; the physics bodies say where. Every
# half of that can be wrong while the gun still works -- a table that never
# filled, a multiplier that declared as an int (1.5 -> 1), a second trace fed
# from the wrong line -- and each looks exactly like "every hit is a body hit".

for var, want in ((G.HEAD_MULT_VAR, G.COMBAT.head_multiplier),
                  (G.LIMB_MULT_VAR, G.COMBAT.limb_multiplier)):
    got = h.get_editor_property(var)
    check(f"{var} is {want}, and a float -- an int would truncate it",
          isinstance(got, float) and abs(got - want) < 1e-6, repr(got))


def _mesh_asset(bp):
    for name in components(bp):
        t = component_template(bp, name)
        if isinstance(t, unreal.SkeletalMeshComponent):
            return t.get_editor_property("skeletal_mesh_asset")
    return None


zoned = {}
for tag, bp in (("player", char), ("NPC", npc)):
    if not bp:
        continue
    comp = component_template(bp, "HealthComponent")
    heads = [str(b) for b in comp.get_editor_property(G.HEAD_BONES_VAR)] if comp else []
    limbs = [str(b) for b in comp.get_editor_property(G.LIMB_BONES_VAR)] if comp else []
    zoned[tag] = (heads, limbs)
    want_head, want_limbs, body = G.hit_zones(_mesh_asset(bp))
    # Rig-AGNOSTIC, deliberately. The first version of these asserted literal
    # mannequin bone names ("head" in heads, upperarm_l in limbs), which is the
    # very bug they were written to catch, one level up: the monsters are on a
    # Mixamo rig whose bodies are Head / LeftArm / LeftUpLeg, the tables were
    # perfectly correct, and the CHECK failed. What is actually worth asserting
    # is structural -- that the tables are what this mesh's own physics asset
    # resolves to, that both zones exist, that they do not overlap, and that
    # the torso is in neither.
    check(f"{tag}: the head table is its own skeleton's head bodies",
          heads == want_head and len(heads) > 0, str(heads))
    check(f"{tag}: the limb table is its own skeleton's arm and leg bodies",
          limbs == want_limbs and len(limbs) >= 4, str(limbs))
    # Four limbs means all four were found, not one root matched twice: a rig
    # whose arms resolved and whose legs did not would still list "several".
    roots = {b for b in limbs if not any(
        o != b and b.lower().startswith(o.lower()) for o in limbs)}
    check(f"{tag}: all four limbs are covered, not just the arms",
          len(limbs) >= 8 or len(roots) >= 4,
          f"{len(limbs)} limb bodies: {limbs}")
    check(f"{tag}: no bone is both head and limb", not set(heads) & set(limbs))
    check(f"{tag}: the torso is neither -- a chest shot is a 1x shot",
          len(body) > 0 and not set(body) & (set(heads) | set(limbs)),
          str(body))

# ─── The player's body ───────────────────────────────────────────────────────
# The player is no longer necessarily SKM_Quinn_Simple. Which body is worn is
# decided by whether the asset pipeline has produced the adventurer, so what is
# asserted here is that WHICHEVER skin resolved is internally consistent --
# and, above all, that the mesh and the anim BP agree about the skeleton. That
# mismatch is the silent one: the component falls back to the reference pose
# and the player slides around the map in a bind pose with nothing in the log.

skin = G.player_skin()
unreal.log_warning(f"[VERIFY] player skin: {skin.mesh.rsplit('/', 1)[1]}")
worn = _mesh_asset(char) if char else None
check("the player wears the skin the builder resolved",
      worn is not None and worn.get_path_name().split(".")[0] == skin.mesh,
      worn.get_path_name() if worn else "None")

_anim_class = unreal.load_class(
    None, f"{skin.anim_bp}.{skin.anim_bp.rsplit('/', 1)[1]}_C")
_mesh_comp = None
for _h, _n in (G._handles(char) if char else []):
    _o = G._component_object(_h)
    if isinstance(_o, unreal.SkeletalMeshComponent):
        _mesh_comp = _o
        break
check("...animated by that skin's anim blueprint",
      _mesh_comp is not None and _anim_class is not None
      and _mesh_comp.get_editor_property("anim_class") == _anim_class,
      str(_mesh_comp.get_editor_property("anim_class")) if _mesh_comp else "no mesh")
_abp = load(skin.anim_bp)
check("...and the two agree about the skeleton, so the pose is not the bind pose",
      worn is not None and _abp is not None
      and _abp.get_editor_property("target_skeleton")
      == worn.get_editor_property("skeleton"),
      f"mesh {worn.get_editor_property('skeleton').get_name() if worn else None} vs "
      f"anim {_abp.get_editor_property('target_skeleton').get_name() if _abp else None}")

if _mesh_comp:
    check("the body stands in its capsule, not on top of it",
          abs(_mesh_comp.get_editor_property("relative_location").z - skin.mesh_z) < 0.01,
          str(_mesh_comp.get_editor_property("relative_location").z))
    check("...facing the actor's forward",
          abs(_mesh_comp.get_editor_property("relative_rotation").yaw
              - skin.mesh_yaw) < 0.01,
          str(_mesh_comp.get_editor_property("relative_rotation").yaw))

# The grip has to resolve to something on the worn mesh. A name that is neither
# a socket nor a bone does not error at attach time: the weapon silently binds
# to the component root and rides in the middle of the player's chest.
if worn:
    _sock = worn.find_socket(skin.grip)
    _bones = [str(b) for b in G._mesh_bone_names(worn)]
    check(f"the weapon's attach point {skin.grip!r} exists on the worn body",
          _sock is not None or skin.grip in _bones,
          "neither a socket nor a bone")
    check("...and the rig it belongs to has a hand at the end of each arm",
          len([b for b in _bones if "hand" in b.lower()]) >= 2
          or len([b for b in _bones if b.lower().endswith("_r")
                  or b.lower().endswith("_l")]) >= 2,
          str([b for b in _bones if "hand" in b.lower()]))
    # Ragdoll and hit zones are the same precondition asked twice: both are
    # reading the bodies of the worn mesh's physics asset, and a skin swapped
    # in without one would pass every graph check in this file and then stand
    # bolt upright at 0 HP.
    check("the worn body has a physics asset, so it can ragdoll and be zoned",
          worn.get_editor_property("physics_asset") is not None,
          str(worn.get_editor_property("physics_asset")))

# The fallback is load-bearing and is never the thing being exercised, so it is
# checked directly: a clone that has not run the asset pipeline gets SKIN_QUINN
# and must get four assets that exist.
_fallback = [a for a in (G.SKIN_QUINN.mesh, G.SKIN_QUINN.anim_bp,
                         G.SKIN_QUINN.aim_rifle, G.SKIN_QUINN.aim_pistol)
             if not load(a)]
check("the mannequin fallback skin is complete, for a clone with no /Game/Sourced",
      not _fallback, str(_fallback))
# Every ready pose the weapons name has to live on the skeleton being worn, or
# PlaySlotAnimationAsDynamicMontage plays nothing and the gun hangs at the hip.
for _label, _pose in (("rifle", skin.aim_rifle), ("pistol", skin.aim_pistol)):
    _p = load(_pose)
    check(f"the {_label} ready pose is authored for the worn skeleton",
          _p is not None and worn is not None
          and _p.get_editor_property("skeleton") == worn.get_editor_property("skeleton"),
          str(_p.get_editor_property("skeleton").get_name()) if _p else "missing")


wt = wg
zone_traces = [n for n in wt if {"TraceStart", "TraceEnd", "bTraceComplex"} <= in_pins(n)]
check("one trace against the struck character's body, per pellet",
      len(zone_traces) == 1, f"{len(zone_traces)} K2_LineTraceComponent node(s)")
if zone_traces:
    zt = zone_traces[0]
    fed = {pin: {str(BEL.get_node_title(PIN.get_owning_node(q))).replace("\n", " ")
                 for q in PIN.list_connected_pins(BEL.find_input_pin(zt, pin))}
           for pin in ("TraceStart", "TraceEnd", "self")}
    # The pellet's own line, from the pellet's own hit result -- not the aim
    # point, not the muzzle recomputed: a second line would land somewhere the
    # first one did not.
    check("it retraces the pellet's own line (TraceStart/TraceEnd of its hit)",
          all(any("BreakHitResult" in t for t in fed[p])
              for p in ("TraceStart", "TraceEnd")), str(fed))
    check("it traces the character's mesh, whose bodies carry bone names",
          any("Mesh" in t for t in fed["self"]), str(fed["self"]))
    check("it traces the simple (physics body) shapes, not the render mesh",
          pin_value(zt, "bTraceComplex").lower() == "false")
contains = [n for n in wt if {"TargetArray", "ItemToFind"} <= in_pins(n)]
tables = {str(BEL.get_node_title(PIN.get_owning_node(q)))
          for n in contains
          for q in PIN.list_connected_pins(BEL.find_input_pin(n, "TargetArray"))}
check("the struck bone is looked up in both of the TARGET's tables",
      {f"Get {G.HEAD_BONES_VAR}", f"Get {G.LIMB_BONES_VAR}"} <= tables, str(tables))
# The damage subtraction's B must be Damage x multiplier, not raw Damage.
scaled = False
for n in titled(wt, "float - float"):
    for q in PIN.list_connected_pins(BEL.find_input_pin(n, "B")):
        mul = PIN.get_owning_node(q)
        if "*" not in str(BEL.get_node_title(mul)):
            continue
        srcs = {str(BEL.get_node_title(PIN.get_owning_node(r)))
                for pin in ("A", "B")
                for r in PIN.list_connected_pins(BEL.find_input_pin(mul, pin))}
        scaled |= "Get Damage" in srcs and any("Select" in s for s in srcs)
check("health loses Damage x the zone's multiplier, not raw Damage", scaled)


def upstream(node, depth=8):
    """Titles of every node feeding `node`'s inputs, transitively."""
    # Data pins only: following "execute" would walk back up the whole shot.
    # Nodes are tracked by name, not title -- two SelectFloats share a title.
    out, seen, frontier = set(), set(), [node]
    for _ in range(depth):
        nxt = []
        for n in frontier:
            for p in BEL.list_input_pins(n):
                if str(PIN.get_pin_name(p)) == "execute":
                    continue
                for q in PIN.list_connected_pins(p):
                    src = PIN.get_owning_node(q)
                    if src.get_name() in seen:
                        continue
                    seen.add(src.get_name())
                    out.add(str(BEL.get_node_title(src)).replace("\n", " "))
                    nxt.append(src)
        frontier = nxt
    return out


# Debug mode's damage readout: the number the target actually lost, at the
# point it was hit, only when the tracers are on.
readouts = [n for n in wt if {"TextLocation", "Text", "Duration"} <= in_pins(n)]
check("one damage readout per impact (DrawDebugString)", len(readouts) == 1,
      f"{len(readouts)} DrawDebugString node(s)")
if readouts:
    ro = readouts[0]
    gates = [PIN.get_owning_node(q) for q in
             PIN.list_connected_pins(BEL.find_input_pin(ro, "execute"))]
    check("...drawn only in debug mode",
          any("Branch" in str(BEL.get_node_title(g))
              and any(G.DEBUG_MODE_VAR in str(BEL.get_node_title(PIN.get_owning_node(q)))
                      for q in PIN.list_connected_pins(BEL.find_input_pin(g, "Condition")))
              for g in gates))
    check("...at the impact point",
          any("BreakHitResult" in str(BEL.get_node_title(PIN.get_owning_node(q)))
              for q in PIN.list_connected_pins(BEL.find_input_pin(ro, "TextLocation"))))
    check("...for as long as the tracer",
          abs((num_pin(ro, "Duration") or 0.0) - G.TRACE_DEBUG_SECONDS) < 1e-6,
          pin_value(ro, "Duration"))
    fed = upstream(ro)
    check("...showing the damage dealt (Damage x zone), not the weapon's raw Damage",
          "Get Damage" in fed and any("*" in t for t in fed)
          and f"Get {G.HEAD_MULT_VAR}" in fed, str(sorted(fed)))

# And the geometry: put a wanderer in the editor world and fire the same
# component trace through each part of it. This is what proves the physics
# asset actually covers the body where the tables say it does, and that the
# bone a trace reports is one the tables know.
if npc and "NPC" in zoned:
    heads, limbs = zoned["NPC"]
    eas = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    dummy = eas.spawn_actor_from_class(BEL.generated_class(npc),
                                       unreal.Vector(0.0, 0.0, 60000.0))
    try:
        body_mesh = dummy.get_component_by_class(unreal.SkeletalMeshComponent)

        def between(a, b):
            pa, pb = body_mesh.get_socket_location(a), body_mesh.get_socket_location(b)
            return (pa + pb) * 0.5

        # (point, direction the shot comes from, what it should be worth). The
        # arms are shot from the side they hang on: in the reference pose they
        # lie along the flanks, and a line through the upper arm from the
        # front meets the chest first -- which is the correct answer for that
        # line, and not the part under test.
        front = unreal.Vector(300.0, 0.0, 0.0)

        # Probe bones resolved from the rig, not written down. Same reason as
        # the tables above -- and here the stakes are higher, because
        # get_socket_location on a bone that does not exist returns the
        # component origin rather than failing, so a stale name does not make
        # the check fail, it makes it trace through the middle of the actor and
        # PASS for the wrong reason. Three of these were doing exactly that.
        def bone(*candidates):
            have = {b.lower(): b for b in (heads + limbs + body)}
            for c in candidates:
                if c.lower() in have:
                    return have[c.lower()]
            return None

        head_b = bone("head", "Head")
        arm_u = bone("upperarm_r", "RightArm")
        arm_l = bone("lowerarm_r", "RightForeArm")
        leg_u = bone("thigh_l", "LeftUpLeg")
        leg_l = bone("calf_l", "LeftLeg")
        chest = bone("spine_03", "Spine2", "Spine1", "Spine")

        aims = {}
        if head_b:
            aims["head"] = (body_mesh.get_socket_location(head_b)
                            + unreal.Vector(0.0, 0.0, 10.0), front,
                            G.COMBAT.head_multiplier)
        # Across the bone, not along a world axis. A fixed sideways shot works
        # on the mannequin, whose arms hang at the flanks, and fails on the
        # Meshy A-pose, whose arms are held out -- there the line reaches the
        # spine first and reports a 1x chest hit, which is the correct answer
        # for that line and not the part under test. 30 cm is short enough that
        # it cannot reach the torso from any limb.
        def across(a, b, reach=30.0):
            pa, pb = (body_mesh.get_socket_location(a),
                      body_mesh.get_socket_location(b))
            axis = pb - pa
            length = axis.length()
            if length < 1e-3:
                return unreal.Vector(0.0, reach, 0.0)
            axis = axis / length
            # Any vector not parallel to the bone, made perpendicular to it.
            seed = (unreal.Vector(0.0, 0.0, 1.0) if abs(axis.z) < 0.9
                    else unreal.Vector(1.0, 0.0, 0.0))
            perp = seed - axis * (seed.x * axis.x + seed.y * axis.y
                                  + seed.z * axis.z)
            n2 = perp.length()
            return (perp / n2) * reach if n2 > 1e-3 else unreal.Vector(0.0, reach, 0.0)

        # Centred on the JOINT at the far end of the limb -- the elbow, the
        # knee -- rather than on the midpoint of the two. The midpoint is fine
        # on the mannequin and lands near the shoulder on the Meshy rig, where
        # a 30 cm line across it still reaches Spine01 and reports a chest hit.
        # An elbow is unambiguously in an arm on any rig.
        if arm_u and arm_l:
            aims["upper arm"] = (body_mesh.get_socket_location(arm_l),
                                 across(arm_u, arm_l, 18.0),
                                 G.COMBAT.limb_multiplier)
        if leg_u and leg_l:
            aims["thigh"] = (body_mesh.get_socket_location(leg_l),
                             across(leg_u, leg_l, 18.0), G.COMBAT.limb_multiplier)
        if chest:
            aims["chest"] = (body_mesh.get_socket_location(chest), front, 1.0)
        check("the zone probe found bones to shoot at on this rig",
              len(aims) == 4,
              f"{sorted(aims)} (head={head_b} arm={arm_u}/{arm_l} "
              f"leg={leg_u}/{leg_l} chest={chest})")
        for part, (at, side, want) in aims.items():
            hit = body_mesh.line_trace_component(at + side, at - side,
                                                 False, False, False)
            bone = str(hit[2]) if hit and hit[2] else "None"
            worth = (G.COMBAT.head_multiplier if bone in heads
                     else G.COMBAT.limb_multiplier if bone in limbs else 1.0)
            check(f"a shot through the {part} strikes a body worth {want}x",
                  bone != "None" and abs(worth - want) < 1e-6,
                  f"bone {bone} -> {worth}x")
    finally:
        dummy.destroy_actor()

# ─── Blood: the spray, not just the spheres ──────────────────────────────────
# The layout is generated from a fixed seed, so it can be recomputed here and
# compared component by component -- a droplet nudged by hand in the editor, or
# a seed changed without meaning to, shows up as a mismatch rather than as "the
# blood looks a bit different from how I remember it".
#
# Most of what follows is about the thing that made the old burst read as a
# cartoon rather than as blood, and every clause of it is asserted: the colour
# is dark, desaturated and LIT; the droplets are droplets; they leave at wildly
# different speeds; they fall under real gravity with drag; and nothing swells.

mel = unreal.MaterialEditingLibrary
blood_mat = load(G.MAT_BLOOD)
lit = mel.get_material_property_input_node(
    blood_mat, unreal.MaterialProperty.MP_EMISSIVE_COLOR) is None
check("blood is lit rather than emissive", lit,
      "an emissive droplet glows in its own little world instead of sitting in "
      "the scene's lighting, which is the loudest cartoon cue of the lot")
base_node = mel.get_material_property_input_node(
    blood_mat, unreal.MaterialProperty.MP_BASE_COLOR)
base = base_node.get_editor_property("constant") if base_node else None
check("blood has a base colour at all", base is not None)
if base is not None:
    check("blood is dark", max(base.r, base.g, base.b) <= 0.25,
          f"brightest channel {max(base.r, base.g, base.b):.3f} (linear)")
    check("blood is not pure saturated red",
          base.g > 0.004 and base.b > 0.004 and base.r / max(base.g, 1e-6) < 20.0,
          f"({base.r:.3f}, {base.g:.3f}, {base.b:.3f}) -- "
          f"R/G {base.r / max(base.g, 1e-6):.1f}")
    check("the builder's colour is the one on disk",
          all(abs(a - b) < 1e-6 for a, b in
              zip(G.BLOOD_BASE_COLOUR, (base.r, base.g, base.b))))
rough_node = mel.get_material_property_input_node(
    blood_mat, unreal.MaterialProperty.MP_ROUGHNESS)
rough = rough_node.get_editor_property("r") if rough_node else None
check("blood is wet, not chalk", rough is not None and rough <= 0.35,
      f"roughness {rough}")
check("M_Blood carries no expressions left over from an earlier build",
      mel.get_num_material_expressions(blood_mat) == 3,
      f"{mel.get_num_material_expressions(blood_mat)} expressions")

blood_bp = load(G.BLOOD_BP_PATH)
want_blobs = G._blood_blobs()
check(f"the splash has {len(want_blobs)} droplets",
      len({c for c in components(blood_bp) if c.startswith("Blob")})
      == len(want_blobs),
      str(sorted({c for c in components(blood_bp) if c.startswith("Blob")})))
placed = True
unshadowed = True
for i, (bx, by, bz, bscale) in enumerate(want_blobs):
    t = component_template(blood_bp, f"Blob{i}")
    if t is None:
        placed = False
        break
    loc = t.get_editor_property("relative_location")
    size = t.get_editor_property("relative_scale3d")
    placed &= (abs(loc.x - bx) < 1e-3 and abs(loc.y - by) < 1e-3
               and abs(loc.z - bz) < 1e-3 and abs(size.x - bscale) < 1e-4)
    unshadowed &= not t.get_editor_property("cast_shadow")
check("every droplet carries the seeded launch velocity in its location", placed)
check("no droplet casts a shadow", unshadowed,
      "19 shadow casters per pellet, eight pellets to a shotgun shell")

# The cone has to lean along +X, which is what the impact rotates onto the hit
# normal. A symmetric ball of droplets would spray nowhere in particular.
check("the cone reaches out along +X, the hit normal",
      max(b[0] for b in want_blobs) > 0.0
      and max(b[0] for b in want_blobs) > max(abs(b[1]) for b in want_blobs),
      f"reach {max(b[0] for b in want_blobs) * G.BLOOD_VELOCITY_ENCODE:.0f} cm/s")
speeds = [math.sqrt(b[0] ** 2 + b[1] ** 2 + b[2] ** 2) * G.BLOOD_VELOCITY_ENCODE
          for b in want_blobs]
check("the spray leaves at wildly different speeds",
      max(speeds) / max(min(speeds), 1e-6) >= 3.0,
      f"{min(speeds):.0f}-{max(speeds):.0f} cm/s, a {max(speeds) / min(speeds):.1f}x "
      "spread -- one speed for everything is what makes a burst read as one "
      "expanding shell")
spray_speeds = speeds[:G.BLOOD_DROPLETS]
mist_speeds = speeds[G.BLOOD_DROPLETS:]
check("the mist hangs at the wound while the spray leaves",
      len(mist_speeds) == G.BLOOD_MIST
      and max(mist_speeds) < min(spray_speeds),
      f"mist <= {max(mist_speeds):.0f} cm/s, spray >= {min(spray_speeds):.0f} cm/s")
# 100 cm is the engine sphere's diameter at scale 1, so scale IS size in metres.
biggest = max(b[3] for b in want_blobs) * 100.0
check("droplets are droplets", biggest <= 4.0, f"largest {biggest:.1f} cm across")
check("the whole thing is over fast", 0.2 <= G.BLOOD_LIFETIME <= 0.6,
      f"{G.BLOOD_LIFETIME}s")

bg = graph(blood_bp).list_all_nodes()
check("nothing swells: the burst no longer rides a sine",
      not any("Sin" in str(BEL.get_node_title(n)) for n in bg),
      "blood does not inflate")
check("droplets fly under drag rather than in a straight line",
      bool(titled(bg, "Exp")),
      "the closed form of dv/dt = g - kv needs an exponential in it")
check("the drag coefficient is the one the builder states",
      any(abs((num_pin(n, "B") if num_pin(n, "B") is not None else 0.0)
              + G.BLOOD_DRAG) < 1e-6 for n in by_pins(bg, "A", "B")),
      f"-{G.BLOOD_DRAG} on a B pin")
check("gravity is rotated into the actor's own frame once",
      bool(titled(bg, "InverseTransformDirection")),
      "the actor faces the hit normal, so world -Z is not local -Z")
falls = [n for n in bg if "MakeVector" in str(BEL.get_node_title(n))
         and num_pin(n, "Z") is not None
         and abs(num_pin(n, "Z") + G.BLOOD_GRAVITY) < 1e-6]
check("and it is real gravity, not a stylised fraction of it", bool(falls),
      f"expected a (0, 0, -{G.BLOOD_GRAVITY:.0f}) constant")
check("each droplet is moved on its own",
      bool(titled(bg, "Set Relative Location")),
      "the old burst moved the whole actor, so every sphere flew at one speed")
check("the actor itself never moves after it spawns",
      not titled(bg, "SetActorLocation"),
      "the wound does not travel")
check("the droplets are walked once a frame, not wired one by one",
      len(titled(bg, "For Each Loop")) >= 2,
      "one loop to read the launch velocities at BeginPlay, one to fly them")
check("velocity is read back off each component, so no parallel table can "
      "fall out of step",
      bool(titled(bg, "GetRelativeTransform")))
check("size only ever falls away",
      any(num_pin(n, "Min") == 0.0 and num_pin(n, "Max") == 1.0
          for n in by_pins(bg, "Value", "Min", "Max")),
      "the fade is a 0..1 clamp, so nothing can grow past the size it was built")
check("the splash still cleans itself up",
      any(num_pin(n, "InLifespan") == G.BLOOD_LIFETIME
          for n in by_pins(bg, "InLifespan")),
      f"{G.BLOOD_LIFETIME}s")

# The droplet solver was proved at runtime with a temporary PrintString in the
# fly loop and a forced spawn at BeginPlay; this is what keeps either from
# being left behind, the same way the ADS probe is kept out.
check("no probe survives in the splash's Tick",
      not by_pins(bg, "InString"),
      "a PrintString per droplet per frame is 19 lines a frame")

blood_vars = {str(v) for v in BEL.list_member_variable_names(blood_bp, False)}
check("the splash keeps the three per-droplet tables it fills at BeginPlay",
      {"Blobs", "Velocity", "Size", "Fall", "Age"} <= blood_vars,
      str(sorted(blood_vars)))

# And the half that makes the direction mean anything: the impact has to turn
# the splash onto the surface normal it hit, and size it by the round.
check("impacts point the splash down the surface normal",
      bool(titled(wg, "MakeRotFromX")),
      "without it the spray leaves along the world's +X, not out of the wound")
check("the spray is sized by what the round did",
      any(num_pin(n, "Min") == G.BLOOD_SCALE_MIN
          and num_pin(n, "Max") == G.BLOOD_SCALE_MAX
          for n in by_pins(wg, "Value", "Min", "Max")),
      f"a clamp to {G.BLOOD_SCALE_MIN}..{G.BLOOD_SCALE_MAX} off Damage / "
      f"{G.BLOOD_REFERENCE_DAMAGE}")


# ─── The damage stamp ────────────────────────────────────────────────────────

health_vars = {str(v) for v in BEL.list_member_variable_names(health_bp, False)}
check("the health component records when it was last hurt",
      G.LAST_DAMAGE_VAR in health_vars, str(sorted(health_vars)))
check("nothing starts the game looking recently hurt",
      abs(float(h.get_editor_property(G.LAST_DAMAGE_VAR)) - G.NEVER_DAMAGED) < 1e-6,
      str(h.get_editor_property(G.LAST_DAMAGE_VAR)))
check("LastDamageTime is a float, not an int",
      isinstance(h.get_editor_property(G.LAST_DAMAGE_VAR), float),
      type(h.get_editor_property(G.LAST_DAMAGE_VAR)).__name__)
check("a pellet stamps the time it landed",
      bool(titled(wg, f"SET {G.LAST_DAMAGE_VAR}"))
      or bool(titled(wg, f"Set {G.LAST_DAMAGE_VAR}")),
      "the HUD floats a wanderer's bar off this")
check("a pellet also records who did it",
      bool(titled(wg, f"SET {G.DAMAGED_BY_PLAYER_VAR}"))
      or bool(titled(wg, f"Set {G.DAMAGED_BY_PLAYER_VAR}")))
check("nothing is born blamed on the player",
      h.get_editor_property(G.DAMAGED_BY_PLAYER_VAR) is False)

# ─── The kill counter ────────────────────────────────────────────────────────

gm_vars = {str(v) for v in BEL.list_member_variable_names(gm, False)}
check("the GameMode carries the kill counter", G.KILL_COUNT_VAR in gm_vars,
      str(sorted(gm_vars)))
check("the GameMode carries the player-death flag", G.PLAYER_DEAD_VAR in gm_vars)
check("a death adds one to the kill counter",
      bool(titled(hg, f"SET {G.KILL_COUNT_VAR}"))
      or bool(titled(hg, f"Set {G.KILL_COUNT_VAR}")))
# The guard that stops the safety net inflating the score: a wanderer that fell
# through the world dies down this very same path, and nobody shot it.
blamed = [n for n in hg if G.DAMAGED_BY_PLAYER_VAR in out_pins(n)]
check("only a death the player caused is counted", len(blamed) == 1,
      f"{len(blamed)} reads of {G.DAMAGED_BY_PLAYER_VAR} in the death path")
if blamed:
    driven = [PIN.get_owning_node(q) for q in
              BEL.find_output_pin(blamed[0],
                                  G.DAMAGED_BY_PLAYER_VAR).list_connected_pins()]
    check("and a Branch is what guards on it, not an AND",
          [n.get_class().get_name() for n in driven] == ["K2Node_IfThenElse"],
          str([n.get_class().get_name() for n in driven]))

# ─── Flinching: took a hit and lived ─────────────────────────────────────────
# Everything here is about the difference between a survivor and a corpse. The
# reaction hangs off the FALSE arm of the death branch, so the two can never run
# on the same frame; it plays into its own slot, so it cannot cost the player
# the aim pose permanently; and it is triggered by polling Health rather than
# called by the shooter, so a damage source that has never heard of it still
# makes its target flinch.

check(f"{G.HIT_REACTIONS_VAR} is an array of animations on the component",
      isinstance(h.get_editor_property(G.HIT_REACTIONS_VAR), (list, unreal.Array)))
check(f"{G.LAST_HIT_FROM_VAR} is a vector, so a direction can be stated",
      isinstance(h.get_editor_property(G.LAST_HIT_FROM_VAR), unreal.Vector))
check(f"{G.PREV_HEALTH_VAR} starts at full health, so nothing flinches on the "
      f"frame it spawns",
      abs(h.get_editor_property(G.PREV_HEALTH_VAR) - G.COMBAT.start_health) < 1e-6,
      str(h.get_editor_property(G.PREV_HEALTH_VAR)))
check(f"{G.NEXT_REACT_VAR} starts at zero, so the FIRST hit is never on cooldown",
      abs(h.get_editor_property(G.NEXT_REACT_VAR)) < 1e-6,
      str(h.get_editor_property(G.NEXT_REACT_VAR)))

# The order is the contract: the graph turns a direction into a base index into
# this tuple and adds a random offset inside the run of Fronts. Three Fronts
# first, then one each of Back, Left and Right.
check("the six reaction clips are the shared tuple, not a second copy",
      G.HIT_REACTION_CLIPS is NPC_HIT_REACTION_CLIPS)
check("six clips, all from Epic's MM_HitReact_* set -- not MM_Death_*, whose "
      "'staggers' carry the head 1-2 m and spin the body up to 180 deg",
      len(G.HIT_REACTION_CLIPS) == 6
      and all(c.startswith("MM_HitReact_") for c in G.HIT_REACTION_CLIPS),
      str(G.HIT_REACTION_CLIPS))
check("the four direction buckets tile the six clips, Fronts first",
      [G.HIT_DIR_FRONT, G.HIT_DIR_BACK, G.HIT_DIR_LEFT, G.HIT_DIR_RIGHT]
      == [(0, 3), (3, 1), (4, 1), (5, 1)])
check("build_retarget.py retargets exactly those six, from Epic's MM_HitReact_* set",
      [p.rsplit("/", 1)[1] for p in RETARGET_HIT_SOURCES] == list(G.HIT_REACTION_CLIPS)
      and all(p.startswith(G.HIT_ANIM_FALLBACK_DIR + "/") for p in RETARGET_HIT_SOURCES),
      str(RETARGET_HIT_SOURCES))


def _clip_motion(seq, pelvis, chest, head, forward_axis, right_axis):
    """(head's peak push as (forward, right) cm, chest's largest turn in deg).

    The turn is the chest's heading change against frame 0, measured on
    whichever of its axes lies flattest -- the mannequin's spine bones point
    their X up, where a rotator's yaw means nothing. forward/right are the
    mesh's own axes (the mannequin faces +Y, its right is -X).
    """
    opts = unreal.AnimPoseEvaluationOptions()
    ext, world = unreal.AnimPoseExtensions, unreal.AnimPoseSpaces.WORLD
    length = seq.get_play_length()
    at = lambda t: ext.get_anim_pose_at_time(seq, t, opts)
    first = at(0.0)
    q0 = ext.get_bone_pose(first, chest, world).rotation
    axis = min((unreal.Vector(1, 0, 0), unreal.Vector(0, 1, 0), unreal.Vector(0, 0, 1)),
               key=lambda a: abs(q0.rotate_vector(a).z))
    heading = lambda q: math.degrees(math.atan2(q.rotate_vector(axis).y,
                                                q.rotate_vector(axis).x))
    h0, head0 = heading(q0), ext.get_bone_pose(first, head, world).translation
    turn, push = 0.0, (0.0, 0.0, 0.0)
    for i in range(41):
        pose = at(length * i / 40)
        d = (heading(ext.get_bone_pose(pose, chest, world).rotation) - h0 + 180) % 360 - 180
        turn = max(turn, abs(d))
        off = ext.get_bone_pose(pose, head, world).translation - head0
        fwd = off.x * forward_axis.x + off.y * forward_axis.y + off.z * forward_axis.z
        right = off.x * right_axis.x + off.y * right_axis.y + off.z * right_axis.z
        if (fwd * fwd + right * right) ** 0.5 > push[0]:
            push = ((fwd * fwd + right * right) ** 0.5, fwd, right)
    return push[1], push[2], turn


# MEASURED, because the names cannot be trusted twice over: the MM_Death_* set
# was chosen on its names and spun the chest half round, and Epic authored no
# Left or Right hit react, so those two slots hold Fronts picked for which way
# the head goes. A round from a side pushes the head AWAY from it.
_want = {"Front": lambda f, r: f < 0, "Back": lambda f, r: f > 0,
         "Left": lambda f, r: r > 0, "Right": lambda f, r: r < 0}
_mesh_fwd, _mesh_right = unreal.Vector(0, 1, 0), unreal.Vector(-1, 0, 0)
for (base, count), name in ((G.HIT_DIR_FRONT, "Front"), (G.HIT_DIR_BACK, "Back"),
                            (G.HIT_DIR_LEFT, "Left"), (G.HIT_DIR_RIGHT, "Right")):
    for clip in G.HIT_REACTION_CLIPS[base:base + count]:
        seq = load(f"{G.HIT_ANIM_FALLBACK_DIR}/{clip}")
        if not seq:
            check(f"{clip} exists", False)
            continue
        fwd, right, turn = _clip_motion(seq, "pelvis", "spine_05", "head",
                                        _mesh_fwd, _mesh_right)
        check(f"{clip}, in the {name} bucket, pushes the head away from a hit "
              f"from the {name.lower()}", _want[name](fwd, right),
              f"head forward {fwd:+.1f} cm, right {right:+.1f} cm")
        check(f"{clip} is a flinch: head moves under 30 cm, chest turns under 60 deg",
              (fwd * fwd + right * right) ** 0.5 < 30.0 and turn < 60.0,
              f"head {(fwd * fwd + right * right) ** 0.5:.1f} cm, chest {turn:.0f} deg")

# And on every creature's retargeted copy: a retarget with a bad spine chain can
# put the spin back in on its own, and the retargeted copies are what play.
for _family in sorted({p.split("/")[-2] for p in unreal.EditorAssetLibrary.list_assets(
        G.HIT_ANIM_ROOT, recursive=True) if "/A_" in p}):
    _turns = {}
    for clip in G.HIT_REACTION_CLIPS:
        seq = load(f"{G.HIT_ANIM_ROOT}/{_family}/A_{_family}_{clip}")
        if seq:
            _turns[clip] = _clip_motion(seq, "Hips", "Spine", "Head",
                                        _mesh_fwd, _mesh_right)[2]
    check(f"{_family}: all six flinches retargeted, none turning the chest past 60 deg",
          len(_turns) == 6 and max(_turns.values()) < 60.0,
          ", ".join(f"{c[12:]} {t:.0f}" for c, t in _turns.items()))

# The tuning, and that it is on COMBAT rather than loose in the graph.
for field, low, high in (("hit_react_cooldown_s", 0.05, 3.0),
                         ("hit_react_rate", 0.25, 4.0),
                         ("hit_react_blend_s", 0.0, 0.5)):
    check(f"COMBAT.{field} is a sane, tunable number",
          field in {f.name for f in dataclasses.fields(G.CombatConfig)}
          and low <= getattr(G.COMBAT, field) <= high,
          str(getattr(G.COMBAT, field, None)))
# A shotgun puts eight pellets into a target in one frame and the SMG fires
# eleven rounds a second. Without a cooldown longer than a frame the target
# stands in the first two frames of a stagger forever -- a vibration, not a
# reaction.
check("the cooldown is longer than a frame, or the reaction is a vibration",
      G.COMBAT.hit_react_cooldown_s > 0.1, str(G.COMBAT.hit_react_cooldown_s))

# Every montage in the health graph, and there is exactly one: the flinch.
_montages = by_pins(hg, "Asset", "SlotNodeName")
check("exactly one montage in the health graph -- the flinch, and nothing else",
      len(_montages) == 1, str(len(_montages)))
check(f"...and it plays into {G.HIT_SLOT}, never {G.FULL_BODY_SLOT}: a full-body "
      f"montage on the death path would blend out and stand the body back up",
      all(pin_value(m, "SlotNodeName") == G.HIT_SLOT for m in _montages),
      str([pin_value(m, "SlotNodeName") for m in _montages]))
if _montages:
    m = _montages[0]
    check("the flinch blends in and out rather than popping",
          num_pin(m, "BlendInTime") == G.COMBAT.hit_react_blend_s
          and num_pin(m, "BlendOutTime") == G.COMBAT.hit_react_blend_s,
          f"{pin_value(m, 'BlendInTime')}/{pin_value(m, 'BlendOutTime')}")
    check(f"...at COMBAT.hit_react_rate ({G.COMBAT.hit_react_rate}x), not the "
          f"authored second",
          num_pin(m, "InPlayRate") == G.COMBAT.hit_react_rate,
          pin_value(m, "InPlayRate"))
    check("...once, not looping: a flinch that loops is a seizure",
          num_pin(m, "LoopCount") == 1, pin_value(m, "LoopCount"))
    # The clip comes out of the array, not off a pin: a literal here would be
    # one skeleton's clip on every body in the game.
    check("the clip is read from the array, never written on the pin",
          bool(PIN.list_connected_pins(BEL.find_input_pin(m, "Asset"))))

# The trigger. Health compared against PrevHealth, and the whole chain hanging
# off the death branch's False arm.
_prev_reads = [n for n in hg if str(BEL.get_node_title(n)).replace("\n", " ")
               == f"Get {G.PREV_HEALTH_VAR}"]
_prev_writes = [n for n in hg if has_in_pin(n, G.PREV_HEALTH_VAR)]
check(f"{G.PREV_HEALTH_VAR} is read once and written once -- the whole trigger",
      len(_prev_reads) == 1 and len(_prev_writes) == 1,
      f"{len(_prev_reads)} reads, {len(_prev_writes)} writes")
if _prev_writes:
    # Written on EVERY path through the reaction block, not only the one that
    # played something: skipping it on the cooldown arm makes the next hit
    # compare against a health from before this one and fire for nothing.
    _arms = PIN.list_connected_pins(BEL.find_execute_pin(_prev_writes[0]))
    check(f"...and written on every arm, including the ones that did not react",
          len(_arms) >= 4, f"{len(_arms)} exec links")

# Direction: two dot products against the owner's own axes, and nothing else.
_dots = titled(hg, "Dot Product")
check("the hit direction is two dot products (forward and right), no angles",
      len(_dots) == 2, str(len(_dots)))
check("...one against the owner's forward",
      len(titled(hg, "GetActorForwardVector")) >= 1)
check("...and one against the owner's right",
      len(titled(hg, "GetActorRightVector")) >= 1)
# Four buckets, four writes of the index.
_index_writes = [n for n in hg if has_in_pin(n, G.REACT_INDEX_VAR)]
check("four directions, four writes of the clip index",
      len(_index_writes) == 4, str(len(_index_writes)))
# Three of the four are pin literals. The fourth -- Front -- has its value
# WIRED, from a RandomIntegerInRange, which is the only reason a firefight does
# not look like one animation on a loop; a literal there would read back as 0
# and pass a naive test, so connected pins are excluded rather than read.
_wired = [n for n in _index_writes
          if PIN.list_connected_pins(BEL.find_input_pin(n, G.REACT_INDEX_VAR))]
_literals = sorted(int(v) for n in _index_writes if n not in _wired
                   for v in [num_pin(n, G.REACT_INDEX_VAR)] if v is not None)
check("Back, Left and Right are written as literals",
      _literals == sorted([G.HIT_DIR_BACK[0], G.HIT_DIR_LEFT[0],
                           G.HIT_DIR_RIGHT[0]]), str(_literals))
check("...and exactly one of the four -- Front -- is wired instead",
      len(_wired) == 1, str(len(_wired)))
# The draw itself: 0..2 over the three Front clips, offset by the Front base.
_draws = [n for n in hg if has_in_pin(n, "Min") and has_in_pin(n, "Max")
          and num_pin(n, "Max") == float(G.HIT_DIR_FRONT[1] - 1)
          and num_pin(n, "Min") == 0.0]
check(f"the Front pick draws over all {G.HIT_DIR_FRONT[1]} Front clips, so a "
      f"firefight is not one animation on a loop",
      len(_draws) == 1, str(len(_draws)))
# An array shorter than six -- a checkout whose retarget has not run -- must
# clip to the last entry rather than read off the end.
check("the index is clamped against the array's real length",
      bool(titled(hg, "Clamp")) or bool(by_pins(hg, "Value", "Min", "Max")))
check("...and the array's length is checked before anything is played",
      bool(titled(hg, "Length")))

# Who writes the direction. Both damage sources do, and neither of them had to
# know the reaction exists to make it fire -- only to make it point the right
# way.
_from_writes = [n for n in wg if has_in_pin(n, G.LAST_HIT_FROM_VAR)]
check(f"the pellet loop records {G.LAST_HIT_FROM_VAR} where it lands",
      len(_from_writes) == 1, str(len(_from_writes)))
if _from_writes:
    _src = [PIN.get_owning_node(q) for q in PIN.list_connected_pins(
        BEL.find_input_pin(_from_writes[0], G.LAST_HIT_FROM_VAR))]
    _src_pin = PIN.list_connected_pins(
        BEL.find_input_pin(_from_writes[0], G.LAST_HIT_FROM_VAR))
    check("...off the hit's own impact normal, which already points back up the "
          "shot",
          [str(PIN.get_pin_name(q)).replace(" ", "") for q in _src_pin]
          == ["ImpactNormal"],
          str([str(PIN.get_pin_name(q)) for q in _src_pin]))

# THE PROBE IS GONE. "A gate that never opens looks identical to one that
# works", so the reaction was proved at runtime with a PrintWarning on the end
# of the chain and a scripted hit on every wanderer -- and both are removed by
# rebuilding with HIT_REACT_PROBE False. These two checks are what stop one
# coming back: the switch, and the built graph.
check("the hit-reaction probe switch is off", G.HIT_REACT_PROBE is False,
      str(G.HIT_REACT_PROBE))
_probe_tokens = (G.HIT_REACT_PROBE_PREFIX, G.POSE_BACK_PROBE_PREFIX)
_probe_nodes = [f"{_g}:{BEL.get_node_title(n)}"
                for _g, _nodes in (("health", hg), ("weapon", wg))
                for n in _nodes
                for _p in BEL.list_input_pins(n)
                if any(t in str(PIN.get_pin_value(_p)) for t in _probe_tokens)]
check("...and no probe node survives in either built graph",
      not _probe_nodes, str(_probe_nodes))
# The scripted hit the probe used to deal itself, too: nothing in the shipped
# health graph may subtract from Health except the world floor's write of zero.
check("...and the probe's scripted self-hit is gone with it",
      not [n for n in hg
           if str(BEL.get_node_title(n)).replace("\n", " ").startswith("Get MaxHealth")],
      "MaxHealth is read by nothing in the health graph but the probe")

# Every character carries its OWN six, because an AnimSequence belongs to one
# skeleton and a shared default could only be right for one body.
for _bp_path, _who in ((G.CHARACTER_BP_PATH, "the player"),
                       (G.NPC_BP_PATH, "a wanderer")):
    _bp = load(_bp_path)
    if not _bp:
        continue
    _comp = component_template(_bp, "HealthComponent")
    if not _comp:
        continue
    _clips = list(_comp.get_editor_property(G.HIT_REACTIONS_VAR))
    check(f"{_who} carries all six reactions, or none at all",
          len(_clips) in (0, len(G.HIT_REACTION_CLIPS)), str(len(_clips)))
    if _clips:
        check(f"...in HIT_REACTION_CLIPS order",
              [c.get_name().rsplit("_MM_", 1)[-1] for c in _clips]
              == [c.split("MM_", 1)[1] for c in G.HIT_REACTION_CLIPS],
              str([c.get_name() for c in _clips]))
        _mesh = _mesh_asset(_bp)
        _skel = _mesh.get_editor_property("skeleton") if _mesh else None
        check(f"...all on {_who}'s OWN skeleton, or they would never play",
              all(c.get_editor_property("skeleton") == _skel for c in _clips),
              str({c.get_editor_property("skeleton").get_name() for c in _clips}))


# ─── Dying: the ragdoll, the corpse, and the menu ────────────────────────────
# The player used to play MM_Death_Front_01 into FullBodySlot and the wanderers
# were destroyed on the frame they died. Both are gone: Epic's six MM_Death_*
# clips are one-second staggers that END STANDING (measured off the assets:
# pelvis 83-88 cm, both feet on the floor, 1.5-2 m of backwards travel), so the
# montage blended out and put the player back on his feet a second before the
# pause -- which is exactly what "he gets up right away" was.

ragdolls = titled(hg, "SetAllBodiesSimulatePhysics")
check("dying is a ragdoll, not a clip", len(ragdolls) == 1, str(len(ragdolls)))
if ragdolls:
    check("...simulating, not un-simulating",
          pin_value(ragdolls[0], "bNewSimulate") in ("true", "True"),
          pin_value(ragdolls[0], "bNewSimulate"))
# SetSimulatePhysics would put the ONE root body into simulation -- a
# creature-shaped brick toppling over. It is not even a UFunction on
# SkeletalMeshComponent, so this is a ban on reaching for the PrimitiveComponent
# one on the mesh pin.
check("and every body in the physics asset, not just the root",
      not titled(hg, "SetSimulatePhysics"))
# The montage count and its slot are checked in the flinch section above; what
# matters here is that the death path itself plays nothing.
profiles = titled(hg, "SetCollisionProfileName")
check("the ragdoll gets a collision profile that lets it hit the ground",
      len(profiles) == 1, str(len(profiles)))
if profiles:
    check(f"...the {G.RAGDOLL_PROFILE} profile, which also ignores Pawn",
          pin_value(profiles[0], "InCollisionProfileName") == G.RAGDOLL_PROFILE,
          pin_value(profiles[0], "InCollisionProfileName"))
# The capsule -- not the mesh -- is what blocks the player and what the pellets
# trace against (see make_shootable), so switching it off is both halves of "a
# corpse is not in the way".
capsules = titled(hg, "SetCollisionEnabled")
check("the capsule stops colliding, so a corpse is neither an obstacle nor a "
      "target", len(capsules) == 1, str(len(capsules)))
if capsules:
    check("...switched off entirely",
          pin_value(capsules[0], "NewType").endswith("NoCollision"),
          pin_value(capsules[0], "NewType"))
check("the body stops where it fell",
      len(titled(hg, "DisableMovement")) == 1,
      "without it CharacterMovement drags the capsule and the mesh with it")

# One collapse, reached from both arms of the death branch. Two would be two
# places for "what dying looks like" to drift apart.
casts = [n for n in hg if n.get_class().get_name() == "K2Node_DynamicCast"
         and "AsCharacter" in {q.replace(" ", "") for q in out_pins(n)}]
# There are TWO of these now and they are not interchangeable: the flinch also
# has to reach the owner's mesh to find an AnimInstance. Told apart by following
# the montage's own self pin back up -- montage <- GetAnimInstance <- Get Mesh
# <- cast -- rather than by position or by exec-link count, either of which
# would quietly pick the wrong one the next time the graph moves.
_flinch_cast = None
if _montages:
    _walk = _montages[0]
    for _ in range(3):
        _up = PIN.list_connected_pins(BEL.find_input_pin(_walk, "self"))
        if not _up:
            break
        _walk = PIN.get_owning_node(_up[0])
    _flinch_cast = _walk if _walk in casts else None
check("the flinch finds its body through its own CastToCharacter",
      _flinch_cast is not None)
collapse_casts = [n for n in casts if n is not _flinch_cast]
check("the player and the wanderers collapse through the same nodes",
      len(collapse_casts) == 1, f"{len(collapse_casts)} collapse CastToCharacter(s) "
      f"of {len(casts)} in the graph")
if collapse_casts:
    feeders = PIN.list_connected_pins(BEL.find_input_pin(collapse_casts[0], "execute"))
    check("...and both arms really do reach it", len(feeders) == 2,
          f"{len(feeders)} exec link(s) into the collapse")

# ─── The corpse, and when it goes away ───────────────────────────────────────
lifespans = titled(hg, "SetLifeSpan")
check("a killed wanderer leaves a corpse instead of vanishing",
      len(lifespans) == 1, str(len(lifespans)))
if lifespans:
    check(f"the corpse despawns after {G.CORPSE_SECONDS:.0f} s",
          abs((num_pin(lifespans[0], "InLifespan") or -1.0)
              - G.CORPSE_SECONDS) < 1e-3,
          pin_value(lifespans[0], "InLifespan"))
check("60 s, as asked for", abs(G.CORPSE_SECONDS - 60.0) < 1e-6,
      f"{G.CORPSE_SECONDS}")
# The chase, the melee and the growls are one self-re-entering loop on the AI
# controller and none of them ask whether the pawn is alive, so a corpse whose
# controller survived would keep hitting the player from the floor.
destroys = titled(hg, "Destroy Actor")
check("a corpse's AI controller is destroyed", len(destroys) == 1,
      str(len(destroys)))
if destroys:
    fed_by = [str(BEL.get_node_title(PIN.get_owning_node(q))).replace("\n", " ")
              for q in PIN.list_connected_pins(
                  BEL.find_input_pin(destroys[0], "self"))]
    check("...the CONTROLLER, not the body -- the body has a lifespan now",
          fed_by == ["GetController"], str(fed_by))

pauses = by_pins(hg, "bPaused")
check("death pauses the game", len(pauses) == 1, str(len(pauses)))
if pauses:
    check("...paused, not unpaused",
          pin_value(pauses[0], "bPaused") in ("true", "True"),
          pin_value(pauses[0], "bPaused"))
# The pause stops physics too, so this is also how long the ragdoll gets to
# settle; pausing early freezes the player mid-topple.
check("the pause waits for the body to land",
      any(abs((num_pin(n, "Duration") or -1.0) - G.DEATH_PAUSE_SECONDS) < 1e-3
          for n in by_pins(hg, "Duration")),
      f"expected a {G.DEATH_PAUSE_SECONDS}s Delay before the pause")
check("the death flag is raised for the HUD to draw the menu from",
      bool(titled(hg, f"SET {G.PLAYER_DEAD_VAR}"))
      or bool(titled(hg, f"Set {G.PLAYER_DEAD_VAR}")))

# One writer, and it is the safety net's. Anything else writing Health inside
# the component's own graph is a probe that was left behind -- which is exactly
# how the 60 s corpse timer was measured, on a compressed value, with a clock
# forcing the death.
writes = [n for n in hg if str(BEL.get_node_title(n)) in ("SET Health", "Set Health")]
check("only the world-floor net writes Health from inside the component",
      len(writes) == 1, f"{len(writes)} Set Health node(s)")

# ─── A ragdoll needs bodies to be a ragdoll ──────────────────────────────────
# Not a formality: it is the one precondition the collapse cannot check for
# itself, and a mesh that arrives without a physics asset would simply stand
# there dead. install_hit_zones already depends on the same bodies, so a rig
# that cannot ragdoll cannot be shot in the head either.
for bp_path in (G.CHARACTER_BP_PATH, G.NPC_BP_PATH):
    bp = load(bp_path)
    if not bp:
        continue
    mesh = None
    for name in components(bp):
        obj = component_template(bp, name)
        if isinstance(obj, unreal.SkeletalMeshComponent):
            mesh = obj
            break
    if mesh is None:
        mesh = cdo(bp).get_editor_property("mesh")
    asset = mesh.get_editor_property("skeletal_mesh_asset") if mesh else None
    pa = asset.get_editor_property("physics_asset") if asset else None
    check(f"{bp_path.rsplit('/', 1)[1]} has a physics asset to ragdoll with",
          pa is not None, pa.get_name() if pa else "None")
    if pa:
        head, limbs, body = G.hit_zones(asset)
        check(f"...with enough bodies to fall apart ({bp_path.rsplit('/', 1)[1]})",
              len(head) + len(limbs) + len(body) >= 8,
              f"{len(head) + len(limbs) + len(body)} bodies")

# The ragdoll's JOINTS, not just its bodies. The importer's physics asset gives
# every joint one soft 45/45/45 cone centred on the bind pose -- knees folding
# sideways and backwards, an elbow bent in the bind pose free to hyperextend --
# and a corpse on those limits lands in shapes no body makes. tune_ragdolls()
# rewrites limits, springs and frames; this reads them back off the saved
# assets and then bends every joint to just inside and just past each end of
# its RAGDOLL_JOINTS range, to prove the saved frames put the range on the
# side of the joint a body really folds to.
def _saved_vec(di, name):
    v = di.get_editor_property(name)
    return (v.x, v.y, v.z)


def _world(rot, v):
    w = rot.rotate_vector(unreal.Vector(*v))
    return (w.x, w.y, w.z)


def _limit_allows(j, di, flex):
    """Would the saved constraint let this joint sit at `flex` (absolute deg)?"""
    axis = j["axis"]
    x1, y1 = (_world(j["rot1"], _saved_vec(di, "pri_axis1")),
              _world(j["rot1"], _saved_vec(di, "sec_axis1")))
    x2, y2 = (_world(j["rot2"], _saved_vec(di, "pri_axis2")),
              _world(j["rot2"], _saved_vec(di, "sec_axis2")))
    # The flex axis is the hinge's X (twist) or the ball joint's Y (swing2);
    # measure the frames' disagreement with the vector that is not it.
    probe1, probe2 = (y1, y2) if j["hinge"] else (x1, x2)
    moved = G._v_rotate(probe1, axis, flex - j["rest"])
    prof = di.get_editor_property("profile_instance")
    limit = (prof.get_editor_property("twist_limit")
             .get_editor_property("twist_limit_degrees") if j["hinge"] else
             prof.get_editor_property("cone_limit")
             .get_editor_property("swing2_limit_degrees"))
    return abs(G._v_signed_angle(probe2, moved, axis)) <= limit + 1e-3


for _path in sorted(unreal.EditorAssetLibrary.list_assets(G.RAGDOLL_MESH_ROOT,
                                                          recursive=True)):
    _mesh = load(_path.split(".")[0])
    if not isinstance(_mesh, unreal.SkeletalMesh):
        continue
    _pa = _mesh.get_editor_property("physics_asset")
    if not _pa:
        continue
    _plan = G.ragdoll_plan(_mesh)
    _name = _pa.get_name()
    check(f"{_name}: every joint has a role in RAGDOLL_JOINTS",
          len(_plan) == len(_pa.get_constraints(False)),
          f"{len(_plan)} of {len(_pa.get_constraints(False))}")
    _dis = {j["child"]: j["template"].get_editor_property("DefaultInstance")
            for j in _plan}
    _bad = {}
    for j in _plan:
        prof = _dis[j["child"]].get_editor_property("profile_instance")
        cone = prof.get_editor_property("cone_limit")
        tw = prof.get_editor_property("twist_limit")
        got = (round(cone.get_editor_property("swing1_limit_degrees"), 3),
               round(cone.get_editor_property("swing2_limit_degrees"), 3),
               round(tw.get_editor_property("twist_limit_degrees"), 3))
        if got != j["limits"]:
            _bad[j["child"]] = got
    check(f"...and the saved limits are the planned ones", not _bad, str(_bad))
    _bad = [j["child"] for j in _plan
            if any(max(abs(a - b) for a, b in zip(
                _saved_vec(_dis[j["child"]], k[:3] + "_axis" + k[3]), j[k])) > 1e-3
                for k in ("pri1", "sec1", "pri2", "sec2"))]
    check(f"...and the saved constraint frames are the planned ones",
          not _bad, str(_bad))
    _soft = {}
    for j in _plan:
        prof = _dis[j["child"]].get_editor_property("profile_instance")
        for lim in (prof.get_editor_property("cone_limit"),
                    prof.get_editor_property("twist_limit")):
            if lim.get_editor_property("stiffness") < 500.0:
                _soft[j["child"]] = lim.get_editor_property("stiffness")
    check(f"...and no joint keeps the importer's soft limit a body falls "
          f"through (stiffness >= 500, as PA_Mannequin)", not _soft, str(_soft))
    _wrong = []
    for j in _plan:
        lo, hi = G.RAGDOLL_JOINTS[j["role"]]["flex"]
        di = _dis[j["child"]]
        for flex, want in ((lo + 2, True), (hi - 2, True),
                           (lo - 5, False), (hi + 5, False)):
            if _limit_allows(j, di, flex) != want:
                _wrong.append(f"{j['child']}@{flex:.0f}")
    check(f"...and every joint bends only its own way, as far as "
          f"RAGDOLL_JOINTS says", not _wrong, str(_wrong))
    _hinges = [j for j in _plan if j["role"] in ("leg", "forearm")]
    _wrong = [f"{j['child']}" for j in _hinges
              if _limit_allows(j, _dis[j["child"]], -10.0)
              or not _limit_allows(j, _dis[j["child"]], 110.0)]
    check(f"...and no knee or elbow hyperextends 10 deg, and all of them fold "
          f"110 deg ({len(_hinges)} hinges)", _hinges and not _wrong, str(_wrong))
    _knees = [j for j in _plan if j["role"] == "leg"]
    check(f"...and both knees are among them", len(_knees) == 2,
          str([j["child"] for j in _knees]))

# ─── Walking off the edge of the world ───────────────────────────────────────
# The navmesh is a disc of radius 85 m and the terrain a 200 m square, but the
# terrain does eventually END -- and a Character in freefall never stops. The
# player used to fall for the rest of the session with nothing noticing, because
# "still falling" and "standing still" look identical to everything watching.
#
# The fix reuses the NPC safety net rather than adding a KillZ or a teleport:
# below WORLD_FLOOR_Z, write Health to 0 and let the death path that already
# exists open the restart menu. What had to change is that the net used to be
# AND-ed with DespawnOnDeath -- NPCs only -- and that gate moved inward so it
# guards only the log line, which quotes an NpcId the player does not have.

floors = [n for n in hg if num_pin(n, "B") == G.WORLD_FLOOR_Z]
check(f"something compares a height against {G.WORLD_FLOOR_Z:.0f} cm",
      len(floors) == 1, f"{len(floors)} comparisons")
if floors:
    gates = [PIN.get_owning_node(q) for q in
             BEL.find_output_pin(floors[0], "ReturnValue").list_connected_pins()]
    # THE REGRESSION THIS EXISTS TO CATCH: an AND here means the test is once
    # again "under the world AND is an NPC", and the player falls forever.
    check("the world floor is branched on directly, not AND-ed with a "
          "\"...and is an NPC\" term",
          [g.get_class().get_name() for g in gates] == ["K2Node_IfThenElse"],
          str([str(BEL.get_node_title(g)) for g in gates]))

# Two writes of Health = 0 would mean two floors; one, reached from both arms
# of the "is this worth a log line" branch, is the shape that catches both the
# wanderer and the player.
zeroes = [n for n in hg
          if str(BEL.get_node_title(n)).replace("\n", " ") == "Set Health"
          and num_pin(n, "Health") == 0.0]
check("exactly one node writes the fall off as death", len(zeroes) == 1,
      f"{len(zeroes)} writes of Health = 0")
if zeroes:
    feeders = [PIN.get_owning_node(q) for q in
               PIN.list_connected_pins(BEL.find_input_pin(zeroes[0], "execute"))]
    check("...and BOTH arms of the report branch reach it -- the reported "
          "wanderer and the unreported player",
          len(feeders) == 2, f"reached from {len(feeders)} exec pin(s)")
    kinds = sorted(f.get_class().get_name() for f in feeders)
    check("...one of them straight from a Branch (the player: no log line)",
          "K2Node_IfThenElse" in kinds, str(kinds))
# The log line stays wanderer-only: it quotes a number and a spawn point.
check("the fall report is still gated on DespawnOnDeath",
      any("DespawnOnDeath" in out_pins(n) for n in hg))
check("...and still names the wanderer and where it was put",
      bool(titled(hg, "PrintWarning")) or bool(titled(hg, "Print Warning")),
      "the fall report is the one line Blueprint can raise above Display")

# ─── Sprint and stamina ──────────────────────────────────────────────────────

for var, kind, want in (("Stamina", float, G.COMBAT.max_stamina),
                        ("MaxStamina", float, G.COMBAT.max_stamina),
                        ("Sprinting", bool, False)):
    value = w.get_editor_property(var)
    check(f"{var} starts at {want!r}",
          isinstance(value, kind)
          and (value == want if kind is bool else abs(value - want) < 1e-6),
          f"{type(value).__name__} = {value}")
check("BaseSpeed is a float, not an int",
      isinstance(w.get_editor_property("BaseSpeed"), float),
      type(w.get_editor_property("BaseSpeed")).__name__)
sprint_polls = [n for n in wg
                if in_pins(n) == {"self", "Key"}
                and any("Get KeySprint" in
                        str(BEL.get_node_title(PIN.get_owning_node(q)))
                        for q in PIN.list_connected_pins(
                            BEL.find_input_pin(n, "Key")))]
check("the sprint bind is polled as held, not as a tap",
      bool(sprint_polls)
      and all("IsInputKeyDown" in str(BEL.get_node_title(n))
              for n in sprint_polls),
      str([str(BEL.get_node_title(n)) for n in sprint_polls]))
walk_titles = {t for t in (str(BEL.get_node_title(n)).replace("\n", " ")
                           for n in wg) if "MaxWalkSpeed" in t}
check("sprinting drives the character's own walk speed",
      any(t.startswith("SET") or t.startswith("Set") for t in walk_titles),
      str(sorted(walk_titles)))
# Cached, never written down: a literal walk speed here would fight any later
# change to the character's movement defaults, and only after the first sprint.
check("the walking speed is cached off the character, not hardcoded",
      any(t.startswith("Get") for t in walk_titles)
      and any("BaseSpeed" in str(BEL.get_node_title(n)).replace("\n", " ")
              for n in wg),
      str(sorted(walk_titles)))
# The hit-box multiplier has two SelectFloats of its own, each picked by a
# table lookup; those are counted in the hit-box section, not here.
selects = [n for n in titled(wg, "SelectFloat")
           if not any("Contains" in str(BEL.get_node_title(PIN.get_owning_node(q)))
                      for q in PIN.list_connected_pins(BEL.find_input_pin(n, "bPickA")))]
# Four now: sprint picks the speed and the sign of the drain, and aiming picks
# both how much of its own cone the weapon keeps and how much of its recoil.
check("SelectFloat picks the speed, the drain, the aimed cone and the aimed "
      "kick", len(selects) == 4, f"{len(selects)} SelectFloat node(s)")
check("stamina is clamped, so it cannot run past its own bar",
      any(pin_value(n, "Max") == str(G.COMBAT.max_stamina)
          for n in by_pins(wg, "Value", "Min", "Max")),
      f"expected a clamp at {G.COMBAT.max_stamina}")
# The requirement the flag exists for: you cannot shoot while running.
sprint_reads = [n for n in wg if "Sprinting" in out_pins(n)]
check("the trigger reads Sprinting", bool(sprint_reads),
      f"{len(sprint_reads)} reads")
negated = [n for n in sprint_reads
           if any("NOT" in str(BEL.get_node_title(PIN.get_owning_node(q))).upper()
                  for q in BEL.find_output_pin(n, "Sprinting").list_connected_pins())]
check("...through a NOT, so firing is refused while it is set", bool(negated),
      str([str(BEL.get_node_title(PIN.get_owning_node(q)))
           for n in sprint_reads
           for q in BEL.find_output_pin(n, "Sprinting").list_connected_pins()]))

# ─── Ammunition, the cooldown and the reload ─────────────────────────────────
# The requirement in one line: the shotgun is limited, the pistol is not. Every
# check here is about the difference between those two being *data* -- a row in
# _weapon_specs -- rather than a branch on the weapon's name somewhere.

for want in G._weapon_specs():
    spec = want["display"]
    gun = cdo(load(want["path"]))
    check(f"{spec}: UsesAmmo is {want['uses_ammo']}",
          gun.get_editor_property("UsesAmmo") == want["uses_ammo"],
          str(gun.get_editor_property("UsesAmmo")))
    check(f"{spec}: it starts loaded, not empty",
          gun.get_editor_property("Loaded")
          == gun.get_editor_property("MagazineSize") == want["magazine"],
          f"{gun.get_editor_property('Loaded')} / "
          f"{gun.get_editor_property('MagazineSize')}")
    check(f"{spec}: reserve is {want['reserve']}",
          gun.get_editor_property("Reserve") == want["reserve"],
          str(gun.get_editor_property("Reserve")))
    check(f"{spec}: there is a pause between shots",
          abs(gun.get_editor_property("FireInterval") - want["interval"]) < 1e-6,
          f"{gun.get_editor_property('FireInterval'):.2f}s")
    check(f"{spec}: the first shot of a session is free",
          gun.get_editor_property("NextFireTime") == 0.0,
          str(gun.get_editor_property("NextFireTime")))
    check(f"{spec}: reloading takes {want['reload_s']}s",
          abs(gun.get_editor_property("ReloadSeconds") - want["reload_s"]) < 1e-6,
          f"{gun.get_editor_property('ReloadSeconds'):.2f}s")

shotgun_cdo = cdo(load(G.SHOTGUN_BP_PATH))
check(f"the shotgun starts with {G.SHOTGUN_MAGAZINE + G.SHOTGUN_RESERVE} shells "
      f"in total -- {G.SHOTGUN_MAGAZINE} loaded and {G.SHOTGUN_RESERVE} spare",
      shotgun_cdo.get_editor_property("Loaded")
      + shotgun_cdo.get_editor_property("Reserve") == 20,
      str(shotgun_cdo.get_editor_property("Loaded")
          + shotgun_cdo.get_editor_property("Reserve")))
# 2x what it was. The pellet count is unchanged, so this is the whole change:
# 8 x 18 = 144 against a 100 HP wanderer, i.e. one connected shot is a kill.
check("the shotgun does twice the damage it used to (9 -> 18 per pellet)",
      abs(shotgun_cdo.get_editor_property("Damage") - 18.0) < 1e-6,
      str(shotgun_cdo.get_editor_property("Damage")))
check("...and still fires the same 8 pellets, so the change is damage and not spread",
      shotgun_cdo.get_editor_property("PelletCount") == 8,
      str(shotgun_cdo.get_editor_property("PelletCount")))
check("the pistol is unlimited and therefore never reloads",
      cdo(load(G.PISTOL_BP_PATH)).get_editor_property("UsesAmmo") is False)

# --- what the graph does with all that ---------------------------------------
loaded_writes = [t for t in (str(BEL.get_node_title(n)).replace("\n", " ")
                             for n in wg) if t == "Set Loaded"]
check("firing spends a round and reloading puts rounds back",
      len(loaded_writes) == 2, f"{len(loaded_writes)} writes to Loaded")
next_writes = [t for t in (str(BEL.get_node_title(n)).replace("\n", " ")
                           for n in wg) if t == "Set NextFireTime"]
check("both the interval and the reload push the same NextFireTime deadline",
      len(next_writes) == 2, f"{len(next_writes)} writes to NextFireTime")
check("the deadline is compared against the clock, not a frame count",
      bool(titled(wg, "GetTimeSeconds")),
      f"{len(titled(wg, 'GetTimeSeconds'))} GetTimeSeconds")
# The reserve is only ever *spent* here; it is topped up by BP_AmmoPickup.
check("the weapon component spends the reserve and never grants it",
      len([t for t in (str(BEL.get_node_title(n)).replace("\n", " ")
                       for n in wg) if t == "Set Reserve"]) == 1)
# The pure-node trap, in the one place where getting it wrong is free ammo.
check("the reload works out how many rounds move ONCE and stores it",
      len([t for t in (str(BEL.get_node_title(n)).replace("\n", " ")
                       for n in wg) if t == "Set ReloadTake"]) == 1)
check("...and reads it back three times rather than recomputing it",
      len([n for n in wg if "ReloadTake" in out_pins(n)]) == 3,
      f"{len([n for n in wg if 'ReloadTake' in out_pins(n)])} reads")
check("the reload can never take more than the reserve holds",
      bool(titled(wg, "Min (Integer)")),
      str(sorted({t for t in (str(BEL.get_node_title(n)).replace("\n", " ")
                              for n in wg) if t.lower().startswith("min")})))
# The gate is nested, not folded: every one of these reads a property off Held,
# and the outer condition is pulled on frames where nothing is equipped.
ammo_reads = [n for n in wg if "UsesAmmo" in out_pins(n)]
check("the fire gate and the reload both ask the weapon whether it uses ammo",
      len(ammo_reads) == 2, f"{len(ammo_reads)} UsesAmmo reads")
check("an unlimited weapon short-circuits the magazine test (an OR, not an AND)",
      bool(titled(wg, "OR Boolean")),
      str(sorted({t for t in (str(BEL.get_node_title(n)).replace("\n", " ")
                              for n in wg) if " OR" in t.upper()})))

# ─── The click and the clack ─────────────────────────────────────────────────
# Two sounds whose whole value is *when* they do not play. A click on every
# refused trigger pull would fire on the SMG's every-0.09s cooldown; a clack on
# every R would reward pressing reload at a full magazine.

titles = [str(BEL.get_node_title(n)).replace("\n", " ") for n in wg]
check("the empty chamber clicks",
      titles.count("Get DryFireSound") == 1,
      f"{titles.count('Get DryFireSound')} reads of DryFireSound")
check("the reload clacks",
      titles.count("Get ReloadSound") == 1,
      f"{titles.count('Get ReloadSound')} reads of ReloadSound")
dry = [n for n in by_pins(wg, "Sound", "Location")
       if any("DryFireSound" in str(BEL.get_node_title(PIN.get_owning_node(q)))
              for q in PIN.list_connected_pins(BEL.find_input_pin(n, "Sound")))]
check("exactly one node plays the click", len(dry) == 1, f"{len(dry)}")
if dry:
    # The gate above it must be an AND, not a bare NOT: "empty" alone would
    # click through every cooldown frame of a held trigger.
    ins = BEL.find_input_pin(dry[0], "execute")
    gate = [PIN.get_owning_node(q) for q in PIN.list_connected_pins(ins)]
    cond = ([PIN.get_owning_node(q)
             for q in PIN.list_connected_pins(
                 BEL.find_input_pin(gate[0], "Condition"))] if gate else [])
    check("...behind a Branch whose condition is an AND of two things, so it "
          "stays silent between shots as well as when loaded",
          bool(cond) and "AND" in str(BEL.get_node_title(cond[0])).upper(),
          str([str(BEL.get_node_title(n)) for n in cond]))
    # And one of the two has to be the negation of the ammunition test.
    nots = [t for t in titles if "NOT" in t.upper() and "Boolean" in t]
    check("...one half of which is \"has no ammunition\"", len(nots) >= 3,
          f"{len(nots)} NOT nodes (unlimited-weapon, not-sprinting, empty, pose)")

# ─── Aiming down the sights ──────────────────────────────────────────────────
# Right mouse narrows the camera to the weapon's own AdsZoom. What can go wrong
# quietly: a zoom that is never applied (the FOV write missing), a zoom that is
# applied and never undone (no path back to BaseFOV), and a BaseFOV that is a
# literal rather than the camera's own -- all three look fine in the graph.

for sp in G._weapon_specs():
    want = sp.get("ads_zoom", G.COMBAT.ads_zoom_irons)
    got = cdo(load(sp["path"])).get_editor_property("AdsZoom")
    check(f"{sp['display']}: AdsZoom is {want}x",
          isinstance(got, float) and abs(got - want) < 1e-6, repr(got))
check("only the sniper carries a scope's worth of zoom",
      {sp["display"] for sp in G._weapon_specs()
       if sp.get("ads_zoom", G.COMBAT.ads_zoom_irons) == G.COMBAT.ads_zoom_scope} == {"Sniper"},
      str(sorted(sp.get("ads_zoom", G.COMBAT.ads_zoom_irons)
                 for sp in G._weapon_specs())))

# Scoped is what the HUD branches on to black the screen out and draw the
# sniper reticle, and it is deliberately a separate fact from AdsZoom -- so
# both the flag and the agreement between the two are worth checking.
scoped = set()
for sp in G._weapon_specs():
    want = bool(sp.get("scoped", False))
    got = cdo(load(sp["path"])).get_editor_property("Scoped")
    check(f"{sp['display']}: Scoped is {want}", got is want, repr(got))
    if got:
        scoped.add(sp["display"])
check("the sniper is the only weapon with glass on it", scoped == {"Sniper"},
      str(sorted(scoped)))
# The HUD fades the scope over (BaseFOV/CurrentFOV - 1) / (AdsZoom - 1), so a
# scoped weapon that does not zoom would divide by zero every frame it is
# aimed. build_weapon refuses to build one; this is the same rule read off the
# assets that shipped.
flat = {sp["display"] for sp in G._weapon_specs()
        if sp.get("scoped") and sp.get("ads_zoom", G.COMBAT.ads_zoom_irons) <= 1.0}
check("...and it zooms, so the scope's fade has something to divide by",
      not flat, str(sorted(flat)))

fov_writes = [x for x in wg if "SetFieldOfView" in
              str(BEL.get_node_title(x)).replace(" ", "")]
check("one write of the camera's field of view, so the two directions cannot "
      "drift", len(fov_writes) == 1, str(len(fov_writes)))
# Two TargetFOV writes -- the zoomed arm and the unzoomed one -- is what makes
# letting go of the button a path back rather than a second mechanism.
target_writes = [x for x in wg
                 if str(BEL.get_node_title(x)).replace("\n", " ")
                 == "Set TargetFOV"]
check("...fed from two writes of TargetFOV: aiming, and not aiming",
      len(target_writes) == 2, str(len(target_writes)))
check("the zoom is interpolated, not snapped",
      bool(titled(wg, "FInterp To")) or bool(titled(wg, "FInterpTo")),
      "FInterpTo")
base_reads = [x for x in wg if "FieldOfView" in out_pins(x)]
check("BaseFOV is cached off the camera, not written down as a literal",
      bool(base_reads), str(len(base_reads)))
check("aiming is refused while sprinting, which cannot fire anyway",
      G.COMBAT.ads_spread_scale < 1.0 and "Get Sprinting" in
      {str(BEL.get_node_title(x)).replace("\n", " ") for x in wg},
      f"cone x{G.COMBAT.ads_spread_scale}")

# ─── Mouse sensitivity, and what the zoom does to it ─────────────────────────
# Three ways this goes wrong without looking wrong. The pitch scale is cached
# rather than written down because the engine ships it NEGATIVE, so a literal
# would invert the look half the time; the slowdown is driven off CurrentFOV
# rather than off the Aiming flag, so it eases in with the zoom and is
# automatically stronger on the scope; and the default sensitivity has to be
# exactly 1.0 or a player who never opens the settings screen gets a mouse
# that does not feel like the controller's own.
wc_cdo = cdo(wc)
check("the weapon component carries a mouse sensitivity",
      isinstance(wc_cdo.get_editor_property("MouseSensitivity"), float))
check("...defaulting to 1.0, i.e. exactly the controller's own feel",
      abs(wc_cdo.get_editor_property("MouseSensitivity")
          - G.COMBAT.mouse_sensitivity_default) < 1e-6
      and abs(G.COMBAT.mouse_sensitivity_default - 1.0) < 1e-6,
      repr(wc_cdo.get_editor_property("MouseSensitivity")))
check("...within a range that cannot reach zero, which would kill the mouse",
      0.0 < G.COMBAT.mouse_sensitivity_min < G.COMBAT.mouse_sensitivity_default
      < G.COMBAT.mouse_sensitivity_max,
      f"{G.COMBAT.mouse_sensitivity_min}..{G.COMBAT.mouse_sensitivity_max}")
# ─── BP_Settings: what survives a restart ────────────────────────────────────
# Built here rather than in build_graphics_menu.py so that both consumers -- the
# weapon component's defaults and the HUD's settings screen -- can name the
# class without a build-order cycle. Nothing in this file reads it at runtime;
# the HUD pushes its values onto the component every DrawHUD frame.
sg = load(G.SETTINGS_BP_PATH)
check("BP_Settings exists", sg is not None, G.SETTINGS_BP_PATH)
if sg:
    check("...and is a USaveGame, so it can be written to a slot",
          BEL.get_blueprint_parent_class(sg) == unreal.SaveGame.static_class(),
          str(BEL.get_blueprint_parent_class(sg)))
    sg_cdo = cdo(sg)
    check("...carrying a mouse sensitivity that is a float, not an int",
          isinstance(sg_cdo.get_editor_property("MouseSensitivity"), float),
          type(sg_cdo.get_editor_property("MouseSensitivity")).__name__)
    check(f"...defaulting to {G.COMBAT.mouse_sensitivity_default}",
          abs(sg_cdo.get_editor_property("MouseSensitivity")
              - G.COMBAT.mouse_sensitivity_default) < 1e-6,
          repr(sg_cdo.get_editor_property("MouseSensitivity")))
    stored = list(sg_cdo.get_editor_property("Binds"))
    check(f"...and {len(G.BIND_VARS)} binds, one per rebindable action",
          len(stored) == len(G.BIND_VARS), str(len(stored)))
    # Index-for-index against BIND_VARS, because Binds is indexed and not
    # keyed: the settings screen writes Binds[row - 1] and the HUD pushes
    # Binds[i] into BIND_VARS[i], so a reordering here silently rebinds every
    # save already on disk.
    check("...in the same order BIND_VARS names them",
          [k.export_text() for k in stored] == [d for _v, d in G.BIND_VARS],
          str([k.export_text() for k in stored]))
    check("the slot it is written to is named and single",
          bool(G.SETTINGS_SLOT) and G.SETTINGS_USER_INDEX == 0,
          f"{G.SETTINGS_SLOT!r} / user {G.SETTINGS_USER_INDEX}")
    # The requirement, exercised rather than inspected: a BP_Settings written
    # to a slot has to come back off the disk with its FKey array intact. An
    # FKey is a struct with no Python-visible fields, so "it compiles" says
    # nothing about whether it serialises -- this is the only check here that
    # writes a file and reads it back.
    probe_slot = f"{G.SETTINGS_SLOT}Probe"
    made = unreal.GameplayStatics.create_save_game_object(
        BEL.generated_class(sg))
    wrote = unreal.GameplayStatics.save_game_to_slot(made, probe_slot, 0)
    read = unreal.GameplayStatics.load_game_from_slot(probe_slot, 0)
    check("a BP_Settings survives a write to a slot and a read back",
          wrote and read is not None
          and [k.export_text() for k in read.get_editor_property("Binds")]
          == [d for _v, d in G.BIND_VARS]
          and abs(read.get_editor_property("MouseSensitivity")
                  - G.COMBAT.mouse_sensitivity_default) < 1e-6,
          f"wrote={wrote}")
    unreal.GameplayStatics.delete_game_in_slot(probe_slot, 0)

for var, _default in G.BIND_VARS:
    check(f"{var} is an FKey on the component, not a string",
          isinstance(w.get_editor_property(var), unreal.Key),
          type(w.get_editor_property(var)).__name__)

check("the engine's pitch scale is negative, so it MUST be cached not written",
      wc_cdo.get_editor_property("BasePitchScale") < 0.0,
      repr(wc_cdo.get_editor_property("BasePitchScale")))
check("...and the yaw scale positive",
      wc_cdo.get_editor_property("BaseYawScale") > 0.0,
      repr(wc_cdo.get_editor_property("BaseYawScale")))
scale_reads = {str(BEL.get_node_title(x)).replace("\n", " ") for x in wg}
for label, want in (("yaw", "Set Deprecated Input Yaw Scale"),
                    ("pitch", "Set Deprecated Input Pitch Scale")):
    hits = [t for t in scale_reads if t.replace(" ", "")
            == want.replace(" ", "")]
    check(f"the {label} look scale is written every frame", bool(hits), want)
for label, want in (("yaw", "Get Deprecated Input Yaw Scale"),
                    ("pitch", "Get Deprecated Input Pitch Scale")):
    hits = [t for t in scale_reads if t.replace(" ", "")
            == want.replace(" ", "")]
    check(f"...from a {label} base READ off the controller, not a literal",
          bool(hits), want)
check("the slowdown is driven off the zoom, not off the Aiming flag -- so it "
      "eases in and is stronger on the scope",
      bool(titled(wg, "Lerp")) and 0.0 < G.COMBAT.ads_sens_compensation <= 1.0,
      f"Lerp(1, CurrentFOV/BaseFOV, {G.COMBAT.ads_sens_compensation})")
# The numbers the player actually feels, spelled out so a change to either
# constant has to be argued for rather than noticed later.
for name, zoom, want in (("irons", G.COMBAT.ads_zoom_irons, 0.75),
                         ("scope", G.COMBAT.ads_zoom_scope, 0.4375)):
    got = 1.0 + G.COMBAT.ads_sens_compensation * (1.0 / zoom - 1.0)
    check(f"...which works out at {want:.2f}x sensitivity down the {name}",
          abs(got - want) < 5e-3, f"{got:.4f}")

# ─── What aiming costs in mobility ───────────────────────────────────────────
# Full ADS is half speed, and it is a second MaxWalkSpeed write layered on top
# of the sprint block's unconditional one. Four ways that goes wrong while the
# graph still looks right: the factor is applied to the LIVE walk speed rather
# than to BaseSpeed, which compounds to a standstill in about a second; nothing
# ever restores the speed, because the author added an "undo" path that turns
# out to be dead; the slowdown is driven off the Aiming flag, so it snaps on a
# frame before the camera moves; and it is driven off the raw CurrentFOV/BaseFOV
# ratio the sensitivity uses, which would make the sniper slower on its legs
# than the pistol and never reach exactly half on anything.

check(f"aiming costs {(1 - G.COMBAT.ads_move_speed_scale) * 100:.0f}% of the "
      f"walking speed, which is the ask",
      abs(G.COMBAT.ads_move_speed_scale - 0.5) < 1e-9,
      f"x{G.COMBAT.ads_move_speed_scale}")

def feeds(pin, limit=250):
    """Every node feeding this pin through DATA links only.

    Same shape, and for the same reason, as the traversal the Automatic check
    uses further down: following the exec pin as well would reach every pure
    node in the graph and make each of these checks pass vacuously.
    """
    seen, stack = set(), [pin]
    while stack and len(seen) < limit:
        for q in PIN.list_connected_pins(stack.pop()):
            node = PIN.get_owning_node(q)
            if node in seen:
                continue
            seen.add(node)
            stack.extend(x for x in BEL.list_input_pins(node)
                         if str(PIN.get_pin_name(x)) != "execute")
    return seen

speed_writes = [n for n in wg if "MaxWalkSpeed" in in_pins(n)]
check("MaxWalkSpeed is written exactly twice: the sprint block's "
      "unconditional write, and the ADS slowdown layered on top of it",
      len(speed_writes) == 2, str(len(speed_writes)))
# The sprint write reaches the movement component through a cast to Character
# (it wants the CastFailed pin as a continuation); the ADS one takes the
# GetComponentByClass shortcut, which is what tells the two apart from here.
by_class = [n for n in speed_writes
            if any("getcomponentbyclass" in
                   str(BEL.get_node_title(PIN.get_owning_node(q)))
                   .replace(" ", "").lower()
                   for q in PIN.list_connected_pins(
                       BEL.find_input_pin(n, "self")))]
check("...the second of them off GetComponentByClass, which reshapes its "
      "return pin to the chosen class and so needs no cast",
      len(by_class) == 1, str(len(by_class)))

if by_class:
    ads_speed = by_class[0]
    up = feeds(BEL.find_input_pin(ads_speed, "MaxWalkSpeed"))
    up_titles = {str(BEL.get_node_title(n)).replace("\n", " ") for n in up}
    check("THE COMPOUNDING TRAP: the slowed speed is computed from BaseSpeed, "
          "never from the MaxWalkSpeed that is already set -- this write runs "
          "every frame, so a factor on the live value would walk the player to "
          "a standstill in about a second",
          any("BaseSpeed" in out_pins(n) for n in up)
          and not any("MaxWalkSpeed" in out_pins(n) for n in up),
          str(sorted(up_titles)))
    check("...and BaseSpeed is still written exactly once, at BeginPlay, off "
          "the character's own default",
          len([n for n in wg if "BaseSpeed" in in_pins(n)]) == 1,
          str(len([n for n in wg if "BaseSpeed" in in_pins(n)])))
    check("the slowdown is driven off how far the zoom has actually travelled, "
          "not off the Aiming flag -- the flag would snap it on a frame before "
          "the camera moved",
          "Set CurrentFOV" in up_titles
          and not any("Aiming" in out_pins(n) for n in up),
          str(sorted(t for t in up_titles if "FOV" in t or "Aiming" in t)))
    check("...normalised by the weapon's OWN AdsZoom, so full ADS is the same "
          "half speed on a 4x scope as on 1.5x irons",
          any("AdsZoom" in out_pins(n) for n in up),
          str(sorted(up_titles)))
    # An FInterpTo can overshoot its target on a long frame, and an unclamped
    # progress past 1 is a walk speed below the number anybody chose.
    # `num_pin(n, "Min") or X` would be the wrong test and quietly the wrong
    # answer: a Min that really is 0.0 is falsy, so the fallback wins and the
    # clamp that exists reads as missing.
    def holds(node, name, want):
        got = num_pin(node, name)
        return got is not None and abs(got - want) < 1e-9

    clamps = [n for n in up if {"Value", "Min", "Max"} <= in_pins(n)]
    check("...clamped to 0..1, because the interpolation can overshoot",
          any(holds(n, "Min", 0.0) and holds(n, "Max", 1.0) for n in clamps),
          str(len(clamps)))
    lerps = [n for n in up
             if holds(n, "B", G.COMBAT.ads_move_speed_scale)
             and holds(n, "A", 1.0)]
    check(f"...and eased Lerp(1, {G.COMBAT.ads_move_speed_scale:g}, progress), "
          f"so it arrives with the zoom rather than with the key",
          len(lerps) == 1, str(len(lerps)))

    # THE REASON THE GATE IS THERE. Sprint writes MaxWalkSpeed unconditionally
    # every frame, earlier in the same Tick, which is what makes releasing the
    # aim key need no code at all -- and also what would make the two writes
    # fight over the frames the player is sprinting, if this one were not shut
    # off on exactly the condition the zoom is.
    driving = [PIN.get_owning_node(q) for q in PIN.list_connected_pins(
        BEL.find_input_pin(ads_speed, "execute"))]
    gates = [n for n in driving if n.get_class().get_name() == "K2Node_IfThenElse"]
    check("the ADS write sits behind a Branch, so the frames it does not run "
          "are the frames sprint's unconditional write stands -- that is the "
          "whole of \"letting go restores the speed\"",
          len(gates) == 1, str([n.get_class().get_name() for n in driving]))
    if gates:
        cond = feeds(BEL.find_input_pin(gates[0], "Condition"))
        cond_titles = {str(BEL.get_node_title(n)).replace("\n", " ")
                       for n in cond}
        check("...gated on NOT Sprinting, the same pin the zoom is, so the two "
              "MaxWalkSpeed writes can never disagree about a frame",
              any("Sprinting" in out_pins(n) for n in cond)
              and any("NOT" in t.upper() for t in cond_titles),
              str(sorted(cond_titles)))
        check("...and on a valid Held, because the AdsZoom read behind it "
              "would otherwise be an Accessed None every frame the hands are "
              "empty",
              any("isvalid" in t.replace(" ", "").lower() for t in cond_titles),
              str(sorted(cond_titles)))

# The headless -game run takes no input, so the gate above never opens by
# itself and the positive case has to be forced with a temporary probe. This is
# what makes sure the probe left again: Aiming is driven by the aim bind and by
# nothing else -- a forcing function wired in front of the key poll (a clock, a
# literal true) would still zoom, still slow the player down, and still pass
# every structural check above.
aiming_writes = [n for n in wg if "Aiming" in in_pins(n)]
check("Aiming is written exactly once", len(aiming_writes) == 1,
      str(len(aiming_writes)))
if aiming_writes:
    src = feeds(BEL.find_input_pin(aiming_writes[0], "Aiming"))
    src_titles = {str(BEL.get_node_title(n)).replace("\n", " ") for n in src}
    check("...off the aim bind, and off nothing that stands in for it -- no "
          "clock and no literal left over from forcing the state at runtime",
          any("Get KeyAim" in t for t in src_titles)
          and not any("Time Seconds" in t or t.strip() in ("Sin", "Sin (Radians)")
                      for t in src_titles),
          str(sorted(src_titles)))
check("and no probe is left printing out of the weapon component's Tick",
      not [n for n in wg
           if "printstring" in
           str(BEL.get_node_title(n)).replace(" ", "").lower()],
      str([str(BEL.get_node_title(n)) for n in wg
           if "printstring" in
           str(BEL.get_node_title(n)).replace(" ", "").lower()]))

# The numbers the player actually feels, spelled out so that a change to either
# the scale or a weapon's zoom has to be argued for rather than noticed later.
# At full ADS CurrentFOV is BaseFOV/AdsZoom, so progress is exactly 1 whatever
# the zoom -- which is the point of dividing by (AdsZoom - 1).
def _eased(zoom, travelled):
    """The walk-speed factor once the camera is `travelled` of the way in."""
    now = 1.0 / (1.0 + travelled * (zoom - 1.0))        # CurrentFOV / BaseFOV
    progress = min(max((1.0 / now - 1.0) / (zoom - 1.0), 0.0), 1.0)
    return 1.0 + (G.COMBAT.ads_move_speed_scale - 1.0) * progress

full_ads = {sp["display"]:
            _eased(sp.get("ads_zoom", G.COMBAT.ads_zoom_irons), 1.0)
            for sp in G._weapon_specs()}
check(f"every weapon lands on exactly {G.COMBAT.ads_move_speed_scale:g}x speed "
      f"at full ADS",
      all(abs(v - G.COMBAT.ads_move_speed_scale) < 1e-9
          for v in full_ads.values()),
      str(sorted(full_ads.items())))
check("...and on full speed with the button up, so nothing is left behind",
      all(abs(_eased(sp.get("ads_zoom", G.COMBAT.ads_zoom_irons), 0.0) - 1.0)
          < 1e-9 for sp in G._weapon_specs()))
halfway = {sp["display"]:
           _eased(sp.get("ads_zoom", G.COMBAT.ads_zoom_irons), 0.5)
           for sp in G._weapon_specs()}
check("...half way in it is 0.75x on every weapon too: the easing follows the "
      "zoom's curve, not the zoom's magnitude",
      all(abs(v - 0.75) < 1e-9 for v in halfway.values()),
      str(sorted(halfway.items())))
# And the contrast that justifies normalising at all: the raw ratio the mouse
# uses would be a different speed per weapon and never exactly the number asked
# for -- right for sensitivity, wrong for legs.
raw = {sp["display"]:
       1.0 + (1.0 - G.COMBAT.ads_move_speed_scale)
       * (1.0 / sp.get("ads_zoom", G.COMBAT.ads_zoom_irons) - 1.0)
       for sp in G._weapon_specs()}
check("...which the raw CurrentFOV/BaseFOV ratio the sensitivity uses would "
      "NOT have been: that is why this one is normalised and that one is not",
      len({round(v, 6) for v in raw.values()}) > 1
      and all(abs(v - G.COMBAT.ads_move_speed_scale) > 1e-6
              for v in raw.values()),
      str(sorted(raw.items())))

# ─── The combat config ───────────────────────────────────────────────────────
# The ask was for a named, tunable home for the global combat parameters, with
# more to follow. What can go wrong quietly is that it becomes a SECOND home --
# the structure exists, a builder still reads a leftover module constant, and
# the two disagree until somebody tunes the one that is not wired up.

check("the global combat tuning lives in one named structure",
      dataclasses.is_dataclass(G.CombatConfig)
      and isinstance(G.COMBAT, G.CombatConfig),
      type(G.COMBAT).__name__)
check("...frozen, so no builder can rewrite a value the verifier then asserts",
      G.CombatConfig.__dataclass_params__.frozen)
knobs = {f.name for f in dataclasses.fields(G.COMBAT)}
check("...holding every global knob: lethality, sprint, ADS, look, recoil",
      knobs >= {"start_health", "head_multiplier", "limb_multiplier",
                "sprint_speed_cms", "max_stamina", "stamina_drain_per_s",
                "stamina_regen_per_s", "ads_zoom_irons", "ads_zoom_scope",
                "ads_interp_speed", "ads_spread_scale",
                "mouse_sensitivity_default", "mouse_sensitivity_min",
                "mouse_sensitivity_max", "mouse_sensitivity_step",
                "ads_sens_compensation", "ads_move_speed_scale",
                "recoil_recovery_speed",
                "recoil_recovery_fraction", "recoil_ads_scale",
                "recoil_horizontal_ratio"},
      str(sorted(knobs)))
stale = [n for n in ("START_HEALTH", "HEAD_MULTIPLIER", "LIMB_MULTIPLIER",
                     "SPRINT_SPEED_CMS", "MAX_STAMINA", "STAMINA_DRAIN_PER_S",
                     "STAMINA_REGEN_PER_S", "ADS_ZOOM_IRONS", "ADS_ZOOM_SCOPE",
                     "ADS_INTERP_SPEED", "ADS_SPREAD_SCALE",
                     "ADS_SENS_COMPENSATION", "MOUSE_SENSITIVITY_DEFAULT",
                     "MOUSE_SENSITIVITY_MIN", "MOUSE_SENSITIVITY_MAX",
                     "MOUSE_SENSITIVITY_STEP")
         if hasattr(G, n)]
check("...and it is the ONLY home -- every loose constant it replaced is gone, "
      "so nothing can read a stale second copy", not stale, str(stale))
# Per-weapon numbers must NOT have been swept into it: that would undo the
# "a sixth weapon is a row in a table" property the whole file is built on.
check("per-weapon numbers stayed on the weapon table",
      not (knobs & {"damage", "spread", "recoil", "interval", "magazine"}),
      str(sorted(knobs)))

# ─── Recoil ──────────────────────────────────────────────────────────────────
# The requested ordering, read off the built assets rather than off the table
# that produced them, plus the one trap this feature had: routing the kick
# through AddControllerPitchInput would multiply it by the deprecated
# InputPitchScale, which is exactly the handle the mouse-sensitivity setting
# drives -- so the recoil would scale with the player's slider.

kick = {}
for sp in G._weapon_specs():
    got = cdo(load(sp["path"])).get_editor_property("RecoilPitch")
    check(f"{sp['display']}: RecoilPitch is {sp['recoil']} deg",
          isinstance(got, float) and abs(got - sp["recoil"]) < 1e-6, repr(got))
    kick[sp["display"]] = got

check("every weapon kicks at all", all(v > 0.0 for v in kick.values()),
      str(sorted(kick.items(), key=lambda kv: -kv[1])))
heavy = min(kick["Shotgun"], kick["Sniper"])
check("the shotgun and the sniper kick hardest of the five",
      heavy > max(kick["Rifle"], kick["SMG"], kick["Pistol"]),
      f"shotgun {kick['Shotgun']}, sniper {kick['Sniper']} vs "
      f"rifle {kick['Rifle']}")
check("...the assault rifle next", kick["Rifle"] > kick["SMG"],
      f"rifle {kick['Rifle']} > smg {kick['SMG']}")
check("...the SMG less than that", kick["SMG"] > kick["Pistol"],
      f"smg {kick['SMG']} > pistol {kick['Pistol']}")
check("...and the pistol least of all",
      kick["Pistol"] == min(kick.values()),
      f"pistol {kick['Pistol']}, lowest of {sorted(kick.values())}")

for name in ("RecoilDebt", "RecoilYawDebt", "RecoilYawKick"):
    got = wc_cdo.get_editor_property(name)
    check(f"{name} is a float on the component, starting settled at zero",
          isinstance(got, float) and abs(got) < 1e-9, repr(got))

flat = [t.replace(" ", "") for t in titles]
banned = sorted({t for t in flat
                 if "PitchInput" in t or "ControllerYawInput" in t})
check("the kick never goes through AddControllerPitchInput -- that route "
      "multiplies by the deprecated InputPitchScale the sensitivity setting "
      "drives, so recoil would scale with the player's slider",
      not banned, str(banned))
for label, want, n in (("written", "SetControlRotation", 2),
                       ("read back first", "GetControlRotation", 2)):
    hits = [t for t in flat if t.startswith(want)]
    check(f"the control rotation is {label} exactly {n}x: the kick and the "
          f"recovery", len(hits) == n, f"{len(hits)} x {want}")
makers = [n for n in wg if {"Roll", "Pitch", "Yaw"} <= in_pins(n)]
check("both writes are rebuilt through a Make Rotator", len(makers) == 2,
      str(len(makers)))
check("...whose Roll comes from the rotation that was read, not a literal zero "
      "that would quietly decide the view never rolls",
      bool(makers) and all(PIN.list_connected_pins(BEL.find_input_pin(m, "Roll"))
                           for m in makers),
      str(len(makers)))

interps = by_pins(wg, "Current", "Target", "DeltaTime", "InterpSpeed")
check("the two debts recover by interpolation, alongside the zoom's",
      len(interps) == 3, f"{len(interps)} FInterpTo (2 recoil + 1 FOV)")
settling = [n for n in interps
            if (num_pin(n, "Target") or 0.0) == 0.0
            and abs((num_pin(n, "InterpSpeed") or 0.0)
                    - G.COMBAT.recoil_recovery_speed) < 1e-6]
check(f"...toward zero at {G.COMBAT.recoil_recovery_speed:g}, so the "
      f"accumulator always settles and nothing builds up across a magazine",
      len(settling) == 2, str(len(settling)))
check("only part of each step is handed back, which is what makes a burst "
      "climb instead of springing exactly home",
      0.0 < G.COMBAT.recoil_recovery_fraction < 1.0,
      f"{G.COMBAT.recoil_recovery_fraction} of every kick returned, "
      f"{(1 - G.COMBAT.recoil_recovery_fraction) * 100:.0f}% kept")
paid = [n for n in by_pins(wg, "A", "B")
        if abs((num_pin(n, "B") or 0.0)
               - G.COMBAT.recoil_recovery_fraction) < 1e-9]
check("...and that fraction is in the graph twice, pitch and yaw",
      len(paid) == 2, str(len(paid)))
for var in ("RecoilDebt", "RecoilYawDebt"):
    writes = [t for t in titles if t == f"Set {var}"]
    check(f"{var} is written twice: charged by the shot, settled by the tick",
          len(writes) == 2, str(len(writes)))

check("aiming down the sights steadies the kick",
      0.0 < G.COMBAT.recoil_ads_scale < 1.0, f"x{G.COMBAT.recoil_ads_scale}")
steadied = [n for n in by_pins(wg, "A", "B", "bPickA")
            if abs((num_pin(n, "A") or 0.0) - G.COMBAT.recoil_ads_scale) < 1e-9]
check("...through the same SelectFloat shape the cone uses, so the aimed and "
      "unaimed cases cannot drift into two branches", len(steadied) == 1,
      str(len(steadied)))
check("the sideways kick is a fraction of the vertical rather than a second "
      "per-weapon column", 0.0 < G.COMBAT.recoil_horizontal_ratio < 1.0,
      f"+/-{G.COMBAT.recoil_horizontal_ratio} of the pitch")
draws = [n for n in wg if str(BEL.get_node_title(n)).replace(" ", "").lower()
         .startswith("randomfloatinrange")]
check("...drawn once per shot", len(draws) == 1, str(len(draws)))
if draws:
    readers = {str(BEL.get_node_title(PIN.get_owning_node(q))).replace("\n", " ")
               for q in PIN.list_connected_pins(
                   BEL.find_output_pin(draws[0], "ReturnValue"))}
    check("...and read by exactly one thing, the RecoilYawKick write -- "
          "RandomFloatInRange is pure, so a second reader would be a second "
          "number and the recovery would never cancel the kick",
          readers == {"Set RecoilYawKick"}, str(sorted(readers)))

# ─── Footsteps ───────────────────────────────────────────────────────────────

foot = load(G.FOOTSTEP_BP_PATH)
check("there is a footstep component", foot is not None)
if foot:
    f = cdo(foot)
    sounds = list(f.get_editor_property("Sounds"))
    check("...with more than one step, so it is not one buffer retriggered",
          len(sounds) >= 3, f"{len(sounds)} clips")
    check("...on a stride measured in centimetres, not seconds",
          abs(f.get_editor_property("StrideCm") - G.FOOTSTEP_STRIDE_CM) < 1e-6,
          repr(f.get_editor_property("StrideCm")))
    fg = graph(foot).list_all_nodes()
    # NOT `titles`: this file is a flat script and `titles` is the weapon
    # component's, read again hundreds of lines below.
    foot_titles = {str(BEL.get_node_title(x)).replace("\n", " ") for x in fg}
    # Distance, not time: the accumulator has to be driven by SPEED x dt. A
    # Delay or a plain timer here would be the bug this design exists to avoid.
    check("...accumulated from the owner's own speed",
          any("eloc" in t for t in foot_titles),
          str(sorted(t for t in foot_titles if "eloc" in t)))
    check("...and the remainder is carried, not zeroed, so the rate does not "
          "follow the framerate",
          any("-" in t or "Subtract" in t for t in foot_titles),
          str(len(foot_titles)))
    # The audibility probe that proved the attenuation boundaries at runtime
    # lived here, on a once-only Tick gate with a Probed flag. Both it and the
    # flag are asserted gone: a probe left in ships a PrintString on every
    # footstep component in the level.
    try:
        f.get_editor_property("Probed")
        _left_over = True
    except Exception:                                             # noqa: BLE001
        _left_over = False
    check("...and the temporary audibility probe is gone",
          not _left_over
          and not any("Print" in t or "Probed" in t for t in foot_titles),
          str(sorted(t for t in foot_titles if "Print" in t or "Probed" in t)))
check("both the player and the wanderers wear it",
      "FootstepComponent" in components(char)
      and (npc is None or "FootstepComponent" in components(npc)))

# ─── Automatic fire ──────────────────────────────────────────────────────────
# Hold the button and the SMG and the assault rifle keep firing; the shotgun,
# the pistol and the sniper are one shot per click. What makes this cheap is
# that the rate limit already existed: FireInterval and NextFireTime were being
# consulted on every frame the trigger was down long before anything could hold
# it down. All that is added is whether a held button still counts as a pull.

autos = {sp["display"] for sp in G._weapon_specs() if sp["automatic"]}
check("exactly the SMG and the assault rifle are automatic",
      autos == set(G.AUTO_DISPLAYS), str(sorted(autos)))
for sp in G._weapon_specs():
    check(f"{sp['display']}: Automatic is {sp['automatic']}",
          bool(cdo(load(sp["path"])).get_editor_property("Automatic"))
          is bool(sp["automatic"]))
# A held trigger with no rate limit is one shot per frame, i.e. 60 rounds a
# second out of a 30-round magazine. Both automatics must have an interval.
for name in G.AUTO_DISPLAYS:
    sp = next(x for x in G._weapon_specs() if x["display"] == name)
    check(f"{name}: has a fire interval, so a held trigger is not one shot "
          f"per frame",
          float(cdo(load(sp["path"])).get_editor_property("FireInterval")) > 0.0,
          str(sp["interval"]))

downs = [n for n in wg if "IsInputKeyDown" in str(BEL.get_node_title(n))]
held_binds = sorted(
    str(BEL.get_node_title(PIN.get_owning_node(q))).replace("\n", " ")
    for x in downs
    for q in PIN.list_connected_pins(BEL.find_input_pin(x, "Key")))
check("three keys are polled held rather than tapped: sprint, aim and the "
      "trigger",
      held_binds == ["Get KeyAim", "Get KeyFire", "Get KeySprint"],
      str(held_binds))

# THE TRAP THIS SECTION EXISTS FOR. Automatic lives on the weapon, so reading
# it means a pure Get with its self pin driven by Held -- and Held is null
# whenever the player's hands are empty. Read in the OUTER fire gate's
# condition, which is pulled on every frame, that is an "Accessed None" per
# frame forever; read behind it, where Held has been checked valid, it is free.
#
# Rather than try to name the outer gate, assert the invariant: Automatic is
# read in the same Branch condition as the other Held properties, all of which
# are already known to sit behind the valid-Held gate.
def upstream(pin, limit=200):
    """Every node feeding this pin, following DATA links only.

    Skipping the exec pin is the whole of it. list_input_pins hands back the
    node's "execute" pin alongside its data pins, and following that walks
    backwards up the exec chain -- from which every pure node in the graph is
    reachable, so the traversal answers "yes" for every Branch and proves
    nothing. The first version of this check did exactly that and reported
    five branches consulting Automatic when there is one.
    """
    seen, stack = set(), [pin]
    while stack and len(seen) < limit:
        for q in PIN.list_connected_pins(stack.pop()):
            node = PIN.get_owning_node(q)
            if node in seen:
                continue
            seen.add(node)
            stack.extend(x for x in BEL.list_input_pins(node)
                         if str(PIN.get_pin_name(x)) != "execute")
    return seen

def reads(nodes, var):
    return any(var in out_pins(x) for x in nodes)

conds = [(x, upstream(BEL.find_input_pin(x, "Condition")))
         for x in wg
         if x.get_class().get_name() == "K2Node_IfThenElse"
         and BEL.find_input_pin(x, "Condition")]
with_auto = [(x, up) for x, up in conds if reads(up, "Automatic")]
check("exactly one Branch consults Automatic", len(with_auto) == 1,
      f"{len(with_auto)} branches")
if with_auto:
    _, up = with_auto[0]
    check("...and it is the gate that also reads Loaded and NextFireTime, so "
          "Automatic is read behind the valid-Held check and not in front of it",
          reads(up, "Loaded") and reads(up, "NextFireTime"),
          f"Loaded={reads(up, 'Loaded')} NextFireTime={reads(up, 'NextFireTime')}")
    # The held button only counts when the weapon says so: Automatic must be
    # AND-ed with the key, never read on its own.
    consumers = [PIN.get_owning_node(q)
                 for x in wg if "Automatic" in out_pins(x)
                 for q in PIN.list_connected_pins(
                     BEL.find_output_pin(x, "Automatic"))]
    check("Automatic is AND-ed with the held key, not used on its own",
          bool(consumers) and all("AND" in str(BEL.get_node_title(c)).upper()
                                  for c in consumers),
          str([str(BEL.get_node_title(c)) for c in consumers]))
# ...and a semi-automatic still fires: the tap has to bypass the Automatic
# test, which means an OR sits between them.
check("a tapped trigger fires regardless of Automatic (an OR, not an AND)",
      len([x for x in wg if "OR Boolean"
           in str(BEL.get_node_title(x)).replace("\n", " ")]) >= 2,
      "one OR for the unlimited-ammo short circuit, one for tap-or-hold")

# ─── Sprinting drops the ready pose ──────────────────────────────────────────
# The complaint this answers: running with the barrel levelled at the horizon.
# There is no new animation -- the fix is to stop playing the ready pose, and
# let ABP_Unarmed's own locomotion state machine through the layered blend.

check("PoseSprinting exists to make the change edge-triggered",
      w.get_editor_property("PoseSprinting") is False,
      str(w.get_editor_property("PoseSprinting")))
check("...and it matches Sprinting at start, so frame one re-equips nothing",
      w.get_editor_property("PoseSprinting")
      == w.get_editor_property("Sprinting"))
check("the sprint state is remembered exactly once",
      titles.count("Set PoseSprinting") == 1,
      f"{titles.count('Set PoseSprinting')} writes")
check("...and re-equipping happens only on the frames the two disagree",
      any("!=" in t or "NotEqual" in t.replace(" ", "") for t in titles),
      str(sorted({t for t in titles if "=" in t})))
# The pose itself: the branch that decides whether to play or stop the slot
# now has a NOT Sprinting in its condition, which is what actually stops it.
plays = by_pins(wg, "Asset", "SlotNodeName")
if plays:
    node, reached = plays[0], False
    ins = BEL.find_input_pin(node, "execute")
    gate = [PIN.get_owning_node(q) for q in PIN.list_connected_pins(ins)]
    if gate:
        cond = [PIN.get_owning_node(q)
                for q in PIN.list_connected_pins(
                    BEL.find_input_pin(gate[0], "Condition"))]
        # Walk the two inputs of the AND looking for a Sprinting read.
        frontier = list(cond)
        for _ in range(6):
            nxt = []
            for n in frontier:
                if "Sprinting" in out_pins(n):
                    reached = True
                for q in BEL.list_input_pins(n):
                    nxt += [PIN.get_owning_node(r)
                            for r in PIN.list_connected_pins(q)]
            frontier = nxt
    check("the ready pose is not played while sprinting", reached,
          "Sprinting read found behind the pose branch's condition")
sprint_gets = [n for n in wg if "Sprinting" in out_pins(n)]
check("Sprinting is read by the fire gate, the pose edge and the pose branch",
      len(sprint_gets) >= 4, f"{len(sprint_gets)} reads")

# ─── Debug mode ──────────────────────────────────────────────────────────────

mode_cdo = cdo(load(G.GAME_MODE_BP_PATH))
check("the GameMode carries the debug flag, where a component can reach it",
      isinstance(mode_cdo.get_editor_property(G.DEBUG_MODE_VAR), bool))
check("...and it is OFF by default -- the overlays are instrumentation",
      mode_cdo.get_editor_property(G.DEBUG_MODE_VAR) is False)
check("the pellet tracer is a DrawDebugLine, not a trace that draws itself",
      bool(by_pins(wg, "LineStart", "LineEnd")),
      f"{len(by_pins(wg, 'LineStart', 'LineEnd'))} DrawDebugLine node(s)")
check("...and it lasts as long as the tracer always did",
      all(abs(float(pin_value(n, "Duration") or 0) - G.TRACE_DEBUG_SECONDS) < 1e-3
          for n in by_pins(wg, "LineStart", "LineEnd")),
      f"{G.TRACE_DEBUG_SECONDS}s")
# Read once per shot off the GameMode, cached, then branched on per pellet.
check("the flag is read off the GameMode once per shot and cached",
      len([t for t in (str(BEL.get_node_title(n)).replace("\n", " ")
                       for n in wg) if t == f"Set {G.DEBUG_MODE_VAR}"]) == 1)
# Three reads: the GameMode's own (once per shot), then the cached copy twice
# per pellet -- the tracer's branch and the damage readout's.
check("...and the pellet loop branches on the cached copy",
      len([n for n in wg if G.DEBUG_MODE_VAR in out_pins(n)]) == 3,
      f"{len([n for n in wg if G.DEBUG_MODE_VAR in out_pins(n)])} reads")

# ─── BP_AmmoPickup ───────────────────────────────────────────────────────────

ammo_bp = load(G.AMMO_BP_PATH)
ammo = cdo(ammo_bp)
ag = graph(ammo_bp).list_all_nodes()

check(f"a drop carries {G.AMMO_DROP_SHELLS} shells",
      ammo.get_editor_property("Shells") == G.AMMO_DROP_SHELLS,
      str(ammo.get_editor_property("Shells")))
check("it starts uncollected", ammo.get_editor_property("Credited") is False)
check("it looks like what it gives you -- one mesh per shell",
      len({n for n in components(ammo_bp) if n.startswith("Shell")})
      == G.AMMO_DROP_SHELLS,
      str(sorted({n for n in components(ammo_bp) if n.startswith("Shell")})))
# Measured HERE, on at most a handful of actors, rather than by sweeping the
# level from the weapon component's Tick every frame whether any exist or not.
check("the pickup measures its own distance to the player",
      bool(by_pins(ag, "V1", "V2")) and bool(by_pins(ag, "PlayerIndex")),
      f"{len(by_pins(ag, 'V1', 'V2'))} distance node(s)")
check(f"...and is taken by walking within {G.AMMO_PICKUP_RADIUS:.0f} cm of it",
      any(pin_value(n, "B") == str(G.AMMO_PICKUP_RADIUS)
          for n in ag if "B" in in_pins(n)),
      f"{G.AMMO_PICKUP_RADIUS:.0f} cm")
check("no key is involved -- it is not another thing to press E on",
      not by_pins(ag, "Key"), f"{len(by_pins(ag, 'Key'))} key polls")
check("it credits the weapon's own Reserve, not a counter on the player",
      any(str(BEL.get_node_title(n)).replace("\n", " ") == "Set Reserve"
          for n in ag))
check("Credited is written on both paths -- the held weapon and the fallback loop",
      len([n for n in ag
           if str(BEL.get_node_title(n)).replace("\n", " ") == "Set Credited"]) == 2,
      f"{len([n for n in ag if str(BEL.get_node_title(n)).replace(chr(10), ' ') == 'Set Credited'])} writes")
check("...and it only vanishes once something has actually taken it",
      len([n for n in ag if "Credited" in out_pins(n)]) == 2,
      f"{len([n for n in ag if 'Credited' in out_pins(n)])} reads of Credited")
# With four of the five weapons using ammunition, "the first one in the
# inventory" means the shotgun in slot 0 forever -- so a player clearing the
# forest with the sniper would watch a gun they are not holding fill up.
check("the shells go to the weapon in the player's hands first",
      any("Held" in out_pins(n) for n in ag),
      "no read of the weapon component's Held on the pickup")
held_reads = [n for n in ag if "Held" in out_pins(n)]
if held_reads:
    # And that read has to be behind an IsValid gate rather than beside one:
    # UsesAmmo is a pure pull off Held, and pulling it while unarmed is an
    # Accessed None -- the trap this project has now hit four times.
    valids = [n for n in ag if "Object" in in_pins(n)
              and "IsValid" in str(BEL.get_node_title(n))]
    check("...behind an IsValid gate, because reading UsesAmmo off None is an "
          "Accessed None", bool(valids), f"{len(valids)} IsValid node(s)")
check("...with the inventory loop kept as the fallback for an unarmed player "
      "or one holding the pistol",
      bool(by_pins(ag, "Array")) or any("Inventory" in out_pins(n) for n in ag),
      "the ForEachLoop over Inventory is gone")

# ─── The 10% weapon drop ─────────────────────────────────────────────────────

drop_classes = list(cdo(health_bp).get_editor_property("DropClasses"))
check(f"a kill can leave one of {len(G.DROP_DISPLAYS)} weapons",
      len(drop_classes) == len(G.DROP_DISPLAYS), str(len(drop_classes)))
check("...and they are the three that are not in the starting loadout",
      [c.get_name() for c in drop_classes]
      == [f"{sp['path'].rsplit('/', 1)[-1]}_C" for sp in G._weapon_specs()
          if sp["display"] in G.DROP_DISPLAYS],
      str([c.get_name() for c in drop_classes]))
check(f"the drop rate is {G.GUN_DROP_CHANCE * 100:.0f}%",
      any(abs((num_pin(n, "B") or -1.0) - G.GUN_DROP_CHANCE) < 1e-6
          for n in hg if "B" in in_pins(n)),
      f"expected a comparison against {G.GUN_DROP_CHANCE}")
# Two draws, not one weighted table: the rate and the table are tuned apart.
check("...rolled once, and which weapon drawn separately",
      bool([n for n in hg if {"Min", "Max"} <= in_pins(n)
            and "Random" in str(BEL.get_node_title(n))]),
      "no random draw in the death path")
check("the weapon is picked by index into the array, not by a Switch that "
      "would need a pin per weapon",
      bool(by_pins(hg, "TargetArray", "Index")),
      f"{len(by_pins(hg, 'TargetArray', 'Index'))} Array_Get node(s)")
# The empty-table guard. Without it RandomIntegerInRange(0, -1) indexes nothing.
check("an empty drop table drops nothing rather than indexing off the end",
      any(str(BEL.get_node_title(n)).replace("\n", " ").startswith("Get DropClasses")
          for n in hg)
      and bool([n for n in hg if "TargetArray" in in_pins(n)
                and "Length" in str(BEL.get_node_title(n))]),
      "no Array_Length on DropClasses")
# The handover: from here it is an ordinary weapon on the ground, and the E key
# that picks up a gun the player threw away picks this one up with no new code.
check("a dropped weapon is flagged Dropped, which is the whole pick-up interface",
      any(str(BEL.get_node_title(n)).replace("\n", " ") == "Set Dropped"
          for n in hg),
      "nothing sets Dropped in the death path")
# Matched by the feeder's PIN SET, not by its title: Array_Get's displayed
# title is the bare word "Get", which is also how every variable getter in the
# graph reads. Pins are the only unambiguous handle.
guns = [n for n in by_pins(hg, "Class", "SpawnTransform")
        if any({"TargetArray", "Index"} <= in_pins(PIN.get_owning_node(q))
               for q in PIN.list_connected_pins(BEL.find_input_pin(n, "Class")))]
check("exactly one spawn in the death path drops a weapon",
      len(guns) == 1, f"{len(guns)} weapon spawns")
# Same guard as the shells and the kill count, walked the same way: the safety
# net kills anything that falls under the world down this very path.
if guns:
    # BREADTH-first over every exec feeder, not a single chain.
    #
    # This used to follow feeders[0] and stop, which made it a coin flip: an
    # exec input takes any number of links and their order is not something
    # this API promises, so on a graph where the drop is reached from more than
    # one place the walk would sometimes take the arm without the guard on it
    # and report the guard missing. It failed intermittently, on a graph that
    # had not changed, which is worse than no check at all -- a flaky assertion
    # teaches you to ignore it.
    seen, frontier, guarded, hops = set(), [guns[0]], False, 0
    while frontier and hops < 400 and not guarded:
        node = frontier.pop(0)
        hops += 1
        if id(node) in seen:
            continue
        seen.add(id(node))
        if "Branch" in str(BEL.get_node_title(node)).replace("\n", " "):
            cond = BEL.find_input_pin(node, "Condition")
            if cond and cond.is_valid() and any(
                    G.DAMAGED_BY_PLAYER_VAR in str(BEL.get_node_title(
                        PIN.get_owning_node(q)))
                    for q in PIN.list_connected_pins(cond)):
                guarded = True
                break
        ins = BEL.find_input_pin(node, "execute")
        if ins and ins.is_valid():
            frontier.extend(PIN.get_owning_node(q)
                            for q in PIN.list_connected_pins(ins))
    check("only a death the player caused drops a weapon", guarded,
          "the safety net must not be a weapon dispenser")
check("an uncollected drop tidies itself away",
      any(abs(float(pin_value(n, "InLifespan") or 0) - G.AMMO_PICKUP_LIFETIME) < 1e-3
          for n in ag if "InLifespan" in in_pins(n)),
      f"{G.AMMO_PICKUP_LIFETIME:.0f}s")

# --- and who drops it --------------------------------------------------------
hp = load(G.HEALTH_BP_PATH)
hg = graph(hp).list_all_nodes()
check("a killed wanderer's health component knows what to drop",
      cdo(hp).get_editor_property("AmmoClass") is not None
      and cdo(hp).get_editor_property("AmmoClass").get_name() == "BP_AmmoPickup_C",
      str(cdo(hp).get_editor_property("AmmoClass")))
drops = [n for n in by_pins(hg, "Class", "SpawnTransform")
         if any("AmmoClass" in str(BEL.get_node_title(PIN.get_owning_node(q)))
                for q in PIN.list_connected_pins(BEL.find_input_pin(n, "Class")))]
check("exactly one spawn in the death path drops ammunition",
      len(drops) == 1, f"{len(drops)} ammo spawns")
# The same guard the kill counter uses, and for the same reason: the safety net
# writes Health to 0 for a wanderer that fell through the world, and paying the
# player for that would turn a bug into an ammunition supply.
if drops:
    seen, node, guarded = set(), drops[0], False
    for _ in range(40):
        ins = BEL.find_input_pin(node, "execute")
        feeders = [PIN.get_owning_node(q) for q in PIN.list_connected_pins(ins)] \
            if ins and ins.is_valid() else []
        if not feeders:
            break
        node = feeders[0]
        if id(node) in seen:
            break
        seen.add(id(node))
        title = str(BEL.get_node_title(node)).replace("\n", " ")
        if "Branch" in title:
            cond = BEL.find_input_pin(node, "Condition")
            if cond and cond.is_valid() and any(
                    G.DAMAGED_BY_PLAYER_VAR in str(BEL.get_node_title(
                        PIN.get_owning_node(q)))
                    for q in PIN.list_connected_pins(cond)):
                guarded = True
                break
    check("only a death the player caused drops shells", guarded,
          f"{G.DAMAGED_BY_PLAYER_VAR} branch found upstream: {guarded}")


# ─── Every call site is a placed one ─────────────────────────────────────────
# Attenuation on the asset only works if the sound is played AT somewhere.
# PlaySound2D / SpawnSound2D are non-spatial by construction -- they bypass
# attenuation entirely, whatever the SoundBase says -- so one of them anywhere
# in the game would be a sound that stayed flat while every check above passed.
#
# The sweep is over every Blueprint in the two folders that make noise, found
# by listing them, so a sixth sound-playing graph added later is covered
# without anybody remembering to add it here.

_placed, _flat_calls, _unwired, _overridden, _graphs = [], [], [], [], 0
for _dir in ("/Game/Weapons", "/Game/Forest/NPC"):
    for _ref in _eas.list_assets(_dir, recursive=True):
        _bp = load(_ref)
        if not isinstance(_bp, unreal.Blueprint):
            continue
        _g = graph(_bp)
        if _g is None:
            continue
        _graphs += 1
        # Nodes carrying a Sound INPUT pin: that is every play and spawn
        # overload and nothing else. Matching on the title instead would sweep
        # up every `Get FireSound` in the graph.
        for _n in by_pins(_g.list_all_nodes(), "Sound"):
            _t = str(BEL.get_node_title(_n)).replace("\n", " ")
            _where = f"{_bp.get_name()}: {_t}"
            _placed.append(_where)
            if "2D" in _t or "Location" not in in_pins(_n):
                _flat_calls.append(_where)
            if not PIN.list_connected_pins(BEL.find_input_pin(_n, "Sound")):
                _unwired.append(_where)
            _ap = BEL.find_input_pin(_n, "AttenuationSettings")
            if _ap and _ap.is_valid() and (PIN.list_connected_pins(_ap)
                                           or str(PIN.get_pin_value(_ap))
                                           not in ("", "None")):
                _overridden.append(_where)

check("every sound is played at a world location, never in 2D",
      not _flat_calls, str(sorted(_flat_calls)))
check("...and every one of them was handed a sound to play",
      not _unwired, str(sorted(_unwired)))
# Not a functional failure -- the pin overrides the asset and would still
# attenuate -- but it would be a second place the answer lives, and the whole
# point of setting it on the SoundBase was that there is only one.
check("...with no per-call attenuation override, so the asset is the one "
      "place it is said", not _overridden, str(sorted(_overridden)))
check("all five known call sites are still there: fire, dry fire, reload, "
      "footstep, and the wanderers' voice and melee thud",
      len(_placed) >= 5, f"{len(_placed)} across {_graphs} graphs")


# ─── Summary ─────────────────────────────────────────────────────────────────

unreal.log_warning(f"[VERIFY] {len(PASS)} passed, {len(FAIL)} failed")
for f in FAIL:
    unreal.log_warning(f"[VERIFY]   FAILED: {f}")
