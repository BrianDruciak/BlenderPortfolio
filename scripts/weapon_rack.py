import argparse
import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector


def parse_args():
    parser = argparse.ArgumentParser(
        description="Generate a medieval fantasy weapon rack portfolio scene."
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
    deselect_all()
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj

def apply_scale(obj):
    activate(obj)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)

def shade_smooth(obj):
    if obj.type != "MESH":
        return
    for poly in obj.data.polygons:
        poly.use_smooth = True

def add_bevel(obj, width=0.03, segments=3):
    if obj.type != "MESH":
        return
    mod = obj.modifiers.new(name="Bevel", type="BEVEL")
    mod.width = width
    mod.segments = segments
    mod.limit_method = "ANGLE"
    mod.angle_limit = math.radians(30)

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
            s.default_value = value
            return

def make_principled_material(
    name, base_color, roughness=0.45, metallic=0.0,
    emission_color=None, emission_strength=0.0, alpha=1.0,
):
    mat = bpy.data.materials.new(name=name)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
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
    apply_scale(obj)
    return obj

def create_cylinder(name, location, radius, depth, vertices=32, rotation=(0, 0, 0)):
    bpy.ops.mesh.primitive_cylinder_add(
        vertices=vertices, radius=radius, depth=depth,
        location=location, rotation=rotation)
    obj = bpy.context.active_object; obj.name = name
    return obj

def create_sphere(name, location, radius, segments=32, ring_count=16):
    bpy.ops.mesh.primitive_uv_sphere_add(
        segments=segments, ring_count=ring_count,
        radius=radius, location=location)
    obj = bpy.context.active_object; obj.name = name
    return obj

def create_cone(name, location, radius1, radius2, depth, vertices=32, rotation=(0, 0, 0)):
    bpy.ops.mesh.primitive_cone_add(
        vertices=vertices, radius1=radius1, radius2=radius2,
        depth=depth, location=location, rotation=rotation)
    obj = bpy.context.active_object; obj.name = name
    return obj


# ── Scene setup ────────────────────────────────────────────────────────────

def setup_world():
    world = bpy.data.worlds["World"]
    world.use_nodes = True
    nodes = world.node_tree.nodes; links = world.node_tree.links
    nodes.clear()
    output = nodes.new("ShaderNodeOutputWorld"); output.location = (250, 0)
    bg = nodes.new("ShaderNodeBackground"); bg.location = (0, 0)
    bg.inputs[0].default_value = (0.025, 0.018, 0.012, 1.0)
    bg.inputs[1].default_value = 0.4
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


# ── Build the weapon rack scene ───────────────────────────────────────────

def build_sword(name, location, mat_blade, mat_guard, mat_grip, mat_pommel, rotation=(0, 0, 0)):
    """Broadsword: blade + guard + grip + pommel."""
    x, y, z = location

    blade = create_cube(f"{name}_Blade", (x, y, z + 0.75), (0.045, 0.015, 0.55))
    assign_material(blade, mat_blade)
    add_bevel(blade, width=0.006, segments=2)
    shade_smooth(blade)

    tip = create_cone(f"{name}_Tip", (x, y, z + 1.32), 0.045, 0.0, 0.12, vertices=4)
    assign_material(tip, mat_blade)
    shade_smooth(tip)

    guard = create_cube(f"{name}_Guard", (x, y, z + 0.18), (0.14, 0.025, 0.025))
    assign_material(guard, mat_guard)
    add_bevel(guard, width=0.005, segments=2)
    shade_smooth(guard)

    grip = create_cylinder(f"{name}_Grip", (x, y, z), radius=0.025, depth=0.34, vertices=12)
    assign_material(grip, mat_grip)
    shade_smooth(grip)

    pommel = create_sphere(f"{name}_Pommel", (x, y, z - 0.18), radius=0.04, segments=16, ring_count=8)
    assign_material(pommel, mat_pommel)
    shade_smooth(pommel)

    parts = [blade, tip, guard, grip, pommel]
    if rotation != (0, 0, 0):
        for p in parts:
            p.rotation_euler = rotation

    return parts


def build_axe(name, location, mat_head, mat_shaft, rotation=(0, 0, 0)):
    x, y, z = location

    shaft = create_cylinder(f"{name}_Shaft", (x, y, z), radius=0.025, depth=1.2, vertices=8)
    assign_material(shaft, mat_shaft)
    shade_smooth(shaft)

    head = create_cube(f"{name}_Head", (x + 0.12, y, z + 0.45), (0.14, 0.025, 0.18))
    assign_material(head, mat_head)
    add_bevel(head, width=0.008, segments=2)
    shade_smooth(head)

    blade_edge = create_cube(f"{name}_Edge", (x + 0.27, y, z + 0.45), (0.02, 0.015, 0.22))
    assign_material(blade_edge, mat_head)
    add_bevel(blade_edge, width=0.004, segments=2)
    shade_smooth(blade_edge)

    parts = [shaft, head, blade_edge]
    if rotation != (0, 0, 0):
        for p in parts:
            p.rotation_euler = rotation
    return parts


def build_shield(name, location, mat_face, mat_rim, mat_boss, rotation=(0, 0, 0)):
    x, y, z = location

    face = create_cylinder(
        f"{name}_Face", (x, y, z), radius=0.45, depth=0.04, vertices=6,
        rotation=(math.radians(90), 0, 0),
    )
    assign_material(face, mat_face)
    add_bevel(face, width=0.015, segments=3)
    shade_smooth(face)

    boss = create_sphere(f"{name}_Boss", (x, y - 0.03, z), radius=0.1, segments=24, ring_count=12)
    boss.scale = (1, 0.5, 1)
    apply_scale(boss)
    assign_material(boss, mat_boss)
    shade_smooth(boss)

    bpy.ops.mesh.primitive_torus_add(
        location=(x, y - 0.015, z),
        major_radius=0.44, minor_radius=0.03,
        major_segments=6, minor_segments=8,
        rotation=(math.radians(90), 0, 0),
    )
    rim = bpy.context.active_object
    rim.name = f"{name}_Rim"
    assign_material(rim, mat_rim)
    shade_smooth(rim)

    parts = [face, boss, rim]
    if rotation != (0, 0, 0):
        for p in parts:
            p.rotation_euler = rotation
    return parts


def build_scene():
    clear_scene()
    setup_world()

    # --- Materials ---
    wood_dark = make_principled_material("WoodDark", (0.12, 0.065, 0.03), roughness=0.75, metallic=0.0)
    wood_light = make_principled_material("WoodLight", (0.22, 0.14, 0.07), roughness=0.7, metallic=0.0)
    iron = make_principled_material("Iron", (0.38, 0.38, 0.40), roughness=0.35, metallic=0.9)
    steel = make_principled_material("Steel", (0.6, 0.6, 0.62), roughness=0.22, metallic=0.95)
    gold = make_principled_material("Gold", (0.85, 0.65, 0.15), roughness=0.28, metallic=1.0)
    leather = make_principled_material("Leather", (0.18, 0.1, 0.05), roughness=0.82, metallic=0.0)
    red_leather = make_principled_material("RedLeather", (0.35, 0.06, 0.04), roughness=0.75, metallic=0.0)
    shield_blue = make_principled_material("ShieldBlue", (0.08, 0.12, 0.28), roughness=0.55, metallic=0.2)
    stone_mat = make_principled_material("Stone", (0.18, 0.16, 0.14), roughness=0.9, metallic=0.0)
    ground_mat = make_principled_material("Ground", (0.055, 0.045, 0.035), roughness=0.92, metallic=0.0)
    torch_glow = make_principled_material(
        "TorchGlow", base_color=(0.3, 0.1, 0.0), roughness=0.5,
        emission_color=(1.0, 0.55, 0.1), emission_strength=15.0,
    )

    # --- Ground plane ---
    bpy.ops.mesh.primitive_plane_add(size=16, location=(0, 0, -0.02))
    ground = bpy.context.active_object
    ground.name = "Floor"
    assign_material(ground, ground_mat)

    # --- Stone back wall ---
    wall = create_cube("BackWall", (0, 1.6, 1.5), (3.0, 0.15, 1.8))
    assign_material(wall, stone_mat)
    add_bevel(wall, width=0.02, segments=2)
    shade_smooth(wall)

    # --- Weapon rack frame (wood) ---
    rack_y = 1.35

    left_post = create_cube("RackPostL", (-1.2, rack_y, 0.9), (0.06, 0.06, 0.9))
    assign_material(left_post, wood_dark)
    add_bevel(left_post, width=0.008, segments=2)
    shade_smooth(left_post)

    right_post = create_cube("RackPostR", (1.2, rack_y, 0.9), (0.06, 0.06, 0.9))
    assign_material(right_post, wood_dark)
    add_bevel(right_post, width=0.008, segments=2)
    shade_smooth(right_post)

    top_rail = create_cube("TopRail", (0, rack_y, 1.72), (1.3, 0.045, 0.045))
    assign_material(top_rail, wood_dark)
    add_bevel(top_rail, width=0.006, segments=2)
    shade_smooth(top_rail)

    mid_rail = create_cube("MidRail", (0, rack_y, 0.65), (1.3, 0.04, 0.03))
    assign_material(mid_rail, wood_dark)
    add_bevel(mid_rail, width=0.005, segments=2)
    shade_smooth(mid_rail)

    # Pegs
    for i, x_off in enumerate([-0.7, 0.0, 0.7]):
        peg = create_cylinder(
            f"Peg_{i}", (x_off, rack_y - 0.1, 1.25), radius=0.02, depth=0.18,
            vertices=8, rotation=(math.radians(90), 0, 0),
        )
        assign_material(peg, wood_light)
        shade_smooth(peg)

    # --- Weapons on rack ---
    build_sword("Sword1", (-0.7, rack_y - 0.06, 0.62), steel, gold, leather, gold)
    build_sword("Sword2", (0.0, rack_y - 0.06, 0.65), iron, iron, red_leather, iron)
    build_axe("Axe1", (0.7, rack_y - 0.06, 0.45), iron, wood_light)

    # --- Shield leaning against wall ---
    build_shield("Shield1", (-0.65, 1.3, 0.48), shield_blue, gold, iron,
                 rotation=(math.radians(10), 0, math.radians(-8)))

    # --- Torch sconces on wall ---
    for i, x_off in enumerate([-1.8, 1.8]):
        bracket = create_cube(f"TorchBracket_{i}", (x_off, 1.45, 1.4), (0.05, 0.08, 0.05))
        assign_material(bracket, iron)
        shade_smooth(bracket)

        shaft = create_cylinder(
            f"TorchShaft_{i}", (x_off, 1.3, 1.55), radius=0.025, depth=0.45,
            vertices=8, rotation=(math.radians(15), 0, 0),
        )
        assign_material(shaft, wood_light)
        shade_smooth(shaft)

        flame = create_sphere(f"TorchFlame_{i}", (x_off, 1.22, 1.82), radius=0.08)
        flame.scale = (0.7, 0.7, 1.3)
        apply_scale(flame)
        assign_material(flame, torch_glow)
        shade_smooth(flame)

        bpy.ops.object.light_add(type="POINT", location=(x_off, 1.1, 1.8))
        tl = bpy.context.active_object
        tl.data.energy = 350
        tl.data.color = (1.0, 0.6, 0.2)
        tl.data.shadow_soft_size = 0.35

    # --- Camera & main lights ---
    bpy.ops.object.empty_add(type="PLAIN_AXES", location=(0, 1.2, 0.95))
    focus = bpy.context.active_object; focus.name = "FocusTarget"

    bpy.ops.object.camera_add(location=(3.8, -3.6, 2.6))
    cam = bpy.context.active_object; cam.name = "PortfolioCamera"
    cam.data.lens = 52
    cam.data.dof.use_dof = True
    cam.data.dof.focus_object = focus
    cam.data.dof.aperture_fstop = 3.5
    look_at(cam, focus.location)
    bpy.context.scene.camera = cam

    bpy.ops.object.light_add(type="AREA", location=(3, -3, 4.5))
    key = bpy.context.active_object
    key.data.energy = 1200
    key.data.color = (1.0, 0.9, 0.75)
    key.data.shape = "RECTANGLE"; key.data.size = 4.0; key.data.size_y = 2.5
    look_at(key, Vector((0, 1.2, 1.0)))

    bpy.ops.object.light_add(type="AREA", location=(-3, -2, 3))
    fill = bpy.context.active_object
    fill.data.energy = 500
    fill.data.color = (0.7, 0.75, 0.9)
    fill.data.shape = "RECTANGLE"; fill.data.size = 3.0; fill.data.size_y = 2.0
    look_at(fill, Vector((0, 1.2, 1.0)))


def main():
    args = parse_args()
    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    blend_path = output_dir / "weapon_rack_portfolio.blend"
    render_path = output_dir / "weapon_rack_portfolio.png"

    build_scene()
    setup_render(args.engine, args.samples, render_path)

    bpy.ops.wm.save_as_mainfile(filepath=str(blend_path))
    bpy.ops.render.render(write_still=True)
    print(f"Saved blend file: {blend_path}")
    print(f"Saved render: {render_path}")


if __name__ == "__main__":
    main()
