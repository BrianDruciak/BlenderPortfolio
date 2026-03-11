import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector


OUTPUT_DIR = Path(__file__).resolve().parent / "blender_output" / "game_assets"


def clear_scene():
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    for block in (bpy.data.meshes, bpy.data.curves, bpy.data.materials,
                  bpy.data.lights, bpy.data.cameras, bpy.data.images):
        for d in list(block):
            if d.users == 0:
                block.remove(d)


def mat(name, color, emission=None, em_strength=0.0, metallic=0.0, roughness=0.45, alpha=1.0):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nodes = m.node_tree.nodes
    links = m.node_tree.links
    nodes.clear()
    out = nodes.new("ShaderNodeOutputMaterial")
    out.location = (300, 0)
    bsdf = nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.location = (0, 0)
    for n in ["Base Color"]:
        s = bsdf.inputs.get(n)
        if s:
            s.default_value = (*color, 1.0)
    for n in ["Roughness"]:
        s = bsdf.inputs.get(n)
        if s:
            s.default_value = roughness
    for n in ["Metallic"]:
        s = bsdf.inputs.get(n)
        if s:
            s.default_value = metallic
    for n in ["Alpha"]:
        s = bsdf.inputs.get(n)
        if s:
            s.default_value = alpha
    if emission:
        for n in ["Emission Color", "Emission"]:
            s = bsdf.inputs.get(n)
            if s:
                s.default_value = (*emission, 1.0)
                break
        for n in ["Emission Strength"]:
            s = bsdf.inputs.get(n)
            if s:
                s.default_value = em_strength
    if alpha < 1.0:
        m.blend_method = "BLEND"
    links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    return m


def assign(obj, material):
    if obj.data.materials:
        obj.data.materials[0] = material
    else:
        obj.data.materials.append(material)


def smooth(obj):
    for p in obj.data.polygons:
        p.use_smooth = True


def bevel(obj, width=0.02, segs=2):
    mod = obj.modifiers.new("Bevel", "BEVEL")
    mod.width = width
    mod.segments = segs
    mod.limit_method = "ANGLE"
    mod.angle_limit = math.radians(30)


def look_at(obj, target):
    d = target - obj.location
    obj.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()


def setup_studio(cam_pos, cam_target, key_pos, key_energy=800, rim_pos=None, rim_energy=400, bg_color=(0.02, 0.025, 0.035)):
    world = bpy.data.worlds["World"]
    world.use_nodes = True
    nodes = world.node_tree.nodes
    links = world.node_tree.links
    nodes.clear()
    out = nodes.new("ShaderNodeOutputWorld")
    out.location = (250, 0)
    bg = nodes.new("ShaderNodeBackground")
    bg.location = (0, 0)
    bg.inputs[0].default_value = (*bg_color, 1.0)
    bg.inputs[1].default_value = 0.6
    links.new(bg.outputs["Background"], out.inputs["Surface"])

    bpy.ops.object.camera_add(location=cam_pos)
    cam = bpy.context.active_object
    cam.data.lens = 65
    cam.data.dof.use_dof = True
    cam.data.dof.aperture_fstop = 3.2
    look_at(cam, cam_target)
    bpy.context.scene.camera = cam

    bpy.ops.object.light_add(type="AREA", location=key_pos)
    key = bpy.context.active_object
    key.data.energy = key_energy
    key.data.color = (0.9, 0.92, 1.0)
    key.data.size = 3.0
    look_at(key, cam_target)

    if rim_pos:
        bpy.ops.object.light_add(type="AREA", location=rim_pos)
        rim = bpy.context.active_object
        rim.data.energy = rim_energy
        rim.data.color = (0.5, 0.7, 1.0)
        rim.data.size = 2.5
        look_at(rim, cam_target)


def setup_render(path, res_x=1920, res_y=1080, samples=64):
    s = bpy.context.scene
    s.render.resolution_x = res_x
    s.render.resolution_y = res_y
    s.render.resolution_percentage = 100
    s.render.image_settings.file_format = "PNG"
    s.render.filepath = str(path)
    s.render.film_transparent = True
    avail = {i.identifier for i in s.render.bl_rna.properties["engine"].enum_items}
    if "BLENDER_EEVEE_NEXT" in avail:
        s.render.engine = "BLENDER_EEVEE_NEXT"
    elif "BLENDER_EEVEE" in avail:
        s.render.engine = "BLENDER_EEVEE"
    try:
        s.view_settings.look = "Medium High Contrast"
    except (TypeError, ValueError):
        pass


def save_and_render(blend_path, render_path):
    bpy.ops.wm.save_as_mainfile(filepath=str(blend_path))
    bpy.ops.render.render(write_still=True)


# ─────────────────── ENEMY: THORN CRAWLER ───────────────────

def build_thorn_crawler():
    clear_scene()
    body_mat = mat("CrawlerBody", (0.25, 0.5, 0.18), emission=(0.1, 0.3, 0.05), em_strength=0.4, roughness=0.55)
    eye_mat = mat("CrawlerEye", (0.9, 1.0, 0.3), emission=(0.9, 1.0, 0.3), em_strength=3.0)
    thorn_mat = mat("CrawlerThorn", (0.18, 0.35, 0.12), roughness=0.7)

    bpy.ops.mesh.primitive_cube_add(location=(0, 0, 0.4))
    body = bpy.context.active_object
    body.scale = (0.55, 0.7, 0.45)
    bpy.ops.object.transform_apply(scale=True)
    assign(body, body_mat)
    bevel(body, 0.06, 3)
    smooth(body)

    for ex in (-0.22, 0.22):
        bpy.ops.mesh.primitive_cube_add(location=(ex, -0.36, 0.52))
        eye = bpy.context.active_object
        eye.scale = (0.09, 0.05, 0.07)
        bpy.ops.object.transform_apply(scale=True)
        assign(eye, eye_mat)

    thorn_positions = [(0.35, 0.1, 0.7), (-0.35, -0.1, 0.7), (0, 0.3, 0.75), (0.2, -0.2, 0.72), (-0.2, 0.25, 0.68)]
    for pos in thorn_positions:
        bpy.ops.mesh.primitive_cone_add(vertices=6, radius1=0.06, depth=0.25, location=pos)
        t = bpy.context.active_object
        t.rotation_euler = (math.radians(15 * (pos[0] * 5)), math.radians(10 * pos[1] * 3), 0)
        assign(t, thorn_mat)
        smooth(t)


def build_frost_wraith():
    clear_scene()
    body_mat = mat("WraithBody", (0.55, 0.75, 0.9), emission=(0.3, 0.7, 1.0), em_strength=1.2, roughness=0.2, alpha=0.85)
    eye_mat = mat("WraithEye", (0.3, 0.85, 1.0), emission=(0.3, 0.85, 1.0), em_strength=5.0)
    ice_mat = mat("WraithIce", (0.7, 0.88, 0.95), emission=(0.5, 0.8, 1.0), em_strength=0.6, roughness=0.1)

    bpy.ops.mesh.primitive_cube_add(location=(0, 0, 0.55))
    body = bpy.context.active_object
    body.scale = (0.42, 0.42, 0.72)
    bpy.ops.object.transform_apply(scale=True)
    assign(body, body_mat)
    bevel(body, 0.04, 3)
    smooth(body)

    for ex in (-0.16, 0.16):
        bpy.ops.mesh.primitive_cube_add(location=(ex, -0.22, 0.72))
        eye = bpy.context.active_object
        eye.scale = (0.07, 0.04, 0.05)
        bpy.ops.object.transform_apply(scale=True)
        assign(eye, eye_mat)

    for pos, rot in [((0.28, 0, 0.85), (0, 0, -0.3)), ((-0.28, 0, 0.85), (0, 0, 0.3)), ((0, 0.2, 1.0), (0.2, 0, 0))]:
        bpy.ops.mesh.primitive_cone_add(vertices=4, radius1=0.04, depth=0.3, location=pos, rotation=rot)
        assign(bpy.context.active_object, ice_mat)
        smooth(bpy.context.active_object)


def build_ember_golem():
    clear_scene()
    body_mat = mat("GolemBody", (0.45, 0.18, 0.08), emission=(1.0, 0.35, 0.05), em_strength=1.8, roughness=0.6, metallic=0.3)
    eye_mat = mat("GolemEye", (1.0, 0.5, 0.1), emission=(1.0, 0.5, 0.1), em_strength=6.0)
    crack_mat = mat("GolemCrack", (1.0, 0.3, 0.0), emission=(1.0, 0.4, 0.05), em_strength=4.0)

    bpy.ops.mesh.primitive_cube_add(location=(0, 0, 0.6))
    body = bpy.context.active_object
    body.scale = (0.72, 0.72, 0.8)
    bpy.ops.object.transform_apply(scale=True)
    assign(body, body_mat)
    bevel(body, 0.05, 2)
    smooth(body)

    bpy.ops.mesh.primitive_cube_add(location=(0, 0, 1.3))
    head = bpy.context.active_object
    head.scale = (0.42, 0.42, 0.38)
    bpy.ops.object.transform_apply(scale=True)
    assign(head, body_mat)
    bevel(head, 0.04, 2)
    smooth(head)

    for ex in (-0.18, 0.18):
        bpy.ops.mesh.primitive_cube_add(location=(ex, -0.25, 1.38))
        eye = bpy.context.active_object
        eye.scale = (0.08, 0.04, 0.06)
        bpy.ops.object.transform_apply(scale=True)
        assign(eye, eye_mat)

    for pos in [(0.4, 0.2, 0.5), (-0.3, -0.3, 0.7), (0.1, 0.35, 0.3)]:
        bpy.ops.mesh.primitive_cube_add(location=pos)
        c = bpy.context.active_object
        c.scale = (0.08, 0.4, 0.04)
        c.rotation_euler = (0, 0, math.radians(20 * pos[0] * 10))
        bpy.ops.object.transform_apply(scale=True, rotation=True)
        assign(c, crack_mat)

    for side in (-0.6, 0.6):
        bpy.ops.mesh.primitive_cube_add(location=(side, 0, 0.95))
        arm = bpy.context.active_object
        arm.scale = (0.2, 0.22, 0.5)
        bpy.ops.object.transform_apply(scale=True)
        assign(arm, body_mat)
        bevel(arm, 0.03, 2)
        smooth(arm)


def build_void_stalker():
    clear_scene()
    body_mat = mat("StalkerBody", (0.12, 0.05, 0.18), emission=(0.5, 0.1, 0.8), em_strength=2.5, roughness=0.15)
    eye_mat = mat("StalkerEye", (0.85, 0.4, 1.0), emission=(0.85, 0.4, 1.0), em_strength=8.0)
    wisp_mat = mat("StalkerWisp", (0.6, 0.2, 0.9), emission=(0.7, 0.2, 1.0), em_strength=4.0, alpha=0.5)

    bpy.ops.mesh.primitive_cube_add(location=(0, 0, 0.5))
    body = bpy.context.active_object
    body.scale = (0.38, 0.38, 0.62)
    bpy.ops.object.transform_apply(scale=True)
    assign(body, body_mat)
    bevel(body, 0.04, 3)
    smooth(body)

    for ex in (-0.14, 0.14):
        bpy.ops.mesh.primitive_cube_add(location=(ex, -0.2, 0.68))
        eye = bpy.context.active_object
        eye.scale = (0.06, 0.04, 0.04)
        bpy.ops.object.transform_apply(scale=True)
        assign(eye, eye_mat)

    for i in range(4):
        angle = math.radians(i * 90 + 45)
        px = math.cos(angle) * 0.35
        pz = math.sin(angle) * 0.35
        bpy.ops.mesh.primitive_uv_sphere_add(radius=0.1, location=(px, pz, 0.7 + i * 0.08))
        w = bpy.context.active_object
        assign(w, wisp_mat)
        smooth(w)


def build_crystal_pickup():
    clear_scene()
    colors = [
        ("WildCrystal", (0.65, 0.2, 0.85)),
        ("Frostite", (0.3, 0.85, 0.95)),
        ("Embersite", (0.95, 0.45, 0.1)),
        ("VoidShard", (0.6, 0.3, 0.9)),
        ("GlacialGem", (0.7, 0.85, 0.95)),
    ]

    spacing = 1.8
    start_x = -(len(colors) - 1) * spacing / 2

    for i, (name, color) in enumerate(colors):
        x = start_x + i * spacing
        crystal_mat = mat(name, color, emission=color, em_strength=4.0, roughness=0.1, alpha=0.88)

        bpy.ops.mesh.primitive_cone_add(vertices=6, radius1=0.28, radius2=0.0, depth=0.7, location=(x, 0, 0.55))
        top = bpy.context.active_object
        assign(top, crystal_mat)
        smooth(top)

        bpy.ops.mesh.primitive_cone_add(vertices=6, radius1=0.28, radius2=0.0, depth=0.35, location=(x, 0, 0.12))
        bottom = bpy.context.active_object
        bottom.rotation_euler = (math.pi, 0, 0)
        assign(bottom, crystal_mat)
        smooth(bottom)

        bpy.ops.object.light_add(type="POINT", location=(x, 0, 0.5))
        light = bpy.context.active_object
        light.data.color = color
        light.data.energy = 80
        light.data.shadow_soft_size = 0.3


def build_tool_set():
    clear_scene()
    handle_mat = mat("Handle", (0.45, 0.28, 0.12), roughness=0.7)
    tiers = [
        ("Wood", (0.55, 0.35, 0.15), 0.0, 0.7),
        ("Crystal", (0.6, 0.2, 0.8), 0.0, 0.2),
        ("Frost", (0.3, 0.75, 0.95), 0.0, 0.15),
        ("Ember", (0.95, 0.4, 0.1), 0.0, 0.25),
        ("Void", (0.2, 0.05, 0.3), 0.0, 0.1),
    ]

    for i, (name, color, metallic_v, rough_v) in enumerate(tiers):
        x = i * 1.6 - 3.2
        head_mat = mat(f"{name}Head", color, metallic=metallic_v, roughness=rough_v)
        em = color if name in ("Crystal", "Frost", "Ember", "Void") else None
        em_s = 2.0 if em else 0.0
        if em:
            head_mat = mat(f"{name}Head", color, emission=em, em_strength=em_s, metallic=metallic_v, roughness=rough_v)

        # Pickaxe handle
        bpy.ops.mesh.primitive_cube_add(location=(x, 0, 0.5))
        h = bpy.context.active_object
        h.scale = (0.06, 0.06, 0.5)
        bpy.ops.object.transform_apply(scale=True)
        assign(h, handle_mat)
        bevel(h, 0.01)

        # Pickaxe head
        bpy.ops.mesh.primitive_cube_add(location=(x, 0, 1.0))
        hd = bpy.context.active_object
        hd.scale = (0.35, 0.06, 0.1)
        bpy.ops.object.transform_apply(scale=True)
        assign(hd, head_mat)
        bevel(hd, 0.015)
        smooth(hd)


def render_asset(build_fn, name, cam_dist=3.0, cam_height=1.5, res=1080):
    build_fn()
    out = OUTPUT_DIR / name
    setup_studio(
        cam_pos=(cam_dist, -cam_dist * 0.8, cam_height),
        cam_target=Vector((0, 0, 0.5)),
        key_pos=(cam_dist * 0.8, -cam_dist, cam_height + 1.5),
        key_energy=600,
        rim_pos=(-cam_dist, cam_dist * 0.6, cam_height),
        rim_energy=300,
    )
    render_path = out.with_suffix(".png")
    blend_path = out.with_suffix(".blend")
    setup_render(render_path, res_x=res if res > 1080 else 1920, res_y=res, samples=64)
    save_and_render(blend_path, render_path)
    print(f"  Saved: {blend_path}")
    print(f"  Saved: {render_path}")


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    print("Generating game asset renders...")
    render_asset(build_thorn_crawler, "enemy_thorn_crawler", cam_dist=2.5, cam_height=1.0)
    render_asset(build_frost_wraith, "enemy_frost_wraith", cam_dist=2.8, cam_height=1.2)
    render_asset(build_ember_golem, "enemy_ember_golem", cam_dist=3.2, cam_height=1.5)
    render_asset(build_void_stalker, "enemy_void_stalker", cam_dist=2.5, cam_height=1.1)
    render_asset(build_crystal_pickup, "crystal_pickups", cam_dist=5.5, cam_height=1.5)
    render_asset(build_tool_set, "tool_tiers", cam_dist=6.0, cam_height=2.0)
    print("Done! All assets in:", OUTPUT_DIR)


if __name__ == "__main__":
    main()
