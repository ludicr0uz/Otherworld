"""Whatever is drawn under the player's mannequin gets what the mannequin
gets: hidden from its own camera behind a scope (sights.py), its head out
of the sight picture (head_hide.py), and both back on death (dead.py).

    OwnerMesh.GetChildrenComponents(all descendants)
        -> ForEach -> Cast to <PrimitiveComponent | SkinnedMeshComponent>
                   -> the same call the mannequin got

A MetaHuman skin (combat/metahuman_body.py) hangs a body, a face, garments
and grooms under the mannequin, and neither OwnerNoSee nor a hidden bone
reaches a child component: the mannequin would go out of the glass and the
MetaHuman stay in it. A mannequin skin has no children, and the loop runs
over none.

Per-view (OwnerNoSee) rather than hidden, as the mannequin is: other
players still see the body, and it still casts its shadow.

The head's own parts (a MetaHuman skin's Face and its six grooms, tagged
HEAD_PART_TAG by metahuman_body.py) are a filter of the same loop: a Branch
on ComponentHasTag after the cast. Down the sights they alone go out of
their owner's view (author_head_parts_no_see), and the hidden head bone
skips them (author_parts_bone's ``skip_tag``): a groom's strands do not
follow a hidden bone, and a face out of view by OwnerNoSee still casts its
shadow (bCastHiddenShadow), which a face with its bone hidden would not.
"""

from uebp.graph import (
    _connect, _loose_pin, _node, _palette, _pin, _set, else_, out, then,
)
from uebp.nodes.actor import FN_COMP_HAS_TAG
from uebp.nodes.palette import MACRO_FOR_EACH
from combat.seat_tuning import HEAD_PART_TAG
from combat.weapon_component import vars as WV

FN_GET_CHILDREN = "/Script/Engine.SceneComponent.GetChildrenComponents"
NODE_CAST_PRIMITIVE = "Utilities|Casting|CastToPrimitiveComponent"
NODE_CAST_SKINNED = "Utilities|Casting|CastToSkinnedMeshComponent"
AS_PRIMITIVE = "AsPrimitive Component"
AS_SKINNED = "AsSkinned Mesh Component"


def author_for_parts(ed, keep, exec_in, cast_name, as_pin, build,
                     tag=None, tagged=True):
    """exec_in -> every component under OwnerMesh, cast -> ``build(part,
    exec)``, which authors the call on ``part`` from ``exec`` and returns
    nothing. With ``tag``, only the parts that have that component tag
    (``tagged``) or only those that have not. Returns the exec pin to carry
    on from (the loop's Completed)."""
    body = keep(ed.add_get_member_variable_node(WV.OwnerMesh))
    kids = keep(_node(ed, FN_GET_CHILDREN))
    _connect(out(body, WV.OwnerMesh), _pin(kids, "self"))
    _set(kids, "bIncludeAllDescendants", True)      # a pure call: no exec pins
    loop = keep(ed.add_macro_node(MACRO_FOR_EACH))
    if not loop:
        raise RuntimeError("could not create the ForEachLoop macro node")
    _connect(_pin(kids, "Children", is_input=False), _loose_pin(loop, "Array"))
    _connect(exec_in, _loose_pin(loop, "Exec"))
    cast = keep(_palette(ed, cast_name))
    _connect(_loose_pin(loop, "ArrayElement", is_input=False), _pin(cast, "Object"))
    _connect(_loose_pin(loop, "LoopBody", is_input=False), _pin(cast, "execute"))
    part, run = _loose_pin(cast, as_pin, is_input=False), then(cast)
    if tag is not None:
        has = keep(_node(ed, FN_COMP_HAS_TAG))      # a pure call
        _connect(part, _pin(has, "self"))
        _set(has, "Tag", tag)
        gate = keep(ed.add_branch_node())
        _connect(out(has), _pin(gate, "Condition"))
        _connect(run, _pin(gate, "execute"))
        run = then(gate) if tagged else else_(gate)
    build(part, run)
    return _loose_pin(loop, "Completed", is_input=False)


def author_parts_no_see(ed, keep, exec_in, no_see_out=None, no_see=None, tag=None):
    """SetOwnerNoSee on every part: from a pin (``no_see_out``) or a literal.
    With ``tag``, on the parts that have that component tag alone."""
    from uebp.nodes.actor import FN_SET_OWNER_NO_SEE

    def build(part, exec_pin):
        call = keep(_node(ed, FN_SET_OWNER_NO_SEE))
        _connect(part, _pin(call, "self"))
        if no_see_out is not None:
            _connect(no_see_out, _pin(call, "bNewOwnerNoSee"))
        else:
            _set(call, "bNewOwnerNoSee", bool(no_see))
        _connect(exec_pin, _pin(call, "execute"))
    return author_for_parts(ed, keep, exec_in, NODE_CAST_PRIMITIVE, AS_PRIMITIVE, build,
                            tag=tag)


def author_head_parts_no_see(ed, keep, exec_in, no_see):
    """SetOwnerNoSee(``no_see``) on the head's own parts alone (the Face and
    the grooms: HEAD_PART_TAG). The body, the arms and the garments are not
    touched: they are the sight picture."""
    return author_parts_no_see(ed, keep, exec_in, no_see=no_see, tag=HEAD_PART_TAG)


def author_parts_bone(ed, keep, exec_in, fn_path, bone, phys_body_op=None,
                      skip_tag=None):
    """HideBoneByName / UnHideBoneByName(bone) on every skinned part. A part
    whose skeleton has no such bone is left as it is (the call says nothing),
    which is what a garment wants. ``skip_tag``: not on the parts tagged so."""
    def build(part, exec_pin):
        call = keep(_node(ed, fn_path))
        _connect(part, _pin(call, "self"))
        _set(call, "BoneName", bone)
        if phys_body_op is not None:
            _set(call, "PhysBodyOption", phys_body_op)
        _connect(exec_pin, _pin(call, "execute"))
    return author_for_parts(ed, keep, exec_in, NODE_CAST_SKINNED, AS_SKINNED, build,
                            tag=skip_tag, tagged=False)
