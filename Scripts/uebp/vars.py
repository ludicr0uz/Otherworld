"""Blueprint member variables, declared once.

A ``Var`` IS its name (a ``str``), so it goes wherever the name went -- a
variable node, a pin, a defaults dict, a probe's WRITABLE list -- and it
carries the variable's pin type and default beside it. Each Blueprint's
table (``<package>/<blueprint>_vars.py``) is what its builder declares from:

    Health = Var("Health", FLOAT, COMBAT.start_health)
    TABLE = (Health, ...)

    declare(ed, HV.TABLE)                              # in the builder
    _apply_defaults(bp, {**defaults(HV.TABLE), ...})
    ed.add_get_member_variable_node(HV.Health)         # in a fragment

A row with no type is a name only: a component, or a variable its builder
declares itself. A default only the editor can make (a key, a zero vector)
is a ``lazy``, made when ``defaults`` is called. Nothing here imports ``unreal`` until a type is resolved, so
a table is plain Python to a probe or a host-side tool.
"""

UNSET = object()


class Var(str):
    """A member variable: its name (the string itself), pin type, default."""

    def __new__(cls, name, pin_type=None, default=UNSET):
        self = super().__new__(cls, name)
        str.__setattr__(self, "pin_type", pin_type)
        str.__setattr__(self, "default", default)
        return self

    def __setattr__(self, key, value):
        raise AttributeError("a Var is frozen")

    @property
    def name(self):
        return str(self)


# ─── Pin types: zero-argument callables, resolved when the builder declares ──

def _bel():
    import unreal
    return unreal.BlueprintEditorLibrary


def _load(path):
    import unreal
    found = unreal.load_object(None, path)
    if not found:
        raise RuntimeError(f"could not load {path}")
    return found


def FLOAT():
    return _bel().get_basic_type_by_name("real")       # "float" silently declares an int


def BOOL():
    return _bel().get_basic_type_by_name("bool")


def INT():
    return _bel().get_basic_type_by_name("int")


def NAME():
    return _bel().get_basic_type_by_name("name")


def STRING():
    return _bel().get_basic_type_by_name("string")


def struct(path):
    """A struct by its path: ``struct("/Script/CoreUObject.Vector")``."""
    return lambda: _bel().get_struct_type(_load(path))


def obj(path):
    """An object reference to a class, engine or generated, by its path."""
    return lambda: _bel().get_object_reference_type(_load(path))


def cls(path):
    """A class reference (a ``TSubclassOf``) to a class by its path."""
    return lambda: _bel().get_class_reference_type(_load(path))


VECTOR = struct("/Script/CoreUObject.Vector")
ROTATOR = struct("/Script/CoreUObject.Rotator")
KEY = struct("/Script/InputCore.Key")


def array(of):
    return lambda: _bel().get_array_type(of())


# ─── Defaults only the editor can make: resolved by ``defaults`` ─────────────

class lazy:
    """A default made when the builder applies it, not when the table loads."""

    def __init__(self, make):
        self.make = make


def _zero_vector():
    import unreal
    return unreal.Vector(0.0, 0.0, 0.0)


def _zero_rotator():
    import unreal
    return unreal.Rotator(0.0, 0.0, 0.0)


ZERO_VECTOR = lazy(_zero_vector)
ZERO_ROTATOR = lazy(_zero_rotator)


def key(name):
    """An FKey by its name: ``key("LeftMouseButton")``."""
    def make():
        from uebp.graph import _key
        return _key(name)
    return lazy(make)


# ─── What a builder does with a table ────────────────────────────────────────

def declare(ed, table):
    """Re-declare every typed row, so a type changed in the table lands."""
    from uebp.graph import _declare
    for var in table:
        if var.pin_type is not None:
            _declare(ed, var, var.pin_type())


def declare_missing(ed, table):
    """Add each typed row that is not there yet. One already there is left
    alone, with the nodes that read it: for a graph that is patched in place
    rather than wiped."""
    for var in table:
        if var.pin_type is not None:
            ed.add_member_variable(var, var.pin_type())


def defaults(table):
    """{name: default} for the rows that have one, for ``_apply_defaults``."""
    return {var: var.default.make() if isinstance(var.default, lazy) else var.default
            for var in table if var.default is not UNSET}
