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
`assets/generated/item_icons/sheet.png` (every icon at 4x: its left half on the slot's dark, its right half on a mid tone, where
the black contour shows).

## The three steps

| step | where | reads | writes |
|---|---|---|---|
| capture (`capture.py`) | the editor | the item's Blueprint | `assets/generated/item_icons/<DisplayName>/{base,normal,mask}.png`, `depth.exr`, `view.json` |
| compose (`light.py`, `compose.py`) | outside | the passes | `assets/ui/T_UI_Icon_<DisplayName>.png`, `sheet.png` |
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
- **The look is constants:** `light.py`'s for the light (a studio shot: a warm key that
  casts shadows across the model, a cool fill, ambient closed off in the creases, the
  key's highlight and a reflection of the studio, then the levelling), `compose.py`'s for
  the fit and the thin black contour (`CONTOUR_PX`, in icon pixels). Tune them with
  `--no-editor`. The
  view and the size are per item, in `items.py`: `yaw`/`pitch` place the camera, `roll` turns
  the picture, `length` is the item's share of the slot's width.
- **Icons build after the items, and the items point at their icons.** On a fresh clone:
  build weapons and survival (they log that the icon is missing), run this, build both again.
  The capture logs a note for each item still without its `Icon`.

## The character's portrait (`portrait.py`)

The I panel's picture of the player (`T_UI_Portrait`, 256 x 512) goes through the same three
steps, named `Character` on the command line: the MetaHuman the player is drawn as
(`asset_pipeline/metahuman_paths.py`), from the front, in boxers, in the first frame of the
idle. It is the same picture whatever the player wears.

- **What stands before the camera** (`portrait_capture.py`) is `combat/metahuman_body.py`'s
  tree rebuilt from plain actors: the whole body in `MI_BodyUnderwear`, the face, the six
  grooms. No hidden mesh, no anim blueprint: nothing ticks in the capture.
- **The pose is a clip retargeted for the picture.** The idle is on the UEFN skeleton and
  reaches the body through `ABP_MetaHuman_Retarget_UEFN` every frame in the game; set on a
  spawned component that blueprint leaves the reference pose (it never updates). So
  `IDLE_CLIP` is batch-retargeted with `RTG_MetaHuman_from_UEFN` into
  `/Game/Sourced/MetaHuman/PortraitScratch`, played as a single node, and the folder is
  deleted after the shot. The clip goes into `animation_data` *before* the mesh is set:
  setting the mesh initialises the animation, which poses the body once.
- **The face is led by the body** (leader pose: the two skeletons name spine, neck and head
  alike), not by `Face_AnimBP`. Its expression is the mesh's own.
- **The grooms are in the picture, as cards and unbound.** A binding follows the skin through
  the skin cache, which nothing has filled for a face spawned in the same frame: bound, the
  hair lay at the feet. Each groom is instead moved as the head bone moved from where the
  face mesh was made. Strands never reach a G-buffer capture; what shows is each groom's
  cards.
- **Two masks mend the picture** (`part_face.png`, `part_hair.png`, written by the capture of
  each part alone; `parts.py`): the whole body is a generic one and Taro's face ends a few
  pixels off its neckline at the shoulders, a hairline of nothing the contour drew black, so
  gaps of up to `SEAM_PX` between face and body are filled from the skin beside them (whether
  the game shows the gap too was not looked at); and a groom writes
  its strand direction where a surface writes its normal, so the hair's normal is taken from
  the depth and it takes no gloss (lit as captured it came out chrome grey).
- **A new body needs a re-run** (`build_item_icons.py Character`), as a re-modelled item
  does. `build_graphics_menu.py` needs the texture: on a fresh clone run this before it.
- **Its own level, `PORTRAIT_LEVEL_TO`:** brought up to the guns' `LEVEL_TO` a body
  washes out, and left as captured it is lost on the panel's dark.
- **The names reach the capture through a file** (`paths.ONLY_PATH`), not the environment:
  an editor that is already open never sees the caller's, and `Character` alone used to
  re-capture every item.

## Traps

- **A lit capture depends on the level.** The first try used `SCS_FINAL_COLOR_LDR` and came
  out black: the forest's sun, sky light and auto-exposure all decide it, and the level
  boots at a random hour. The passes are G-buffer (base colour, world normal), which depend
  on the model alone; `light.py` does the lighting.
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
  grey. It suits the dark slot; a darker steel needs the metallic channel, and a
  post-process material does not get it (below).
- **The FPS bundle's guns are near-black, and so is the slot.** Hence the levelling
  (`LEVEL_TO`); without it the pistol and the shotgun disappear. The contour is black, so
  it does not help there: it holds the shape where the slot is drawn over the world.
- **Level before the gloss goes on.** The highlight and the reflection are added after the
  gain; multiplied by a near-black model's gain (the wood's, x6) they turned it to chrome.
- **The shape comes from the depth pass,** `SCS_SCENE_COLOR_SCENE_DEPTH` into an
  `RTF_RGBA32F` target: the alpha is the distance in cm. A float target is exported as an
  EXR whatever the file is called, and an 8-bit or `R32F` one as a PNG clamped at 1 (all
  white). `exr.py` reads it: Pillow cannot.
- **The scene's depth is a half float,** so its step grows with the distance: 0.125 cm from
  128 cm on. The camera stands as close as clears the model (`CAMERA_RADII`); it is
  orthographic, so the distance changes nothing else.
- **The wait before the capture covers only what has been asked for.** The first model of
  a run came out in the default material (the pistol, one flat grey) until a capture that
  is thrown away came before the wait.
- **A post-process material on the capture is ignored** (tried for the metallic and
  roughness channels: `add_or_update_blendable`, a transient material and an asset, after
  and replacing the tonemapper, all three final-colour sources). The picture came back
  the lit scene every time. So every surface is lit as a dielectric.
- **Reduce with the colour premultiplied** (`convert("RGBa")`), or the capture's black
  background bleeds into the outline.
- **`build_ui_art.py` must not write `T_UI_Icon_*`.** It shares `assets/ui/` and would
  overwrite the renders; its icon drawings were removed for that reason.

## Verifying

- `verify_graphics_menu.py` (`checks.py`): every item's texture is imported (128 x 64, UI
  group, no mips), is the item's own `Icon`, and the item's `SlotColor` is white.
- `light.py` refuses a model that covers under 2% of its capture, and `compose.py` an icon that
  has fewer than 24 shades: an empty or flat picture never reaches the game.
- The portrait: imported the same way, 256 x 512 (`checks.py`); the widget and its gate are
  `graphics_menu/wear_checks.py`'s.
- By eye: `sheet.png`, and `assets/ui/T_UI_Portrait.png`.
