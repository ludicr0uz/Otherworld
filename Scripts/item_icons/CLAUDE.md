# Item icons — Claude quick reference

An item's inventory icon is a picture of its own 3D model. Nothing is drawn by hand.

```bash
python3 Scripts/build_item_icons.py              # capture, compose, import: every item
python3 Scripts/build_item_icons.py Axe Wood     # only these
python3 Scripts/build_item_icons.py Character    # the I panel's portrait alone
python3 Scripts/build_item_icons.py --no-editor  # compose again from the passes on disk
```

Run it **outside** the editor: the compose step needs Pillow and numpy. It calls `uepy.py`
itself for the two editor steps. Look at the result in
`assets/generated/item_icons/sheet.png` (every icon at 4x on the slot's dark).

## The three steps

| step | where | reads | writes |
|---|---|---|---|
| capture (`capture.py`) | the editor | the item's Blueprint | `assets/generated/item_icons/<DisplayName>/{base,normal,mask}.png`, `view.json` |
| compose (`compose.py`) | outside | the passes | `assets/ui/T_UI_Icon_<DisplayName>.png`, `sheet.png` |
| import (`asset_pipeline/import_ui_art.py`) | the editor | `assets/ui/*.png` | `/Game/UI/Art` |

## Rules

- **Adding an item:** one row in `items.py` (DisplayName, Blueprint, view, `length`). Its
  builder sets `Icon` with `combat.weapon_specs._weapon_icon(display)` and `SlotColor` to
  `ICON_TINT`. Then run the script, and the item's build again if it was built first.
- **The icon follows the Blueprint, not a mesh path.** The capture spawns the item and shows
  only it, so whatever its builder hung on it is in the picture (the sniper's scope, a
  model's scale). An item given a new model needs only a re-run.
- **The HUD draws an icon untinted.** The slot and the loot row still tint by the item's
  `SlotColor`, so every item's is white (`ICON_TINT`). The white silhouettes these replaced
  were coloured by that tint; a colour there now would stain the render.
- **The look is `compose.py`'s constants** (light direction, levelling, the pale edge). The
  view and the size are per item, in `items.py`: `yaw`/`pitch` place the camera, `roll` turns
  the picture, `length` is the item's share of the slot's width.
- **Icons build after the items, and the items point at their icons.** On a fresh clone:
  build weapons and survival (they log that the icon is missing), run this, build both again.
  The capture logs a note for each item still without its `Icon`.

## The character's portrait (`portrait.py`)

The I panel's picture of the player (`T_UI_Portrait`, 256 x 512) goes through the same three
steps, named `Character` on the command line: the body the player wears
(`asset_pipeline/player_body.py`), from the front, in the first frame of its idle clip.

- **A new body needs a re-run** (`build_item_icons.py Character`), as a re-modelled item
  does. `build_graphics_menu.py` needs the texture: on a fresh clone run this before it.
- **Its own level, `PORTRAIT_LEVEL_TO`:** brought up to the guns' `LEVEL_TO` a clothed body
  washes out, and left as captured it is lost on the panel's dark.
- **Nothing ticks an animation in the capture,** so a clip set on the spawned component
  leaves the bind pose (arms out). The clip goes into `animation_data` *before* the mesh is
  set: setting the mesh initialises the animation, which poses the body once.

## Traps

- **A lit capture depends on the level.** The first try used `SCS_FINAL_COLOR_LDR` and came
  out black: the forest's sun, sky light and auto-exposure all decide it, and the level
  boots at a random hour. The passes are G-buffer (base colour, world normal), which depend
  on the model alone; `compose.py` does the lighting.
- **The first capture of a model is the default checker material** while its shaders
  compile and its textures stream. `AutomationLibrary.finish_loading_before_screenshot()`
  before the capture waits for both.
- **`set_editor_property("show_only_actors", …)` on the capture component raises "cannot be
  edited on templates".** Call `show_only_actor_components(actor)`.
- **The alpha is the scene-colour pass's, inverted:** `SCS_SCENE_COLOR_HDR` into an RGBA8
  target leaves 0 on the model and 255 off it. The base-colour and normal passes have no
  alpha at all.
- **An RGBA8 render target is linear.** Base colour comes out linear, and compose encodes
  to sRGB at the end.
- **Metals come out pale.** A metallic material's base colour is its reflectance, and no
  capture source gives the metallic channel, so the AK's and the SMG's steel reads as light
  grey. It suits the dark slot; a darker steel needs a post-process material that writes
  `SceneTexture:Metallic`.
- **The FPS bundle's guns are near-black, and so is the slot.** Hence the levelling
  (`LEVEL_TO`) and the pale edge; without them the pistol and the shotgun disappear.
- **Reduce with the colour premultiplied** (`convert("RGBa")`), or the capture's black
  background bleeds into the outline.
- **`build_ui_art.py` must not write `T_UI_Icon_*`.** It shares `assets/ui/` and would
  overwrite the renders; its icon drawings were removed for that reason.

## Verifying

- `verify_graphics_menu.py` (`checks.py`): every item's texture is imported (128 x 64, UI
  group, no mips), is the item's own `Icon`, and the item's `SlotColor` is white.
- `compose.py` refuses to write an icon whose model covers under 2% of its capture or that
  has fewer than 24 shades: an empty or flat picture never reaches the game.
- The portrait: imported the same way, 256 x 512 (`checks.py`); the widget and its gate are
  `graphics_menu/wear_checks.py`'s.
- By eye: `sheet.png`, and `assets/ui/T_UI_Portrait.png`.
