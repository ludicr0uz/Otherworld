"""``uebp.verify_vars.check_table`` against a fake table and a fake Blueprint:
what it passes, and that each of its four checks fails on its own fault.
"""

import unittest

import _paths  # noqa: F401

from uebp.vars import NONE, REP_NOTIFY, REPLICATED, Var, lazy
from uebp.verify_vars import _brief, check_table


class _Type:
    def __init__(self, text):
        self.text = text

    def export_text(self):
        return self.text


def _type(text):
    return lambda: _Type(text)


REAL, FLAG, WHOLE = _type("real"), _type("bool"), _type("int")

Health = Var("Health", REAL, 100.0, rep=REP_NOTIFY)
Dead = Var("Dead", FLAG, False, rep=REPLICATED)
Hits = Var("Hits", WHOLE)                          # no default: whatever it starts at
Home = Var("Home", _type("vector"), lazy(lambda: (0.0, 0.0, 0.0)))
Mesh = Var("Mesh")                                 # a component: a name only
TABLE = (Health, Dead, Hits, Home, Mesh)


class _Blueprint:
    """A Blueprint as ``check_table`` reads one: {name: (type, default, rep)}."""

    def __init__(self, **declared):
        self.declared = declared

    def get_name(self):
        return "BP_Fake"

    def names(self):
        return set(self.declared)

    def type_of(self, name):
        return self.declared[name][0]

    def default_of(self, name):
        return self.declared[name][1]

    def replication_of(self, name):
        return self.declared[name][2]

    def same(self, got, want):
        return got == want


def _built(**changed):
    declared = {"Health": ("real", 100.0, REP_NOTIFY), "Dead": ("bool", False, REPLICATED),
                "Hits": ("int", 7, NONE), "Home": ("vector", (0.0, 0.0, 0.0), NONE)}
    declared.update(changed)
    return _Blueprint(**{k: v for k, v in declared.items() if v is not None})


def _run(bp, table=TABLE, **kw):
    seen = []
    check_table(bp, table, lambda label, ok, detail="": seen.append((label, bool(ok), detail)),
                read=bp, **kw)
    return seen


class CheckTableTest(unittest.TestCase):
    def test_a_blueprint_built_from_its_table_passes_four_checks(self):
        seen = _run(_built())
        self.assertEqual([ok for _label, ok, _detail in seen], [True] * 4)
        self.assertEqual(len({label for label, _ok, _detail in seen}), 4)
        self.assertIn("BP_Fake", seen[0][0])
        self.assertIn("4 rows", seen[0][0])          # Mesh has no type: not a row to declare
        self.assertIn("Dead, Health", seen[2][0])

    def test_a_missing_row_fails_the_first_check_alone(self):
        seen = _run(_built(Dead=None))
        self.assertEqual([ok for _label, ok, _detail in seen], [False, True, True, True])
        self.assertIn("Dead", seen[0][2])
        self.assertIn("not declared", seen[0][2])

    def test_a_wrong_type_fails_the_first_check(self):
        seen = _run(_built(Health=("int", 100.0, REP_NOTIFY)))
        self.assertEqual([ok for _label, ok, _detail in seen], [False, True, True, True])
        self.assertIn("int != real", seen[0][2])

    def test_a_wrong_default_fails_the_second_check(self):
        seen = _run(_built(Health=("real", 0.0, REP_NOTIFY)))
        self.assertEqual([ok for _label, ok, _detail in seen], [True, False, True, True])
        self.assertIn("Health", seen[1][2])

    def test_a_lazy_default_is_made_before_it_is_compared(self):
        seen = _run(_built(Home=("vector", (1.0, 0.0, 0.0), NONE)))
        self.assertEqual([ok for _label, ok, _detail in seen], [True, False, True, True])

    def test_a_row_with_no_default_starts_at_anything(self):
        self.assertTrue(all(ok for _label, ok, _detail in _run(_built(Hits=("int", 99, NONE)))))

    def test_replication_must_be_the_rows(self):
        for name, declared in (("Dead", ("bool", False, NONE)),             # lost
                               ("Health", ("real", 100.0, REPLICATED)),     # no notify
                               ("Hits", ("int", 7, REPLICATED))):           # the row says none
            seen = _run(_built(**{name: declared}))
            self.assertEqual([ok for _label, ok, _detail in seen], [True, True, False, True],
                             name)
            self.assertIn(name, seen[2][2])

    def test_an_undeclared_variable_fails_the_last_check(self):
        seen = _run(_built(Stray=("int", 0, NONE)))
        self.assertEqual([ok for _label, ok, _detail in seen], [True, True, True, False])
        self.assertIn("Stray", seen[3][2])

    def test_others_may_sit_beside_the_table(self):
        seen = _run(_built(Stray=("int", 0, NONE)), others=("Stray",))
        self.assertTrue(all(ok for _label, ok, _detail in seen))

    def test_an_untyped_row_is_a_known_name(self):
        seen = _run(_built(Mesh=("object", None, NONE)))
        self.assertTrue(all(ok for _label, ok, _detail in seen))

    def test_an_open_blueprint_gets_three_checks(self):
        seen = _run(_built(Stray=("int", 0, NONE)), closed=False)
        self.assertEqual([ok for _label, ok, _detail in seen], [True] * 3)

    def test_a_table_with_no_typed_row_fails(self):
        seen = _run(_built(), table=(Mesh,), closed=False)
        self.assertFalse(seen[0][1])

    def test_a_type_is_told_briefly(self):
        text = ('(PinCategory="object",PinSubCategory="",PinSubCategoryObject='
                '"/Script/CoreUObject.Class\'/Script/Engine.Actor\'",PinValueType=('
                'TerminalCategory=""),ContainerType=Array,bIsReference=False)')
        self.assertEqual(_brief(text),
                         "object /Script/CoreUObject.Class'/Script/Engine.Actor' Array")
        self.assertEqual(_brief('(PinCategory="real",PinSubCategory="double",'
                                'PinSubCategoryObject=None,ContainerType=None)'), "real")

    def test_a_row_is_local_unless_it_says(self):
        self.assertEqual(Var("X", WHOLE).rep, NONE)
        self.assertEqual(Var("X", WHOLE, 1, REPLICATED).rep, REPLICATED)


if __name__ == "__main__":
    unittest.main()
