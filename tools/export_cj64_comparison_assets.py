#!/usr/bin/env python3
"""Export paired GTA-source and SM64-retargeted CJ GLBs from one Blender rig build.

The original ped.ifp is deliberately not consumed by this workflow. The browser
viewer parses the user's local IFP file and applies the same retarget equations
used by tools/generate_cj_sm64_animations.py.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import bpy  # type: ignore


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def ensure_gltf_exporter() -> None:
    """Enable Blender's bundled glTF 2.0 exporter in factory-startup mode."""
    try:
        bpy.ops.export_scene.gltf.get_rna_type()
        return
    except Exception:
        pass
    try:
        bpy.ops.preferences.addon_enable(module="io_scene_gltf2")
        bpy.ops.export_scene.gltf.get_rna_type()
    except Exception as exc:
        raise RuntimeError(
            "Blender's glTF 2.0 exporter is unavailable. Ensure io_scene_gltf2 "
            "is installed and enabled in the Blender 4.5.16 runner."
        ) from exc


def import_fbx(path: Path) -> None:
    if bpy.app.version >= (4, 4, 0):
        bpy.ops.wm.fbx_import(
            filepath=str(path),
            use_anim=False,
            use_custom_props=True,
            ignore_leaf_bones=False,
            validate_meshes=True,
        )
    else:
        if not any(addon.module == "io_scene_fbx" for addon in bpy.context.preferences.addons):
            bpy.ops.preferences.addon_enable(module="io_scene_fbx")
        bpy.ops.import_scene.fbx(
            filepath=str(path),
            use_anim=False,
            use_custom_props=True,
            automatic_bone_orientation=False,
            ignore_leaf_bones=False,
        )


def select_export(objects: list, output: Path) -> None:
    ensure_gltf_exporter()
    bpy.ops.object.select_all(action="DESELECT")
    for obj in objects:
        obj.hide_set(False)
        obj.hide_viewport = False
        obj.hide_render = False
        obj.select_set(True)
    bpy.context.view_layer.objects.active = objects[0]
    bpy.ops.export_scene.gltf(
        filepath=str(output),
        export_format="GLB",
        use_selection=True,
        export_animations=False,
        export_skins=True,
        export_yup=True,
        export_apply=False,
        export_texcoords=True,
        export_normals=True,
        export_materials="EXPORT",
        export_image_format="AUTO",
    )
    require(output.is_file() and output.stat().st_size > 50_000,
            f"GLB export is missing or unexpectedly small: {output}")


def main() -> None:
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    if len(argv) != 5:
        raise SystemExit(
            "usage: export_cj64_comparison_assets.py <source.fbx> <rig.blend> "
            "<retarget-map.json> <fbx-bone-map.json> <output-dir>"
        )
    source_fbx, rig_blend, retarget_map_path, fbx_bone_map_path, output_dir = (
        Path(value).resolve() for value in argv
    )
    for path in (source_fbx, rig_blend, retarget_map_path, fbx_bone_map_path):
        require(path.is_file(), f"Required comparison input is missing: {path}")
    output_dir.mkdir(parents=True, exist_ok=True)

    # Export the original GTA FBX skeleton using the same Blender importer/version
    # that generated the source rest matrices in the retarget map.
    bpy.ops.wm.read_factory_settings(use_empty=True)
    ensure_gltf_exporter()
    import_fbx(source_fbx)
    source_armatures = [obj for obj in bpy.context.scene.objects if obj.type == "ARMATURE"]
    require(len(source_armatures) == 1,
            f"Expected one source CJ armature, found {len(source_armatures)}")
    source_arm = source_armatures[0]
    source_meshes = [obj for obj in bpy.context.scene.objects
                     if obj.type == "MESH" and obj.find_armature() == source_arm]
    require(source_meshes, "The source CJ FBX has no mesh skinned to its armature")
    source_mesh = max(source_meshes, key=lambda obj: len(obj.data.vertices))
    source_bones = set(source_arm.data.bones.keys())
    fbx_bone_map = json.loads(fbx_bone_map_path.read_text(encoding="utf-8"))
    source_required = fbx_bone_map["ifp_to_fbx"]
    missing_source = sorted(set(source_required.values()) - source_bones)
    require(not missing_source, "Source FBX is missing mapped IFP bones: " + ", ".join(missing_source))
    source_glb = output_dir / "cj64-gta-source.glb"
    select_export([source_arm, source_mesh], source_glb)

    # Open the actual rig-transfer output. Its target mesh already has the
    # converted target-space coordinates and exact Fast64 vertex weights.
    bpy.ops.wm.open_mainfile(filepath=str(rig_blend))
    target_arm = bpy.data.objects.get("CJ64_Mario_Armature")
    target_mesh = bpy.data.objects.get("CJ64_Rigged_Mesh")
    require(target_arm is not None and target_arm.type == "ARMATURE",
            "Saved rig-transfer scene is missing CJ64_Mario_Armature")
    require(target_mesh is not None and target_mesh.type == "MESH",
            "Saved rig-transfer scene is missing CJ64_Rigged_Mesh")
    require(target_mesh.find_armature() == target_arm,
            "Saved target mesh is not bound to CJ64_Mario_Armature")

    # Re-import the source FBX to obtain standard PBR materials and UVs for the
    # browser preview. The preview geometry/weights still come from the target
    # mesh built by the game export pipeline.
    import_fbx(source_fbx)
    imported_armatures = [obj for obj in bpy.context.scene.objects
                          if obj.type == "ARMATURE" and obj is not target_arm]
    imported_meshes = [obj for obj in bpy.context.scene.objects
                       if obj.type == "MESH" and obj.find_armature() in imported_armatures]
    require(imported_armatures and imported_meshes,
            "Could not re-import source FBX materials for the retargeted preview")
    original_mesh = max(imported_meshes, key=lambda obj: len(obj.data.vertices))
    require(len(original_mesh.data.vertices) == len(target_mesh.data.vertices),
            "Source and target mesh vertex counts differ; refusing an invalid skin transfer")

    preview_data = original_mesh.data.copy()
    preview_data.name = "CJ64_Comparison_Target_MeshData"
    coords = [0.0] * (len(target_mesh.data.vertices) * 3)
    for index, vertex in enumerate(target_mesh.data.vertices):
        coords[index * 3:index * 3 + 3] = [float(vertex.co.x), float(vertex.co.y), float(vertex.co.z)]
    preview_data.vertices.foreach_set("co", coords)
    preview_data.update()

    preview_mesh = bpy.data.objects.new("CJ64_Comparison_Target_Mesh", preview_data)
    bpy.context.scene.collection.objects.link(preview_mesh)
    preview_mesh.matrix_world.identity()
    preview_mesh.parent = target_arm

    # Reuse the exact single-bone assignments used by Fast64; do not calculate
    # any new weights for the comparison-only GLB.
    for group in list(preview_mesh.vertex_groups):
        preview_mesh.vertex_groups.remove(group)
    target_groups = {group.index: group.name for group in target_mesh.vertex_groups}
    preview_groups = {name: preview_mesh.vertex_groups.new(name=name)
                      for name in target_groups.values()}
    for vertex in target_mesh.data.vertices:
        for assignment in vertex.groups:
            group_name = target_groups[assignment.group]
            preview_groups[group_name].add([vertex.index], float(assignment.weight), "REPLACE")

    for modifier in list(preview_mesh.modifiers):
        preview_mesh.modifiers.remove(modifier)
    armature_modifier = preview_mesh.modifiers.new("CJ64_Comparison_Skin", "ARMATURE")
    armature_modifier.object = target_arm
    armature_modifier.use_vertex_groups = True
    armature_modifier.use_bone_envelopes = False
    bpy.context.view_layer.update()
    require(preview_mesh.find_armature() == target_arm,
            "Comparison mesh did not bind to the target SM64 armature")

    target_glb = output_dir / "cj64-sm64-target.glb"
    select_export([target_arm, preview_mesh], target_glb)

    retarget_map = json.loads(retarget_map_path.read_text(encoding="utf-8"))
    require(retarget_map.get("generated_from_actual_rig") is True,
            "Retarget map was not generated from the actual Blender/Fast64 rig")
    require(retarget_map.get("target_animation_node_count") == 20,
            "Retarget map does not contain the expected 20 SM64 animation nodes")
    require(len(retarget_map.get("source_fbx_parent_by_bone", {})) >= 20,
            "Retarget map does not contain the actual source FBX hierarchy")
    require(len(retarget_map.get("source_rest_rotation_wxyz", {})) >= 20,
            "Retarget map does not contain source rest rotations")
    require(len(retarget_map.get("source_fbx_parent_by_bone", {}))
            == len(retarget_map.get("source_rest_rotation_wxyz", {})),
            "Source FBX parent map and rest-rotation map have different bone counts")
    require(set(retarget_map["target_node_order"])
            == set(retarget_map["target_parent_rest_rotation_wxyz"]),
            "Target animated nodes and parent rest rotations do not match")

    map_output = output_dir / "cj64_sm64_animation_retarget_map.json"
    bone_map_output = output_dir / "cj_fbx_bone_map.json"
    map_output.write_text(json.dumps(retarget_map, indent=2), encoding="utf-8")
    bone_map_output.write_text(fbx_bone_map_path.read_text(encoding="utf-8"), encoding="utf-8")

    manifest = {
        "format": "cj64-animation-comparison-assets-v1",
        "source_model": source_glb.name,
        "target_model": target_glb.name,
        "retarget_map": map_output.name,
        "source_bone_map": bone_map_output.name,
        "source_bone_count": len(source_bones),
        "target_animation_node_count": retarget_map["target_animation_node_count"],
        "source_vertex_count": len(source_mesh.data.vertices),
        "target_vertex_count": len(preview_mesh.data.vertices),
        "ifp_file_embedded": False,
        "validation_scope": "paired_GLTF_assets_and_actual_retarget_metadata; not_SM64_runtime_or_Dynos_render_validation",
    }
    (output_dir / "comparison-assets.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
