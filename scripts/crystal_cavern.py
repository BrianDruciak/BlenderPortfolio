import argparse
import math
import random
import sys
from pathlib import Path

import bpy
from mathutils import Vector


def parse_args():
    parser = argparse.ArgumentParser(
        description="Generate a stylized crystal cavern portfolio scene."
    )
    parser.add_argument(
        "--output-dir",
        default=str(Path(__file__).resolve().parent / "blender_output"),
        help="Directory for the rendered image and .blend file.",
    )
    parser.add_argument(
        "--engine", default="BLENDER_EEVEE_NEXT",
        help="Render engine: BLENDER_EEVEE_NEXT, BLENDER_EEVEE, or CYCLES.",
    )
    parser.add_argument("--samples", type=int, default=128, help="Render samples.")
    if "--" not in sys.argv:
        return parser.parse_args([])
    return parser.parse_args(sys.argv[sys.argv.index("--") + 1 :])


# ── Utilities ──────────────────────────────────────────────────────────────

def deselect_all():
    for obj in bpy.context.selected_objects:
        obj.select_set(False)

def activate(obj):
    deselect_all(); obj.select_set(True)
    bpy.context.view_layer.objects.active = obj

def apply_scale(obj):
    activate(obj)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)

def shade_smooth(obj):
    if obj.type != "MESH":
        return
    for poly in obj.data.polygons:
        poly.use_smooth = True

def shade_flat(obj):
    if obj.type != "MESH":
        return
    for poly in obj.data.polygons:
        poly.use_smooth = False

def add_bevel(obj, width=0.03, segments=3):
    if obj.type != "MESH":
        return
    mod = obj.modifiers.new(name="Bevel", type="BEVEL")
    mod.width = width; mod.segments = segments
    mod.limit_method = "ANGLE"; mod.angle_limit = math.radians(30)

def assign_material(obj, material):
    if obj.type not in {"MESH", "CURVE"}:
        return
    if obj.data.materials:
        obj.data.materials[0] = material
    else:
        obj.data.materials.append(material)

def clear_scene():
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    for block in (
        bpy.data.meshes, bpy.data.curves, bpy.data.materials,
        bpy.data.lights, bpy.data.cameras, bpy.data.images,
    ):
        for db in list(block):
            if db.users == 0:
                block.remove(db)

def set_socket(node, names, value):
    for name in names:
        s = node.inputs.get(name)
        if s is not None:
            s.default_value = value; return

def make_principled_material(
    name, base_color, roughness=0.45, metallic=0.0,
    emission_color=None, emission_strength=0.0, alpha=1.0,
):
    mat = bpy.data.materials.new(name=name)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes; links = mat.node_tree.links
    nodes.clear()
    output = nodes.new("ShaderNodeOutputMaterial"); output.location = (300, 0)
    bsdf = nodes.new("ShaderNodeBsdfPrincipled"); bsdf.location = (0, 0)
    set_socket(bsdf, ["Base Color"], (*base_color, 1.0))
    set_socket(bsdf, ["Roughness"], roughness)
    set_socket(bsdf, ["Metallic"], metallic)
    set_socket(bsdf, ["Alpha"], alpha)
    if emission_color is not None:
        set_socket(bsdf, ["Emission Color", "Emission"], (*emission_color, 1.0))
        set_socket(bsdf, ["Emission Strength"], emission_strength)
    if alpha < 1.0:
        if hasattr(mat, "blend_method"):
            mat.blend_method = "BLEND"
        if hasattr(mat, "shadow_method"):
            mat.shadow_method = "HASHED"
    links.new(bsdf.outputs["BSDF"], output.inputs["Surface"])
    return mat

def look_at(obj, target):
    direction = target - obj.location
    obj.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()

def create_cube(name, location, scale, rotation=(0, 0, 0)):
    bpy.ops.mesh.primitive_cube_add(location=location, rotation=rotation)
    obj = bpy.context.active_object; obj.name = name; obj.scale = scale
    apply_scale(obj); return obj

def create_cylinder(name, location, radius, depth, vertices=32, rotation=(0, 0, 0)):
    bpy.ops.mesh.primitive_cylinder_add(
        vertices=vertices, radius=radius, depth=depth,
        location=location, rotation=rotation)
    obj = bpy.context.active_object; obj.name = name; return obj

def create_cone(name, location, radius1, radius2, depth, vertices=32, rotation=(0, 0, 0)):
    bpy.ops.mesh.primitive_cone_add(
        vertices=vertices, radius1=radius1, radius2=radius2,
        depth=depth, location=location, rotation=rotation)
    obj = bpy.context.active_object; obj.name = name; return obj

def create_sphere(name, location, radius, segments=32, ring_count=16):
    bpy.ops.mesh.primitive_uv_sphere_add(
        segments=segments, ring_count=ring_count,
        radius=radius, location=location)
    obj = bpy.context.active_object; obj.name = name; return obj


# ── World & render ─────────────────────────────────────────────────────────

def setup_world():
    world = bpy.data.worlds["World"]
    world.use_nodes = True
    nodes = world.node_tree.nodes; links = world.node_tree.links
    nodes.clear()
    output = nodes.new("ShaderNodeOutputWorld"); output.location = (250, 0)
    bg = nodes.new("ShaderNodeBackground"); bg.location = (0, 0)
    bg.inputs[0].default_value = (0.008, 0.006, 0.018, 1.0)
    bg.inputs[1].default_value = 0.3
    links.new(bg.outputs["Background"], output.inputs["Surface"])

def setup_render(engine_name, samples, render_path):
    scene = bpy.context.scene
    scene.render.resolution_x = 1920
    scene.render.resolution_y = 1080
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.filepath = str(render_path)
    available = {i.identifier for i in scene.render.bl_rna.properties["engine"].enum_items}
    if engine_name in available:
        scene.render.engine = engine_name
    elif "BLENDER_EEVEE_NEXT" in available:
        scene.render.engine = "BLENDER_EEVEE_NEXT"
    elif "BLENDER_EEVEE" in available:
        scene.render.engine = "BLENDER_EEVEE"
    else:
        scene.render.engine = "CYCLES"
    if scene.render.engine == "CYCLES":
        scene.cycles.samples = samples
        scene.cycles.use_adaptive_sampling = True
    else:
        if hasattr(scene, "eevee") and hasattr(scene.eevee, "taa_render_samples"):
            scene.eevee.taa_render_samples = samples
        if hasattr(scene, "eevee") and hasattr(scene.eevee, "use_bloom"):
            scene.eevee.use_bloom = True
    scene.render.film_transparent = False
    try:
        scene.view_settings.look = "Medium High Contrast"
    except (TypeError, ValueError):
        pass


# ── Crystal builder ────────────────────────────────────────────────────────

def build_crystal(name, location, height, radius, vertices, material,
                  tilt_x=0, tilt_y=0, tilt_z=0):
    crystal = create_cone(
        name, location, radius1=radius, radius2=0.0, depth=height,
        vertices=vertices,
        rotation=(tilt_x, tilt_y, tilt_z),
    )
    assign_material(crystal, material)
    shade_flat(crystal)
    return crystal


def build_rock(name, location, size, material):
    rock = create_sphere(name, location, radius=size, segments=8, ring_count=6)
    sx = 0.7 + random.random() * 0.6
    sy = 0.7 + random.random() * 0.6
    sz = 0.5 + random.random() * 0.5
    rock.scale = (sx, sy, sz)
    apply_scale(rock)
    assign_material(rock, material)
    shade_flat(rock)
    return rock


# ── Main scene ─────────────────────────────────────────────────────────────

def build_scene():
    clear_scene()
    setup_world()
    random.seed(42)

    # --- Materials ---
    rock_mat = make_principled_material("CaveRock", (0.065, 0.055, 0.07), roughness=0.92, metallic=0.0)
    rock_dark = make_principled_material("CaveRockDark", (0.03, 0.025, 0.04), roughness=0.95, metallic=0.0)
    ground_mat = make_principled_material("CaveFloor", (0.04, 0.035, 0.045), roughness=0.88, metallic=0.0)

    crystal_purple = make_principled_material(
        "CrystalPurple", (0.18, 0.02, 0.35), roughness=0.08, metallic=0.0,
        emission_color=(0.6, 0.1, 1.0), emission_strength=6.0, alpha=0.85,
    )
    crystal_cyan = make_principled_material(
        "CrystalCyan", (0.02, 0.2, 0.3), roughness=0.06, metallic=0.0,
        emission_color=(0.1, 0.8, 1.0), emission_strength=8.0, alpha=0.82,
    )
    crystal_pink = make_principled_material(
        "CrystalPink", (0.3, 0.03, 0.15), roughness=0.1, metallic=0.0,
        emission_color=(1.0, 0.2, 0.6), emission_strength=5.0, alpha=0.88,
    )
    crystal_green = make_principled_material(
        "CrystalGreen", (0.02, 0.25, 0.1), roughness=0.07, metallic=0.0,
        emission_color=(0.15, 1.0, 0.4), emission_strength=7.0, alpha=0.84,
    )
    pool_mat = make_principled_material(
        "Pool", (0.01, 0.06, 0.1), roughness=0.02, metallic=0.0,
        emission_color=(0.05, 0.4, 0.7), emission_strength=2.5, alpha=0.7,
    )
    moss_mat = make_principled_material("Moss", (0.04, 0.1, 0.03), roughness=0.85, metallic=0.0)

    # --- Ground ---
    bpy.ops.mesh.primitive_plane_add(size=18, location=(0, 0, -0.05))
    gnd = bpy.context.active_object; gnd.name = "CaveFloor"
    assign_material(gnd, ground_mat)

    # --- Central crystal cluster ---
    crystal_mats = [crystal_purple, crystal_cyan, crystal_pink, crystal_green]
    cluster_specs = [
        ((0, 0, 0.6),     1.6, 0.22, 5, crystal_purple, 0, 0, 0),
        ((0.35, 0.15, 0.45), 1.1, 0.16, 5, crystal_cyan, 0.15, 0.1, 0.2),
        ((-0.25, 0.3, 0.4),  0.9, 0.14, 6, crystal_pink, -0.12, 0.08, -0.15),
        ((0.1, -0.35, 0.35), 0.75, 0.12, 5, crystal_green, 0.1, -0.2, 0.1),
        ((-0.4, -0.15, 0.3), 0.65, 0.1, 5, crystal_cyan, -0.2, -0.1, 0.25),
        ((0.5, -0.1, 0.25),  0.55, 0.09, 6, crystal_purple, 0.25, 0.15, -0.1),
        ((0.15, 0.45, 0.2),  0.48, 0.08, 5, crystal_pink, -0.08, 0.22, 0.18),
    ]
    for i, (loc, h, r, v, mat, tx, ty, tz) in enumerate(cluster_specs):
        build_crystal(f"CentralCrystal_{i}", loc, h, r, v, mat, tx, ty, tz)

    # Central crystal base rock
    build_rock("CentralRock", (0, 0, 0.05), 0.55, rock_mat)

    # --- Scattered smaller crystal groups ---
    scatter_groups = [
        ((-2.0, 1.5, 0.0), crystal_cyan, 0.8),
        ((2.2, -1.0, 0.0), crystal_purple, 0.7),
        ((-1.5, -2.0, 0.0), crystal_green, 0.65),
        ((1.8, 2.0, 0.0), crystal_pink, 0.75),
        ((-2.8, -0.5, 0.0), crystal_cyan, 0.5),
        ((0.5, 3.0, 0.0), crystal_purple, 0.6),
    ]
    for gi, (center, mat, scale) in enumerate(scatter_groups):
        cx, cy, cz = center
        n_crystals = random.randint(2, 4)
        for ci in range(n_crystals):
            ox = (random.random() - 0.5) * 0.6
            oy = (random.random() - 0.5) * 0.6
            h = (0.3 + random.random() * 0.5) * scale
            r = (0.06 + random.random() * 0.08) * scale
            tx = (random.random() - 0.5) * 0.4
            ty = (random.random() - 0.5) * 0.4
            alt_mat = crystal_mats[random.randint(0, 3)] if random.random() > 0.7 else mat
            build_crystal(
                f"ScatterCrystal_{gi}_{ci}",
                (cx + ox, cy + oy, cz + h * 0.35),
                h, r, random.choice([5, 6]), alt_mat, tx, ty, 0,
            )
        build_rock(f"ScatterRock_{gi}", (cx, cy, cz), 0.25 * scale, rock_mat)

    # --- Cave rock formations ---
    rock_positions = [
        (-3.5, 0, 0.3), (3.5, 0.5, 0.25), (0, -3.5, 0.2), (0, 3.5, 0.3),
        (-2.5, 2.5, 0.15), (2.5, -2.5, 0.2), (-3, -2.8, 0.25), (3, 2.8, 0.2),
    ]
    for i, pos in enumerate(rock_positions):
        size = 0.4 + random.random() * 0.5
        mat = rock_dark if random.random() > 0.5 else rock_mat
        build_rock(f"CaveRock_{i}", pos, size, mat)

    # --- Stalactites (hanging from above) ---
    stalactite_specs = [
        ((-1.0, 0.5, 4.0), 1.8, 0.2, rock_dark),
        ((1.5, -0.8, 4.2), 1.5, 0.18, rock_mat),
        ((0.3, 1.8, 4.5), 1.2, 0.15, rock_dark),
        ((-2.0, -1.5, 3.8), 2.0, 0.22, rock_mat),
        ((2.5, 1.2, 4.3), 1.0, 0.12, rock_dark),
    ]
    for i, (loc, h, r, mat) in enumerate(stalactite_specs):
        stal = create_cone(
            f"Stalactite_{i}", loc, radius1=r, radius2=0.0, depth=h,
            vertices=6, rotation=(math.pi, 0, random.random() * math.tau),
        )
        assign_material(stal, mat)
        shade_flat(stal)

    # --- Small reflective pool ---
    pool = create_cylinder("Pool", (1.0, 1.2, 0.0), radius=0.7, depth=0.04, vertices=32)
    assign_material(pool, pool_mat)
    shade_smooth(pool)

    # Moss patches
    for i in range(6):
        mx = (random.random() - 0.5) * 5
        my = (random.random() - 0.5) * 5
        moss = create_cube(
            f"Moss_{i}", (mx, my, 0.01),
            (0.15 + random.random() * 0.2, 0.15 + random.random() * 0.2, 0.01),
        )
        assign_material(moss, moss_mat)

    # --- Lighting ---
    bpy.ops.object.empty_add(type="PLAIN_AXES", location=(0, 0, 0.6))
    focus = bpy.context.active_object; focus.name = "FocusTarget"

    bpy.ops.object.camera_add(location=(5.5, -5.0, 3.5))
    cam = bpy.context.active_object; cam.name = "PortfolioCamera"
    cam.data.lens = 45
    cam.data.dof.use_dof = True
    cam.data.dof.focus_object = focus
    cam.data.dof.aperture_fstop = 2.8
    look_at(cam, focus.location)
    bpy.context.scene.camera = cam

    bpy.ops.object.light_add(type="AREA", location=(4, -3, 5))
    key = bpy.context.active_object
    key.data.energy = 600
    key.data.color = (0.7, 0.6, 1.0)
    key.data.shape = "RECTANGLE"; key.data.size = 5.0; key.data.size_y = 3.0
    look_at(key, Vector((0, 0, 0.5)))

    bpy.ops.object.light_add(type="AREA", location=(-4, 4, 3))
    fill = bpy.context.active_object
    fill.data.energy = 350
    fill.data.color = (0.3, 0.9, 0.7)
    fill.data.shape = "RECTANGLE"; fill.data.size = 4.0; fill.data.size_y = 2.5
    look_at(fill, Vector((0, 0, 0.5)))

    bpy.ops.object.light_add(type="POINT", location=(0, 0, 1.8))
    core = bpy.context.active_object
    core.data.energy = 500
    core.data.color = (0.5, 0.15, 1.0)
    core.data.shadow_soft_size = 0.6

    bpy.ops.object.light_add(type="POINT", location=(1.0, 1.2, 0.4))
    pool_light = bpy.context.active_object
    pool_light.data.energy = 150
    pool_light.data.color = (0.1, 0.6, 0.9)
    pool_light.data.shadow_soft_size = 0.4

    bpy.ops.object.light_add(type="POINT", location=(-2.0, 1.5, 0.8))
    scatter_light = bpy.context.active_object
    scatter_light.data.energy = 200
    scatter_light.data.color = (0.1, 0.8, 1.0)
    scatter_light.data.shadow_soft_size = 0.5


def main():
    args = parse_args()
    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    blend_path = output_dir / "crystal_cavern_portfolio.blend"
    render_path = output_dir / "crystal_cavern_portfolio.png"

    build_scene()
    setup_render(args.engine, args.samples, render_path)

    bpy.ops.wm.save_as_mainfile(filepath=str(blend_path))
    bpy.ops.render.render(write_still=True)
    print(f"Saved blend file: {blend_path}")
    print(f"Saved render: {render_path}")


if __name__ == "__main__":
    main()
