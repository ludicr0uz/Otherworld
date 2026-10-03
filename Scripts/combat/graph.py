"""The combat builders' way in to the authoring helpers, which live in
uebp/graph.py. A temporary shim: each module imports from uebp directly once
the call sites are migrated (Scripts/dev/plans/remove_graph_literals.md,
Phase 2).
"""

from uebp.graph import (
    BEL, BGE, PIN, SDL, _add_component, _apply_defaults, _assets, _component_object,
    _connect, _create_blueprint, _declare, _drop_components, _events, _find_handle,
    _float_type, _handles, _key, _literal_matches, _loose_pin, _must_load, _node, _palette,
    _pin, _pin_names, _post_physics_tick, _root_handle, _rot, _same, _set, _struct_type,
    _subobjects, _vec, make_log)

_log = make_log("GUN")
