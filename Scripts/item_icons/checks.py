"""What the verifier holds the icons to (verify_graphics_menu.py calls it, as
it checks the rest of the HUD's artwork): every item has its own texture,
imported the way UI art must be, and draws it untinted.

That a texture is a shaded picture of the model, and not an empty frame, is
compose.py's own check: it refuses to write one that is not.
"""

import unreal

from item_icons.items import ICON_H, ICON_TINT, ICON_W, ITEMS, UI_ART_DIR, icon_name
from item_icons.portrait import PORTRAIT_H, PORTRAIT_TEXTURE, PORTRAIT_W


def _texture(item):
    return unreal.EditorAssetLibrary.load_asset(f"{UI_ART_DIR}/{icon_name(item.display)}")


def _texture_fault(tex, want=(ICON_W, ICON_H)):
    if not tex:
        return "not imported"
    size = (tex.blueprint_get_size_x(), tex.blueprint_get_size_y())
    if size != want:
        return f"{size[0]} x {size[1]}"
    if tex.get_editor_property("lod_group") != unreal.TextureGroup.TEXTUREGROUP_UI:
        return "not in the UI texture group"
    if tex.get_editor_property("mip_gen_settings") != unreal.TextureMipGenSettings.TMGS_NO_MIPMAPS:
        return "has mipmaps"
    return ""


def _item_fault(item):
    cls = unreal.load_object(None, f"{item.blueprint}.{item.blueprint.rsplit('/', 1)[1]}_C")
    if not cls:
        return "not built"
    cdo = unreal.get_default_object(cls)
    if cdo.get_editor_property("Icon") != _texture(item) or not _texture(item):
        return "its Icon is not its own texture"
    tint = cdo.get_editor_property("SlotColor")
    if (tint.r, tint.g, tint.b, tint.a) != ICON_TINT + (1.0,):
        return f"tinted {tint.to_tuple()}"
    return ""


def check_item_icons(check):
    wrong = [f"{i.display}: {f}" for i in ITEMS for f in [_texture_fault(_texture(i))] if f]
    check(f"...and so is every item's icon: {len(ITEMS)} textures, {ICON_W} x {ICON_H}, "
          "UI group, no mips", not wrong, "; ".join(wrong))
    wrong = [f"{i.display}: {f}" for i in ITEMS for f in [_item_fault(i)] if f]
    check("every item shows its own icon (T_UI_Icon_<DisplayName>, the render of "
          "its model), untinted: its SlotColor is white", not wrong, "; ".join(wrong))
    fault = _texture_fault(
        unreal.EditorAssetLibrary.load_asset(f"{UI_ART_DIR}/{PORTRAIT_TEXTURE}"),
        (PORTRAIT_W, PORTRAIT_H))
    check(f"the character's portrait is imported the same way: {PORTRAIT_TEXTURE}, "
          f"{PORTRAIT_W} x {PORTRAIT_H}", not fault, fault)
