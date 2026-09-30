"""Authoring UMG widget trees from Python: the designer half of a Widget
Blueprint, built the way a person would build it in the UMG editor.

Python cannot reach UWidgetBlueprint::WidgetTree (a protected, non-Blueprint
UPROPERTY), which is why this HUD used to be an AHUD canvas. The engine's
UMGToolSet plugin (Engine/Plugins/Experimental/Toolsets, enabled for the
editor only in Otherworld.uproject) wraps the UMG editor's own operations --
create, add a widget under a parent, mark it a variable, compile -- in static
UFUNCTIONs. They are meta=(AICallable), not BlueprintCallable, so they have no
Python glue; ``call_method`` reaches them through reflection all the same.

Once a widget is in the tree it is an ordinary UObject: its properties are
set with set_editor_property, and its slot (the layout it has inside its
parent) through the slot's BlueprintCallable setters.
"""

import re

import unreal

from combat.graph import BEL, BGE, _assets, _must_load
from graphics_menu.umg_consts import PANEL_PADDING, UI_ART_DIR, UI_FONT

_COLOUR = re.compile(r"R=([\d.]+),G=([\d.]+),B=([\d.]+),A=([\d.]+)")


def toolset():
    cls = getattr(unreal, "UMGToolSet", None)
    if cls is None:
        raise RuntimeError("the UMGToolSet plugin is not loaded -- it is enabled "
                           "in Otherworld.uproject; restart the editor")
    return unreal.get_default_object(cls)


def _widgets(wbp):
    info = toolset().call_method("GetWidgets", (wbp,))
    return list(info.get_editor_property("widgets"))


def widget_blueprint(path):
    """The Widget Blueprint at ``path`` with an empty tree and event graph,
    created if absent.

    Emptied rather than deleted and recreated: the HUD's variables are typed
    to these classes, and a deleted class would leave them pointing at
    nothing until the HUD is rebuilt. Removing the root takes its subtree.
    """
    eas = _assets()
    if eas.does_asset_exist(path):
        wbp = eas.load_asset(path)
        # The graph first: nodes that read a widget variable stop compiling
        # the moment the tree is emptied, and the builder re-authors them.
        ed = BGE.get_graph_editor_by_name(wbp, "EventGraph")
        if ed:
            ed.remove_nodes(ed.list_all_nodes())
        for info in _widgets(wbp):
            if info.get_editor_property("parent") is None and not info.get_editor_property("inherited"):
                if not toolset().call_method("RemoveWidget", (wbp, info.get_editor_property("widget"))):
                    raise RuntimeError(f"could not empty {path}")
        left = _widgets(wbp)
        if left:
            raise RuntimeError(f"{path} still holds {len(left)} widgets after the wipe")
        return wbp
    folder, name = path.rsplit("/", 1)
    wbp = toolset().call_method("CreateWidgetBlueprint", (folder, name, unreal.UserWidget))
    if not wbp:
        raise RuntimeError(f"could not create {path}")
    return wbp


def add(wbp, cls, name, parent=None, variable=False):
    """Add a ``cls`` widget called ``name`` under ``parent`` (None: the root).

    The name is asserted: AddWidget sanitises a clashing one into Name_0,
    and the HUD finds its widgets by name.
    """
    info = toolset().call_method("AddWidget", (wbp, cls, name, parent, -1))
    w = info.get_editor_property("widget") if info else None
    if not w or str(w.get_name()) != name:
        raise RuntimeError(f"could not add {name} to {wbp.get_name()} (got {w})")
    if variable:
        toolset().call_method("ToggleWidgetAsVariable", (wbp, w, True))
    return w


def compile_and_save(wbp):
    if not toolset().call_method("CompileWidgetBlueprint", (wbp,)):
        raise RuntimeError(f"{wbp.get_name()} failed to compile")
    _assets().save_loaded_asset(wbp)
    return BEL.generated_class(wbp)


# ─── Values ──────────────────────────────────────────────────────────────────

def colour(text):
    """A pin-literal colour string, ``(R=..,G=..,B=..,A=..)``, as a LinearColor."""
    m = _COLOUR.search(text)
    if not m:
        raise ValueError(f"not a colour: {text!r}")
    return unreal.LinearColor(*(float(v) for v in m.groups()))


def slate_colour(text):
    c = unreal.SlateColor()
    c.set_editor_property("specified_color", colour(text))
    return c


def font(size, bold=False):
    f = unreal.SlateFontInfo()
    f.set_editor_property("font_object", _must_load(UI_FONT))
    f.set_editor_property("typeface_font_name", "Bold" if bold else "Regular")
    f.set_editor_property("size", float(size))
    return f


def brush(texture, size=None):
    """A brush drawing a generated UI texture stretched, like DrawTexture did."""
    b = unreal.SlateBrush()
    b.set_editor_property("resource_object", _must_load(f"{UI_ART_DIR}/{texture}"))
    b.set_editor_property("draw_as", _enum(unreal.SlateBrushDrawType, "IMAGE"))
    if size:
        # ImageSize is a DeprecateSlateVector2D, which takes no Vector2D.
        v = b.get_editor_property("image_size")
        if not v.import_text(f"(X={size[0]},Y={size[1]})"):
            raise RuntimeError(f"brush size {size} would not import")
        b.set_editor_property("image_size", v)
    return b


def _enum(enum, suffix):
    """The member of ``enum`` whose name ends with ``suffix``: the Python names
    carry the C++ prefix mangled (HAlign_Center -> H_ALIGN_CENTER)."""
    for name in dir(enum):
        if name.isupper() and (name == suffix or name.endswith("_" + suffix)):
            return getattr(enum, name)
    raise LookupError(f"{enum.__name__} has no *{suffix}: "
                      f"{[n for n in dir(enum) if n.isupper()]}")


def visibility(name):
    """ESlateVisibility by its C++ name (``Collapsed``, ``HitTestInvisible``)."""
    return _enum(unreal.SlateVisibility, re.sub(r"(?<!^)(?=[A-Z])", "_", name).upper())


# ─── Widgets ─────────────────────────────────────────────────────────────────

def text(wbp, parent, name, label, size, col, variable=False, bold=False):
    w = add(wbp, unreal.TextBlock, name, parent, variable)
    w.set_editor_property("text", unreal.Text(label))
    w.set_editor_property("font", font(size, bold))
    w.set_editor_property("color_and_opacity", slate_colour(col))
    return w


def image(wbp, parent, name, texture, size=None, variable=False):
    w = add(wbp, unreal.Image, name, parent, variable)
    w.set_editor_property("brush", brush(texture, size))
    return w


def sized(wbp, parent, name, w=None, h=None, variable=False):
    box = add(wbp, unreal.SizeBox, name, parent, variable)
    if w is not None:
        box.set_width_override(float(w))
    if h is not None:
        box.set_height_override(float(h))
    return box


def bar(wbp, parent, name, size, fill):
    """A ProgressBar on the generated track and fill art, ``size`` exactly.

    SProgressBar clips the fill brush to the percentage rather than squashing
    it, so the lit gradient keeps its shape as the bar empties.
    """
    box = sized(wbp, parent, f"{name}Box", *size)
    pb = add(wbp, unreal.ProgressBar, name, box, variable=True)
    style = pb.get_editor_property("widget_style")
    style.set_editor_property("background_image", brush("T_UI_BarTrack"))
    style.set_editor_property("fill_image", brush("T_UI_Bar"))
    pb.set_editor_property("widget_style", style)
    pb.set_editor_property("fill_color_and_opacity", colour(fill))
    pb.set_editor_property("percent", 1.0)
    return pb


def panel(wbp, parent, name, texture, min_w=None, min_h=None, variable=False,
          padding=PANEL_PADDING):
    """Panel artwork holding a vertical stack; returns (outer, stack).

    The SizeBox floors the size at the artwork's, and the panel grows past it
    when its rows need more -- the old canvas panels were fixed and had their
    heights computed by hand from the row count.
    """
    outer = add(wbp, unreal.SizeBox, name, parent, variable)
    if min_w:
        outer.set_min_desired_width(float(min_w))
    if min_h:
        outer.set_min_desired_height(float(min_h))
    border = add(wbp, unreal.Border, f"{name}Art", outer)
    border.set_editor_property("background", brush(texture))
    border.set_padding(unreal.Margin(*padding))
    stack = add(wbp, unreal.VerticalBox, f"{name}Stack", border)
    return outer, stack


def scaled(wbp, parent, name, scale):
    """A ScaleBox at a fixed ``scale``: its content is laid out bigger, so text
    is rasterised at the larger size rather than stretched."""
    box = add(wbp, unreal.ScaleBox, name, parent)
    box.set_stretch(_enum(unreal.Stretch, "USER_SPECIFIED"))
    box.set_user_specified_scale(float(scale))
    return box


def hide(w):
    w.set_editor_property("visibility", visibility("Collapsed"))


# ─── Slots: where a widget sits in its parent ────────────────────────────────

def at(w, anchor, align, pos, size=None):
    """A CanvasPanel child pinned to ``anchor`` (0..1 of the parent), its own
    ``align`` point placed ``pos`` from there. Auto-sized unless ``size``."""
    s = w.get_editor_property("slot")
    a = unreal.Anchors()
    a.set_editor_property("minimum", unreal.Vector2D(*anchor))
    a.set_editor_property("maximum", unreal.Vector2D(*anchor))
    s.set_anchors(a)
    s.set_alignment(unreal.Vector2D(*align))
    s.set_position(unreal.Vector2D(*pos))
    s.set_auto_size(size is None)
    if size is not None:
        s.set_size(unreal.Vector2D(*size))


def fill_parent(w):
    """A CanvasPanel child stretched over the whole of its parent."""
    s = w.get_editor_property("slot")
    a = unreal.Anchors()
    a.set_editor_property("minimum", unreal.Vector2D(0.0, 0.0))
    a.set_editor_property("maximum", unreal.Vector2D(1.0, 1.0))
    s.set_anchors(a)
    s.set_offsets(unreal.Margin(0.0, 0.0, 0.0, 0.0))


def pad(w, left=0.0, top=0.0, right=0.0, bottom=0.0, h=None, v=None):
    """Padding and alignment in a box or overlay slot. ``h``/``v``: Left,
    Center, Right, Fill / Top, Center, Bottom, Fill."""
    s = w.get_editor_property("slot")
    s.set_padding(unreal.Margin(left, top, right, bottom))
    if h:
        s.set_horizontal_alignment(_enum(unreal.HorizontalAlignment, h.upper()))
    if v:
        s.set_vertical_alignment(_enum(unreal.VerticalAlignment, v.upper()))


def cell(w, row, column):
    s = w.get_editor_property("slot")
    s.set_row(row)
    s.set_column(column)
