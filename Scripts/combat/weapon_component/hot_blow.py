"""What a blow takes: the strike's damage, or more of it off a creature afraid
of fire when the blade in hand is hot.

The blow's `damage` fragment (punch._author_blow), run once the sweep has met
a body with health and before that health is written:

    BlowDamage = the strike's damage
    IsValid(Held) --> Held.Hot --> the body carries FIRE_FEAR_TAG
        --> BlowDamage = the strike's damage x HOT_BLOW_SCALE

BlowDamage is a variable because the answer hangs on Held, which may be read
only behind its own IsValid Branch: the blow lands a moment after the press,
and the hands may be empty by then. Three nested Branches, not one folded
condition, for the same reason. Who is afraid of fire is the creature's own
business: its Blueprint carries the actor tag (npc/character.py, for the
creatures of forest_generator/npc_ward.NPC_WARD_FEARS: the wendigo), and this
only reads it, so a zombie takes a hot blade as it takes a cold one.
"""

from uebp.graph import _connect, _node, _pin, _set, else_, out, then
from combat.heat_tuning import (
    BLOW_DAMAGE_VAR, FIRE_FEAR_TAG, HOT_BLOW_SCALE, HOT_VAR,
)
from combat.weapon_component.common import _prop
from uebp.nodes.actor import FN_HAS_TAG
from uebp.nodes.system import FN_IS_VALID
from combat.weapon_component import vars as WV


def author_hot_blow(strike):
    """The `damage` fragment for ``strike``: ``(ed, body, exec_in) ->
    (the damage's pin, the exits)``, ``body`` being the actor the sweep met."""
    def _author(ed, body, exec_in):
        made = []

        def keep(n):
            made.append(n)
            return n

        def put(value):
            n = keep(ed.add_set_member_variable_node(BLOW_DAMAGE_VAR))
            _set(n, BLOW_DAMAGE_VAR, value)
            return n

        plain = put(strike.damage)
        _connect(exec_in, _pin(plain, "execute"))

        held_n = keep(ed.add_get_member_variable_node(WV.Held))
        held = out(held_n, WV.Held)
        armed = keep(_node(ed, FN_IS_VALID))
        _connect(held, _pin(armed, "Object"))
        gate = keep(ed.add_branch_node())
        _connect(out(armed), _pin(gate, "Condition"))
        _connect(then(plain), _pin(gate, "execute"))
        hot_pin, hot_n = _prop(ed, HOT_VAR, held)
        keep(hot_n)
        hot = keep(ed.add_branch_node())
        _connect(hot_pin, _pin(hot, "Condition"))
        _connect(then(gate), _pin(hot, "execute"))
        fears = keep(_node(ed, FN_HAS_TAG))
        _connect(body, _pin(fears, "self"))
        _set(fears, "Tag", FIRE_FEAR_TAG)
        burns = keep(ed.add_branch_node())
        _connect(out(fears), _pin(burns, "Condition"))
        _connect(then(hot), _pin(burns, "execute"))
        seared = put(strike.damage * HOT_BLOW_SCALE)
        _connect(then(burns), _pin(seared, "execute"))

        amount = keep(ed.add_get_member_variable_node(BLOW_DAMAGE_VAR))
        ed.add_comment_to_nodes(
            f"What the {strike.name}'s blow takes ({BLOW_DAMAGE_VAR}, "
            f"hot_blow.py): {strike.damage:g} HP, or {HOT_BLOW_SCALE:g} times "
            f"that with a hot blade in hand off a body tagged {FIRE_FEAR_TAG} "
            "(a creature afraid of fire).",
            made)
        return (out(amount, BLOW_DAMAGE_VAR), (else_(gate), else_(hot), else_(burns), then(seared)))
    return _author
