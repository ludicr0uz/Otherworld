"""A verifier's check of a Blueprint's variables against their table.

``check_table(bp, TABLE, check)`` is what a verifier calls once per
Blueprint instead of re-stating the variables it expects: every typed row
is declared with the row's pin type, starts at the row's default, compiles
with the row's replication (``Var(..., rep=REPLICATED)``; a row says nothing
and is local), and no variable the table does not name sits beside them.
``TABLE`` is every row the Blueprint's builders declare, so a Blueprint
several fragments write to is handed their tables joined.

It makes four ``check`` lines per Blueprint, whatever the table's length.
Nothing here imports ``unreal`` until a Blueprint is read: the reading is a
``_Editor``, and a dev unit test hands ``check_table`` a fake in its place.
"""

import re

from uebp.vars import NONE, UNSET, defaults

_PARTS = re.compile(r'\b(PinCategory|PinSubCategoryObject|ContainerType)="?([^",)]*)')


def _brief(pin_type):
    """A pin type's exported text cut to what tells two apart, for a detail
    line: ``real``, ``object /Script/Engine.Actor, Array``."""
    said = [value for _key, value in _PARTS.findall(pin_type) if value not in ("", "None")]
    return " ".join(said) or pin_type


class _Editor:
    """What ``check_table`` asks of a Blueprint, answered by the editor."""

    def __init__(self, bp):
        import unreal
        from uebp.graph import BEL
        self.bp = bp
        self.bel = BEL
        self.cdo = unreal.get_default_object(BEL.generated_class(bp))

    def names(self):
        """The Blueprint's own: an inherited one is listed by its class's path
        (``/Script/Engine.Actor.Tags``), and is its parent's to check."""
        listed = (str(n) for n in self.bel.list_member_variable_names(self.bp))
        return {n for n in listed if "." not in n}

    def type_of(self, name):
        return self.bel.get_member_variable_type(self.bp, name).export_text()

    def default_of(self, name):
        return self.cdo.get_editor_property(name)

    def replication_of(self, name):
        from uebp import net
        return net.compiled_replication(self.bp, name)[0]

    def same(self, got, want):
        from uebp.graph import _same
        return _same(got, want)


def check_table(bp, table, check, others=(), closed=True, read=None):
    """Four checks that ``bp`` declares exactly what ``table`` says.

    ``others``: names that may sit beside the table's rows (what a parent
    Blueprint's builder or the engine put there). ``closed=False`` drops the
    last check, for a stock Blueprint a builder only adds to.
    """
    read = read or _Editor(bp)
    name = bp.get_name()
    declared = read.names()
    typed = [v for v in table if v.pin_type is not None]

    wrong = {}
    for var in typed:
        if var not in declared:
            wrong[str(var)] = "not declared"
            continue
        got, want = read.type_of(var), var.pin_type().export_text()
        if got != want:
            wrong[str(var)] = f"{_brief(got)} != {_brief(want)}"
    check(f"{name} declares every row of its variable table with the row's type "
          f"({len(typed)} rows)", bool(typed) and not wrong, str(wrong))
    there = [v for v in typed if v in declared]

    want = defaults(table)
    off = {}
    for var in there:
        if var.default is UNSET:
            continue
        got = read.default_of(var)
        if not read.same(got, want[var]):
            off[str(var)] = f"{got!r} != {want[var]!r}"
    check(f"...{name}: each starts at its row's default", not off, str(off))

    kinds = {}
    for var in there:
        got = read.replication_of(var)
        if got != var.rep:
            kinds[str(var)] = f"{got}, the row says {var.rep}"
    told = sorted(str(v) for v in typed if v.rep != NONE)
    check(f"...{name}: each compiles with its row's replication "
          f"({', '.join(told) or 'none replicates'})", not kinds, str(kinds))

    if closed:
        known = {str(v) for v in table} | {str(o) for o in others}
        extra = sorted(declared - known)
        check(f"...{name}: no variable sits beside them that no table names",
              not extra, str(extra))
