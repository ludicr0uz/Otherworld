"""Graph fragments BP_HealthComponent runs when something dies: the kill
count, the shells, the ragdoll collapse, the corpse timer and the player's own
death. The gun drop spliced in after the shells is gun_drop.py; the corpse
loot rolled after it is loot/roll.py.
"""

from combat.game_state import (
    DAMAGED_BY_PLAYER_VAR, DEAD_LOG_PREFIX, KILL_COUNT_VAR, PLAYER_DEAD_VAR,
)
from uebp.graph import (
    _connect, _loose_pin, _node, _palette, _pin, _set, _vec, else_, out, then)
from combat.gun_drop import _author_gun_drop
from combat.paths import GAME_MODE_CLASS_PATH
from combat.ragdoll import RAGDOLL_PROFILE
from combat.tuning import AMMO_DROP_SHELLS, AMMO_PICKUP_LIFT
from loot.roll import author_loot_roll
from uebp.nodes.actor import (
    FN_ACTOR_LOC, FN_DISABLE_MOVEMENT, FN_GET_CONTROLLER, FN_GET_OWNER, FN_LIFESPAN,
    FN_SET_COLLISION, FN_SET_PROFILE, FN_SIMULATE_ALL)
from uebp.nodes.math import FN_ADD_II, FN_ADD_VV, FN_MAKE_TRANSFORM
from uebp.nodes.palette import (
    NODE_CAST_CHARACTER, NODE_CAST_GAME_MODE, NODE_CAST_PAWN, NODE_SPAWN)
from uebp.nodes.system import (
    FN_CONCAT, FN_DELAY, FN_GET_GAME_MODE, FN_INT_TO_STR, FN_IS_VALID, FN_PRINT,
    FN_SET_PAUSED)


# How long a corpse lies where it fell. Long enough that a firefight leaves a
# visible history of itself, short enough that a long session does not end up
# rendering a hundred skeletal meshes nobody is looking at.
CORPSE_SECONDS = 60.0
# How long a dead wanderer's AI controller outlives it. Not zero: SetLifeSpan(0)
# means "live forever". The controller's own heartbeat already stopped when it
# saw the pawn Dead (npc/corpse.py), so this is only how soon it is cleaned up.
CONTROLLER_RETIRE_SECONDS = 0.1
# How long the player's body is left falling before the game pauses and the
# menu opens. The pause stops physics too, so this is also how long the ragdoll
# gets to settle: pausing early freezes the player mid-topple, which reads as a
# hang rather than as a death.
DEATH_PAUSE_SECONDS = 2.2


def _author_kill_count(ed, exec_in):
    """Count this death on the GameMode, if a pellet is what caused it.

    Spliced between "this one despawns" and the respawn, so it sees exactly the
    deaths that are a wanderer's. The guard is the point: the safety net writes
    Health to 0 for anything that falls under the world, and the same death path
    runs for it -- counting that as a kill would inflate the score every time
    the terrain lost someone. Only a pellet sets DamagedByPlayer.

    Returns the exec pins to carry on from -- both of them, because a wanderer
    that died unshot still has to be replaced.
    """
    earned = ed.add_get_member_variable_node(DAMAGED_BY_PLAYER_VAR)
    shot = ed.add_branch_node()
    _connect(out(earned, DAMAGED_BY_PLAYER_VAR), _pin(shot, "Condition"))
    _connect(exec_in, _pin(shot, "execute"))

    mode = _node(ed, FN_GET_GAME_MODE)
    as_mode = _palette(ed, NODE_CAST_GAME_MODE)
    _connect(out(mode), _pin(as_mode, "Object"))
    _connect(then(shot), _pin(as_mode, "execute"))
    mode_out = _loose_pin(as_mode, "AsBPThirdPersonGameMode", is_input=False)

    tally = ed.add_get_member_variable_node(KILL_COUNT_VAR, GAME_MODE_CLASS_PATH)
    _connect(mode_out, _pin(tally, "self"))
    one_more = _node(ed, FN_ADD_II)
    _connect(out(tally, KILL_COUNT_VAR), _pin(one_more, "A"))
    _set(one_more, "B", 1)
    write = ed.add_set_member_variable_node(KILL_COUNT_VAR, GAME_MODE_CLASS_PATH)
    _connect(mode_out, _pin(write, "self"))
    _connect(out(one_more), _pin(write, KILL_COUNT_VAR))
    _connect(then(as_mode), _pin(write, "execute"))

    # --- and the shells it drops --------------------------------------------
    # On the same arm as the count, and for the same reason: a wanderer the
    # terrain swallowed was not killed, and paying the player for it would turn
    # the safety net into an ammunition supply.
    #
    # Spawned before the owner is destroyed, at the owner's feet plus a lift --
    # the corpse's origin is at the capsule centre, so a drop placed exactly
    # there is inside the body on the frame it appears.
    corpse = _node(ed, FN_GET_OWNER)
    fell_at = _node(ed, FN_ACTOR_LOC)
    _connect(out(corpse), _pin(fell_at, "self"))
    lifted = _node(ed, FN_ADD_VV)
    _connect(out(fell_at), _pin(lifted, "A"))
    _connect(_vec(ed, 0.0, 0.0, AMMO_PICKUP_LIFT), _pin(lifted, "B"))
    where = _node(ed, FN_MAKE_TRANSFORM)
    _connect(out(lifted), _pin(where, "Location"))
    # A struct pin cannot be given a literal, and an unset Scale pin compiles to
    # the zero vector -- which spawns the pickup at zero size, invisible.
    _connect(_vec(ed, 1.0, 1.0, 1.0), _pin(where, "Scale"))

    ammo_cls = ed.add_get_member_variable_node("AmmoClass")
    drop = _palette(ed, NODE_SPAWN)
    _connect(out(ammo_cls, "AmmoClass"), _pin(drop, "Class"))
    _connect(out(where), _pin(drop, "SpawnTransform"))
    _set(drop, "CollisionHandlingOverride", "AlwaysSpawn")
    _connect(then(write), _pin(drop, "execute"))

    ed.add_comment_to_nodes(
        f"One kill, counted on the GameMode where it outlives the wanderer that "
        f"earned it, and {AMMO_DROP_SHELLS} shells left where it fell. "
        "DamagedByPlayer is the guard on both: the safety net kills anything "
        "that falls under the world through this same path, and nobody shot it.",
        [earned, shot, mode, as_mode, tally, one_more, write, corpse, fell_at,
         lifted, where, ammo_cls, drop])

    gun_exits = _author_gun_drop(ed, mode_out, out(lifted), then(drop))
    # Then what the body carries, for the loot window (loot/roll.py). After the
    # gun drop, on the same counted-kill arm.
    looted = author_loot_roll(ed, gun_exits)
    return (looted, out(as_mode, "CastFailed"), else_(shot))


def _author_death_collapse(ed, exec_ins):
    """The body goes down, physically, and stops being in the way.

    Shared by the player and by every wanderer, which is the point: there is
    one answer in this project to "what does dying look like", and both arms of
    the death branch walk into it. See the RAGDOLL_PROFILE comment for why it
    is a ragdoll and not a clip -- in short, there is no clip, here or in Epic's
    content, that ends with a body on the ground.

    Four calls, in this order and for these reasons:

      1. DisableMovement. CharacterMovement is still driving the capsule, and a
         corpse whose capsule is walking gets dragged along by the mesh's
         attachment. Movement, not input: the HUD polls the restart key off the
         same PlayerController and turning input off risks it.
      2. the capsule stops colliding. It is the capsule -- not the mesh -- that
         blocks the player and that blocks the pellets (see make_shootable), so
         switching it off is both halves of "a corpse is not in the way": you
         can walk through it and you cannot waste ammunition on it.
      3. the mesh takes the Ragdoll profile, which is what makes the bodies
         collide with the terrain and ignore Pawn. Without it the mesh keeps
         CharacterMesh, which collides with nothing, and the ragdoll falls
         through the world.
      4. only then simulate. Set the profile after simulation starts and the
         first frame is resolved against the old responses.

    Returns the exec to carry on with.
    """
    owner = _node(ed, FN_GET_OWNER)
    as_char = _palette(ed, NODE_CAST_CHARACTER)
    _connect(out(owner), _pin(as_char, "Object"))
    for tail in exec_ins:
        _connect(tail, _pin(as_char, "execute"))
    char_out = _loose_pin(as_char, "AsCharacter", is_input=False)

    movement = ed.add_get_member_variable_node("CharacterMovement", "/Script/Engine.Character")
    _connect(char_out, _pin(movement, "self"))
    stop = _node(ed, FN_DISABLE_MOVEMENT)
    _connect(out(movement, "CharacterMovement"), _pin(stop, "self"))
    _connect(then(as_char), _pin(stop, "execute"))

    capsule = ed.add_get_member_variable_node("CapsuleComponent", "/Script/Engine.Character")
    _connect(char_out, _pin(capsule, "self"))
    intangible = _node(ed, FN_SET_COLLISION)
    _connect(out(capsule, "CapsuleComponent"), _pin(intangible, "self"))
    _set(intangible, "NewType", "NoCollision")
    _connect(then(stop), _pin(intangible, "execute"))

    mesh = ed.add_get_member_variable_node("Mesh", "/Script/Engine.Character")
    _connect(char_out, _pin(mesh, "self"))
    mesh_out = out(mesh, "Mesh")

    loosen = _node(ed, FN_SET_PROFILE)
    _connect(mesh_out, _pin(loosen, "self"))
    _set(loosen, "InCollisionProfileName", RAGDOLL_PROFILE)
    _connect(then(intangible), _pin(loosen, "execute"))

    limp = _node(ed, FN_SIMULATE_ALL)
    _connect(mesh_out, _pin(limp, "self"))
    _set(limp, "bNewSimulate", "true")
    _connect(then(loosen), _pin(limp, "execute"))

    ed.add_comment_to_nodes(
        f"Dying, for the player and for every wanderer alike: stop the "
        f"movement, switch the capsule off so the body is neither an obstacle "
        f"nor a target, put the mesh on the {RAGDOLL_PROFILE} profile and "
        f"simulate every body in the physics asset. There is no death clip in "
        f"this project to play instead -- Meshy generates a walk and a run, and "
        f"Epic's six MM_Death_* clips are staggers that end on their feet.",
        [owner, as_char, movement, stop, capsule, intangible, mesh, loosen, limp])

    # The cast failure is carried, not dropped: a thing with no Character under
    # it cannot be ragdolled, but the player still has to get a menu and a
    # wanderer still has to be cleaned up.
    return (then(limp), out(as_char, "CastFailed"))


def _author_corpse(ed, exec_ins):
    """Everything a dead wanderer has to stop doing, and when it goes away.

    The collapse is shared (see _author_death_collapse); this is the half that
    is only true of an NPC.

    The AI controller is retired with SetLifeSpan, NOT K2_DestroyActor. This
    used to call DestroyActor on it, and that never did anything: the engine
    overrides AController::K2_DestroyActor with an empty body ("disallow
    destroying controller from Blueprints", Controller.cpp). Every corpse kept
    its controller, and the controller kept its chase-and-swing loop. Its
    movement was disabled, but the melee is a distance check from the capsule,
    and the ragdoll rolls away from the capsule. A player who stood where a
    wanderer died was hit by nothing they could see.

    Two things now close that, and neither relies on the other:
      * npc/corpse.py: the heartbeat's first check is the pawn's Dead flag, and
        a corpse's loop ends there. That is what stops the swinging.
      * here: the controller gets CONTROLLER_RETIRE_SECONDS of lifespan. When a
        lifespan runs out the engine calls the C++ Destroy(), which the
        Blueprint override does not block, and a destroyed controller
        unpossesses on the way out. So one controller does not leak per kill.

    The body lies there for CORPSE_SECONDS, also by SetLifeSpan -- a Delay here
    would be a latent action on a component belonging to the actor it is
    waiting to destroy.
    """
    owner = _node(ed, FN_GET_OWNER)
    owner_out = out(owner)
    as_pawn = _palette(ed, NODE_CAST_PAWN)
    _connect(owner_out, _pin(as_pawn, "Object"))
    for tail in exec_ins:
        _connect(tail, _pin(as_pawn, "execute"))

    # GetController, not the Controller member: APawn::Controller is not marked
    # BlueprintReadOnly, and a get-variable node for it compiles as a warning
    # today and an error in a future release.
    brain = _node(ed, FN_GET_CONTROLLER)
    _connect(_loose_pin(as_pawn, "AsPawn", is_input=False), _pin(brain, "self"))
    brain_out = out(brain)
    possessed = _node(ed, FN_IS_VALID)
    _connect(brain_out, _pin(possessed, "Object"))
    has_brain = ed.add_branch_node()
    _connect(out(possessed), _pin(has_brain, "Condition"))
    _connect(then(as_pawn), _pin(has_brain, "execute"))

    lobotomy = _node(ed, FN_LIFESPAN)
    _connect(brain_out, _pin(lobotomy, "self"))
    _set(lobotomy, "InLifespan", CONTROLLER_RETIRE_SECONDS)
    _connect(then(has_brain), _pin(lobotomy, "execute"))

    rot = _node(ed, FN_LIFESPAN)
    _connect(owner_out, _pin(rot, "self"))
    _set(rot, "InLifespan", CORPSE_SECONDS)
    for tail in (then(lobotomy), else_(has_brain), out(as_pawn, "CastFailed")):
        _connect(tail, _pin(rot, "execute"))

    ed.add_comment_to_nodes(
        f"A dead wanderer: give its AI controller {CONTROLLER_RETIRE_SECONDS} s "
        f"of lifespan (K2_DestroyActor on a controller is a no-op in the "
        f"engine; an expiring lifespan really destroys it) and the body "
        f"{CORPSE_SECONDS:.0f} s. "
        f"The kill has already been counted by the time this runs; the "
        f"replacement comes later (replacement.py), off this same component, "
        f"which is why the body has to outlast the respawn delay.",
        [owner, as_pawn, brain, possessed, has_brain, lobotomy, rot])
    return then(rot)


def _author_player_death(ed, exec_ins):
    """The player is down: wait for the fall, then pause and open the menu.

    This is the DespawnOnDeath-false arm, and it now starts from a body that is
    already a ragdoll -- so there is nothing here that has to keep it down. The
    bug this used to have was the opposite one: a dynamic montage of
    MM_Death_Front_01 blended OUT after 1.1 s, the locomotion state machine
    underneath took the pose back, and the player was on his feet a whole
    second before the pause arrived to freeze him there.

    The Delay is still here and still comes before the pause, for the reason it
    always did -- pausing stops physics as well as everything else, so pausing
    early freezes the body mid-topple.

    PlayerDead is set on the GameMode rather than here because the HUD is what
    draws the menu and the HUD has no route to this component -- it would have
    to find the player's pawn, find this component and cast to it, every frame,
    to read one bool that the GameMode already exists to hold.
    """
    wait = _node(ed, FN_DELAY)
    _set(wait, "Duration", DEATH_PAUSE_SECONDS)
    for tail in exec_ins:
        _connect(tail, _pin(wait, "execute"))

    mode = _node(ed, FN_GET_GAME_MODE)
    as_mode = _palette(ed, NODE_CAST_GAME_MODE)
    _connect(out(mode), _pin(as_mode, "Object"))
    _connect(then(wait), _pin(as_mode, "execute"))
    tell = ed.add_set_member_variable_node(PLAYER_DEAD_VAR, GAME_MODE_CLASS_PATH)
    _connect(_loose_pin(as_mode, "AsBPThirdPersonGameMode", is_input=False),
             _pin(tell, "self"))
    _set(tell, PLAYER_DEAD_VAR, "true")
    _connect(then(as_mode), _pin(tell, "execute"))

    # Say so in the log, with the score. A paused game and a game where the
    # death path silently did nothing look exactly the same from outside, and
    # the menu that would tell them apart is drawn on a canvas that a headless
    # run has nobody looking at.
    score = ed.add_get_member_variable_node(KILL_COUNT_VAR, GAME_MODE_CLASS_PATH)
    _connect(_loose_pin(as_mode, "AsBPThirdPersonGameMode", is_input=False),
             _pin(score, "self"))
    score_str = _node(ed, FN_INT_TO_STR)
    _connect(out(score, KILL_COUNT_VAR), _pin(score_str, "InInt"))
    dead_line = _node(ed, FN_CONCAT)
    _set(dead_line, "A", DEAD_LOG_PREFIX)
    _connect(out(score_str), _pin(dead_line, "B"))
    say_dead = _node(ed, FN_PRINT)
    _connect(out(dead_line), _pin(say_dead, "InString"))
    # Log only: the menu is what says it on screen, and it says it better.
    _set(say_dead, "bPrintToScreen", "false")
    _set(say_dead, "bPrintToLog", "true")
    _set(say_dead, "Duration", 0.0)
    _connect(then(tell), _pin(say_dead, "execute"))

    # Pause last, and on every arm: with the flag set the HUD draws the menu,
    # and with the game paused nothing moves behind it. The HUD polls its
    # restart key from the PlayerController, which ticks through a pause.
    freeze = _node(ed, FN_SET_PAUSED)
    _set(freeze, "bPaused", "true")
    for tail in (then(say_dead), out(as_mode, "CastFailed")):
        _connect(tail, _pin(freeze, "execute"))

    ed.add_comment_to_nodes(
        f"The player's death, from a body that is already on the floor: wait "
        f"{DEATH_PAUSE_SECONDS}s for the ragdoll to settle, tell the GameMode "
        f"and pause. The pause stops physics too, so the body stays exactly as "
        f"it fell until the level reopens -- which is the fix for the player "
        f"standing back up. BP_GraphicsMenuHUD draws the menu off "
        f"{PLAYER_DEAD_VAR} and restarts the level from it.",
        [wait, mode, as_mode, tell, score, score_str, dead_line, say_dead, freeze])
