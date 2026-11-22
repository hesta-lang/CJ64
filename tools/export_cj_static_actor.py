#!/usr/bin/env python3
"""Export the prepared static CJ GLB as an SM64CoopDX DynOS actor."""
from __future__ import annotations
import json, math, os, re, shutil, sys, zipfile
from array import array
from pathlib import Path
import bpy
from mathutils import Matrix, Vector


def require(ok, message):
    if not ok:
        raise RuntimeError(message)


def mesh_summary(obj):
    """Return numeric bounds for a mesh after its object transform is applied."""
    coords = [tuple(float(c) for c in vertex.co) for vertex in obj.data.vertices]
    require(bool(coords), f"Mesh {obj.name} has no vertices")
    minimum = [min(point[i] for point in coords) for i in range(3)]
    maximum = [max(point[i] for point in coords) for i in range(3)]
    dimensions = [maximum[i] - minimum[i] for i in range(3)]
    return {
        "name": obj.name,
        "vertices": len(obj.data.vertices),
        "faces": len(obj.data.polygons),
        "minimum": minimum,
        "maximum": maximum,
        "dimensions": dimensions,
        "max_dimension": max(dimensions),
    }


def combined_mesh_bounds(meshes):
    coords = [tuple(float(c) for c in vertex.co)
              for obj in meshes for vertex in obj.data.vertices]
    require(bool(coords), "Imported model has no mesh vertices")
    minimum = [min(point[i] for point in coords) for i in range(3)]
    maximum = [max(point[i] for point in coords) for i in range(3)]
    dimensions = [maximum[i] - minimum[i] for i in range(3)]
    return {"minimum": minimum, "maximum": maximum, "dimensions": dimensions,
            "max_dimension": max(dimensions)}



def render_glb_import_preview(obj, output_path, view="front"):
    """Render imported glTF materials in Blender 3.6 before Fast64 conversion."""
    scene = bpy.context.scene
    original_engine = scene.render.engine
    original_filepath = scene.render.filepath
    original_x = scene.render.resolution_x
    original_y = scene.render.resolution_y
    original_percentage = scene.render.resolution_percentage

    target = (float(obj.location.x), float(obj.location.y),
              float(obj.location.z + obj.dimensions.z * 0.52))
    camera_data = bpy.data.cameras.new("CJ64_Diagnostic_Camera")
    camera = bpy.data.objects.new("CJ64_Diagnostic_Camera", camera_data)
    scene.collection.objects.link(camera)
    camera.location = (2.9, -4.8, 2.45) if view == "front" else (2.9, 4.8, 2.45)
    direction = Vector(target) - camera.location
    camera.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()
    camera_data.lens = 58
    scene.camera = camera

    lights = []
    light_specs = [
        ("CJ64_Key", (2.0, -3.0, 3.5), 650.0, 3.2),
        ("CJ64_Fill", (-3.0, -1.5, 2.2), 350.0, 4.0),
        ("CJ64_Rim", (0.0, 3.0, 2.8), 450.0, 3.0),
    ]
    for name, location, energy, size in light_specs:
        data = bpy.data.lights.new(name, "AREA")
        data.energy = energy
        data.shape = "DISK"
        data.size = size
        light = bpy.data.objects.new(name, data)
        scene.collection.objects.link(light)
        light.location = location
        light.rotation_euler = (Vector(target) - light.location).to_track_quat("-Z", "Y").to_euler()
        lights.append(light)

    if scene.world is None:
        scene.world = bpy.data.worlds.new("CJ64_Diagnostic_World")
    scene.world.use_nodes = True
    background = scene.world.node_tree.nodes.get("Background")
    if background is not None:
        background.inputs["Color"].default_value = (0.055, 0.055, 0.055, 1.0)
        background.inputs["Strength"].default_value = 0.8

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
    scene.render.filepath = str(output_path)
    bpy.ops.render.render(write_still=True)

    scene.render.engine = original_engine
    scene.render.filepath = original_filepath
    scene.render.resolution_x = original_x
    scene.render.resolution_y = original_y
    scene.render.resolution_percentage = original_percentage

    return {
        "path": output_path.name,
        "engine": "BLENDER_EEVEE",
        "render_size": [900, 900],
        "camera": list(camera.location),
        "lighting": [name for name, *_ in light_specs],
        "mesh_materials": [
            {
                "name": material.name if material else None,
                "image_textures": (
                    [node.image.name for node in material.node_tree.nodes
                     if node.type == "TEX_IMAGE" and node.image]
                    if material and material.use_nodes else []
                ),
            }
            for material in obj.data.materials
        ],
    }


def largest_power_of_two_at_most(value):
    value = max(1, int(value))
    return 1 << (value.bit_length() - 1)


def tmem_safe_dimensions(width, height, max_texels=2048):
    """Return dimensions whose row-padded RGBA16 footprint fits N64 TMEM.

    Fast64 pads each RGBA16 row to a 64-bit boundary (four texels). Therefore
    TMEM cost is ceil(width / 4) * 4 * height, not width * height.
    """
    width, height = max(1, int(width)), max(1, int(height))
    scale = min(
        1.0,
        64.0 / float(width),
        64.0 / float(height),
        (max_texels / float(max(4, ((width + 3) // 4) * 4) * height)) ** 0.5,
    )
    target_w = max(4, min(64, int(width * scale) // 4 * 4))
    target_h = max(1, min(64, int(round(height * scale))))

    def padded_texels(w, h):
        return ((w + 3) // 4 * 4) * h

    while padded_texels(target_w, target_h) > max_texels:
        width_error = abs((target_w - 4) / float(width) - target_h / float(height))
        height_error = abs(target_w / float(width) - (target_h - 1) / float(height))
        if target_w > 4 and (target_h == 1 or width_error < height_error):
            target_w -= 4
        elif target_h > 1:
            target_h -= 1
        elif target_w > 4:
            target_w -= 4
        else:
            raise RuntimeError(
                f"Unable to fit {width}x{height} texture into {max_texels} RGBA16 TMEM texels"
            )
    return target_w, target_h


def material_base_image(material):
    if not material or not material.use_nodes or not material.node_tree:
        return None
    principled = next((n for n in material.node_tree.nodes if n.type == "BSDF_PRINCIPLED"), None)
    if principled is not None:
        base = principled.inputs.get("Base Color")
        if base is not None:
            for link in base.links:
                node = link.from_node
                if node.type == "TEX_IMAGE" and node.image:
                    return node.image
    return next((n.image for n in material.node_tree.nodes
                 if n.type == "TEX_IMAGE" and n.image), None)


def face_uv_islands(mesh, material_index, uv_layer, epsilon=1e-5):
    """Find connected UV islands for a material by matching shared UV edges."""
    from collections import defaultdict, deque

    edge_records = defaultdict(list)
    face_ids = [poly.index for poly in mesh.polygons if poly.material_index == material_index]
    for face_id in face_ids:
        loops = list(mesh.polygons[face_id].loop_indices)
        for i, loop_index in enumerate(loops):
            next_loop = loops[(i + 1) % len(loops)]
            va = mesh.loops[loop_index].vertex_index
            vb = mesh.loops[next_loop].vertex_index
            uva = tuple(float(v) for v in uv_layer.data[loop_index].uv)
            uvb = tuple(float(v) for v in uv_layer.data[next_loop].uv)
            key = tuple(sorted((va, vb)))
            endpoint_uv = (uva, uvb) if va <= vb else (uvb, uva)
            edge_records[key].append((face_id, endpoint_uv))

    adjacency = {face_id: set() for face_id in face_ids}
    def uv_equal(a, b):
        return abs(a[0] - b[0]) <= epsilon and abs(a[1] - b[1]) <= epsilon

    for records in edge_records.values():
        for i in range(len(records)):
            face_a, uv_a = records[i]
            for j in range(i + 1, len(records)):
                face_b, uv_b = records[j]
                if face_a != face_b and uv_equal(uv_a[0], uv_b[0]) and uv_equal(uv_a[1], uv_b[1]):
                    adjacency[face_a].add(face_b)
                    adjacency[face_b].add(face_a)

    islands, unseen = [], set(face_ids)
    while unseen:
        start_face = unseen.pop()
        component, queue = {start_face}, deque([start_face])
        while queue:
            current = queue.popleft()
            for other in adjacency[current]:
                if other in unseen:
                    unseen.remove(other)
                    component.add(other)
                    queue.append(other)
        islands.append(sorted(component))
    return islands


def create_cropped_uv_image(source_image, source_material, island_id, uv_bounds,
                            island_report, max_texels=2048, padding=1):
    """Create a high-detail local image crop for one UV island."""
    width, height = int(source_image.size[0]), int(source_image.size[1])
    require(width > 0 and height > 0,
            f"Source atlas {source_image.name} has no decoded dimensions: {width}x{height}")
    umin, vmin, umax, vmax = uv_bounds
    x0 = max(0, int(math.floor(umin * width)) - padding)
    x1 = min(width, int(math.ceil(umax * width)) + padding)
    y0 = max(0, int(math.floor(vmin * height)) - padding)
    y1 = min(height, int(math.ceil(vmax * height)) + padding)
    x1, y1 = max(x0 + 1, x1), max(y0 + 1, y1)
    crop_w, crop_h = x1 - x0, y1 - y0

    # Blender stores pixels row-major from the lower-left, the same origin as UVs.
    source_pixels = array("f", [0.0]) * (width * height * 4)
    source_image.pixels.foreach_get(source_pixels)
    require(len(source_pixels) == width * height * 4,
            f"Source image pixel count mismatch for {source_image.name}: "
            f"{len(source_pixels)} != {width * height * 4}")
    cropped_pixels = []
    for y in range(y0, y1):
        start = (y * width + x0) * 4
        cropped_pixels.extend(source_pixels[start:start + crop_w * 4])

    image = bpy.data.images.new(
        f"CJ64_{source_material.name}_uv{island_id:03d}",
        width=crop_w, height=crop_h, alpha=True
    )
    require(len(cropped_pixels) == crop_w * crop_h * 4,
            f"UV crop pixel count mismatch for {image.name}: "
            f"{len(cropped_pixels)} != {crop_w * crop_h * 4}")
    image.pixels.foreach_set(cropped_pixels)
    image.update()

    target_w, target_h = tmem_safe_dimensions(crop_w, crop_h, max_texels)
    if (crop_w, crop_h) != (target_w, target_h):
        image.scale(target_w, target_h)
        image.update()
    image.pack()

    padded_tmem_texels = ((target_w + 3) // 4 * 4) * target_h
    island_report.append({
        "source_material": source_material.name,
        "source_image": source_image.name,
        "island": island_id,
        "source_size": [width, height],
        "source_crop": [x0, y0, x1, y1],
        "crop_size": [crop_w, crop_h],
        "export_size": [target_w, target_h],
        "row_padded_tmem_texels": padded_tmem_texels,
        "rgba16_bytes": padded_tmem_texels * 2,
        "uv_bounds": [umin, vmin, umax, vmax],
    })
    return image, (x0, y0, crop_w, crop_h)


def split_materials_into_tmem_uv_islands(obj, max_texels=2048):
    """Crop the original atlas per UV island instead of shrinking the whole atlas.

    Every resulting texture is <= 4 KiB RGBA16, has local 0..1 UV coordinates,
    and uses normal zero-origin texture loads in SM64CoopDX.
    """
    mesh = obj.data
    require(len(mesh.uv_layers) > 0, "CJ mesh has no UV layer")
    uv_layer = mesh.uv_layers.get("UVMap") or mesh.uv_layers[0]
    uv_layer.name = "UVMap"

    original_material_count = len(mesh.materials)
    island_report, generated = [], 0
    for material_index in range(original_material_count):
        if material_index >= len(mesh.materials):
            continue
        source_material = mesh.materials[material_index]
        source_image = material_base_image(source_material)
        if source_image is None:
            continue
        width, height = int(source_image.size[0]), int(source_image.size[1])

        islands = face_uv_islands(mesh, material_index, uv_layer)
        for island_number, face_ids in enumerate(islands):
            loop_ids = [loop_index for face_id in face_ids
                        for loop_index in mesh.polygons[face_id].loop_indices]
            coords = [tuple(float(v) for v in uv_layer.data[index].uv) for index in loop_ids]
            umin, vmin = min(v[0] for v in coords), min(v[1] for v in coords)
            umax, vmax = max(v[0] for v in coords), max(v[1] for v in coords)
            require(umin >= -0.001 and vmin >= -0.001 and umax <= 1.001 and vmax <= 1.001,
                    f"{source_material.name} UV island {island_number} exceeds [0,1]: "
                    f"{[umin, vmin, umax, vmax]}")

            image, crop = create_cropped_uv_image(
                source_image, source_material, island_number,
                (umin, vmin, umax, vmax), island_report, max_texels
            )
            x0, y0, crop_w, crop_h = crop

            new_material = source_material.copy()
            new_material.name = f"{source_material.name}_uv{island_number:03d}"
            for node in new_material.node_tree.nodes:
                if node.type == "TEX_IMAGE" and node.image == source_image:
                    node.image = image
            mesh.materials.append(new_material)
            new_slot = len(mesh.materials) - 1

            for face_id in face_ids:
                poly = mesh.polygons[face_id]
                poly.material_index = new_slot
                for loop_index in poly.loop_indices:
                    uv = uv_layer.data[loop_index].uv
                    u, v = float(uv[0]), float(uv[1])
                    uv_layer.data[loop_index].uv = (
                        (u * width - x0) / crop_w,
                        (v * height - y0) / crop_h,
                    )
            generated += 1

    require(generated > 0, "No textured UV islands were split")

    # Remove unused original atlas slots. Keep a snapshot of polygon indices
    # before mutating the Blender material collection because Blender may adjust
    # those indices while slots are popped.
    face_material_indices = [poly.material_index for poly in mesh.polygons]
    used_indices = sorted(set(face_material_indices))
    old_materials = list(mesh.materials)
    new_index = {old_index: new_index for new_index, old_index in enumerate(used_indices)}
    for index in range(len(mesh.materials) - 1, -1, -1):
        mesh.materials.pop(index=index)
    for old_index in used_indices:
        mesh.materials.append(old_materials[old_index])
    for poly in mesh.polygons:
        poly.material_index = new_index[face_material_indices[poly.index]]

    return {
        "original_material_count": original_material_count,
        "generated_material_count": generated,
        "final_material_slot_count": len(mesh.materials),
        "island_count": len(island_report),
        "islands": island_report,
    }


def ensure_base_color_texture(material):
    """Keep image maps; give the one untextured source slot a solid color map."""
    if material is None:
        return False
    material.use_nodes = True
    nodes, links = material.node_tree.nodes, material.node_tree.links
    principled = next((n for n in nodes if n.type == "BSDF_PRINCIPLED"), None)
    if principled is None:
        principled = nodes.new("ShaderNodeBsdfPrincipled")
        output = next((n for n in nodes if n.type == "OUTPUT_MATERIAL"), None)
        if output is None:
            output = nodes.new("ShaderNodeOutputMaterial")
        links.new(principled.outputs["BSDF"], output.inputs["Surface"])
    base = principled.inputs.get("Base Color")
    if base is None:
        raise RuntimeError(f"Material {material.name} has no Base Color")
    if any(link.from_node.type == "TEX_IMAGE" and link.from_node.image for link in base.links):
        return False
    rgba = tuple(min(1.0, max(0.0, float(v))) for v in base.default_value)
    image = bpy.data.images.new(f"CJ64_{material.name}_solid", 4, 4, alpha=True)
    image.pixels = list(rgba) * 16
    image.pack()
    tex = nodes.new("ShaderNodeTexImage")
    tex.label = "Generated solid fallback for originally untextured FBX material"
    tex.image = image
    links.new(tex.outputs["Color"], base)
    return True


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    if len(argv) != 3:
        raise SystemExit("usage: export_cj_static_actor.py <prepared.glb> <repo_root> <output_dir>")
    glb, repo_root, output = [Path(v).resolve() for v in argv]
    output.mkdir(parents=True, exist_ok=True)
    require(glb.is_file(), f"Prepared GLB missing: {glb}")
    require((repo_root / "main.lua").is_file(), "Repository is missing main.lua")

    fast64_root = Path(os.environ.get("FAST64_ADDON_PATH", "")).resolve()
    require((fast64_root / "__init__.py").is_file(), "FAST64_ADDON_PATH is not configured")
    sys.path.insert(0, str(fast64_root.parent))
    import fast64
    fast64.register()
    try:
        bpy.ops.preferences.addon_enable(module="io_scene_gltf2")
    except Exception:
        pass
    require(hasattr(bpy.ops.import_scene, "gltf"), "Blender glTF importer is unavailable")

    # IMPORTANT: --factory-startup creates a default Cube, Camera and Light.
    # The previous exporter accidentally joined that default Cube to CJ.
    # It exported as a 2x2x2 gray box and obscured the lower half of the model.
    startup_objects = [obj.name for obj in bpy.data.objects]
    for startup_obj in list(bpy.data.objects):
        bpy.data.objects.remove(startup_obj, do_unlink=True)

    bpy.ops.import_scene.gltf(filepath=str(glb))
    imported_objects = list(bpy.context.scene.objects)
    meshes = [o for o in imported_objects if o.type == "MESH"]
    require(meshes, "Prepared GLB contains no mesh")
    for obj in meshes:
        world = obj.matrix_world.copy()
        for vertex in obj.data.vertices:
            vertex.co = world @ vertex.co
        obj.matrix_world = Matrix.Identity(4)
        obj.parent = None
        for modifier in list(obj.modifiers):
            obj.modifiers.remove(modifier)

    imported_mesh_diagnostics = [mesh_summary(obj) for obj in meshes]
    source_bounds = combined_mesh_bounds(meshes)
    require(source_bounds["max_dimension"] <= 1.80,
            "Unexpected oversized geometry in prepared GLB: "
            + json.dumps(source_bounds, sort_keys=True))
    bpy.ops.object.select_all(action="DESELECT")
    for obj in meshes:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = meshes[0]
    if len(meshes) > 1:
        bpy.ops.object.join()
    obj = bpy.context.view_layer.objects.active
    obj.name = "CJ_Static_Model_Test"

    # Deliberate visual gameplay scale: CJ is 1.75x the Mario reference height.
    # This is an art/gameplay choice, not a claim about a canonical GTA character height.
    mario_reference_height_units = 160.0
    cj_visual_scale_ratio = 1.75
    blender_to_sm64_scale = 100.0
    cj_target_height_units = mario_reference_height_units * cj_visual_scale_ratio
    cj_target_height_blender_units = cj_target_height_units / blender_to_sm64_scale
    source_height_blender_units = source_bounds["dimensions"][2]
    require(source_height_blender_units > 0.0, "CJ source model has zero height")
    visual_scale_factor = cj_target_height_blender_units / source_height_blender_units
    for vertex in obj.data.vertices:
        vertex.co *= visual_scale_factor
    obj.data.update()

    joined_geometry = mesh_summary(obj)
    pre_fast64_preview = render_glb_import_preview(
        obj, output / "CJ64-3.6-GLB-Preview.png"
    )
    require(abs(joined_geometry["dimensions"][2] - cj_target_height_blender_units) < 0.005,
            "CJ visual height does not match the 2.80-unit / 280-unit target: "
            + json.dumps(joined_geometry, sort_keys=True))

    fallbacks = [m.name for m in obj.data.materials if ensure_base_color_texture(m)]

    # Crop UV islands while GLTF material nodes still reference their original
    # decoded image buffers. Fast64 conversion can detach the source image data.
    texture_island_report = split_materials_into_tmem_uv_islands(obj, max_texels=2048)

    import fast64.fast64_internal.f3d_material_converter as converter
    converter.convertAllBSDFtoF3D([obj], True)
    unresolved = [m.name for m in obj.data.materials if m and not bool(getattr(m, "is_f3d", False))]
    require(not unresolved, f"Fast64 failed to convert: {unresolved}")

    # Cropped maps now have local UVs and dedicated materials.
    from fast64.fast64_internal.f3d.f3d_material import all_combiner_uses
    texture_settings = {}
    texture_budget = {}
    for material in obj.data.materials:
        if material is None or not bool(getattr(material, "is_f3d", False)):
            continue
        f3d = material.f3d_mat
        uses = all_combiner_uses(f3d)
        if f3d.tex1.tex_set and not uses.get("Texture 1", False):
            f3d.tex1.tex_set = False
        require(not (uses.get("Texture 0", False) and uses.get("Texture 1", False)),
                f"{material.name} samples both texture slots; the static test needs one map per material")
        f3d.use_large_textures = False
        f3d.large_edges = "Clamp"
        image_info = None
        if f3d.tex0.tex is not None and f3d.tex0.tex_set:
            w, h = int(f3d.tex0.tex.size[0]), int(f3d.tex0.tex.size[1])
            padded_texels = ((w + 3) // 4 * 4) * h
            image_info = {"name": f3d.tex0.tex.name, "export_size": [w, h],
                          "row_padded_tmem_texels": padded_texels,
                          "rgba16_bytes": padded_texels * 2}
            require(padded_texels <= 2048,
                    f"{material.name} image exceeds padded TMEM: {w}x{h} -> {padded_texels} texels")
            texture_budget[material.name] = image_info
        texture_settings[material.name] = {
            "tex0_size": list(f3d.tex0.tex.size) if f3d.tex0.tex else None,
            "tex0_enabled": bool(f3d.tex0.tex_set),
            "tex1_size": list(f3d.tex1.tex.size) if f3d.tex1.tex else None,
            "tex1_enabled": bool(f3d.tex1.tex_set),
            "combiner_uses_tex1": bool(uses.get("Texture 1", False)),
            "large_textures_enabled": bool(f3d.use_large_textures),
            "texture_budget": image_info,
        }
    tmem_preview = render_glb_import_preview(
        obj, output / "CJ64-3.6-TMEM-Preview.png"
    )
    back_preview = render_glb_import_preview(
        obj, output / "CJ64-3.6-Back-Preview.png", view="back"
    )
    print("CJ64 UV-island texture settings:", json.dumps(texture_settings, sort_keys=True))

    output.mkdir(parents=True, exist_ok=True)
    mod = output / "CJ64-Model-Test"
    actors = mod / "actors"
    actors.mkdir(parents=True, exist_ok=True)
    scene = bpy.context.scene
    scene.gameEditorMode = "SM64"
    scene.fast64.sm64.exportType = "C"
    scene.saveTextures = True
    scene.geoSeparateTextureDef = False
    scene.geoCustomExport = True
    scene.geoExportPath = str(actors)
    scene.geoTexDir = "actors/cj/"
    scene.geoName = "cj"
    scene.geoStructName = "cj_geo"
    scene.geoGroupName = "group0"
    scene.geoExportHeaderType = "Actor"
    scene.geoDeleteOldGeo = True
    scene.exportInlineF3D = False
    scene.blenderToSM64Scale = blender_to_sm64_scale
    obj.geo_cmd_static = "Optimal"
    obj.draw_layer_static = "1"
    obj.use_render_area = False
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.mode_set(mode="OBJECT")
    result = bpy.ops.object.sm64_export_geolayout_object()
    require("FINISHED" in result, f"Fast64 export did not finish: {result}")

    actor = actors / "cj"
    required = ["geo.inc.c", "model.inc.c", "geo_header.h"]
    missing = [name for name in required if not (actor / name).is_file()]
    require(not missing, f"Fast64 did not produce: {missing}")

    model_source = (actor / "model.inc.c").read_text(encoding="utf-8")
    tile_origins = [
        (int(s), int(t))
        for s, t in re.findall(
            r"gsDPLoadTile\s*\(\s*\d+\s*,\s*(-?\d+)\s*,\s*(-?\d+)",
            model_source,
        )
    ]
    invalid_tile_origins = [(s, t) for s, t in tile_origins if s != 0 or t != 0]
    require(not invalid_tile_origins,
            f"Unsupported non-zero gsDPLoadTile origins remain: {invalid_tile_origins[:12]}")
    shutil.copy2(repo_root / "main.lua", mod / "main.lua")
    shutil.copy2(repo_root / "character.lua", mod / "character.lua")
    (mod / "README-INSTALL.txt").write_text("""CJ64 — static model visibility test

Copy this CJ64-Model-Test folder into SM64CoopDX/mods/ and enable the CJ64
Lua mod. On first launch the game builds the actor binary from C GeoLayout
files in actors/cj/. The mod replaces only the visible model on the existing
marioObj. MarioState, movement, collision, camera and physics remain native.

LIMITATION: the mesh is baked in its FBX rest pose and is not weighted to
Mario's Armature. It will not follow Mario's limb animations yet. This test
checks appearance, orientation, materials, DynOS actor compilation and loading.

Source: Carl Johnson (CJ) by Tsaphnat (Tsaphnat Mbuyi), Sketchfab, CC BY 4.0.
https://sketchfab.com/3d-models/carl-johnson-cj-647f5417720344cb8c2079edd48704ac
""", encoding="utf-8")
    (actor / "README.md").write_text("Static CJ actor test. Runtime symbol: cj_geo. No skinning or custom animation yet.\n", encoding="utf-8")
    actor_files = [{"path": str(p.relative_to(mod)), "size": p.stat().st_size}
                   for p in sorted(actor.rglob("*")) if p.is_file()]
    blender_scene_path = output / "CJ64-Blender-Scene.blend"
    bpy.ops.wm.save_as_mainfile(filepath=str(blender_scene_path))

    scene_diagnostics = {
        "bridge": "GitHub Actions -> Blender Python API -> Fast64-Coop -> DynOS",
        "blender_version": bpy.app.version_string,
        "factory_startup_objects_removed": startup_objects,
        "default_cube_removed": "Cube" in startup_objects,
        "imported_object_names": [o.name for o in imported_objects],
        "imported_mesh_count": len(meshes),
        "imported_meshes": imported_mesh_diagnostics,
        "source_bounds": source_bounds,
        "joined_geometry": joined_geometry,
        "visual_scale_factor": visual_scale_factor,
        "scale_calculation": {
            "mario_reference_height_units": mario_reference_height_units,
            "cj_visual_scale_ratio": cj_visual_scale_ratio,
            "sm64_units_per_blender_unit": blender_to_sm64_scale,
            "cj_target_height_units": cj_target_height_units,
            "source_height_blender_units": source_height_blender_units,
            "target_height_blender_units": cj_target_height_blender_units,
            "cj_to_mario_height_ratio": cj_target_height_units / mario_reference_height_units,
            "scale_is_visual_override": True,
        },
        "pre_fast64_blender_preview": pre_fast64_preview,
        "saved_blend_scene": blender_scene_path.name,
        "unexpected_default_cube_in_export": any(
            abs(joined_geometry["minimum"][axis] + 100.0) < 0.01
            and abs(joined_geometry["maximum"][axis] - 100.0) < 0.01
            for axis in range(3)
        ),
    }
    (output / "cj_scene_diagnostics.json").write_text(
        json.dumps(scene_diagnostics, indent=2), encoding="utf-8")

    report = {
        "format": "cj64-static-model-test-v2",
        "status": "EXPORTED_WITH_BLENDER_DIAGNOSTICS_NOT_TESTED_IN_GAME",
        "model_name": "cj_geo",
        "animation_mode": "STATIC_REST_POSE",
        "character_height_reference": {
            "mario_reference_height_units": mario_reference_height_units,
            "cj_visual_scale_ratio": cj_visual_scale_ratio,
            "cj_target_height_units": cj_target_height_units,
            "cj_to_mario_ratio": cj_target_height_units / mario_reference_height_units,
            "scale_is_visual_override": True,
        },
        "keeps_native_mario_object": True,
        "keeps_native_mariostate_physics_collision_camera": True,
        "vertex_count": len(obj.data.vertices),
        "polygon_count": len(obj.data.polygons),
        "material_names": [m.name if m else None for m in obj.data.materials],
        "generated_solid_fallback_materials": fallbacks,
        "texture_settings": texture_settings,
        "texture_tmem_budget": texture_budget,
        "texture_uv_islands": texture_island_report,
        "tmem_safe_blender_preview": tmem_preview,
        "back_blender_preview": back_preview,
        "blender_scene": scene_diagnostics,
        "actor_files": actor_files,
        "warnings": ["Static rest-pose model; it does not follow Mario's limb animations.",
                     "The package still requires an in-game test on the user's SM64CoopDX installation."]
    }
    (output / "cj_model_test_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    archive = output / "CJ64-Model-Test.zip"
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED, compresslevel=8) as zf:
        for path in sorted(mod.rglob("*")):
            if path.is_file():
                zf.write(path, path.relative_to(mod.parent))
    print(json.dumps({"package": str(archive), "report": report}, indent=2))


if __name__ == "__main__":
    main()
