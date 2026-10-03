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

from combat.graph import BEL, _at, _connect, _node, _pin, _set
from uebp.graph import out
from combat.heat_tuning import (
    BLOW_DAMAGE_VAR, FIRE_FEAR_TAG, HOT_BLOW_SCALE, HOT_VAR,
)
from combat.nodes import FN_IS_VALID
from combat.weapon_component.common import _prop

FN_ACTOR_HAS_TAG = "/Script/Engine.Actor.ActorHasTag"


def author_hot_blow(strike):
    """The `damage` fragment for ``strike``: ``(ed, body, exec_in, x, y) ->
    (the damage's pin, the exits)``, ``body`` being the actor the sweep met."""
    def _author(ed, body, exec_in, x0, y0):
        made = []

        def keep(n):
            made.append(n)
            return n

        def put(value, x, y):
            n = keep(_at(ed.add_set_member_variable_node(BLOW_DAMAGE_VAR), x, y))
            _set(n, BLOW_DAMAGE_VAR, value)
            return n

        plain = put(strike.damage, x0, y0)
        _connect(exec_in, _pin(plain, "execute"))

        held_n = keep(_at(ed.add_get_member_variable_node("Held"), x0, y0 + 300))
        held = out(held_n, "Held")
        armed = keep(_at(_node(ed, FN_IS_VALID), x0 + 240, y0 + 300))
        _connect(held, _pin(armed, "Object"))
        gate = keep(_at(ed.add_branch_node(), x0 + 480, y0))
        _connect(out(armed), _pin(gate, "Condition"))
        _connect(BEL.find_then_pin(plain), _pin(gate, "execute"))
        hot_pin, hot_n = _prop(ed, HOT_VAR, held, x0 + 480, y0 + 300)
        keep(hot_n)
        hot = keep(_at(ed.add_branch_node(), x0 + 740, y0))
        _connect(hot_pin, _pin(hot, "Condition"))
        _connect(BEL.find_then_pin(gate), _pin(hot, "execute"))
        fears = keep(_at(_node(ed, FN_ACTOR_HAS_TAG), x0 + 740, y0 + 300))
        _connect(body, _pin(fears, "self"))
        _set(fears, "Tag", FIRE_FEAR_TAG)
        burns = keep(_at(ed.add_branch_node(), x0 + 1000, y0))
        _connect(out(fears), _pin(burns, "Condition"))
        _connect(BEL.find_then_pin(hot), _pin(burns, "execute"))
        seared = put(strike.damage * HOT_BLOW_SCALE, x0 + 1260, y0 - 160)
        _connect(BEL.find_then_pin(burns), _pin(seared, "execute"))

        amount = keep(_at(ed.add_get_member_variable_node(BLOW_DAMAGE_VAR),
                          x0 + 1520, y0 + 300))
        ed.add_comment_to_nodes(
            f"What the {strike.name}'s blow takes ({BLOW_DAMAGE_VAR}, "
            f"hot_blow.py): {strike.damage:g} HP, or {HOT_BLOW_SCALE:g} times "
            f"that with a hot blade in hand off a body tagged {FIRE_FEAR_TAG} "
            "(a creature afraid of fire).",
            made)
        return (out(amount, BLOW_DAMAGE_VAR),
                (BEL.find_else_pin(gate), BEL.find_else_pin(hot),
                 BEL.find_else_pin(burns), BEL.find_then_pin(seared)))
    return _author
