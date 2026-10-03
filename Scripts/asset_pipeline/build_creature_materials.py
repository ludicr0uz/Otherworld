"""build_creature_materials.py -- give the Meshy monsters their PBR skin.

Editor-side.  Run through the usual harness, after import_characters.py:

    python3 Scripts/dev/uepy.py --cold Scripts/asset_pipeline/build_creature_materials.py

── Why this exists ─────────────────────────────────────────────────────────

Meshy's refine stage was run with ``enable_pbr`` on, so every monster ships a
full PBR set.  Exactly ONE map reaches the game on its own: the rigged FBX
embeds ``texture_0`` -- the base colour -- and the importer builds a material
with that single map plugged into Base Color.  A monster with no normal map
has no skin detail at grazing angles, and one with no roughness map is
uniformly shiny, which is the "shades like plastic" failure enable_pbr existed
to prevent.  So the maps are imported here explicitly and wired into a real
master material.

── WHICH maps, and why it is not the obvious ones ──────────────────────────

The pipeline is preview -> refine -> remesh -> rig, and **remesh re-lays the
UVs**.  The rigger caps at 320k faces, the refine mesh is 724k, so the model
that actually ships is the remeshed one -- with a completely different UV
atlas from the mesh the refine stage textured.

That matters because the files sitting in ``<id>/textures/`` are a mixture:

    <id>_base_color.png          refine stage   -- WRONG UVs
    <id>_normal.png              refine stage   -- WRONG UVs
    <id>_roughness.png           refine stage   -- WRONG UVs, and superseded
    <id>_metallic.png            refine stage   -- WRONG UVs, and superseded
    <id>_metallic_roughness.png  remesh stage   -- correct

They all have the same filename shape and the same average colour, so wiring
up the wrong ones produces a monster that is textured, plausibly lit, and
subtly scrambled -- the failure mode reads as "one flat texture over the whole
model" rather than as an error.  Measured on zombie_01, refine base colour vs
remesh base colour differs by a mean of 30-40 per channel while the mean
colour differs by under 3: same paint, different atlas.

The complete, correct set is embedded in ``<id>_remesh.glb`` as three images
-- ``texture_0``, ``normal`` and ``texture_0_metallic_roughness`` -- so that is
what this script extracts and imports.  Two facts make it safe to treat the
remesh maps as the rigged mesh's maps: the remesh GLB's ``texture_0`` is
BYTE-IDENTICAL to the rigged GLB's, so rigging preserves the remesh UVs; and
the remesh GLB's packed map is byte-identical to the ``metallic_roughness.png``
already on disk.  Only the base colour and normal were ever wrong.

── Channel packing, measured rather than assumed ───────────────────────────

The packed map follows the glTF convention, confirmed by
differencing it against the separate maps for zombie_01 (mean |delta| per
channel, 0-255):

    channel   vs roughness.png   vs metallic.png
      R            94.5              246.8
      G            17.7              154.4      <- roughness
      B           159.8                0.4      <- metallic

G is roughness, B is metallic, and R is ambient occlusion (mean 247, i.e.
near-unoccluded).  One packed texture therefore replaces three samplers, which
is why the separate roughness/metallic PNGs are left in the cache unused.
Metallic reads a mean of 0.1/255 -- flesh is not metal -- but it is wired
anyway so a future armoured or wet creature needs no material change.

── Quality scaling ─────────────────────────────────────────────────────────

Every texture is put in a character LOD group.  That is the whole mechanism:
Unreal's ``sg.TextureQuality`` scalability setting applies a per-LOD-group mip
bias, so a monster texture in TEXTUREGROUP_Character drops a mip on Medium and
two on Low without this script, the material, or the mesh knowing anything
about it.  A texture left in TEXTUREGROUP_World -- which is what an
FBX-embedded import defaults to -- silently opts out of that.

``MAX_TEXTURE_SIZE`` clamps the 4k sources at import.  The catalog generates at
4k deliberately ("Unreal can clamp a 4k source down ... but it cannot invent
detail that was never generated") and names 2k as the ship-time value; this is
where that intent is applied.  It is a ceiling, not a floor: TextureQuality
still scales below it.
"""

import json
import os
import struct

import unreal

PROJECT_DIR = unreal.Paths.project_dir()
CACHE_ROOT = os.path.join(PROJECT_DIR, "assets", "cache", "meshy")
DEST_ROOT = "/Game/Sourced/Characters"
MATERIAL_DIR = f"{DEST_ROOT}/Materials"
MASTER_PATH = f"{MATERIAL_DIR}/M_MeshyCreature"

# The catalog generates at 4k and names 2k as the ship-time value.  Applied at
# import as a hard ceiling; sg.TextureQuality biases down from here.
MAX_TEXTURE_SIZE = 2048
# Occlusion and the two scalar channels carry far less detail than the colour
# and normal, so the packed map is clamped harder.
MAX_ORM_SIZE = 1024

# image name inside <id>_remesh.glb -> (asset suffix, srgb, compression,
#                                        lod group, size clamp)
MAPS = (
    ("texture_0", "BaseColor", True,
     unreal.TextureCompressionSettings.TC_DEFAULT,
     unreal.TextureGroup.TEXTUREGROUP_CHARACTER, MAX_TEXTURE_SIZE),
    ("normal", "Normal", False,
     unreal.TextureCompressionSettings.TC_NORMALMAP,
     unreal.TextureGroup.TEXTUREGROUP_CHARACTER_NORMAL_MAP, MAX_TEXTURE_SIZE),
    ("texture_0_metallic_roughness", "ORM", False,
     unreal.TextureCompressionSettings.TC_MASKS,
     unreal.TextureGroup.TEXTUREGROUP_CHARACTER_SPECULAR, MAX_ORM_SIZE),
)

# Where the extracted PNGs are parked.  A sibling of textures/ rather than a
# file in it: the names would otherwise collide with the refine-stage maps that
# caused this bug, and the whole point is that the two sets stay separable.
REMESH_TEX_SUBDIR = "textures_remesh"

# Meshy names every export's material Material_1 and its texture texture_0.
# Once the mesh wears a real instance these are unreferenced dead weight --
# and texture_0 is a 4k base colour in TEXTUREGROUP_World, i.e. precisely the
# unscalable texture this script exists to replace. Meshy's exports since
# October 2026 (adventurer_02) name them BakedMaterial and its _baseColor.
GENERIC_LEFTOVERS = ("Material_1", "texture_0",
                     "BakedMaterial", "BakedMaterial_baseColor")


def _log(msg):
    # print() is not captured in a cold -ExecutePythonScript run; the log is.
    unreal.log_warning(f"[MAT] {msg}")


def _specs():
    """Cached monsters, read the same way import_characters.py reads them."""
    out = []
    if not os.path.isdir(CACHE_ROOT):
        return out
    for sid in sorted(os.listdir(CACHE_ROOT)):
        state = os.path.join(CACHE_ROOT, sid, "task.json")
        if os.path.exists(state):
            with open(state) as fh:
                out.append(json.load(fh))
    return out


def _monster_dir(spec):
    return f"{DEST_ROOT}/{os.path.basename(spec.get('dest', spec['id']))}"


def _monster_name(spec):
    return os.path.basename(spec.get("dest", spec["id"]))


# ─── Textures ───────────────────────────────────────────────────────────────

def import_texture(png, dest_dir, asset_name, srgb, compression, group, max_size):
    """Import one PNG and configure it for its role.

    replace_existing keeps this idempotent: a second run re-imports over the
    same asset rather than minting Texture_1 beside it.
    """
    task = unreal.AssetImportTask()
    task.filename = png
    task.destination_path = dest_dir
    task.destination_name = asset_name
    task.replace_existing = True
    task.automated = True
    task.save = True
    task.options = unreal.TextureFactory()
    unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])

    path = f"{dest_dir}/{asset_name}"
    tex = unreal.EditorAssetLibrary.load_asset(path)
    if not tex:
        _log(f"  FAILED to import {os.path.basename(png)}")
        return None

    # Order matters: srgb must be set before compression on a normal map, or
    # the engine re-derives it and the map comes out washed out.
    tex.set_editor_property("srgb", srgb)
    tex.set_editor_property("compression_settings", compression)
    tex.set_editor_property("lod_group", group)
    tex.set_editor_property("max_texture_size", max_size)
    if compression == unreal.TextureCompressionSettings.TC_MASKS:
        # A packed map is three unrelated scalars. Treating it as colour would
        # let the compressor trade precision between them.
        tex.set_editor_property("compression_no_alpha", True)
    unreal.EditorAssetLibrary.save_asset(path)
    _log(f"  {asset_name:22s} {'sRGB' if srgb else 'linear':6s} "
         f"clamp {max_size} {group.name}")
    return tex


def _glb_images(path):
    """Every embedded image in a .glb, as {name: png bytes}.

    Hand-parsed rather than pulled in as a dependency: a GLB is a 12-byte
    header, a JSON chunk and a binary chunk, and the images are byte ranges
    into the second one.  The editor's Python has no glTF library and this is
    twenty lines.
    """
    with open(path, "rb") as fh:
        blob = fh.read()
    if blob[:4] != b"glTF":
        raise RuntimeError(f"{path} is not a GLB")
    json_len = struct.unpack("<I", blob[12:16])[0]
    doc = json.loads(blob[20:20 + json_len])
    bin_start = 20 + json_len
    bin_len = struct.unpack("<I", blob[bin_start:bin_start + 4])[0]
    bin_chunk = blob[bin_start + 8: bin_start + 8 + bin_len]

    views = doc.get("bufferViews", [])
    out = {}
    for i, img in enumerate(doc.get("images", [])):
        if "bufferView" not in img:
            continue
        view = views[img["bufferView"]]
        off = view.get("byteOffset", 0)
        out[img.get("name") or f"image_{i}"] = bin_chunk[off: off + view["byteLength"]]
    return out


def extract_remesh_maps(spec):
    """Unpack the remesh GLB's textures to disk so the importer can read them.

    Written once and reused: the GLB is ~50 MB and re-extracting it on every
    run would dominate the script's runtime for no gain.  Keyed on existence
    rather than a hash because the cache is immutable once fetched.
    """
    sid = spec["id"]
    glb = os.path.join(CACHE_ROOT, sid, f"{sid}_remesh.glb")
    out_dir = os.path.join(CACHE_ROOT, sid, REMESH_TEX_SUBDIR)
    wanted = {img for img, _, _, _, _, _ in MAPS}

    have = {img: os.path.join(out_dir, f"{sid}_{img}.png")
            for img in wanted
            if os.path.exists(os.path.join(out_dir, f"{sid}_{img}.png"))}
    if set(have) == wanted:
        return have

    if not os.path.exists(glb):
        _log(f"{sid}: no {os.path.basename(glb)} in cache -- "
             "cannot recover the remeshed UVs' textures")
        return have

    os.makedirs(out_dir, exist_ok=True)
    images = _glb_images(glb)
    for img in sorted(wanted):
        if img in have:
            continue
        if img not in images:
            _log(f"{sid}: {os.path.basename(glb)} has no image {img!r} "
                 f"(it has {sorted(images)})")
            continue
        dest = os.path.join(out_dir, f"{sid}_{img}.png")
        with open(dest, "wb") as fh:
            fh.write(images[img])
        have[img] = dest
        _log(f"{sid}: extracted {img} ({len(images[img]) / 1e6:.1f} MB) "
             f"from the remesh GLB")
    return have


def import_maps(spec):
    """Every PBR map for one monster, keyed by its role.

    Sourced from the remesh GLB, not from textures/ -- see the module
    docstring.  The refine-stage PNGs in textures/ are atlased for a mesh that
    was thrown away before rigging.
    """
    sid = spec["id"]
    sources = extract_remesh_maps(spec)
    if not sources:
        _log(f"{sid}: no remesh textures -- nothing to wire")
        return {}

    dest_dir = _monster_dir(spec)
    name = _monster_name(spec).replace("SKM_", "")
    out = {}
    for img, role, srgb, compression, group, max_size in MAPS:
        png = sources.get(img)
        if not png:
            _log(f"{sid}: MISSING {img} -- "
                 f"{role} will fall back to the master default")
            continue
        tex = import_texture(png, dest_dir, f"T_{name}_{role}",
                             srgb, compression, group, max_size)
        if tex:
            out[role] = tex
    return out


# ─── Master material ────────────────────────────────────────────────────────

def _expr(mat, cls, x, y):
    return unreal.MaterialEditingLibrary.create_material_expression(mat, cls, x, y)


def build_master(defaults):
    """One material for every creature; per-monster differences are instances.

    ``defaults`` maps each texture parameter name to the Texture2D that stands
    in when nothing overrides it.  It is not cosmetic: a TextureSampleParameter
    with a null texture is a **compile error**, and a master material that
    fails to compile is silently replaced by the engine's grey default on every
    instance beneath it -- which is exactly how every monster ended up grey.
    The defaults come from a real monster rather than /Engine, so each one also
    matches its sampler's expected colour space and compression.

    Built from scratch each run rather than patched: a material graph edited in
    place accumulates orphaned nodes, and this asset has no hand edits worth
    preserving -- everything variable about it is a parameter.
    """
    mel = unreal.MaterialEditingLibrary
    unreal.EditorAssetLibrary.make_directory(MATERIAL_DIR)

    # Deleted and recreated rather than cleared in place.
    # delete_all_material_expressions does not leave an empty graph behind: the
    # node count crept up across rebuilds (10, then 11, then 12) before settling,
    # so something survives the clear. Nothing here is hand-authored, and the
    # instances are re-parented immediately below, so starting from an empty
    # asset is both safe and the only way the output is a function of the input
    # alone.
    if unreal.EditorAssetLibrary.does_asset_exist(MASTER_PATH):
        if not unreal.EditorAssetLibrary.delete_asset(MASTER_PATH):
            raise RuntimeError(f"could not delete {MASTER_PATH} to rebuild it")
    mat = unreal.AssetToolsHelpers.get_asset_tools().create_asset(
        "M_MeshyCreature", MATERIAL_DIR, unreal.Material,
        unreal.MaterialFactoryNew())
    if not mat:
        raise RuntimeError(f"could not create {MASTER_PATH}")

    # ── Base colour: texture * tint ──────────────────────────────────────────
    # The tint is what lets a second zombie be greyer than the first without
    # regenerating a 4k texture, and costs one instruction.
    base = _expr(mat, unreal.MaterialExpressionTextureSampleParameter2D, -800, -300)
    base.set_editor_property("parameter_name", "BaseColor")
    base.set_editor_property("texture", defaults["BaseColor"])
    base.set_editor_property("sampler_type", unreal.MaterialSamplerType.SAMPLERTYPE_COLOR)

    tint = _expr(mat, unreal.MaterialExpressionVectorParameter, -800, 0)
    tint.set_editor_property("parameter_name", "Tint")
    tint.set_editor_property("default_value", unreal.LinearColor(1.0, 1.0, 1.0, 1.0))

    tinted = _expr(mat, unreal.MaterialExpressionMultiply, -450, -250)
    mel.connect_material_expressions(base, "RGB", tinted, "A")
    mel.connect_material_expressions(tint, "", tinted, "B")
    mel.connect_material_property(tinted, "", unreal.MaterialProperty.MP_BASE_COLOR)

    # ── Normal ───────────────────────────────────────────────────────────────
    norm = _expr(mat, unreal.MaterialExpressionTextureSampleParameter2D, -800, 300)
    norm.set_editor_property("parameter_name", "Normal")
    norm.set_editor_property("texture", defaults["Normal"])
    norm.set_editor_property("sampler_type", unreal.MaterialSamplerType.SAMPLERTYPE_NORMAL)
    mel.connect_material_property(norm, "RGB", unreal.MaterialProperty.MP_NORMAL)

    # ── Packed occlusion / roughness / metallic ──────────────────────────────
    # Channel assignment is measured, not assumed -- see the module docstring.
    orm = _expr(mat, unreal.MaterialExpressionTextureSampleParameter2D, -800, 700)
    orm.set_editor_property("parameter_name", "ORM")
    orm.set_editor_property("texture", defaults["ORM"])
    orm.set_editor_property("sampler_type", unreal.MaterialSamplerType.SAMPLERTYPE_MASKS)

    # Roughness gets a scalar trim. Meshy's roughness reads a little flat on
    # skin, and this is the one knob an artist reaches for first; exposing it
    # here means doing so never requires touching the graph.
    rough_scale = _expr(mat, unreal.MaterialExpressionScalarParameter, -800, 1000)
    rough_scale.set_editor_property("parameter_name", "RoughnessScale")
    rough_scale.set_editor_property("default_value", 1.0)
    rough = _expr(mat, unreal.MaterialExpressionMultiply, -450, 700)
    mel.connect_material_expressions(orm, "G", rough, "A")
    mel.connect_material_expressions(rough_scale, "", rough, "B")
    mel.connect_material_property(rough, "", unreal.MaterialProperty.MP_ROUGHNESS)

    mel.connect_material_property(orm, "B", unreal.MaterialProperty.MP_METALLIC)
    mel.connect_material_property(orm, "R",
                                  unreal.MaterialProperty.MP_AMBIENT_OCCLUSION)

    # Skeletal meshes are a separate shader permutation from static ones; a
    # master material that has never been used on one will not compile for it.
    empty = [n for n, e in (("BaseColor", base), ("Normal", norm), ("ORM", orm))
             if not e.get_editor_property("texture")]
    if empty:
        raise RuntimeError(
            f"{MASTER_PATH}: samplers with no default texture: {empty}. "
            "The material would fail to compile and every monster would be grey.")

    mel.set_material_usage(mat, unreal.MaterialUsage.MATUSAGE_SKELETAL_MESH)
    mel.recompile_material(mat)
    unreal.EditorAssetLibrary.save_asset(MASTER_PATH)
    _log(f"master {MASTER_PATH} "
         f"({mel.get_num_material_expressions(mat)} nodes)")
    return mat


# ─── Per-monster instance ───────────────────────────────────────────────────

def build_instance(spec, master, maps):
    mel = unreal.MaterialEditingLibrary
    name = _monster_name(spec).replace("SKM_", "")
    path = f"{_monster_dir(spec)}/MI_{name}"

    mi = unreal.EditorAssetLibrary.load_asset(path)
    if not mi:
        mi = unreal.AssetToolsHelpers.get_asset_tools().create_asset(
            f"MI_{name}", _monster_dir(spec), unreal.MaterialInstanceConstant,
            unreal.MaterialInstanceConstantFactoryNew())
    if not mi:
        _log(f"{spec['id']}: could not create {path}")
        return None

    mel.set_material_instance_parent(mi, master)
    for role, tex in maps.items():
        mel.set_material_instance_texture_parameter_value(mi, role, tex)
    unreal.EditorAssetLibrary.save_asset(path)
    _log(f"{spec['id']}: {path} <- {', '.join(sorted(maps))}")
    return mi


def assign_to_mesh(spec, mi):
    """Point every material slot on the monster's mesh at its instance.

    Meshy exports a single slot, but writing the whole array rather than
    slot 0 means a future multi-material creature does not silently keep an
    FBX-default material on slots 1+.
    """
    mesh_path = f"{_monster_dir(spec)}/{_monster_name(spec)}"
    mesh = unreal.EditorAssetLibrary.load_asset(mesh_path)
    if not mesh:
        _log(f"{spec['id']}: no mesh at {mesh_path}")
        return False

    slots = list(mesh.get_editor_property("materials"))
    for slot in slots:
        slot.set_editor_property("material_interface", mi)
    mesh.set_editor_property("materials", slots)
    unreal.EditorAssetLibrary.save_asset(mesh_path)
    _log(f"{spec['id']}: {len(slots)} slot(s) on {_monster_name(spec)} -> {mi.get_name()}")
    return True


def sweep_generic(specs):
    """Drop the FBX-default material and texture once nothing points at them.

    Two things make this a separate pass rather than a step inside the
    per-monster loop.  It has to run after the meshes are saved, because the
    asset registry answers ``find_package_referencers_for_asset`` from what is
    on disk and reports the mesh as still wearing Material_1 until then.  And
    the leftovers form a chain -- Material_1 samples texture_0 -- so texture_0
    only becomes collectable once Material_1 is gone; within a single run the
    registry still lists the just-deleted material as a referencer, which is
    why a referencer that no longer exists is not counted as one.

    Guarded on the referencer check rather than deleted outright: if the slot
    reassignment failed for any reason the mesh is still wearing them, and
    deleting would leave it with no material at all.
    """
    for _pass in range(len(GENERIC_LEFTOVERS)):
        progress = False
        for spec in specs:
            for leftover in GENERIC_LEFTOVERS:
                path = f"{_monster_dir(spec)}/{leftover}"
                if not unreal.EditorAssetLibrary.does_asset_exist(path):
                    continue
                live = [r for r in
                        unreal.EditorAssetLibrary.find_package_referencers_for_asset(path, False)
                        if unreal.EditorAssetLibrary.does_asset_exist(str(r))]
                if live:
                    continue
                if unreal.EditorAssetLibrary.delete_asset(path):
                    _log(f"{spec['id']}: swept {leftover}")
                    progress = True
        if not progress:
            break

    for spec in specs:
        for leftover in GENERIC_LEFTOVERS:
            path = f"{_monster_dir(spec)}/{leftover}"
            if unreal.EditorAssetLibrary.does_asset_exist(path):
                refs = unreal.EditorAssetLibrary.find_package_referencers_for_asset(path, False)
                _log(f"{spec['id']}: kept {leftover}, still referenced by {len(refs)}")


# ─── Verification ───────────────────────────────────────────────────────────

def verify(specs):
    """Check the thing that actually matters: what the MESH renders with.

    An instance that exists and a mesh that uses it are different claims, and
    the earlier version of this pipeline satisfied the first while failing the
    second for both monsters at once.
    """
    mel = unreal.MaterialEditingLibrary
    ok = True
    _log("================ verify ================")
    for spec in specs:
        sid = spec["id"]
        mesh = unreal.EditorAssetLibrary.load_asset(
            f"{_monster_dir(spec)}/{_monster_name(spec)}")
        if not mesh:
            _log(f"  {sid}: FAIL no mesh")
            ok = False
            continue

        slots = mesh.get_editor_property("materials")
        bound = [s.get_editor_property("material_interface") for s in slots]
        if not bound or any(b is None for b in bound):
            _log(f"  {sid}: FAIL an empty material slot")
            ok = False
            continue

        for mi in bound:
            if not isinstance(mi, unreal.MaterialInstanceConstant):
                _log(f"  {sid}: FAIL slot holds {type(mi).__name__}, not an instance")
                ok = False
                continue
            parent = mi.get_editor_property("parent")
            if not parent or parent.get_path_name().split(".")[0] != MASTER_PATH:
                _log(f"  {sid}: FAIL {mi.get_name()} parent is {parent}")
                ok = False

            missing = []
            for role in ("BaseColor", "Normal", "ORM"):
                tex = mel.get_material_instance_texture_parameter_value(mi, role)
                if not tex:
                    missing.append(role)
            if missing:
                _log(f"  {sid}: FAIL {mi.get_name()} has no {', '.join(missing)}")
                ok = False
                continue

            # Two monsters sharing a texture is the exact failure that made the
            # zombie and the wendigo wear one skin, so it is checked by identity
            # rather than trusted to the folder layout.
            names = {role: mel.get_material_instance_texture_parameter_value(mi, role).get_name()
                     for role in ("BaseColor", "Normal", "ORM")}
            _log(f"  {sid}: ok  {mi.get_name()}  "
                 + "  ".join(f"{r}={n}" for r, n in names.items()))

    # cross-monster texture collision
    seen = {}
    for spec in specs:
        mesh = unreal.EditorAssetLibrary.load_asset(
            f"{_monster_dir(spec)}/{_monster_name(spec)}")
        if not mesh:
            continue
        for slot in mesh.get_editor_property("materials"):
            mi = slot.get_editor_property("material_interface")
            if not isinstance(mi, unreal.MaterialInstanceConstant):
                continue
            for role in ("BaseColor", "Normal", "ORM"):
                tex = mel.get_material_instance_texture_parameter_value(mi, role)
                if not tex:
                    continue
                key = (role, tex.get_path_name())
                if key in seen and seen[key] != spec["id"]:
                    _log(f"  FAIL {spec['id']} and {seen[key]} share {role} "
                         f"{tex.get_name()}")
                    ok = False
                seen[key] = spec["id"]

    _log("all monsters wear their own PBR skin" if ok
         else "CHECKS FAILED -- see above")
    return ok


def _existing_maps(spec):
    """The textures an earlier run imported for a character, keyed by role."""
    name = _monster_name(spec).replace("SKM_", "")
    out = {}
    for _img, role, *_rest in MAPS:
        tex = unreal.EditorAssetLibrary.load_asset(f"{_monster_dir(spec)}/T_{name}_{role}")
        if tex:
            out[role] = tex
    return out


def main(only=None):
    """Every cached character, or just the ids in ``only`` (as import_characters).

    ``only`` limits the texture import, never the instances: the master is
    deleted and recreated each run, and an instance left out of the re-parent
    loses its parent and renders the engine's grey default. That is how
    adding adventurer_02 greyed the player and both monsters.
    """
    unreal.AssetRegistryHelpers.get_asset_registry().wait_for_completion()
    every = _specs()
    specs = [s for s in every if not only or s["id"] in only]
    if not specs:
        _log(f"nothing cached under {CACHE_ROOT} -- run fetch_monsters.py first")
        return

    # Textures first: the master needs a real one per sampler as its default.
    imported = []
    for spec in specs:
        _log(f"--- {spec['id']} ---")
        maps = import_maps(spec)
        if maps:
            imported.append((spec, maps))

    defaults = next((m for _, m in imported
                     if all(k in m for k in ("BaseColor", "Normal", "ORM"))), None)
    if not defaults:
        _log("no monster has a full map set -- cannot build the master material")
        return

    master = build_master(defaults)
    fresh = {spec["id"] for spec, _ in imported}
    imported += [(spec, _existing_maps(spec)) for spec in every
                 if spec["id"] not in fresh]
    for spec, maps in imported:
        if not maps:
            continue
        mi = build_instance(spec, master, maps)
        if mi:
            assign_to_mesh(spec, mi)

    # Save before sweeping: the referencer check reads what is on disk, and an
    # unsaved mesh still claims to be wearing the material about to be deleted.
    unreal.EditorAssetLibrary.save_directory(DEST_ROOT, only_if_is_dirty=False)
    sweep_generic(specs)
    verify(every)


if __name__ == "__main__":
    main()
