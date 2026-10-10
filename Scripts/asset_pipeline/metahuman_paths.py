"""metahuman_paths -- where the player's MetaHuman is, and what it is made
of.  Constants only (no ``unreal``): the host-side copier, the editor-side
rig builder and combat/skin.py all read the same names.

The character is the sample's Taro (import_metahuman.py).  His blueprint is
not used: the component set below is BP_Taro's, read off it once
(2026-10-07) and spawned by combat/skin.py under the player's mannequin.
"""

CHARACTER = "Taro"
ROOT = f"/Game/MetaHumans/{CHARACTER}"
COMMON = "/Game/MetaHumans/Common"

# The body, on the MetaHuman skeleton, with the sample's ragdoll physics asset.
BODY_MESH = f"{ROOT}/Body/m_med_nrw_body"
BODY_SKELETON = f"{COMMON}/Female/Medium/NormalWeight/Body/metahuman_base_skel"
BODY_PHYSICS = f"{COMMON}/Male/Medium/NormalWeight/Body/m_med_nrw_ragdoll"

# BODY_MESH is Taro's body as he is dressed: the skin under his hoodie, jeans
# and shoes is cut out of it (11k vertices; hands and a strip of neck are
# what is left).  The whole body is the sample's preview mesh, on the same
# skeleton: 32k vertices, ONE LOD, no material and no physics asset of its
# own.  It is what the player wears, undressed (combat/metahuman_body.py);
# the rigs are still built on BODY_MESH (same skeleton, same reference pose).
BODY_MESH_WHOLE = f"{COMMON}/Common/m_med_nrw_body_preview"

# The body's material as the sample ships it: it paints underwear, and pulls
# the skin in under where BP_Taro's clothes were (BodyHideScale, -3) so it
# never pokes through them.
BODY_MATERIAL = f"{ROOT}/Materials/MI_BodySynthesized"
BODY_HIDE_PARAM = "BodyHideScale"

# The face, on the face archetype skeleton, animated by Face_AnimBP (a Live
# Link pose with no subject, and Copy Pose From Mesh off the body it hangs
# under: that is what carries the head).  Its post-process anim BP (RigLogic)
# is on the mesh.
FACE_MESH = f"{ROOT}/Face/{CHARACTER}_FaceMesh"
FACE_ANIM_BP = f"{COMMON}/Face/Face_AnimBP"

# The clothing BP_Taro wears, each a skeletal mesh under the body.
CLOTHING = {
    "Torso": f"{COMMON}/Male/Medium/NormalWeight/Tops/Hoodie/Meshes/"
             "m_med_nrw_top_hoodie_nrm_Cinematic",
    "Legs": f"{COMMON}/Male/Medium/NormalWeight/Bottoms/Jeans/"
            "m_med_nrw_btm_jeans_nrm_Cinematic",
    "Feet": f"{COMMON}/Male/Medium/NormalWeight/Shoes/RunningShoes/"
            "m_med_nrw_shs_runningshoes_Cinematic",
}

# The grooms, each (groom asset, its binding to the face), under the face.
GROOMS = {
    "Hair": (f"{ROOT}/MaleHair/Hair/Hair_M_SideSweptFringe",
             f"{ROOT}/MaleHair/GroomBinding/"
             "Hair_M_SideSweptFringe_m_head_Archetype_Binding"),
    "Eyebrows": (f"{ROOT}/MaleHair_pfn/Hair/Eyebrows_L_Scraggly",
                 f"{ROOT}/MaleHair_pfn/GroomBinding/"
                 "Eyebrows_L_Scraggly_MaleHair_pfn_Face_Archetype_Binding"),
    "Eyelashes": (f"{ROOT}/MaleHair/Hair/Eyelashes_S_Sparse",
                  f"{ROOT}/MaleHair/GroomBinding/"
                  "Eyelashes_S_Sparse_m_med_nrw_head_skmesh_Face_Archetype_Binding"),
    "Mustache": (f"{ROOT}/MaleHair/Hair/Mustache_L_Wavy",
                 f"{ROOT}/MaleHair/GroomBinding/"
                 "Mustache_L_Wavy_m_head_Archetype_Binding"),
    "Beard": (f"{ROOT}/MaleHair/Hair/Goatee_S_ChinStrap",
              f"{ROOT}/MaleHair/GroomBinding/"
              "Goatee_S_ChinStrap_m_head_Archetype_Binding"),
    "Fuzz": (f"{ROOT}/FemaleHair/Hair/Peachfuzz_M_Thin",
             f"{ROOT}/FemaleHair/GroomBinding/"
             "Peachfuzz_M_Thin_f_head_Archetype_Binding"),
}

# What MetaHumanComponentUE gives the garments that have no post-process
# anim BP of their own (the jeans): a copy of the body's pose. BP_Taro's.
CLOTHING_POST_PROCESS = f"{COMMON}/Shared/Animation/ABP_Clothing_PostProcess"

# The sample's own retargeting anim BP: one Retarget Pose From Mesh node off
# the parent component.  build_metahuman_retarget.py duplicates it.
ABP_RETARGET_SAMPLE = f"{COMMON}/Common/Animation/Retargeting/ABP_MetaHuman_m_med_nrw_Retargeting"

# What build_metahuman_retarget.py writes.
SOURCED_DIR = "/Game/Sourced/MetaHuman"
IK_METAHUMAN = f"{SOURCED_DIR}/IK_MetaHuman"
RTG_FROM_MANNEQUIN = f"{SOURCED_DIR}/RTG_MetaHuman_from_Mannequin"
ABP_RETARGET = f"{SOURCED_DIR}/ABP_MetaHuman_Retarget"
# BODY_MATERIAL copied with BODY_HIDE_PARAM at 0: the whole body, in its
# underwear.  What the Body component wears (combat/metahuman_body.py).
BODY_MATERIAL_BARE = f"{SOURCED_DIR}/MI_BodyUnderwear"
