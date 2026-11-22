#!/usr/bin/env python3
"""Transfer the CJ FBX skin to the inspected SM64CoopDX Mario/Fast64 armature.

This builds an experimental Fast64 DynOS actor from the CJ-to-Mario rig transfer.
The output still requires visual pose review and in-game validation before release.
"""
from __future__ import annotations
import json
import math
import os
import shutil
import sys
import zipfile
from pathlib import Path

import bpy
from mathutils import Matrix, Vector

SOURCE_WEIGHT_TO_TARGET = {
    "root ground": "Butt", "root hips": "Butt", "pelvis": "Butt",
    "spine lower": "Torso", "spine middle": "Torso", "spine upper": "Torso",
    "belly": "Torso", "l breast": "Torso", "r breast": "Torso",
    "head neck lower": "Head DL", "head neck upper": "Head DL",
    "head eyeball left": "Head DL", "head eyeball right": "Head DL",
    "head eyebrow left 1": "Head DL", "head eyebrow left 2": "Head DL",
    "head eyebrow left 3": "Head DL", "head eyebrow right 1": "Head DL",
    "head eyebrow right 2": "Head DL", "head eyebrow right 3": "Head DL",
    "head eyebrow middle": "Head DL", "head eyelid left lower": "Head DL",
    "head eyelid left upper": "Head DL", "head eyelid right lower": "Head DL",
    "head eyelid right upper": "Head DL", "head lip upper left": "Head DL",
    "head lip upper right": "Head DL", "head lip upper middle": "Head DL",
    "head jaw": "Head DL", "head lip lower left": "Head DL",
    "head lip lower right": "Head DL", "head lip lower middle": "Head DL",
    "head mouth corner left": "Head DL", "head mouth corner right": "Head DL",
    "arm left shoulder 1": "Left Arm Color", "arm left shoulder 2": "Left Arm Color",
    "arm left elbow": "Left Forearm", "arm left wrist": "Left Hand DL",
    "arm left finger 1a": "Left Hand DL", "arm left finger 1b": "Left Hand DL",
    "arm left finger 1c": "Left Hand DL", "arm left finger 2a": "Left Hand DL",
    "arm left finger 2b": "Left Hand DL", "arm left finger 2c": "Left Hand DL",
    "arm right shoulder 1": "Right Arm Color", "arm right shoulder 2": "Right Arm Color",
    "arm right elbow": "Right Forearm", "arm right wrist": "Right Hand DL",
    "arm right finger 1a": "Right Hand DL", "arm right finger 1b": "Right Hand DL",
    "arm right finger 1c": "Right Hand DL", "arm right finger 2a": "Right Hand DL",
    "arm right finger 2b": "Right Hand DL", "arm right finger 2c": "Right Hand DL",
    "leg left thigh": "Left Thigh Color", "leg left knee": "Left Leg",
    "leg left ankle": "Left Shoe", "leg left toes": "Left Shoe",
    "leg right thigh": "Right Thigh Color", "leg right knee": "Right Leg",
    "leg right ankle": "Right Shoe DL", "leg right toes": "Right Shoe DL",
}


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def checkpoint(label):
    print(f"[CJ64-RIG-CHECKPOINT] {label}", flush=True)


def find_object(name, object_type):
    obj = bpy.data.objects.get(name)
    require(obj is not None and obj.type == object_type,
            f"Expected {object_type} object '{name}' in rig-inspection scene")
    return obj


def set_edit_bone_from_source(edit_bone, source_matrix, source_length, source_to_target):
    matrix = source_to_target @ source_matrix
    edit_bone.matrix = matrix
    edit_bone.length = max(0.001, source_length * source_to_target.to_scale().x)
    edit_bone.use_connect = False


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    if len(argv) != 3:
        raise SystemExit(
            "usage: prepare_cj_rig_transfer.py <mario_template.blend> <cj.fbx> <output_dir>"
        )
    template_path, source_fbx, output_dir = (
        Path(value).resolve() for value in argv
    )
    require(template_path.is_file(), f"Mario template blend missing: {template_path}")
    require(source_fbx.is_file(), f"CJ source FBX missing: {source_fbx}")
    output_dir.mkdir(parents=True, exist_ok=True)
    fast64_path = os.environ.get("FAST64_ADDON_PATH")
    require(fast64_path, "FAST64_ADDON_PATH is required for DynOS export")
    fast64_dir = Path(fast64_path).resolve()
    require((fast64_dir / "__init__.py").is_file(), f"Fast64-Gart add-on missing: {fast64_dir}")
    sys.path.insert(0, str(fast64_dir.parent))
    sys.path.insert(0, str(fast64_dir))
    import fast64
    fast64.register()
    addon_version = tuple(fast64.bl_info.get("version", ()))
    addon_name = fast64.bl_info.get("name", "")
    if addon_name != "Fast64 Gart Edition" or addon_version != (2, 5, 3):
        raise SystemExit(
            f"Expected pinned Fast64-Gart 2.5.3, found {addon_name} {addon_version}"
        )
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import export_cj_static_actor as shared

    # Load Mario, copy its Fast64 armature, then remove every unrelated
    # template object BEFORE evaluating the dependency graph. The source
    # template contains seven auxiliary facial meshes whose Armature modifiers
    # form dependency cycles in Blender 4.5. Those cycles were present during
    # CJ import and preceded the native crash (exit 139) in the prior runs.
    checkpoint("before-opening-mario-template")
    bpy.ops.wm.open_mainfile(filepath=str(template_path))
    checkpoint("mario-template-opened")
    mario_arm = find_object("Mario", "ARMATURE")
    checkpoint("mario-armature-found")

    target_arm = mario_arm.copy()
    target_arm.data = mario_arm.data.copy()
    target_arm.name = "CJ64_Mario_Armature"
    target_arm.data.name = "CJ64_Mario_ArmatureData"
    target_arm.matrix_world = Matrix.Identity(4)
    bpy.context.scene.collection.objects.link(target_arm)
    checkpoint("fast64-mario-armature-copied")

    removed_template_objects = 0
    for obj in list(bpy.context.scene.objects):
        if obj is not target_arm:
            bpy.data.objects.remove(obj, do_unlink=True)
            removed_template_objects += 1
    checkpoint(f"template-isolated-removed-{removed_template_objects}-objects")
    bpy.context.view_layer.update()
    checkpoint("isolated-template-dependency-graph-updated")

    if source_fbx.suffix.casefold() != ".fbx":
        raise SystemExit("The current CJ rig-transfer pipeline requires an FBX source")
    checkpoint("before-cj-fbx-import")
    if bpy.app.version >= (4, 4, 0):
        bpy.ops.wm.fbx_import(
            filepath=str(source_fbx),
            use_anim=False,
            use_custom_props=True,
            ignore_leaf_bones=False,
            validate_meshes=True,
        )
    else:
        if not any(addon.module == "io_scene_fbx"
                   for addon in bpy.context.preferences.addons):
            bpy.ops.preferences.addon_enable(module="io_scene_fbx")
        bpy.ops.import_scene.fbx(
            filepath=str(source_fbx),
            use_custom_props=True,
            automatic_bone_orientation=False,
            ignore_leaf_bones=False,
        )
    checkpoint("cj-fbx-import-completed")
    bpy.context.view_layer.update()
    checkpoint("dependency-graph-updated-after-cj-import")

    imported_objects = [
        obj for obj in bpy.context.scene.objects if obj is not target_arm
    ]
    checkpoint(f"imported-object-count-{len(imported_objects)}")
    for obj in imported_objects:
        obj.name = "CJ_SRC__" + obj.name
        if obj.type == "ARMATURE":
            obj.data.name = "CJ_SRC__" + obj.data.name
    checkpoint("source-objects-renamed")

    source_arm = find_object("CJ_SRC__Armature", "ARMATURE")
    source_mesh = find_object("CJ_SRC__Object001", "MESH")
    require(source_mesh.find_armature() == source_arm,
            "CJ source mesh is not bound to CJ_SRC__Armature")
    checkpoint("cj-source-rig-and-mesh-validated")

    # Source FBX local axes are X lateral / Y vertical / Z depth.
    # The Coop Mario template uses X vertical / Y lateral / Z depth.
    axis = Matrix.Rotation(-math.pi / 2.0, 4, "Z")
    source_unit = 0.0254  # FBX source armature object is imported at inch-to-metre scale.
    source_to_target_unscaled = axis @ Matrix.Scale(source_unit, 4)

    mesh_to_target_unscaled = (
        source_to_target_unscaled
        @ source_arm.matrix_world.inverted()
        @ source_mesh.matrix_world
    )
    transformed = [mesh_to_target_unscaled @ vertex.co for vertex in source_mesh.data.vertices]
    minimum = [min(v[i] for v in transformed) for i in range(3)]
    maximum = [max(v[i] for v in transformed) for i in range(3)]
    dimensions = [maximum[i] - minimum[i] for i in range(3)]
    source_height = dimensions[0]
    require(source_height > 0.01, f"Transformed CJ height is invalid: {dimensions}")
    target_height = 2.8  # 280 SM64 units at Fast64's 100 units per Blender unit.
    visual_scale = target_height / source_height
    scale = Matrix.Scale(visual_scale, 4)
    source_to_target = scale @ source_to_target_unscaled
    mesh_to_target = scale @ mesh_to_target_unscaled

    source_arm_name = source_arm.name
    source_mesh_name = source_mesh.name

    # The target armature was copied before template cleanup and CJ import.
    checkpoint("beginning-cj-to-mario-rest-pose-transfer")

    # Position the Fast64 animation bones using the actual CJ source rest matrices.
    target_bone_sources = {
        "Body": "root ground",
        "Butt": "pelvis",
        "2 Torso Rotation": "spine lower",
        "Torso": "spine middle",
        "Head": "spine upper",
        "Head DL": "head neck upper",
        "Left Arm": "arm left shoulder 1",
        "Left Arm Color": "arm left shoulder 2",
        "Left Forearm": "arm left elbow",
        "Left Hand Switch": "arm left wrist",
        "Left Hand": "arm left wrist",
        "Left Hand DL": "arm left wrist",
        "Right Arm": "arm right shoulder 1",
        "Right Arm Color": "arm right shoulder 2",
        "Right Forearm": "arm right elbow",
        "Right Hand Switch": "arm right wrist",
        "Right Hand": "arm right wrist",
        "Right Hand DL": "arm right wrist",
        "Left Thigh": "leg left thigh",
        "Left Thigh Color": "leg left thigh",
        "Left Leg": "leg left knee",
        "Left Shoe": "leg left ankle",
        "Right Thigh": "leg right thigh",
        "Right Thigh Color": "leg right thigh",
        "Right Leg": "leg right knee",
        "Right Shoe": "leg right ankle",
        "Right Shoe DL": "leg right ankle",
    }
    # Snapshot source rest transforms before entering edit mode. Do not read
    # another armature's RNA bones while Blender is editing the target armature:
    # this avoids cross-datablock dependency evaluation in the background runner.
    source_rest_bones = {}
    for source_name in set(target_bone_sources.values()):
        source_bone = source_arm.data.bones.get(source_name)
        if source_bone is not None:
            source_rest_bones[source_name] = (
                source_bone.matrix_local.copy(),
                float(source_bone.length),
            )
    checkpoint(f"source-rest-bones-cached-{len(source_rest_bones)}")

    # Avoid a global selection operator after FBX import. Clear selection
    # directly, then make the duplicated Mario armature the sole active object.
    for obj in bpy.context.view_layer.objects:
        if obj.select_get():
            obj.select_set(False)
    checkpoint("all-scene-objects-deselected")
    target_arm.select_set(True)
    bpy.context.view_layer.objects.active = target_arm
    checkpoint("target-armature-made-active")
    bpy.ops.object.mode_set(mode="EDIT")
    checkpoint("target-armature-entered-edit-mode")

    missing_target_bones = []
    missing_source_bones = []
    for target_name, source_name in target_bone_sources.items():
        edit_bone = target_arm.data.edit_bones.get(target_name)
        source_rest = source_rest_bones.get(source_name)
        if edit_bone is None:
            missing_target_bones.append(target_name)
            continue
        if source_rest is None:
            missing_source_bones.append(source_name)
            continue
        set_edit_bone_from_source(
            edit_bone, source_rest[0], source_rest[1], source_to_target
        )
    checkpoint("target-bone-rest-transforms-applied")
    bpy.ops.object.mode_set(mode="OBJECT")
    checkpoint("target-armature-returned-to-object-mode")
    require(not missing_target_bones,
            "Mario template is missing expected bones: " + ", ".join(missing_target_bones))
    require(not missing_source_bones,
            "CJ source armature is missing expected bones: " + ", ".join(missing_source_bones))

    # Preserve original FBX vertex-group assignments before creating the target groups.
    source_group_names = {
        group.index: group.name.strip().casefold()
        for group in source_mesh.vertex_groups
    }

    # Copy CJ mesh and bake its coordinate conversion/280-unit scale.
    rigged_mesh = source_mesh.copy()
    rigged_mesh.data = source_mesh.data.copy()
    rigged_mesh.name = "CJ64_Rigged_Mesh"
    rigged_mesh.data.name = "CJ64_Rigged_MeshData"
    bpy.context.scene.collection.objects.link(rigged_mesh)
    for vertex in rigged_mesh.data.vertices:
        vertex.co = mesh_to_target @ vertex.co
    rigged_mesh.matrix_world = Matrix.Identity(4)
    rigged_mesh.parent = target_arm

    # Fast64/SM64 supports one deform-bone influence per vertex. Collapse the
    # original GTA FBX weights to the strongest mapped Mario deform group;
    # use nearest retargeted segment only for any source vertex without a mapped group.
    for bone_name in ("Left Wing DL", "Right Wing DL"):
        bone = target_arm.data.bones.get(bone_name)
        if bone is not None:
            bone.use_deform = False
    for group in list(rigged_mesh.vertex_groups):
        rigged_mesh.vertex_groups.remove(group)
    deform_bones = [bone for bone in target_arm.data.bones if bone.use_deform]
    require(len(deform_bones) >= 15,
            f"Expected at least 15 Mario deform bones, found {len(deform_bones)}")
    groups = {bone.name: rigged_mesh.vertex_groups.new(name=bone.name)
              for bone in deform_bones}
    segments = []
    for bone in deform_bones:
        head = bone.head_local.copy()
        tail = bone.tail_local.copy()
        axis_vec = tail - head
        axis_len_sq = max(axis_vec.length_squared, 1e-10)
        segments.append((bone.name, head, axis_vec, axis_len_sq))

    source_weighted_vertices = 0
    fallback_weight_vertices = 0
    for vertex in rigged_mesh.data.vertices:
        mapped_weights = {}
        source_vertex = source_mesh.data.vertices[vertex.index]
        for assignment in source_vertex.groups:
            source_name = source_group_names.get(assignment.group)
            target_name = SOURCE_WEIGHT_TO_TARGET.get(source_name)
            if target_name in groups:
                mapped_weights[target_name] = mapped_weights.get(target_name, 0.0) + float(assignment.weight)
        if mapped_weights:
            target_name = max(mapped_weights, key=mapped_weights.get)
            source_weighted_vertices += 1
        else:
            point = vertex.co
            distances = []
            for name, head, axis_vec, axis_len_sq in segments:
                amount = max(0.0, min(1.0, (point - head).dot(axis_vec) / axis_len_sq))
                nearest = head + axis_vec * amount
                distances.append(((point - nearest).length, name))
            _, target_name = min(distances)
            fallback_weight_vertices += 1
        groups[target_name].add([vertex.index], 1.0, "REPLACE")

    # The copied FBX object still references the source armature; remove that
    # modifier before binding it to the retargeted Mario armature.
    for old_modifier in list(rigged_mesh.modifiers):
        rigged_mesh.modifiers.remove(old_modifier)
    arm_mod = rigged_mesh.modifiers.new("CJ64_Mario_Skin", "ARMATURE")
    arm_mod.object = target_arm
    arm_mod.use_vertex_groups = True
    arm_mod.use_bone_envelopes = False
    rigged_mesh.parent = target_arm

    # Rebuild the animation retarget map from the actual retargeted armatures.
    from fast64.fast64_internal.utility import findStartBones
    from fast64.fast64_internal.sm64.sm64_geolayout_utility import is_bone_animatable
    node_queue = findStartBones(target_arm)
    animation_nodes = []
    while node_queue:
        bone_name = node_queue.pop(0)
        bone = target_arm.data.bones[bone_name]
        if is_bone_animatable(bone):
            q = bone.matrix_local.to_3x3().to_quaternion()
            animation_nodes.append({
                "index": len(animation_nodes),
                "name": bone.name,
                "parent": bone.parent.name if bone.parent else None,
                "rest_rotation_wxyz": [round(float(x), 7) for x in (q.w, q.x, q.y, q.z)],
            })
        node_queue = sorted(child.name for child in bone.children) + node_queue
    require(len(animation_nodes) == 20,
            f"Fast64 expected 20 animation nodes, found {len(animation_nodes)}")
    map_path = Path(__file__).resolve().parents[1] / "tools" / "cj64_sm64_animation_retarget_map.json"
    retarget_map = json.loads(map_path.read_text(encoding="utf-8"))
    actual_node_names = {node["name"] for node in animation_nodes}
    require(actual_node_names == set(retarget_map["target_source_chains"]),
            "Fast64 node names do not match retarget chain map: " + str(sorted(actual_node_names)))
    retarget_map["format"] = "cj64-sm64-animation-retarget-map-v2"
    retarget_map["generated_from_actual_rig"] = True
    retarget_map["source_armature"] = source_arm.name
    retarget_map["target_armature"] = target_arm.name
    retarget_map["target_animation_node_count"] = len(animation_nodes)
    retarget_map["target_node_order"] = [node["name"] for node in animation_nodes]
    retarget_map["target_rest_rotation_wxyz"] = {
        node["name"]: node["rest_rotation_wxyz"] for node in animation_nodes
    }
    retarget_map["target_source_chains"]["Torso"] = ["spine lower", "spine middle"]
    retarget_map["target_source_chains"]["Head"] = [
        "spine upper", "head neck lower", "head neck upper"
    ]
    source_rest = {}
    for chain in retarget_map["target_source_chains"].values():
        for source_name in chain:
            source_bone = source_arm.data.bones.get(source_name)
            if source_bone is not None:
                q = source_bone.matrix_local.to_3x3().to_quaternion()
                source_rest[source_name] = [round(float(x), 7) for x in (q.w, q.x, q.y, q.z)]
    require(source_rest, "No source rest rotations were read from the CJ armature")
    retarget_map["source_rest_rotation_wxyz"] = source_rest
    align_q = source_to_target.to_3x3().to_quaternion()
    retarget_map["axis_alignment"] = {
        "quaternion_xyzw": [round(float(x), 8) for x in
                            (align_q.x, align_q.y, align_q.z, align_q.w)],
        "description": "Computed from the actual FBX-to-Mario rest-space transform used for bone retargeting."
    }
    retarget_map_path = output_dir / "cj64_sm64_animation_retarget_map.json"
    retarget_map_path.write_text(json.dumps(retarget_map, indent=2), encoding="utf-8")
    node_order_path = output_dir / "target_animation_node_order.json"
    node_order_path.write_text(json.dumps({
        "format": "cj64-fast64-animation-node-order-v1",
        "node_count": len(animation_nodes),
        "nodes": animation_nodes,
    }, indent=2), encoding="utf-8")

    # Keep only the new actor and its target armature. This removes the template's
    # auxiliary head/hand armatures and their unrelated dependency cycles.
    for obj in list(bpy.context.scene.objects):
        if obj not in (rigged_mesh, target_arm):
            bpy.data.objects.remove(obj, do_unlink=True)
    rigged_mesh.hide_render = False
    rigged_mesh.hide_viewport = False
    target_arm.hide_render = False
    target_arm.hide_viewport = False
    rigged_mesh.matrix_world = Matrix.Identity(4)
    target_arm.matrix_world = Matrix.Identity(4)
    rigged_mesh.parent = target_arm

    # Prepare TMEM-safe textures and convert materials for Fast64.
    fallback_materials = [
        material.name for material in rigged_mesh.data.materials
        if material is not None and shared.ensure_base_color_texture(material)
    ]
    texture_islands = shared.split_materials_into_tmem_uv_islands(
        rigged_mesh, max_texels=2048
    )
    import fast64.fast64_internal.f3d_material_converter as converter
    converter.convertAllBSDFtoF3D([rigged_mesh], True)
    unresolved_materials = [
        material.name for material in rigged_mesh.data.materials
        if material and not bool(getattr(material, "is_f3d", False))
    ]
    require(not unresolved_materials,
            "Fast64 material conversion failed: " + ", ".join(unresolved_materials))

    # Export through Fast64-Gart's current Combined Exporter settings.
    # The armature GeoLayout operator still exists, but it now reads from
    # scene.fast64.sm64.combined_export instead of the legacy geo* Scene props.
    mod_dir = output_dir / "CJ64-Rigged-Test"
    actor_root = mod_dir / "actors"
    actor_root.mkdir(parents=True, exist_ok=True)
    scene = bpy.context.scene
    scene.gameEditorMode = "SM64"
    scene.fast64.sm64.export_type = "C"
    scene.fast64.sm64.blender_to_sm64_scale = 100.0
    scene.saveTextures = True
    require(hasattr(scene, "geoSeparateTextureDef"),
            "Fast64-Gart did not register the GeoLayout texture export setting")
    scene.geoSeparateTextureDef = False
    scene.exportInlineF3D = False

    combined = scene.fast64.sm64.combined_export
    combined.export_header_type = "Custom"
    combined.custom_export_path = str(actor_root.resolve())
    combined.custom_include_directory = "actors/cj/"
    combined.object_name = "cj"
    combined.group_name = "group0"
    combined.export_gfx = True
    combined.export_col = False
    combined.export_anim = False
    combined.export_bhv = False
    combined.export_script_loads = False
    combined.export_all_selected = False
    combined.use_name_filtering = False
    combined.graphics_object = rigged_mesh
    combined.context_obj = rigged_mesh

    bpy.ops.object.select_all(action="DESELECT")
    target_arm.select_set(True)
    bpy.context.view_layer.objects.active = target_arm
    if bpy.context.object.mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")
    export_result = bpy.ops.object.sm64_export_geolayout_armature(export_obj=target_arm.name)
    require("FINISHED" in export_result,
            f"Fast64-Gart armature export did not finish: {export_result}")
    actor_dir = actor_root / "cj"
    require((actor_dir / "geo.inc.c").is_file() and
            (actor_dir / "model.inc.c").is_file(),
            "Fast64 did not create the CJ DynOS actor files")
    repo_root = Path(__file__).resolve().parents[1]
    shutil.copy2(repo_root / "main.lua", mod_dir / "main.lua")
    shutil.copy2(repo_root / "character.lua", mod_dir / "character.lua")
    (mod_dir / "rigged_actor.lua").write_text(
        "CJ64 = CJ64 or {}\nCJ64.riggedActor = true\n", encoding="utf-8"
    )
    (mod_dir / "README-INSTALL.txt").write_text(
        "CJ64 experimental skinned actor. It uses the Mario/Fast64 armature, "
        "one deform bone per vertex at weight 1.0, and a 280 SM64-unit model. "
        "The private cj64_gta_animations.lua module is not included. "
        "Test the actor in SM64CoopDX before treating this as a release.\n",
        encoding="utf-8"
    )

    bpy.context.view_layer.update()
    depsgraph = bpy.context.evaluated_depsgraph_get()
    evaluated = rigged_mesh.evaluated_get(depsgraph)
    evaluated_mesh = evaluated.to_mesh()
    coords = [evaluated.matrix_world @ v.co for v in evaluated_mesh.vertices]
    bounds_min = [min(v[i] for v in coords) for i in range(3)]
    bounds_max = [max(v[i] for v in coords) for i in range(3)]
    bounds = [bounds_max[i] - bounds_min[i] for i in range(3)]
    evaluated.to_mesh_clear()

    weighted_vertices = sum(1 for vertex in rigged_mesh.data.vertices if vertex.groups)
    require(weighted_vertices == len(rigged_mesh.data.vertices),
            f"Unweighted CJ vertices remain: {len(rigged_mesh.data.vertices) - weighted_vertices}")
    influence_counts = [
        sum(1 for assignment in vertex.groups if assignment.weight > 0.0001)
        for vertex in rigged_mesh.data.vertices
    ]
    max_influences = max(influence_counts) if influence_counts else 0
    invalid_weight_vertices = sum(1 for count in influence_counts if count != 1)
    require(invalid_weight_vertices == 0,
            f"{invalid_weight_vertices} vertices do not have exactly one bone influence")
    require(abs(bounds[0] - target_height) < 0.03,
            f"CJ target height is not 2.8 units on Mario X-up rig: {bounds}")

    report = {
        "format": "cj64-rig-transfer-preview-v1",
        "status": "FAST64_EXPORTED_EXPERIMENTAL_NOT_VISUALLY_OR_IN_GAME_VALIDATED",
        "fast64_addon": addon_name,
        "fast64_version": list(addon_version),
        "source_armature": source_arm_name,
        "target_armature": target_arm.name,
        "source_mesh": source_mesh_name,
        "rigged_mesh": rigged_mesh.name,
        "source_vertices": len(rigged_mesh.data.vertices),
        "source_faces": len(rigged_mesh.data.polygons),
        "target_height_blender_units": target_height,
        "target_height_sm64_units": target_height * 100.0,
        "visual_scale_factor": visual_scale,
        "axis_alignment": "source FBX Y-up to Mario template X-up: Rz(-90 degrees)",
        "source_to_target_bone_map": target_bone_sources,
        "target_vertex_groups": sorted(group.name for group in rigged_mesh.vertex_groups),
        "weighted_vertices": weighted_vertices,
        "weight_influences_per_vertex": max_influences,
        "vertices_using_original_source_weights": source_weighted_vertices,
        "vertices_using_nearest_bone_fallback": fallback_weight_vertices,
        "invalid_weight_vertices": invalid_weight_vertices,
        "target_animation_node_count": len(animation_nodes),
        "target_animation_nodes": animation_nodes,
        "texture_uv_islands": texture_islands,
        "generated_fallback_materials": fallback_materials,
        "fast64_export_result": str(export_result),
        "actor_files": [str(path.relative_to(mod_dir)) for path in actor_dir.rglob("*") if path.is_file()],
        "bounds_after_armature_evaluation": bounds,
        "preview_image": "CJ64-Rigged-Rest-Preview.png",
        "notes": [
            "Original FBX vertex weights are collapsed to one mapped Mario deform bone at weight 1.0; nearest-bone fallback is used only for unweighted/unmapped source vertices.",
            "Mario helper hierarchy was retained and the corresponding source rest matrices were applied to animation bones.",
            "The Fast64 DynOS actor is exported, but major poses and in-game rendering still require visual and runtime validation.",
            "The original CJ mesh and source IFP are not added to the repository by this script."
        ]
    }
    report_path = output_dir / "cj64_rig_transfer_report.json"
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    # Render a rest-pose preview with the Mario template's X-up orientation.
    scene = bpy.context.scene
    if bpy.app.version >= (4, 2, 0):
        scene.render.engine = "BLENDER_EEVEE_NEXT"
    else:
        scene.render.engine = "BLENDER_EEVEE"
        scene.eevee.taa_render_samples = 32
    scene.render.resolution_x = 900
    scene.render.resolution_y = 900
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA"
    scene.render.film_transparent = False
    scene.view_settings.view_transform = "Standard"
    scene.view_settings.look = "Medium High Contrast"
    if scene.world is None:
        scene.world = bpy.data.worlds.new("CJ64_Rig_Preview_World")
    scene.world.use_nodes = True
    background = scene.world.node_tree.nodes.get("Background")
    if background is not None:
        background.inputs["Color"].default_value = (0.055, 0.055, 0.055, 1.0)
        background.inputs["Strength"].default_value = 0.8

    target = Vector((1.4, 0.0, 0.0))
    camera_data = bpy.data.cameras.new("CJ64_Rig_Preview_Camera")
    camera = bpy.data.objects.new("CJ64_Rig_Preview_Camera", camera_data)
    scene.collection.objects.link(camera)
    camera.location = (1.4, 0.0, -5.2)
    forward = (target - camera.location).normalized()
    up_reference = Vector((1.0, 0.0, 0.0))
    right = forward.cross(up_reference).normalized()
    camera_up = right.cross(forward).normalized()
    camera_basis = Matrix((right, camera_up, -forward)).transposed()
    camera.rotation_euler = camera_basis.to_euler()
    camera_data.lens = 55
    scene.camera = camera

    light_specs = [
        ("CJ64_Rig_Key", (3.0, -3.0, -3.0), 850.0, 3.0),
        ("CJ64_Rig_Fill", (0.0, 3.0, -2.0), 500.0, 4.0),
        ("CJ64_Rig_Rim", (1.5, 0.0, 3.0), 650.0, 3.0),
    ]
    for light_name, location, energy, size in light_specs:
        light_data = bpy.data.lights.new(light_name, "AREA")
        light_data.energy = energy
        light_data.shape = "DISK"
        light_data.size = size
        light_obj = bpy.data.objects.new(light_name, light_data)
        scene.collection.objects.link(light_obj)
        light_obj.location = location
        light_obj.rotation_euler = (target - light_obj.location).to_track_quat("-Z", "Y").to_euler()

    preview_path = output_dir / "CJ64-Rigged-Rest-Preview.png"
    scene.render.filepath = str(preview_path)
    bpy.ops.render.render(write_still=True)

    scene_path = output_dir / "CJ64-CJ-Rig-Transfer.blend"
    bpy.ops.wm.save_as_mainfile(filepath=str(scene_path))
    archive = output_dir / "CJ64-Rigged-Test.zip"
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED, compresslevel=8) as package:
        for path in sorted(mod_dir.rglob("*")):
            if path.is_file():
                package.write(path, path.relative_to(output_dir))
    print(json.dumps({
        "scene": str(scene_path), "report": str(report_path),
        "package": str(archive), **report
    }, indent=2))


if __name__ == "__main__":
    main()
