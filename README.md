# Blender Portfolio — Procedural 3D Art & Game Assets

Fully procedural 3D scenes and game assets generated with **Blender 5.0** and Python scripting. Every model, material, and light is created from code — no manual modeling required.

---

## Showcase

### Extraction Beacon Diorama

A sci-fi extraction beacon built entirely through `bpy` — hexagonal platform, energy core, support pillars, cable routing, crate geometry, and cinematic studio lighting with depth of field.

![Extraction Beacon](renders/extraction_beacon.png)

---

### VoxelCraft Enemy Roster

Low-poly procedural enemy models designed for [VoxelCraft: Core Runner](https://github.com/BrianDruciak/VoxelWorld), a Minecraft-style voxel sandbox built in Godot 4.6.

| Thorn Crawler | Frost Wraith | Ember Golem | Void Stalker |
|:---:|:---:|:---:|:---:|
| ![Thorn Crawler](renders/game_assets/enemy_thorn_crawler.png) | ![Frost Wraith](renders/game_assets/enemy_frost_wraith.png) | ![Ember Golem](renders/game_assets/enemy_ember_golem.png) | ![Void Stalker](renders/game_assets/enemy_void_stalker.png) |
| Forest zone bruiser with spiked shell | Glacial zone phantom with ice shards | Volcanic zone tank with magma cracks | End-game wraith trailing void wisps |

---

### Crystal Pickups

Collectible ore crystals that spawn across the world — each zone has a unique shard variant with emissive glow and point lighting.

![Crystal Pickups](renders/game_assets/crystal_pickups.png)

---

### Tool Tiers

Tiered pickaxe set progressing through the game's resource tree: Wood, Crystal, Frost, Ember, and Void.

![Tool Tiers](renders/game_assets/tool_tiers.png)

---

## Repo Structure

```
BlenderPortfolio/
├── scripts/                  # Blender Python source files
│   ├── extraction_beacon.py  # Sci-fi diorama generator
│   └── game_assets.py        # Enemy, crystal, and tool generators
├── blend_files/              # Saved .blend scenes (open in Blender 5.0+)
│   ├── extraction_beacon.blend
│   └── game_assets/
│       ├── enemy_thorn_crawler.blend
│       ├── enemy_frost_wraith.blend
│       ├── enemy_ember_golem.blend
│       ├── enemy_void_stalker.blend
│       ├── crystal_pickups.blend
│       └── tool_tiers.blend
└── renders/                  # Final PNG renders
    ├── extraction_beacon.png
    └── game_assets/
        ├── enemy_thorn_crawler.png
        ├── enemy_frost_wraith.png
        ├── enemy_ember_golem.png
        ├── enemy_void_stalker.png
        ├── crystal_pickups.png
        └── tool_tiers.png
```

## Running the Scripts

Requires **Blender 5.0+** with Python `bpy` available.

```bash
# Render the extraction beacon diorama
blender --factory-startup -b -P scripts/extraction_beacon.py -- --samples 128

# Render all game assets
blender --factory-startup -b -P scripts/game_assets.py
```

## Tech Stack

- **Blender 5.0** — EEVEE Next renderer
- **Python 3.x** — `bpy`, `mathutils`
- Principled BSDF materials with emission, transparency, and metallic workflows
- Procedural geometry: bevels, smooth shading, hexagonal platforms, cable paths
- Studio lighting: area lights, point lights, depth of field

## License

MIT

## Author

**Brian Druciak** — [GitHub](https://github.com/BrianDruciak)
