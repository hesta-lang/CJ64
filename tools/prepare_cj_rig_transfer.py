#!/usr/bin/env python3
"""Transfer the CJ FBX skin to the inspected SM64CoopDX Mario/Fast64 armature.

This builds an experimental Fast64 DynOS actor from the CJ-to-Mario rig transfer.
The output still requires visual pose review and in-game validation before release.
"""
from __future__ import annotations
import json
import math
import os
import re
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


def ensure_f3d_color_attributes(mesh):
    """Normalize Fast64 color attributes without invoking geometry.attribute_convert."""
    for attribute_name in ("Col", "Alpha"):
        attribute = mesh.attributes.get(attribute_name)
        if attribute is not None and attribute.data_type == "FLOAT_COLOR" and attribute.domain == "CORNER":
            continue

        old_domain = attribute.domain if attribute is not None else None
        old_values = []
        if attribute is not None:
            for element in attribute.data:
                if hasattr(element, "color"):
                    value = tuple(float(v) for v in element.color)
                elif hasattr(element, "vector"):
                    vector = tuple(float(v) for v in element.vector)
                    value = vector[:3] + (1.0,)
                elif hasattr(element, "value"):
                    scalar = float(element.value)
                    value = (scalar, scalar, scalar, 1.0)
                else:
                    value = (1.0, 1.0, 1.0, 1.0)
                old_values.append(value)

            mesh.attributes.remove(attribute)

        new_attribute = mesh.color_attributes.new(
            name=attribute_name, type="FLOAT_COLOR", domain="CORNER"
        )
        for polygon in mesh.polygons:
            for loop_index in polygon.loop_indices:
                source_index = None
                if old_domain == "POINT":
                    source_index = mesh.loops[loop_index].vertex_index
                elif old_domain == "FACE":
                    source_index = polygon.index
                elif old_domain == "CORNER":
                    source_index = loop_index
                if source_index is not None and source_index < len(old_values):
                    new_attribute.data[loop_index].color = old_values[source_index]
                else:
                    new_attribute.data[loop_index].color = (1.0, 1.0, 1.0, 1.0)


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

    # SM64CoopDX's PC build defaults to F3DEX2 Extended, not classic F3D.
    # The official CoopDX Makefile sets GRUCODE=f3dex2e by default. The Mario
    # authoring template sets the Fast64 scene to classic F3D (16 vertices),
    # which incorrectly limits skinned parent buffers to 14 entries.
    bpy.context.scene.gameEditorMode = "SM64"
    bpy.context.scene.f3d_type = "F3DEX2E"
    from fast64.fast64_internal.f3d.f3d_gbi import get_F3D_GBI
    target_gbi = get_F3D_GBI()
    require(
        target_gbi.vert_load_size == 64,
        f"Expected F3DEX2E 64-vertex load buffer, got "
        f"{target_gbi.F3D_VER}/{target_gbi.vert_load_size}",
    )
    checkpoint(
        f"target-microcode-{target_gbi.F3D_VER}-"
        f"load-{target_gbi.vert_load_size}-parent-buffer-{target_gbi.vert_load_size - 2}"
    )

    mario_arm = find_object("Mario", "ARMATURE")
    checkpoint("mario-armature-found")
    require(mario_arm.data.bones.get("Body") is not None,
            "Mario template is missing the Body root bone")
    mario_body_rest_matrix = mario_arm.data.bones["Body"].matrix_local.copy()
    checkpoint("mario-native-body-root-rest-cached")

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
    require("root ground" in source_rest_bones,
            "CJ source armature is missing its root ground bone")

    # Normalize the imported CJ root frame to Mario's native Body rest frame.
    # Without this correction the FBX root's rest rotation is copied verbatim
    # into mario_geo; DynOS then combines it with Mario's player-space root
    # transforms and the whole character can lie sideways in game. Apply only
    # a rigid rotation/translation here (never scale), so the requested 280-unit
    # model size and all per-bone dimensions remain unchanged.
    source_root_target = source_to_target @ source_rest_bones["root ground"][0]
    source_root_rotation = (
        source_root_target.to_3x3().to_quaternion().to_matrix().to_4x4()
    )
    mario_root_rotation = (
        mario_body_rest_matrix.to_3x3().to_quaternion().to_matrix().to_4x4()
    )
    root_rotation_correction = mario_root_rotation @ source_root_rotation.inverted()
    root_translation_correction = (
        mario_body_rest_matrix.translation - source_root_target.translation
    )
    root_correction = (
        Matrix.Translation(root_translation_correction)
        @ root_rotation_correction
    )
    source_to_target = root_correction @ source_to_target
    mesh_to_target = root_correction @ mesh_to_target
    aligned_source_root = source_to_target @ source_rest_bones["root ground"][0]
    require(
        (aligned_source_root.translation - mario_body_rest_matrix.translation).length < 1e-4,
        "CJ root translation did not align with Mario's native Body root",
    )
    aligned_root_quat = aligned_source_root.to_3x3().to_quaternion()
    mario_root_quat = mario_body_rest_matrix.to_3x3().to_quaternion()
    require(
        abs(abs(aligned_root_quat.dot(mario_root_quat)) - 1.0) < 1e-5,
        "CJ root orientation did not align with Mario's native Body root",
    )
    root_alignment_report = {
        "source_root_rotation_wxyz_before": [
            round(float(x), 7) for x in
            (source_root_target.to_3x3().to_quaternion().w,
             source_root_target.to_3x3().to_quaternion().x,
             source_root_target.to_3x3().to_quaternion().y,
             source_root_target.to_3x3().to_quaternion().z)
        ],
        "mario_body_rotation_wxyz": [
            round(float(x), 7) for x in
            (mario_root_quat.w, mario_root_quat.x, mario_root_quat.y, mario_root_quat.z)
        ],
        "aligned_root_translation_error": (
            aligned_source_root.translation - mario_body_rest_matrix.translation
        ).length,
        "aligned_root_rotation_dot": abs(aligned_root_quat.dot(mario_root_quat)),
    }
    checkpoint("cj-root-frame-aligned-to-native-mario-body")

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
    checkpoint("rest-pose-transfer-validated")

    # Preserve original FBX vertex-group assignments before creating the target groups.
    source_group_names = {
        group.index: group.name.strip().casefold()
        for group in source_mesh.vertex_groups
    }
    checkpoint(f"source-vertex-groups-read-{len(source_group_names)}")

    # Create a clean mesh object from copied mesh data instead of cloning the FBX
    # object and its imported modifier stack. The original FBX armature modifier
    # stays on the source object and is never attached to the new actor.
    checkpoint("before-copying-source-mesh-data")
    rigged_mesh_data = source_mesh.data.copy()
    checkpoint("source-mesh-data-copied")
    rigged_mesh_data.name = "CJ64_Rigged_MeshData"
    rigged_mesh = bpy.data.objects.new("CJ64_Rigged_Mesh", rigged_mesh_data)
    checkpoint("clean-rigged-mesh-object-created")
    bpy.context.scene.collection.objects.link(rigged_mesh)
    checkpoint("clean-rigged-mesh-object-linked")
    checkpoint("before-transforming-cj-mesh-vertices")
    vertex_count = len(rigged_mesh.data.vertices)
    coordinates = [0.0] * (vertex_count * 3)
    rigged_mesh.data.vertices.foreach_get("co", coordinates)
    for offset in range(0, len(coordinates), 3):
        transformed_point = mesh_to_target @ Vector((
            coordinates[offset],
            coordinates[offset + 1],
            coordinates[offset + 2],
        ))
        coordinates[offset] = float(transformed_point.x)
        coordinates[offset + 1] = float(transformed_point.y)
        coordinates[offset + 2] = float(transformed_point.z)
    rigged_mesh.data.vertices.foreach_set("co", coordinates)
    rigged_mesh.data.update()
    checkpoint(f"cj-mesh-vertices-transformed-{vertex_count}")
    rigged_mesh.matrix_world = Matrix.Identity(4)
    checkpoint("cj-mesh-world-matrix-reset")
    # Defer parenting and the Armature modifier until all vertex groups
    # have been populated; this prevents dependency evaluation of a half-built
    # skin while weights are being created.
    checkpoint("cj-mesh-parenting-deferred")

    # Fast64/SM64 supports one deform-bone influence per vertex. Collapse the
    # original GTA FBX weights to the strongest mapped Mario deform group;
    # use nearest retargeted segment only for any source vertex without a mapped group.
    # Fast64 requires every 0x15 DisplayList bone to remain deformable,
    # even when the CJ mesh has no vertices explicitly assigned to that
    # auxiliary Mario display-list group (e.g. Left/Right Wing DL).
    enabled_display_list_bones = []
    for bone in target_arm.data.bones:
        if bone.geo_cmd == "DisplayList" and not bone.use_deform:
            bone.use_deform = True
            enabled_display_list_bones.append(bone.name)
    checkpoint(
        "fast64-display-list-deform-bones-enabled-"
        + ",".join(sorted(enabled_display_list_bones))
    )
    for group in list(rigged_mesh.vertex_groups):
        rigged_mesh.vertex_groups.remove(group)
    checkpoint("existing-rigged-mesh-groups-cleared")
    deform_bones = [bone for bone in target_arm.data.bones if bone.use_deform]
    checkpoint(f"target-deform-bones-collected-{len(deform_bones)}")
    require(len(deform_bones) >= 15,
            f"Expected at least 15 Mario deform bones, found {len(deform_bones)}")
    groups = {bone.name: rigged_mesh.vertex_groups.new(name=bone.name)
              for bone in deform_bones}
    checkpoint(f"target-vertex-groups-created-{len(groups)}")
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

    # Fast64 partitions skinned triangles along the deform-bone tree. It
    # allows vertices from one bone to meet its direct deform parent or any
    # descendant, but not a sibling or a grandparent. Promote only boundary
    # vertices to the nearest valid ancestor so every triangle obeys that rule.
    deform_names = set(groups)
    deform_parent = {}
    for bone_name in deform_names:
        parent_bone = target_arm.data.bones[bone_name].parent
        while parent_bone is not None and parent_bone.name not in deform_names:
            parent_bone = parent_bone.parent
        deform_parent[bone_name] = parent_bone.name if parent_bone else None

    def deform_ancestors(bone_name):
        result = [bone_name]
        while deform_parent[result[-1]] is not None:
            result.append(deform_parent[result[-1]])
        return result

    labels = []
    for vertex in rigged_mesh.data.vertices:
        valid_assignments = [
            assignment for assignment in vertex.groups if assignment.weight > 0.5
        ]
        require(len(valid_assignments) == 1,
                f"Vertex {vertex.index} does not have exactly one dominant target group")
        labels.append(rigged_mesh.vertex_groups[valid_assignments[0].group].name)

    def promote_vertex_group(vertex_index, new_bone_name):
        old_bone_name = labels[vertex_index]
        if old_bone_name == new_bone_name:
            return False
        require(new_bone_name in groups,
                f"Boundary repair selected non-deform bone {new_bone_name}")
        groups[old_bone_name].remove([vertex_index])
        groups[new_bone_name].add([vertex_index], 1.0, "REPLACE")
        labels[vertex_index] = new_bone_name
        return True

    rigged_mesh.data.calc_loop_triangles()
    triangles = [
        tuple(loop_triangle.vertices)
        for loop_triangle in rigged_mesh.data.loop_triangles
    ]
    face_weight_repairs = 0
    face_weight_repair_passes = 0
    for repair_pass in range(24):
        changes_this_pass = 0
        for triangle in triangles:
            pairs = ((0, 1), (0, 2), (1, 2))
            for left_pos, right_pos in pairs:
                left_index = triangle[left_pos]
                right_index = triangle[right_pos]
                left_bone = labels[left_index]
                right_bone = labels[right_index]
                if left_bone == right_bone:
                    continue
                if (deform_parent[left_bone] == right_bone
                        or deform_parent[right_bone] == left_bone):
                    continue

                left_chain = deform_ancestors(left_bone)
                right_chain = deform_ancestors(right_bone)
                if left_bone in right_chain:
                    # The left bone is an ancestor, but not the direct parent.
                    new_bone = deform_parent[right_bone]
                    if new_bone is not None:
                        changes_this_pass += int(
                            promote_vertex_group(right_index, new_bone)
                        )
                elif right_bone in left_chain:
                    # The right bone is an ancestor, but not the direct parent.
                    new_bone = deform_parent[left_bone]
                    if new_bone is not None:
                        changes_this_pass += int(
                            promote_vertex_group(left_index, new_bone)
                        )
                else:
                    # Sibling branches cannot share a triangle. Promote both
                    # boundary vertices to their nearest common deform ancestor.
                    common_bone = next(
                        (name for name in left_chain if name in right_chain),
                        None,
                    )
                    if common_bone is None:
                        common_bone = "Body" if "Body" in groups else None
                    require(common_bone is not None,
                            f"No common deform ancestor for {left_bone} and {right_bone}")
                    changes_this_pass += int(
                        promote_vertex_group(left_index, common_bone)
                    )
                    changes_this_pass += int(
                        promote_vertex_group(right_index, common_bone)
                    )

        face_weight_repairs += changes_this_pass
        face_weight_repair_passes = repair_pass + 1
        if changes_this_pass == 0:
            break

    incompatible_face_pairs = []
    for triangle in triangles:
        triangle_groups = [labels[index] for index in triangle]
        for left_pos, right_pos in ((0, 1), (0, 2), (1, 2)):
            left_bone = triangle_groups[left_pos]
            right_bone = triangle_groups[right_pos]
            if left_bone == right_bone:
                continue
            if deform_parent[left_bone] == right_bone or deform_parent[right_bone] == left_bone:
                continue
            left_chain = deform_ancestors(left_bone)
            right_chain = deform_ancestors(right_bone)
            if left_bone in right_chain or right_bone in left_chain:
                continue
            incompatible_face_pairs.append((left_bone, right_bone))
            if len(incompatible_face_pairs) >= 8:
                break
        if len(incompatible_face_pairs) >= 8:
            break
    require(not incompatible_face_pairs,
            "Fast64 face-weight boundaries remain incompatible: "
            + str(incompatible_face_pairs))
    used_deform_groups = sorted(set(labels))
    checkpoint(
        f"fast64-face-weights-repaired-{face_weight_repairs}-changes-"
        f"{face_weight_repair_passes}-passes-{len(used_deform_groups)}-active-bones"
    )

    # Keep the new mesh disconnected from the armature while its animation
    # node map is read. The Armature modifier and parent link are added only
    # after Fast64 has traversed the copied Mario rig.
    checkpoint("skin-weights-complete-without-armature-link")

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

    # Keep the skin disconnected while the material converter and UV-island
    # builder alter the mesh/material datablocks. Fast64 exports only after
    # those operations finish, so the armature link can safely be added later.
    checkpoint("source-rig-removed-and-node-map-saved")

    # Prepare TMEM-safe textures and convert materials for Fast64.
    checkpoint("before-ensure-base-color-textures")
    fallback_materials = [
        material.name for material in rigged_mesh.data.materials
        if material is not None and shared.ensure_base_color_texture(material)
    ]
    checkpoint(f"base-color-textures-ensured-{len(fallback_materials)}")
    checkpoint("before-splitting-tmem-uv-islands")
    texture_islands = shared.split_materials_into_tmem_uv_islands(
        rigged_mesh, max_texels=2048
    )
    checkpoint(f"tmem-uv-islands-split-{texture_islands.get('island_count', 0)}")
    import fast64.fast64_internal.f3d_material_converter as converter
    import fast64.fast64_internal.f3d.f3d_material as f3d_material_module
    checkpoint("before-normalizing-fast64-color-attributes")
    ensure_f3d_color_attributes(rigged_mesh.data)
    color_attribute_report = {
        name: {
            "domain": rigged_mesh.data.attributes[name].domain,
            "data_type": rigged_mesh.data.attributes[name].data_type,
        }
        for name in ("Col", "Alpha")
    }
    checkpoint("fast64-color-attributes-normalized")

    # Fast64's batch converter calls Blender context-sensitive operators
    # while adding F3D materials. Make this mesh the unambiguous active object
    # and convert one material slot at a time so native crashes are localized.
    for obj in bpy.data.objects:
        try:
            if obj.select_get():
                obj.select_set(False)
        except ReferenceError:
            continue
    rigged_mesh.select_set(True)
    bpy.context.view_layer.objects.active = rigged_mesh
    checkpoint("rigged-mesh-selected-for-material-conversion")
    for uv_layer in rigged_mesh.data.uv_layers:
        uv_layer.name = "UVMap"

    # The Mario template already links Fast64's material library. Calling
    # createF3DMat normally re-links the same library for every material and
    # removes the linked source material after each copy. Reuse the existing
    # library material instead, and assign slots directly (Col/Alpha were
    # normalized above), avoiding duplicate library links and context operators.
    base_f3d_material = bpy.data.materials.get("fast64_f3d_material_library_beefwashere")
    if base_f3d_material is None:
        checkpoint("fast64-template-material-library-not-present-linking-once")
        f3d_material_module.link_f3d_material_library()
        base_f3d_material = bpy.data.materials.get("fast64_f3d_material_library_beefwashere")
    require(base_f3d_material is not None,
            "Fast64 F3D base material is unavailable after one library link")
    checkpoint("fast64-f3d-base-material-ready")

    def create_f3d_material_from_existing_library(obj, preset="Shaded Solid", index=None):
        checkpoint("safe-f3d-create-before-base-copy")
        material = base_f3d_material.copy()
        checkpoint("safe-f3d-create-after-base-copy")
        material.name = "f3dlite_material"
        checkpoint("safe-f3d-create-after-material-rename")
        node_tree = material.node_tree
        checkpoint("safe-f3d-create-before-isolated-scene-properties-group")
        scene_group = bpy.data.node_groups.get("CJ64_SceneProperties")
        if scene_group is None:
            scene_group = bpy.data.node_groups.new(
                "CJ64_SceneProperties", "ShaderNodeTree"
            )
            output_node = scene_group.nodes.new("NodeGroupOutput")
            scene_output_specs = [
                ("FogEnable", "NodeSocketFloat", 0.0),
                ("FogColor", "NodeSocketColor", (0.0, 0.0, 0.0, 1.0)),
                ("F3D_NearClip", "NodeSocketFloat", 0.1),
                ("F3D_FarClip", "NodeSocketFloat", 1000.0),
                ("Blender_Game_Scale", "NodeSocketFloat", 1.0),
                ("FogNear", "NodeSocketFloat", 0.0),
                ("FogFar", "NodeSocketFloat", 1000.0),
                ("AmbientColor", "NodeSocketColor", (1.0, 1.0, 1.0, 1.0)),
                ("Light0Color", "NodeSocketColor", (1.0, 1.0, 1.0, 1.0)),
                ("Light0Dir", "NodeSocketVector", (0.0, 0.0, 1.0)),
                ("Light0Size", "NodeSocketFloat", 1.0),
                ("Light1Color", "NodeSocketColor", (1.0, 1.0, 1.0, 1.0)),
                ("Light1Dir", "NodeSocketVector", (0.0, 0.0, 1.0)),
                ("Light1Size", "NodeSocketFloat", 1.0),
            ]
            for socket_name, socket_type, default_value in scene_output_specs:
                scene_group.interface.new_socket(
                    name=socket_name, socket_type=socket_type, in_out="OUTPUT"
                )
                output_node.inputs[socket_name].default_value = default_value
            scene_group["version"] = 2
        checkpoint("safe-f3d-create-isolated-scene-properties-group-ready")

        scene_props = node_tree.nodes.new(type="ShaderNodeGroup")
        checkpoint("safe-f3d-create-after-scene-properties-node")
        scene_props.name = "SceneProperties"
        scene_props.location = (-320, -23)
        scene_props.node_tree = scene_group
        checkpoint("safe-f3d-create-after-scene-properties-node-tree")

        scene_links = [
            ("FogEnable", "FogEnable", 0),
            ("FogColor", "FogColor", 0),
            ("F3D_NearClip", "CalcFog", "F3D_NearClip"),
            ("F3D_FarClip", "CalcFog", "F3D_FarClip"),
            ("Blender_Game_Scale", "CalcFog", "Blender_Game_Scale"),
            ("FogNear", "CalcFog", "FogNear"),
            ("FogFar", "CalcFog", "FogFar"),
            ("AmbientColor", "AmbientColor", 0),
            ("Light0Color", "Light0Color", 0),
            ("Light0Dir", "Light0Dir", 0),
            ("Light0Size", "Light0Size", 0),
            ("Light1Color", "Light1Color", 0),
            ("Light1Dir", "Light1Dir", 0),
            ("Light1Size", "Light1Size", 0),
        ]
        for output_name, target_node_name, input_name in scene_links:
            target_input = node_tree.nodes[target_node_name].inputs[input_name]
            node_tree.links.new(scene_props.outputs[output_name], target_input)
            checkpoint(f"safe-f3d-create-scene-link-{output_name}")
        checkpoint("safe-f3d-create-after-scene-properties")
        if index is None:
            obj.data.materials.append(material)
            obj.active_material_index = len(obj.material_slots) - 1
        else:
            obj.data.materials[index] = material
            obj.active_material_index = index
        checkpoint("safe-f3d-create-after-material-slot-assignment")
        material.is_f3d = True
        material.mat_ver = converter.F3D_MAT_CUR_VERSION
        checkpoint("safe-f3d-create-after-f3d-flags")
        converter.update_preset_manual_v4(material, preset)
        checkpoint("safe-f3d-create-after-preset")
        return material

    converter.createF3DMat = create_f3d_material_from_existing_library
    checkpoint("fast64-f3d-material-creation-patched-to-reuse-library")

    material_dict = {}
    checkpoint(f"before-fast64-material-conversion-{len(rigged_mesh.material_slots)}-slots")
    for slot_index, slot in enumerate(rigged_mesh.material_slots):
        material = slot.material
        if material is None or material.is_f3d:
            checkpoint(f"material-slot-{slot_index}-already-compatible")
            continue
        if material in material_dict:
            slot.material = material_dict[material]
            checkpoint(f"material-slot-{slot_index}-reused-{material.name}")
            continue
        checkpoint(f"before-material-slot-{slot_index}-{material.name}")
        converter.convertBSDFtoF3D(
            rigged_mesh, slot_index, material, material_dict
        )
        checkpoint(f"after-material-slot-{slot_index}-{material.name}")
    checkpoint("fast64-material-conversion-completed")
    unresolved_materials = [
        material.name for material in rigged_mesh.data.materials
        if material and not bool(getattr(material, "is_f3d", False))
    ]
    require(not unresolved_materials,
            "Fast64 material conversion failed: " + ", ".join(unresolved_materials))
    checkpoint("fast64-materials-validated")

    # Fast64's skinned mesh buffer reserves two entries from the active
    # microcode's vertex-load window. Calculate the parent capacity from the
    # same GBI configuration used by the export operator instead of assuming
    # classic F3D's 16-vertex limit. Estimate usage with Fast64's own F3DVert
    # and BufferVertex equality rules (position, UV, color, normal, alpha, material).
    import fast64.fast64_internal.f3d.f3d_writer as f3d_writer
    checkpoint("before-measuring-fast64-parent-vertex-buffers")
    mesh_info = f3d_writer.getInfoDict(rigged_mesh)
    checkpoint("fast64-mesh-info-ready-for-buffer-measurement")

    def f3d_buffer_vertex_key(f3d_vertex, material_index):
        return (
            tuple(float(value) for value in f3d_vertex.position),
            tuple(float(value) for value in f3d_vertex.uv),
            f3d_vertex.stOffset,
            tuple(float(value) for value in f3d_vertex.rgb)
                if f3d_vertex.rgb is not None else None,
            tuple(float(value) for value in f3d_vertex.normal)
                if f3d_vertex.normal is not None else None,
            float(f3d_vertex.alpha),
            int(material_index),
        )

    def measure_parent_buffer(bone_name):
        parent_name = deform_parent[bone_name]
        if parent_name is None:
            return {}, {}, set()

        layer_material_keys = {}
        key_contributors = {}
        candidate_vertices = set()
        seen_faces = set()
        for vertex_index, label in enumerate(labels):
            if label != bone_name:
                continue
            for face in mesh_info.vert.get(vertex_index, ()):
                face_index = int(face.index)
                if face_index in seen_faces:
                    continue
                seen_faces.add(face_index)
                face_labels = [labels[int(index)] for index in face.vertices]

                # Fast64 skips faces connected to any other bone on the
                # current branch (ancestor or descendant), except for the
                # immediate deform parent whose vertices enter this buffer.
                # Only cross-branch/sibling groups are invalid here.
                related_non_parent = any(
                    label_name not in (bone_name, parent_name)
                    and (
                        label_name in deform_ancestors(bone_name)[1:]
                        or bone_name in deform_ancestors(label_name)[1:]
                    )
                    for label_name in face_labels
                )
                if related_non_parent:
                    continue

                unexpected = [
                    label_name for label_name in face_labels
                    if label_name not in (bone_name, parent_name)
                ]
                require(
                    not unexpected,
                    f"Fast64 buffer measurement for {bone_name} found "
                    f"unexpected adjacent groups: {unexpected}",
                )

                material_index = int(face.material_index)
                material = rigged_mesh.material_slots[material_index].material
                f3d_material = material.f3d_mat if material.mat_ver > 3 else material
                draw_layer = int(f3d_material.draw_layer.sm64)
                buffer_key = (draw_layer, material_index)
                unique_vertices = layer_material_keys.setdefault(buffer_key, set())

                for loop_index in face.loops:
                    loop = rigged_mesh.data.loops[int(loop_index)]
                    parent_vertex_index = int(loop.vertex_index)
                    if labels[parent_vertex_index] != parent_name:
                        continue
                    candidate_vertices.add(parent_vertex_index)
                    f3d_vertex = mesh_info.f3dVert[int(loop_index)]
                    vertex_key = f3d_buffer_vertex_key(f3d_vertex, material_index)
                    unique_vertices.add(vertex_key)
                    key_contributors.setdefault(
                        (draw_layer, material_index, vertex_key), set()
                    ).add(parent_vertex_index)

        counts_by_layer = {}
        for (draw_layer, material_index), unique_vertices in layer_material_keys.items():
            counts_by_layer[draw_layer] = (
                counts_by_layer.get(draw_layer, 0) + len(unique_vertices)
            )
        return counts_by_layer, key_contributors, candidate_vertices

    def can_promote_parent_vertex(vertex_index, child_bone_name):
        # Fast64 treats any ancestor/descendant on the active bone branch as a
        # child-skinned face (except the immediate parent, which is buffered).
        # Only cross-branch/sibling labels are unsafe. Requiring an immediate
        # parent-child pair here was too strict and blocked valid limb repairs.
        for face in mesh_info.vert.get(vertex_index, ()):
            simulated = [
                child_bone_name if int(index) == vertex_index else labels[int(index)]
                for index in face.vertices
            ]
            for left_pos, right_pos in ((0, 1), (0, 2), (1, 2)):
                left_name = simulated[left_pos]
                right_name = simulated[right_pos]
                if left_name == right_name:
                    continue
                if (left_name in deform_ancestors(right_name)
                        or right_name in deform_ancestors(left_name)):
                    continue
                return False
        return True

    capacity_repair_count = 0
    max_parent_buffer_vertices = target_gbi.vert_load_size - 2
    checkpoint(f"fast64-parent-buffer-capacity-{max_parent_buffer_vertices}")
    for capacity_pass in range(len(rigged_mesh.data.vertices) + 1):
        measurements = {}
        worst = None
        for bone_name in deform_names:
            counts_by_layer, contributors, candidates = measure_parent_buffer(bone_name)
            if counts_by_layer:
                worst_layer, worst_count = max(
                    counts_by_layer.items(), key=lambda item: item[1]
                )
                measurements[bone_name] = (
                    counts_by_layer, contributors, candidates
                )
                if worst_count > max_parent_buffer_vertices and (
                    worst is None or worst_count > worst[0]
                ):
                    worst = (
                        worst_count, bone_name, worst_layer,
                        contributors, candidates,
                    )

        if worst is None:
            break

        worst_count, bone_name, draw_layer, contributors, candidates = worst
        safe_candidates = []
        for vertex_index in candidates:
            if labels[vertex_index] != deform_parent[bone_name]:
                continue
            if not can_promote_parent_vertex(vertex_index, bone_name):
                continue
            exclusive_keys = [
                key for key, vertex_set in contributors.items()
                if key[0] == draw_layer
                and vertex_set == {vertex_index}
            ]
            benefit = len(exclusive_keys)
            if benefit > 0:
                safe_candidates.append((benefit, vertex_index))

        require(
            safe_candidates,
            f"Fast64 parent buffer for {bone_name} on draw layer {draw_layer} "
            f"has {worst_count} unique vertices (maximum {max_parent_buffer_vertices}), but no boundary "
            "vertex can be promoted without violating the adjacent bone hierarchy",
        )
        safe_candidates.sort(reverse=True)
        best_benefit, best_vertex = safe_candidates[0]
        promote_vertex_group(best_vertex, bone_name)
        capacity_repair_count += 1
        if capacity_repair_count % 4 == 0:
            checkpoint(
                f"fast64-parent-buffer-repair-{capacity_repair_count}-"
                f"promoted-{best_benefit}-vertices-from-{bone_name}"
            )
    else:
        raise RuntimeError(
            "Fast64 parent-buffer repair exceeded the mesh vertex count"
        )

    final_buffer_overflows = []
    for bone_name in deform_names:
        counts_by_layer, _, _ = measure_parent_buffer(bone_name)
        for draw_layer, count in counts_by_layer.items():
            if count > max_parent_buffer_vertices:
                final_buffer_overflows.append(
                    (bone_name, draw_layer, count)
                )
    require(
        not final_buffer_overflows,
        f"Fast64 parent vertex buffers still exceed {max_parent_buffer_vertices} entries: "
        + str(final_buffer_overflows[:8]),
    )
    used_deform_groups = sorted(set(labels))
    checkpoint(
        f"fast64-parent-buffers-repaired-{capacity_repair_count}-promotions-"
        f"{len(used_deform_groups)}-active-bones"
    )

    # Bind the completed, texture-converted mesh only now.
    for old_modifier in list(rigged_mesh.modifiers):
        rigged_mesh.modifiers.remove(old_modifier)
    arm_mod = rigged_mesh.modifiers.new("CJ64_Mario_Skin", "ARMATURE")
    arm_mod.object = target_arm
    arm_mod.use_vertex_groups = True
    arm_mod.use_bone_envelopes = False
    rigged_mesh.parent = target_arm
    checkpoint("finished-skin-bound-after-material-conversion")

    # Export through Fast64-Gart's current Combined Exporter settings.
    # The armature GeoLayout operator still exists, but it now reads from
    # scene.fast64.sm64.combined_export instead of the legacy geo* Scene props.
    mod_dir = output_dir / "CJ64-Rigged-Test"
    pack_dir = output_dir / "CJ64"
    mod_dir.mkdir(parents=True, exist_ok=True)
    pack_dir.mkdir(parents=True, exist_ok=True)
    # DynOS scans folders under dynos/packs as independent packs. Keep the
    # actor sources in pack_dir/Assets so DynOS generates the .bin in pack_dir.
    actor_root = pack_dir
    scene = bpy.context.scene
    scene.gameEditorMode = "SM64"
    # gameEditorMode's update callback restores the legacy F3D default; reset
    # the explicit CoopDX target microcode after that callback before exporting.
    scene.f3d_type = "F3DEX2E"
    export_gbi = get_F3D_GBI()
    require(
        export_gbi.F3D_VER == target_gbi.F3D_VER
        and export_gbi.vert_load_size == target_gbi.vert_load_size,
        "The scene microcode changed between buffer measurement and export",
    )
    checkpoint(f"final-export-microcode-{export_gbi.F3D_VER}-load-{export_gbi.vert_load_size}")
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
    combined.custom_include_directory = "Assets/"
    combined.object_name = "Assets"
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

    # The copied Mario geolayout has optional cap-state mesh switches pointing
    # to auxiliary armatures removed during template isolation. CJ is a single
    # skinned mesh and does not use Mario's cap variants, so remove only orphaned
    # Mesh options while preserving the base Switch bone and its normal children.
    removed_orphan_switch_options = []
    for bone in target_arm.data.bones:
        if bone.geo_cmd != "Switch":
            continue
        for option_index in reversed(range(len(bone.switch_options))):
            switch_option = bone.switch_options[option_index]
            if (switch_option.switchType == "Mesh"
                    and switch_option.optionArmature is None):
                removed_orphan_switch_options.append(
                    {"bone": bone.name, "option_index": option_index}
                )
                bone.switch_options.remove(option_index)
    checkpoint(
        f"orphaned-mario-mesh-switch-options-removed-{len(removed_orphan_switch_options)}"
    )
    require(
        not any(
            bone.geo_cmd == "Switch"
            and any(
                option.switchType == "Mesh" and option.optionArmature is None
                for option in bone.switch_options
            )
            for bone in target_arm.data.bones
        ),
        "The target armature still contains orphaned mesh switch options",
    )

    bpy.ops.object.select_all(action="DESELECT")
    target_arm.select_set(True)
    bpy.context.view_layer.objects.active = target_arm
    if bpy.context.object.mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")
    export_result = bpy.ops.object.sm64_export_geolayout_armature(export_obj=target_arm.name)
    require("FINISHED" in export_result,
            f"Fast64-Gart armature export did not finish: {export_result}")
    actor_dir = actor_root / "Assets"
    require((actor_dir / "geo.inc.c").is_file() and
            (actor_dir / "model.inc.c").is_file(),
            "Fast64 did not create the CJ DynOS actor files")

    # Fast64 names the root GeoLayout after the export object, so the name
    # varies with the pack's source-folder name. DynOS associates player-model
    # packs by the builtin root name; Mario must therefore use mario_geo.
    dynos_geo_name = "mario_geo"
    geo_path = actor_dir / "geo.inc.c"
    header_path = actor_dir / "geo_header.h"
    require(geo_path.is_file() and header_path.is_file(),
            "Fast64 did not create geo.inc.c and geo_header.h")
    geo_source = geo_path.read_text(encoding="utf-8")
    declarations = re.findall(r"\bGeoLayout\s+([A-Za-z_][A-Za-z0-9_]*)\s*\[\s*\]\s*=", geo_source)
    require(declarations, "Fast64 geo.inc.c contains no GeoLayout declarations")
    fast64_root_name = declarations[-1]
    require(fast64_root_name != dynos_geo_name,
            "Fast64 unexpectedly already exported the Mario root symbol")
    geo_header = header_path.read_text(encoding="utf-8")
    root_token = re.compile(r"\b" + re.escape(fast64_root_name) + r"\b")
    require(root_token.search(geo_header) is not None,
            f"geo_header.h does not declare Fast64 root symbol {fast64_root_name}")
    geo_source = root_token.sub(dynos_geo_name, geo_source)
    geo_header = root_token.sub(dynos_geo_name, geo_header)
    geo_path.write_text(geo_source, encoding="utf-8")
    header_path.write_text(geo_header, encoding="utf-8")
    require(re.search(r"\bGeoLayout\s+" + re.escape(dynos_geo_name) + r"\s*\[\s*\]\s*=", geo_source) is not None,
            "Mario root GeoLayout symbol was not written")
    require(f"extern const GeoLayout {dynos_geo_name}[];" in geo_header,
            "Mario root GeoLayout declaration is missing")

    repo_root = Path(__file__).resolve().parents[1]
    shutil.copy2(repo_root / "main.lua", mod_dir / "main.lua")
    shutil.copy2(repo_root / "character.lua", mod_dir / "character.lua")
    (mod_dir / "rigged_actor.lua").write_text(
        "CJ64 = CJ64 or {}\nCJ64.riggedActor = true\n", encoding="utf-8"
    )
    (mod_dir / "README-INSTALL.txt").write_text(
        "CJ64 experimental player-model test. Root GeoLayout symbol: mario_geo. "
        "Install this Lua folder as mods/CJ64-Rigged-Test and the separate CJ64 "
        "folder as dynos/packs/CJ64. The pack contains Assets/model.inc.c, "
        "Assets/geo.inc.c and its textures. SM64CoopDX scans dynos/packs at startup "
        "and generates CJ64/mario_geo.bin from those sources. The Lua controller "
        "enables the CJ64 DynOS pack before requesting the model by its GeoLayout "
        "name. Do not put the CJ64 pack inside mods. The private "
        "cj64_gta_animations.lua module is not included in this export. "
        "Test the actor in SM64CoopDX before treating this as a release.\\n",
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
        "axis_alignment": "source FBX Y-up to Mario template X-up: Rz(-90 degrees), followed by rigid CJ-root to native Mario Body alignment",
        "root_alignment": root_alignment_report,
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
        "dynos_geolayout_name": dynos_geo_name,
        "dynos_pack_name": "CJ64",
        "dynos_pack_actor_folder": "Assets",
        "actor_files": [str(path.relative_to(pack_dir)) for path in actor_dir.rglob("*") if path.is_file()],
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
    print(json.dumps({
        "scene": str(scene_path), "report": str(report_path),
        "lua_mod_dir": str(mod_dir), "dynos_pack_dir": str(pack_dir), **report
    }, indent=2))


if __name__ == "__main__":
    main()
