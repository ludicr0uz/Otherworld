"""The guard and the use key as the server knows them (task M20;
combat/strike_vars.py has the picture).

Both are keys held, read where the keys are: block.py writes Blocking and
torch.py FireWard on the owning machine's copy, every frame. But the rules
that read them run on the server: a wanderer's swing asks the player's
Blocking (npc/block.py), a wendigo the player's FireWard (npc/ward.py). So the
owning machine reports the two keys, and the server decides each from its own
copy:

    owning machine   Blocking or Using changed --> Server_SetHolds(Blocking,
                     Using), reliable, on that frame alone
    server           AskGuard, AskUse = what it was told
    the server's     Blocking = AskGuard AND the movement's own stamina > 0
    copy, each Tick              AND not sprinting   (the server's stamina: a
                                 client cannot guard on an empty bar)
                     FireWard = AskUse AND IsValid(Held) AND Held.Lit   (the
                                 server's stick: a client cannot ward with
                                 one that is not burning there)

Blocking replicates to everyone but the owner, so another player's copy poses
the guard (pose_weights.py reads it on every copy). FireWard goes nowhere: only
the server's wanderers read it, and the stick held out is seen as its pose
(LookPose, look.py).

In single player the one machine is the owner's: the keys write both, the
event is a local call that writes two variables nothing reads, and the mirror
never runs.
"""

import unreal

from combat.paths import FIRE_WARD_VAR, ITEM_CLASS_PATH
from combat.strike_vars import (
    GUARD_PARAM, HOLDS_PARAMS, SERVER_SET_HOLDS, USE_PARAM, AskGuard, AskUse, SentGuard,
    SentUse)
from combat.torch_tuning import LIT_VAR
from combat.use_tuning import USING_VAR
from combat.weapon_component import vars as WV
from combat.weapon_component.record import authority
from combat.weapon_component.slot_nodes import not_, op, valid
from net.guard import author_guard
from uebp import net
from uebp.g import _G
from uebp.graph import _connect, _node, _pin, out, then
from uebp.nodes.math import FN_AND, FN_GREATER_FF, FN_NEQ_BB, FN_OR
from uebp.nodes.move import FN_GET_STAMINA, FN_IS_SPRINTING


def replicate_holds(bp):
    """After every declare, which drops the flags (uebp/CLAUDE.md)."""
    net.replicate(bp, WV.Blocking, unreal.LifetimeCondition.COND_SKIP_OWNER)


def author_set_holds(ed):
    """The Server event: keep what the owning client reports."""
    g = _G(ed)
    event = g.keep(net.server_event(ed, SERVER_SET_HOLDS, HOLDS_PARAMS))
    go, _refused = author_guard(g, SERVER_SET_HOLDS, [then(event)])
    tail = g.put(AskGuard, out(event, GUARD_PARAM), [go])
    g.put(AskUse, out(event, USE_PARAM), [tail])
    ed.add_comment_to_nodes(
        f"{SERVER_SET_HOLDS} (holds.py): the owning client says whether it holds "
        "its guard up and its use key down. The server keeps both and decides "
        "Blocking and FireWard on its own copy, each Tick, from them and from its "
        "own stamina and its own item in hand.", g.made)


def _author_holds_report(ed, exec_ins):
    """On the owning machine, once Blocking and Using are written: report them
    on the frame either changes. Returns the exec pins to carry on from."""
    g = _G(ed)
    changed = op(g, FN_OR,
                 op(g, FN_NEQ_BB, g.get(WV.Blocking), g.get(SentGuard)),
                 op(g, FN_NEQ_BB, g.get(USING_VAR), g.get(SentUse)))
    new, same = g.branch(changed, exec_ins)
    tail = g.put(SentGuard, g.get(WV.Blocking), [new])
    tail = g.put(SentUse, g.get(USING_VAR), [tail])
    send = g.keep(_node(ed, SERVER_SET_HOLDS))
    _connect(g.get(SentGuard), _pin(send, GUARD_PARAM))
    _connect(g.get(SentUse), _pin(send, USE_PARAM))
    _connect(tail, _pin(send, "execute"))
    ed.add_comment_to_nodes(
        "The guard and the use key, reported (holds.py): on the frame Blocking or "
        f"Using changes, the owning machine tells the server ({SERVER_SET_HOLDS}). "
        "In single player the call is local and nothing reads what it writes.",
        g.made)
    return (then(send), same)


def _author_holds_mirror(ed, owner_out, exec_ins):
    """On a copy that is not the local player's: the server writes Blocking
    and FireWard from what it was told and its own state; another client's
    copy has Blocking by replication and needs no FireWard. Returns the exec
    pins to carry on from."""
    g = _G(ed, ITEM_CLASS_PATH)
    owns, other = g.branch(authority(g), exec_ins)
    left = op(g, FN_GREATER_FF, out(g.call(FN_GET_STAMINA, Character=owner_out)), "0.0")
    able = op(g, FN_AND, left, not_(g, out(g.call(FN_IS_SPRINTING, Character=owner_out))))
    tail = g.put(WV.Blocking, op(g, FN_AND, g.get(AskGuard), able), [owns])
    # Held's flag behind its own Branches: the hand may be empty.
    asked, idle = g.branch(g.get(AskUse), [tail])
    held = g.get(WV.Held)
    armed, empty = g.branch(valid(g, held), [asked])
    ward = g.put(FIRE_WARD_VAR, g.iget(held, LIT_VAR), [armed])
    down = g.put(FIRE_WARD_VAR, "false", [idle, empty])
    ed.add_comment_to_nodes(
        "The guard and the fire held out, on the server's copy of a client's "
        "character (holds.py): Blocking is what the client asked for while the "
        "server's own stamina lasts and it is not sprinting; FireWard is the use "
        "key asked for with a Lit item in the server's hand. A wanderer's swing "
        "and a wendigo read these, never a client's own.", g.made)
    return (ward, down, other)
