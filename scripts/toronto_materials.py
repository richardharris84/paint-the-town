import struct
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image
from project_paths import ASSETS


@dataclass(frozen=True)
class MaterialZone:
    wall: str
    floor: str
    ceiling: str
    light: int


ZONES = {
    "union_plaza": MaterialZone("UWLIMEX", "UFPLAZA", "F_SKY1", 224),
    "union_hall": MaterialZone("UWZUMBR", "UFMARBL", "UFCOFFR", 208),
    "union_concourse": MaterialZone("UWCONCR", "UFTERRZ", "UFCOFFR", 208),
    "union_platform": MaterialZone("UWPLATF", "UFCONCT", "UFCONCT", 192),
    "rom_forecourt": MaterialZone("RWSANDS", "RFSLABS", "F_SKY1", 224),
    "rom_crystal": MaterialZone("RWMETAL", "RFSLABS", "RFACOUS", 216),
    "rom_rotunda": MaterialZone("RWLIMES", "RFMARBL", "RFGOLD", 208),
    "rom_gallery": MaterialZone("RWPLAST", "RFSLABS", "RFACOUS", 208),
    "rom_heritage": MaterialZone("RWSANDS", "RFMARBL", "RFACOUS", 200),
    "zoo_entry": MaterialZone("ZWCONCT", "ZFASPH", "F_SKY1", 224),
    "zoo_path": MaterialZone("ZWSTONE", "ZFASPH", "F_SKY1", 224),
    "zoo_habitat": MaterialZone("ZWCEDAR", "ZFEARTH", "F_SKY1", 216),
    "zoo_meadow": MaterialZone("ZWSTONE", "ZFGRASS", "F_SKY1", 224),
    "zoo_pavilion": MaterialZone("ZWGLASS", "ZFCONCT", "ZFROOF", 208),
}

# Four wall samples, then floor/ceiling samples, in each 4-by-2 source atlas.
WALL_SAMPLES = {
    "materials_union.png": ("UWZUMBR", "UWLIMEX", "UWCONCR", "UWPLATF"),
    "materials_rom.png": ("RWLIMES", "RWSANDS", "RWMETAL", "RWPLAST"),
    "materials_zoo.png": ("ZWSTONE", "ZWCEDAR", "ZWCONCT", "ZWGLASS"),
}
FLAT_SAMPLES = {
    "materials_union.png": ((4, "UFMARBL"), (5, "UFTERRZ"), (6, "UFPLAZA"),
                            (7, "UFCOFFR"), (3, "UFCONCT")),
    "materials_rom.png": ((4, "RFMARBL"), (5, "RFSLABS"), (6, "RFGOLD"), (7, "RFACOUS")),
    "materials_zoo.png": ((4, "ZFASPH"), (5, "ZFEARTH"), (6, "ZFGRASS"),
                          (7, "ZFROOF"), (2, "ZFCONCT")),
}
MAP_SKIES = {
    "E1M1": ("Union Station", "TSKYUNI"),
    "E1M2": ("Royal Ontario Museum", "TSKYROM"),
    "E1M3": ("Toronto Zoo", "TSKYZOO"),
}
# The AI sky atlas has unequal strip heights; crop actual boundaries, not thirds.
SKY_BOUNDS = ((0, 333), (333, 630), (630, 940))


def zone_for(map_name, row, col):
    if map_name == "E1M1":
        name = ("union_plaza" if row == 0 else
                "union_hall" if row <= 2 else
                "union_concourse" if row == 3 else "union_platform")
    elif map_name == "E1M2":
        name = ("rom_forecourt" if row == 0 else
                "rom_crystal" if row == 1 else
                "rom_rotunda" if row == 2 and col == 2 else
                "rom_heritage" if row == 4 or (row == 2 and col < 2) else "rom_gallery")
    elif map_name == "E1M3":
        name = ("zoo_entry" if row == 0 else
                "zoo_pavilion" if row == 3 and col in (1, 2) else
                "zoo_meadow" if row >= 4 else
                "zoo_habitat" if col in (0, 4) else "zoo_path")
    else:
        raise ValueError(f"No site materials for map {map_name}")
    return ZONES[name]


def _tile_edges(image, vertical):
    pixels = np.array(image, dtype=np.float64)
    for axis in ((1, 0) if vertical else (1,)):
        length = pixels.shape[axis]
        blend = max(2, length // 16)
        for distance in range(blend):
            low = [slice(None)] * 3
            high = [slice(None)] * 3
            low[axis], high[axis] = distance, length - 1 - distance
            a, b = pixels[tuple(low)].copy(), pixels[tuple(high)].copy()
            weight = 0.5 * (1 - distance / blend) ** 2
            pixels[tuple(low)] = a * (1 - weight) + b * weight
            pixels[tuple(high)] = b * (1 - weight) + a * weight
    return Image.fromarray(np.rint(pixels).astype(np.uint8))


def _sample_tiles(filename):
    with Image.open(ASSETS / filename) as source:
        image = source.convert("RGB")
    return [
        image.crop((round(col * image.width / 4) + 2,
                    round(row * image.height / 2) + 2,
                    round((col + 1) * image.width / 4) - 2,
                    round((row + 1) * image.height / 2) - 2))
        for row in range(2) for col in range(4)
    ]


def material_images(palette_bytes):
    palette = Image.new("P", (1, 1))
    palette.putpalette(palette_bytes)

    def indexed(image, size, vertical=False, sky=False):
        if sky:
            pixels = np.array(image, dtype=np.float64)
            blue = (pixels[:, :, 2] > pixels[:, :, 0] + 10) & (pixels[:, :, 2] > pixels[:, :, 1] + 8)
            grey = pixels @ np.array([0.299, 0.587, 0.114])
            # PLAYPAL's lavender ramp cannot represent daylight blue. Grade only
            # the open sky toward natural overcast grey, retaining foliage colour.
            pixels[blue] = pixels[blue] * 0.15 + grey[blue, None] * 0.85
            image = Image.fromarray(np.rint(pixels).astype(np.uint8))
        image = image.resize(size, Image.Resampling.LANCZOS)
        image = _tile_edges(image, vertical)
        return image.quantize(palette=palette, dither=Image.Dither.NONE)

    walls, flats = {}, {}
    for filename, names in WALL_SAMPLES.items():
        tiles = _sample_tiles(filename)
        for index, name in enumerate(names):
            walls[name] = indexed(tiles[index], (128, 128))
        for index, name in FLAT_SAMPLES[filename]:
            flats[name] = indexed(tiles[index], (64, 64), vertical=True)
    with Image.open(ASSETS / "skies_toronto.png") as source:
        sky = source.convert("RGB")
    if sky.size != (1672, 940):
        raise ValueError("Sky source dimensions changed; review the panorama crop bounds")
    for (_, name), (top, bottom) in zip(MAP_SKIES.values(), SKY_BOUNDS):
        walls[name] = indexed(sky.crop((0, top, sky.width, bottom)), (1024, 128), sky=True)
    return walls, flats


def texture_records(data):
    count = struct.unpack_from("<i", data)[0]
    if count < 0 or 4 + count * 4 > len(data):
        raise ValueError("Invalid source texture directory")
    records = []
    for index in range(count):
        offset = struct.unpack_from("<i", data, 4 + index * 4)[0]
        if offset < 4 + count * 4 or offset + 22 > len(data):
            raise ValueError("Invalid source texture record")
        patches = struct.unpack_from("<h", data, offset + 20)[0]
        end = offset + 22 + patches * 10
        if patches < 0 or end > len(data):
            raise ValueError("Invalid source texture patch list")
        records.append(data[offset:end])
    return records


def _texture_directory(records):
    offset = 4 + len(records) * 4
    offsets = []
    for record in records:
        offsets.append(offset)
        offset += len(record)
    return struct.pack("<i", len(records)) + b"".join(struct.pack("<i", n) for n in offsets) + b"".join(records)


def material_lumps(iwad, encode_patch, images=None):
    walls, flats = material_images(iwad["PLAYPAL"][:768]) if images is None else images
    pnames = iwad["PNAMES"]
    count = struct.unpack_from("<i", pnames)[0]
    if count < 0 or len(pnames) != 4 + count * 8 or count + len(walls) > 32767:
        raise ValueError("Invalid or oversized source patch-name directory")
    names = [pnames[4 + i * 8:12 + i * 8] for i in range(count)]
    records = texture_records(iwad["TEXTURE1"])
    existing = {record[:8].rstrip(b"\0").decode("ascii") for record in records}
    if "TEXTURE2" in iwad:
        existing.update(record[:8].rstrip(b"\0").decode("ascii")
                        for record in texture_records(iwad["TEXTURE2"]))
    lumps = []
    for name, image in walls.items():
        if name in existing or name.encode("ascii").ljust(8, b"\0") in names:
            raise ValueError(f"Custom material collides with an IWAD resource: {name}")
        encoded = name.encode("ascii").ljust(8, b"\0")
        # Stack ordinary short patches rather than relying on port-specific tall posts.
        pieces = [(0, image)] if image.height <= 256 else [
            (y, image.crop((0, y, image.width, min(y + 128, image.height))))
            for y in range(0, image.height, 128)]
        placements = []
        for index, (y, piece) in enumerate(pieces):
            patch_name = name if index == 0 else f"{name[:6]}{index:02}"
            patch_name_bytes = patch_name.encode("ascii").ljust(8, b"\0")
            if patch_name_bytes in names:
                raise ValueError(f"Custom patch collides with an existing resource: {patch_name}")
            placements.append(struct.pack("<5h", 0, y, len(names), 0, 0))
            names.append(patch_name_bytes)
            pixels = piece.tobytes()
            alpha = piece.convert("RGBA").getchannel("A").tobytes()
            pixels = [pixel if opacity else None for pixel, opacity in zip(pixels, alpha)]
            canvas = [pixels[row * piece.width:(row + 1) * piece.width]
                      for row in range(piece.height)]
            lumps.append((patch_name, encode_patch(canvas, (0, 0))))
        records.append(struct.pack("<8sihhih", encoded, 0, image.width, image.height, 0, len(pieces))
                       + b"".join(placements))
    lumps.extend((
        ("PNAMES", struct.pack("<i", len(names)) + b"".join(names)),
        ("TEXTURE1", _texture_directory(records)),
        ("F_START", b""),
    ))
    lumps.extend((name, image.tobytes()) for name, image in flats.items())
    lumps.append(("F_END", b""))
    mapinfo = "\n".join(
        f'map {map_name}\n{{\n    levelname = "{title}"\n    skytexture = "{sky}"\n}}\n'
        for map_name, (title, sky) in MAP_SKIES.items()
    )
    lumps.append(("UMAPINFO", mapinfo.encode("ascii")))
    return lumps
