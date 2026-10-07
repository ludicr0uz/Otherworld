"""The use key on a hot blade: it cauterises the wound.

One of use.py's kinds. A press of the use key with a Hot item in hand (a
knife or an axe heated at a campfire: heat.py) takes the bleeding off the
player:

    UsePressed --> Held.Hot --> Server_Cauterize()

    Server_Cauterize, a reliable Server event (task M25, combat/fire_vars.py;
    in single player a plain call). Alive, and this machine's Held is Hot:
        the owner's ability system is valid
        --> RemoveActiveEffectsWithGrantedTags(Debuff.Bleeding)

The bleed is an effect on the server's ability system (survival/on_hit.py
rolls it there), and Hot the server's item's: a client that only says its
blade is hot seals nothing.

The bleed is survival's GameplayEffect (survival/on_hit.py), built after this
graph, so it is named by the tag its spec grants (combat.tuning.BLEEDING_TAG),
as the health drain names it (debuff_drain.py), not by its class. The engine's
query reads the tags a spec was given as well as its effect's own, which is
where this one's are. With no bleed the call removes nothing, so there is no
test for one: a press on a player who is not bleeding does nothing.

The blade stays hot: the press does not spend its heat. Held.Hot is read
behind the Branch on UsePressed, which is false with empty hands (use.py).
"""

from uebp import net
from uebp.g import _G
from uebp.graph import _connect, _node, _pin, _set, else_, out, then
from combat.fire_vars import SERVER_CAUTERIZE
from combat.heat_tuning import HOT_VAR
from combat.paths import ITEM_CLASS_PATH
from combat.tuning import BLEEDING_TAG
from combat.use_tuning import USE_PRESSED_VAR
from combat.weapon_component import vars as WV
from combat.weapon_component.common import _prop
from combat.weapon_component.shot import _author_alive
from combat.weapon_component.slot_nodes import valid
from uebp.nodes.actor import FN_GET_OWNER
from uebp.nodes.gas import FN_GET_ASC, FN_REMOVE_GRANTING

# The tag container's literal, as the pin stores it.
CAUTERIZE_TAGS = f'(GameplayTags=((TagName="{BLEEDING_TAG}")))'


def _author_cauterize(ed, held, owner, exec_ins):
    """See the module docstring. Returns the exits."""
    made = []

    def keep(n):
        made.append(n)
        return n

    pressed_n = keep(ed.add_get_member_variable_node(USE_PRESSED_VAR))
    press = keep(ed.add_branch_node())
    _connect(out(pressed_n, USE_PRESSED_VAR), _pin(press, "Condition"))
    for e in exec_ins:
        _connect(e, _pin(press, "execute"))
    hot_pin, hot_n = _prop(ed, HOT_VAR, held)
    keep(hot_n)
    hot = keep(ed.add_branch_node())
    _connect(hot_pin, _pin(hot, "Condition"))
    _connect(then(press), _pin(hot, "execute"))

    ask = keep(_node(ed, SERVER_CAUTERIZE))
    _connect(then(hot), _pin(ask, "execute"))

    ed.add_comment_to_nodes(
        "The use key on a hot blade (cauterize.py): a press asks the server to "
        f"cauterise ({SERVER_CAUTERIZE}). The blade stays hot.",
        made)
    return (else_(press), else_(hot), then(ask))


def author_cauterize_event(ed):
    """Server_Cauterize(): the press, on the machine that owns the wound.
    Refused unless the owner is alive and its own Held is there and Hot; then
    every effect granting the bleeding tag comes off its ability system.
    Before the Tick, which calls it by name."""
    g = _G(ed, ITEM_CLASS_PATH)
    event = g.keep(net.server_event(ed, SERVER_CAUTERIZE))
    alive = _author_alive(g, [then(event)])
    held = g.get(WV.Held)
    armed, _bare = g.branch(valid(g, held), alive)
    hot, _cold = g.branch(g.iget(held, HOT_VAR), [armed])
    asc = out(g.call(FN_GET_ASC, Actor=out(g.call(FN_GET_OWNER))))
    able, _none = g.branch(valid(g, asc), [hot])
    seal = g.call(FN_REMOVE_GRANTING, [able], self=asc)
    _set(seal, "Tags", CAUTERIZE_TAGS)
    ed.add_comment_to_nodes(
        f"{SERVER_CAUTERIZE} (cauterize.py): the owning client's use key on a hot "
        "blade. Refused unless the owner is alive and this machine's Held is "
        f"{HOT_VAR}; then every effect granting {BLEEDING_TAG} comes off the "
        "owner's ability system, which is the server's.", g.made)
