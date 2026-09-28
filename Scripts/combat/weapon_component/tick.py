"""The weapon component's Tick: polls every key and calls into the
aim/fire/inventory/sprint/recoil/ammo fragments in order.
"""

from combat.graph import BEL, _at, _connect, _node, _pin, _set
from combat.nodes import (
    FN_ADD_II, FN_AND, FN_ARR_LEN, FN_GET_OWNER, FN_GET_PC, FN_GE_FF,
    FN_GREATER_II, FN_IS_KEY_DOWN, FN_IS_VALID, FN_LESS_II, FN_MOD_II,
    FN_NEQ_BB, FN_NOT, FN_OR, FN_TIME_SECONDS, FN_WAS_PRESSED,
)
from combat.tuning import BIND_VARS, SWITCH_KEY
from combat.weapon_component.aim import _author_ads, _author_resolve_aim
from combat.weapon_component.ammo import _author_dry_fire, _author_reload
from combat.weapon_component.common import _prop
from combat.weapon_component.firing import _author_fire
from combat.weapon_component.inventory import (
    _author_drop, _author_equip, _author_pickup,
)
from combat.weapon_component.ready_pose import _author_ready_pose_keepalive
from combat.weapon_component.recoil import (
    _author_recoil_kick, _author_recoil_recovery,
)
from combat.weapon_component.sprint import _author_sprint


def _author_wc_tick(ed, tick):
    """Five polled keys and a refresh, chained so each block rejoins the next.

    There is no Sequence node here: an exec *input* accepts any number of links,
    so every block's exit and its guard branch's False pin both run into the
    next guard. That keeps the chain flat and means a block can be inserted or
    removed without re-fanning a Sequence's pins.

    Refresh runs last so a switch, drop or pick-up earlier in the same frame is
    already applied when it does.
    """
    pc = _at(_node(ed, FN_GET_PC), 240, 260)
    _set(pc, "PlayerIndex", 0)
    pc_out = _pin(pc, "ReturnValue", is_input=False)

    owner = _at(_node(ed, FN_GET_OWNER), 240, 400)
    owner_out = _pin(owner, "ReturnValue", is_input=False)

    held_get = _at(ed.add_get_member_variable_node("Held"), 240, 520)
    held = _pin(held_get, "Held", is_input=False)
    armed = _at(_node(ed, FN_IS_VALID), 480, 520)
    _connect(held, _pin(armed, "Object"))
    armed_out = _pin(armed, "ReturnValue", is_input=False)

    # One Get per bind, reused by every poll below -- an output pin takes any
    # number of links. The Key pins are DRIVEN rather than set to a literal,
    # which is the whole of rebinding: the HUD writes these variables each
    # frame from the player's save, and a literal cannot be written to.
    key_pins = {}
    for i, (name, _default) in enumerate(BIND_VARS):
        getter = _at(ed.add_get_member_variable_node(name), -40, 260 + i * 120)
        key_pins[name] = _pin(getter, name, is_input=False)

    def pressed(var, y):
        n = _at(_node(ed, FN_WAS_PRESSED), 480, y)
        _connect(pc_out, _pin(n, "self"))
        _connect(key_pins[var], _pin(n, "Key"))
        return _pin(n, "ReturnValue", is_input=False)

    def both(a, b, y):
        n = _at(_node(ed, FN_AND), 760, y)
        _connect(a, _pin(n, "A"))
        _connect(b, _pin(n, "B"))
        return _pin(n, "ReturnValue", is_input=False)

    # --- aim -----------------------------------------------------------------
    # First, and unconditionally: the reticle has to be right on the frames
    # where nothing is fired, which is nearly all of them. It also leaves
    # AimPoint and the muzzle position sitting there for the fire block to use.
    # --- recoil recovery -----------------------------------------------------
    # First of all, because it moves the view: the aim trace below has to be
    # taken after this frame's give-back rather than one frame behind it.
    recoil_exits = _author_recoil_recovery(ed, tick, pc_out,
                                           BEL.find_then_pin(tick), 1040, -3600)

    aim_exits, muzzle = _author_resolve_aim(ed, held, recoil_exits,
                                            1040, -2400)

    # --- sprint --------------------------------------------------------------
    # Before the trigger, because the trigger reads Sprinting: polled in the
    # other order, a shot would be allowed on the frame the sprint started.
    sprint_exits = _author_sprint(ed, tick, pc_out, owner_out,
                                  key_pins["KeySprint"], aim_exits,
                                  1040, -1400)

    # --- aim down the sights -------------------------------------------------
    # After the sprint block, which writes Sprinting, and before the trigger,
    # which the cone width now depends on: polled in any other order the zoom
    # and the spread would disagree by a frame.
    ads_exits = _author_ads(ed, tick, pc_out, owner_out, held, armed_out,
                            key_pins["KeyAim"], sprint_exits, 1040, -700)

    # --- the pose follows the sprint -----------------------------------------
    # Edge-triggered, not level-triggered, and that distinction is the whole
    # block. Re-equipping costs a detach, an attach and a montage restart; done
    # every frame the player holds Shift it would restart the run's ready pose
    # sixty times a second, which is a weapon that flickers. PoseSprinting is
    # what the pose currently reflects, Sprinting is what it should reflect,
    # and only the frames where those disagree do any work.
    now_sprint = _at(ed.add_get_member_variable_node("Sprinting"), 240, 1020)
    now_sprint_out = _pin(now_sprint, "Sprinting", is_input=False)
    posed = _at(ed.add_get_member_variable_node("PoseSprinting"), 240, 1140)
    changed = _at(_node(ed, FN_NEQ_BB), 520, 1060)
    _connect(now_sprint_out, _pin(changed, "A"))
    _connect(_pin(posed, "PoseSprinting", is_input=False), _pin(changed, "B"))
    pose_gate = _at(ed.add_branch_node(), 780, 940)
    _connect(_pin(changed, "ReturnValue", is_input=False), _pin(pose_gate, "Condition"))
    for exit_pin in ads_exits:
        _connect(exit_pin, _pin(pose_gate, "execute"))
    remember = _at(ed.add_set_member_variable_node("PoseSprinting"), 1040, 940)
    _connect(now_sprint_out, _pin(remember, "PoseSprinting"))
    _connect(BEL.find_then_pin(pose_gate), _pin(remember, "execute"))
    pose_dirty = _at(ed.add_set_member_variable_node("NeedsRefresh"), 1300, 940)
    _set(pose_dirty, "NeedsRefresh", "true")
    _connect(BEL.find_then_pin(remember), _pin(pose_dirty, "execute"))
    pose_exits = (BEL.find_then_pin(pose_dirty), BEL.find_else_pin(pose_gate))

    # --- and the pose survives being shot ------------------------------------
    # After the sprint edge, because that block is what starts and stops the
    # pose deliberately, and this one only restores what something else took
    # away. See _author_ready_pose_keepalive: a hit reaction stops the ready
    # pose as a side effect of the montage group, and without this the player
    # fights the rest of the session with the gun in the locomotion pose.
    pose_exits = _author_ready_pose_keepalive(ed, held, pose_exits, 240, 1400)

    ed.add_comment_to_nodes(
        "Started or stopped sprinting this frame -- re-equip, which is what "
        "starts or stops the ready pose. Edge-triggered on PoseSprinting: the "
        "level-triggered version restarts the montage every frame Shift is "
        "held, and the weapon strobes.",
        [now_sprint, posed, changed, pose_gate, remember, pose_dirty])

    # --- fire ----------------------------------------------------------------
    # Three conditions, and "not sprinting" is the new one: the weapon is being
    # used to run with, not to aim with. Note this AND is safe to fold together
    # -- every input is a plain bool read, with no chain behind it that could be
    # pulled by the half that should not have run (unlike the NPC melee gate).
    #
    # The trigger is polled BOTH ways, and the two are OR'd here rather than
    # chosen between. Which one a given weapon honours is settled further in,
    # behind this gate, because the answer is a property of Held -- and this
    # condition is evaluated on every frame, including the frames where nothing
    # is equipped. Reading Automatic here would be an Accessed None per frame
    # for as long as the player's hands are empty.
    #
    # So the outer gate asks the question that is answerable without a weapon:
    # is the player touching the trigger at all? A tap is also a hold on the
    # frame it happens, so the OR is not strictly necessary for the automatics
    # -- it is there so that a semi-automatic still opens the gate on the tap
    # frame even if IsInputKeyDown were ever to disagree, and so that the two
    # reads that actually decide are the same two pins the weapon is asked
    # about below.
    steady = _at(_node(ed, FN_NOT), 760, 760)
    _connect(_pin(_at(ed.add_get_member_variable_node("Sprinting"), 480, 760),
                  "Sprinting", is_input=False), _pin(steady, "A"))

    tap = pressed("KeyFire", 600)
    holding = _at(_node(ed, FN_IS_KEY_DOWN), 480, 860)
    _connect(pc_out, _pin(holding, "self"))
    _connect(key_pins["KeyFire"], _pin(holding, "Key"))
    holding_out = _pin(holding, "ReturnValue", is_input=False)
    touching = _at(_node(ed, FN_OR), 760, 580)
    _connect(tap, _pin(touching, "A"))
    _connect(holding_out, _pin(touching, "B"))

    fire_gate = _at(ed.add_branch_node(), 1040, 0)
    _connect(both(both(_pin(touching, "ReturnValue", is_input=False),
                       armed_out, 640),
                  _pin(steady, "ReturnValue", is_input=False), 700),
             _pin(fire_gate, "Condition"))
    for exit_pin in pose_exits:
        _connect(exit_pin, _pin(fire_gate, "execute"))

    # Ammunition and the cooldown are a SECOND branch inside the first, not two
    # more terms folded into its condition, and that nesting is the whole
    # reason this reads the way it does. Both tests have to read properties off
    # Held, and the condition of the outer gate is pulled on every frame --
    # including the frames where nothing is equipped at all. A pure Get with a
    # null self is an "Accessed None" per frame forever. Behind the gate, Held
    # has already been checked valid.
    loaded, loaded_n = _prop(ed, "Loaded", held, 1240, 300)
    rounds = _at(_node(ed, FN_GREATER_II), 1480, 300)
    _connect(loaded, _pin(rounds, "A"))
    _set(rounds, "B", 0)
    limited, limited_n = _prop(ed, "UsesAmmo", held, 1240, 420)
    unlimited = _at(_node(ed, FN_NOT), 1480, 420)
    _connect(limited, _pin(unlimited, "A"))
    # OR, so the pistol never consults a magazine it does not have.
    has_ammo = _at(_node(ed, FN_OR), 1720, 360)
    _connect(_pin(unlimited, "ReturnValue", is_input=False), _pin(has_ammo, "A"))
    _connect(_pin(rounds, "ReturnValue", is_input=False), _pin(has_ammo, "B"))

    when, when_n = _prop(ed, "NextFireTime", held, 1240, 560)
    right_now = _at(_node(ed, FN_TIME_SECONDS), 1240, 680)
    cooled = _at(_node(ed, FN_GE_FF), 1480, 560)
    _connect(_pin(right_now, "ReturnValue", is_input=False), _pin(cooled, "A"))
    _connect(when, _pin(cooled, "B"))

    # Held trigger, or tapped trigger? Now that Held is known valid, the
    # weapon can be asked. An automatic accepts either; everything else
    # accepts only the tap, which is what makes one click one shot on the
    # shotgun even though the button is still down on the following frame.
    auto_pin, auto_n = _prop(ed, "Automatic", held, 1240, 820)
    spraying = _at(_node(ed, FN_AND), 1480, 820)
    _connect(holding_out, _pin(spraying, "A"))
    _connect(auto_pin, _pin(spraying, "B"))
    trigger = _at(_node(ed, FN_OR), 1720, 760)
    _connect(tap, _pin(trigger, "A"))
    _connect(_pin(spraying, "ReturnValue", is_input=False), _pin(trigger, "B"))
    trigger_out = _pin(trigger, "ReturnValue", is_input=False)

    ready = _at(_node(ed, FN_AND), 1960, 420)
    _connect(_pin(has_ammo, "ReturnValue", is_input=False), _pin(ready, "A"))
    _connect(_pin(cooled, "ReturnValue", is_input=False), _pin(ready, "B"))
    allowed = _at(_node(ed, FN_AND), 1960, 600)
    _connect(_pin(ready, "ReturnValue", is_input=False), _pin(allowed, "A"))
    _connect(trigger_out, _pin(allowed, "B"))
    ready_gate = _at(ed.add_branch_node(), 2200, 0)
    _connect(_pin(allowed, "ReturnValue", is_input=False),
             _pin(ready_gate, "Condition"))
    _connect(BEL.find_then_pin(fire_gate), _pin(ready_gate, "execute"))

    ed.add_comment_to_nodes(
        "The trigger is being touched, the weapon is out and the player is not "
        "sprinting -- now, can it actually fire? A weapon with no ammunition "
        "rule passes on the first half; every weapon waits out its own "
        "FireInterval on the second; and an automatic is the only kind that "
        "counts a held button as a pull. Nested inside the first gate rather "
        "than folded into it, because every one of these reads a property off "
        "Held.",
        [loaded_n, rounds, limited_n, unlimited, has_ammo, when_n, right_now,
         cooled, auto_n, spraying, trigger, ready, allowed, ready_gate])

    # The kick lands before the round is spent, which costs nothing and reads
    # in the right order. It cannot bend the shot that caused it: the pellets
    # fly down the AimPoint resolved at the top of this frame.
    kicked = _author_recoil_kick(ed, held, pc_out,
                                 BEL.find_then_pin(ready_gate), 6800, -1400)
    after_fire = _author_fire(ed, held, muzzle, kicked, 2700, 0)

    # --- the click, when the gate said no ------------------------------------
    dry_exits = _author_dry_fire(
        ed, held, muzzle,
        _pin(has_ammo, "ReturnValue", is_input=False),
        _pin(cooled, "ReturnValue", is_input=False), tap,
        BEL.find_else_pin(ready_gate), 2200, 1100)

    # --- reload --------------------------------------------------------------
    # Shares its key with the death menu's "try again", and that is safe rather
    # than lucky: Event Tick does not run while the game is paused, so this
    # graph is not listening on any frame the menu is on screen. (The HUD's
    # DrawHUD is; it is renderer-driven, which is why the menu can poll a key at
    # all.)
    reload_gate = _at(ed.add_branch_node(), 1040, 7200)
    _connect(both(pressed("KeyReload", 7360), armed_out, 7300),
             _pin(reload_gate, "Condition"))
    for exit_pin in (after_fire, BEL.find_else_pin(fire_gate)) + dry_exits:
        _connect(exit_pin, _pin(reload_gate, "execute"))
    reload_exits = _author_reload(ed, held, BEL.find_then_pin(reload_gate),
                                  1400, 7200)

    # --- switch --------------------------------------------------------------
    switch_gate = _at(ed.add_branch_node(), 1040, 1400)
    inv = _at(ed.add_get_member_variable_node("Inventory"), 240, 1560)
    count = _at(_node(ed, FN_ARR_LEN), 480, 1560)
    _connect(_pin(inv, "Inventory", is_input=False), _pin(count, "TargetArray"))
    count_out = _pin(count, "ReturnValue", is_input=False)
    any_held = _at(_node(ed, FN_LESS_II), 760, 1680)
    _set(any_held, "A", 0)
    _connect(count_out, _pin(any_held, "B"))
    _connect(both(pressed("KeySwitch", 1560), _pin(any_held, "ReturnValue", is_input=False),
                  1620), _pin(switch_gate, "Condition"))
    for exit_pin in reload_exits + (BEL.find_else_pin(reload_gate),):
        _connect(exit_pin, _pin(switch_gate, "execute"))

    idx = _at(ed.add_get_member_variable_node("EquippedIndex"), 1300, 1600)
    step = _at(_node(ed, FN_ADD_II), 1540, 1600)
    _connect(_pin(idx, "EquippedIndex", is_input=False), _pin(step, "A"))
    _set(step, "B", 1)
    wrap = _at(_node(ed, FN_MOD_II), 1780, 1600)
    _connect(_pin(step, "ReturnValue", is_input=False), _pin(wrap, "A"))
    _connect(count_out, _pin(wrap, "B"))
    to = _at(ed.add_set_member_variable_node("EquippedIndex"), 2020, 1400)
    _connect(_pin(wrap, "ReturnValue", is_input=False), _pin(to, "EquippedIndex"))
    _connect(BEL.find_then_pin(switch_gate), _pin(to, "execute"))
    switch_dirty = _at(ed.add_set_member_variable_node("NeedsRefresh"), 2280, 1400)
    _set(switch_dirty, "NeedsRefresh", "true")
    _connect(BEL.find_then_pin(to), _pin(switch_dirty, "execute"))

    ed.add_comment_to_nodes(
        f"{SWITCH_KEY} cycles: (index + 1) mod count, so it wraps and works for "
        "any number of carried weapons. 1/2/3 and M would have been the obvious "
        "keys but they already belong to the graphics menu.",
        [inv, count, any_held, idx, step, wrap, to, switch_dirty, switch_gate])

    # --- drop ----------------------------------------------------------------
    drop_gate = _at(ed.add_branch_node(), 1040, 2200)
    _connect(both(pressed("KeyDrop", 2360), armed_out, 2300), _pin(drop_gate, "Condition"))
    _connect(BEL.find_then_pin(switch_dirty), _pin(drop_gate, "execute"))
    _connect(BEL.find_else_pin(switch_gate), _pin(drop_gate, "execute"))
    after_drop = _author_drop(ed, held, owner_out, BEL.find_then_pin(drop_gate),
                              1400, 2200)
    drop_dirty = _at(ed.add_set_member_variable_node("NeedsRefresh"), 4700, 2200)
    _set(drop_dirty, "NeedsRefresh", "true")
    _connect(after_drop, _pin(drop_dirty, "execute"))

    # --- pick up -------------------------------------------------------------
    pick_gate = _at(ed.add_branch_node(), 1040, 3400)
    _connect(pressed("KeyPickup", 3560), _pin(pick_gate, "Condition"))
    _connect(BEL.find_then_pin(drop_dirty), _pin(pick_gate, "execute"))
    _connect(BEL.find_else_pin(drop_gate), _pin(pick_gate, "execute"))
    after_pick = _author_pickup(ed, owner_out, BEL.find_then_pin(pick_gate),
                                1400, 3400)
    pick_dirty = _at(ed.add_set_member_variable_node("NeedsRefresh"), 4900, 3400)
    _set(pick_dirty, "NeedsRefresh", "true")
    _connect(after_pick, _pin(pick_dirty, "execute"))

    # --- refresh -------------------------------------------------------------
    dirty_get = _at(ed.add_get_member_variable_node("NeedsRefresh"), 1040, 4760)
    refresh_gate = _at(ed.add_branch_node(), 1300, 4600)
    _connect(_pin(dirty_get, "NeedsRefresh", is_input=False),
             _pin(refresh_gate, "Condition"))
    _connect(BEL.find_then_pin(pick_dirty), _pin(refresh_gate, "execute"))
    _connect(BEL.find_else_pin(pick_gate), _pin(refresh_gate, "execute"))
    settle = _at(ed.add_set_member_variable_node("NeedsRefresh"), 1560, 4600)
    _set(settle, "NeedsRefresh", "false")
    _connect(BEL.find_then_pin(refresh_gate), _pin(settle, "execute"))
    _author_equip(ed, BEL.find_then_pin(settle), 1900, 4600)
