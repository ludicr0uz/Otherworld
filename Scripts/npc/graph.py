"""Authoring helpers every NPC module shares. The node/pin/connect/set ones
live in uebp/graph.py and are re-imported here, a temporary shim (removed in
Phase 2 of Scripts/dev/plans/remove_graph_literals.md); what is the NPC
package's own is _Graph (the node shapes a long fragment repeats) and the
creature asset paths.
"""

from uebp.graph import (  # noqa: F401
    BEL, BGE, PIN, _assets, _at, _connect, _create_blueprint, _loose_pin, _name_literal,
    _node, _palette, _pin, _resolve, _set, _try_set, make_log, out)

_log = make_log("NPC")
_asset_sub = _assets


class _Graph:
    """The node shapes a long fragment repeats (npc/stalk.py, stalk_cover.py),
    over the helpers above. ``made`` collects every node, for the caller's
    comment box."""

    def __init__(self, ed):
        self.ed, self.made = ed, []

    def keep(self, node, x, y):
        self.made.append(_at(node, x, y))
        return node

    def call(self, fn, x, y, **literals):
        node = self.keep(_node(self.ed, fn), x, y)
        for pin, value in literals.items():
            _set(node, pin, value)
        return node

    def op(self, fn, a, b, x, y):
        """A two-input maths node: ``a`` is a pin, ``b`` a pin or a number.
        Returns its output pin. A wired first: these are wildcards until
        then, and a wildcard B takes no literal."""
        node = self.keep(_node(self.ed, fn), x, y)
        _connect(a, _pin(node, "A"))
        if isinstance(b, (int, float)):
            _set(node, "B", b)
        else:
            _connect(b, _pin(node, "B"))
        return out(node)

    def get(self, var, x, y):
        node = self.keep(self.ed.add_get_member_variable_node(var), x, y)
        return _pin(node, var, is_input=False)

    def put(self, var, exec_in, x, y, pin=None, literal=None):
        """Write ``var`` from a pin or a literal; returns the Set's then pin.
        ``exec_in`` is one exec pin or several."""
        node = self.keep(self.ed.add_set_member_variable_node(var), x, y)
        if pin is not None:
            _connect(pin, _pin(node, var))
        else:
            _set(node, var, literal)
        for source in (exec_in if isinstance(exec_in, list) else [exec_in]):
            _connect(source, _pin(node, "execute"))
        return BEL.find_then_pin(node)

    def branch(self, condition, exec_in, x, y):
        """A Branch on ``condition`` (None: always true), run by ``exec_in``."""
        node = self.keep(self.ed.add_branch_node(), x, y)
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
