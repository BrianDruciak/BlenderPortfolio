import argparse
import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector


def parse_args():
    parser = argparse.ArgumentParser(
        description="Generate a futuristic control terminal portfolio scene."
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


# ── World & render ─────────────────────────────────────────────────────────

def setup_world():
    world = bpy.data.worlds["World"]
    world.use_nodes = True
    nodes = world.node_tree.nodes; links = world.node_tree.links
    nodes.clear()
    output = nodes.new("ShaderNodeOutputWorld"); output.location = (250, 0)
    bg = nodes.new("ShaderNodeBackground"); bg.location = (0, 0)
    bg.inputs[0].default_value = (0.012, 0.015, 0.025, 1.0)
    bg.inputs[1].default_value = 0.5
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


# ── Build terminal scene ──────────────────────────────────────────────────

def build_scene():
    clear_scene()
    setup_world()

    # --- Materials ---
    chassis_mat = make_principled_material(
        "Chassis", (0.06, 0.065, 0.08), roughness=0.25, metallic=0.85,
    )
    panel_mat = make_principled_material(
        "Panel", (0.1, 0.11, 0.13), roughness=0.35, metallic=0.6,
    )
    dark_mat = make_principled_material(
        "DarkTrim", (0.025, 0.025, 0.03), roughness=0.5, metallic=0.7,
    )
    screen_mat = make_principled_material(
        "Screen", (0.005, 0.01, 0.02), roughness=0.02, metallic=0.0,
        emission_color=(0.15, 0.75, 1.0), emission_strength=10.0,
    )
    screen_amber = make_principled_material(
        "ScreenAmber", (0.02, 0.01, 0.005), roughness=0.02, metallic=0.0,
        emission_color=(1.0, 0.65, 0.1), emission_strength=8.0,
    )
    button_green = make_principled_material(
        "ButtonGreen", (0.01, 0.04, 0.01), roughness=0.3, metallic=0.2,
        emission_color=(0.15, 1.0, 0.3), emission_strength=6.0,
    )
    button_red = make_principled_material(
        "ButtonRed", (0.04, 0.01, 0.01), roughness=0.3, metallic=0.2,
        emission_color=(1.0, 0.15, 0.1), emission_strength=6.0,
    )
    led_blue = make_principled_material(
        "LEDBlue", (0.01, 0.02, 0.05), roughness=0.1, metallic=0.0,
        emission_color=(0.2, 0.5, 1.0), emission_strength=12.0,
    )
    cable_mat = make_principled_material(
        "Cable", (0.02, 0.02, 0.025), roughness=0.65, metallic=0.3,
    )
    floor_mat = make_principled_material(
        "Floor", (0.035, 0.038, 0.045), roughness=0.8, metallic=0.1,
    )
    rubber_mat = make_principled_material(
        "Rubber", (0.03, 0.03, 0.03), roughness=0.9, metallic=0.0,
    )

    # --- Floor ---
    bpy.ops.mesh.primitive_plane_add(size=16, location=(0, 0, 0))
    floor = bpy.context.active_object; floor.name = "Floor"
    assign_material(floor, floor_mat)

    # --- Main terminal body ---
    base = create_cube("TerminalBase", (0, 0, 0.55), (0.65, 0.5, 0.55))
    assign_material(base, chassis_mat)
    add_bevel(base, width=0.02, segments=3)
    shade_smooth(base)

    desk_top = create_cube("DeskTop", (0, -0.15, 1.08), (0.72, 0.6, 0.04))
    assign_material(desk_top, panel_mat)
    add_bevel(desk_top, width=0.01, segments=2)
    shade_smooth(desk_top)

    # --- Main screen (angled) ---
    screen_back = create_cube(
        "ScreenBack", (0, 0.22, 1.55), (0.6, 0.04, 0.38),
        rotation=(math.radians(-12), 0, 0),
    )
    assign_material(screen_back, chassis_mat)
    add_bevel(screen_back, width=0.015, segments=2)
    shade_smooth(screen_back)

    screen = create_cube(
        "MainScreen", (0, 0.19, 1.55), (0.55, 0.008, 0.34),
        rotation=(math.radians(-12), 0, 0),
    )
    assign_material(screen, screen_mat)

    screen_bezel = create_cube(
        "ScreenBezel", (0, 0.205, 1.55), (0.58, 0.012, 0.37),
        rotation=(math.radians(-12), 0, 0),
    )
    assign_material(screen_bezel, dark_mat)
    add_bevel(screen_bezel, width=0.008, segments=2)
    shade_smooth(screen_bezel)

    # --- Side screen (smaller, amber) ---
    side_back = create_cube(
        "SideScreenBack", (0.55, 0.12, 1.35), (0.22, 0.03, 0.25),
        rotation=(math.radians(-8), math.radians(20), 0),
    )
    assign_material(side_back, chassis_mat)
    add_bevel(side_back, width=0.01, segments=2)
    shade_smooth(side_back)

    side_screen = create_cube(
        "SideScreen", (0.53, 0.1, 1.35), (0.19, 0.006, 0.22),
        rotation=(math.radians(-8), math.radians(20), 0),
    )
    assign_material(side_screen, screen_amber)

    # --- Keyboard panel (angled on desk) ---
    kb_base = create_cube(
        "KeyboardBase", (0, -0.3, 1.12), (0.45, 0.22, 0.02),
        rotation=(math.radians(8), 0, 0),
    )
    assign_material(kb_base, dark_mat)
    add_bevel(kb_base, width=0.005, segments=2)
    shade_smooth(kb_base)

    for row in range(4):
        for col in range(10):
            kx = -0.33 + col * 0.072
            ky = -0.18 - row * 0.055
            key = create_cube(
                f"Key_{row}_{col}", (kx, ky, 1.14 + row * 0.004),
                (0.028, 0.02, 0.008),
            )
            mat = led_blue if (row == 0 and col in [0, 9]) else panel_mat
            assign_material(key, mat)

    # --- Button cluster (left of keyboard) ---
    for i, (bx, by, mat) in enumerate([
        (-0.55, -0.2, button_green), (-0.55, -0.28, button_red),
        (-0.55, -0.36, button_green), (-0.48, -0.24, led_blue),
    ]):
        btn = create_cylinder(
            f"Button_{i}", (bx, by, 1.12), radius=0.022, depth=0.015, vertices=16,
        )
        assign_material(btn, mat)
        shade_smooth(btn)

    # --- Status LEDs along front edge ---
    for i in range(8):
        lx = -0.42 + i * 0.12
        led = create_cube(f"LED_{i}", (lx, -0.58, 1.06), (0.02, 0.005, 0.005))
        mat = led_blue if i % 3 != 0 else button_green
        assign_material(led, mat)

    # --- Ventilation grills on sides ---
    for side_x, mirror in [(0.66, 1), (-0.66, -1)]:
        for gi in range(5):
            gz = 0.35 + gi * 0.12
            vent = create_cube(
                f"Vent_{side_x}_{gi}", (side_x, 0, gz), (0.008, 0.3, 0.04),
            )
            assign_material(vent, dark_mat)

    # --- Cable bundle from rear ---
    for i, (cx, cz) in enumerate([(-0.2, 0.3), (0.1, 0.25), (0.25, 0.35)]):
        cable = create_cylinder(
            f"Cable_{i}", (cx, 0.6, cz), radius=0.018, depth=0.5,
            vertices=8, rotation=(math.radians(85), 0, 0),
        )
        assign_material(cable, cable_mat)
        shade_smooth(cable)

    # --- Floor grating beneath ---
    for i in range(6):
        gx = -0.5 + i * 0.2
        grate = create_cube(f"Grate_{i}", (gx, 0, 0.01), (0.015, 0.8, 0.01))
        assign_material(grate, dark_mat)

    # --- Rubber feet ---
    for fx, fy in [(-0.5, -0.4), (0.5, -0.4), (-0.5, 0.4), (0.5, 0.4)]:
        foot = create_cylinder(f"Foot_{fx}_{fy}", (fx, fy, 0.02), radius=0.04, depth=0.04, vertices=16)
        assign_material(foot, rubber_mat)
        shade_smooth(foot)

    # --- Holographic projector nub on top ---
    proj_base = create_cylinder(
        "ProjBase", (0, 0.22, 1.95), radius=0.06, depth=0.04, vertices=16,
    )
    assign_material(proj_base, chassis_mat)
    shade_smooth(proj_base)

    proj_lens = create_sphere("ProjLens", (0, 0.22, 1.99), radius=0.035, segments=16, ring_count=8)
    assign_material(proj_lens, led_blue)
    shade_smooth(proj_lens)

    # --- Camera & lighting ---
    bpy.ops.object.empty_add(type="PLAIN_AXES", location=(0, 0, 1.1))
    focus = bpy.context.active_object; focus.name = "FocusTarget"

    bpy.ops.object.camera_add(location=(3.5, -4.0, 2.8))
    cam = bpy.context.active_object; cam.name = "PortfolioCamera"
    cam.data.lens = 55
    cam.data.dof.use_dof = True
    cam.data.dof.focus_object = focus
    cam.data.dof.aperture_fstop = 3.0
    look_at(cam, focus.location)
    bpy.context.scene.camera = cam

    bpy.ops.object.light_add(type="AREA", location=(4, -3, 5))
    key = bpy.context.active_object
    key.data.energy = 1800
    key.data.color = (0.85, 0.9, 1.0)
    key.data.shape = "RECTANGLE"; key.data.size = 5.0; key.data.size_y = 3.0
    look_at(key, Vector((0, 0, 1.0)))

    bpy.ops.object.light_add(type="AREA", location=(-3, 3, 3.5))
    rim = bpy.context.active_object
    rim.data.energy = 800
    rim.data.color = (0.2, 0.6, 1.0)
    rim.data.shape = "RECTANGLE"; rim.data.size = 3.5; rim.data.size_y = 2.0
    look_at(rim, Vector((0, 0, 1.0)))

    bpy.ops.object.light_add(type="POINT", location=(0, 0.15, 1.55))
    screen_glow = bpy.context.active_object
    screen_glow.data.energy = 120
    screen_glow.data.color = (0.15, 0.75, 1.0)
    screen_glow.data.shadow_soft_size = 0.3

    bpy.ops.object.light_add(type="POINT", location=(0.55, 0.1, 1.35))
    side_glow = bpy.context.active_object
    side_glow.data.energy = 60
    side_glow.data.color = (1.0, 0.65, 0.1)
    side_glow.data.shadow_soft_size = 0.2

    bpy.ops.object.light_add(type="POINT", location=(0, -0.5, 1.3))
    fill = bpy.context.active_object
    fill.data.energy = 200
    fill.data.color = (0.9, 0.85, 0.8)
    fill.data.shadow_soft_size = 0.6


def main():
    args = parse_args()
    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    blend_path = output_dir / "control_terminal_portfolio.blend"
    render_path = output_dir / "control_terminal_portfolio.png"

    build_scene()
    setup_render(args.engine, args.samples, render_path)

    bpy.ops.wm.save_as_mainfile(filepath=str(blend_path))
    bpy.ops.render.render(write_still=True)
    print(f"Saved blend file: {blend_path}")
    print(f"Saved render: {render_path}")


if __name__ == "__main__":
    main()
