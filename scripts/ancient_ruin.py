import argparse
import math
import random
import sys
from pathlib import Path

import bpy
from mathutils import Vector


def parse_args():
    parser = argparse.ArgumentParser(
        description="Generate an ancient ruin archway portfolio scene."
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

def create_sphere(name, location, radius, segments=32, ring_count=16):
    bpy.ops.mesh.primitive_uv_sphere_add(
        segments=segments, ring_count=ring_count,
        radius=radius, location=location)
    obj = bpy.context.active_object; obj.name = name; return obj

def create_cone(name, location, radius1, radius2, depth, vertices=32, rotation=(0, 0, 0)):
    bpy.ops.mesh.primitive_cone_add(
        vertices=vertices, radius1=radius1, radius2=radius2,
        depth=depth, location=location, rotation=rotation)
    obj = bpy.context.active_object; obj.name = name; return obj


# ── World & render ─────────────────────────────────────────────────────────

def setup_world():
    world = bpy.data.worlds["World"]
    world.use_nodes = True
    nodes = world.node_tree.nodes; links = world.node_tree.links
    nodes.clear()
    output = nodes.new("ShaderNodeOutputWorld"); output.location = (250, 0)
    bg = nodes.new("ShaderNodeBackground"); bg.location = (0, 0)
    bg.inputs[0].default_value = (0.12, 0.15, 0.22, 1.0)
    bg.inputs[1].default_value = 0.8
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


# ── Build ruin scene ──────────────────────────────────────────────────────

def build_scene():
    clear_scene()
    setup_world()
    random.seed(99)

    # --- Materials ---
    stone_light = make_principled_material("StoneLight", (0.32, 0.30, 0.26), roughness=0.88, metallic=0.0)
    stone_dark = make_principled_material("StoneDark", (0.18, 0.16, 0.14), roughness=0.92, metallic=0.0)
    stone_warm = make_principled_material("StoneWarm", (0.28, 0.22, 0.16), roughness=0.85, metallic=0.0)
    marble_mat = make_principled_material("Marble", (0.72, 0.70, 0.66), roughness=0.35, metallic=0.0)
    gold_mat = make_principled_material("Gold", (0.75, 0.55, 0.12), roughness=0.3, metallic=1.0)
    moss_mat = make_principled_material("Moss", (0.06, 0.12, 0.04), roughness=0.9, metallic=0.0)
    vine_mat = make_principled_material("Vine", (0.04, 0.08, 0.02), roughness=0.85, metallic=0.0)
    ground_mat = make_principled_material("Ground", (0.14, 0.12, 0.09), roughness=0.95, metallic=0.0)
    rune_glow = make_principled_material(
        "RuneGlow", (0.02, 0.04, 0.08), roughness=0.15, metallic=0.0,
        emission_color=(0.3, 0.7, 1.0), emission_strength=8.0,
    )
    fire_mat = make_principled_material(
        "Fire", (0.3, 0.08, 0.01), roughness=0.5, metallic=0.0,
        emission_color=(1.0, 0.5, 0.1), emission_strength=12.0,
    )

    # --- Ground ---
    bpy.ops.mesh.primitive_plane_add(size=20, location=(0, 0, 0))
    gnd = bpy.context.active_object; gnd.name = "Ground"
    assign_material(gnd, ground_mat)

    # --- Raised stone platform ---
    platform = create_cube("Platform", (0, 0, 0.12), (2.5, 2.5, 0.12))
    assign_material(platform, stone_dark)
    add_bevel(platform, width=0.02, segments=2)
    shade_smooth(platform)

    step1 = create_cube("Step1", (0, -2.2, 0.06), (2.8, 0.3, 0.06))
    assign_material(step1, stone_dark); add_bevel(step1, width=0.015, segments=2)

    step2 = create_cube("Step2", (0, -2.55, 0.03), (3.0, 0.3, 0.03))
    assign_material(step2, stone_dark); add_bevel(step2, width=0.01, segments=2)

    # --- Two main pillars ---
    pillar_x = 1.3
    for side, sx in enumerate([-pillar_x, pillar_x]):
        pillar_base = create_cylinder(
            f"PillarBase_{side}", (sx, 0, 0.35), radius=0.42, depth=0.22, vertices=8,
        )
        assign_material(pillar_base, stone_warm)
        add_bevel(pillar_base, width=0.015, segments=2)
        shade_smooth(pillar_base)

        shaft = create_cylinder(
            f"PillarShaft_{side}", (sx, 0, 1.8), radius=0.3, depth=2.7, vertices=12,
        )
        assign_material(shaft, stone_light)
        shade_smooth(shaft)

        # Fluting effect (thin cylinders cut along shaft)
        for fi in range(8):
            angle = fi * (math.tau / 8)
            fx = sx + math.cos(angle) * 0.28
            fy = math.sin(angle) * 0.28
            flute = create_cylinder(
                f"Flute_{side}_{fi}", (fx, fy, 1.8),
                radius=0.04, depth=2.5, vertices=8,
            )
            assign_material(flute, stone_dark)

        cap = create_cylinder(
            f"PillarCap_{side}", (sx, 0, 3.2), radius=0.45, depth=0.18, vertices=8,
        )
        assign_material(cap, stone_warm)
        add_bevel(cap, width=0.015, segments=2)
        shade_smooth(cap)

        # Rune strips on pillar
        for ri in range(3):
            rz = 1.0 + ri * 0.8
            rune = create_cube(
                f"Rune_{side}_{ri}", (sx + (0.31 if sx > 0 else -0.31), 0, rz),
                (0.008, 0.08, 0.04),
            )
            assign_material(rune, rune_glow)

    # --- Lintel (crossbar on top) ---
    lintel = create_cube("Lintel", (0, 0, 3.45), (1.6, 0.35, 0.18))
    assign_material(lintel, stone_warm)
    add_bevel(lintel, width=0.02, segments=2)
    shade_smooth(lintel)

    # Decorative frieze
    for fi in range(7):
        fx = -0.9 + fi * 0.3
        frieze = create_cube(f"Frieze_{fi}", (fx, -0.36, 3.45), (0.08, 0.005, 0.12))
        assign_material(frieze, gold_mat)

    # Keystone at center top
    keystone = create_cube("Keystone", (0, 0, 3.7), (0.2, 0.2, 0.12))
    assign_material(keystone, marble_mat)
    add_bevel(keystone, width=0.01, segments=2)
    shade_smooth(keystone)

    keystone_rune = create_sphere("KeystoneRune", (0, -0.21, 3.7), radius=0.08, segments=16, ring_count=8)
    assign_material(keystone_rune, rune_glow)
    shade_smooth(keystone_rune)

    # --- Broken secondary pillars ---
    broken_specs = [
        ((-2.5, -1.5), 1.2, 0.22, math.radians(5)),
        ((2.5, 1.3), 0.8, 0.2, math.radians(-8)),
        ((-2.8, 1.8), 1.5, 0.25, math.radians(3)),
    ]
    for bi, ((bx, by), bh, br, tilt) in enumerate(broken_specs):
        stump = create_cylinder(
            f"BrokenPillar_{bi}", (bx, by, bh / 2), radius=br, depth=bh,
            vertices=10, rotation=(tilt, 0, random.random()),
        )
        assign_material(stump, stone_light)
        shade_flat(stump)

        rubble_count = random.randint(2, 4)
        for ri in range(rubble_count):
            rx = bx + (random.random() - 0.5) * 0.8
            ry = by + (random.random() - 0.5) * 0.8
            rs = 0.08 + random.random() * 0.15
            rubble = create_cube(
                f"Rubble_{bi}_{ri}", (rx, ry, rs / 2),
                (rs, rs * 0.8, rs * 0.6),
                rotation=(random.random() * 0.3, random.random() * 0.3, random.random()),
            )
            assign_material(rubble, random.choice([stone_light, stone_dark, stone_warm]))

    # --- Moss and vine patches ---
    for mi in range(10):
        mx = (random.random() - 0.5) * 5
        my = (random.random() - 0.5) * 5
        mz = random.random() * 0.3
        moss = create_cube(
            f"Moss_{mi}", (mx, my, mz),
            (0.1 + random.random() * 0.2, 0.1 + random.random() * 0.2, 0.015),
        )
        assign_material(moss, moss_mat)

    # Vines on pillars
    for side, sx in enumerate([-pillar_x, pillar_x]):
        for vi in range(3):
            vz = 0.5 + vi * 0.9
            vine = create_cube(
                f"Vine_{side}_{vi}",
                (sx + (0.32 if vi % 2 == 0 else -0.32), 0.1 * vi, vz),
                (0.02, 0.15, 0.3),
                rotation=(0.1, 0.05, vi * 0.3),
            )
            assign_material(vine, vine_mat)

    # --- Stone braziers with fire ---
    for bi, (bx, by) in enumerate([(-1.8, -1.2), (1.8, -1.2)]):
        brazier_base = create_cylinder(
            f"BrazierBase_{bi}", (bx, by, 0.15), radius=0.2, depth=0.3, vertices=8,
        )
        assign_material(brazier_base, stone_dark)
        add_bevel(brazier_base, width=0.01, segments=2)
        shade_smooth(brazier_base)

        bowl = create_cylinder(
            f"BrazierBowl_{bi}", (bx, by, 0.38), radius=0.25, depth=0.12, vertices=8,
        )
        assign_material(bowl, gold_mat)
        add_bevel(bowl, width=0.008, segments=2)
        shade_smooth(bowl)

        flame = create_sphere(
            f"Flame_{bi}", (bx, by, 0.55), radius=0.12, segments=12, ring_count=8,
        )
        flame.scale = (0.7, 0.7, 1.5)
        apply_scale(flame)
        assign_material(flame, fire_mat)
        shade_smooth(flame)

        bpy.ops.object.light_add(type="POINT", location=(bx, by, 0.7))
        fl = bpy.context.active_object
        fl.data.energy = 500
        fl.data.color = (1.0, 0.6, 0.2)
        fl.data.shadow_soft_size = 0.4

    # --- Camera & lighting ---
    bpy.ops.object.empty_add(type="PLAIN_AXES", location=(0, 0, 1.8))
    focus = bpy.context.active_object; focus.name = "FocusTarget"

    bpy.ops.object.camera_add(location=(5.5, -6.0, 3.5))
    cam = bpy.context.active_object; cam.name = "PortfolioCamera"
    cam.data.lens = 42
    cam.data.dof.use_dof = True
    cam.data.dof.focus_object = focus
    cam.data.dof.aperture_fstop = 3.5
    look_at(cam, focus.location)
    bpy.context.scene.camera = cam

    bpy.ops.object.light_add(type="SUN", location=(3, -2, 8))
    sun = bpy.context.active_object
    sun.data.energy = 3.5
    sun.data.color = (1.0, 0.92, 0.78)
    sun.data.angle = math.radians(2)
    look_at(sun, Vector((0, 0, 0)))

    bpy.ops.object.light_add(type="AREA", location=(-4, 4, 4))
    fill = bpy.context.active_object
    fill.data.energy = 600
    fill.data.color = (0.6, 0.7, 0.9)
    fill.data.shape = "RECTANGLE"; fill.data.size = 5.0; fill.data.size_y = 3.0
    look_at(fill, Vector((0, 0, 1.5)))

    bpy.ops.object.light_add(type="POINT", location=(0, -0.2, 3.7))
    rune_light = bpy.context.active_object
    rune_light.data.energy = 200
    rune_light.data.color = (0.3, 0.7, 1.0)
    rune_light.data.shadow_soft_size = 0.5


def main():
    args = parse_args()
    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    blend_path = output_dir / "ancient_ruin_portfolio.blend"
    render_path = output_dir / "ancient_ruin_portfolio.png"

    build_scene()
    setup_render(args.engine, args.samples, render_path)

    bpy.ops.wm.save_as_mainfile(filepath=str(blend_path))
    bpy.ops.render.render(write_still=True)
    print(f"Saved blend file: {blend_path}")
    print(f"Saved render: {render_path}")


if __name__ == "__main__":
    main()
