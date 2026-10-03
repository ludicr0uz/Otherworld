"""Wind in the materials: MPC_Wind, and the world-position offset (WPO) that
makes the grass and the trees move. The numbers and what moves how are in
forest_generator/wind.py.

    Scripts/dev/uepy.py Scripts/forest_import/wind.py   # standalone

ensure_wind() makes the collection and patches the two tree masters;
foliage_assets.build_material() calls author_grass_wind() into
M_ProcFoliage, which it rebuilds whole. ensure_foliage_assets() (the level
import) runs both.

The masters are patched, not rebuilt: M_Master_Bark and M_Master_Foliage
have no builder any more (it went in a cleanup), and every tree, shrub and
fern instance is parented to them. Each expression the wind adds carries the
desc EXPR_TAG, and a re-run deletes those first, so the patch is idempotent
and leaves the masters' own graph alone.

On/off is not here. A material cannot be switched at runtime, but a
component can stop evaluating WPO (SetEvaluateWorldPositionOffset), and then
the material's offset is skipped, cost and all: that is the graphics menu's
wind row (graphics_menu/gfx_tuner_wind.py).
"""

import os
import sys

import unreal

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from forest_generator import wind as W  # noqa: E402

MEL = unreal.MaterialEditingLibrary
MP = unreal.MaterialProperty


def _log(msg):
    unreal.log_warning(f"[GEN] wind: {msg}")


def ensure_collection():
    """MPC_Wind with its two scalars at their defaults. Returns it."""
    eas = unreal.get_editor_subsystem(unreal.EditorAssetSubsystem)
    if eas.does_asset_exist(W.MPC_PATH):
        mpc = eas.load_asset(W.MPC_PATH)
    else:
        mpc = unreal.AssetToolsHelpers.get_asset_tools().create_asset(
            W.MPC_NAME, W.MPC_DIR, unreal.MaterialParameterCollection,
            unreal.MaterialParameterCollectionFactoryNew())
    have = {str(p.get_editor_property("parameter_name")): p
            for p in mpc.get_editor_property("scalar_parameters")}
    params = []
    for name, value in W.MPC_DEFAULTS.items():
        # Keep an existing parameter's Id: materials refer to it by that.
        p = have.get(name) or unreal.CollectionScalarParameter()
        p.set_editor_property("parameter_name", name)
        p.set_editor_property("default_value", value)
        params.append(p)
    mpc.set_editor_property("scalar_parameters", params)
    eas.save_loaded_asset(mpc, only_if_is_dirty=False)
    return mpc


class _Graph:
    """Expression helpers for one material, every node tagged EXPR_TAG."""

    def __init__(self, mat, mpc, x0, y0):
        self.mat, self.mpc, self.x, self.y = mat, mpc, x0, y0

    def expr(self, cls, *inputs, **props):
        """A node with ``inputs`` wired to its first pins in order: each a
        node, or (node, output name)."""
        e = MEL.create_material_expression(self.mat, cls, self.x, self.y)
        self.y += 120
        e.set_editor_property("desc", W.EXPR_TAG)
        for k, v in props.items():
            e.set_editor_property(k, v)
        names = MEL.get_material_expression_input_names(e)
        for name, src in zip(names, inputs):
            node, out = src if isinstance(src, tuple) else (src, "")
            if not MEL.connect_material_expressions(node, out, e, name):
                raise RuntimeError(f"wind: could not wire {name} of {cls.__name__}")
        return e

    def const(self, value):
        return self.expr(unreal.MaterialExpressionConstant, r=float(value))

    def vec(self, xyz):
        return self.expr(unreal.MaterialExpressionConstant3Vector,
                         constant=unreal.LinearColor(*xyz, 0.0))

    def param(self, name):
        return self.expr(unreal.MaterialExpressionCollectionParameter,
                         collection=self.mpc, parameter_name=name)

    def mul(self, a, b):
        return self.expr(unreal.MaterialExpressionMultiply, a, b)

    def add(self, a, b):
        return self.expr(unreal.MaterialExpressionAdd, a, b)

    def sine(self, cycles):
        return self.expr(unreal.MaterialExpressionSine, cycles)

    def world_pos(self):
        # Inside WPO the position must leave the offsets out: it is what
        # they are being computed from.
        return self.expr(
            unreal.MaterialExpressionWorldPosition,
            world_position_shader_offset=(
                unreal.WorldPositionIncludedOffsets.WPT_EXCLUDE_ALL_SHADER_OFFSETS))

    def along(self, pos, axis, per_cm):
        """Cycles along ``axis``: dot(pos, axis) / wavelength."""
        dot = self.expr(unreal.MaterialExpressionDotProduct, pos, self.vec(axis))
        return self.mul(dot, self.const(1.0 / per_cm))

    def wave(self, t, hz, phase):
        """sin(t x hz - phase), in cycles."""
        return self.sine(self.expr(unreal.MaterialExpressionSubtract,
                                   self.mul(t, self.const(hz)), phase))

    def time(self):
        """Seconds x MPC_Wind.Speed."""
        return self.mul(self.expr(unreal.MaterialExpressionTime), self.param(W.PARAM_SPEED))

    def field(self, t, pos, hz, cm, cross_cm):
        """Two wave trains crossing on GUST_HEADINGS, -1..1: it varies in
        patches over the ground, and the patches travel downwind."""
        (share, axis), (cross_share, cross_axis) = W.GUST_HEADINGS
        main = self.wave(t, hz, self.along(pos, axis, cm))
        cross = self.wave(t, hz * W.CROSS_RATE, self.along(pos, cross_axis, cross_cm))
        return self.add(self.mul(main, self.const(share)),
                        self.mul(cross, self.const(cross_share)))

    def instance_random(self):
        return self.expr(unreal.MaterialExpressionPerInstanceRandom)

    def heading(self, turns):
        """(along, across): DIRECTION turned by ``turns``, and the unit
        vector 90 degrees left of that."""
        cos = self.expr(unreal.MaterialExpressionCosine, turns)
        sin = self.sine(turns)
        wind, cross = self.vec(W.DIRECTION), self.vec(W.CROSSWIND)
        along = self.add(self.mul(wind, cos), self.mul(cross, sin))
        across = self.expr(unreal.MaterialExpressionSubtract,
                           self.mul(cross, cos), self.mul(wind, sin))
        return along, across

    def veer(self, t, pos, veer_turns, scatter_turns, hz, cm, cross_cm):
        """Turns off DIRECTION here and now: the drifting field's, plus the
        instance's own (-scatter..scatter, from PerInstanceRandom)."""
        own = self.mul(self.add(self.instance_random(), self.const(-0.5)),
                       self.const(2.0 * scatter_turns))
        return self.add(self.mul(self.field(t, pos, hz, cm, cross_cm),
                                 self.const(veer_turns)), own)

    def push(self, amount, amp_cm, axis):
        """axis x amount x amp_cm x MPC_Wind.Strength: a WPO vector.
        ``axis`` is a node (a heading) or a constant xyz."""
        if isinstance(axis, tuple):
            axis = self.vec(axis)
        scaled = self.mul(amount, self.mul(self.param(W.PARAM_STRENGTH), self.const(amp_cm)))
        return self.mul(axis, scaled)


def _height(g):
    """The vertex's height above the mesh's own origin (the trunk base)."""
    return g.expr(unreal.MaterialExpressionComponentMask,
                  g.expr(unreal.MaterialExpressionPreSkinnedPosition),
                  r=False, g=False, b=True, a=False)


def _tree_sway(g):
    """Every tree's bend: (h / ref)^2 x (0.35 + 0.35 gust + own sway) along
    its heading, and a share of its own sway across it."""
    t = g.time()
    pos = g.world_pos()
    h = g.expr(unreal.MaterialExpressionSaturate,
               g.mul(_height(g), g.const(1.0 / W.TREE_REF_HEIGHT_CM)))
    bend = g.mul(h, h)
    gust = g.field(t, pos, W.TREE_GUST_HZ, W.TREE_GUST_CM, W.TREE_CROSS_GUST_CM)
    own = g.wave(t, W.TREE_SWAY_HZ, g.mul(g.instance_random(), g.const(-1.0)))
    amount = g.add(g.const(0.35), g.add(g.mul(gust, g.const(0.35)),
                                        g.mul(own, g.const(W.TREE_OWN_SWAY))))
    # Across the heading at another rate and phase, so the two never line up.
    rock = g.wave(t, W.TREE_SWAY_HZ * W.TREE_CROSS_SWAY_RATE,
                  g.mul(g.instance_random(), g.const(-3.7)))
    along, across = g.heading(g.veer(
        t, pos, W.TREE_VEER_TURNS, W.TREE_SCATTER_TURNS, W.TREE_VEER_HZ,
        W.TREE_VEER_CM, W.TREE_CROSS_VEER_CM))
    return g.add(
        g.push(g.mul(amount, bend), W.TREE_AMP_CM, along),
        g.push(g.mul(rock, bend), W.TREE_AMP_CM * W.TREE_OWN_SWAY * W.TREE_CROSS_SWAY,
               across))


def _leaf_flutter(g):
    t = g.time()
    scatter = g.expr(unreal.MaterialExpressionDotProduct, g.world_pos(),
                     g.vec(W.LEAF_SCATTER))
    flutter = g.wave(t, W.LEAF_HZ, scatter)
    ramp = g.expr(unreal.MaterialExpressionSaturate,
                  g.mul(_height(g), g.const(1.0 / W.LEAF_REF_CM)))
    return g.push(g.mul(flutter, ramp), W.LEAF_AMP_CM, W.LEAF_AXIS)


def author_grass_wind(mat, mpc, weight, x0=-1200, y0=1100):
    """M_ProcFoliage's WPO: lean and sway along the clump's own heading in
    rolling gusts, x ``weight`` (the vertex colour's alpha: 0 at the root, 1
    at the tip)."""
    g = _Graph(mat, mpc, x0, y0)
    t = g.time()
    pos = g.world_pos()
    sway = g.field(t, pos, W.GRASS_SWAY_HZ, W.GRASS_WAVE_CM, W.GRASS_CROSS_WAVE_CM)
    flutter = g.wave(t, W.GRASS_FLUTTER_HZ, g.mul(g.instance_random(), g.const(-1.0)))
    amount = g.add(g.add(g.const(0.55), g.mul(sway, g.const(0.45))),
                   g.mul(flutter, g.const(W.GRASS_FLUTTER)))
    along, _ = g.heading(g.veer(
        t, pos, W.GRASS_VEER_TURNS, W.GRASS_SCATTER_TURNS, W.GRASS_VEER_HZ,
        W.GRASS_VEER_CM, W.GRASS_CROSS_VEER_CM))
    wpo = g.push(g.mul(amount, weight), W.GRASS_AMP_CM, along)
    MEL.connect_material_property(wpo, "", MP.MP_WORLD_POSITION_OFFSET)
    mat.set_editor_property("max_world_position_offset_displacement",
                            W.GRASS_MAX_DISPLACEMENT_CM)


def _wind_exprs(mat):
    return [e for e in MEL.get_material_expressions(mat)
            if str(e.get_editor_property("desc")) == W.EXPR_TAG]


def patch_master(path, mpc, leaves):
    """Give a tree master the sway (and, for ``leaves``, the flutter)."""
    mat = unreal.load_asset(path)
    if not mat:
        raise RuntimeError(f"{path} is missing")
    for e in _wind_exprs(mat):
        MEL.delete_material_expression(mat, e)
    if MEL.get_material_property_input_node(mat, MP.MP_WORLD_POSITION_OFFSET):
        raise RuntimeError(f"{path} already has a WPO of its own; not overwriting it")
    g = _Graph(mat, mpc, -2400, 1400)
    wpo = _tree_sway(g)
    if leaves:
        g.x, g.y = -3400, 1400
        wpo = g.add(wpo, _leaf_flutter(g))
    MEL.connect_material_property(wpo, "", MP.MP_WORLD_POSITION_OFFSET)
    mat.set_editor_property("max_world_position_offset_displacement",
                            W.TREE_MAX_DISPLACEMENT_CM)
    MEL.recompile_material(mat)
    unreal.EditorAssetLibrary.save_loaded_asset(mat, only_if_is_dirty=False)
    _log(f"{path}: {len(_wind_exprs(mat))} wind nodes")
    return mat


def ensure_wind():
    """The collection and both tree masters. Returns the collection."""
    mpc = ensure_collection()
    patch_master(W.MASTER_BARK, mpc, leaves=False)
    patch_master(W.MASTER_FOLIAGE, mpc, leaves=True)
    return mpc


def verify_wind(check):
    """The collection and every material's WPO. ``check`` is the level
    verifier's harness."""
    mpc = unreal.load_asset(W.MPC_PATH)
    check("MPC_Wind Exists", bool(mpc))
    if mpc:
        got = {str(p.get_editor_property("parameter_name")):
               p.get_editor_property("default_value")
               for p in mpc.get_editor_property("scalar_parameters")}
        check("MPC_Wind Strength And Speed At Their Defaults",
              all(abs(got.get(k, -1) - v) < 1e-6 for k, v in W.MPC_DEFAULTS.items()),
              str(got))
    for path in (W.PROC_FOLIAGE, W.MASTER_BARK, W.MASTER_FOLIAGE):
        mat = unreal.load_asset(path)
        name = path.rsplit("/", 1)[1]
        if not mat:
            check(f"{name} Has Wind", False, "missing")
            continue
        wpo = MEL.get_material_property_input_node(mat, MP.MP_WORLD_POSITION_OFFSET)
        reads = {str(e.get_editor_property("parameter_name"))
                 for e in MEL.get_material_expressions(mat)
                 if isinstance(e, unreal.MaterialExpressionCollectionParameter)
                 and e.get_editor_property("collection") == mpc}
        check(f"{name} Has Wind (WPO From MPC_Wind's Strength And Speed)",
              bool(wpo) and reads == set(W.MPC_DEFAULTS), f"wpo={bool(wpo)} reads={reads}")
        check(f"{name} Wind Is Bounded",
              mat.get_editor_property("max_world_position_offset_displacement") > 0)
        # One heading for everything is a wall of wind: the push's axis is
        # turned (a Cosine exists for nothing else) by the instance's own
        # angle and a field over the ground.
        kinds = {type(e) for e in _wind_exprs(mat)}
        need = {unreal.MaterialExpressionCosine, unreal.MaterialExpressionPerInstanceRandom,
                unreal.MaterialExpressionWorldPosition}
        check(f"{name} Wind's Heading Varies From Instance To Instance And Over The Ground",
              need <= kinds, str(sorted(k.__name__ for k in need - kinds)))


if __name__ == "__main__":
    ensure_wind()
