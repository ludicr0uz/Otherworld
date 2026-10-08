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
"""

from uebp.graph import _connect, _loose_pin, _node, _palette, _pin, _set, out, then
from uebp.nodes.palette import MACRO_FOR_EACH
from combat.weapon_component import vars as WV

FN_GET_CHILDREN = "/Script/Engine.SceneComponent.GetChildrenComponents"
NODE_CAST_PRIMITIVE = "Utilities|Casting|CastToPrimitiveComponent"
NODE_CAST_SKINNED = "Utilities|Casting|CastToSkinnedMeshComponent"
AS_PRIMITIVE = "AsPrimitive Component"
AS_SKINNED = "AsSkinned Mesh Component"


def author_for_parts(ed, keep, exec_in, cast_name, as_pin, build):
    """exec_in -> every component under OwnerMesh, cast -> ``build(part,
    exec)``, which authors the call on ``part`` from ``exec`` and returns
    nothing. Returns the exec pin to carry on from (the loop's Completed)."""
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
    build(_loose_pin(cast, as_pin, is_input=False), then(cast))
    return _loose_pin(loop, "Completed", is_input=False)


def author_parts_no_see(ed, keep, exec_in, no_see_out=None, no_see=None):
    """SetOwnerNoSee on every part: from a pin (``no_see_out``) or a literal."""
    from uebp.nodes.actor import FN_SET_OWNER_NO_SEE

    def build(part, exec_pin):
        call = keep(_node(ed, FN_SET_OWNER_NO_SEE))
        _connect(part, _pin(call, "self"))
        if no_see_out is not None:
            _connect(no_see_out, _pin(call, "bNewOwnerNoSee"))
        else:
            _set(call, "bNewOwnerNoSee", bool(no_see))
        _connect(exec_pin, _pin(call, "execute"))
    return author_for_parts(ed, keep, exec_in, NODE_CAST_PRIMITIVE, AS_PRIMITIVE, build)


def author_parts_bone(ed, keep, exec_in, fn_path, bone, phys_body_op=None):
    """HideBoneByName / UnHideBoneByName(bone) on every skinned part. A part
    whose skeleton has no such bone is left as it is (the call says nothing),
    which is what a garment wants."""
    def build(part, exec_pin):
        call = keep(_node(ed, fn_path))
        _connect(part, _pin(call, "self"))
        _set(call, "BoneName", bone)
        if phys_body_op is not None:
            _set(call, "PhysBodyOption", phys_body_op)
        _connect(exec_pin, _pin(call, "execute"))
    return author_for_parts(ed, keep, exec_in, NODE_CAST_SKINNED, AS_SKINNED, build)
