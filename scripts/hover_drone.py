import argparse
import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector


def parse_args():
    parser = argparse.ArgumentParser(
        description="Generate a sci-fi hover drone portfolio scene in Blender."
    )
    parser.add_argument(
        "--output-dir",
        default=str(Path(__file__).resolve().parent / "blender_output"),
        help="Directory for the rendered image and .blend file.",
    )
    parser.add_argument(
        "--engine",
        default="BLENDER_EEVEE_NEXT",
        help="Render engine: BLENDER_EEVEE_NEXT, BLENDER_EEVEE, or CYCLES.",
    )
    parser.add_argument("--samples", type=int, default=128, help="Render samples.")
    if "--" not in sys.argv:
        return parser.parse_args([])
    return parser.parse_args(sys.argv[sys.argv.index("--") + 1 :])


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
        for datablock in list(block):
            if datablock.users == 0:
                block.remove(datablock)


def set_socket(node, names, value):
    for name in names:
        socket = node.inputs.get(name)
        if socket is not None:
            socket.default_value = value
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

    output = nodes.new("ShaderNodeOutputMaterial")
    output.location = (300, 0)
    bsdf = nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.location = (0, 0)

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
    obj = bpy.context.active_object
    obj.name = name
    obj.scale = scale
    apply_scale(obj)
    return obj


def create_cylinder(name, location, radius, depth, vertices=32, rotation=(0, 0, 0)):
    bpy.ops.mesh.primitive_cylinder_add(
        vertices=vertices, radius=radius, depth=depth,
        location=location, rotation=rotation,
    )
    obj = bpy.context.active_object
    obj.name = name
    return obj


def create_sphere(name, location, radius, segments=32, ring_count=16):
    bpy.ops.mesh.primitive_uv_sphere_add(
        segments=segments, ring_count=ring_count,
        radius=radius, location=location,
    )
    obj = bpy.context.active_object
    obj.name = name
    return obj


def setup_world():
    world = bpy.data.worlds["World"]
    world.use_nodes = True
    nodes = world.node_tree.nodes
    links = world.node_tree.links
    nodes.clear()

    output = nodes.new("ShaderNodeOutputWorld")
    output.location = (250, 0)
    background = nodes.new("ShaderNodeBackground")
    background.location = (0, 0)
    background.inputs[0].default_value = (0.018, 0.025, 0.04, 1.0)
    background.inputs[1].default_value = 0.6
    links.new(background.outputs["Background"], output.inputs["Surface"])


def setup_render(engine_name, samples, render_path):
    scene = bpy.context.scene
    scene.render.resolution_x = 1920
    scene.render.resolution_y = 1080
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.filepath = str(render_path)

    available_engines = {
        item.identifier for item in scene.render.bl_rna.properties["engine"].enum_items
    }
    if engine_name in available_engines:
        scene.render.engine = engine_name
    elif "BLENDER_EEVEE_NEXT" in available_engines:
        scene.render.engine = "BLENDER_EEVEE_NEXT"
    elif "BLENDER_EEVEE" in available_engines:
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


def build_scene():
    clear_scene()
    setup_world()

    # --- Materials ---
    hull_mat = make_principled_material(
        "DroneHull", base_color=(0.22, 0.24, 0.26), roughness=0.18, metallic=0.9,
    )
    accent_mat = make_principled_material(
        "DroneAccent", base_color=(0.9, 0.35, 0.0), roughness=0.32, metallic=0.4,
    )
    dark_mat = make_principled_material(
        "DroneDark", base_color=(0.04, 0.04, 0.05), roughness=0.6, metallic=0.7,
    )
    lens_mat = make_principled_material(
        "DroneLens", base_color=(0.01, 0.01, 0.02), roughness=0.05, metallic=0.0,
        emission_color=(1.0, 0.15, 0.05), emission_strength=12.0,
    )
    thruster_glow = make_principled_material(
        "ThrusterGlow", base_color=(0.02, 0.06, 0.2), roughness=0.1, metallic=0.0,
        emission_color=(0.2, 0.6, 1.0), emission_strength=18.0,
    )
    ground_mat = make_principled_material(
        "Ground", base_color=(0.04, 0.045, 0.05), roughness=0.85, metallic=0.0,
    )
    antenna_mat = make_principled_material(
        "Antenna", base_color=(0.12, 0.12, 0.14), roughness=0.3, metallic=0.8,
    )

    # --- Ground ---
    bpy.ops.mesh.primitive_plane_add(size=20, location=(0, 0, -1.2))
    ground = bpy.context.active_object
    ground.name = "GroundPlane"
    assign_material(ground, ground_mat)

    # --- Main body: flattened ellipsoid shape ---
    body = create_sphere("DroneBody", (0, 0, 0), radius=1.0, segments=48, ring_count=24)
    body.scale = (1.4, 1.0, 0.35)
    apply_scale(body)
    assign_material(body, hull_mat)
    add_bevel(body, width=0.015, segments=2)
    shade_smooth(body)

    # Top canopy
    canopy = create_sphere("Canopy", (0, 0, 0.18), radius=0.55, segments=32, ring_count=16)
    canopy.scale = (1.0, 0.8, 0.45)
    apply_scale(canopy)
    assign_material(canopy, dark_mat)
    shade_smooth(canopy)

    # Front sensor eye
    eye = create_sphere("SensorEye", (1.15, 0, -0.02), radius=0.18, segments=24, ring_count=12)
    assign_material(eye, lens_mat)
    shade_smooth(eye)

    eye_housing = create_cylinder(
        "EyeHousing", (1.05, 0, -0.02), radius=0.24, depth=0.14, vertices=24,
        rotation=(0, math.radians(90), 0),
    )
    assign_material(eye_housing, dark_mat)
    add_bevel(eye_housing, width=0.01, segments=2)
    shade_smooth(eye_housing)

    # Accent stripes on body
    for i, y_off in enumerate([-0.42, 0.42]):
        stripe = create_cube(
            f"Stripe_{i}", (0, y_off, 0.12), (0.9, 0.025, 0.06),
        )
        assign_material(stripe, accent_mat)

    # --- Arms and rotors (4 arms) ---
    arm_angles = [45, 135, 225, 315]
    arm_length = 1.6
    for i, angle_deg in enumerate(arm_angles):
        angle = math.radians(angle_deg)
        ax = math.cos(angle) * 0.8
        ay = math.sin(angle) * 0.8
        ex = math.cos(angle) * arm_length
        ey = math.sin(angle) * arm_length

        arm = create_cube(
            f"Arm_{i}",
            ((ax + ex) / 2, (ay + ey) / 2, -0.04),
            (0.06, 0.35, 0.04),
            rotation=(0, 0, angle + math.radians(90)),
        )
        assign_material(arm, hull_mat)
        add_bevel(arm, width=0.008, segments=2)
        shade_smooth(arm)

        motor = create_cylinder(
            f"Motor_{i}", (ex, ey, 0.02), radius=0.16, depth=0.14, vertices=24,
        )
        assign_material(motor, dark_mat)
        add_bevel(motor, width=0.01, segments=2)
        shade_smooth(motor)

        rotor_disc = create_cylinder(
            f"RotorDisc_{i}", (ex, ey, 0.12), radius=0.45, depth=0.008, vertices=48,
        )
        assign_material(rotor_disc, make_principled_material(
            f"RotorGhost_{i}", base_color=(0.5, 0.5, 0.5),
            roughness=0.1, metallic=0.3, alpha=0.12,
        ))
        shade_smooth(rotor_disc)

        thruster = create_cylinder(
            f"Thruster_{i}", (ex, ey, -0.12), radius=0.10, depth=0.06, vertices=16,
        )
        assign_material(thruster, thruster_glow)
        shade_smooth(thruster)

    # --- Undercarriage details ---
    belly_plate = create_cube("BellyPlate", (0, 0, -0.28), (0.7, 0.5, 0.04))
    assign_material(belly_plate, dark_mat)
    add_bevel(belly_plate, width=0.01, segments=2)
    shade_smooth(belly_plate)

    for i, x_off in enumerate([-0.35, 0.35]):
        skid = create_cube(
            f"Skid_{i}", (x_off, 0, -0.42), (0.04, 0.5, 0.12),
        )
        assign_material(skid, hull_mat)
        add_bevel(skid, width=0.008, segments=2)
        shade_smooth(skid)

        foot = create_cube(
            f"SkidFoot_{i}", (x_off, 0, -0.52), (0.06, 0.25, 0.02),
        )
        assign_material(foot, accent_mat)

    # --- Rear antenna ---
    antenna = create_cylinder(
        "Antenna", (-1.1, 0, 0.22), radius=0.015, depth=0.5, vertices=8,
        rotation=(math.radians(15), 0, 0),
    )
    assign_material(antenna, antenna_mat)
    shade_smooth(antenna)

    antenna_tip = create_sphere("AntennaTip", (-1.1, 0.06, 0.48), radius=0.035)
    assign_material(antenna_tip, lens_mat)
    shade_smooth(antenna_tip)

    # --- Side-mounted cargo pods ---
    for i, y_off in enumerate([-0.72, 0.72]):
        pod = create_cube(
            f"CargoPod_{i}", (0.15, y_off, -0.12), (0.22, 0.12, 0.1),
        )
        assign_material(pod, hull_mat)
        add_bevel(pod, width=0.01, segments=2)
        shade_smooth(pod)

        pod_accent = create_cube(
            f"PodAccent_{i}", (0.15, y_off, -0.06), (0.18, 0.005, 0.04),
        )
        assign_material(pod_accent, accent_mat)

    # --- Camera & lighting ---
    bpy.ops.object.empty_add(type="PLAIN_AXES", location=(0, 0, 0))
    focus = bpy.context.active_object
    focus.name = "FocusTarget"

    bpy.ops.object.camera_add(location=(4.5, -4.5, 3.2))
    cam = bpy.context.active_object
    cam.name = "PortfolioCamera"
    cam.data.lens = 65
    cam.data.dof.use_dof = True
    cam.data.dof.focus_object = focus
    cam.data.dof.aperture_fstop = 3.2
    look_at(cam, focus.location)
    bpy.context.scene.camera = cam

    bpy.ops.object.light_add(type="AREA", location=(5, -3, 5))
    key = bpy.context.active_object
    key.data.energy = 2500
    key.data.color = (1.0, 0.95, 0.9)
    key.data.shape = "RECTANGLE"
    key.data.size = 5.0
    key.data.size_y = 3.0
    look_at(key, Vector((0, 0, 0)))

    bpy.ops.object.light_add(type="AREA", location=(-4, 4, 3.5))
    rim = bpy.context.active_object
    rim.data.energy = 1200
    rim.data.color = (0.3, 0.6, 1.0)
    rim.data.shape = "RECTANGLE"
    rim.data.size = 4.0
    rim.data.size_y = 2.5
    look_at(rim, Vector((0, 0, 0)))

    bpy.ops.object.light_add(type="POINT", location=(1.5, 0, -0.5))
    under = bpy.context.active_object
    under.data.energy = 200
    under.data.color = (0.2, 0.6, 1.0)
    under.data.shadow_soft_size = 0.5

    bpy.ops.object.light_add(type="POINT", location=(-1.5, -1, 2))
    fill = bpy.context.active_object
    fill.data.energy = 300
    fill.data.color = (1.0, 0.5, 0.2)
    fill.data.shadow_soft_size = 0.8


def main():
    args = parse_args()
    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    blend_path = output_dir / "hover_drone_portfolio.blend"
    render_path = output_dir / "hover_drone_portfolio.png"

    build_scene()
    setup_render(args.engine, args.samples, render_path)

    bpy.ops.wm.save_as_mainfile(filepath=str(blend_path))
    bpy.ops.render.render(write_still=True)

    print(f"Saved blend file: {blend_path}")
    print(f"Saved render: {render_path}")


if __name__ == "__main__":
    main()
