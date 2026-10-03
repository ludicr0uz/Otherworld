"""The use key on a hot blade: it cauterises the wound.

One of use.py's kinds. A press of the use key with a Hot item in hand (a
knife or an axe heated at a campfire: heat.py) takes the bleeding off the
player:

    UsePressed --> Held.Hot --> the owner's ability system is valid
        --> RemoveActiveEffectsWithGrantedTags(Debuff.Bleeding)

The bleed is survival's GameplayEffect (survival/on_hit.py), built after this
graph, so it is named by the tag its spec grants (combat.tuning.BLEEDING_TAG),
as the health drain names it (debuff_drain.py), not by its class. The engine's
query reads the tags a spec was given as well as its effect's own, which is
where this one's are. With no bleed the call removes nothing, so there is no
test for one: a press on a player who is not bleeding does nothing.

The blade stays hot: the press does not spend its heat. Held.Hot is read
behind the Branch on UsePressed, which is false with empty hands (use.py).
"""

from uebp.graph import _connect, _node, _pin, _set, else_, out, then
from combat.heat_tuning import HOT_VAR
from combat.nodes import FN_GET_ASC, FN_IS_VALID, GAS
from combat.tuning import BLEEDING_TAG
from combat.use_tuning import USE_PRESSED_VAR
from combat.weapon_component.common import _prop

FN_REMOVE_GRANTING = f"{GAS}.AbilitySystemComponent.RemoveActiveEffectsWithGrantedTags"
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

    lookup = keep(_node(ed, FN_GET_ASC))
    _connect(owner, _pin(lookup, "Actor"))
    asc = out(lookup)
    valid = keep(_node(ed, FN_IS_VALID))
    _connect(asc, _pin(valid, "Object"))
    able = keep(ed.add_branch_node())
    _connect(out(valid), _pin(able, "Condition"))
    _connect(then(hot), _pin(able, "execute"))
    seal = keep(_node(ed, FN_REMOVE_GRANTING))
    _connect(asc, _pin(seal, "self"))
    _set(seal, "Tags", CAUTERIZE_TAGS)
    _connect(then(able), _pin(seal, "execute"))

    ed.add_comment_to_nodes(
        "The use key on a hot blade (cauterize.py): a press takes every "
        f"effect granting {BLEEDING_TAG} off the player. The blade stays hot.",
        made)
    return (else_(press), else_(hot), else_(able), then(seal))
