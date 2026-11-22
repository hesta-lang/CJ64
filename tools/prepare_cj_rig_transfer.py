#!/usr/bin/env python3
"""Transfer the CJ FBX skin to the inspected SM64CoopDX Mario/Fast64 armature.

This is a rig-transfer preview stage only. It deliberately does not export or
enable an in-game actor until the resulting pose and Fast64 hierarchy are
visually approved.
"""
from __future__ import annotations
import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Matrix, Vector


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def find_object(name, object_type):
    obj = bpy.data.objects.get(name)
    require(obj is not None and obj.type == object_type,
            f"Expected {object_type} object '{name}' in rig-inspection scene")
    return obj


def set_edit_bone_from_source(edit_bone, source_bone, source_to_target):
    matrix = source_to_target @ source_bone.matrix_local
    edit_bone.matrix = matrix
    edit_bone.length = max(0.001, source_bone.length * source_to_target.to_scale().x)
    edit_bone.use_connect = False


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    if len(argv) != 2:
        raise SystemExit("usage: prepare_cj_rig_transfer.py <inspection.blend> <output_dir>")
    blend_path, output_dir = Path(argv[0]).resolve(), Path(argv[1]).resolve()
    require(blend_path.is_file(), f"Rig inspection blend missing: {blend_path}")
    output_dir.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.open_mainfile(filepath=str(blend_path))

    source_arm = find_object("CJ_SRC__Armature", "ARMATURE")
    source_mesh = find_object("CJ_SRC__Object001", "MESH")
    mario_arm = find_object("Mario", "ARMATURE")
    require(source_mesh.find_armature() == source_arm,
            "CJ source mesh is not bound to CJ_SRC__Armature")

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

    # Duplicate the template armature so the inspection source remains untouched.
    source_mesh_name = source_mesh.name

    target_arm = mario_arm.copy()
    target_arm.data = mario_arm.data.copy()
    target_arm.name = "CJ64_Mario_Armature"
    target_arm.data.name = "CJ64_Mario_ArmatureData"
    target_arm.matrix_world = Matrix.Identity(4)
    bpy.context.scene.collection.objects.link(target_arm)

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
    bpy.context.view_layer.objects.active = target_arm
    target_arm.select_set(True)
    bpy.ops.object.mode_set(mode="EDIT")
    missing_target_bones = []
    missing_source_bones = []
    for target_name, source_name in target_bone_sources.items():
        edit_bone = target_arm.data.edit_bones.get(target_name)
        source_bone = source_arm.data.bones.get(source_name)
        if edit_bone is None:
            missing_target_bones.append(target_name)
            continue
        if source_bone is None:
            missing_source_bones.append(source_name)
            continue
        set_edit_bone_from_source(edit_bone, source_bone, source_to_target)
    bpy.ops.object.mode_set(mode="OBJECT")
    require(not missing_target_bones,
            "Mario template is missing expected bones: " + ", ".join(missing_target_bones))
    require(not missing_source_bones,
            "CJ source armature is missing expected bones: " + ", ".join(missing_source_bones))

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

    # Generate deterministic skin weights from the nearest retargeted deform-bone
    # segments. Automatic heat weights fail on this source's overlapping helper
    # bones; this distance-based pass keeps every vertex attached to real limbs.
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

    for vertex in rigged_mesh.data.vertices:
        point = vertex.co
        distances = []
        for name, head, axis_vec, axis_len_sq in segments:
            amount = max(0.0, min(1.0, (point - head).dot(axis_vec) / axis_len_sq))
            nearest = head + axis_vec * amount
            distances.append(((point - nearest).length, name))
        # Fast64/SM64 skinning uses a single deform-bone influence per
        # vertex. Assign the closest deform segment at full weight instead
        # of Blender-style smooth multi-bone weights.
        distance, nearest_bone = min(distances)
        groups[nearest_bone].add([vertex.index], 1.0, "REPLACE")

    # The copied FBX object still references the source armature; remove that
    # modifier before binding it to the retargeted Mario armature.
    for old_modifier in list(rigged_mesh.modifiers):
        rigged_mesh.modifiers.remove(old_modifier)
    arm_mod = rigged_mesh.modifiers.new("CJ64_Mario_Skin", "ARMATURE")
    arm_mod.object = target_arm
    arm_mod.use_vertex_groups = True
    arm_mod.use_bone_envelopes = False
    rigged_mesh.parent = target_arm

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
    require(abs(bounds[0] - target_height) < 0.03,
            f"CJ target height is not 2.8 units on Mario X-up rig: {bounds}")

    report = {
        "format": "cj64-rig-transfer-preview-v1",
        "status": "RIGGED_PREVIEW_NOT_FAST64_EXPORTED_OR_IN_GAME_TESTED",
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
        "bounds_after_armature_evaluation": bounds,
        "preview_image": "CJ64-Rigged-Rest-Preview.png",
        "notes": [
            "First rig-transfer pass; deterministic nearest-bone-segment weights were generated for the Mario/Fast64 deform bones.",
            "Mario helper hierarchy was retained and the corresponding source rest matrices were applied to animation bones.",
            "Inspect all major poses before Fast64 export; no runtime animation is enabled by this workflow.",
            "The original CJ mesh and source IFP are not added to the repository by this script."
        ]
    }
    report_path = output_dir / "cj64_rig_transfer_report.json"
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    # Render a rest-pose preview with the Mario template's X-up orientation.
    scene = bpy.context.scene
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
    print(json.dumps({"scene": str(scene_path), "report": str(report_path), **report}, indent=2))


if __name__ == "__main__":
    main()
