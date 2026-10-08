"""Writing a relevancy row (net/relevancy_consts.py) onto a class's defaults,
and reading it back: NetCullDistanceSquared, NetUpdateFrequency and
MinNetUpdateFrequency on an actor Blueprint's CDO. A class default, so
written after a compile, like net.replicate_actor (uebp/CLAUDE.md).
"""

import unreal

from net.relevancy_consts import (
    CULL_PROPERTY, M_TO_CM, MIN_RATE_PROPERTY, RATE_PROPERTY, Relevancy, cull_cm2)
from uebp.graph import BEL


def _cdo(bp):
    return unreal.get_default_object(BEL.generated_class(bp))


def apply(bp, row):
    """Write ``row`` onto the Blueprint's class defaults; reads each back."""
    cdo = _cdo(bp)
    for prop, want in ((CULL_PROPERTY, cull_cm2(row)),
                       (RATE_PROPERTY, row.update_hz),
                       (MIN_RATE_PROPERTY, row.min_hz)):
        cdo.set_editor_property(prop, want)
        got = float(cdo.get_editor_property(prop))
        if abs(got - want) > 1e-3 * max(1.0, abs(want)):
            raise RuntimeError(f"{bp.get_name()}.{prop} did not stick: {got} != {want}")


def read(bp):
    """The row as the class defaults hold it (cull_m rounded to a metre)."""
    cdo = _cdo(bp)
    return Relevancy(cull_m=round(float(cdo.get_editor_property(CULL_PROPERTY)) ** 0.5 / M_TO_CM, 3),
                     update_hz=float(cdo.get_editor_property(RATE_PROPERTY)),
                     min_hz=float(cdo.get_editor_property(MIN_RATE_PROPERTY)))


def matches(bp, row):
    """Whether the class defaults hold ``row``."""
    got = read(bp)
    return (abs(got.cull_m - row.cull_m) < 0.01 and got.update_hz == row.update_hz
            and got.min_hz == row.min_hz)
