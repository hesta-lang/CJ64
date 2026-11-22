#!/usr/bin/env python3
"""Experimental binary-weight CJ -> SM64CoopDX Mario rig transfer."""
import json, os, shutil, sys, zipfile
from pathlib import Path
import bpy
from mathutils import Vector
from mathutils.kdtree import KDTree

sys.path.insert(0, str(Path(__file__).resolve().parent))
import export_cj_static_actor as shared

SRC = {
 "root ground":"Butt","root hips":"Butt","pelvis":"Butt",
 "spine lower":"Torso","spine middle":"Torso","spine upper":"Torso",
 "belly":"Torso","l breast":"Torso","r breast":"Torso",
 "head neck lower":"Head DL","head neck upper":"Head DL",
 "head eyeball left":"Head DL","head eyeball right":"Head DL",
 "head eyebrow left 1":"Head DL","head eyebrow left 2":"Head DL","head eyebrow left 3":"Head DL",
 "head eyebrow right 1":"Head DL","head eyebrow right 2":"Head DL","head eyebrow right 3":"Head DL",
 "head eyebrow middle":"Head DL","head eyelid left lower":"Head DL","head eyelid left upper":"Head DL",
 "head eyelid right lower":"Head DL","head eyelid right upper":"Head DL",
 "head lip upper left":"Head DL","head lip upper right":"Head DL","head lip upper middle":"Head DL",
 "head jaw":"Head DL","head lip lower left":"Head DL","head lip lower right":"Head DL",
 "head lip lower middle":"Head DL","head mouth corner left":"Head DL","head mouth corner right":"Head DL",
 "arm left shoulder 1":"Left Arm Color","arm left shoulder 2":"Left Arm Color",
 "arm left elbow":"Left Forearm","arm left wrist":"Left Hand DL",
 "arm left finger 1a":"Left Hand DL","arm left finger 1b":"Left Hand DL","arm left finger 1c":"Left Hand DL",
 "arm left finger 2a":"Left Hand DL","arm left finger 2b":"Left Hand DL","arm left finger 2c":"Left Hand DL",
 "arm right shoulder 1":"Right Arm Color","arm right shoulder 2":"Right Arm Color",
 "arm right elbow":"Right Forearm","arm right wrist":"Right Hand DL",
 "arm right finger 1a":"Right Hand DL","arm right finger 1b":"Right Hand DL","arm right finger 1c":"Right Hand DL",
 "arm right finger 2a":"Right Hand DL","arm right finger 2b":"Right Hand DL","arm right finger 2c":"Right Hand DL",
 "leg left thigh":"Left Thigh Color","leg left knee":"Left Leg","leg left ankle":"Left Shoe","leg left toes":"Left Shoe",
 "leg right thigh":"Right Thigh Color","leg right knee":"Right Leg","leg right ankle":"Right Shoe DL","leg right toes":"Right Shoe DL"
}
TARGETS=set(SRC.values())

def need(ok,msg):
    if not ok: raise RuntimeError(msg)

def join_meshes(items,name):
    need(items,"No mesh objects found")
    bpy.ops.object.select_all(action="DESELECT")
    for x in items: x.select_set(True)
    bpy.context.view_layer.objects.active=items[0]
    if len(items)>1: bpy.ops.object.join()
    obj=bpy.context.view_layer.objects.active
    obj.name=name
    return obj

def bake_world(obj):
    m=obj.matrix_world.copy()
    for v in obj.data.vertices: v.co=m@v.co
    obj.matrix_world.identity()
    obj.parent=None
    for mod in list(obj.modifiers): obj.modifiers.remove(mod)
    obj.data.update()

def get_bounds(obj):
    pts=[v.co.copy() for v in obj.data.vertices]
    lo=Vector(tuple(min(p[i] for p in pts) for i in range(3)))
    hi=Vector(tuple(max(p[i] for p in pts) for i in range(3)))
    return lo,hi,hi-lo

def main():
    args=sys.argv[sys.argv.index("--")+1:]
    need(len(args)==5,"usage: rig_cj_to_mario.py template.blend prepared.glb source.fbx repo_root output_dir")
    template,glb,fbx,repo,out=map(lambda x:Path(x).resolve(),args)
    for p in (template,glb,fbx): need(p.is_file(),f"Missing input: {p}")
    out.mkdir(parents=True,exist_ok=True)

    fast64=Path(os.environ["FAST64_ADDON_PATH"]).resolve()
    need((fast64/"__init__.py").is_file(),"Fast64-Coop missing")
    sys.path.insert(0,str(fast64.parent))
    import fast64 as fast64_addon
    fast64_addon.register()
    bpy.ops.wm.open_mainfile(filepath=str(template))
    mario=bpy.data.objects.get("Mario")
    need(mario and mario.type=="ARMATURE","Mario armature missing in official template")
    for obj in list(bpy.context.scene.objects):
        if obj!=mario: bpy.data.objects.remove(obj,do_unlink=True)

    bpy.ops.import_scene.fbx(filepath=str(fbx),use_custom_props=True,automatic_bone_orientation=False)
    src_armatures=[o for o in bpy.context.scene.objects if o.type=="ARMATURE" and o!=mario]
    src_meshes=[o for o in bpy.context.scene.objects if o.type=="MESH"]
    need(len(src_armatures)==1 and src_meshes,"Could not identify the single CJ source rig and mesh")
    src_arm=src_armatures[0]
    src_mesh=join_meshes(src_meshes,"CJ64_Source_Weights")

    bpy.ops.import_scene.gltf(filepath=str(glb))
    glb_meshes=[o for o in bpy.context.scene.objects if o.type=="MESH" and o!=src_mesh]
    target=join_meshes(glb_meshes,"CJ64_Carl_Johnson")
    bake_world(target)

    # Align source FBX vertices to the prepared GLB by uniform AABB fit.
    # Abort rather than transfer if the two imports have incompatible axes.
    slo,shi,sd=get_bounds(src_mesh)
    tlo,thi,td=get_bounds(target)
    need(sd.z>0 and td.z>0,"Source or prepared mesh has zero height")
    ratios=[td[i]/sd[i] for i in range(3) if sd[i]>1e-5]
    scale=sum(ratios)/len(ratios)
    need(max(abs(r/scale-1) for r in ratios)<0.04,f"FBX/GLB axis mismatch: {ratios}")
    for v in src_mesh.data.vertices: v.co=tlo+(v.co-slo)*scale
    src_mesh.data.update()
    need(abs(td.z-2.8)<0.005,f"CJ height is not 280 units: {td.z*100:.2f}")

    for name in TARGETS:
        need(mario.data.bones.get(name) is not None,f"Target Mario deform bone missing: {name}")
        if target.vertex_groups.get(name) is None: target.vertex_groups.new(name=name)
    source_group_map={}
    for g in src_mesh.vertex_groups:
        target_name=SRC.get(g.name.strip().casefold())
        if target_name: source_group_map[g.index]=target_name

    tree=KDTree(len(src_mesh.data.vertices))
    for i,v in enumerate(src_mesh.data.vertices): tree.insert(v.co,i)
    tree.balance()
    target_groups={n:target.vertex_groups[n] for n in TARGETS}
    counts={n:0 for n in TARGETS}
    max_distance=0.0
    for v in target.data.vertices:
        _,idx,dist=tree.find(v.co)
        max_distance=max(max_distance,float(dist))
        weights={}
        for a in src_mesh.data.vertices[idx].groups:
            n=source_group_map.get(a.group)
            if n: weights[n]=weights.get(n,0.0)+float(a.weight)
        need(weights,f"Target vertex {v.index} has no mapped source weight")
        chosen=max(weights,key=weights.get)
        target_groups[chosen].add([v.index],1.0,"REPLACE")
        counts[chosen]+=1
    need(max_distance<=0.025*td.z,f"Vertex correspondence too distant: {max_distance:.5f}")

    # Scale the actual template armature uniformly to the 280-unit visual height.
    bones=list(mario.data.bones)
    z0=min(min(b.head_local.z,b.tail_local.z) for b in bones)
    z1=max(max(b.head_local.z,b.tail_local.z) for b in bones)
    rig_h=z1-z0
    need(rig_h>0.01,"Mario armature has invalid height")
    rig_scale=td.z/rig_h
    root=mario.data.bones["Body"].head_local.copy()
    center=Vector(((tlo.x+thi.x)*.5,(tlo.y+thi.y)*.5,tlo.z))
    bpy.context.view_layer.objects.active=mario
    bpy.ops.object.mode_set(mode="EDIT")
    for b in mario.data.edit_bones:
        b.head=center+(b.head-root)*rig_scale
        b.tail=center+(b.tail-root)*rig_scale
    bpy.ops.object.mode_set(mode="OBJECT")
    bpy.context.view_layer.update()

    target.parent=mario
    target.matrix_parent_inverse=mario.matrix_world.inverted()
    mod=target.modifiers.new("CJ64_Mario_Armature","ARMATURE")
    mod.object=mario
    mod.use_vertex_groups=True
    mod.use_bone_envelopes=False
    for v in target.data.vertices:
        active=[a for a in v.groups if a.weight>0.0001]
        need(len(active)==1 and abs(active[0].weight-1.0)<1e-5,f"Vertex {v.index} is not single-bone skinned")

    # Preserve the template's bone metadata and export using its armature operator.
    shared.split_materials_into_tmem_uv_islands(target,max_texels=2048)
    import fast64.fast64_internal.f3d_material_converter as converter
    converter.convertAllBSDFtoF3D([target],True)
    unresolved=[m.name for m in target.data.materials if m and not bool(getattr(m,"is_f3d",False))]
    need(not unresolved,f"Fast64 material conversion failed: {unresolved}")

    moddir=out/"CJ64-Rigged-Test"
    actors=moddir/"actors"
    actors.mkdir(parents=True,exist_ok=True)
    scene=bpy.context.scene
    scene.gameEditorMode="SM64"
    scene.fast64.sm64.exportType="C"
    scene.saveTextures=True
    scene.geoSeparateTextureDef=False
    scene.geoCustomExport=True
    scene.geoExportPath=str(actors)
    scene.geoTexDir="actors/cj/"
    scene.geoName="cj"
    scene.geoStructName="cj_geo"
    scene.geoGroupName="group0"
    scene.geoExportHeaderType="Actor"
    scene.geoDeleteOldGeo=True
    scene.exportInlineF3D=False
    scene.blenderToSM64Scale=100.0
    bpy.ops.object.select_all(action="DESELECT")
    mario.select_set(True)
    bpy.context.view_layer.objects.active=mario
    bpy.ops.object.mode_set(mode="OBJECT")
    result=bpy.ops.object.sm64_export_geolayout_armature()
    need("FINISHED" in result,f"Fast64 armature export failed: {result}")
    actor=actors/"cj"
    need((actor/"geo.inc.c").is_file() and (actor/"model.inc.c").is_file(),"Fast64 actor files missing")
    shutil.copy2(repo/"main.lua",moddir/"main.lua")
    shutil.copy2(repo/"character.lua",moddir/"character.lua")
    (moddir/"README-INSTALL.txt").write_text(
      "CJ64 experimental rigged actor. Binary single-bone weights were transferred from the source CJ FBX to the official Mario/Fast64 armature. "
      "Height: 280 SM64 units. This is not yet visually or in-game validated. Native MarioState and physics remain unchanged.\\n",encoding="utf-8")
    blend=out/"CJ64-Rigged-Scene.blend"
    bpy.ops.wm.save_as_mainfile(filepath=str(blend))
    report={
      "format":"cj64-rigged-actor-test-v1",
      "status":"EXPORTED_EXPERIMENTAL_NOT_VISUALLY_OR_IN_GAME_VALIDATED",
      "model_name":"cj_geo","height_blender_units":float(td.z),"height_sm64_units":float(td.z*100),
      "rig_scale":float(rig_scale),"max_nearest_source_vertex_distance":max_distance,
      "weight_mode":"one influence per vertex, weight 1.0",
      "vertices_by_target_bone":counts,"total_vertices":len(target.data.vertices),
      "target_deform_groups":sorted(TARGETS),
      "native_mario_state_preserved":True,
      "warnings":["Weight transfer uses nearest source vertex dominant bone.","Mario rig is uniformly scaled; joint proportions still need visual review.",
                  "Original GTA animation tables are not bundled in this public CI build.","Android/in-game test remains pending."]
    }
    (out/"cj64_rigged_actor_report.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
    with zipfile.ZipFile(out/"CJ64-Rigged-Test.zip","w",zipfile.ZIP_DEFLATED,compresslevel=8) as z:
      for p in sorted(moddir.rglob("*")):
        if p.is_file(): z.write(p,p.relative_to(out))
    print(json.dumps(report,indent=2))

if __name__=="__main__": main()
