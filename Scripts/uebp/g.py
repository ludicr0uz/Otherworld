"""_G: the few node shapes a long fragment repeats, each made and kept.

    g = _G(ed, ITEM_CLASS_PATH)
    held = g.get("Held")
    hit, missed = g.branch(out(g.call(FN_IS_VALID, Object=held)), [exec_in])

``g.made`` collects every node, for the caller's comment box.
"""

from uebp.graph import _connect, _loose_pin, _node, _pin, _set, else_, out, then


class _G:
    def __init__(self, ed, item_class=None):
        """``item_class``: the class iget/iput read when given none."""
        self.ed, self.made, self.item_class = ed, [], item_class

    def keep(self, n):
        self.made.append(n)
        return n

    def get(self, var):
        return out(self.keep(self.ed.add_get_member_variable_node(var)), var)

    def put(self, var, value, execs):
        """Set ``var`` to a pin, or to a literal string. Returns its then pin."""
        n = self.keep(self.ed.add_set_member_variable_node(var))
        if isinstance(value, str):
            _set(n, var, value)
        elif value is not None:
            _connect(value, _pin(n, var))
        for e in execs:
            _connect(e, _pin(n, "execute"))
        return then(n)

    def call(g, fn, execs=(), **inputs):
        n = g.keep(_node(g.ed, fn))
        for name, value in inputs.items():
            if isinstance(value, (str, int)):
                _set(n, name, value)
            else:
                _connect(value, _loose_pin(n, name))
        for e in execs:
            _connect(e, _pin(n, "execute"))
        return n

    def iget(self, item, var, class_path=None):
        """Read ``var`` off another object (an item, by default)."""
        n = self.keep(self.ed.add_get_member_variable_node(var, class_path or self.item_class))
        _connect(item, _pin(n, "self"))
        return out(n, var)

    def iput(self, item, var, value, execs, class_path=None):
        """Set ``var`` on another object to a pin or a literal string."""
        n = self.keep(self.ed.add_set_member_variable_node(var, class_path or self.item_class))
        _connect(item, _pin(n, "self"))
        if isinstance(value, str):
            _set(n, var, value)
        else:
            _connect(value, _pin(n, var))
        for e in execs:
            _connect(e, _pin(n, "execute"))
        return then(n)

    def branch(self, cond, execs):
        br = self.keep(self.ed.add_branch_node())
        _connect(cond, _pin(br, "Condition"))
        for e in execs:
            _connect(e, _pin(br, "execute"))
        return then(br), else_(br)
