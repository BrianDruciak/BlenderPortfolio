import argparse
import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector


def parse_args():
    parser = argparse.ArgumentParser(
        description="Generate a stylized Blender portfolio scene."
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
    parser.add_argument(
        "--samples",
        type=int,
        default=128,
        help="Render samples.",
    )
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
        bpy.data.meshes,
        bpy.data.curves,
        bpy.data.materials,
        bpy.data.lights,
        bpy.data.cameras,
        bpy.data.images,
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
    name,
    base_color,
    roughness=0.45,
    metallic=0.0,
    emission_color=None,
    emission_strength=0.0,
    alpha=1.0,
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
        mat.blend_method = "BLEND"
        mat.shadow_method = "HASHED"

    links.new(bsdf.outputs["BSDF"], output.inputs["Surface"])
    return mat


def look_at(obj, target):
    direction = target - obj.location
    obj.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()


def create_cube(name, location, scale, rotation=(0.0, 0.0, 0.0)):
    bpy.ops.mesh.primitive_cube_add(location=location, rotation=rotation)
    obj = bpy.context.active_object
    obj.name = name
    obj.scale = scale
    apply_scale(obj)
    return obj


def create_cylinder(name, location, radius, depth, vertices=32, rotation=(0.0, 0.0, 0.0)):
    bpy.ops.mesh.primitive_cylinder_add(
        vertices=vertices, radius=radius, depth=depth, location=location, rotation=rotation
    )
    obj = bpy.context.active_object
    obj.name = name
    return obj


def create_curve(name, points, material, bevel_depth=0.02):
    curve_data = bpy.data.curves.new(name=name, type="CURVE")
    curve_data.dimensions = "3D"
    curve_data.resolution_u = 18
    curve_data.bevel_depth = bevel_depth
    curve_data.bevel_resolution = 6

    spline = curve_data.splines.new("BEZIER")
    spline.bezier_points.add(len(points) - 1)
    for bp, point in zip(spline.bezier_points, points):
        bp.co = point
        bp.handle_left_type = "AUTO"
        bp.handle_right_type = "AUTO"

    obj = bpy.data.objects.new(name, curve_data)
    bpy.context.collection.objects.link(obj)
    assign_material(obj, material)
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
    background.inputs[0].default_value = (0.014, 0.022, 0.036, 1.0)
    background.inputs[1].default_value = 0.9
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
    except TypeError:
        pass
    except ValueError:
        pass


def build_scene():
    clear_scene()
    setup_world()

    dark_metal = make_principled_material(
        "DarkMetal", base_color=(0.07, 0.08, 0.1), roughness=0.28, metallic=0.85
    )
    panel_metal = make_principled_material(
        "PanelMetal", base_color=(0.13, 0.16, 0.2), roughness=0.38, metallic=0.55
    )
    accent_blue = make_principled_material(
        "AccentBlue",
        base_color=(0.05, 0.18, 0.34),
        roughness=0.15,
        metallic=0.0,
        emission_color=(0.12, 0.85, 1.0),
        emission_strength=8.0,
    )
    accent_orange = make_principled_material(
        "AccentOrange",
        base_color=(0.32, 0.12, 0.02),
        roughness=0.2,
        metallic=0.0,
        emission_color=(1.0, 0.34, 0.05),
        emission_strength=6.5,
    )
    ground_mat = make_principled_material(
        "Ground", base_color=(0.045, 0.05, 0.06), roughness=0.82, metallic=0.0
    )

    bpy.ops.mesh.primitive_plane_add(size=24, location=(0, 0, -0.18))
    ground = bpy.context.active_object
    ground.name = "GroundPlane"
    assign_material(ground, ground_mat)

    base = create_cylinder("BasePlatform", (0, 0, 0.0), radius=2.8, depth=0.38, vertices=6)
    assign_material(base, dark_metal)
    add_bevel(base, width=0.05, segments=4)
    shade_smooth(base)

    top_plate = create_cylinder("TopPlate", (0, 0, 0.26), radius=2.15, depth=0.12, vertices=6)
    assign_material(top_plate, panel_metal)
    add_bevel(top_plate, width=0.04, segments=4)
    shade_smooth(top_plate)

    core_base = create_cylinder("CoreBase", (0, 0, 0.73), radius=0.7, depth=0.82, vertices=12)
    assign_material(core_base, dark_metal)
    add_bevel(core_base, width=0.03, segments=3)
    shade_smooth(core_base)

    core_light = create_cylinder("CoreLight", (0, 0, 1.05), radius=0.24, depth=1.55, vertices=24)
    assign_material(core_light, accent_blue)
    shade_smooth(core_light)

    bpy.ops.mesh.primitive_torus_add(
        location=(0, 0, 1.0),
        major_radius=0.9,
        minor_radius=0.06,
        major_segments=48,
        minor_segments=18,
    )
    energy_ring = bpy.context.active_object
    energy_ring.name = "EnergyRing"
    assign_material(energy_ring, accent_orange)
    shade_smooth(energy_ring)

    pillar_positions = [
        Vector((1.55, 1.55, 0.72)),
        Vector((-1.55, 1.55, 0.72)),
        Vector((-1.55, -1.55, 0.72)),
        Vector((1.55, -1.55, 0.72)),
    ]

    for index, pos in enumerate(pillar_positions, start=1):
        pillar = create_cube(f"Pillar_{index}", tuple(pos), (0.18, 0.18, 0.72))
        assign_material(pillar, panel_metal)
        add_bevel(pillar, width=0.025, segments=3)
        shade_smooth(pillar)

        cap = create_cube(f"PillarCap_{index}", (pos.x, pos.y, 1.46), (0.24, 0.24, 0.09))
        assign_material(cap, dark_metal)
        add_bevel(cap, width=0.02, segments=3)
        shade_smooth(cap)

        light_strip = create_cube(
            f"LightStrip_{index}",
            (pos.x * 0.95, pos.y * 0.95, 0.95),
            (0.03, 0.03, 0.48),
            rotation=(0.0, 0.0, math.radians(45)),
        )
        assign_material(light_strip, accent_blue if index % 2 else accent_orange)

        mid_point = Vector((pos.x * 0.58, pos.y * 0.58, 0.55))
        create_curve(
            f"Cable_{index}",
            [Vector((0, 0, 0.9)), mid_point, Vector((pos.x, pos.y, 1.32))],
            dark_metal,
            bevel_depth=0.025,
        )

    crate_specs = [
        ((1.65, -0.25, 0.42), (0.34, 0.34, 0.24), accent_orange),
        ((-1.2, -1.0, 0.39), (0.28, 0.28, 0.21), accent_blue),
        ((-0.55, 1.45, 0.36), (0.22, 0.22, 0.18), accent_orange),
    ]
    for index, (location, scale, accent_mat) in enumerate(crate_specs, start=1):
        crate = create_cube(f"Crate_{index}", location, scale, rotation=(0.0, 0.0, math.radians(18 * index)))
        assign_material(crate, panel_metal)
        add_bevel(crate, width=0.02, segments=3)
        shade_smooth(crate)
        panel = create_cube(
            f"CratePanel_{index}",
            (location[0], location[1], location[2] + scale[2] + 0.01),
            (scale[0] * 0.55, scale[1] * 0.55, 0.015),
            rotation=(0.0, 0.0, math.radians(18 * index)),
        )
        assign_material(panel, accent_mat)

    bpy.ops.object.empty_add(type="PLAIN_AXES", location=(0, 0, 0.9))
    focus_target = bpy.context.active_object
    focus_target.name = "FocusTarget"

    bpy.ops.object.camera_add(location=(6.3, -6.1, 4.35))
    camera = bpy.context.active_object
    camera.name = "PortfolioCamera"
    camera.data.lens = 58
    camera.data.dof.use_dof = True
    camera.data.dof.focus_object = focus_target
    camera.data.dof.aperture_fstop = 2.8
    look_at(camera, focus_target.location)
    bpy.context.scene.camera = camera

    bpy.ops.object.light_add(type="AREA", location=(4.6, -4.8, 5.6))
    key_light = bpy.context.active_object
    key_light.data.energy = 3000
    key_light.data.color = (0.85, 0.92, 1.0)
    key_light.data.shape = "RECTANGLE"
    key_light.data.size = 5.5
    key_light.data.size_y = 3.0
    look_at(key_light, Vector((0, 0, 0.9)))

    bpy.ops.object.light_add(type="AREA", location=(-4.5, 5.0, 3.8))
    rim_light = bpy.context.active_object
    rim_light.data.energy = 1400
    rim_light.data.color = (0.15, 0.7, 1.0)
    rim_light.data.shape = "RECTANGLE"
    rim_light.data.size = 4.5
    rim_light.data.size_y = 2.5
    look_at(rim_light, Vector((0, 0, 1.0)))

    bpy.ops.object.light_add(type="POINT", location=(0, 0, 1.1))
    core_light_obj = bpy.context.active_object
    core_light_obj.data.energy = 700
    core_light_obj.data.color = (0.35, 0.9, 1.0)
    core_light_obj.data.shadow_soft_size = 0.3

    bpy.ops.object.light_add(type="POINT", location=(1.0, -2.8, 1.6))
    fill_light = bpy.context.active_object
    fill_light.data.energy = 260
    fill_light.data.color = (1.0, 0.42, 0.1)
    fill_light.data.shadow_soft_size = 0.6


def main():
    args = parse_args()
    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    blend_path = output_dir / "extraction_beacon_portfolio.blend"
    render_path = output_dir / "extraction_beacon_portfolio.png"

    build_scene()
    setup_render(args.engine, args.samples, render_path)

    bpy.ops.wm.save_as_mainfile(filepath=str(blend_path))
    bpy.ops.render.render(write_still=True)

    print(f"Saved blend file: {blend_path}")
    print(f"Saved render: {render_path}")


if __name__ == "__main__":
    main()
