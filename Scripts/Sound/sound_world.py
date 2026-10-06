"""The world's sounds, and the player's own: footsteps, the player's grunt at
a blow and cry at death, the forest's three beds, and where the world is
heard from.

SOUNDS is the area's rows of the sound table and BINDINGS where each is played
from:

    BP_FootstepComponent.Sounds        a footfall: the component's own takes,
                                       the player's (combat/footsteps.py owns
                                       the stride; it plays through
                                       Sound/play.py). Whoever else wears the
                                       component has a binding of its own on
                                       its Blueprint's copy of it: the
                                       wanderers' is Sound/sound_monsters.py
    BP_FootstepComponent.RustleSounds  a bush gone through, by anyone
                                       (the rustle, below)
    BP_HealthComponent.HurtSounds      the player's grunt   (the voice, below)
    BP_HealthComponent.DeathSounds     the player's cry
    BP_HealthComponent.HeartbeatSounds the player's heart at low health
    BP_WeaponComponent.BreathSounds    the player out of breath: the run key
                                       held with no stamina left
    BP_DayNightCycle BedDay/BedNight/BedWind   the beds     (the ambience, below)

and the pieces of sound logic that are the world's: the voice (the grunt, the
cry, the heartbeat, the breath), the rustle, the ambience, and the listener.
"""

import unreal

from combat import footstep_vars as FV
from combat import health_vars as HV
from combat.game_state import LAST_DAMAGE_VAR, NEVER_DAMAGED
from combat.paths import FOOTSTEP_BP_PATH, HEALTH_BP_PATH, WEAPON_COMP_BP_PATH
from combat.weapon_component import vars as WV
from combat.weapon_component.slot_nodes import for_each, not_, op
from combat.weapon_component.sprint import SPRINT_SPENT_VAR
from forest_generator.bush_placement import DEFAULT_BUSH_SPECS
from forest_generator.grass_cells import GRASS_TAG
from Sound.bind import defaults_for
from Sound.play import _author_random_sound
from Sound.sound_def import (
    ATT_FOLEY, ATT_FOOTSTEP, AUDIBLE_LIMIT_CM, AttenuationProfile, BED_DIR, Binding, Sound, takes)
from uebp import props as EP
from uebp.g import _G
from uebp.graph import (
    BEL, _add_component, _assets, _component_object, _connect, _drop_components, _loose_pin,
    _must_load, _node, _palette, _pin, _root_handle, _set, else_, out, then)
from uebp.nodes.actor import (
    FN_ACTOR_LOC, FN_GET_COMP, FN_GET_OWNER, FN_INSTANCES_IN_SPHERE, FN_IS_LOCALLY_CONTROLLED,
    FN_SET_LISTENER_ATTENUATION)
from uebp.nodes.array import FN_ARR_ADD, FN_ARR_CONTAINS, FN_ARR_LEN
from uebp.nodes.math import (
    FN_ADD_FF, FN_AND, FN_GE_FF, FN_GREATER_FF, FN_GREATER_II, FN_LESS_FF, FN_MUL_FF,
    FN_SUB_FF)
from uebp.nodes.palette import NODE_CAST_INSTANCED, NODE_CAST_PAWN
from uebp.nodes.system import FN_SET_VOLUME, FN_TIME_SECONDS, FN_WITH_TAG
from world import day_night_vars as DV
from world.day_night_graph import _call, _map
from world.day_night_graph import _get as _dn_get
from world.paths import DAY_NIGHT_BP_PATH

# The footsteps were as loud as recorded and drowned the forest: under half.
FOOTSTEPS = Sound("footsteps", "footsteps", takes("footsteps"), ATT_FOOTSTEP, volume=0.4)
PLAYER_HIT = Sound("player_hit", "player hit", takes("player_hit"), ATT_FOLEY)
PLAYER_DEATH = Sound("player_death", "player death", takes("player_death"), ATT_FOLEY)
# HOW FAR OFF A BUSH IS HEARD TO RUSTLE: the config for it. Anyone going through
# a bush, the player or a wanderer, is silent from this far and further, and
# rises on a straight line to full volume at RUSTLE_FULL_CM. On the footstep's
# own 20 m line a zombie in a bush 10 m off was at half volume under its own
# heavier step, and was not heard. To change it: this number, then
# build_sound.py.
RUSTLE_HEARD_CM = 3000.0
RUSTLE_FULL_CM = 500.0
if not RUSTLE_FULL_CM < RUSTLE_HEARD_CM <= AUDIBLE_LIMIT_CM:
    raise RuntimeError(
        f"RUSTLE_HEARD_CM is {RUSTLE_HEARD_CM:g}: it has to be over "
        f"{RUSTLE_FULL_CM:g} (full volume) and at most {AUDIBLE_LIMIT_CM:g}")
ATT_RUSTLE = AttenuationProfile(
    "A_Att_Rustle", RUSTLE_FULL_CM, RUSTLE_HEARD_CM - RUSTLE_FULL_CM, linear=True)
# A bush gone through: leaves brushed past, heard from further than a footstep.
GRASS_RUSTLE = Sound("grass_rustle", "bush rustle", takes("grass_rustle"), ATT_RUSTLE)
PLAYER_BREATH = Sound("player_breath", "player out of breath", takes("player_breath"), ATT_FOLEY)
# Under the rest: the recording is loud, and it plays for as long as the
# player is hurt.
HEARTBEAT = Sound("heartbeat", "heartbeat", takes("heartbeat"), ATT_FOLEY, volume=0.6)

# ── The beds ─────────────────────────────────────────────────────────────────
#
# The one kind of sound that is NOT something in the level making a noise at a
# place: the forest itself, by day and by night, and the wind. A bed is
# stereo, loops, and has no attenuation profile on purpose -- it is all round
# the player wherever they stand. They live in a folder of their own, below
# the one apply_attenuation() sweeps, so that sweep still means what it says:
# every wave in the two audio folders is placed, and a flat one there is a
# mistake. BP_DayNightCycle plays them (the ambience, below).


def _bed(key, label, volume):
    return Sound(key, label, takes(key), None, folder=BED_DIR, volume=volume)


# Under everything else; the wind silent until a better one is found: the bed
# plays, at nothing.
AMBIENCE_DAY = _bed("ambience_day", "day birds", 0.7)
AMBIENCE_NIGHT = _bed("ambience_night", "night", 0.7)
AMBIENCE_WIND = _bed("ambience_wind", "wind", 0.0)
SOUNDS = (FOOTSTEPS, PLAYER_HIT, PLAYER_DEATH, AMBIENCE_DAY, AMBIENCE_NIGHT, AMBIENCE_WIND,
          GRASS_RUSTLE, PLAYER_BREATH, HEARTBEAT)

BED_DAY, BED_NIGHT, BED_WIND = (s.names[0] for s in (AMBIENCE_DAY, AMBIENCE_NIGHT, AMBIENCE_WIND))
BED_DAY_COMP, BED_NIGHT_COMP, BED_WIND_COMP = "BedDay", "BedNight", "BedWind"
BEDS = ((BED_DAY_COMP, BED_DAY), (BED_NIGHT_COMP, BED_NIGHT), (BED_WIND_COMP, BED_WIND))

BINDINGS = (
    Binding(FOOTSTEP_BP_PATH, FV.Sounds, FOOTSTEPS),
    Binding(HEALTH_BP_PATH, HV.HurtSounds, PLAYER_HIT),
    Binding(HEALTH_BP_PATH, HV.DeathSounds, PLAYER_DEATH),
    Binding(FOOTSTEP_BP_PATH, FV.RustleSounds, GRASS_RUSTLE),
    Binding(HEALTH_BP_PATH, HV.HeartbeatSounds, HEARTBEAT),
    Binding(WEAPON_COMP_BP_PATH, WV.BreathSounds, PLAYER_BREATH),
    Binding(DAY_NIGHT_BP_PATH, "sound", AMBIENCE_DAY, single=True, component=BED_DAY_COMP),
    Binding(DAY_NIGHT_BP_PATH, "sound", AMBIENCE_NIGHT, single=True, component=BED_NIGHT_COMP),
    Binding(DAY_NIGHT_BP_PATH, "sound", AMBIENCE_WIND, single=True, component=BED_WIND_COMP),
)


# ─── The player's voice ──────────────────────────────────────────────────────
#
# The player's voice: a grunt when a blow lands, a cry when it kills.
#
# Authored into BP_HealthComponent's Tick, because that is where a hit is
# known, whoever dealt it:
#
#     [Tick ...] --> LastDamageTime later than HeardDamageTime?    a new blow
#                  --> HeardDamageTime = LastDamageTime
#                  --> the player's (not DespawnOnDeath), and still alive?
#                  --> one of HurtSounds, at the owner
#     [... Dead = true] --> the player's? --> one of DeathSounds, at the owner
#
# A BLOW, NOT A LOSS OF HEALTH. Health also goes down by a little every frame
# while the player starves, bleeds or freezes (debuff_drain.py), and a voice
# hung on "Health went down" would grunt sixty times a second. Whatever strikes
# stamps LastDamageTime (a pellet, a fist, a wanderer's swing), and nothing that
# drains does, so the stamp moving is the blow.
#
# THE PLAYER ONLY, for now: the component is the wanderers' too, and theirs
# have no takes yet. DespawnOnDeath is what tells the two apart, as it does for
# the death menu.
#
# The blow that kills is not grunted at: the death branch cries instead.


def voice_defaults():
    """{variable: its takes, loaded}; a take never imported is left out."""
    return {**defaults_for(HEALTH_BP_PATH, BINDINGS), HV.HeardDamageTime: NEVER_DAMAGED}


def _get(ed, name):
    return out(ed.add_get_member_variable_node(name), name)


def _at_owner(ed):
    owner = _node(ed, FN_GET_OWNER)
    here = _node(ed, FN_ACTOR_LOC)
    _connect(out(owner), _pin(here, "self"))
    return out(here)


def _author_hurt_voice(ed, exec_ins):
    """A new blow on a living player: grunt. Returns the stage's exits."""
    newer = _node(ed, FN_GREATER_FF)
    _connect(_get(ed, LAST_DAMAGE_VAR), _pin(newer, "A"))
    _connect(_get(ed, HV.HeardDamageTime), _pin(newer, "B"))
    struck = ed.add_branch_node()
    _connect(out(newer), _pin(struck, "Condition"))
    for pin in exec_ins:
        _connect(pin, _pin(struck, "execute"))
    heard = ed.add_set_member_variable_node(HV.HeardDamageTime)
    _connect(_get(ed, LAST_DAMAGE_VAR), _pin(heard, HV.HeardDamageTime))
    _connect(then(struck), _pin(heard, "execute"))

    wanderer = ed.add_branch_node()
    _connect(_get(ed, HV.DespawnOnDeath), _pin(wanderer, "Condition"))
    _connect(then(heard), _pin(wanderer, "execute"))
    living = _node(ed, FN_GREATER_FF)
    _connect(_get(ed, HV.Health), _pin(living, "A"))
    _set(living, "B", 0.0)
    alive = ed.add_branch_node()
    _connect(out(living), _pin(alive, "Condition"))
    _connect(else_(wanderer), _pin(alive, "execute"))
    _made, grunted = _author_random_sound(ed, HV.HurtSounds, _at_owner(ed), then(alive))

    ed.add_comment_to_nodes(
        "The player's grunt. LastDamageTime moved, so something struck (a "
        "drain does not stamp it); on the player, still alive, one of "
        "HurtSounds is played where they stand.",
        [struck, heard, wanderer, alive])
    return (grunted, else_(struck), then(wanderer), else_(alive))


def _author_death_voice(ed, exec_ins):
    """Just dead: the player cries out. Returns the stage's exits."""
    wanderer = ed.add_branch_node()
    _connect(_get(ed, HV.DespawnOnDeath), _pin(wanderer, "Condition"))
    for pin in exec_ins:
        _connect(pin, _pin(wanderer, "execute"))
    _made, cried = _author_random_sound(ed, HV.DeathSounds, _at_owner(ed), else_(wanderer))
    ed.add_comment_to_nodes(
        "The player's death: one of DeathSounds, the once (DeathPlayed was just set).",
        [wanderer])
    return (cried, then(wanderer))


# ─── The heart and the breath ────────────────────────────────────────────────
#
# Two sounds that go on for as long as a state does, each a take played again
# as it ends: a time it may next be heard, pushed on by the take's length each
# time it is played. A one-shot, not a component, so a take that has started
# plays out (the heart beats on for up to HEARTBEAT_S after a heal).
#
#     the heart   BP_HealthComponent's Tick: the player's (not DespawnOnDeath),
#                 alive, under LOW_HEALTH_FRACTION of MaxHealth
#     the breath  BP_WeaponComponent's Tick, after the sprint: SprintSpent,
#                 which is the run key held with Stamina run out (sprint.py)

# Under this much of MaxHealth the heart is heard.
LOW_HEALTH_FRACTION = 0.3
# The heartbeat's cut is four beats, one every 1.64 s (selection.py): played
# again on the beat. The breath is the take's length and a moment.
HEARTBEAT_S = 6.56
BREATH_S = 4.3


def _num(g, fn, a, b):
    """A two-input pure node with a float literal on B; its ReturnValue."""
    n = g.call(fn, A=a)
    _set(n, "B", b)
    return out(n)


def _author_again(g, due_var, period, sounds_var, at_pin, wanted, exec_ins):
    """Where ``wanted`` (a bool pin) holds and ``due_var`` has come: play one
    of ``sounds_var`` at ``at_pin`` and put ``due_var`` ``period`` on. Returns
    the exits."""
    due = op(g, FN_GE_FF, out(g.call(FN_TIME_SECONDS)), g.get(due_var))
    play, rest = g.branch(op(g, FN_AND, wanted, due), exec_ins)
    waits = g.put(due_var, _num(g, FN_ADD_FF, out(g.call(FN_TIME_SECONDS)), period), [play])
    made, heard = _author_random_sound(g.ed, sounds_var, at_pin, waits)
    g.made.extend(made)
    return (heard, rest)


def _author_heartbeat(ed, exec_ins):
    """The player's heart, heard while they are badly hurt. Returns the exits."""
    g = _G(ed)
    low = op(g, FN_LESS_FF, g.get(HV.Health), _num(g, FN_MUL_FF, g.get(HV.MaxHealth),
                                                   LOW_HEALTH_FRACTION))
    alive = _num(g, FN_GREATER_FF, g.get(HV.Health), 0.0)
    hurt = op(g, FN_AND, op(g, FN_AND, not_(g, g.get(HV.DespawnOnDeath)), alive), low)
    # A heart is heard by the one whose it is: this copy's player is this
    # machine's (another player's character has a health component here too).
    pawn = g.keep(_palette(ed, NODE_CAST_PAWN))
    _connect(out(g.call(FN_GET_OWNER)), _pin(pawn, "Object"))
    for pin in exec_ins:
        _connect(pin, _pin(pawn, "execute"))
    mine = g.call(FN_IS_LOCALLY_CONTROLLED, self=_loose_pin(pawn, "AsPawn", is_input=False))
    exits = _author_again(g, HV.HeartbeatNextTime, HEARTBEAT_S, HV.HeartbeatSounds,
                          _at_owner(ed), op(g, FN_AND, hurt, out(mine)), [then(pawn)])
    ed.add_comment_to_nodes(
        f"The player's heart: this machine's own player, alive and under "
        f"{LOW_HEALTH_FRACTION:g} of MaxHealth, one of HeartbeatSounds where they stand, "
        f"again every {HEARTBEAT_S:g} s (its four beats).",
        g.made)
    return (*exits, out(pawn, "CastFailed"))


def _author_breath(ed, owner_out, exec_ins):
    """The player out of breath: the run key held with no stamina left
    (SprintSpent). On the weapon component, after the sprint. Returns the exits."""
    g = _G(ed)
    here = g.call(FN_ACTOR_LOC, self=owner_out)
    exits = _author_again(g, WV.BreathNextTime, BREATH_S, WV.BreathSounds, out(here),
                          g.get(SPRINT_SPENT_VAR), exec_ins)
    ed.add_comment_to_nodes(
        f"Out of breath: while {SPRINT_SPENT_VAR} (the run key held, Stamina run out), one "
        f"of BreathSounds at the player, again every {BREATH_S:g} s.", g.made)
    return exits


# ─── Going through a bush ────────────────────────────────────────────────────
#
# Whoever wears the footstep component, the player or a wanderer, rustles as
# they go through a bush. A bush has no collision (it is walked through), so
# nothing overlaps it: the walker asks the bushes themselves.
#
#     [BeginPlay] every actor tagged as a grass cell -> its instanced mesh
#                 component -> Bushes, if its mesh is one of BushMeshes
#     [every RustleStrideCm of ground covered: RUSTLE_STRIDE_CM]
#                 InBush = some component of Bushes has an instance whose
#                 bounds reach within RUSTLE_REACH_CM of the walker
#                 -> one of RustleSounds there, at StepVolume
#
# The rustle has a measure of its own (RustleTravelled), half a footfall's
# stride. Asked only at a footfall, a bush crossed was one rustle, played in
# the same instant as the step: a wanderer's heavier step covered it, and a
# zombie was not heard to go through a bush at all. On its own measure a bush
# crossed is two or three, most of them between two steps.
#
# The bush cells carry the grass cells' tag and no other, so the mesh tells
# them apart (the level needs no regenerating for this). The walk over Bushes
# is per RUSTLE_STRIDE_CM, not per frame: 2 components on the 200 m map, 200
# on the 1 km one.

RUSTLE_STRIDE_CM = 80.0
RUSTLE_REACH_CM = 30.0
ISM_CLASS = "/Script/Engine.InstancedStaticMeshComponent"


def rustle_defaults():
    """{BushMeshes: the bush meshes, loaded (one never built is left out),
    RustleStrideCm: the rustle's measure}."""
    eas = _assets()
    return {FV.RustleStrideCm: RUSTLE_STRIDE_CM,
            FV.BushMeshes: [eas.load_asset(s.mesh_path) for s in DEFAULT_BUSH_SPECS
                            if eas.does_asset_exist(s.mesh_path)]}


def _author_find_bushes(ed, exec_in):
    """BeginPlay: Bushes = the level's bush components. Returns the exec pin after."""
    g = _G(ed)
    cells = g.call(FN_WITH_TAG, [exec_in], Tag=GRASS_TAG)
    cell, _index, body, done = for_each(g, out(cells, "OutActors"), [then(cells)])
    comp = g.call(FN_GET_COMP, self=cell)
    _pin(comp, "ComponentClass").set_pin_value(ISM_CLASS)
    instanced = g.keep(_palette(ed, NODE_CAST_INSTANCED))
    _connect(out(comp), _pin(instanced, "Object"))
    _connect(body, _pin(instanced, "execute"))
    as_ism = _loose_pin(instanced, "AsInstancedStaticMeshComponent", is_input=False)
    mesh = g.iget(as_ism, EP.STATIC_MESH, "/Script/Engine.StaticMeshComponent")
    known = g.call(FN_ARR_CONTAINS, TargetArray=g.get(FV.BushMeshes), ItemToFind=mesh)
    bush, _other = g.branch(out(known), [then(instanced)])
    g.call(FN_ARR_ADD, [bush], TargetArray=g.get(FV.Bushes), NewItem=as_ism)
    ed.add_comment_to_nodes(
        f"The level's bushes: of the cells tagged {GRASS_TAG}, the instanced "
        "components whose mesh is one of BushMeshes. A footfall asks them "
        "whether it is inside one.", g.made)
    return done


def _author_rustle(ed, at_pin, volume_pin, moved_pin, exec_in):
    """``moved_pin`` of ground covered this frame by a walker at ``at_pin``:
    every RustleStrideCm of it, inside a bush, one of RustleSounds there, at
    ``volume_pin``. Returns the exits."""
    g = _G(ed)
    # Stored, then read: the sum is pure and would be taken again off the new
    # RustleTravelled on a second read.
    gone = g.put(FV.RustleTravelled, op(g, FN_ADD_FF, g.get(FV.RustleTravelled), moved_pin),
                 [exec_in])
    far = op(g, FN_GE_FF, g.get(FV.RustleTravelled), g.get(FV.RustleStrideCm))
    due, not_yet = g.branch(far, [gone])
    left = g.call(FN_SUB_FF, A=g.get(FV.RustleTravelled), B=g.get(FV.RustleStrideCm))
    out_of = g.keep(ed.add_set_member_variable_node(FV.InBush))
    _set(out_of, FV.InBush, False)
    _connect(g.put(FV.RustleTravelled, out(left), [due]), _pin(out_of, "execute"))
    bush, _index, body, done = for_each(g, g.get(FV.Bushes), [then(out_of)])
    near = g.call(FN_INSTANCES_IN_SPHERE, self=bush, Center=at_pin)
    _set(near, "Radius", RUSTLE_REACH_CM)
    _set(near, "bSphereInWorldSpace", True)
    # Const, so pure here; were it ever given an exec pin, it goes in the chain.
    runs = BEL.find_input_pin(near, "execute")
    if runs and runs.is_valid():
        _connect(body, runs)
        body = then(near)
    count = g.call(FN_ARR_LEN, TargetArray=out(near))
    inside, _clear = g.branch(op(g, FN_GREATER_II, out(count), 0), [body])
    mark = g.keep(ed.add_set_member_variable_node(FV.InBush))
    _set(mark, FV.InBush, True)
    _connect(inside, _pin(mark, "execute"))
    brushed, open_ground = g.branch(g.get(FV.InBush), [done])
    made, heard = _author_random_sound(ed, FV.RustleSounds, at_pin, brushed, volume_pin=volume_pin)
    ed.add_comment_to_nodes(
        f"Going through a bush rustles: every {RUSTLE_STRIDE_CM:g} cm of ground covered, "
        f"some component of Bushes has an instance within {RUSTLE_REACH_CM:g} cm of the "
        "walker (a bush has no collision, so its instances' bounds are asked), and one of "
        "RustleSounds plays there, at StepVolume.",
        g.made + made)
    return (heard, open_ground, not_yet)


# ─── The forest's own sound ──────────────────────────────────────────────────
#
# The forest's own sound: three beds on BP_DayNightCycle, and the Tick step
# that hands the day's over to the night's.
#
#     BedDay     the day's birds          volume = DayAmount
#     BedNight   crickets and owls        volume = 1 - DayAmount
#     BedWind    the wind, always         volume 1
#
# Three AudioComponents on the cycle actor, each playing one looping stereo
# wave (BEDS) from the moment the level starts. They are
# on the cycle because it is the one actor every level has and the one that
# knows DayAmount: the same number that fades the sun into the moon fades the
# birds into the crickets, so dusk sounds like dusk for as long as it looks
# like it.
#
# A bed has no attenuation and is not at a place: where the actor stands does
# not matter. Its loudness is its SoundClass's row on the SOUND SETTINGS tab,
# which the component's volume multiplies.
#
# A bed at volume zero goes on playing (the wave's virtualization mode, set
# at import), so the night's is in the same place in its two minutes when dusk
# comes round as it would have been had it been heard all day.


def build_beds(bp):
    """Drop and re-add the three bed components, each with its wave."""
    _drop_components(bp, {name for name, _wave in BEDS})
    root = _root_handle(bp)
    for name, wave in BEDS:
        bed = _component_object(_add_component(bp, root, unreal.AudioComponent, name))
        bed.set_editor_property("sound", _must_load(f"{BED_DIR}/{wave}"))
        bed.set_editor_property("auto_activate", True)
        # All round the player, not at the actor: a bed is not a place.
        bed.set_editor_property("allow_spatialization", False)
        bed.set_editor_property("is_ui_sound", False)


def author_ambience(ed, chain):
    """Extend the Tick chain: the day's bed by DayAmount, the night's by the rest."""
    day = _dn_get(ed, DV.DayAmount)
    night = _map(ed, _dn_get(ed, DV.DayAmount), 0.0, 1.0, 1.0, 0.0)
    birds = chain.step(_call(ed, FN_SET_VOLUME, self=_dn_get(ed, BED_DAY_COMP),
                             NewVolumeMultiplier=day))
    crickets = chain.step(_call(ed, FN_SET_VOLUME, self=_dn_get(ed, BED_NIGHT_COMP),
                                NewVolumeMultiplier=night))
    ed.add_comment_to_nodes(
        "The forest's sound follows the light: the day's bed is as loud as "
        "DayAmount, the night's as 1 - DayAmount. The wind plays on.",
        [birds, crickets])


# ─── Heard from the character, not the camera ────────────────────────────────
#
# BeginPlay: hear the world from where the character stands, not from the camera.
#
# The engine's listener sits on the camera, for panning and for distance alike.
# The camera does not stay put: over the shoulder it rides the boom about 2.6 m
# behind the character, and down the sights it travels to the gun at the eye.
# Every sound measured against it changed loudness with the view. The footsteps
# showed it most (A_Att_Foley falls off from 1 m): they were quiet behind the
# shoulder and loud down the sights.
#
# SetAudioListenerAttenuationOverride splits the two. Distance is measured from
# the character's capsule, which is the same place in every view. Direction still
# comes from the camera, so a sound on the left of the screen is still heard on
# the left. The override follows the component and never needs refreshing. A
# restart opens the level again, and the new character's BeginPlay sets it again.


def _author_listener_at_character(ed, as_char, pc_out, exec_in):
    """Pin the player controller's attenuation listener to the capsule.

    The offset pin stays empty, which compiles as zero: the listener is the
    capsule's centre. Returns the then pin.
    """
    capsule = ed.add_get_member_variable_node(EP.CAPSULE_COMPONENT, "/Script/Engine.Character")
    _connect(as_char, _pin(capsule, "self"))
    listen = _node(ed, FN_SET_LISTENER_ATTENUATION)
    _connect(pc_out, _pin(listen, "self"))
    _connect(out(capsule, EP.CAPSULE_COMPONENT), _pin(listen, "AttachToComponent"))
    _connect(exec_in, _pin(listen, "execute"))
    ed.add_comment_to_nodes(
        "Sounds fade with the distance from the character, not from the "
        "camera, so aiming down the sights does not make the footsteps "
        "louder. Panning still follows the camera.",
        [capsule, listen])
    return then(listen)
