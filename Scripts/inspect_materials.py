"""
Inspect material parameters in LevelPrototyping
"""
import unreal

def inspect_materials():
    asset_sub = unreal.get_editor_subsystem(unreal.EditorAssetSubsystem)
    mats = [
        "/Game/LevelPrototyping/Materials/M_FlatCol.M_FlatCol",
        "/Game/LevelPrototyping/Materials/MI_PrototypeGrid_Gray.MI_PrototypeGrid_Gray",
        "/Game/LevelPrototyping/Materials/M_PrototypeGrid.M_PrototypeGrid"
    ]
    for m_path in mats:
        mat = asset_sub.load_asset(m_path)
        if mat:
            unreal.log(f"[INSPECT] Loaded {m_path} ({type(mat)})")
            if isinstance(mat, unreal.MaterialInstanceConstant) or isinstance(mat, unreal.MaterialInstance):
                for vp in mat.vector_parameter_values:
                    unreal.log(f"  VectorParam: {vp.parameter_info.name} = {vp.parameter_value}")
                for sp in mat.scalar_parameter_values:
                    unreal.log(f"  ScalarParam: {sp.parameter_info.name} = {sp.parameter_value}")

if __name__ == "__main__":
    inspect_materials()
