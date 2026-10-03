"""What the NPC package's authoring modules share on top of uebp: the
package's log line, _Graph (the node shapes a long fragment repeats) and a
creature asset's object path.
"""

from uebp.graph import _connect, _node, _pin, _set, make_log, out, then

_log = make_log("NPC")


class _Graph:
    """The node shapes a long fragment repeats (npc/stalk.py, stalk_cover.py),
    over the helpers above. ``made`` collects every node, for the caller's
    comment box."""

    def __init__(self, ed):
        self.ed, self.made = ed, []

    def keep(self, node):
        self.made.append(node)
        return node

    def call(self, fn, **literals):
        node = self.keep(_node(self.ed, fn))
        for pin, value in literals.items():
            _set(node, pin, value)
        return node

    def op(self, fn, a, b):
        """A two-input maths node: ``a`` is a pin, ``b`` a pin or a number.
        Returns its output pin. A wired first: these are wildcards until
        then, and a wildcard B takes no literal."""
        node = self.keep(_node(self.ed, fn))
        _connect(a, _pin(node, "A"))
        if isinstance(b, (int, float)):
            _set(node, "B", b)
        else:
            _connect(b, _pin(node, "B"))
        return out(node)

    def get(self, var):
        node = self.keep(self.ed.add_get_member_variable_node(var))
        return out(node, var)

    def put(self, var, exec_in, pin=None, literal=None):
        """Write ``var`` from a pin or a literal; returns the Set's then pin.
        ``exec_in`` is one exec pin or several."""
        node = self.keep(self.ed.add_set_member_variable_node(var))
        if pin is not None:
            _connect(pin, _pin(node, var))
        else:
            _set(node, var, literal)
        for source in (exec_in if isinstance(exec_in, list) else [exec_in]):
            _connect(source, _pin(node, "execute"))
        return then(node)

    def branch(self, condition, exec_in):
        """A Branch on ``condition`` (None: always true), run by ``exec_in``."""
        node = self.keep(self.ed.add_branch_node())
        if condition is None:       # a join: several exec wires into one
            _set(node, "Condition", "true")
        else:
            _connect(condition, _pin(node, "Condition"))
        for source in (exec_in if isinstance(exec_in, list) else [exec_in]):
            _connect(source, _pin(node, "execute"))
        return node


# ── Body and animation ───────────────────────────────────────────────────────
#
# The wanderers wear Meshy creatures, each on its OWN skeleton, animated by
# its own A_<Creature>_ABP_Unarmed -- ABP_Unarmed retargeted onto that
# skeleton, state machine and blend space included, by
# Scripts/asset_pipeline/build_retarget.py.
# An anim BP is bound to one skeleton, so the mannequin's cannot drive a
# creature; retargeting the BLUEPRINT rather than a folder of clips is what
# makes the monsters usable by a Character at all.
#
# Every one of these lives under /Game/Sourced, which is git-ignored and
# rebuilt from assets/cache/meshy.  A checkout that has not run the asset
# pipeline therefore has none of them, and the mannequin pair it falls back to
# is the combination that shipped before the creatures existed -- a wanderer
# that looks wrong is a far better failure than a build that stops, and the log
# says loudly which one happened.
# _resolve (uebp/graph.py) picks between the two.


def _mesh_object(pkg):
    return f"{pkg}.{pkg.rsplit('/', 1)[-1]}"
