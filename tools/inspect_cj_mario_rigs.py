#!/usr/bin/env python3
"""Inspect the official SM64CoopDX Mario template and uploaded CJ FBX in Blender.

Prerequisite for retargeting. This deliberately does not guess bone matches.
It writes a rig report and a combined inspection .blend.
"""
from __future__ import annotations
import json
import os
import sys
from pathlib import Path
import bpy  # type: ignore


def vec(v):
    return [round(float(x), 6) for x in v]


def quat(q):
    return [round(float(x), 7) for x in (q.w, q.x, q.y, q.z)]


def matrix4(m):
    return [[round(float(m[r][c]), 6) for c in range(4)] for r in range(4)]


def bone_report(armature):
    bones = []
    for bone in armature.data.bones:
        rest = bone.matrix_local.to_3x3().to_quaternion()
        bones.append({
            "name": bone.name,
            "parent": bone.parent.name if bone.parent else None,
            "use_deform": bool(bone.use_deform),
            "collections": [collection.name for collection in bone.collections] if hasattr(bone, "collections") else [],
            "geo_cmd": getattr(bone, "geo_cmd", None),
            "field_layout": getattr(bone, "field_layout", None),
            "custom_geo_cmd_macro": getattr(getattr(getattr(bone, "fast64", None), "sm64", None), "custom_geo_cmd_macro", None),
            "head_local": vec(bone.head_local),
            "tail_local": vec(bone.tail_local),
            "length": round(float(bone.length), 6),
            "rest_rotation_wxyz": quat(rest),
            "matrix_local": matrix4(bone.matrix_local),
        })
    return bones


def image_paths(material):
    found = []
    if not material or not material.use_nodes or not material.node_tree:
        return found
    for node in material.node_tree.nodes:
        if node.type == "TEX_IMAGE" and node.image:
            found.append({
                "image": node.image.name,
                "filepath": node.image.filepath,
                "packed": bool(node.image.packed_file),
            })
    return found


def mesh_report(obj):
    groups = [g.name for g in obj.vertex_groups]
    weighted = set()
    for vertex in obj.data.vertices:
        for assignment in vertex.groups:
            if assignment.weight > 0.0001 and assignment.group < len(groups):
                weighted.add(groups[assignment.group])
    materials = []
    for mat in obj.data.materials:
        if mat:
            materials.append({"name": mat.name, "images": image_paths(mat)})
    armature_modifiers = [
        m.object.name for m in obj.modifiers
        if m.type == "ARMATURE" and m.object is not None
    ]
    return {
        "name": obj.name,
        "vertices": len(obj.data.vertices),
        "polygons": len(obj.data.polygons),
        "dimensions": vec(obj.dimensions),
        "location": vec(obj.location),
        "scale": vec(obj.scale),
        "vertex_group_count": len(groups),
        "vertex_groups": groups,
        "weighted_groups": sorted(weighted),
        "armature_modifiers": armature_modifiers,
        "materials": materials,
    }


def all_objects_report(objects):
    result = {"armatures": [], "meshes": [], "other_objects": []}
    for obj in objects:
        if obj.type == "ARMATURE":
            result["armatures"].append({
                "name": obj.name,
                "data_name": obj.data.name,
                "bone_count": len(obj.data.bones),
                "parent": obj.parent.name if obj.parent else None,
                "location": vec(obj.location),
                "rotation_euler": vec(obj.rotation_euler),
                "scale": vec(obj.scale),
                "bones": bone_report(obj),
            })
        elif obj.type == "MESH":
            result["meshes"].append(mesh_report(obj))
        else:
            result["other_objects"].append({"name": obj.name, "type": obj.type})
    return result


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    if len(argv) != 3:
        raise SystemExit("usage: inspect_cj_mario_rigs.py <mario_template.blend> <cj.fbx> <output_dir>")
    template, fbx, out = (Path(value).resolve() for value in argv)
    if not template.is_file() or not fbx.is_file():
        raise SystemExit("Mario template .blend and CJ FBX must both exist")
    out.mkdir(parents=True, exist_ok=True)

    fast64_path = os.environ.get("FAST64_ADDON_PATH")
    if not fast64_path:
        raise SystemExit("FAST64_ADDON_PATH is required to read the template GeoLayout bone properties")
    fast64_dir = Path(fast64_path).resolve()
    if not (fast64_dir / "__init__.py").is_file():
        raise SystemExit(f"Fast64-Gart add-on source not found: {fast64_dir}")
    sys.path.insert(0, str(fast64_dir.parent))
    sys.path.insert(0, str(fast64_dir))
    import fast64  # type: ignore
    fast64.register()
    addon_version = tuple(fast64.bl_info.get("version", ()))
    addon_name = fast64.bl_info.get("name", "")
    if addon_name != "Fast64 Gart Edition" or addon_version != (2, 5, 3):
        raise SystemExit(
            f"Expected pinned Fast64-Gart 2.5.3, found {addon_name} {addon_version}"
        )
    if not hasattr(bpy.ops.wm, "fbx_import"):
        try:
            bpy.ops.preferences.addon_enable(module="io_scene_fbx")
        except Exception:
            pass

    bpy.ops.wm.open_mainfile(filepath=str(template))
    bpy.context.view_layer.update()
    template_objects = list(bpy.context.scene.objects)
    template_report = all_objects_report(template_objects)
    if not template_report["armatures"]:
        raise SystemExit("The official Mario template contains no Armature object")

    if fbx.suffix.casefold() == ".glb":
        bpy.ops.import_scene.gltf(filepath=str(fbx))
    elif fbx.suffix.casefold() == ".fbx":
        # The Blender operator namespace dynamically exposes unknown names,
        # so hasattr(bpy.ops.wm, "fbx_import") is not a valid capability check.
        # Blender 3.6 uses the legacy add-on operator; 4.5 uses the built-in ufbx operator.
        if bpy.app.version >= (4, 4, 0):
            bpy.ops.wm.fbx_import(
                filepath=str(fbx),
                use_anim=False,
                use_custom_props=True,
                ignore_leaf_bones=False,
                validate_meshes=True,
            )
        else:
            bpy.ops.preferences.addon_enable(module="io_scene_fbx")
            import io_scene_fbx
            io_scene_fbx.register()
            bpy.ops.import_scene.fbx(
                filepath=str(fbx),
                use_custom_props=True,
                automatic_bone_orientation=False,
                ignore_leaf_bones=False,
            )
    else:
        raise SystemExit("CJ source must be a GLB or FBX file")
    bpy.context.view_layer.update()
    original_names = {obj.name for obj in template_objects}
    imported_objects = [obj for obj in bpy.context.scene.objects if obj.name not in original_names]
    for obj in imported_objects:
        obj.name = "CJ_SRC__" + obj.name
        if obj.type == "ARMATURE":
            obj.data.name = "CJ_SRC__" + obj.data.name

    source_report = all_objects_report(imported_objects)
    if not source_report["armatures"]:
        raise SystemExit("The CJ FBX import did not contain an Armature")

    actions_report = []
    for action in bpy.data.actions:
        curves = []
        for curve in action.fcurves:
            group_name = curve.group.name if curve.group else None
            curves.append({
                "data_path": curve.data_path,
                "array_index": curve.array_index,
                "group": group_name,
                "keyframes": len(curve.keyframe_points),
            })
        actions_report.append({
            "name": action.name,
            "frame_range": [float(action.frame_range[0]), float(action.frame_range[1])],
            "fcurves": curves,
        })

    target_bone_collections = []
    mario_armature_obj = next(obj for obj in bpy.context.scene.objects
                              if obj.type == "ARMATURE" and obj.name == "Mario")

    # Match Fast64-Gart: traverse start bones and alphabetically sorted children.
    # Its current API detects standard and animated Custom nodes through
    # is_bone_animatable(), which handles standard and animated Custom nodes.
    from fast64.fast64_internal.utility import findStartBones
    from fast64.fast64_internal.sm64.sm64_geolayout_utility import is_bone_animatable
    bones_to_process = findStartBones(mario_armature_obj)
    target_animation_nodes = []
    while bones_to_process:
        bone_name = bones_to_process[0]
        bones_to_process = bones_to_process[1:]
        bone = mario_armature_obj.data.bones[bone_name]
        if is_bone_animatable(bone):
            target_animation_nodes.append({
                "index": len(target_animation_nodes),
                "name": bone.name,
                "parent": bone.parent.name if bone.parent else None,
                "geo_cmd": getattr(bone, "geo_cmd", None),
                "use_deform": bool(bone.use_deform),
                "rest_matrix": matrix4(bone.matrix_local),
                "rest_rotation_wxyz": quat(bone.matrix_local.to_3x3().to_quaternion()),
            })
        bones_to_process = sorted(child.name for child in bone.children) + bones_to_process
    if not target_animation_nodes:
        raise SystemExit("Fast64 found no animatable GeoLayout bones on the Mario armature.")
    for collection in getattr(mario_armature_obj.data, "collections", []):
        target_bone_collections.append({
            "name": collection.name,
            "visible": bool(collection.is_visible),
            "bones": [bone.name for bone in collection.bones],
        })

    report = {
        "format": "cj64-cj-mario-rig-inspection-v3",
        "blender_version": bpy.app.version_string,
        "fast64_addon": addon_name,
        "fast64_version": list(addon_version),
        "template_file": template.name,
        "source_model_import": fbx.name,
        "target_template": template_report,
        "source_cj": source_report,
        "target_bone_collections": target_bone_collections,
        "target_animation_nodes": target_animation_nodes,
        "target_animation_node_count": len(target_animation_nodes),
        "template_actions": actions_report,
        "retarget_status": "NOT_STARTED",
        "warnings": [
            "No automatic source-to-Mario mapping was applied.",
            "Compare parent hierarchy, joint positions, rest rotations and mesh weights before retargeting.",
            "SM64CoopDX animation export does not preserve arbitrary limb translation or scaling.",
        ],
    }
    report_path = out / "cj_mario_rig_inspection.json"
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    node_order_path = out / "target_animation_node_order.json"
    node_order_path.write_text(json.dumps({
        "format": "cj64-fast64-animation-node-order-v1",
        "node_count": len(target_animation_nodes),
        "nodes": target_animation_nodes,
    }, indent=2), encoding="utf-8")
    blend_path = out / "cj_mario_dual_rig_inspection.blend"
    bpy.ops.wm.save_as_mainfile(filepath=str(blend_path))
    compact_bones = lambda rig: [
        {
            "armature": armature["name"],
            "name": bone["name"],
            "parent": bone["parent"],
            "head": bone["head_local"],
            "tail": bone["tail_local"],
            "rest_quaternion_wxyz": bone["rest_rotation_wxyz"],
        }
        for armature in rig["armatures"]
        for bone in armature["bones"]
    ]
    print(json.dumps({
        "report": str(report_path),
        "blend": str(blend_path),
        "target_armatures": [(a["name"], a["bone_count"]) for a in template_report["armatures"]],
        "source_armatures": [(a["name"], a["bone_count"]) for a in source_report["armatures"]],
        "target_bones": compact_bones(template_report),
        "source_bones": compact_bones(source_report),
    }, indent=2))


if __name__ == "__main__":
    main()
